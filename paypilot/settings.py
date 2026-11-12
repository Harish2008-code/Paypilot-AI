"""Settings for the PayPilot AI demo application."""
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me-before-production")
DEBUG = os.getenv("DJANGO_DEBUG", "True").strip().lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [host.strip() for host in os.getenv(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.e2b.app,testserver"
).split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "commerce",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Intentionally omitted for the embedded Arena preview. Re-enable XFrameOptionsMiddleware
    # (or a strict CSP frame-ancestors policy) when deploying outside this demo environment.
]

ROOT_URLCONF = "paypilot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "paypilot.wsgi.application"
ASGI_APPLICATION = "paypilot.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# App-level files live in commerce/static and are found by Django's AppDirectoriesFinder.
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Security defaults suitable for local development. Enable HTTPS enforcement in production.
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True

# PayPal REST API configuration. Empty credentials intentionally enable clearly labelled demo mode.
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox").lower()
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_CURRENCY = os.getenv("PAYPAL_CURRENCY", "USD").upper()
PAYPAL_BUSINESS_NAME = os.getenv("PAYPAL_BUSINESS_NAME", "Northstar Studio")
PAYPAL_BUSINESS_EMAIL = os.getenv("PAYPAL_BUSINESS_EMAIL", "merchant@example.com")

# LLM configuration. The app uses the OpenAI-compatible Chat Completions protocol.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
