// Demandes administratives des étudiants (SC-34, EF-REQ-01, EF-REQ-02).

import type { Session } from '../auth/session'
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
