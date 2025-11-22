#!/usr/bin/env python3
"""
Simple HTTP server for the monitoring dashboard.
Serves monitor.html on http://localhost:4000

Author: David Marleau
Project: Distributed Voting System - Demo Version
Description: Real-time results dashboard with national aggregation
"""
import http.server
import socketserver
import os

PORT = 4000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print(f"╔══════════════════════════════════════════════════════════════╗")
        print(f"║  📊 Monitor Dashboard Server Running                         ║")
        print(f"╚══════════════════════════════════════════════════════════════╝")
        print(f"")
        print(f"  🌐 Access the dashboard at:")
        print(f"     http://localhost:{PORT}/monitor.html")
        print(f"")
        print(f"  Press CTRL+C to stop the server")
        print(f"")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n\n🛑 Server stopped.")
