"""
Password validators for employee profiles.

Centralized location for password validation rules.
Modify constants below to adjust password requirements.
"""
from django.core.exceptions import ValidationError


# Password validation constants - modify these to change requirements
MAX_PASSWORD_LENGTH = 6
MIN_LETTERS_REQUIRED = 3
DEFAULT_PASSWORD = "abc123"


class EmployeePasswordValidator:
    """
    Validates employee password requirements.
    
    Rules:
    - Maximum length: MAX_PASSWORD_LENGTH characters
    - Minimum letters: MIN_LETTERS_REQUIRED alphabetic characters
    """
    
    def __call__(self, value):
        """Validate the password."""
        if not value:
            raise ValidationError("Password is required.")
        
        # Check maximum length
        if len(value) > MAX_PASSWORD_LENGTH:
            raise ValidationError(
                f"Password must be at most {MAX_PASSWORD_LENGTH} characters long."
            )
        
        # Check minimum letters
        letter_count = sum(1 for char in value if char.isalpha())
        if letter_count < MIN_LETTERS_REQUIRED:
            raise ValidationError(
                f"Password must contain at least {MIN_LETTERS_REQUIRED} letters."
            )
        
        return value
    
    def get_help_text(self):
        """Return help text for password field."""
        return (
            f"Password must be at most {MAX_PASSWORD_LENGTH} characters "
            f"and contain at least {MIN_LETTERS_REQUIRED} letters."
        )
