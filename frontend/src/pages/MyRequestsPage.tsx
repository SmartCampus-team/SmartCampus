// « Mes demandes » (SC-35, EF-REQ-04, RG-14) : numéro, type, statut, dates de dépôt et de mise à jour.
// Recherche par numéro, filtres par statut et par type ; l'API ne renvoie que les demandes de
// l'étudiant connecté. Adresse : #/demandes?q=00042&statut=en_attente&type=releve_notes

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import {
  fetchMyRequests,
  formatDate,
  formatDateTime,
  REQUEST_STATUS_LABELS,
  REQUEST_STATUSES,
  REQUEST_TYPE_LABELS,
  REQUEST_TYPES,
  type RequestFilters,
  type RequestStatus,
  type RequestSummary,
  type RequestType,
} from '../api/requests'
import type { Session } from '../auth/session'
import RequestStatusBadge from '../components/RequestStatusBadge'
import { FileIcon, PlusIcon, SearchIcon } from '../components/icons'
import { Link, navigate, withQuery, type Location } from '../router'
import './MyRequestsPage.css'

interface Props {
  session: Session
  location: Location
}

function filtersFromQuery(query: URLSearchParams): Required<RequestFilters> {
  const status = query.get('statut')
  const type = query.get('type')
  return {
    q: query.get('q') ?? '',
    status: REQUEST_STATUSES.includes(status as RequestStatus) ? (status as RequestStatus) : '',
    type: REQUEST_TYPES.includes(type as RequestType) ? (type as RequestType) : '',
  }
}

function filtersToPath(filters: RequestFilters): string {
  return withQuery('/demandes', { q: filters.q?.trim(), statut: filters.status, type: filters.type })
}

export default function MyRequestsPage({ session, location }: Props) {
  const applied = useMemo(() => filtersFromQuery(location.query), [location.query])
  const [form, setForm] = useState(applied)
  const [requests, setRequests] = useState<RequestSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => setForm(applied), [applied])

  useEffect(() => {
    let active = true
    fetchMyRequests(session, applied)
      .then((list) => {
        if (!active) return
        setRequests(list)
        setError(null)
      })
      .catch((err) => active && setError(errorMessage(err)))
    return () => {
      active = false
    }
  }, [session, applied])

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    navigate(filtersToPath(form), { replace: true })
  }

  const filtered = applied.q !== '' || applied.status !== '' || applied.type !== ''

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Mes demandes</h1>
          <p>Suivez le statut de vos demandes et lisez la réponse de la scolarité.</p>
        </div>
        <Link to="/demandes/nouvelle" className="button-primary request-cta">
          <PlusIcon />
          Nouvelle demande
        </Link>
      </header>

      <form className="panel request-filters" onSubmit={handleSubmit} role="search" aria-label="Filtrer mes demandes">
        <div className="field">
          <label htmlFor="filter-q">Numéro</label>
          <input
            id="filter-q"
            className="input"
            value={form.q}
            maxLength={20}
            placeholder="DA-2026-00042"
            onChange={(event) => setForm({ ...form, q: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="filter-status">Statut</label>
          <select
            id="filter-status"
            className="select"
            value={form.status}
            onChange={(event) => setForm({ ...form, status: event.target.value as RequestStatus | '' })}
          >
            <option value="">Tous les statuts</option>
            {REQUEST_STATUSES.map((value) => (
              <option key={value} value={value}>
                {REQUEST_STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-type">Type</label>
          <select
            id="filter-type"
            className="select"
            value={form.type}
            onChange={(event) => setForm({ ...form, type: event.target.value as RequestType | '' })}
          >
            <option value="">Tous les types</option>
            {REQUEST_TYPES.map((value) => (
              <option key={value} value={value}>
                {REQUEST_TYPE_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
        <div className="request-filters-actions">
          <button type="submit" className="button-primary">
            <SearchIcon />
            Rechercher
          </button>
          {filtered && (
            <Link to="/demandes" className="button-secondary">
              Effacer
            </Link>
          )}
        </div>
      </form>

      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}

      {requests === null && !error && <p className="loading">Chargement de vos demandes…</p>}

      {requests !== null && requests.length === 0 && (
        <div className="empty-state">
          <FileIcon className="empty-icon" />
          {filtered ? (
            <p>Aucune demande ne correspond à ces critères.</p>
          ) : (
            <>
              <p>Vous n'avez encore déposé aucune demande.</p>
              <Link to="/demandes/nouvelle" className="button-secondary">
                Nouvelle demande
              </Link>
            </>
          )}
        </div>
      )}

      {requests !== null && requests.length > 0 && (
        <section aria-labelledby="requests-count">
          <h2 id="requests-count" className="request-count-title">
            {requests.length} demande{requests.length > 1 ? 's' : ''}
          </h2>
          <ul className="request-list">
            {requests.map((request) => (
              <li key={request.id} className="request-item">
                <div className="request-item-head">
                  <h3 className="request-number">{request.number}</h3>
                  <RequestStatusBadge status={request.status} />
                </div>
                <p className="request-type">{REQUEST_TYPE_LABELS[request.request_type]}</p>
                <p className="request-dates">
                  Déposée le {formatDate(request.created_at)} · mise à jour le {formatDateTime(request.updated_at)}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
