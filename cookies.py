import re
from typing import Optional

from email.utils import formatdate
from time import time

VALID_SAMESITE_VALUES = {"Strict", "Lax", "None"}

# Regular expression for validating the expiration date format of a cookie
_PATTERN = r'^[A-Za-z]{3},\s\d{2}\s[A-Za-z]{3}\s\d{4}\s\d{2}:\d{2}:\d{2}\sGMT$'

class Cookie:
    """
    A class for representing an HTTP cookie.
    """
    def __init__(self, key, value: str = "", expires: Optional[str] = None,
                 max_age: Optional[int] = None, path: str = None,
                 domain: str = None, http_only: bool = None,
                 secure: bool = None, samesite: Optional[str] = None):
        """
        Initializes a cookie object.

        :param key: The name of the cookie.
        :param value: The value of the cookie.
        :param expires: The expiration date in the format 'Day, DD Mon YYYY HH:MM:SS GMT'.
        :param max_age: The maximum lifetime in seconds.
        :param path: The path for which the cookie is accessible.
        :param domain: The domain for which the cookie is valid.
        :param http_only: HttpOnly flag (accessible only via HTTP).
        :param secure: Secure flag (sent only over HTTPS).
        :param samesite: The SameSite policy ('Strict', 'Lax', or 'None').
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
        Generates a cookie string for the Set-Cookie header.

        :return: The cookie string with parameters.
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