// Détail d'une demande (SC-36, EF-REQ-05, RG-14) : type, description, statut, dates, pièces jointes
// et réponse de la scolarité. L'étudiant n'ouvre que ses demandes (l'API répond 404 sinon) et
// n'a aucun bouton pour changer le statut ; l'agent de scolarité ouvre toutes les demandes.
// Adresse : #/demandes/12, éventuellement ?retour=… (la liste d'où l'on vient)

import { useEffect, useState } from 'react'
import { ApiError, errorMessage } from '../api/client'
import { fetchRequest, formatDateTime, REQUEST_TYPE_LABELS, type AdminRequest } from '../api/requests'
import type { Session } from '../auth/session'
import RequestStatusBadge from '../components/RequestStatusBadge'
import { ChevronLeftIcon } from '../components/icons'
import { Link, withQuery } from '../router'
import StatusPage from './StatusPage'
import './RequestDetailPage.css'

interface Props {
  session: Session
  requestId: number
  back: string | null
}

/** Adresse du détail ; `back` : la liste où revenir (avec ses filtres). */
export function requestPath(id: number, back?: string): string {
  return withQuery(`/demandes/${id}`, { retour: back })
}

export default function RequestDetailPage({ session, requestId, back }: Props) {
  const [request, setRequest] = useState<AdminRequest | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isRegistrar = session.user.role === 'scolarite'

  useEffect(() => {
    let active = true
    fetchRequest(session, requestId)
      .then((result) => {
        if (!active) return
        setRequest(result)
        setError(null)
      })
      .catch((err) => {
        if (!active) return
        if (err instanceof ApiError && err.status === 404) setNotFound(true)
        else setError(errorMessage(err))
      })
    return () => {
      active = false
    }
  }, [session, requestId])

  if (notFound) {
    return <StatusPage title="Demande introuvable" message="Cette demande n'existe pas ou ne vous appartient pas." />
  }

  const backTo = back && back.startsWith('/demandes') ? back : '/demandes'

  return (
    <>
      <Link to={backTo} className="back-link">
        <ChevronLeftIcon />
        Retour à mes demandes
      </Link>

      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}
      {request === null && !error && <p className="loading">Chargement de la demande…</p>}

      {request && (
        <>
          <header className="page-head request-head">
            <div>
              <h1>
                Demande <span>{request.number}</span>
              </h1>
              <p>{REQUEST_TYPE_LABELS[request.request_type]}</p>
            </div>
            <RequestStatusBadge status={request.status} />
          </header>

          <div className="request-detail">
            <section className="panel request-main" aria-labelledby="request-info-title">
              <h2 id="request-info-title" className="panel-title">
                Demande
              </h2>
              <dl className="request-facts">
                <div>
                  <dt>Type</dt>
                  <dd>{REQUEST_TYPE_LABELS[request.request_type]}</dd>
                </div>
                <div>
                  <dt>Déposée le</dt>
                  <dd>{formatDateTime(request.created_at)}</dd>
                </div>
                <div>
                  <dt>Dernière mise à jour</dt>
                  <dd>{formatDateTime(request.updated_at)}</dd>
                </div>
                {isRegistrar && (
                  <div>
                    <dt>Étudiant</dt>
                    <dd>
                      {request.student.full_name} ·{' '}
                      <a href={`mailto:${request.student.email}`}>{request.student.email}</a>
                    </dd>
                  </div>
                )}
              </dl>
              <h3 className="request-subtitle">Description</h3>
              <p className="request-description">{request.description}</p>
            </section>

            <div className="request-side">
              <section className="panel" aria-labelledby="request-answer-title">
                <h2 id="request-answer-title" className="panel-title">
                  Réponse de la scolarité
                </h2>
                <p className="request-empty">La scolarité n'a pas encore répondu.</p>
              </section>

              <section className="panel" aria-labelledby="request-files-title">
                <h2 id="request-files-title" className="panel-title">
                  Pièces jointes
                </h2>
                <p className="request-empty">Aucune pièce jointe.</p>
              </section>
            </div>
          </div>
        </>
      )}
    </>
  )
}
