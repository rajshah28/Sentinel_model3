"""
Real HTTP test of fetch_catalogue() against a minimal local server that
shapes its response like GET /api/ingest per the integration spec
(id, location, codec, live status, stream properties, and RTSP/WHEP/HLS
URLs). Not a mock of fetch_catalogue itself -- a real HTTP GET over a
real socket, exercising the exact parsing logic that will run against
the real sandbox.
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters.govt_grid_catalogue import fetch_catalogue, CatalogueError

CATALOGUE_RESPONSE = {
    "cameras": [
        {
            "id": "cam-01",
            "location": "MG Road Junction",
            "codec": "h264",
            "live": True,
            "urls": {
                "rtsp": "rtsp://127.0.0.1:8554/stream/cam-01",
                "whep": "http://127.0.0.1:8889/stream/cam-01/whep",
                "hls": "http://127.0.0.1/live/stream/cam-01/index.m3u8",
            },
        },
        {
            "id": "cam-02",
            "location": "Ring Road Toll Plaza",
            "codec": "h265",
            "live": True,
            "urls": {
                "rtsp": "rtsp://127.0.0.1:8554/stream/cam-02",
                "whep": "http://127.0.0.1:8889/stream/cam-02/whep",
                "hls": "http://127.0.0.1/live/stream/cam-02/index.m3u8",
            },
        },
        {
            "id": "cam-03",
            "location": "Bus Depot Gate",
            "codec": "h264",
            "live": False,
            "urls": {
                "rtsp": "rtsp://127.0.0.1:8554/stream/cam-03",
            },
        },
    ]
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/ingest":
            body = json.dumps(CATALOGUE_RESPONSE).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # quiet


def main():
    server = HTTPServer(("127.0.0.1", 18081), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    print("Fetching real HTTP catalogue from http://127.0.0.1:18081/api/ingest ...")
    cameras = fetch_catalogue("127.0.0.1:18081")

    assert len(cameras) == 3, f"Expected 3 cameras, got {len(cameras)}"
    assert cameras[0].camera_id == "cam-01"
    assert cameras[0].codec == "h264"
    assert cameras[0].live is True
    assert cameras[0].rtsp_url == "rtsp://127.0.0.1:8554/stream/cam-01"
    assert cameras[1].codec == "h265"
    assert cameras[2].live is False

    for c in cameras:
        print(f"  {c.camera_id}: {c.location} codec={c.codec} live={c.live} rtsp={c.rtsp_url}")

    print("\nPASS: catalogue client correctly parses id/location/codec/live/urls over a real HTTP GET")

    # Also confirm unreachable-host behavior raises CatalogueError cleanly
    try:
        fetch_catalogue("127.0.0.1:1", timeout=2.0)
        print("FAIL: expected CatalogueError for unreachable host")
        sys.exit(1)
    except CatalogueError as e:
        print(f"PASS: unreachable host correctly raises CatalogueError: {e}")

    server.shutdown()


if __name__ == "__main__":
    main()
