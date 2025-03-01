import os
import sys
import time
import json
import uuid
import argparse
import random
import string
import asyncio

from quart import Quart, request, jsonify
from typing import Dict, Optional
from dataclasses import dataclass
from patchright.async_api import async_playwright, Page, BrowserContext
from camoufox.async_api import AsyncCamoufox
from logmagix import Loader
from collections import deque
from functools import wraps
from .logger import log

DEBUG = False

def set_debug(value: bool):
    global DEBUG
    DEBUG = value

def debug(func_or_message, *args, **kwargs):
    global DEBUG
    if callable(func_or_message):
        @wraps(func_or_message)
        async def wrapper(*args, **kwargs):
            result = await func_or_message(*args, **kwargs)
            if DEBUG:
                log.debug(f"{func_or_message.__name__} returned: {result}")
            return result
        return wrapper
    else:
        if DEBUG:
            log.debug(f"Debug: {func_or_message}")

@dataclass
class TurnstileResult:
    turnstile_value: Optional[str]
    elapsed_time_seconds: float
    status: str
    reason: Optional[str] = None

class TurnstileAPIServer:
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Turnstile Solver</title>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async></script>
    </head>
    <body>
        <!-- cf turnstile -->
    </body>
    </html>
    """

    def __init__(self, headless: bool = False, useragent: str = None, debug: bool = False, browser_type: str = "chromium", thread: int = 1):
        global DEBUG
        DEBUG = debug
        self.debug = debug
        self.app = Quart(__name__)
        self.log = log
        self.loader = Loader(desc="Solving captcha...", timeout=0.05)
        self.results = self._load_results()
        self.browser_type = browser_type
        self.headless = headless
        self.useragent = useragent
        self.thread_count = thread
        self.browser_pool = asyncio.Queue()
        self.browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--window-position=2000,2000",
        ]
        
        if useragent:
            self.browser_args.append(f"--user-agent={useragent}")

        self._setup_routes()

    @staticmethod
    def _load_results():
        """Load previous results from results.json."""
        try:
            if os.path.exists("results.json"):
                with open("results.json", "r") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"Error loading results: {str(e)}. Starting with an empty results dictionary.")
        return {}

    def _save_results(self):
        """Save results to results.json."""
        try:
            with open("results.json", "w") as result_file:
                json.dump(self.results, result_file, indent=4)
        except IOError as e:
            log.error(f"Error saving results to file: {str(e)}")

    def _setup_routes(self) -> None:
        """Set up the application routes."""
        self.app.before_serving(self._startup)
        self.app.route('/turnstile', methods=['GET'])(self.process_turnstile)
        self.app.route('/result', methods=['GET'])(self.get_result)
        self.app.route('/')(self.index)

    async def _startup(self) -> None:
        """Initialize the browser and page pool on startup."""
        log.info("Starting browser initialization")
        try:
            await self._initialize_browser()
        except Exception as e:
            log.error(f"Failed to initialize browser: {str(e)}")
            raise

    async def _initialize_browser(self) -> None:
        """Initialize the browser and create the page pool."""
        if self.browser_type == "chromium" or self.browser_type == "chrome" or self.browser_type == "msedge":
            playwright = await async_playwright().start()
        elif self.browser_type == "camoufox":
            camoufox = AsyncCamoufox(headless=self.headless)

        for i in range(self.thread_count):
            if self.browser_type == "chromium":
                browser = await playwright.chromium.launch(
                    headless=self.headless,
                    args=self.browser_args
                )
                page = await browser.new_page()

            elif self.browser_type == "chrome":
                browser = await playwright.chromium.launch_persistent_context(
                    user_data_dir=f"{os.getcwd()}/tmp/turnstile-chrome-{''.join(random.choices(string.ascii_letters + string.digits, k=10))}",
                    channel="chrome",
                    headless=self.headless,
                    no_viewport=True,
                )
                page = browser.pages[0]
                
            elif self.browser_type == "msedge":
                browser = await playwright.chromium.launch_persistent_context(
                    user_data_dir=f"{os.getcwd()}/tmp/turnstile-edge-{''.join(random.choices(string.ascii_letters + string.digits, k=10))}",
                    channel="msedge",
                    headless=self.headless,
                    no_viewport=True,
                )
                page = browser.pages[0]

            elif self.browser_type == "camoufox":
                browser = await camoufox.start()
                page = await browser.new_page()

            await self.browser_pool.put((i+1, browser, page))

            if self.debug:
                log.success(f"Browser {i + 1} initialized successfully")

        log.success(f"Browser pool initialized with {self.browser_pool.qsize()} browsers")

    async def _solve_turnstile(self, task_id: str, url: str, sitekey: str, action: str = None, cdata: str = None, invisible: bool = False):
        """Solve the Turnstile challenge."""
        index, browser, page = await self.browser_pool.get()
        start_time = time.time()

        try:
            if self.debug:
                log.debug(f"Browser {index}: Starting Turnstile solve for URL: {url} with Sitekey: {sitekey}")
                log.debug(f"Browser {index}: Setting up page data and route")

            url_with_slash = url + "/" if not url.endswith("/") else url
            turnstile_div = f'<div class="cf-turnstile" data-sitekey="{sitekey}"' + (f' data-action="{action}"' if action else '') + (f' data-cdata="{cdata}"' if cdata else '') + '></div>'
            page_data = self.HTML_TEMPLATE.replace("<!-- cf turnstile -->", turnstile_div)

            await page.route(url_with_slash, lambda route: route.fulfill(body=page_data, status=200))
            await page.goto(url_with_slash)

            if self.debug:
                log.debug(f"Browser {index}: Starting Turnstile response retrieval loop")

            for attempt in range(10):
                try:
                    turnstile_check = await page.eval_on_selector(
                        "[name=cf-turnstile-response]",
                        "el => el.value"
                    )
                    
                    if turnstile_check == "":
                        if self.debug:
                            log.debug(f"Browser {index}: Attempt {attempt+1} - No Turnstile response yet")

                        if not invisible:
                            await page.evaluate("document.querySelector('.cf-turnstile').style.width = '70px'")
                            await page.click(".cf-turnstile")
                            
                        await asyncio.sleep(0.5)
                    else:
                        element = await page.query_selector("[name=cf-turnstile-response]")
                        if element:
                            value = await element.get_attribute("value")
                            elapsed_time = round(time.time() - start_time, 3)

                            log.success(f"Browser {index}: Successfully solved captcha in {elapsed_time} seconds")

                            self.results[task_id] = {"value": value, "elapsed_time": elapsed_time}
                            self._save_results()
                            break
                except Exception as e:
                    log.warning(f"Browser {index}: Error during attempt {attempt+1}: {str(e)}")
                    await asyncio.sleep(0.5)
                    continue

            if self.results.get(task_id) == "CAPTCHA_NOT_READY":
                elapsed_time = round(time.time() - start_time, 3)
                self.results[task_id] = {"value": "CAPTCHA_FAIL", "elapsed_time": elapsed_time}
                log.error(f"Browser {index}: Failed to solve Turnstile in {elapsed_time} seconds")
                
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3)
            self.results[task_id] = {"value": "CAPTCHA_FAIL", "elapsed_time": elapsed_time}
            log.error(f"Browser {index}: Error solving Turnstile: {str(e)}")
            
        finally:
            if self.debug:
                log.debug(f"Browser {index}: Clearing page state")
                
            try:
                await page.goto("about:blank")
                await page.evaluate("""() => {
                    try {
                        window.localStorage.clear();
                        window.sessionStorage.clear();
                    } catch (e) {}
                }""")
            except:
                pass
                
            await self.browser_pool.put((index, browser, page))

    async def process_turnstile(self):
        """Handle the /turnstile endpoint requests."""
        url = request.args.get('url')
        sitekey = request.args.get('sitekey')
        action = request.args.get('action')
        cdata = request.args.get('cdata')
        invisible = request.args.get('invisible', 'false').lower() == 'true'

        if not url or not sitekey:
            return jsonify({
                "status": "error",
                "error": "Both 'url' and 'sitekey' are required"
            }), 400

        task_id = str(uuid.uuid4())
        self.results[task_id] = "CAPTCHA_NOT_READY"

        try:
            asyncio.create_task(self._solve_turnstile(
                task_id=task_id, 
                url=url, 
                sitekey=sitekey, 
                action=action, 
                cdata=cdata,
                invisible=invisible
            ))

            if self.debug:
                log.debug(f"Request completed with taskid {task_id}.")
            return jsonify({"task_id": task_id}), 202
        except Exception as e:
            log.error(f"Unexpected error processing request: {str(e)}")
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500

    async def get_result(self):
        """Return solved data"""
        task_id = request.args.get('id')

        if not task_id or task_id not in self.results:
            return jsonify({"status": "error", "error": "Invalid task ID/Request parameter"}), 400

        result = self.results[task_id]
        
        # If it's still processing
        if result == "CAPTCHA_NOT_READY":
            return jsonify({"status": "processing"}), 202
            
        status_code = 200
        if result.get('value') == "CAPTCHA_FAIL":
            status_code = 422

        return jsonify(result), status_code

    @staticmethod
    async def index():
        """Serve the API documentation page."""
        return """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Turnstile Solver API</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-gray-900 text-gray-200 min-h-screen flex items-center justify-center">
                <div class="bg-gray-800 p-8 rounded-lg shadow-md max-w-2xl w-full border border-red-500">
                    <h1 class="text-3xl font-bold mb-6 text-center text-red-500">Welcome to Turnstile Solver API</h1>

                    <p class="mb-4 text-gray-300">To use the turnstile service, send a GET request to 
                       <code class="bg-red-700 text-white px-2 py-1 rounded">/turnstile</code> with the following query parameters:</p>

                    <ul class="list-disc pl-6 mb-6 text-gray-300">
                        <li><strong>url</strong>: The URL where Turnstile is to be validated</li>
                        <li><strong>sitekey</strong>: The site key for Turnstile</li>
                        <li><strong>action</strong>: (Optional) Custom action parameter</li>
                        <li><strong>cdata</strong>: (Optional) Custom data parameter</li>
                        <li><strong>invisible</strong>: (Optional) Set to 'true' for invisible captchas</li>
                    </ul>

                    <div class="bg-gray-700 p-4 rounded-lg mb-6 border border-red-500">
                        <p class="font-semibold mb-2 text-red-400">Example usage:</p>
                        <code class="text-sm break-all text-red-300">/turnstile?url=https://example.com&sitekey=sitekey&invisible=true</code>
                    </div>
                    
                    <div class="bg-gray-700 p-4 rounded-lg mb-6 border border-red-500">
                        <p class="font-semibold mb-2 text-red-400">Then check the result with:</p>
                        <code class="text-sm break-all text-red-300">/result?id=your_task_id</code>
                    </div>

                    <div class="bg-red-900 border-l-4 border-red-600 p-4 mb-6">
                        <p class="text-red-200 font-semibold">This project is inspired by 
                           <a href="https://github.com/Body-Alhoha/turnaround" class="text-red-300 hover:underline">Turnaround</a> 
                           and is currently maintained by
                           <a href="https://github.com/sexfrance" class="text-red-300 hover:underline">Sexfrance</a>.</p>
                    </div>
                </div>
            </body>
            </html>
        """

    def create_app(self):
        """Create and configure the application instance."""
        return self.app

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Turnstile API Server")
    parser.add_argument('--headless', action='store_true', help='Run the browser in headless mode')
    parser.add_argument('--useragent', type=str, default=None, help='Custom User-Agent string')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--browser_type', type=str, default='chromium', help='Specify the browser type for the solver. Supported options: chromium, chrome, msedge, camoufox (default: chromium)')    
    parser.add_argument('--thread', type=int, default=1, help='Number of browser threads')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host IP address')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    return parser.parse_args()

def create_app(headless=False, useragent=None, debug=False, browser_type="chromium", thread=1):
    """Create the Quart application."""
    server = TurnstileAPIServer(
        headless=headless,
        useragent=useragent,
        debug=debug,
        browser_type=browser_type,
        thread=thread
    )
    return server.app

if __name__ == "__main__":
    args = parse_args()

    browser_types = [
        'chromium',
        'chrome',
        'msedge',
        'camoufox',
    ]
    
    if args.headless and args.useragent is None and args.browser_type != "camoufox":
        log.critical("You must specify a User-Agent for headless mode or use camoufox")
    
    if args.browser_type not in browser_types:
        log.critical("Invalid browser type specified. Supported options: chromium, chrome, msedge, camoufox")
        
    app = create_app(
        headless=args.headless,
        useragent=args.useragent,
        debug=args.debug,
        browser_type=args.browser_type,
        thread=args.thread
    )
    app.run(host=args.host, port=args.port)

# Credits for the changes: github.com/sexfrance
# Credit for the original script: github.com/Theyka