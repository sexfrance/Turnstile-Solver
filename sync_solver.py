import time
import os
import random
import string

from typing import Dict, Optional
from dataclasses import dataclass
from patchright.sync_api import sync_playwright, Page, BrowserContext
from camoufox.sync_api import Camoufox
from logmagix import Loader
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
        def wrapper(*args, **kwargs):
            result = func_or_message(*args, **kwargs)
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

class TurnstileSolver:
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Turnstile Solver</title>
        <script
          src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onloadTurnstileCallback"
          async=""
          defer=""
        ></script>
      </head>
      <body>
        <!-- cf turnstile -->
      </body>
    </html>
    """

    def __init__(self, debug: bool = False, headless: Optional[bool] = None, useragent: Optional[str] = None, browser_type: str = "chromium"):
        self.debug = debug
        self.browser_type = browser_type
        self.headless = headless if headless is not None else False
        self.useragent = useragent
        self.log = log
        self.loader = Loader(desc="Solving captcha...", timeout=0.05)
        
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

        if self.useragent:
            self.browser_args.append(f"--user-agent={self.useragent}")

        if self.headless and not self.useragent:
            self.log.warning("To solve captchas with headless mode you need to set the useragent!")
 

    @debug
    def _setup_page(self, browser, url: str, sitekey: str = None, action: str = None, cdata: str = None) -> Page:
        """Set up the page with or without Turnstile widget."""
        if self.browser_type == "chrome":
            page = browser.pages[0]
        else:
            page = browser.new_page()
            
        url_with_slash = url + "/" if not url.endswith("/") else url
        
        debug(f"Navigating to URL: {url_with_slash}")

        if sitekey:
            turnstile_div = f'<div class="cf-turnstile" data-sitekey="{sitekey}"' + (f' data-action="{action}"' if action else '') + (f' data-cdata="{cdata}"' if cdata else '') + ' data-theme="light"></div>'
            page_data = self.HTML_TEMPLATE.replace("<!-- cf turnstile -->", turnstile_div)
            page.route(url_with_slash, lambda route: route.fulfill(body=page_data, status=200))
        
        page.goto(url_with_slash)
        return page

    @debug
    def _get_turnstile_response(self, page: Page, max_attempts: int = 10, invisible: bool = False) -> Optional[str]:
        """Attempt to retrieve Turnstile response."""
        attempts = 0

        while attempts < max_attempts:
            turnstile_check = page.eval_on_selector(
                "[name=cf-turnstile-response]", 
                "el => el.value"
            )

            if turnstile_check == "":
                
                debug(f"Attempt {attempts + 1}: No Turnstile response yet.")

                if not invisible:
                    page.evaluate("document.querySelector('.cf-turnstile').style.width = '70px'")
                    page.click(".cf-turnstile")

                time.sleep(0.5)
                attempts += 1
            else:
                turnstile_element = page.query_selector("[name=cf-turnstile-response]")
                if turnstile_element:
                    return turnstile_element.get_attribute("value")
                break

        return None

    @debug
    def solve(self, url: str, sitekey: str = None, invisible: bool = False, cookies: dict = None, action: str = None, cdata: str = None) -> TurnstileResult:
        """
        Solve the Turnstile challenge and return the result.
        
        Args:
            url: The URL where the Turnstile challenge is hosted
            sitekey: The Turnstile sitekey
            invisible: Whether the Turnstile challenge is invisible
            cookies: Optional dictionary of cookies to set
            action: Optional action parameter for Turnstile
            cdata: Optional custom data parameter for Turnstile

        Returns:
            TurnstileResult object containing the solution details
        """
        
        self.loader.start()
        start_time = time.time()

        try:
            if self.browser_type == "chromium":
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=self.headless, args=self.browser_args)
                    context = browser.new_context()
                    
                    if cookies:
                        domain = url.split("//")[-1].split("/")[0]
                        cookie_list = []
                        for name, value in cookies.items():
                            cookie_list.append({
                                "name": name,
                                "value": str(value),
                                "domain": domain,
                                "path": "/"
                            })
                        if cookie_list:
                            context.add_cookies(cookie_list)

                    try:
                        page = self._setup_page(context, url, sitekey, action, cdata)
                        turnstile_value = self._get_turnstile_response(page, invisible=invisible)
                        
                        elapsed_time = round(time.time() - start_time, 3)

                        if not turnstile_value:
                            result = TurnstileResult(
                                turnstile_value=None,
                                elapsed_time_seconds=elapsed_time,
                                status="failure",
                                reason="Max attempts reached without token retrieval"
                            )
                            self.log.failure("Failed to retrieve Turnstile value.")
                        else:
                            result = TurnstileResult(
                                turnstile_value=turnstile_value,
                                elapsed_time_seconds=elapsed_time,
                                status="success"
                            )
                            self.loader.stop()
                            self.log.message(
                                "Cloudflare",
                                f"Successfully solved captcha: {turnstile_value[:45]}...",
                                start=start_time,
                                end=time.time()
                            )

                    except Exception as e:
                        self.log.failure(f"Error during captcha solving: {str(e)}")
                        raise

                    finally:
                        try:
                            context.close()
                            browser.close()
                        except Exception as e:
                            self.log.failure(f"Error closing browser: {str(e)}")

                        debug(f"Elapsed time: {result.elapsed_time_seconds} seconds")
                        debug("Browser closed. Returning result.")

            elif self.browser_type == "chrome":
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch_persistent_context(
                        user_data_dir=f"{os.getcwd()}/tmp/turnstile-chrome-{''.join(random.choices(string.ascii_letters + string.digits, k=10))}",
                        channel="chrome",
                        headless=self.headless,
                        no_viewport=True,
                    )
                    
                    try:
                        page = self._setup_page(browser, url, sitekey, action, cdata)
                        turnstile_value = self._get_turnstile_response(page, invisible=invisible)
                        
                        elapsed_time = round(time.time() - start_time, 3)

                        if not turnstile_value:
                            result = TurnstileResult(
                                turnstile_value=None,
                                elapsed_time_seconds=elapsed_time,
                                status="failure",
                                reason="Max attempts reached without token retrieval"
                            )
                            self.log.failure("Failed to retrieve Turnstile value.")
                        else:
                            result = TurnstileResult(
                                turnstile_value=turnstile_value,
                                elapsed_time_seconds=elapsed_time,
                                status="success"
                            )
                            self.loader.stop()
                            self.log.message(
                                "Cloudflare",
                                f"Successfully solved captcha: {turnstile_value[:45]}...",
                                start=start_time,
                                end=time.time()
                            )

                    except Exception as e:
                        self.log.failure(f"Error during captcha solving: {str(e)}")
                        raise

                    finally:
                        try:
                            browser.close()
                        except Exception as e:
                            self.log.failure(f"Error closing browser: {str(e)}")

                        debug(f"Elapsed time: {result.elapsed_time_seconds} seconds")
                        debug("Browser closed. Returning result.")
                        
            elif self.browser_type == "msedge":
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch_persistent_context(
                        user_data_dir=f"{os.getcwd()}/tmp/turnstile-edge-{''.join(random.choices(string.ascii_letters + string.digits, k=10))}",
                        channel="msedge",
                        headless=self.headless,
                        no_viewport=True,
                    )
                    
                    try:
                        page = self._setup_page(browser, url, sitekey, action, cdata)
                        turnstile_value = self._get_turnstile_response(page, invisible=invisible)
                        
                        elapsed_time = round(time.time() - start_time, 3)

                        if not turnstile_value:
                            result = TurnstileResult(
                                turnstile_value=None,
                                elapsed_time_seconds=elapsed_time,
                                status="failure",
                                reason="Max attempts reached without token retrieval"
                            )
                            self.log.failure("Failed to retrieve Turnstile value.")
                        else:
                            result = TurnstileResult(
                                turnstile_value=turnstile_value,
                                elapsed_time_seconds=elapsed_time,
                                status="success"
                            )
                            self.loader.stop()
                            self.log.message(
                                "Cloudflare",
                                f"Successfully solved captcha: {turnstile_value[:45]}...",
                                start=start_time,
                                end=time.time()
                            )

                    except Exception as e:
                        self.log.failure(f"Error during captcha solving: {str(e)}")
                        raise

                    finally:
                        try:
                            browser.close()
                        except Exception as e:
                            self.log.failure(f"Error closing browser: {str(e)}")

                        debug(f"Elapsed time: {result.elapsed_time_seconds} seconds")
                        debug("Browser closed. Returning result.")

            elif self.browser_type == "camoufox":
                browser = Camoufox(headless=self.headless).start()
                
                try:
                    page = self._setup_page(browser, url, sitekey, action, cdata)
                    turnstile_value = self._get_turnstile_response(page, invisible=invisible)
                    
                    elapsed_time = round(time.time() - start_time, 3)

                    if not turnstile_value:
                        result = TurnstileResult(
                            turnstile_value=None,
                            elapsed_time_seconds=elapsed_time,
                            status="failure",
                            reason="Max attempts reached without token retrieval"
                        )
                        self.log.failure("Failed to retrieve Turnstile value.")
                    else:
                        result = TurnstileResult(
                            turnstile_value=turnstile_value,
                            elapsed_time_seconds=elapsed_time,
                            status="success"
                        )
                        self.loader.stop()
                        self.log.message(
                            "Cloudflare",
                            f"Successfully solved captcha: {turnstile_value[:45]}...",
                            start=start_time,
                            end=time.time()
                        )

                except Exception as e:
                    self.log.failure(f"Error during captcha solving: {str(e)}")
                    raise

                finally:
                    try:
                        browser.close()
                    except Exception as e:
                        self.log.failure(f"Error closing browser: {str(e)}")

                    debug(f"Elapsed time: {result.elapsed_time_seconds} seconds")
                    debug("Browser closed. Returning result.")

        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3)
            self.loader.stop()
            return TurnstileResult(
                turnstile_value=None,
                elapsed_time_seconds=elapsed_time,
                status="error",
                reason=str(e)
            )

        return result

class ChallengeSolver: #TODO
    pass

@debug
def get_turnstile_token(headless: bool = False, url: str = None, sitekey: str = None, invisible: bool = False, 
                       cookies: dict = None, user_agent: str = None, debug: bool = False, browser_type: str = "chromium",
                       action: str = None, cdata: str = None) -> Dict:
    """Legacy wrapper function for backward compatibility."""
    browser_types = [
        'chromium',
        'chrome',
        'camoufox',
        'msedge',
    ]
    if browser_type not in browser_types:
        log.error(f"Unknown browser type: {browser_type} Available browser types: {browser_types}")
        return {"status": "error", "error": f"Unknown browser type: {browser_type}"}
    elif headless is True and user_agent is None and browser_type != "camoufox":
        log.error(f"You must specify a User-Agent for Turnstile Solver or use camoufox without useragent")
        return {"status": "error", "error": "Headless mode requires a useragent"}
    
    solver = TurnstileSolver(headless=headless, useragent=user_agent, debug=debug, browser_type=browser_type)
    result = solver.solve(
        url=url, 
        sitekey=sitekey, 
        invisible=invisible, 
        cookies=cookies, 
        action=action, 
        cdata=cdata
    )
    return result.__dict__

if __name__ == "__main__":
    result = get_turnstile_token(
        url="https://streamlabs.com/discord/nitro",
        sitekey="0x4AAAAAAACELUBpqiwktdQ9",
        invisible=True,
        browser_type="chromium",
        debug=True
    )
    print(result)