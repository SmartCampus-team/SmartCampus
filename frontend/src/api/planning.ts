// Planning d'une salle en vue jour ou semaine (SC-23, EF-ROOM-03).

import type { Session } from '../auth/session'
import { withQuery } from '../router'
import { apiJson } from './client'
import type { Room } from './rooms'

export type PlanningView = 'day' | 'week'

export interface PlanningEntry {
  kind: 'reservation' | 'blocage'
  id: number
  day: string // AAAA-MM-JJ
  start: string // HH:MM:SS
  end: string
  label: string // « Réservé », « En attente de validation », « Terminé », « Bloqué »
  status: 'confirmee' | 'en_attente' | 'terminee' | null // null pour un blocage
  detail: string | null // motif de la réservation (si visible) ou du blocage
  holder_name: string | null
  mine: boolean
}

export interface Planning {
  room: Room
  view: PlanningView
  days: string[]
  opening: string
  closing: string
  slot_minutes: number
  entries: PlanningEntry[]
}

export function fetchPlanning(session: Session, roomId: number, date: string, view: PlanningView): Promise<Planning> {
  return apiJson<Planning>(session, withQuery(`/api/rooms/${roomId}/planning`, { date, view }))
}
