// Navigation entre les pages par l'ancre de l'URL : #/salles, #/salles/3?vue=semaine (SC-17).
// Aucune dépendance de plus : le bouton Précédent du navigateur fonctionne et chaque page a son adresse.

import { useMemo, useSyncExternalStore, type AnchorHTMLAttributes } from 'react'

export interface Location {
  path: string // toujours commence par « / »
  query: URLSearchParams
}

type QueryValue = string | number | boolean | null | undefined | Array<string | number>

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}

function currentHash(): string {
  return window.location.hash
}

export function parseHash(hash: string): Location {
  const raw = hash.replace(/^#/, '')
  const separator = raw.indexOf('?')
  const path = separator === -1 ? raw : raw.slice(0, separator)
  const query = separator === -1 ? '' : raw.slice(separator + 1)
  return { path: path.startsWith('/') ? path : '/', query: new URLSearchParams(query) }
}

/** Page affichée ; le composant se redessine quand l'ancre change. */
export function useLocation(): Location {
  const hash = useSyncExternalStore(subscribe, currentHash)
  return useMemo(() => parseHash(hash), [hash])
}

/** Va à une page ; replace évite d'ajouter une entrée dans l'historique. */
export function navigate(to: string, options: { replace?: boolean } = {}): void {
  if (options.replace) {
    window.location.replace(`#${to}`)
  } else {
    window.location.hash = to
  }
}

/** « /salles/:id » et « /salles/3 » → { id: '3' } ; null si le chemin ne correspond pas. */
export function matchPath(pattern: string, path: string): Record<string, string> | null {
  const expected = pattern.split('/').filter(Boolean)
  const actual = path.split('/').filter(Boolean)
  if (expected.length !== actual.length) return null
  const params: Record<string, string> = {}
  for (let i = 0; i < expected.length; i += 1) {
    if (expected[i].startsWith(':')) {
      params[expected[i].slice(1)] = decodeURIComponent(actual[i])
    } else if (expected[i] !== actual[i]) {
      return null
    }
  }
  return params
}

/** Ajoute des paramètres à un chemin ; les valeurs vides sont ignorées. */
export function withQuery(path: string, params: Record<string, QueryValue>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '' || value === false) continue
    if (Array.isArray(value)) {
      value.forEach((item) => query.append(key, String(item)))
    } else {
      query.set(key, String(value))
    }
  }
  const text = query.toString()
  return text ? `${path}?${text}` : path
}

interface LinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  to: string
}

export function Link({ to, ...props }: LinkProps) {
  return <a href={`#${to}`} {...props} />
}
