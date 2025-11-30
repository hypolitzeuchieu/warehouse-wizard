from __future__ import annotations

import os
import socket
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from shared.config.logging_config import get_logging_config

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = (
    os.getenv("ALLOWED_HOSTS", default="localhost,testserver").split(",")
    if os.getenv("ALLOWED_HOSTS")
    else ["localhost", "testserver"]
)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "infrastructure.persistence.models.apps.PersistenceModelsConfig",
    "tasks.apps.TasksConfig",
    "rest_framework",
    "corsheaders",
    "rest_framework.authtoken",
    "drf_yasg",
    "rest_framework_simplejwt.token_blacklist",
]

# Add debug toolbar only in DEBUG mode
if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "shared.authentication.jwt_blacklist_authentication.JWTAuthenticationWithBlacklist",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("RATE_LIMIT_ANON", "100/day"),
        "user": os.getenv("RATE_LIMIT_USER", "1000/day"),
    },
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "shared.exceptions.handler.custom_exception_handler",
}


SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": ("Bearer token authentication. " 'Example: "Bearer {token}"'),
        }
    },
    "USE_SESSION_AUTH": False,
}

# JWT Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is required")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": JWT_ALGORITHM,
    "SIGNING_KEY": JWT_SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "BLACKLIST_TOKEN_CHECKS": ["access", "refresh"],
    "UPDATE_LAST_LOGIN": True,
}


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "shared.middleware.doc_auth.DocumentationAuthMiddleware",
]

# Add debug toolbar middleware only in DEBUG mode
if DEBUG:
    MIDDLEWARE.insert(5, "debug_toolbar.middleware.DebugToolbarMiddleware")

# CORS settings
CORS_ALLOWED_ALL_ORIGINS = os.getenv("CORS_ALLOWED_ALL_ORIGINS", "False").lower() == "true"
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()
] or ([os.getenv("FRONTEND_URL")] if os.getenv("FRONTEND_URL") else [])
CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken", "X-Refresh-Token"]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
CORS_PREFLIGHT_MAX_AGE = 86400 * 30
CORS_ALLOW_CREDENTIALS = True

# CSRF settings
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_AGE = 86400 * 30

# Session settings
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 86400 * 30

# Security settings
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").lower() == "true"
ROOT_URLCONF = "retailpulse.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "retailpulse.wsgi.application"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]


if DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        },
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DATABASE_NAME"),
            "USER": os.getenv("DATABASE_USER"),
            "PASSWORD": os.getenv("DATABASE_PASSWORD"),
            "HOST": os.getenv("DATABASE_HOST"),
            "PORT": os.getenv("DATABASE_PORT"),
        },
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("REDIS_URL"),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "retailpulse",
            "TIMEOUT": 300,
        }
    }

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# AWS settings

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = os.getenv("AWS_REGION_NAME")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")


STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

AUTH_USER_MODEL = "persistence_models.RetailPulseUser"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# SMTP settings

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = os.getenv("EMAIL_PORT")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

# CELERY Settings

CELERY_BROKER_URL = os.environ.get("REDIS_URL")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Celery Beat Schedule

CELERY_BEAT_SCHEDULE = {
    "check-expired-products": {
        "task": "tasks.inventory_tasks.check_expired_products",
        "schedule": timedelta(seconds=60),
    },
    "cleanup-expired-tokens": {
        "task": "tasks.auth_tasks.cleanup_expired_tokens",
        "schedule": timedelta(seconds=120),
    },
}

# Logging configuration
LOGGING = get_logging_config(debug=DEBUG)

# Documentation Authentication Settings
DOC_USERNAME = os.getenv("DOC_USERNAME", None)
DOC_PASSWORD = os.getenv("DOC_PASSWORD", None)

# Google OAuth Settings
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", None)
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", None)

