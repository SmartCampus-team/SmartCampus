// « Mes réservations » (SC-28, EF-BOOK-03) : à venir, passées et annulées, en trois onglets.
// Chacun ne voit que ses propres réservations : l'API ne renvoie que celles de l'utilisateur connecté.
// SC-29 : bouton « Annuler » (avec confirmation), désactivé moins de 2 h avant le début, raison affichée.
// Adresse : #/reservations, #/reservations?onglet=passees

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { BOOKING_STATUS_LABELS, fetchMyBookings, type Booking, type BookingStatus, type MyBookings } from '../api/bookings'
import { errorMessage } from '../api/client'
import type { Session } from '../auth/session'
import { CalendarIcon, CalendarCheckIcon, ClockIcon, CloseIcon, MapPinIcon, SearchIcon, UsersIcon } from '../components/icons'
import { formatLongDate, parseIsoDate, shortTime } from '../dates'
import { Link, navigate, withQuery, type Location } from '../router'
import CancelBookingDialog from './CancelBookingDialog'
import { planningPath } from './RoomPlanningPage'
import './MyBookingsPage.css'

interface Props {
  session: Session
  location: Location
}

type Tab = keyof MyBookings

const TABS: { id: Tab; param: string; label: string; empty: string }[] = [
  { id: 'upcoming', param: 'a-venir', label: 'À venir', empty: "Vous n'avez aucune réservation à venir." },
  { id: 'past', param: 'passees', label: 'Passées', empty: 'Aucune réservation passée pour le moment.' },
  { id: 'cancelled', param: 'annulees', label: 'Annulées', empty: 'Aucune réservation annulée.' },
]

const STATUS_BADGE: Record<BookingStatus, string> = {
  confirmee: 'badge badge-success',
  en_attente: 'badge badge-warning',
  terminee: 'badge badge-info',
  non_honoree: 'badge badge-danger',
  annulee: 'badge badge-neutral',
  refusee: 'badge badge-danger',
}

export function tabPath(tab: Tab): string {
  const param = TABS.find((item) => item.id === tab)?.param
  return withQuery('/reservations', { onglet: tab === 'upcoming' ? undefined : param })
}

/** « 11/11/2026 à 14:32 » : date et heure d'un instant renvoyé par l'API. */
function formatDateTime(iso: string): string {
  const moment = new Date(iso)
  const time = moment.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  return `${moment.toLocaleDateString('fr-FR')} à ${time}`
}

/** Une réservation : salle, date, horaires, motif et statut ; `children` reçoit les actions. */
function BookingItem({ booking, back, children }: { booking: Booking; back: string; children?: ReactNode }) {
  const day = parseIsoDate(booking.date)
  return (
    <li className="booking-item">
      <div className="booking-day" aria-hidden="true">
        <span className="booking-day-number">{day.getDate()}</span>
        <span className="booking-day-month">{day.toLocaleDateString('fr-FR', { month: 'short' })}</span>
      </div>
      <div className="booking-body">
        <div className="booking-head">
          <h3>
            <Link to={planningPath(booking.room.id, { date: booking.date, back })}>Salle {booking.room.code}</Link>
          </h3>
          <span className={STATUS_BADGE[booking.status]}>{BOOKING_STATUS_LABELS[booking.status]}</span>
        </div>
        <ul className="booking-meta">
          <li>
            <CalendarIcon />
            {formatLongDate(booking.date)}
          </li>
          <li>
            <ClockIcon />
            {shortTime(booking.start)} – {shortTime(booking.end)}
          </li>
          <li>
            <MapPinIcon />
            {booking.room.building}
          </li>
          <li>
            <UsersIcon />
            {booking.participants} participant{booking.participants > 1 ? 's' : ''}
          </li>
        </ul>
        <p className="booking-purpose">{booking.purpose}</p>
        {booking.cancelled_at && (
          <p className="booking-cancelled">
            Annulée le {formatDateTime(booking.cancelled_at)}
            {booking.cancel_reason ? ` · Motif : ${booking.cancel_reason}` : ''}
          </p>
        )}
        {children && <div className="booking-actions">{children}</div>}
      </div>
    </li>
  )
}

