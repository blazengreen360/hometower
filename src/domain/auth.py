"""Auth domain logic — pure functions, no I/O.

Only imports standard-library modules. No SQLModel, FastAPI, or network calls.
"""


def validate_password_strength(password: str) -> None:
    """Raise ValueError if password does not meet minimum strength requirements.

    Current rule: minimum 8 characters. Complexity rules beyond length are
    intentionally omitted for homelab ergonomics — see HT-025 Non-Goals.

    Args:
        password: The plaintext password to validate.

    Raises:
        ValueError: when the password is shorter than 8 characters.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
