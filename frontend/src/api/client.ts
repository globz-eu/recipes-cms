// Base URL of the Django backend. Empty when the frontend is served from the
// same origin (local compose setup); set to e.g. https://staging.example.com
// when the frontend is served from the static CDN host.
export const API_BASE: string = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, message: string, body: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface RequestOptions {
  method?: HttpMethod
  body?: unknown
}

const SAFE_METHODS: ReadonlySet<HttpMethod> = new Set(['GET'])

let csrfTokenPromise: Promise<string> | null = null

// The csrftoken cookie belongs to the backend host and can't be read from the
// frontend origin, so the token is fetched from the backend and cached.
export function getCsrfToken(): Promise<string> {
  if (!csrfTokenPromise) {
    csrfTokenPromise = fetch(apiUrl('/api/csrf/'), {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new ApiError(response.status, `HTTP ${response.status}: ${response.statusText}`)
        }
        const data = (await response.json()) as { csrfToken: string }
        return data.csrfToken
      })
      .catch((error: unknown) => {
        csrfTokenPromise = null
        throw error
      })
  }
  return csrfTokenPromise
}

export function resetCsrfToken(): void {
  csrfTokenPromise = null
}

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('Content-Type') ?? ''
  if (contentType.includes('application/json')) {
    return response.json()
  }
  const text = await response.text()
  return text || null
}

function isCsrfFailure(status: number, body: unknown): boolean {
  if (status !== 403) return false
  const text = typeof body === 'string' ? body : JSON.stringify(body ?? '')
  return text.includes('CSRF')
}

async function send(path: string, method: HttpMethod, body: unknown): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (!SAFE_METHODS.has(method)) {
    headers['X-CSRFToken'] = await getCsrfToken()
  }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  return fetch(apiUrl(path), {
    method,
    credentials: 'include',
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}

export async function apiRequest<T>(path: string, { method = 'GET', body }: RequestOptions = {}): Promise<T> {
  let response = await send(path, method, body)
  let responseBody = await parseBody(response)

  // The token rotates on login; refresh it once and retry.
  if (!SAFE_METHODS.has(method) && isCsrfFailure(response.status, responseBody)) {
    resetCsrfToken()
    response = await send(path, method, body)
    responseBody = await parseBody(response)
  }

  if (!response.ok) {
    throw new ApiError(response.status, `HTTP ${response.status}: ${response.statusText}`, responseBody)
  }

  return responseBody as T
}

export function apiFetch<T>(path: string): Promise<T> {
  return apiRequest<T>(path)
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, { method: 'POST', body })
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, { method: 'PUT', body })
}

export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, { method: 'PATCH', body })
}

export function apiDelete<T = void>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: 'DELETE' })
}
