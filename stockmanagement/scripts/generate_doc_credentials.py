#!/usr/bin/env python
"""Script to generate documentation credentials."""

import os
import sys

import django

from management.commands.generate_doc_credentials import Command

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "retailpulse.settings")

django.setup()


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Error: Username is required.")
        print("Usage: python scripts/generate_doc_credentials.py <username> [--days N]")
        sys.exit(1)

    username = sys.argv[1]
    days = None

    # Parse optional --days argument
    if "--days" in sys.argv:
        days_index = sys.argv.index("--days")
        if days_index + 1 < len(sys.argv):
            days = sys.argv[days_index + 1]

    # Create command instance and call handle
    cmd = Command()
    options = {"username": username}
    if days:
        options["days"] = int(days)
    cmd.handle(**options)


if __name__ == "__main__":
    main()