# Django Debug Toolbar Settings
if DEBUG:
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [
        "127.0.0.1",
        "localhost",
    ]
    # Add gateway IPs for Docker/remote development
    for ip in ips:
        gateway_ip = ip[: ip.rfind(".")] + ".1"
        if gateway_ip not in INTERNAL_IPS:
            INTERNAL_IPS.append(gateway_ip)

    # Configure Debug Toolbar panels
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
        "SHOW_COLLAPSED": True,
        "HIDE_DJANGO_SQL": False,
        "ENABLE_STACKTRACES": True,
        "SHOW_TEMPLATE_CONTEXT": True,
    }

    # Enable all panels for maximum debugging information
    DEBUG_TOOLBAR_PANELS = [
        "debug_toolbar.panels.versions.VersionsPanel",
        "debug_toolbar.panels.timer.TimerPanel",
        "debug_toolbar.panels.settings.SettingsPanel",
        "debug_toolbar.panels.headers.HeadersPanel",
        "debug_toolbar.panels.request.RequestPanel",
        "debug_toolbar.panels.sql.SQLPanel",
        "debug_toolbar.panels.staticfiles.StaticFilesPanel",
        "debug_toolbar.panels.templates.TemplatesPanel",
        "debug_toolbar.panels.cache.CachePanel",
        "debug_toolbar.panels.signals.SignalsPanel",
        "debug_toolbar.panels.logging.LoggingPanel",
        "debug_toolbar.panels.redirects.RedirectsPanel",
        "debug_toolbar.panels.profiling.ProfilingPanel",
    ]

# Password Reset Settings
PASSWORD_RESET_EXPIRY_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRY_MINUTES", "10"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Twilio SMS Settings
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", None)
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", None)
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", None)

# Rate Limiting Settings (configurable via environment variables)
RATE_LIMIT_SIGNUP_REQUESTS = int(os.getenv("RATE_LIMIT_SIGNUP_REQUESTS", "5"))
RATE_LIMIT_SIGNUP_PERIOD = int(os.getenv("RATE_LIMIT_SIGNUP_PERIOD", "3600"))

RATE_LIMIT_LOGIN_REQUESTS = int(os.getenv("RATE_LIMIT_LOGIN_REQUESTS", "10"))
RATE_LIMIT_LOGIN_PERIOD = int(os.getenv("RATE_LIMIT_LOGIN_PERIOD", "900"))
RATE_LIMIT_VERIFY_OTP_REQUESTS = int(os.getenv("RATE_LIMIT_VERIFY_OTP_REQUESTS", "5"))
RATE_LIMIT_VERIFY_OTP_PERIOD = int(os.getenv("RATE_LIMIT_VERIFY_OTP_PERIOD", "300"))

RATE_LIMIT_REQUEST_OTP_REQUESTS = int(os.getenv("RATE_LIMIT_REQUEST_OTP_REQUESTS", "3"))
RATE_LIMIT_REQUEST_OTP_PERIOD = int(os.getenv("RATE_LIMIT_REQUEST_OTP_PERIOD", "300"))

RATE_LIMIT_GOOGLE_AUTH_URL_REQUESTS = int(os.getenv("RATE_LIMIT_GOOGLE_AUTH_URL_REQUESTS", "10"))
RATE_LIMIT_GOOGLE_AUTH_URL_PERIOD = int(os.getenv("RATE_LIMIT_GOOGLE_AUTH_URL_PERIOD", "60"))

RATE_LIMIT_GOOGLE_CALLBACK_REQUESTS = int(os.getenv("RATE_LIMIT_GOOGLE_CALLBACK_REQUESTS", "5"))
RATE_LIMIT_GOOGLE_CALLBACK_PERIOD = int(os.getenv("RATE_LIMIT_GOOGLE_CALLBACK_PERIOD", "300"))

RATE_LIMIT_FORGOT_PASSWORD_REQUESTS = int(os.getenv("RATE_LIMIT_FORGOT_PASSWORD_REQUESTS", "3"))
RATE_LIMIT_FORGOT_PASSWORD_PERIOD = int(os.getenv("RATE_LIMIT_FORGOT_PASSWORD_PERIOD", "300"))

RATE_LIMIT_RESET_PASSWORD_REQUESTS = int(os.getenv("RATE_LIMIT_RESET_PASSWORD_REQUESTS", "5"))
RATE_LIMIT_RESET_PASSWORD_PERIOD = int(os.getenv("RATE_LIMIT_RESET_PASSWORD_PERIOD", "300"))
RATE_LIMIT_REFRESH_TOKEN_REQUESTS = int(os.getenv("RATE_LIMIT_REFRESH_TOKEN_REQUESTS", "20"))
RATE_LIMIT_REFRESH_TOKEN_PERIOD = int(os.getenv("RATE_LIMIT_REFRESH_TOKEN_PERIOD", "60"))
