

import type { Session } from '../auth/session'
import { withQuery } from '../router'
import { apiJson } from './client'

export type RoomType = 'amphitheatre' | 'salle_cours' | 'salle_td' | 'salle_tp' | 'salle_travail'
export type RoomStatus = 'active' | 'hors_service' | 'archivee'

export interface Room {
  id: number
  code: string
  building: string
  room_type: RoomType
  capacity: number
  status: RoomStatus
  description: string | null
}

export interface RoomInput {
  code: string
  building: string
  room_type: RoomType
  capacity: number
  description: string
}

export const ROOM_TYPE_LABELS: Record<RoomType, string> = {
  amphitheatre: 'Amphithéâtre',
  salle_cours: 'Salle de cours',
  salle_td: 'Salle de TD',
  salle_tp: 'Salle de TP',
  salle_travail: 'Salle de travail',
}

export const ROOM_STATUS_LABELS: Record<RoomStatus, string> = {
  active: 'Active',
  hors_service: 'Hors service',
  archivee: 'Archivée',
}

export const ROOM_TYPES = Object.keys(ROOM_TYPE_LABELS) as RoomType[]

export interface RoomFilters {
  q?: string // code ou bâtiment
  building?: string
  room_type?: RoomType | ''
  min_capacity?: number | null
}

export function fetchRooms(
  session: Session,
  options: RoomFilters & { includeArchived?: boolean } = {},
): Promise<Room[]> {
  const { includeArchived, ...filters } = options
  return apiJson<Room[]>(session, withQuery('/api/rooms', { ...filters, include_archived: includeArchived }))
}

export function createRoom(session: Session, input: RoomInput): Promise<Room> {
  return apiJson<Room>(session, '/api/rooms', 'POST', input)
}

export function updateRoom(session: Session, id: number, input: Partial<RoomInput>): Promise<Room> {
  return apiJson<Room>(session, `/api/rooms/${id}`, 'PATCH', input)
}

export function archiveRoom(session: Session, id: number): Promise<Room> {
  return apiJson<Room>(session, `/api/rooms/${id}/archive`, 'POST')
}

export interface SlotSearch extends RoomFilters {
  date: string // AAAA-MM-JJ
  start: string // HH:MM
  end: string // HH:MM
}

export interface Availability {
  date: string
  start: string // HH:MM:SS
  end: string
  rooms: Room[]
}

export function searchAvailableRooms(session: Session, search: SlotSearch): Promise<Availability> {
  return apiJson<Availability>(session, withQuery('/api/rooms/available', { ...search }))
}
