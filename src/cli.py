"""Break-glass CLI for Hometower administration.

Usage:
    python -m src.cli reset-password --username EMAIL [--password NEWPASS]

Hides the decision of how admins interact with the system off-band.
If argparse is replaced with Click, only this file changes.
"""
import argparse
import getpass
import sys

from sqlmodel import Session

from src.domain.auth import validate_password_strength
from src.services import user_service
from src.utils.db import engine
from src.utils.logger import logger


def _reset_password(email: str, new_password: str) -> int:
    """Reset the password for the user with the given email.

    Returns:
        0 on success, 1 on failure.
    """
    try:
        validate_password_strength(new_password)
    except ValueError as exc:
        logger.error("{}", str(exc))
        return 1
    with Session(engine) as session:
        try:
            user_service.reset_password_by_email(email, new_password, session)
        except ValueError as exc:
            logger.error("{}", str(exc))
            return 1
    logger.info("Password reset successfully for: {}", email)
    return 0


def main() -> None:
    """Entry point for the Hometower administration CLI."""
    parser = argparse.ArgumentParser(description="Hometower administration CLI")
    subparsers = parser.add_subparsers(dest="command")

    reset_cmd = subparsers.add_parser(
        "reset-password", help="Reset a user's password"
    )
    reset_cmd.add_argument(
        "--username", required=True, help="User email address"
    )
    reset_cmd.add_argument(
        "--password", default=None, help="New password (prompted if omitted)"
    )

    args = parser.parse_args()

    if args.command == "reset-password":
        password = args.password
        if password is None:
            password = getpass.getpass("New password: ")
        sys.exit(_reset_password(args.username, password))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
