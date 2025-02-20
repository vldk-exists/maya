# Импорты
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

# Статус коды и сообщения которые они отображают по умолчанию
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
    Класс для создания и управления сокетом сервера.

    Атрибуты:
        socket (socket): Сокет IPv4, TCP(с заранее подготовленным биндом).

    Методы:
        listen(): Начинает слущать входящие соединения.
    """
    def __init__(self, addr:str = "127.0.0.1", port:int = 80):
        """
        Инициализирует новый совет IPv4, TCP и биндит его.

        :param addr: Адрес сокета, по умолчанию "127.0.0.1".
        :param port: Порт сокета(Число от 1 до 65537), по умолчанию 80.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((addr, port))

    def listen(self, max_connections:int = socket.SOMAXCONN):
        """
        Начинает слушать входящие соединения.

        :param max_connections: Максимальное колличество соединение которое может обработать за раз сокет, по умолчанию равен socket.SOMAXCONN .
        """
        self.socket.listen(max_connections)
        return self.socket

class String:
    """
    Класс-обёртка для строк, запрещает использование символа '/'.
    """
    def __init__(self, string: str):
        self.string = html.escape(string)

    def __str__(self):
        return self.string


class Path:
    """
    Класс для представления пути, требует наличие символа '/'.
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

# Типы данных для удобного использования в парсинге динамических ссылок
types = {
    "int": int,
    "String": String,
    "float": float,
    "path": Path,
    "uuid": UUID
}

def check_if_template(path):
    """
    Проверяет, содержит ли URL шаблонный параметр вида <type:name>.

    :param path: Путь который нужно проверить на наличие динамических параметров.
    """
    pattern = r"<([a-zA-Z_]+):([a-zA-Z_]+)>"
    match = re.search(pattern, path)

    return match is not None

def check_if_dynamic_parameters(path, template):
    """
    Проверяет, соответствует ли URL шаблону с динамическими параметрами.

    :param path: Путь который нужно проверить на сходство с шаблоном template.
    :param template: Шаблон.
    """
    regex_pattern = "^" + re.sub(
        r"<([a-zA-Z_]+):([a-zA-Z_]+)>",
        lambda m: f"(?P<{m.group(2)}>[^/]+)",
        template
    ) + "$"

    return re.match(regex_pattern, path)

def parse_dynamic_parameters(match, template):
    """
    Извлекает параметры из динамического URL и приводит их к нужным типам.

    :param match: Результат функции chech_if_dynamic_parameters.
    :param template: Шаблон который задаёт правила парсинга первого параметра.
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
    Считывает HTTP-запрос от клиента, поддерживает обработку тела запроса.

    :param conn: Соиденённый сокет с сокетом клиента который должен получить информацию о запросе.
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

# Ошибки для удобной обработки событий
class BadRequest(Exception):
    """
    Ошибка которая появляеться во время некоректного клиент-запроса(используеться исключительно для обработки собитый)
    """
    def __init__(self):
        self.message = "Bad Request"
        super().__init__(self.message)

class IntenralServerError(Exception):
    """
    Ошибка которая появляеться во время ошибки сервера(используеться исключительно для обработки собитый)

    Аттрибуты:
        e (Exception): Ошибка которая и вызвала InternalServerError
    """
    def __init__(self, e: Exception):
        self.e = e
        self.message = "Internal Server Error"
        super().__init__(self.message)

class PrematureResponse(Exception):
    """
    Ошибка которая говорит о преждевременном возврате ответа сервера(используеться исключительно для обработки собитый)

    Аттрибуты:
        r (Response): ответ сервера
    """
    def __init__(self, r: Response):
        self.r = r
        self.message = "Premature Return Of Response"
        super().__init__(self.message)

from flask import Flask

class WebServer:
    """
    Основной класс веб-сервера. Управляет обработчиками маршрутов и запросами.

    Методы:
        run(addr:str = "127.0.0.1", port:int = 80, debug: bool = False): Запускает сервер на указанном адресе и порту.
        handle_request(conn, addr, debug): Обрабатывает входящий HTTP-запрос, вызывает соответствующий обработчик.
        before_request(f: Callable): Добавляет обработчик в очередь обработчиков что выполняються до запроса.
        after_request(f: Callable): Добавляет обработчик в очередь обработчиков что выполняються после запроса.
        add_route(path: str, handler: Callable): Добавляет обработчик и путь что он обрабатывает в словарь маршрутизации.
        add_status_handler(status_code: int, handler: Callable): Добавляет обработчик и статус код что он обрабатывает в словарь маршрутизации статус кодов.
        add_status_handler(status_code: int, handler: Callable): Добавляет обработчик и статус код что он обрабатывает в словарь маршрутизации.
        add_static_file(path): Добавляет обработчик для статического файла что он отправляет, в словарь маршрутизации.
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
        Запускает сервер на указанном адресе и порту.

        :param addr: Адрес веб-сервера.
        :param port: Порт веб-сервера.
        :param debug: Режим дебаггинга.
        """
        if not (1 <= port <= 65535):
            raise ValueError("Port must be in diapason from 1 to 65535")

        serversocket = ServerSocket(addr, port).listen()

        if not self.__url_patterns:
            print(Fore.YELLOW + "WARNING:")
            print("Сервер не нашёл обработчиков. Каждая ссылка будет сопровождаться 404 статусом. Пожайлуста добавьте обработчиков через .set_url_patterns(...)" + Fore.RESET)

        print(Fore.GREEN+ f"Сервер запущен и доступен здесь - http://{addr}:{port}" + Fore.RESET)
        if debug:
            print(Fore.BLUE+ "Debug режим включён" + Fore.RESET)
        print(Fore.RED + "Ctrl + C -> Чтобы остановить работу сервера\n" + Fore.RESET)

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
            print(Fore.RED + "Сервер отключён" + Fore.RESET)
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
        Обрабатывает входящий HTTP-запрос, вызывает соответствующий обработчик.

        :param conn: Соиденённый сокет с сокетом клиента который должен получить информацию о запросе.
        :param addr: Адрес и порт сокета.
        :param debug: Режим дебаггинга.
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

    # TODO: Обновить докстринги, зделать их более подробными и вставить примеры кода для наглядности