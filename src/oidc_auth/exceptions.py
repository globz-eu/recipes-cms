"""Exceptions that refuse a social login with a user-facing message."""

from social_core.exceptions import AuthPolicyError


class LoginRefused(AuthPolicyError):
    """A social login refused by our own rules; handled by LoginRefusedMiddleware."""

    auth_error: str = "login_refused"
    message: str = "Sign-in was refused."

    def __str__(self) -> str:
        return self.message


class EmailMissing(LoginRefused):
    auth_error = "email_missing"
    message = "Your sign-in provider did not share an email address."


class EmailNotVerified(LoginRefused):
    auth_error = "email_unverified"
    message = (
        "Please verify your email address with your provider. "
        "If you didn't get a verification email, ask an administrator to resend it."
    )


class EmailOwnedElsewhere(LoginRefused):
    auth_error = "email_in_use"
    message = (
        "This email address is already used by another sign-in method. "
        "Sign in the way you did before, or ask an administrator."
    )


class AlreadySignedIn(LoginRefused):
    auth_error = "already_signed_in"
    message = (
        "You are already signed in. Sign out first to use a different sign-in method."
    )


class OrgMismatch(LoginRefused):
    auth_error = "org_mismatch"
    message = "This account does not belong to this site's sign-in organisation."
