# Request Replay Tool

Capture and replay HTTP requests for testing and debugging. I built this because I kept needing to grab real requests from my app and replay them against different environments without manually reconstructing everything in curl or Postman.

## Quick Start

```bash
# Start the capture server
python main.py capture -n my-test-session

# In another terminal, send some requests
curl http://127.0.0.1:8765/api/users
curl -X POST http://127.0.0.1:8765/api/users -d '{"name":"test"}'

# Stop the server with Ctrl+C

# List what you captured
python main.py list

# Replay against your staging environment
python main.py replay ./captured_requests/my-test-session_*.json -t http://staging.example.com

# Or do a dry run first to see what would happen
python main.py replay ./captured_requests/my-test-session_*.json --dry-run
```

## Commands

### capture

Starts a local HTTP server that captures all incoming requests to a JSON file.

```bash
python main.py capture -n session-name -p 8765 -d ./captures
```

Options:
- `-n, --name` - Session name for the capture file (default: "session")
- `-p, --port` - Port to listen on (default: 8765)
- `-d, --dir` - Storage directory (default: ./captured_requests)

The server handles GET, POST, PUT, DELETE, and PATCH methods. Each request gets stored with its timestamp, headers, and body.

### replay

Replays captured requests against a target URL.

```bash
python main.py replay ./captures/session_20260306_143022.json -t http://localhost:3000
```

Options:
- `-t, --target` - Target URL to replay requests to
- `--dry-run` - Show what would be sent without actually sending
- `--delay` - Add delay between requests in seconds (useful for rate-limited APIs)

If you don't specify a target, it defaults to `http://localhost:8080`.

### list

Shows all captured request files in the storage directory.

```bash
python main.py list -d ./captures
```

### show

Displays details of a specific capture file.

```bash
python main.py show ./captures/session_20260306_143022.json
```

## Use Cases

**Testing API changes** - Capture requests from your production app, replay them against a new version to catch breaking changes.

**Load testing prep** - Grab real traffic patterns and replay them with delays to simulate load.

**Debugging** - Capture a problematic request sequence and replay it locally while you debug.

**Environment migration** - Verify your staging environment behaves like production by replaying real requests.

## Storage Format

Captures are stored as JSON arrays. Each request includes:

```json
{
  "timestamp": "2026-03-06T14:30:22.123456",
  "method": "POST",
  "path": "/api/users",
  "headers": {"Content-Type": "application/json", ...},
  "body": "{\"name\":\"test\"}"
}
```

You can manually edit these files if you need to tweak something before replaying.

## Notes

- The capture server runs on 127.0.0.1 only (not exposed externally)
- Host and Content-Length headers are stripped during replay (urllib handles these)
- Requests timeout after 30 seconds during replay
- Capture files are appended to, so you can capture multiple batches into one file
