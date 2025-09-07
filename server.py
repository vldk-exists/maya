import threading
import sys
import traceback
import re
import uuid
import html
import socket
import inspect
import mimetypes

from typing import Callable, Optional, Dict, Set
from datetime import datetime
from colorama import Fore

from .request import Request
from .response import render_from_string, render_http_message
from .response import Response

# Status codes and the messages they display by default
STATUS_CODES = {
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',

    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',

    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',
    308: 'Permanent Redirect',

    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Payload Too Large',
    414: 'URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Range Not Satisfiable',
    417: 'Expectation Failed',
    418: "I'm a teapot",
    422: 'Unprocessable Entity',
    429: 'Too Many Requests',

    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
}

class ServerSocket:
    """
    A class for creating and managing a server socket.

    Attributes:
        socket (socket): An IPv4, TCP socket (pre-bound).

    Methods:
        listen(): Starts listening for incoming connections.
    """
    def __init__(self, addr:str = "127.0.0.1", port:int = 80):
        """
        Initializes a new IPv4, TCP socket and binds it.

        :param addr: The socket address, default is "127.0.0.1".
        :param port: The socket port (a number from 1 to 65537), default is 80.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((addr, port))

    def listen(self, max_connections:int = socket.SOMAXCONN):
        """
        Starts listening for incoming connections.

        :param max_connections: The maximum number of connections the socket can handle at a time,
                                defaults to socket.SOMAXCONN.
        """
        self.socket.listen(max_connections)
        return self.socket

class String:
    """
    A wrapper class for strings that disallows the use of the '/' character.
    """
    def __init__(self, string: str):
        self.string = html.escape(string)

    def __str__(self):
        return self.string


class Path:
    """
    A class for representing a path, requiring the presence of the '/' character.
    """
    def __init__(self, path: str):
        if not path.startswith("/"):
            raise ValueError("Path must start with '/'")
        self.path = path

    def __str__(self):
        return self.path


class UUID:
    def __init__(self, uuid_string):
        try:
            parsed_uuid = uuid.UUID(uuid_string)
            if parsed_uuid.version != 4:
                raise ValueError("UUID must be v4")
            self.uuid = parsed_uuid
        except ValueError:
            raise ValueError("UUID invalid")

    def __str__(self):
        return str(self.uuid)

# Data types for convenient use in parsing dynamic links
types = {
    "int": int,
    "String": String,
    "float": float,
    "path": Path,
    "uuid": UUID
}

def check_if_template(path):
    """
    Checks if the URL contains a template parameter in the form <type:name>.

    :param path: The path to check for dynamic parameters.
    """
    pattern = r"<([a-zA-Z_]+):([a-zA-Z_]+)>"
    match = re.search(pattern, path)

    return match is not None

def check_if_dynamic_parameters(path, template):
    """
    Checks if the URL matches the template with dynamic parameters.

    :param path: The path to check for similarity with the template.
    :param template: The template.
    """
    regex_pattern = "^" + re.sub(
        r"<([a-zA-Z_]+):([a-zA-Z_]+)>",
        lambda m: f"(?P<{m.group(2)}>[^/]+)",
        template
    ) + "$"

    return re.match(regex_pattern, path)

def parse_dynamic_parameters(match, template):
    """
    Extracts parameters from a dynamic URL and converts them to the required types.

    :param match: The result of the function check_if_dynamic_parameters.
    :param template: The template that defines the parsing rules for the first parameter.
    """
    params = match.groupdict()
    parsed_params = {}

    for part in template.split("/"):
        if part.startswith("<") and part.endswith(">"):
            type_name, param_name = re.match(r"<([a-zA-Z_]+):([a-zA-Z_]+)>", part).groups()
            param_type = types.get(type_name)
            if param_name in params:
                parsed_params[param_name] = param_type(html.escape(params[param_name]))

    return parsed_params

def read_request(conn):
    """
    Reads an HTTP request from the client, supports processing of the request body.

    :param conn: The connected socket with the client socket that should receive information about the request.
    """
    buffer_size = 1024
    request_bytes = b""

    while True:
        conn.settimeout(5)
        try:
            chunk = conn.recv(buffer_size)
        except socket.timeout:
            return b""
        request_bytes += chunk
        if b"\r\n\r\n" in request_bytes:
            break

    headers, _, body = request_bytes.partition(b"\r\n\r\n")

    content_length = next(
        (int(line.split(b":")[1].strip()) for line in headers.split(b"\r\n") if
         line.lower().startswith(b"content-length:")),
        0
    )

    while len(body) < content_length:
        body += conn.recv(buffer_size)

    return headers + b"\r\n\r\n" + body

# Exceptions for comfortable event handling
class BadRequest(Exception):
    """
    An error that occurs during an incorrect client request (used exclusively for event handling).
    """
    def __init__(self):
        self.message = "Bad Request"
        super().__init__(self.message)

class IntenralServerError(Exception):
    """
    An error that occurs during a server error (used exclusively for event handling).

    Attributes:
        e (Exception): The error that caused the InternalServerError.
    """
    def __init__(self, e: Exception):
        self.e = e
        self.message = "Internal Server Error"
        super().__init__(self.message)

class PrematureResponse(Exception):
    """
    An error that indicates a premature return of the server's response (used exclusively for event handling).

    Attributes:
        r (Response): The server's response.
    """
    def __init__(self, r: Response):
        self.r = r
        self.message = "Premature Return Of Response"
        super().__init__(self.message)

class WebServer:
    """
    The main class of the web server. Manages route handlers and requests.

    Methods:
        run(addr: str = "127.0.0.1", port: int = 80, debug: bool = False): Starts the server on the specified address and port.
        handle_request(conn, addr, debug): Handles an incoming HTTP request, calls the appropriate handler.
        before_request(f: Callable): Adds a handler to the queue of handlers that run before the request.
        after_request(f: Callable): Adds a handler to the queue of handlers that run after the request.
        add_route(path: str, handler: Callable): Adds a handler and the path it handles to the routing dictionary.
        add_status_handler(status_code: int, handler: Callable): Adds a handler and the status code it handles to the routing dictionary of status codes.
        add_static_file(path): Adds a handler for the static file it serves to the routing dictionary.
    """
    __before_request: Set[Callable] = set()
    __after_request: Set[Callable] = set()
    __url_patterns: Dict[str, Callable] = dict()
    __status_patterns: Dict[int, Callable] = dict()

    __is_running = True

    __print_lock = threading.Lock()

    def before_request(self, f: Callable):
        self.__before_request.add(f)

    def after_request(self, f: Callable):
        self.__after_request.add(f)

    def add_route(self, path: str, handler: Callable):
        self.__url_patterns[path] = handler

    def add_status_handler(self, status_code: int, handler: Callable):
        self.__status_patterns[status_code] = handler

    def add_static_file(self, path):
        content_type, encoding = mimetypes.guess_type(path)
        with open(path, "rb") as body:
            body = body.read()
            content_length = len(body)
        headers = [
            ("Content-Type", (content_type + "charset="+encoding if encoding else content_type)),
            ("Content-Length", content_length),
            ("Connection", "close")
        ]
        handler = lambda: Response(headers=headers, status=200, body=body)
        self.__url_patterns["/" + path] = handler

    def run(self, addr:str = "127.0.0.1", port:int = 80, debug:bool = False):
        """
        Starts the server on the specified address and port.

        :param addr: The address of the web server.
        :param port: The port of the web server.
        :param debug: Debugging mode.
        """
        if not (1 <= port <= 65535):
            raise ValueError("Port must be in diapason from 1 to 65535")

        serversocket = ServerSocket(addr, port).listen()

        if not self.__url_patterns:
            print(Fore.YELLOW + "WARNING:")
            print("Server could not find any handlers. Each link will be accompanied by a 404 status. Please add handlers using .set_url_patterns(...)." + Fore.RESET)

        print(Fore.GREEN+ f"Server is running and accessible at http://{addr}:{port}" + Fore.RESET)
        if debug:
            print(Fore.BLUE + "Debug mode is enabled" + Fore.RESET)
        print(Fore.RED + "Ctrl + C -> To stop the server\n" + Fore.RESET)

        try:
            while self.__is_running:
                serversocket.settimeout(1)
                try:
                    conn, addr = serversocket.accept()
                    thread = threading.Thread(target=self.__handle_request, args=(conn, addr, debug), daemon=True)
                    thread.start()
                except socket.timeout:
                    continue

        except KeyboardInterrupt:
            print(Fore.RED + "The server is shut down" + Fore.RESET)
            self.__is_running = False
        finally:
            serversocket.close()
            sys.exit(0)

    def __render_status_code_response(self, status_code):
        return self.__status_patterns[status_code]() if self.__status_patterns and self.__status_patterns.get(
            status_code) else render_from_string(html_string=f"<h1>{STATUS_CODES[status_code]}</h1>",
                                                 status=status_code)

    def __handle_request(self, conn, addr, debug):
        """
        Handles the incoming HTTP request, calls the corresponding handler.

        :param conn: The connected socket with the client socket that should receive information about the request.
        :param addr: The address and port of the socket.
        :param debug: Debugging mode.
        """

        try:
            request_bytes = read_request(conn)

            if not request_bytes or request_bytes == b'\r\n\r\n':
                conn.close()
                return

            try:
                request = Request(request_bytes)
            except Exception:
                raise BadRequest()

            if request.path == "/favicon.ico" or request.headers.get('purpose') and request.headers.get('purpose') == "prefetch":
                conn.close()
                return

            if debug:
                print(Fore.BLUE + f"\n[DEBUG] Incoming Request:"
                                  f"\n  METHOD: {request.method}"
                                  f"\n  PATH: {request.path}"
                                  f"\n  HEADERS: {request.headers}"
                                  f"{f'\n  BODY: {request.body}' if request.body else ''}"
                                  f"{f'\n  QUERY PARAMS: {request.args}' if request.args else ''}"
                                  f"\n  CLIENT IP: {addr[0]}:{addr[1]}" + Fore.RESET)

            if self.__before_request:
                for before_request_handler in self.__before_request:
                    if debug:
                        print(Fore.BLUE + f"\n[DEBUG] Before Request Handler: {before_request_handler}" + Fore.RESET)
                    sig = inspect.signature(before_request_handler)
                    if "request" in sig.parameters:
                        response: Optional[Response] = before_request_handler(request=request)
                    else:
                        response: Optional[Response] = before_request_handler()
                    if response is not None:
                        raise PrematureResponse(response)

            try:
                status_code = 404
                for path, handler in self.__url_patterns.items():
                    match_handler = check_if_dynamic_parameters(request.path, path)
                    query_handler = request.path.split("?")[0] == path and request.args
                    if request.path == path or query_handler or match_handler:
                        if debug:
                            print(Fore.BLUE + f"\n[DEBUG] Matched Handler: {handler}" + Fore.RESET)
                        params = {}
                        if match_handler:
                            params = parse_dynamic_parameters(match_handler, path)
                        if request.method == "HEAD":
                            response = Response()
                        elif request.method == "TRACE":
                            response = render_http_message(request.__str__())
                        else:
                            sig = inspect.signature(handler)
                            if "request" in sig.parameters:
                                response: Optional[Response] = handler(request=request, **(params or {}))
                            else:
                                response: Optional[Response] = handler(**(params or {}))
                        status_code = 200
            except Exception as e:
                raise IntenralServerError(e)

            if status_code != 200:
                response = self.__render_status_code_response(status_code)

            if self.__after_request:
                for after_request_handler in self.__after_request:
                    sig = inspect.signature(after_request_handler)
                    params = sig.parameters.keys()

                    kwargs = {}
                    if "response" in params:
                        kwargs["response"] = response
                    if "request" in params:
                        kwargs["request"] = request
                    if debug:
                        print(Fore.BLUE + f"\n[DEBUG] After Request Handler: {after_request_handler}" + Fore.RESET)
                    response = after_request_handler(**kwargs)
                    if not isinstance(response, Response):
                        raise ValueError("after request function must return Response object")
        except Exception as error:
            if not isinstance(error, PrematureResponse):
                if isinstance(error, BadRequest):
                    status_code = 400
                elif isinstance(error, ConnectionResetError):
                    return
                elif isinstance(error, IntenralServerError):
                    print(Fore.RED + "SERVER ERROR:")
                    print("".join(traceback.format_exception(type(error.e), error.e, error.e.__traceback__)).strip())
                    print(Fore.RESET)
                    status_code = 500
                response = self.__render_status_code_response(status_code)
            else:
                response = error.r
        if debug:
            print(Fore.BLUE + f"\n[DEBUG] Response Info:"
                              f"\n  STATUS: {response.status}"
                              f"\n  HEADERS: {response.headers}"
                              f"{f'\n  BODY: {response.body}' if response.body else ''}" + Fore.RESET)
        conn.sendall(response.render_response())
        with self.__print_lock:
            print((Fore.GREEN if status_code == 200 else Fore.RED if status_code == 500 else Fore.YELLOW) +
                  (f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {addr[0]}: '{request.path}' {request.method} -> {status_code}" if status_code != 400 else
                   f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {addr[0]}: '?' ? -> {status_code}") +
                  Fore.RESET)
        conn.close()
