"""Password generation utility."""

import secrets
import string


def generate_secure_password(length: int = 12) -> str:
    """
    Generate a secure random password.

    Args:
        length: Length of the password (default: 12)

    Returns:
        A secure random password containing letters, digits, and special characters
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password
