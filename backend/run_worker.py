import argparse
import threading

import uvicorn

from app.worker.daemon import run_daemon
from app.worker.health_api import app as health_app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dozhim worker daemon")
    parser.add_argument("--poll-interval", type=int, default=2, help="Polling interval in seconds")
    parser.add_argument("--health-port", type=int, default=8100, help="Port for worker health API")
    parser.add_argument("--no-health-api", action="store_true", help="Disable health HTTP server")
    args = parser.parse_args()

    if args.no_health_api:
        run_daemon(poll_interval_seconds=args.poll_interval)
    else:
        thread = threading.Thread(
            target=run_daemon,
            kwargs={"poll_interval_seconds": args.poll_interval},
            daemon=True,
        )
        thread.start()
        uvicorn.run(health_app, host="0.0.0.0", port=args.health_port)
