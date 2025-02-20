import json
from jinja2 import BaseLoader, FileSystemLoader, Environment
from typing import List, Tuple, TypeVar, Optional, Union
from .cookies import Cookie

T = TypeVar('T')

class Response:
    """
    A class representing an HTTP response. Encapsulates version, status, headers, and body of the response.

    Attributes:
        version (str): The HTTP version (default is "HTTP/1.1").
        status (int): The HTTP status code (default is 200).
        headers (Optional[List[Tuple[str, T]]]): The HTTP headers as a list of tuples, where each tuple contains a header name and its value.
        body (str): The body of the HTTP response (e.g., HTML, JSON).
    """
    DEFAULT_VERSION = "HTTP/1.1"  # Стандартная версия HTTP
    DEFAULT_STATUS = 200  # Стандартный статус HTTP (ОК)
    EMPTY_BODY_STATUS = 204 # Статус код при пустом теле ответа (No Content)
    def __init__(self,
                 headers:Optional[List[Tuple[str, T]]] = None,
                 version:str = DEFAULT_VERSION,
                 status:int = DEFAULT_STATUS,
                 body:Optional[Union[str, bytes]] = None):
        """
        Initializes the Response object.

        :param headers: A list of HTTP headers. Default is None.
        :param version: The HTTP version. Default is "HTTP/1.1".
        :param status: The HTTP status code. Default is 200.
        :param body: The body of the HTTP response. Default is None.
        """
        self.version = version
        self.status = status or (self.EMPTY_BODY_STATUS if not body else self.DEFAULT_STATUS)
        self.headers = headers
        self.body = body

    def render_response(self):
        """
         Generates the HTTP response as a string.
        """
        response = f"{self.version} {self.status}\r\n"
        for header, value in self.headers:
            response += f"{header}: {value}\r\n"
        response_bytes = response.encode()
        if self.body:
            response_bytes += b"\r\n"

            if isinstance(self.body, bytes):
                response_bytes += self.body
            elif isinstance(self.body, (str, int, float, bool)):
                response_bytes += str(self.body).encode()
            elif isinstance(self.body, dict) or isinstance(self.body, list):
                import json
                response_bytes += json.dumps(self.body, ensure_ascii=False).encode()
            else:
                response_bytes += repr(self.body).encode()
        return response_bytes

def render_template(page_path, status: int = Response.DEFAULT_STATUS, cookies: List[Cookie] = None, loader:str = None, **kwargs):
    """
    Generates an HTML page from a template, using the provided context and cookies.

    :param page_path: The path to the HTML template file.
    :param status: The HTTP status code. Default is 200.
    :param cookies: A list of cookies to set in the response. Default is None.
    :param kwargs: Arbitrary arguments to be passed to the template for rendering.
    :param loader: The path from which files will be imported (for Jinja2 usage).
    """
    with open(page_path, "r", encoding="utf-8") as html_document:
        html_document = Environment(loader=BaseLoader() if not loader else FileSystemLoader(loader)).from_string(html_document.read()).render(**kwargs)
        content_length = len(html_document.encode("utf-8"))
        headers = [
            ("Content-Type", "text/html; charset=UTF-8"),
            ("Content-Length", content_length),
            ("Connection", "close")
        ]
        if cookies:
            for cookie in cookies:
                cookie_data = cookie.generate_cookie_data()
                headers.append(("Set-Cookie", cookie_data))
        response = Response(headers=headers,
                            status=status,
                            body=html_document)
        return response

def render_from_string(html_string, status: int = Response.DEFAULT_STATUS, cookies: List[Cookie] = None, loader:str = None, **kwargs):
    """
    Generates an HTML page from a string, using the provided context and cookies.

    :param html_string: HTML content as a string.
    :param status: The HTTP status code. Default is 200.
    :param cookies: A list of cookies to set in the response. Default is None.
    :param kwargs: Arbitrary arguments to be passed to the template for rendering.
    :param loader: The path from which files will be imported (for Jinja2 usage).
    """
    html_document = Environment(loader=BaseLoader() if not loader else FileSystemLoader(loader)).from_string(html_string).render(**kwargs)
    content_length = len(html_document)
    headers = [
        ("Content-Type", "text/html; charset=UTF-8"),
        ("Content-Length", content_length),
        ("Connection", "close")
    ]
    if cookies:
        for cookie in cookies:
            cookie_data = cookie.generate_cookie_data()
            headers.append(("Set-Cookie", cookie_data))
    response = Response(headers=headers,
                        status=status,
                        body=html_document)
    return response

def redirect(location, cookies: List[Cookie] = None):
    """
    Generates a response for redirecting to the specified URL.

    :param location: The URL to which the redirection should occur.
    :param cookies: A list of cookies to set in the response. Default is None.
    """
    status = 302
    headers = [
        ("Location", location),
    ]
    if cookies:
        for cookie in cookies:
            cookie_data = cookie.generate_cookie_data()
            headers.append(("Set-Cookie", cookie_data))
    response = Response(status=status,
                        headers=headers)
    return response

def render_json(json_data, status: int = Response.DEFAULT_STATUS, cookies: List[Cookie] = None):
    """
    Generates a JSON response in the HTTP response.

    :param json_data: The JSON data to be included in the response body.
    :param status: The HTTP status code. Default is 200.
    :param cookies: A list of cookies to set in the response. Default is None.
    """
    json_data = json.dumps(json_data, ensure_ascii=False)
    content_length = len(json_data)
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", content_length),
        ("Connection", "close")
    ]
    if cookies:
        for cookie in cookies:
            cookie_data = cookie.generate_cookie_data()
            headers.append(("Set-Cookie", cookie_data))
    response = Response(headers=headers,
                        status=status,
                        body=json_data)
    return response

def render_http_message(data, status:int = Response.DEFAULT_STATUS, cookies: List[Cookie] = None):
    """
    Generates an HTTP message in the response body.

    :param data: Raw HTTP message data to be included in the body.
    :param status: The HTTP status code. Default is 200.
    :param cookies: A list of cookies to set in the response. Default is None.
    """
    content_length = len(data)
    headers = [
        ("Content-Type", "message/http"),
        ("Content-Length", content_length),
        ("Connection", "close")
    ]
    if cookies:
        for cookie in cookies:
            cookie_data = cookie.generate_cookie_data()
            headers.append(("Set-Cookie", cookie_data))
    response = Response(headers=headers,
                        status=status,
                        body=data)
    return response