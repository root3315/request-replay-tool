#!/usr/bin/env python3
"""
Request Replay Tool - Capture and replay HTTP requests for testing and debugging.
"""

import argparse
import json
import os
import socket
import sys
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error


DEFAULT_STORAGE_DIR = "./captured_requests"
DEFAULT_PORT = 8765


class RequestCaptureHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures incoming requests to storage."""

    storage_file: str = ""
    captured_count: int = 0

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[Capture] {args[0]}")

    def handle_request(self, method: str) -> None:
        request_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "path": self.path,
            "headers": dict(self.headers),
            "body": None,
        }

        content_length = self.headers.get("Content-Length")
        if content_length:
            body = self.rfile.read(int(content_length))
            request_data["body"] = body.decode("utf-8", errors="replace")

        self.captured_count += 1
        save_capture(self.storage_file, request_data)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = json.dumps({"status": "captured", "id": self.captured_count})
        self.wfile.write(response.encode())

    def do_GET(self) -> None:
        self.handle_request("GET")

    def do_POST(self) -> None:
        self.handle_request("POST")

    def do_PUT(self) -> None:
        self.handle_request("PUT")

    def do_DELETE(self) -> None:
        self.handle_request("DELETE")

    def do_PATCH(self) -> None:
        self.handle_request("PATCH")


def ensure_storage_dir(storage_dir: str) -> None:
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)
        print(f"Created storage directory: {storage_dir}")


def get_capture_filename(name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace(" ", "_").replace("/", "_")
    return f"{safe_name}_{timestamp}.json"


def save_capture(filepath: str, request_data: Dict[str, Any]) -> None:
    existing: List[Dict[str, Any]] = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    if not isinstance(existing, list):
        existing = [existing]

    existing.append(request_data)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


def start_capture_server(port: int, session_name: str, storage_dir: str) -> None:
    ensure_storage_dir(storage_dir)
    capture_file = os.path.join(storage_dir, get_capture_filename(session_name))

    RequestCaptureHandler.storage_file = capture_file
    RequestCaptureHandler.captured_count = 0

    server = HTTPServer(("127.0.0.1", port), RequestCaptureHandler)

    print(f"Capture server started on http://127.0.0.1:{port}")
    print(f"Session: {session_name}")
    print(f"Saving to: {capture_file}")
    print("Press Ctrl+C to stop capturing")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping capture server...")
        server.shutdown()
        print(f"Captured {RequestCaptureHandler.captured_count} requests")


def load_captures(filepath: str) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    return [data]


def replay_request(request_data: Dict[str, Any], target_url: str, dry_run: bool = False, timeout: float = 30.0) -> Dict[str, Any]:
    original_path = request_data.get("path", "/")
    if target_url:
        if target_url.endswith("/"):
            full_url = target_url + original_path.lstrip("/")
        else:
            full_url = target_url + original_path
    else:
        full_url = "http://localhost:8080" + original_path

    method = request_data.get("method", "GET")
    headers = request_data.get("headers", {})
    body = request_data.get("body")

    filtered_headers = {k: v for k, v in headers.items() if k.lower() not in ["host", "content-length"]}

    result: Dict[str, Any] = {
        "method": method,
        "url": full_url,
        "status": "skipped" if dry_run else None,
        "response_time_ms": None,
        "error": None,
    }

    if dry_run:
        print(f"[Dry Run] {method} {full_url}")
        return result

    try:
        req = urllib.request.Request(full_url, method=method)
        for key, value in filtered_headers.items():
            req.add_header(key, value)

        data = None
        if body and method in ["POST", "PUT", "PATCH"]:
            data = body.encode("utf-8")

        start_time = time.time()
        response = urllib.request.urlopen(req, data=data, timeout=timeout)
        elapsed_ms = (time.time() - start_time) * 1000

        result["status"] = response.status
        result["response_time_ms"] = round(elapsed_ms, 2)

    except urllib.error.HTTPError as e:
        result["status"] = e.code
        result["error"] = str(e)
    except urllib.error.URLError as e:
        result["error"] = str(e.reason)
    except socket.timeout as e:
        result["error"] = f"Request timed out after {timeout}s"
    except Exception as e:
        result["error"] = str(e)

    return result


def list_captures(storage_dir: str) -> None:
    if not os.path.exists(storage_dir):
        print(f"Storage directory not found: {storage_dir}")
        return

    files = [f for f in os.listdir(storage_dir) if f.endswith(".json")]
    if not files:
        print("No captured requests found")
        return

    print(f"Found {len(files)} capture file(s):\n")
    for filename in sorted(files):
        filepath = os.path.join(storage_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            count = len(data) if isinstance(data, list) else 1
            size = os.path.getsize(filepath)
            print(f"  {filename} ({count} requests, {size} bytes)")
        except Exception as e:
            print(f"  {filename} (error reading: {e})")


def show_capture_details(filepath: str) -> None:
    captures = load_captures(filepath)
    print(f"\nCapture file: {filepath}")
    print(f"Total requests: {len(captures)}\n")

    for i, req in enumerate(captures, 1):
        print(f"[{i}] {req.get('method', 'UNKNOWN')} {req.get('path', '/')}")
        print(f"    Time: {req.get('timestamp', 'N/A')}")
        headers = req.get('headers', {})
        if headers:
            print(f"    Headers: {len(headers)} entries")
        if req.get('body'):
            print(f"    Body: {len(req['body'])} chars")
        print()


def run_replay(capture_file: str, target_url: Optional[str], dry_run: bool, delay: float, timeout: float) -> None:
    captures = load_captures(capture_file)
    print(f"Replaying {len(captures)} request(s)")
    if target_url:
        print(f"Target: {target_url}")
    else:
        print("Target: localhost:8080 (default)")
    if dry_run:
        print("Mode: Dry run (no actual requests)")
    print()

    results: List[Dict[str, Any]] = []
    for i, req in enumerate(captures, 1):
        print(f"[{i}/{len(captures)}]", end=" ")
        result = replay_request(req, target_url or "", dry_run, timeout)
        results.append(result)

        if result.get("error"):
            print(f"ERROR: {result['error']}")
        elif result.get("status"):
            print(f"Status: {result['status']}, Time: {result.get('response_time_ms', 'N/A')}ms")

        if delay > 0 and i < len(captures):
            time.sleep(delay)

    print()
    successful = sum(1 for r in results if r.get("status") and 200 <= r["status"] < 400)
    errors = sum(1 for r in results if r.get("error"))
    print(f"Summary: {successful} successful, {errors} errors")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture and replay HTTP requests for testing and debugging"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    capture_parser = subparsers.add_parser("capture", help="Start capture server")
    capture_parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT,
                                help=f"Port to listen on (default: {DEFAULT_PORT})")
    capture_parser.add_argument("-n", "--name", type=str, default="session",
                                help="Session name for the capture file")
    capture_parser.add_argument("-d", "--dir", type=str, default=DEFAULT_STORAGE_DIR,
                                help=f"Storage directory (default: {DEFAULT_STORAGE_DIR})")

    replay_parser = subparsers.add_parser("replay", help="Replay captured requests")
    replay_parser.add_argument("file", type=str, help="Path to capture file")
    replay_parser.add_argument("-t", "--target", type=str, default=None,
                               help="Target URL to replay to")
    replay_parser.add_argument("--dry-run", action="store_true",
                               help="Show what would be replayed without sending")
    replay_parser.add_argument("--delay", type=float, default=0,
                               help="Delay between requests in seconds")
    replay_parser.add_argument("--timeout", type=float, default=30.0,
                               help="Request timeout in seconds (default: 30.0)")

    list_parser = subparsers.add_parser("list", help="List captured request files")
    list_parser.add_argument("-d", "--dir", type=str, default=DEFAULT_STORAGE_DIR,
                             help=f"Storage directory (default: {DEFAULT_STORAGE_DIR})")

    show_parser = subparsers.add_parser("show", help="Show details of a capture file")
    show_parser.add_argument("file", type=str, help="Path to capture file")

    args = parser.parse_args()

    if args.command == "capture":
        start_capture_server(args.port, args.name, args.dir)
    elif args.command == "replay":
        run_replay(args.file, args.target, args.dry_run, args.delay, args.timeout)
    elif args.command == "list":
        list_captures(args.dir)
    elif args.command == "show":
        show_capture_details(args.file)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
