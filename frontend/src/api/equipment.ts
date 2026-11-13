// Catalogue d'équipements et affectation aux salles (SC-31, EF-ROOM-05).

import type { Session } from '../auth/session'
import { apiJson } from './client'
import type { Room } from './rooms'

export type EquipmentCategory = 'audiovisuel' | 'informatique' | 'mobilier' | 'confort' | 'accessibilite'

export const EQUIPMENT_CATEGORY_LABELS: Record<EquipmentCategory, string> = {
  audiovisuel: 'Audiovisuel',
  informatique: 'Informatique',
  mobilier: 'Mobilier',
  confort: 'Confort',
  accessibilite: 'Accessibilité',
}

export const EQUIPMENT_CATEGORIES = Object.keys(EQUIPMENT_CATEGORY_LABELS) as EquipmentCategory[]

export interface Equipment {
  id: number
  label: string
  category: EquipmentCategory
}

export interface CatalogueItem extends Equipment {
  room_count: number // salles non archivées équipées
}

export interface EquipmentInput {
  label: string
  category: EquipmentCategory
}

export function fetchEquipment(session: Session): Promise<CatalogueItem[]> {
  return apiJson<CatalogueItem[]>(session, '/api/equipment')
}

export function createEquipment(session: Session, input: EquipmentInput): Promise<Equipment> {
  return apiJson<Equipment>(session, '/api/equipment', 'POST', input)
}

export function updateEquipment(session: Session, id: number, input: Partial<EquipmentInput>): Promise<Equipment> {
  return apiJson<Equipment>(session, `/api/equipment/${id}`, 'PATCH', input)
}

/** Remplace les équipements de la salle par ceux de la liste. */
export function setRoomEquipment(session: Session, roomId: number, equipmentIds: number[]): Promise<Room> {
  return apiJson<Room>(session, `/api/rooms/${roomId}/equipment`, 'PUT', { equipment_ids: equipmentIds })
}

/** Par ordre alphabétique français (« Écran » avec les E), quel que soit le classement de la base. */
export function sortByLabel<T extends Equipment>(items: T[]): T[] {
  return [...items].sort((a, b) => a.label.localeCompare(b.label, 'fr'))
}
