export function LoginPrompt() {
  return (
    <div className="auth-prompt">
      <p>You must be logged in to view this content.</p>
      <a href="/login/auth0_openidconnect/?next=/frontend/">Log in with Auth0</a>
    </div>
  )
}
