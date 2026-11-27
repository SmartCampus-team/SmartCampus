// Nouvelle demande administrative (SC-34, EF-REQ-01, EF-REQ-02) : l'étudiant choisit un type et
// décrit sa demande ; son nom et son e-mail viennent de son compte. Après le dépôt, le numéro
// DA-AAAA-NNNNN attribué par l'API s'affiche (SC-35 : lien vers « Mes demandes »). Adresse : #/demandes/nouvelle

import { useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import {
  createRequest,
  REQUEST_STATUS_LABELS,
  REQUEST_TYPE_LABELS,
  REQUEST_TYPES,
  type AdminRequest,
  type RequestType,
} from '../api/requests'
import type { Session } from '../auth/session'
import { CheckIcon, FileIcon } from '../components/icons'
import { Link } from '../router'
import './NewRequestPage.css'

interface Props {
  session: Session
}

const MAX_DESCRIPTION = 2000

export default function NewRequestPage({ session }: Props) {
  const [requestType, setRequestType] = useState<RequestType>('attestation_scolarite')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState<AdminRequest | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = description.trim()
    setError(text.length < 3 ? 'Décrivez votre demande (3 caractères au moins).' : null)
    setServerError(null)
    if (text.length < 3) return

    setBusy(true)
    try {
      setCreated(await createRequest(session, { request_type: requestType, description: text }))
    } catch (err) {
      setServerError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  function startOver() {
    setCreated(null)
    setDescription('')
    setRequestType('attestation_scolarite')
  }

  if (created) {
    return (
      <>
        <header className="page-head">
          <div>
            <h1>Demande déposée</h1>
            <p>La scolarité va la prendre en charge ; son statut change à chaque étape.</p>
          </div>
        </header>
        <section className="panel request-created" role="status" aria-live="polite">
          <CheckIcon className="request-created-icon" />
          <p className="request-created-label">Numéro de votre demande</p>
          <p className="request-created-number">{created.number}</p>
          <p>
            {REQUEST_TYPE_LABELS[created.request_type]} · statut « {REQUEST_STATUS_LABELS[created.status]} ». Notez ce
            numéro : il identifie votre demande auprès de la scolarité.
          </p>
          <div className="form-actions">
            <button type="button" className="button-secondary" onClick={startOver}>
              Déposer une autre demande
            </button>
            <Link to="/demandes" className="button-secondary">
              Voir mes demandes
            </Link>
          </div>
        </section>
      </>
    )
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Nouvelle demande</h1>
          <p>Demandez un document ou signalez un problème à la scolarité, sans vous déplacer au guichet.</p>
        </div>
      </header>

      <form className="panel request-form" onSubmit={handleSubmit} noValidate>
        <fieldset className="request-applicant">
          <legend>Demandeur</legend>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="request-name">Nom</label>
              <input id="request-name" className="input" value={session.user.full_name} readOnly />
            </div>
            <div className="field">
              <label htmlFor="request-email">E-mail</label>
              <input id="request-email" className="input" value={session.user.email} readOnly />
            </div>
          </div>
          <p className="field-hint">Repris de votre compte : ils ne se modifient pas ici.</p>
        </fieldset>

        <div className="field">
          <label htmlFor="request-type">Type de demande</label>
          <select
            id="request-type"
            className="select"
            value={requestType}
            onChange={(event) => setRequestType(event.target.value as RequestType)}
          >
            {REQUEST_TYPES.map((value) => (
              <option key={value} value={value}>
                {REQUEST_TYPE_LABELS[value]}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="request-description">Description</label>
          <textarea
            id="request-description"
            className="textarea"
            rows={6}
            maxLength={MAX_DESCRIPTION}
            value={description}
            placeholder="Précisez ce dont vous avez besoin : nombre d'exemplaires, semestre concerné, destinataire…"
            onChange={(event) => setDescription(event.target.value)}
            aria-invalid={!!error}
            aria-describedby={
              error ? 'request-description-error request-description-count' : 'request-description-count'
            }
          />
          <p id="request-description-count" className="field-hint request-count">
            {description.length} / {MAX_DESCRIPTION} caractères
          </p>
          {error && (
            <p id="request-description-error" className="field-error">
              {error}
            </p>
          )}
        </div>

        {serverError && (
          <p className="notice notice-error" role="alert">
            {serverError}
          </p>
        )}

        <div className="form-actions">
          <button type="submit" className="button-primary" disabled={busy}>
            <FileIcon />
            {busy ? 'Dépôt…' : 'Déposer la demande'}
          </button>
        </div>
      </form>
    </>
  )
}
