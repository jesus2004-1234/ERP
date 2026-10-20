"""Configuración para correr las pruebas sin MySQL:  python manage.py test --settings=config.settings_test"""
from .settings import *  # noqa: F401,F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DEBUG = False
ALLOWED_HOSTS = ['testserver']
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
