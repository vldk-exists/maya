from .server import WebServer
from .cookies import Cookie
from .response import render_from_string, render_template, render_http_message, render_json, redirect

__version__ = "0.0.1"

def __getattr__(name):
    if name == "__version__":
        return __version__