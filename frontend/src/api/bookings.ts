// Réservations des salles (SC-25, EF-BOOK-01), « Mes réservations » (SC-28, EF-BOOK-03)
// et annulation (SC-29, EF-BOOK-04).

import type { Role, Session } from '../auth/session'
import { apiJson } from './client'
import type { RoomType } from './rooms'

export type BookingStatus = 'en_attente' | 'confirmee' | 'refusee' | 'annulee' | 'non_honoree' | 'terminee'

export const BOOKING_STATUS_LABELS: Record<BookingStatus, string> = {
  en_attente: 'En attente de validation',
  confirmee: 'Confirmée',
  refusee: 'Refusée',
  annulee: 'Annulée',
  non_honoree: 'Non honorée',
  terminee: 'Terminée',
}

export interface BookingRoom {
  id: number
  code: string
  building: string
  room_type: RoomType
  capacity: number
}

export interface Booking {
  id: number
  room: BookingRoom
  date: string // AAAA-MM-JJ, à l'heure du campus
  start: string // HH:MM:SS
  end: string
  purpose: string
  participants: number
  status: BookingStatus
  created_at: string
  // Annulation (SC-29) : l'API dit si le bouton est actif, et sinon pourquoi
  can_cancel: boolean
  cancel_refusal: string | null
  cancelled_at: string | null
  cancel_reason: string | null
}

export interface BookingInput {
  room_id: number
  date: string
  start: string // HH:MM
  end: string
  purpose: string
  participants: number
}

// Durée maximale d'une réservation selon le rôle (RG-03) ; l'API applique la même règle
export const MAX_BOOKING_MINUTES: Partial<Record<Role, number>> = { etudiant: 120, enseignant: 240 }

/** L'étudiant et l'enseignant réservent ; les autres rôles consultent seulement. */
export function canBook(role: Role): boolean {
  return MAX_BOOKING_MINUTES[role] !== undefined
}

export function createBooking(session: Session, input: BookingInput): Promise<Booking> {
  return apiJson<Booking>(session, '/api/bookings', 'POST', input)
}

// « Mes réservations » (SC-28, EF-BOOK-03) : les trois onglets, calculés par l'API

export interface MyBookings {
  upcoming: Booking[] // la plus proche d'abord
  past: Booking[] // la plus récente d'abord
  cancelled: Booking[]
}

export function fetchMyBookings(session: Session): Promise<MyBookings> {
  return apiJson<MyBookings>(session, '/api/bookings/me')
}

/** Annule une réservation (SC-29) ; le motif est facultatif (gestionnaire). */
export function cancelBooking(session: Session, id: number, reason?: string): Promise<Booking> {
  return apiJson<Booking>(session, `/api/bookings/${id}/cancel`, 'POST', reason ? { reason } : undefined)
}
