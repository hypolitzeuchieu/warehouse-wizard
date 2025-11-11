"""User domain value objects."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Email:
    """Email value object."""

    value: str

    def __post_init__(self) -> None:
        """Validate email format."""
        if not self.value or "@" not in self.value:
            raise ValueError("Invalid email format")

    def __str__(self) -> str:
        """Return email as string."""
        return self.value


@dataclass(frozen=True)
class PhoneNumber:
    """Phone number value object."""

    value: str
    country_code: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate phone number."""
        if not self.value:
            raise ValueError("Phone number cannot be empty")

    def __str__(self) -> str:
        """Return phone number as string."""
        if self.country_code:
            return f"{self.country_code}{self.value}"
        return self.value


@dataclass(frozen=True)
class Address:
    """Address value object."""

    street: str
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    def __str__(self) -> str:
        """Return formatted address."""
        parts = [self.street, self.city]
        if self.state:
            parts.append(self.state)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)

