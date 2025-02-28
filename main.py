
import threading
import asyncio
from typing import Dict
from queue import Queue
from api_solver import create_app
from sync_solver import get_turnstile_token as sync_solve
from async_solver import get_turnstile_token as async_solve
from logmagix import Logger, Loader
class TurnstileTester:
    def __init__(self):
        self.log = Logger(github_repository="https://github.com/sexfrance/Turnstile-Solver")
        self.loader = Loader(desc="Processing...", timeout=0.05)

    def _get_user_input(self) -> tuple[str, str, str]:
        """Get user input for solver configuration."""
        self.log.info("Select solver mode:")
        self.log.info("1. Sync Solver")
        self.log.info("2. Async Solver")
        self.log.info("3. API Server")

        mode = input("Enter mode (1-3): ")
        while mode not in ['1', '2', '3']:
            self.log.warning("Invalid mode. Please enter 1, 2, or 3.")
            mode = input("Enter mode (1-3): ")

        if mode == '3':
            return 'api', '', ''

        self.log.info("\nEnter Turnstile details:")
        url = input("URL: ")
        sitekey = input("Sitekey: ")

        return {
            '1': 'sync',
            '2': 'async',
            '3': 'api'
        }[mode], url, sitekey


    def run_sync_solver(self, url: str, sitekey: str, result_queue: Queue) -> None:
        """Run the synchronous solver with logging in a separate thread."""
        self.log.debug(f"Starting sync solver for {url}")

        def sync_task():
            try:
                result = sync_solve(url=url, sitekey=sitekey, headless=False)
                if result.get('status') == 'success':
                    self.log.success("Sync solver completed successfully")
                else:
                    self.log.error("Sync solver failed")
                result_queue.put(result)
            except Exception as e:
                self.log.error(f"Sync solver encountered an error: {e}")
                result_queue.put({})

        thread = threading.Thread(target=sync_task)
        thread.start()
        thread.join()


    async def run_async_solver(self, url: str, sitekey: str) -> Dict:
        """Run the asynchronous solver with logging."""
        self.log.debug(f"Starting async solver for {url}")
        try:
            result = await async_solve(url=url, sitekey=sitekey, headless=False)
            if result.get('status') == 'success':
                self.log.success("Async solver completed successfully")
            else:
                self.log.error("Async solver failed")
            return result
        except Exception as e:
            self.log.error(f"Async solver encountered an error: {e}")
            return {}


    async def run_api_server(self, debug=False, headless=False, useragent=None, browser_type="chromium", thread=1) -> None:
        """Run the API server with logging."""
        self.log.info("Starting API server on http://localhost:5000")
        self.log.info("API documentation available at http://localhost:5000/")

        try:
            app = create_app(debug=debug, headless=headless, useragent=useragent, browser_type=browser_type, thread=thread)
            import hypercorn.asyncio
            config = hypercorn.Config()
            config.bind = ["127.0.0.1:5000"]
            await hypercorn.asyncio.serve(app, config)
        except Exception as e:
            self.log.error(f"API server failed to start: {str(e)}")

    async def main(self):
        """Main execution flow with proper logging."""
        self.log.info("Turnstile: Welcome to Turnstile Solver Tester")

        try:
            mode, url, sitekey = self._get_user_input()

            if mode == 'api':
                await self.run_api_server()
            else:
                if not url or not sitekey:
                    self.log.error("URL and sitekey are required")
                    return

                result_queue = Queue()

                if mode == 'sync':
                    self.run_sync_solver(url, sitekey, result_queue)
                    result = result_queue.get()
                else:
                    result = await self.run_async_solver(url, sitekey)

                self.log.debug("Result details:")
                for key, value in result.items():
                    self.log.debug(f"{key}: {value}")

        except KeyboardInterrupt:
            self.log.warning("\nOperation cancelled by user")
        except Exception as e:
            self.log.error(f"An error occurred: {str(e)}")
        finally:
            self.log.info("Turnstile: Testing completed")


if __name__ == "__main__":
    tester = TurnstileTester()
    asyncio.run(tester.main())

# Credits for the changes: github.com/sexfrance
# Credit for the original script: github.com/Theyka
