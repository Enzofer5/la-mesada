"""Punto de entrada.

Desarrollo:   python run.py            (http://127.0.0.1:5000)
Producción:   waitress-serve --port=8000 --call run:crear   (Windows)  |  gunicorn "run:crear()" (Linux)
"""
import os

from app import create_app

app = create_app()


def crear():
    return app


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "0") == "1")
