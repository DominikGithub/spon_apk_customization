#!/usr/bin/env python3
"""Evaluate JavaScript in the app's live WebView over the DevTools protocol.

Needs the patched build (it calls WebView.setWebContentsDebuggingEnabled(true))
and a forwarded port:

    adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>

Usage:
    python3 patch/cdp.py 'document.querySelectorAll("a").length'
    python3 patch/cdp.py -f snippet.js

Minimal RFC 6455 client - no third-party packages on this machine.
"""
import argparse
import base64
import json
import os
import socket
import struct
import sys
import urllib.request


def pick_page(port: int) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=10) as r:
        targets = json.load(r)
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    real = [t for t in pages if t.get("url", "").startswith("http")]
    if not real:
        sys.exit("no http page target - is the app on an article/home page?")
    return real[0]["webSocketDebuggerUrl"]


class WS:
    def __init__(self, url: str):
        rest = url.split("://", 1)[1]
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=20)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                sys.exit("devtools closed the connection during handshake")
            buf += chunk
        if b"101" not in buf.split(b"\r\n", 1)[0]:
            sys.exit(f"handshake failed: {buf.split(chr(13).encode())[0]!r}")
        self.buf = buf.split(b"\r\n\r\n", 1)[1]

    def send(self, payload: str) -> None:
        data = payload.encode()
        header = b"\x81"
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 1 << 16:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(header + mask + masked)

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                sys.exit("devtools connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self) -> str:
        while True:
            b0, b1 = self._read(2)
            opcode = b0 & 0x0F
            length = b1 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(length)
            if opcode == 0x8:
                sys.exit("devtools sent close")
            if opcode == 0x9:  # ping -> pong
                continue
            if opcode in (0x1, 0x2):
                return payload.decode(errors="replace")


def evaluate(expression: str, port: int = 9222) -> None:
    ws = WS(pick_page(port))
    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        },
    }))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") != 1:
            continue  # skip events
        if "error" in msg:
            sys.exit(f"CDP error: {msg['error']}")
        res = msg["result"]
        if res.get("exceptionDetails"):
            print("JS exception:", json.dumps(res["exceptionDetails"])[:600])
            return
        value = res.get("result", {}).get("value")
        print(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False))
        return


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("expression", nargs="?")
    ap.add_argument("-f", "--file")
    ap.add_argument("-p", "--port", type=int, default=9222)
    a = ap.parse_args()
    expr = open(a.file).read() if a.file else a.expression
    if not expr:
        sys.exit("give an expression or -f file")
    evaluate(expr, a.port)
