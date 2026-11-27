// Demandes administratives des étudiants : dépôt (SC-34, EF-REQ-01, EF-REQ-02), « Mes demandes »
// (SC-35, EF-REQ-04) et détail (SC-36, EF-REQ-05).

import type { Session } from '../auth/session'
import { withQuery } from '../router'
import { apiJson } from './client'

export type RequestType =
  'attestation_scolarite' | 'releve_notes' | 'certificat_reussite' | 'demande_stage' | 'reclamation' | 'autre'

export const REQUEST_TYPE_LABELS: Record<RequestType, string> = {
  attestation_scolarite: 'Attestation de scolarité',
  releve_notes: 'Relevé de notes',
  certificat_reussite: 'Certificat de réussite',
  demande_stage: 'Demande de stage',
  reclamation: 'Réclamation administrative',
  autre: 'Autre',
}

export const REQUEST_TYPES = Object.keys(REQUEST_TYPE_LABELS) as RequestType[]

// Cycle de vie d'une demande (RG-13, tableau 13 du cahier des charges)
export type RequestStatus = 'en_attente' | 'en_cours' | 'infos_demandees' | 'acceptee' | 'refusee' | 'terminee'

export const REQUEST_STATUS_LABELS: Record<RequestStatus, string> = {
  en_attente: 'En attente',
  en_cours: 'En cours de traitement',
  infos_demandees: 'Informations complémentaires demandées',
  acceptee: 'Acceptée',
  refusee: 'Refusée',
  terminee: 'Terminée',
}

export interface RequestStudent {
  id: number
  full_name: string
  email: string
}

export const REQUEST_STATUSES = Object.keys(REQUEST_STATUS_LABELS) as RequestStatus[]

/** Ligne d'une liste de demandes (SC-35) */
export interface RequestSummary {
  id: number
  number: string
  request_type: RequestType
  status: RequestStatus
  created_at: string
  updated_at: string
}

export interface AdminRequest {
  id: number
  number: string // DA-AAAA-NNNNN
  request_type: RequestType
  description: string
  status: RequestStatus
  created_at: string // date de dépôt
  updated_at: string // dernière mise à jour
  student: RequestStudent
}

export interface RequestInput {
  request_type: RequestType
  description: string
}

export function createRequest(session: Session, input: RequestInput): Promise<AdminRequest> {
  return apiJson<AdminRequest>(session, '/api/requests', 'POST', input)
}

/** « 24/11/2026 à 10:42 » : un instant renvoyé par l'API, à l'heure de l'ordinateur. */
export function formatDateTime(iso: string): string {
  const moment = new Date(iso)
  const time = moment.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  return `${moment.toLocaleDateString('fr-FR')} à ${time}`
}

export interface RequestFilters {
  q?: string // numéro ou partie du numéro
  status?: RequestStatus | ''
  type?: RequestType | ''
}

/** Mes demandes (SC-35) : l'API ne renvoie que celles de l'étudiant connecté. */
export function fetchMyRequests(session: Session, filters: RequestFilters = {}): Promise<RequestSummary[]> {
  return apiJson<RequestSummary[]>(session, withQuery('/api/requests/me', { ...filters }))
}

/** « 24/11/2026 » */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR')
}

/** Détail d'une demande (SC-36) : 404 pour la demande d'un autre étudiant. */
export function fetchRequest(session: Session, id: number): Promise<AdminRequest> {
  return apiJson<AdminRequest>(session, `/api/requests/${id}`)
}
