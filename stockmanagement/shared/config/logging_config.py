"""Logging configuration for RetailPulse application."""

from __future__ import annotations

from pathlib import Path


def get_logging_config(debug: bool = False) -> dict:
    """
    Get logging configuration dictionary.

    Args:
        debug: Whether debug mode is enabled

    Returns:
        Dictionary with logging configuration
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    logs_dir = base_dir / "logs"

    # Create logs directory if it doesn't exist
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True, exist_ok=True)

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {name} {process:d} {message}",
                "style": "{",
            },
            "simple": {
                "format": "{levelname} {asctime} {message}",
                "style": "{",
            },
            "structured": {
                "format": "{levelname} {asctime} [{name}] {message}",
                "style": "{",
            },
            "colored": {
                "()": "colorlog.ColoredFormatter",
                "format": "%(log_color)s%(levelname)s%(reset)s %(asctime)s [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "log_colors": {
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
                "secondary_log_colors": {},
                "style": "%",
            },
        },
        "filters": {
            "require_debug_true": {
                "()": "django.utils.log.RequireDebugTrue",
            },
        },
        "handlers": {
            "console": {
                "level": "DEBUG" if debug else "INFO",
                "class": "logging.StreamHandler",
                "formatter": "colored",
            },
            "file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(logs_dir / "retailpulse.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10 MB
                "backupCount": 5,
                "formatter": "verbose",
            },
            "error_file": {
                "level": "ERROR",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(logs_dir / "retailpulse_errors.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10 MB
                "backupCount": 5,
                "formatter": "verbose",
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
        "loggers": {
            "fontTools": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "fontTools.subset": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "weasyprint": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "django": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "django.request": {
                "handlers": ["console", "error_file"],
                "level": "ERROR",
                "propagate": False,
            },
            "django.db.backends": {
                "handlers": ["console", "file"],
                "level": "WARNING",  # Reduce SQL query logging
                "propagate": False,
            },
            "shared.exceptions": {
                "handlers": ["console", "error_file"],
                "level": "ERROR",
                "propagate": False,
            },
            "application": {
                "handlers": ["console", "file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            "infrastructure": {
                "handlers": ["console", "file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            "presentation": {
                "handlers": ["console", "file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            "domain": {
                "handlers": ["console", "file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
        },
    }
