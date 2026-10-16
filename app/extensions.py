"""Extensiones compartidas de Flask (se inicializan en create_app)."""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Ingresá con tu usuario para continuar."
login_manager.login_message_category = "info"
login_manager.session_protection = "strong"
