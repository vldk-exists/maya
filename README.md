# Maya

![Maya Logo](https://static.wikia.nocookie.net/azumanga/images/3/3f/Maya.jpg)

Maya is a lightweight Python package for handling HTTP requests, responses, and server operations. It provides an easy-to-use framework for managing web interactions efficiently.

## Features

- Request handling
- Response generation
- Cookie management
- Simple server setup

## Installation

To install Maya, simply clone the repository and use it in your project:

```bash
# Clone the repository
git clone https://github.com/Vladislavus1/Maya.git
cd maya
```

Alternatively, if this package is published on PyPI(*will be published soon*):

```bash
pip install maya
```

## Usage

Here's a basic example of how to use Maya:

```python
from maya import WebServer, render_from_string

app = WebServer()

def home():
    return render_from_string("Hello, world!")

app.add_route('/', home)

if __name__ == "__main__":
    app.run()
```

## Modules Overview

- `maya.request` - Handles HTTP requests.
- `maya.response` - Generates HTTP responses.
- `maya.cookies` - Manages cookies.
- `maya.server` - Runs the web server.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.