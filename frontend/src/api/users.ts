// Comptes et rôles, pour l'administrateur système (SC-17, EF-AUTH-07).

import type { Role, Session } from '../auth/session'
import { withQuery } from '../router'
import { apiJson } from './client'

export interface Account {
  id: number
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface AccountFilters {
  q?: string
  role?: Role | ''
  active?: 'true' | 'false' | ''
}

export interface AccountCreate {
  email: string
  full_name: string
  role: Role
}

/** Seuls les champs présents sont modifiés. */
export type AccountUpdate = Partial<AccountCreate & { is_active: boolean }>

const URL = '/api/users'

export function fetchAccounts(session: Session, filters: AccountFilters): Promise<Account[]> {
  return apiJson<Account[]>(session, withQuery(URL, { ...filters }))
}

export function createAccount(session: Session, input: AccountCreate): Promise<Account> {
  return apiJson<Account>(session, URL, 'POST', input)
}

export function updateAccount(session: Session, id: number, input: AccountUpdate): Promise<Account> {
  return apiJson<Account>(session, `${URL}/${id}`, 'PATCH', input)
}
