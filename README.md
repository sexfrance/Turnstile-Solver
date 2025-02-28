<div align="center">
 
  <h2 align="center">Cloudflare - Turnstile Solver</h2>
  <p align="center">
A Python-based solution for solving Cloudflare Turnstile challenges quickly (4-6 seconds solve time). The script uses patchright library to interact with web pages and solve the challenges with optimized browser management.
    <br />
    <br />
    <a href="https://discord.cyberious.xyz">💬 Discord</a>
    ·
    <a href="#-changelog">📜 ChangeLog</a>
    ·
    <a href="https://github.com/sexfrance/Turnstile-Solver/issues">⚠️ Report Bug</a>
    ·
    <a href="https://github.com/sexfrance/Turnstile-Solver/issues">💡 Request Feature</a>
  </p>
</div>

## 📋 Table of Contents

- [Installation](#️-installation)
- [Features](#-features)
- [Usage Examples](#-usage-examples)
- [Advanced Usage](#-advanced-usage)
- [API Documentation](#-api-documentation)
- [Command Line Arguments](#-command-line-arguments)
- [Docker Image](#-docker-image)
- [Disclaimers](#-disclaimers)
- [ChangeLog](#-changelog)

## ⚙️ Installation

- Requires: `Python 3.8+`
- Make a python virtual environment: `python3 -m venv venv`
- Source the environment: `venv\Scripts\activate` (Windows) / `source venv/bin/activate` (macOS, Linux)
- Install the requirements: `pip install -r requirements.txt`
- Install chromium: `patchright install chromium` / `python -m patchright install chromium`
- Start: `python main.py` to access all solvers through an interactive interface

## 🔥 Features

- **Multi-Browser Support**:
  - Chromium (default) - Fast and reliable
  - Chrome - For persistent sessions
  - Camoufox - Enhanced anti-bot evasion
- **Multiple Solving Modes**:
  - **Synchronous**: Simple direct API for basic use cases
  - **Asynchronous**: High-performance async API
  - **API Server**: Web service for remote use
- **Performance Optimization**:
  - Browser pooling with multiple instances
  - Page reuse and state management
  - Multi-threaded parallel solving
- **Advanced Capabilities**:
  - Cookie and session handling
  - Action and cdata parameter support
  - Invisible and visible challenge support
  - Custom user agent configuration
  - Headless mode with proper stealth
- **Developer Tools**:
  - Comprehensive logging system
  - Debug mode for troubleshooting
  - Detailed error reporting
  - Performance metrics

## 📹 Preview

![Preview](https://i.imgur.com/YI6RZ5P.gif)

## 🚀 Usage Examples

### Synchronous Usage

```python
from sync_solver import get_turnstile_token

result = get_turnstile_token(
    url="https://example.com",
    sitekey="your-site-key",
    invisible=True,
    headless=True,
    user_agent="Mozilla/5.0 ..."
)
```

### Asynchronous Usage

```python
from async_solver import get_turnstile_token
import asyncio

async def main():
    result = await get_turnstile_token(
        url="https://example.com",
        sitekey="your-site-key",
        invisible=True,
        headless=True,
        user_agent="Mozilla/5.0 ..."
    )
```

### API Server Usage

```sh
curl "http://localhost:5000/turnstile?url=https://example.com&sitekey=your-site-key&invisible=true&headless=true&useragent=Mozilla/5.0..."
```

## 🔧 Command Line Arguments

| Parameter      | Default     | Type      | Description                                                                       |
| -------------- | ----------- | --------- | --------------------------------------------------------------------------------- |
| `--headless`   | `False`     | `boolean` | Runs the browser in headless mode. Requires the `--useragent` argument to be set. |
| `--useragent`  | `None`      | `string`  | Specifies a custom User-Agent string for the browser.                             |
| `--debug`      | `False`     | `boolean` | Enables or disables debug mode for additional logging and troubleshooting.        |
| `--persistent` | `False`     | `boolean` | Enables a persistent browser context.                                             |
| `--thread`     | `1`         | `integer` | Sets the number of browser threads to use in multi-threaded mode.                 |
| `--host`       | `127.0.0.1` | `string`  | Specifies the IP address the API solver runs on.                                  |
| `--port`       | `5000`      | `integer` | Sets the port the API solver listens on.                                          |

## 🐳 Docker Image

### Running the Container

To start the container, use:

- Change the TZ environment variable and ports to the correct one for yourself:

```sh
docker run -d -p 3389:3389 -p 5000:5000 -e TZ=Asia/Baku --name turnstile_solver theyka/turnstile_solver:latest
```

### Connecting to the Container

1. Use an **RDP client** (like Windows Remote Desktop, Remmina, or FreeRDP)
2. Connect to `localhost:3389`
3. Login with the default user:
   - **Username:** root
   - **Password:** root
4. After this, you can start the solver by navigating to the `Turnstile-Solver` folder.

## 📡 API Documentation

### Solve turnstile

```http
  GET /turnstile?url=https://example.com&sitekey=0x4AAAAAAA
```

### Request Parameters:

| Parameter | Type   | Description                                                          | Required |
| --------- | ------ | -------------------------------------------------------------------- | -------- |
| `url`     | string | The target URL containing the CAPTCHA. (e.g., `https://example.com`) | Yes      |
| `sitekey` | string | The site key for the CAPTCHA to be solved. (e.g., `0x4AAAAAAA`)      | Yes      |
| `action`  | string | Action to trigger during CAPTCHA solving, e.g., `login`              | No       |
| `cdata`   | string | Custom data that can be used for additional CAPTCHA parameters.      | No       |

### Response:

If the request is successfully received, the server will respond with a `task_id` for the CAPTCHA solving task:

```json
{
  "task_id": "d2cbb257-9c37-4f9c-9bc7-1eaee72d96a8"
}
```

### Get Result

```http
  GET /result?id=f0dbe75b-fa76-41ad-89aa-4d3a392040af
```

### Request Parameters:

| Parameter | Type   | Description                                                | Required |
| --------- | ------ | ---------------------------------------------------------- | -------- |
| `id`      | string | The unique task ID returned from the `/turnstile` request. | Yes      |

### Response:

If the CAPTCHA is solved successfully, the server will respond with the following information:

```json
{
  "elapsed_time": 7.625,
  "value": "0.KBtT-r"
}
```

## ❗ Disclaimers

- I am not responsible for anything that may happen, such as API Blocking, IP ban, etc.
- This was a quick project that was made for fun and personal use if you want to see further updates, star the repo & create an "issue" [here](https://github.com/sexfrance/Turnstile-Solver/issues/)

## 📜 ChangeLog

```diff
v0.0.1 ⋮ 21/10/2024
! Initial release

v0.0.2 ⋮ 10/28/2024
! Modified the script, page.html is now in the scripts
! Made it faster and less resource intensive
! Modified the sync logic and made an async version
! Implemented logmagix logging
! Added timer

v0.0.3 ⋮ 11/7/2024
+ Added API server implementation
+ Added web interface for API documentation
+ Improved error handling and logging
+ Added concurrent processing support

v0.0.4 ⋮ 12/7/2024
+ Added cookie support for authentication
+ Added action and cdata parameter support
+ Enhanced invisible Turnstile support
+ Improved browser management

v0.0.5 ⋮ 12/24/2024
+ Implemented browser pooling system
+ Added page pooling for each browser
+ Enhanced browser stealth features
+ Added headless mode with user agent support
+ Improved resource cleanup and management
+ Added comprehensive error handling
+ Optimized browser lifecycle management

v0.0.6 ⋮ 12/31/2024
+ Added custom user agent support
+ Enhanced headless mode stability
+ Improved browser argument handling
+ Added automatic scaling for resources
+ Enhanced error reporting system
+ Optimized page cleanup process

v0.1.0 ⋮ 11/7/2024
+ Added API server implementation
+ Added web interface for API documentation
+ Improved error handling and logging
+ Added concurrent processing support

v0.1.1 ⋮ 15/2/2025
+ Added --headless argument
+ Added --debug argument
+ Added --useragent argument
! Modified logging method to use the logging library

v0.1.2 ⋮ 19/02/2025
+ Added optional action and cData parameters, similar to sitekey and url.

v0.1.3 ⋮ 22/02/2025
+ Added persistent context browser for improved security
+ Implemented multi-threaded mode for enhanced performance
+ Added method to configure host and port for API server
```

<p align="center">
  <img src="https://img.shields.io/github/license/sexfrance/Turnstile-Solver.svg?style=for-the-badge&labelColor=black&color=f429ff&logo=IOTA"/>
  <img src="https://img.shields.io/github/stars/sexfrance/Turnstile-Solver.svg?style=for-the-badge&labelColor=black&color=f429ff&logo=IOTA"/>
  <img src="https://img.shields.io/github/languages/top/sexfrance/Turnstile-Solver.svg?style=for-the-badge&labelColor=black&color=f429ff&logo=python"/>
</p>

Inspired by [Turnaround](https://github.com/Body-Alhoha/turnaround)
Original code by [Theyka](https://github.com/Theyka/Turnstile-Solver)
Changes by [Sexfrance](https://github.com/sexfrance)
