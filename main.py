import sys
import os
import traceback

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CHATBOT_DIR = os.path.join(ROOT_DIR, "Chatbot")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if CHATBOT_DIR not in sys.path:
    sys.path.insert(0, CHATBOT_DIR)

try:
    from Chatbot.backend import app
except Exception as e:
    err_tb = traceback.format_exc()
    print("CRITICAL IMPORT ERROR IN BACKEND:\n", err_tb)

    async def app(scope, receive, send):
        if scope["type"] == "http":
            body = f"CRITICAL BACKEND IMPORT ERROR:\n\n{err_tb}".encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })

__all__ = ["app"]
