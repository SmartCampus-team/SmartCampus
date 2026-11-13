// Bloquer une salle sur une période (SC-32, EF-ROOM-06) : examen, maintenance, événement.
// Les réservations de la période qui ne sont pas terminées passent « Annulée » avec le motif ;
// le planning et la recherche en tiennent compte aussitôt. Le gestionnaire peut aussi lever
// un blocage en cours ou à venir.

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { createBlocking, fetchBlockings, removeBlocking, type Blocking, type BlockingCreated } from '../api/blockings'
import { errorMessage } from '../api/client'
import type { Session } from '../auth/session'
import Dialog from '../components/Dialog'
import { CLOSING, isValidIsoDate, OPENING, shortTime, timeOptions } from '../dates'
import './BlockingDialog.css'

interface Props {
  session: Session
  room: { id: number; code: string }
  initialDate: string
  onClose: () => void
  onBlocked: (blocking: BlockingCreated) => void
  onChanged?: () => void // un blocage a été levé
}

type Errors = Partial<Record<'period' | 'reason', string>>

const START_OPTIONS = timeOptions(OPENING, '19:30')
const END_OPTIONS = timeOptions('08:30', CLOSING)

/** « 12/11/2026 08:00 » */
export function formatMoment(date: string, time: string): string {
  const [year, month, day] = date.split('-')
  return `${day}/${month}/${year} ${shortTime(time)}`
}

export default function BlockingDialog({ session, room, initialDate, onClose, onBlocked, onChanged }: Props) {
  const [startDate, setStartDate] = useState(initialDate)
  const [startTime, setStartTime] = useState(OPENING)
  const [endDate, setEndDate] = useState(initialDate)
  const [endTime, setEndTime] = useState(CLOSING)
  const [reason, setReason] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // Blocages en cours ou à venir, et celui dont la levée attend confirmation
  const [blockings, setBlockings] = useState<Blocking[] | null>(null)
  const [confirming, setConfirming] = useState<number | null>(null)

  const load = useCallback(() => {
    fetchBlockings(session, room.id)
      .then(setBlockings)
      .catch(() => setBlockings([]))
  }, [session, room.id])

  useEffect(() => {
    load()
  }, [load])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found: Errors = {}
    if (!isValidIsoDate(startDate) || !isValidIsoDate(endDate)) found.period = 'Choisissez les deux dates.'
    else if (`${endDate}T${endTime}` <= `${startDate}T${startTime}`) found.period = 'La fin doit être après le début.'
    if (reason.trim().length < 3) found.reason = 'Indiquez le motif (3 caractères au moins).'
    setErrors(found)
    setServerError(null)
    if (Object.keys(found).length > 0) return

    setBusy(true)
    try {
      onBlocked(
        await createBlocking(session, room.id, {
          start_date: startDate,
          start_time: startTime,
          end_date: endDate,
          end_time: endTime,
          reason: reason.trim(),
        }),
      )
    } catch (err) {
      setServerError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRemove(blocking: Blocking) {
    setServerError(null)
    try {
      await removeBlocking(session, room.id, blocking.id)
      setConfirming(null)
      load()
      onChanged?.()
    } catch (err) {
      setServerError(errorMessage(err))
    }
  }

  return (
    <Dialog
      open
      title={`Bloquer la salle ${room.code}`}
      description="Examen, maintenance, événement : personne ne peut réserver la salle sur cette période. Les réservations qui la touchent et ne sont pas terminées sont annulées avec ce motif."
      onClose={onClose}
      onSubmit={handleSubmit}
      footer={
        <>
          <button type="button" className="button-secondary" onClick={onClose}>
            Fermer
          </button>
          <button type="submit" className="button-danger" disabled={busy}>
            {busy ? 'Blocage…' : 'Bloquer la salle'}
          </button>
        </>
      }
    >
      <div className="form-grid blocking-form-grid">
        <div className="field">
          <label htmlFor="blocking-start-date">Du</label>
          <input
            id="blocking-start-date"
            className="input"
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            aria-invalid={!!errors.period}
            aria-describedby={errors.period ? 'blocking-period-error' : undefined}
          />
        </div>
        <div className="field">
          <label htmlFor="blocking-start-time">À partir de</label>
          <select
            id="blocking-start-time"
            className="select"
            value={startTime}
            onChange={(event) => setStartTime(event.target.value)}
          >
            {START_OPTIONS.map((time) => (
              <option key={time}>{time}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="blocking-end-date">Au</label>
          <input
            id="blocking-end-date"
            className="input"
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            aria-invalid={!!errors.period}
            aria-describedby={errors.period ? 'blocking-period-error' : undefined}
          />
        </div>
        <div className="field">
          <label htmlFor="blocking-end-time">Jusqu'à</label>
          <select
            id="blocking-end-time"
            className="select"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
          >
            {END_OPTIONS.map((time) => (
              <option key={time}>{time}</option>
            ))}
          </select>
        </div>
        {errors.period && (
          <p id="blocking-period-error" className="field-error blocking-wide">
            {errors.period}
          </p>
        )}
        <div className="field blocking-wide">
          <label htmlFor="blocking-reason">Motif</label>
          <input
            id="blocking-reason"
            className="input"
            value={reason}
            maxLength={200}
            placeholder="Examen de mi-semestre, maintenance du réseau…"
            onChange={(event) => setReason(event.target.value)}
            aria-invalid={!!errors.reason}
            aria-describedby={errors.reason ? 'blocking-reason-error' : undefined}
            data-autofocus
          />
          {errors.reason && (
            <p id="blocking-reason-error" className="field-error">
              {errors.reason}
            </p>
          )}
        </div>
      </div>

      {serverError && (
        <p className="notice notice-error" role="alert">
          {serverError}
        </p>
      )}

      <section className="blocking-list" aria-labelledby="blocking-list-title">
        <h3 id="blocking-list-title">Blocages en cours et à venir</h3>
        {blockings === null && <p className="field-hint">Chargement…</p>}
        {blockings !== null && blockings.length === 0 && <p className="field-hint">Aucun blocage pour cette salle.</p>}
        {blockings !== null && blockings.length > 0 && (
          <ul>
            {blockings.map((blocking) => (
              <li key={blocking.id}>
                <span>
                  <strong>
                    {formatMoment(blocking.start_date, blocking.start_time)} →{' '}
                    {formatMoment(blocking.end_date, blocking.end_time)}
                  </strong>
                  <span className="blocking-reason">{blocking.reason}</span>
                </span>
                {confirming === blocking.id ? (
                  <span className="blocking-confirm">
                    <button type="button" className="button-link" onClick={() => setConfirming(null)}>
                      Garder
                    </button>
                    <button type="button" className="button-link is-danger" onClick={() => handleRemove(blocking)}>
                      Confirmer la levée
                    </button>
                  </span>
                ) : (
                  <button type="button" className="button-link" onClick={() => setConfirming(blocking.id)}>
                    Lever le blocage
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </Dialog>
  )
}
