"""Helpers to filter and sort in-memory DTO collections."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any


def _resolve_attr(item: Any, attr: str) -> Any:
    """Resolve attribute/field value from dataclass, object, or dict."""
    if not attr:
        return None

    target = item
    for part in attr.split("."):
        if target is None:
            return None
        if isinstance(target, dict):
            target = target.get(part)
        else:
            target = getattr(target, part, None)
    return target


def filter_by_search(
    items: Iterable[Any],
    search_term: str | None,
    search_fields: Sequence[str] | None,
) -> list[Any]:
    """Filter items by search term across allowed fields."""
    if not search_term or not search_fields:
        return list(items)

    normalized = search_term.lower()
    filtered: list[Any] = []
    for item in items:
        for field in search_fields:
            value = _resolve_attr(item, field)
            if value and normalized in str(value).lower():
                filtered.append(item)
                break
    return filtered


def filter_by_name(
    items: Iterable[Any],
    name_value: str | None,
    name_fields: Sequence[str] | None = None,
) -> list[Any]:
    """Filter collection by a partial match on provided name fields."""
    if not name_value:
        return list(items)
    fields = list(name_fields or ["name"])
    normalized = name_value.lower()
    result: list[Any] = []
    for item in items:
        for field in fields:
            value = _resolve_attr(item, field)
            if value and normalized in str(value).lower():
                result.append(item)
                break
    return result


def sort_items(
    items: Iterable[Any],
    order_by: str,
) -> list[Any]:
    """Sort items by the provided order clause (supports '-' prefix)."""
    if not order_by:
        return list(items)

    reverse = order_by.startswith("-")
    field = order_by[1:] if reverse else order_by
    return sorted(
        items,
        key=lambda item: _resolve_attr(item, field),
        reverse=reverse,
    )
