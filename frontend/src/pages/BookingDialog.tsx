// Réserver une salle sur un créneau (SC-25, EF-BOOK-01), depuis la recherche ou le planning.
// L'interface vérifie la grille (RG-03), la durée selon le rôle et la capacité (RG-08) ;
// l'API applique les mêmes règles et son message s'affiche s'il refuse.

import { useState, type FormEvent } from 'react'
import { createBooking, MAX_BOOKING_MINUTES, type Booking } from '../api/bookings'
import { errorMessage } from '../api/client'
import { ROOM_TYPE_LABELS, type Room } from '../api/rooms'
import type { Session } from '../auth/session'
import Dialog from '../components/Dialog'
import { CLOSING, isOpenDay, isValidIsoDate, OPENING, STEP_MINUTES, timeOptions, toMinutes } from '../dates'
import './BookingDialog.css'

export interface BookingDraft {
  date: string
  start: string
  end: string
  participants?: string
}

interface Props {
  session: Session
  room: Room
  initial: BookingDraft
  onClose: () => void
  onBooked: (booking: Booking) => void
}

interface FormState {
  date: string
  start: string
  end: string
  participants: string
  purpose: string
}

type Errors = Partial<Record<'date' | 'slot' | 'participants' | 'purpose', string>>

const START_OPTIONS = timeOptions(OPENING, '19:30')
const END_OPTIONS = timeOptions('08:30', CLOSING)

/** 120 → « 2 h », 90 → « 1 h 30 ». */
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest} min`
  return rest ? `${hours} h ${String(rest).padStart(2, '0')}` : `${hours} h`
}

function validate(form: FormState, room: Room, maxMinutes: number): Errors {
  const errors: Errors = {}
  if (!isValidIsoDate(form.date)) errors.date = 'Choisissez une date.'
  else if (!isOpenDay(form.date)) errors.date = 'Le campus est fermé le dimanche.'

  const start = toMinutes(form.start)
  const end = toMinutes(form.end)
  if (start % STEP_MINUTES !== 0 || end % STEP_MINUTES !== 0) {
    errors.slot = `Les créneaux vont par pas de ${STEP_MINUTES} min.`
  } else if (end <= start) {
    errors.slot = "L'heure de fin doit être après l'heure de début."
  } else if (end - start > maxMinutes) {
    errors.slot = `Une réservation dure au plus ${formatDuration(maxMinutes)} pour votre rôle.`
  }

  const participants = Number(form.participants)
  if (!form.participants || !Number.isInteger(participants) || participants < 1) {
    errors.participants = 'Indiquez le nombre de participants.'
  } else if (participants > room.capacity) {
    errors.participants = `La salle compte ${room.capacity} places : choisissez une salle plus grande.`
  }

  if (form.purpose.trim().length < 3) errors.purpose = 'Indiquez le motif (3 caractères au moins).'
  return errors
}

export default function BookingDialog({ session, room, initial, onClose, onBooked }: Props) {
  const maxMinutes = MAX_BOOKING_MINUTES[session.user.role] ?? 0
  const [form, setForm] = useState<FormState>({
    date: initial.date,
    start: initial.start,
    end: initial.end,
    participants: initial.participants ?? '',
    purpose: '',
  })
  const [errors, setErrors] = useState<Errors>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validate(form, room, maxMinutes)
    setErrors(found)
    setServerError(null)
    if (Object.keys(found).length > 0) return

    setBusy(true)
    try {
      const booking = await createBooking(session, {
        room_id: room.id,
        date: form.date,
        start: form.start,
        end: form.end,
        purpose: form.purpose.trim(),
        participants: Number(form.participants),
      })
      onBooked(booking)
    } catch (error) {
      setServerError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open
      title={`Réserver la salle ${room.code}`}
      description={`${ROOM_TYPE_LABELS[room.room_type]} · ${room.building} · ${room.capacity} places. Durée maximale : ${formatDuration(maxMinutes)}.`}
      onClose={onClose}
      onSubmit={handleSubmit}
      footer={
        <>
          <button type="button" className="button-secondary" onClick={onClose}>
            Annuler
          </button>
          <button type="submit" className="button-primary" disabled={busy}>
            {busy ? 'Réservation…' : 'Réserver'}
          </button>
        </>
      }
    >
      <div className="form-grid booking-form-grid">
        <div className="field">
          <label htmlFor="booking-date">Date</label>
          <input
            id="booking-date"
            className="input"
            type="date"
            value={form.date}
            onChange={(event) => update('date', event.target.value)}
            aria-invalid={!!errors.date}
            aria-describedby={errors.date ? 'booking-date-error' : undefined}
          />
          {errors.date && (
            <p id="booking-date-error" className="field-error">
              {errors.date}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="booking-start">Début</label>
          <select
            id="booking-start"
            className="select"
            value={form.start}
            onChange={(event) => update('start', event.target.value)}
            aria-invalid={!!errors.slot}
            aria-describedby={errors.slot ? 'booking-slot-error' : undefined}
          >
            {START_OPTIONS.map((time) => (
              <option key={time}>{time}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="booking-end">Fin</label>
          <select
            id="booking-end"
            className="select"
            value={form.end}
            onChange={(event) => update('end', event.target.value)}
            aria-invalid={!!errors.slot}
            aria-describedby={errors.slot ? 'booking-slot-error' : undefined}
          >
            {END_OPTIONS.map((time) => (
              <option key={time}>{time}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="booking-participants">Participants</label>
          <input
            id="booking-participants"
            className="input"
            type="number"
            min={1}
            max={room.capacity}
            inputMode="numeric"
            value={form.participants}
            onChange={(event) => update('participants', event.target.value)}
            aria-invalid={!!errors.participants}
            aria-describedby={errors.participants ? 'booking-participants-error' : undefined}
          />
          {errors.participants && (
            <p id="booking-participants-error" className="field-error">
              {errors.participants}
            </p>
          )}
        </div>
        {errors.slot && (
          <p id="booking-slot-error" className="field-error booking-slot-error">
            {errors.slot}
          </p>
        )}
        <div className="field booking-purpose">
          <label htmlFor="booking-purpose">Motif</label>
          <input
            id="booking-purpose"
            className="input"
            value={form.purpose}
            maxLength={200}
            placeholder="Révision en groupe, soutenance, réunion de club…"
            onChange={(event) => update('purpose', event.target.value)}
            aria-invalid={!!errors.purpose}
            aria-describedby={errors.purpose ? 'booking-purpose-error' : undefined}
            data-autofocus
          />
          {errors.purpose && (
            <p id="booking-purpose-error" className="field-error">
              {errors.purpose}
            </p>
          )}
        </div>
      </div>
      {serverError && (
        <p className="notice notice-error" role="alert">
          {serverError}
        </p>
      )}
    </Dialog>
  )
}
