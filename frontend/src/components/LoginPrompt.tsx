import { apiUrl } from '../api/client'

export function LoginPrompt() {
  const next = encodeURIComponent(window.location.href)
  return (
    <div className="auth-prompt">
      <p>You must be logged in to view this content.</p>
      <a href={apiUrl(`/login/auth0_openidconnect/?next=${next}`)}>Log in with Auth0</a>
    </div>
  )
}
