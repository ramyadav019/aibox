import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHATBOT_DIR = os.path.join(ROOT_DIR, "Chatbot")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if CHATBOT_DIR not in sys.path:
    sys.path.insert(0, CHATBOT_DIR)

from main import app
import Chatbot.backend

__all__ = ["app"]
app = Chatbot.backend.app
