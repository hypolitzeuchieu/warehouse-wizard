"""Script to generate documentation credentials."""

import os
import sys

import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "retailpulse.settings")


django.setup()

from management.commands.generate_doc_credentials import Command  # noqa: E402


def main():
    """Main function."""
    username = None
    days = None

    # Parse arguments if provided
    if len(sys.argv) >= 2:
        # Check if first arg is --days
        if sys.argv[1] == "--days" and len(sys.argv) >= 3:
            days = sys.argv[2]
        elif sys.argv[1] != "--days":
            username = sys.argv[1]

    # Parse optional --days argument
    if "--days" in sys.argv:
        days_index = sys.argv.index("--days")
        if days_index + 1 < len(sys.argv):
            days = sys.argv[days_index + 1]

    # Create command instance and call handle
    cmd = Command()
    options = {}
    if username:
        options["username"] = username
    if days:
        options["days"] = int(days)
    cmd.handle(**options)


if __name__ == "__main__":
    main()
