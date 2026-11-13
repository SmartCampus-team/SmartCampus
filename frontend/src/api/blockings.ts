// Blocages d'une salle par le gestionnaire (SC-32, EF-ROOM-06).

import type { Session } from '../auth/session'
import { apiJson } from './client'

export interface Blocking {
  id: number
  room_id: number
  start_date: string // AAAA-MM-JJ, à l'heure du campus
  start_time: string // HH:MM:SS
  end_date: string
  end_time: string
  reason: string
  author_name: string | null
}

export interface BlockingCreated extends Blocking {
  cancelled_bookings: number // réservations annulées par le blocage
}

export interface BlockingInput {
  start_date: string
  start_time: string // HH:MM
  end_date: string
  end_time: string
  reason: string
}

/** Blocages en cours ou à venir de la salle. */
export function fetchBlockings(session: Session, roomId: number): Promise<Blocking[]> {
  return apiJson<Blocking[]>(session, `/api/rooms/${roomId}/blockings`)
}

export function createBlocking(session: Session, roomId: number, input: BlockingInput): Promise<BlockingCreated> {
  return apiJson<BlockingCreated>(session, `/api/rooms/${roomId}/blockings`, 'POST', input)
}

/** Lève un blocage ; les réservations déjà annulées ne sont pas rétablies. */
export function removeBlocking(session: Session, roomId: number, blockingId: number): Promise<void> {
  return apiJson<void>(session, `/api/rooms/${roomId}/blockings/${blockingId}`, 'DELETE')
}
