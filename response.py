import json
from jinja2 import BaseLoader, FileSystemLoader, Environment
from typing import List, Tuple, TypeVar, Optional, Union
from .cookies import Cookie

T = TypeVar('T')

class Response:
    """
    Класс, представляющий HTTP-ответ. Инкапсулирует версию, статус, заголовки и тело ответа.

    Атрибуты:
        version (str): HTTP-версия (по умолчанию "HTTP/1.1").
        status (int): HTTP-статус код (по умолчанию 200).
        headers (Optional[List[Tuple[str, T]]]): Заголовки HTTP как список кортежей, где каждый кортеж состоит из имени заголовка и его значения.
        body (str): Тело HTTP-ответа (например, HTML, JSON).
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
        Инициализация объекта Response.

        :param headers: Список HTTP-заголовков. По умолчанию None.
        :param version: Версия HTTP. По умолчанию "HTTP/1.1".
        :param status: Код HTTP-статуса. По умолчанию 200.
        :param body: Тело HTTP-ответа. По умолчанию None.
        """
        self.version = version
        self.status = status or (self.EMPTY_BODY_STATUS if not body else self.DEFAULT_STATUS)
        self.headers = headers
        self.body = body

    def render_response(self):
        """
        Генерирует HTTP-ответ в виде строки.
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
    Генерирует HTML-страницу из шаблона, используя переданный контекст и cookies.

    :param page_path: Путь к файлу HTML-шаблона.
    :param status: Код статуса HTTP. По умолчанию 200.
    :param cookies: Список cookies, которые нужно установить в ответе. По умолчанию None.
    :param kwargs: Произвольные аргументы, которые будут переданы в шаблон для рендеринга.
    :param loader: Путь по которому будут импортироваться файлы(для работы Jinja2)
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
    Генерирует HTML-страницу из строки, используя переданный контекст и cookies.

    :param html_string: HTML-контент в виде строки.
    :param status: Код статуса HTTP. По умолчанию 200.
    :param cookies: Список cookies, которые нужно установить в ответе. По умолчанию None.
    :param kwargs: Произвольные аргументы, которые будут переданы в шаблон для рендеринга.
    :param loader: Путь по которому будут импортироваться файлы(для работы Jinja2)
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
    Генерирует ответ для перенаправления на указанный адрес.

    :param location: URL, на который нужно выполнить перенаправление.
    :param cookies: Список cookies, которые нужно установить в ответе. По умолчанию None.
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
    Генерирует JSON-ответ в HTTP-ответе.

    :param json_data: Данные в формате JSON, которые будут включены в тело ответа.
    :param status: Код статуса HTTP. По умолчанию 200.
    :param cookies: Список cookies, которые нужно установить в ответе. По умолчанию None.
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
    Генерирует HTTP-сообщение в теле ответа.

    :param data: Сырые данные HTTP-сообщения, которые будут включены в тело.
    :param status: Код статуса HTTP. По умолчанию 200.
    :param cookies: Список cookies, которые нужно установить в ответе. По умолчанию None.
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