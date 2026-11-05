// Mot de passe oublié (SC-18, EF-AUTH-05) : appels sans session.

import { ApiError } from './client'

async function post(path: string, body: unknown): Promise<string> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  let detail: string | null = null
  try {
    const json = await response.json()
    if (typeof json?.detail === 'string') detail = json.detail
  } catch {
    // réponse sans JSON
  }
  if (!response.ok) throw new ApiError(response.status, detail)
  return detail ?? ''
}

/** Renvoie le message à afficher, le même que l'adresse ait un compte ou non. */
export function requestPasswordReset(email: string): Promise<string> {
  return post('/api/auth/password/forgot', { email })
}

/** Vérifie un lien à son ouverture ; rejette (400) s'il est expiré, déjà utilisé ou inconnu. */
export function checkResetLink(token: string): Promise<string> {
  return post('/api/auth/password/check', { token })
}

export function resetPassword(token: string, newPassword: string): Promise<string> {
  return post('/api/auth/password/reset', { token, new_password: newPassword })
}

/** Mêmes règles que l'API (backend/src/services/password_policy.py). */
export function passwordProblem(password: string): string | null {
  if (password.length < 8 || password.length > 64) return 'De 8 à 64 caractères.'
  if (!/\p{L}/u.test(password)) return 'Au moins une lettre.'
  if (!/\d/.test(password)) return 'Au moins un chiffre.'
  return null
}
