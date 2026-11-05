// Avatar : photo de profil, ou initiales à défaut (SC-19).

import { useEffect, useState } from 'react'
import { fetchPhotoUrl, fetchProfile, PHOTO_CHANGED_EVENT } from '../api/profile'
import type { Session } from '../auth/session'
import './Avatar.css'

export function initials(fullName: string): string {
  return fullName
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
}

/** Adresse locale de la photo de l'utilisateur connecté ; rechargée quand elle change. */
export function useProfilePhoto(session: Session): string | null {
  const [url, setUrl] = useState<string | null>(null)
  const token = session.accessToken

  useEffect(() => {
    let active = true
    let current: string | null = null

    async function load() {
      try {
        const profile = await fetchProfile(session)
        const next = profile.has_photo ? await fetchPhotoUrl(session) : null
        if (!active) {
          if (next) URL.revokeObjectURL(next)
          return
        }
        if (current) URL.revokeObjectURL(current)
        current = next
        setUrl(next)
      } catch {
        // Sans photo, les initiales restent affichées
      }
    }

    load()
    window.addEventListener(PHOTO_CHANGED_EVENT, load)
    return () => {
      active = false
      window.removeEventListener(PHOTO_CHANGED_EVENT, load)
      if (current) URL.revokeObjectURL(current)
    }
    // Relancé seulement quand le jeton change (la session change aussi quand le nom est modifié)
  }, [token])

  return url
}

interface Props {
  name: string
  photoUrl: string | null
  className?: string
}

export default function Avatar({ name, photoUrl, className = 'avatar' }: Props) {
  return (
    <span className={className} aria-hidden="true">
      {photoUrl ? <img src={photoUrl} alt="" /> : initials(name)}
    </span>
  )
}
