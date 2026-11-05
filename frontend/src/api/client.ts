
import { clearSession, type Session, type SessionUser } from '../auth/session'

export class ApiError extends Error {
  status: number
  detail: string | null

  constructor(status: number, detail: string | null) {
    super(detail ?? `Erreur HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

async function readError(response: Response): Promise<ApiError> {
  let detail: string | null = null
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') detail = body.detail
  } catch {
    // réponse sans JSON
  }
  return new ApiError(response.status, detail)
}

export async function login(email: string, password: string): Promise<Session> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) throw await readError(response)
  const body = await response.json()
  return { accessToken: body.access_token, expiresAt: body.expires_at, user: body.user }
}

// Appelé quand l'API refuse le jeton (expiré, révoqué) : l'écran revient à la connexion
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

export async function authFetch(session: Session, path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${session.accessToken}`)
  const response = await fetch(path, { ...init, headers })
  if (response.status === 401) {
    clearSession()
    onUnauthorized?.()
  }
  if (!response.ok) throw await readError(response)
  return response
}

export async function fetchMe(session: Session): Promise<SessionUser> {
  const response = await authFetch(session, '/api/auth/me')
  return response.json()
}

export async function logout(session: Session): Promise<void> {
  try {
    await authFetch(session, '/api/auth/logout', { method: 'POST' })
  } finally {
    // Même si l'API est injoignable, la session locale est effacée
    clearSession()
  }
}

// Appels JSON de l'API pour les pages du Sprint 2 (SC-17)

export const SERVER_UNREACHABLE = 'Serveur injoignable. Réessayez dans un instant.'

/** Requête authentifiée qui renvoie le JSON de la réponse (undefined pour une réponse 204). */
export async function apiJson<T>(
  session: Session,
  path: string,
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' = 'GET',
  body?: unknown,
): Promise<T> {
  const init: RequestInit = { method }
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  const response = await authFetch(session, path, init)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

/** Message à afficher pour une erreur d'appel : celui de l'API s'il existe. */
export function errorMessage(error: unknown, fallback = SERVER_UNREACHABLE): string {
  if (error instanceof ApiError && error.status < 500 && error.detail) return error.detail
  return fallback
}
