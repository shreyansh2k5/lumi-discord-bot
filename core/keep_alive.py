# core/keep_alive.py

from flask import Flask
from threading import Thread

app = Flask(__name__)


@app.route('/')
def home():
    return "I'm alive!"


def _run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=_run, daemon=True)
    t.start()
