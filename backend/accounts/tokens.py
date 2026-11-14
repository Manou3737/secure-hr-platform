from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(
    PasswordResetTokenGenerator
):
    """Generate tokens exclusively for email verification."""

    key_salt = (
        "accounts.tokens.EmailVerificationTokenGenerator"
    )


email_verification_token_generator = (
    EmailVerificationTokenGenerator()
)
