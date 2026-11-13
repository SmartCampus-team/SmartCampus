// Confirmation avant d'annuler une réservation (SC-29, EF-BOOK-04, ENF-18) : depuis « Mes réservations »
// pour le titulaire, depuis le planning pour le gestionnaire (avec un motif facultatif).
// Annulée, la réservation n'est jamais supprimée : elle passe dans l'onglet « Annulées ».

import { useState, type FormEvent } from 'react'
import { cancelBooking, type Booking } from '../api/bookings'
import { errorMessage } from '../api/client'
import type { Session } from '../auth/session'
import Dialog from '../components/Dialog'
import { formatLongDate, shortTime } from '../dates'

export interface CancelTarget {
  id: number
  roomCode: string
  date: string
  start: string
  end: string
  holderName?: string | null
}

interface Props {
  session: Session
  target: CancelTarget
  askReason?: boolean // gestionnaire : motif enregistré avec l'annulation
  onClose: () => void
  onCancelled: (booking: Booking) => void
}

export default function CancelBookingDialog({ session, target, askReason = false, onClose, onCancelled }: Props) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onCancelled(await cancelBooking(session, target.id, reason.trim() || undefined))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const when = `${formatLongDate(target.date)}, ${shortTime(target.start)} – ${shortTime(target.end)}`
  return (
    <Dialog
      open
      size="small"
      title="Annuler la réservation ?"
      description={
        <>
          Salle {target.roomCode}, {when}
          {target.holderName ? ` (${target.holderName})` : ''}. Le créneau redevient libre pour les autres ; la
          réservation reste visible dans les réservations annulées.
        </>
      }
      onClose={onClose}
      onSubmit={handleSubmit}
      footer={
        <>
          <button type="button" className="button-secondary" onClick={onClose}>
            Garder la réservation
          </button>
          <button type="submit" className="button-danger" disabled={busy}>
            {busy ? 'Annulation…' : 'Annuler la réservation'}
          </button>
        </>
      }
    >
      {(askReason || error) && (
        <>
          {askReason && (
            <div className="field">
              <label htmlFor="cancel-reason">Motif (facultatif)</label>
              <input
                id="cancel-reason"
                className="input"
                value={reason}
                maxLength={200}
                placeholder="Salle réquisitionnée pour un jury…"
                onChange={(event) => setReason(event.target.value)}
                data-autofocus
              />
              <p className="field-hint">Le titulaire le verra dans ses réservations annulées.</p>
            </div>
          )}
          {error && (
            <p className="notice notice-error" role="alert">
              {error}
            </p>
          )}
        </>
      )}
    </Dialog>
  )
}
