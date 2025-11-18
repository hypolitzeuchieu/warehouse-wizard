#!/usr/bin/env python3
"""Script to refactor BaseAPIException to specific exceptions."""

import re
from pathlib import Path

# Mapping of status codes to specific exceptions
EXCEPTION_MAPPING = {
    400: "BadRequestError",
    401: "UnauthorizedError",
    403: "ForbiddenError",
    404: "NotFoundError",
    429: "RateLimitExceededError",
    500: "InternalServerError",
}

# Files to process
USE_CASES_DIR = Path("application/use_cases")
FILES_TO_PROCESS = [
    "inventory_use_cases.py",
    "sales_use_cases.py",
    "customer_use_cases.py",
    "finance_use_cases.py",
    "credit_use_cases.py",
    "salary_use_cases.py",
    "dashboard_use_cases.py",
]


def refactor_file(file_path: Path) -> bool:
    """Refactor a single file."""
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return False

    content = file_path.read_text(encoding="utf-8")
    original_content = content

    # Add imports if needed
    if "from shared.exceptions.specific import" not in content:
        # Find the BaseAPIException import line
        base_import_pattern = r"(from shared\.exceptions\.base import BaseAPIException)"
        if re.search(base_import_pattern, content):
            # Add specific exceptions import
            content = re.sub(
                base_import_pattern,
                r"\1\nfrom shared.exceptions.specific import BadRequestError, ForbiddenError, NotFoundError, UnauthorizedError, RateLimitExceededError, InternalServerError",
                content,
            )

    # Pattern to match BaseAPIException with status_code
    pattern = (
        r'raise BaseAPIException\(\s*detail="([^"]+)",\s*code="([^"]+)",\s*status_code=(\d+),?\s*\)'
    )

    def replace_exception(match):
        detail = match.group(1)
        code = match.group(2)
        status_code = int(match.group(3))

        exception_class = EXCEPTION_MAPPING.get(status_code, "BaseAPIException")
        if exception_class == "BaseAPIException":
            return match.group(0)  # Keep original if no mapping

        return f'raise {exception_class}(\n                detail="{detail}",\n                code="{code}",\n            )'

    content = re.sub(pattern, replace_exception, content)

    # Also handle cases with details parameter
    pattern_with_details = r'raise BaseAPIException\(\s*detail="([^"]+)",\s*code="([^"]+)",\s*status_code=(\d+),\s*details=([^,]+),?\s*\)'

    def replace_exception_with_details(match):
        detail = match.group(1)
        code = match.group(2)
        status_code = int(match.group(3))
        details = match.group(4)

        exception_class = EXCEPTION_MAPPING.get(status_code, "BaseAPIException")
        if exception_class == "BaseAPIException":
            return match.group(0)

        return f'raise {exception_class}(\n                detail="{detail}",\n                code="{code}",\n                details={details},\n            )'

    content = re.sub(pattern_with_details, replace_exception_with_details, content)

    if content != original_content:
        file_path.write_text(content, encoding="utf-8")
        print(f"✓ Refactored: {file_path}")
        return True
    else:
        print(f"- No changes: {file_path}")
        return False


def main():
    """Main function."""
    base_dir = Path(__file__).parent.parent
    use_cases_dir = base_dir / USE_CASES_DIR

    if not use_cases_dir.exists():
        print(f"Directory not found: {use_cases_dir}")
        return

    refactored_count = 0
    for filename in FILES_TO_PROCESS:
        file_path = use_cases_dir / filename
        if refactor_file(file_path):
            refactored_count += 1

    print(f"\n✓ Refactored {refactored_count} file(s)")


if __name__ == "__main__":
    main()
