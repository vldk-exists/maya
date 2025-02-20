import urllib.parse
import html
import json
import re

# Lists of MIME types used to determine the content type of a request
BYTES_DATA = ("application/pdf",
              "application/msword",
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              "application/vnd.ms-excel",
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
              "application/zip",
              "application/x-rar-compressed",
              "application/octet-stream",
              "application/gzip",
              "font/woff",
              "font/woff2",
              "application/vnd.ms-fontobject",
              "font/ttf",
              "font/otf",
              "application/x-tar",
              "application/x-shockwave-flash",
              "image/png",
              "image/jpeg",
              "image/gif",
              "image/svg+xml",
              "image/webp",
              "audio/mpeg",
              "audio/ogg",
              "audio/wav",
              "video/mp4",
              "video/webm",
              "video/ogg")

TEXT_DATA = ("text/plain",
            "text/html",
            "text/css",
            "text/javascript",
            "text/csv",
            "application/xml")

FORM_DATA = ("application/x-www-form-urlencoded",)

JSON_DATA = ("application/json",
            "application/ld+json",
             "application/x-ndjson")

def parse_form_data(body: bytes):
    """
    Parses form data (application/x-www-form-urlencoded) from the request body.

    :param body: Binary data of the request body.
    """
    body_content = urllib.parse.parse_qs(body.decode())
    return {
        k.lower(): html.escape(html.unescape(urllib.parse.unquote(v[0])))
        .replace("'", "\\'").replace('"', '\\"').replace("--", "")
        for k, v in body_content.items()
    }

def parse_json_data(body: bytes):
    """
    Parses JSON data from the request body. Supports JSON Lines.

    :param body: Binary data of the request body.
    """
    body = body.decode()
    try:
        return json.loads(body)
    except json.decoder.JSONDecodeError:
        return [json.loads(line) for line in body.split('\n') if line.strip()]

def parse_multipart_formdata(body:bytes, boundary: bytes):
    """
    Parses a multipart/form-data request, handling the nested data.

    :param body: Binary data of the request body.
    :param boundary: Binary data of the multipart boundary.
    """
    result = {}
    parts = body.split(b"--" + boundary)

    for part in parts:
        part = part.strip()
        if not part or part == b'--':
            continue

        headers, _, content = part.partition(b"\r\n\r\n")
        if not headers:
            continue

        content_disposition = re.search(rb'Content-Disposition: (.+)', headers, re.IGNORECASE)
        if not content_disposition:
            continue

        disposition_parts = content_disposition.group(1).split(b";")
        field_name = None
        filename = None

        for part in disposition_parts:
            part = part.strip()
            if part.startswith(b'name='):
                field_name = part.split(b"=", 1)[1].strip(b'"')
            elif part.startswith(b'filename='):
                filename = part.split(b"=", 1)[1].strip(b'"')

        if not field_name:
            continue

        if filename:
            result[field_name.decode()] = {"filename": filename.decode(), "content": content}
        else:
            result[field_name.decode()] = content.decode(errors="ignore")

    return result

def parse_query_params(path):
    """
    Extracts query parameters from the URL.

    :param path: The path from which to extract parameters.
    """
    parsed_path = urllib.parse.urlparse(path)

    query = parsed_path.query

    if query:
        return urllib.parse.parse_qs(query)

def parse_cookies(value: str):
    """
    Parses a cookie string into a list of tuples (key, value).

    :param value: The cookie string.
    """
    return [cookie.split("=", 1) for cookie in value.split("; ")]

def parse_request(request_bytes: bytes):
    """
    Parses the HTTP request into its components: method, headers, path, body, and parameters.

    :param request_bytes: Binary data of the request body.
    """
    headers, body = (request_bytes.split(b"\r\n\r\n", 1))
    headers = headers.decode()
    lines = headers.split("\n")
    method, path, version = re.split(r'\s+', lines[0].strip(), maxsplit=2)

    request_dict = {
        "method": method,
        "path": path,
        "version": version,
        "headers": {},
        "args": parse_query_params(path) or {},
        "body": {}
    }

    for line in lines[1:]:
        if ":" in line:
            key, value = map(str.strip, line.split(":", 1))
            request_dict["headers"][key.lower()] = parse_cookies(value) if key.lower() == "cookie" else value

    body_strip = body.strip()
    if body_strip:
        content_type = request_dict["headers"].get("content-type")
        if content_type:
            if any(text_data in content_type for text_data in TEXT_DATA):
                content_type, charset = content_type.split(";") if len(content_type.split(";")) > 1 else [content_type, ""]
                if charset:
                    _, encoding = charset.split("=")
                    body = body.decode(encoding=encoding)
                else:
                    body = body.decode()
                data_type = "text"
            elif content_type in JSON_DATA:
                body = parse_json_data(body_strip)
                data_type = "json"
            elif content_type in BYTES_DATA:
                data_type = "bytes"
            elif content_type in FORM_DATA:
                body = parse_form_data(body_strip)
                data_type = "form"
            elif "multipart/form-data" in content_type:
                boundary_match = re.search(r'boundary=(.+)', content_type, re.IGNORECASE)
                if not boundary_match:
                    raise ValueError("Multipart boundary missing in content-type")
                boundary = boundary_match.group(1)
                body = parse_multipart_formdata(body, boundary.encode())
                data_type = "multiform"
            request_dict["body"][data_type] = body

    return request_dict

class Request:
    """
    A class representing an HTTP request.

    Attributes:
        method (str): The HTTP method of the request (e.g., 'GET', 'POST').
        path (str): The path to the resource being requested.
        version (str): The version of the HTTP protocol.
        headers (dict): The headers of the request.
        args (dict): The query parameters of the request.
        body (str): The body of the request, if present.

    Constructor parameters:
        request_bytes (bytes): The HTTP request in byte form to be parsed.
    """

    def __init__(self, request_bytes):
        """Initializes the request object by parsing the provided HTTP request in bytes."""
        self.__bytes_data = request_bytes
        self.__data = parse_request(request_bytes)
        self.method = self.__data["method"]
        self.path = self.__data["path"]
        self.version = self.__data["version"]
        self.headers = self.__data["headers"]
        self.args = self.__data["args"]
        self.body = self.__data["body"]

    def __bytes__(self):
        """Returns the byte representation of the request."""
        return self.__bytes_data

    def __dict__(self):
        """Returns the dictionary representation of the request."""
        return self.__data