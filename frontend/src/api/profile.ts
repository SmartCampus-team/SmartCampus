// Profil de l'utilisateur connecté (SC-19, EF-AUTH-06).

import type { Role, Session } from '../auth/session'
import { apiJson, authFetch } from './client'

export type NotificationChannel = 'les_deux' | 'email' | 'application'

export interface Profile {
  id: number
  email: string
  full_name: string
  role: Role
  phone: string | null
  notification_channel: NotificationChannel
  has_photo: boolean
}

export interface ProfileInput {
  full_name: string
  phone: string | null
  notification_channel: NotificationChannel
}

export const CHANNEL_LABELS: Record<NotificationChannel, string> = {
  les_deux: "Par e-mail et dans l'application",
  email: 'Par e-mail seulement',
  application: "Dans l'application seulement",
}

export const MAX_PHOTO_BYTES = 2 * 1024 * 1024

/** Événement envoyé quand la photo change : la barre du haut la recharge. */
export const PHOTO_CHANGED_EVENT = 'smartcampus:photo-changed'

export function fetchProfile(session: Session): Promise<Profile> {
  return apiJson<Profile>(session, '/api/me')
}

export function updateProfile(session: Session, input: ProfileInput): Promise<Profile> {
  return apiJson<Profile>(session, '/api/me', 'PATCH', input)
}

export async function uploadPhoto(session: Session, file: File): Promise<Profile> {
  const response = await authFetch(session, '/api/me/photo', {
    method: 'PUT',
    headers: { 'Content-Type': file.type },
    body: file,
  })
  return response.json()
}

export function deletePhoto(session: Session): Promise<void> {
  return apiJson<void>(session, '/api/me/photo', 'DELETE')
}

/** Photo de profil en adresse locale (blob:), ou null s'il n'y en a pas. */
export async function fetchPhotoUrl(session: Session): Promise<string | null> {
  const response = await fetch('/api/me/photo', {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  })
  if (!response.ok) return null
  return URL.createObjectURL(await response.blob())
}
