import re
from typing import Optional

from email.utils import formatdate
from time import time

VALID_SAMESITE_VALUES = {"Strict", "Lax", "None"}

# Регулярное выражение для проверки формата даты истечения срока действия cookie
_PATTERN = r'^[A-Za-z]{3},\s\d{2}\s[A-Za-z]{3}\s\d{4}\s\d{2}:\d{2}:\d{2}\sGMT$'

class Cookie:
    """
    Класс для представления HTTP cookie.
    """
    def __init__(self, key, value: str = "", expires: Optional[str] = None,
                 max_age: Optional[int] = None, path: str = None,
                 domain: str = None, http_only: bool = None,
                 secure: bool = None, samesite: Optional[str] = None):
        """
        Инициализация объекта cookie.

        :param key: Название cookie
        :param value: Значение cookie
        :param expires: Дата истечения срока действия в формате 'Day, DD Mon YYYY HH:MM:SS GMT'
        :param max_age: Максимальное время жизни в секундах
        :param path: Доступный путь для cookie
        :param domain: Домен, для которого действует cookie
        :param http_only: Флаг HttpOnly (доступен только через HTTP)
        :param secure: Флаг Secure (отправляется только по HTTPS)
        :param samesite: Политика SameSite ('Strict', 'Lax' или 'None')
        """
        self.key = key
        self.value = value
        self.expires = expires
        self.max_age = max_age
        self.path = path
        self.domain = domain
        self.http_only = http_only
        self.secure = secure
        self.samesite = samesite

    def generate_cookie_data(self):
        """
        Генерирует строку cookie для заголовка Set-Cookie.

        :return: Строка cookie с параметрами
        """
        cookie_data = f"{self.key}={self.value}"

        if self.expires:
            try:
                if not re.match(_PATTERN, self.expires):
                    raise ValueError
                cookie_data += f"; Expires={self.expires}"
            except ValueError:
                cookie_data += f"; Expires={formatdate(time(), usegmt=True)}"  # Устанавливаем текущее GMT-время
        if self.max_age is not None:
            cookie_data += f"; Max-Age={self.max_age}"
        if self.path:
            cookie_data += f"; Path={self.path}"
        if self.domain:
            cookie_data += f"; Domain={self.domain}"
        if self.http_only:
            cookie_data += "; HttpOnly"
        if self.secure:
            cookie_data += "; Secure"
        if self.samesite:
            if self.samesite not in VALID_SAMESITE_VALUES:
                raise ValueError("SameSite must be 'Strict', 'Lax', or 'None'")
            cookie_data += f"; SameSite={self.samesite}"

        return cookie_data