"""Exceptions that refuse a social login with a user-facing message."""

from social_core.exceptions import AuthException


class LoginRefused(AuthException):
    """A social login refused by our own rules; handled by LoginRefusedMiddleware."""

    code: str = "login_refused"
    message: str = "Sign-in was refused."

    def __str__(self) -> str:
        return self.message


class EmailNotVerified(LoginRefused):
    code = "email_unverified"
    message = "Your email address is not verified with this sign-in provider."


class EmailOwnedElsewhere(LoginRefused):
    code = "email_in_use"
    message = (
        "This email address is already used by another sign-in method. "
        "Sign in the way you did before, or ask an administrator."
    )


class AlreadySignedIn(LoginRefused):
    code = "already_signed_in"
    message = (
        "You are already signed in. Sign out first to use a different sign-in method."
    )
