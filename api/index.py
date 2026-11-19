import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
CHATBOT_DIR = os.path.join(ROOT_DIR, "Chatbot")

for path in [ROOT_DIR, CHATBOT_DIR, CURRENT_DIR]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

try:
    from Chatbot.backend import app
except ImportError:
    from backend import app