export default function MyBookingsPage({ session, location }: Props) {
  const tab = TABS.find((item) => item.param === location.query.get('onglet'))?.id ?? 'upcoming'
  const [bookings, setBookings] = useState<MyBookings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState<Booking | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const tabRefs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({})

  const load = useCallback(() => {
    return fetchMyBookings(session)
      .then((result) => {
        setBookings(result)
        setError(null)
      })
      .catch((err) => setError(errorMessage(err)))
  }, [session])

  useEffect(() => {
    load()
  }, [load])

  function handleCancelled(booking: Booking) {
    setCancelling(null)
    setMessage(
      `Réservation annulée : salle ${booking.room.code}, ${formatLongDate(booking.date)}, ` +
        `${shortTime(booking.start)} – ${shortTime(booking.end)}. Le créneau est de nouveau libre.`,
    )
    load()
  }

  /** Bouton « Annuler » d'une réservation à venir ; désactivé avec la raison donnée par l'API (RG-05). */
  function cancelAction(booking: Booking) {
    return (
      <>
        <button
          type="button"
          className="button-secondary booking-cancel"
          disabled={!booking.can_cancel}
          aria-describedby={booking.can_cancel ? undefined : `cancel-why-${booking.id}`}
          onClick={() => {
            setMessage(null)
            setCancelling(booking)
          }}
        >
          <CloseIcon />
          Annuler
        </button>
        {!booking.can_cancel && booking.cancel_refusal && (
          <span id={`cancel-why-${booking.id}`} className="booking-action-hint">
            {booking.cancel_refusal}
          </span>
        )}
      </>
    )
  }

  function select(next: Tab, focus = false) {
    navigate(tabPath(next), { replace: true })
    if (focus) tabRefs.current[next]?.focus()
  }

  // Onglets au clavier : flèches gauche et droite, Début et Fin
  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = TABS.length - 1
    const target =
      event.key === 'ArrowRight' ? (index === last ? 0 : index + 1)
      : event.key === 'ArrowLeft' ? (index === 0 ? last : index - 1)
      : event.key === 'Home' ? 0
      : event.key === 'End' ? last
      : null
    if (target === null) return
    event.preventDefault()
    select(TABS[target].id, true)
  }

  const current = TABS.find((item) => item.id === tab) ?? TABS[0]
  const list = bookings ? bookings[tab] : []
  const back = tabPath(tab)

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Mes réservations</h1>
          <p>Retrouvez où et quand vous avez une salle : réservations à venir, passées et annulées.</p>
        </div>
        <Link to="/salles" className="button-primary booking-cta">
          <SearchIcon />
          Réserver une salle
        </Link>
      </header>

      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="notice notice-success booking-message" role="status">
          {message}
        </p>
      )}

      <div className="booking-tabs" role="tablist" aria-label="Mes réservations">
        {TABS.map((item, index) => (
          <button
            key={item.id}
            ref={(element) => {
              tabRefs.current[item.id] = element
            }}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={item.id === tab}
            aria-controls="booking-panel"
            tabIndex={item.id === tab ? 0 : -1}
            className={item.id === tab ? 'booking-tab is-active' : 'booking-tab'}
            onClick={() => select(item.id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
          >
            {item.label}
            {bookings && <span className="booking-tab-count">{bookings[item.id].length}</span>}
          </button>
        ))}
      </div>

      <section id="booking-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="booking-panel">
        {bookings === null && !error && <p className="loading">Chargement de vos réservations…</p>}

        {bookings !== null && list.length === 0 && (
          <div className="empty-state">
            <CalendarCheckIcon className="empty-icon" />
            <p>{current.empty}</p>
            {tab === 'upcoming' && (
              <Link to="/salles" className="button-secondary">
                Trouver une salle libre
              </Link>
            )}
          </div>
        )}

        {list.length > 0 && (
          <ul className="booking-list">
            {list.map((booking) => (
              <BookingItem key={booking.id} booking={booking} back={back}>
                {tab === 'upcoming' && cancelAction(booking)}
              </BookingItem>
            ))}
          </ul>
        )}
      </section>

      {cancelling && (
        <CancelBookingDialog
          session={session}
          target={{
            id: cancelling.id,
            roomCode: cancelling.room.code,
            date: cancelling.date,
            start: cancelling.start,
            end: cancelling.end,
          }}
          onClose={() => setCancelling(null)}
          onCancelled={handleCancelled}
        />
      )}
    </>
  )
}
