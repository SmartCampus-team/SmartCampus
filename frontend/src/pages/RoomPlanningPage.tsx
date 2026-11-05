// Planning d'occupation d'une salle (SC-23, EF-ROOM-03, RG-03) : vue jour par défaut, par pas
// de 30 min de 08:00 à 20:00, ou vue semaine du lundi au samedi. Chaque créneau occupé porte un
// libellé (Réservé, En attente de validation, Bloqué), pas seulement une couleur.
// Adresse : #/salles/3?date=2026-11-02&vue=semaine

import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { ApiError, errorMessage } from '../api/client'
import { fetchPlanning, type Planning, type PlanningEntry, type PlanningView } from '../api/planning'
import { ROOM_STATUS_LABELS, ROOM_TYPE_LABELS } from '../api/rooms'
import type { Session } from '../auth/session'
import { ChevronLeftIcon, ChevronRightIcon, MapPinIcon, UsersIcon } from '../components/icons'
import {
  addDays,
  formatLongDate,
  formatShortDay,
  fromMinutes,
  isoDate,
  isOpenDay,
  isValidIsoDate,
  parseIsoDate,
  shortTime,
  toMinutes,
} from '../dates'
import { Link, navigate, withQuery, type Location } from '../router'
import StatusPage from './StatusPage'
import './RoomPlanningPage.css'

interface Props {
  session: Session
  roomId: number
  location: Location
}

const VIEW_PARAM: Record<PlanningView, string> = { day: 'jour', week: 'semaine' }

/** Lien vers le planning d'une salle (SC-23) ; `back` ramène à la recherche d'origine. */
export function planningPath(roomId: number, options: { date?: string; view?: PlanningView; back?: string } = {}) {
  return withQuery(`/salles/${roomId}`, {
    date: options.date,
    vue: options.view ? VIEW_PARAM[options.view] : undefined,
    retour: options.back,
  })
}

function weekTitle(days: string[]): string {
  const first = parseIsoDate(days[0])
  const last = parseIsoDate(days[days.length - 1])
  const end = last.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
  const start =
    first.getMonth() === last.getMonth()
      ? String(first.getDate())
      : first.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
  return `Semaine du ${start} au ${end}`
}

/** Jour ouvré suivant ou précédent (le dimanche est sauté). */
function stepDay(date: string, direction: 1 | -1): string {
  const next = addDays(date, direction)
  return isOpenDay(next) ? next : addDays(next, direction)
}

function entryClass(entry: PlanningEntry): string {
  const classes = ['planning-entry']
  if (entry.kind === 'blocage') classes.push('is-blocage')
  else if (entry.status === 'en_attente') classes.push('is-attente')
  else if (entry.status === 'terminee') classes.push('is-termine')
  else classes.push('is-reserve')
  if (entry.mine) classes.push('is-mine')
  return classes.join(' ')
}

function entryText(entry: PlanningEntry): string {
  const parts = [`${shortTime(entry.start)} – ${shortTime(entry.end)}`, entry.label]
  if (entry.detail) parts.push(entry.detail)
  if (entry.holder_name) parts.push(entry.holder_name)
  return parts.join(' · ')
}

export default function RoomPlanningPage({ session, roomId, location }: Props) {
  const today = isoDate(new Date())
  const date = isValidIsoDate(location.query.get('date')) ? (location.query.get('date') as string) : today
  const view: PlanningView = location.query.get('vue') === 'semaine' ? 'week' : 'day'
  const back = location.query.get('retour')
  const backTo = back && (back.startsWith('/salles') || back.startsWith('/gestion/salles')) ? back : '/salles'

  const [planning, setPlanning] = useState<Planning | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    fetchPlanning(session, roomId, date, view)
      .then((result) => active && setPlanning(result))
      .catch((err) => {
        if (!active) return
        if (err instanceof ApiError && err.status === 404) setNotFound(true)
        else setError(errorMessage(err))
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [session, roomId, date, view])

  function go(nextDate: string, nextView: PlanningView = view) {
    navigate(withQuery(`/salles/${roomId}`, { date: nextDate, vue: VIEW_PARAM[nextView], retour: back }), {
      replace: true,
    })
  }

  // Une ligne par pas de 30 min, de l'ouverture à la fermeture
  const rows = useMemo(() => {
    if (!planning) return []
    const opening = toMinutes(planning.opening)
    const count = (toMinutes(planning.closing) - opening) / planning.slot_minutes
    return Array.from({ length: count }, (_, index) => opening + index * planning.slot_minutes)
  }, [planning])

  if (notFound) {
    return <StatusPage title="Salle introuvable" message="Cette salle n'existe pas ou a été archivée." />
  }

  const room = planning?.room
  const days = planning?.days ?? []
  const title = days.length === 0 ? '' : view === 'week' ? weekTitle(days) : formatLongDate(days[0])

  function rowOf(time: string): number {
    if (!planning) return 0
    const opening = toMinutes(planning.opening)
    const minutes = Math.min(Math.max(toMinutes(time), opening), toMinutes(planning.closing))
    return (minutes - opening) / planning.slot_minutes + 2 // ligne 1 : en-têtes des jours
  }

  return (
    <>
      <Link to={backTo} className="back-link">
        <ChevronLeftIcon />
        {backTo.startsWith('/gestion') ? 'Retour à la gestion des salles' : 'Retour aux salles'}
      </Link>

      <header className="page-head">
        <div>
          <h1>{room ? `Salle ${room.code}` : 'Planning de la salle'}</h1>
          {room && (
            <ul className="room-meta planning-room-meta">
              <li>
                <span className="badge badge-info">{ROOM_TYPE_LABELS[room.room_type]}</span>
              </li>
              <li>
                <MapPinIcon />
                {room.building}
              </li>
              <li>
                <UsersIcon />
                {room.capacity} places
              </li>
            </ul>
          )}
        </div>
      </header>

      {room && room.status !== 'active' && (
        <p className="notice notice-info planning-status" role="status">
          {room.status === 'archivee'
            ? 'Salle archivée : son planning reste consultable pour retrouver ses réservations passées.'
            : `Salle ${ROOM_STATUS_LABELS[room.status].toLowerCase()} : elle ne peut pas être réservée pour le moment.`}
          {room.description ? ` ${room.description}` : ''}
        </p>
      )}

      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}

      <section className="panel planning" aria-labelledby="planning-title" aria-busy={loading}>
        <div className="planning-toolbar">
          <div className="planning-nav">
            <button
              type="button"
              className="icon-button"
              onClick={() => go(view === 'day' ? stepDay(date, -1) : addDays(date, -7))}
              aria-label={view === 'week' ? 'Semaine précédente' : 'Jour précédent'}
            >
              <ChevronLeftIcon />
            </button>
            <button type="button" className="button-secondary" onClick={() => go(today)}>
              Aujourd'hui
            </button>
            <button
              type="button"
              className="icon-button"
              onClick={() => go(view === 'day' ? stepDay(date, 1) : addDays(date, 7))}
              aria-label={view === 'week' ? 'Semaine suivante' : 'Jour suivant'}
            >
              <ChevronRightIcon />
            </button>
            <h2 id="planning-title">{title || 'Planning'}</h2>
          </div>

          <div className="planning-controls">
            <label htmlFor="planning-date" className="visually-hidden">
              Aller à la date
            </label>
            <input
              id="planning-date"
              className="input planning-date"
              type="date"
              value={date}
              onChange={(event) => isValidIsoDate(event.target.value) && go(event.target.value)}
            />
            <div className="segmented" role="group" aria-label="Affichage">
              <button type="button" aria-pressed={view === 'day'} onClick={() => go(date, 'day')}>
                Jour
              </button>
              <button type="button" aria-pressed={view === 'week'} onClick={() => go(date, 'week')}>
                Semaine
              </button>
            </div>
          </div>
        </div>

        <ul className="planning-legend" aria-label="Légende">
          <li>
            <span className="legend-swatch is-free" />
            Libre
          </li>
          <li>
            <span className="legend-swatch is-reserve" />
            Réservé
          </li>
          <li>
            <span className="legend-swatch is-attente" />
            En attente de validation
          </li>
          <li>
            <span className="legend-swatch is-blocage" />
            Bloqué
          </li>
          <li>
            <span className="legend-swatch is-mine" />
            Ma réservation
          </li>
        </ul>

        {view === 'day' && !isOpenDay(date) && (
          <p className="notice notice-info" role="status">
            Le campus est fermé le dimanche.
          </p>
        )}

        {planning && (
          <div className="planning-scroll">
            <div
              className={view === 'day' ? 'planning-grid is-day' : 'planning-grid'}
              style={{ '--days': days.length, '--rows': rows.length } as CSSProperties}
            >
              <div className="planning-corner" aria-hidden="true" />
              {days.map((day, index) => (
                <div
                  key={day}
                  className={day === today ? 'planning-day is-today' : 'planning-day'}
                  style={{ gridColumn: index + 2 }}
                >
                  {view === 'week' ? formatShortDay(day) : formatLongDate(day)}
                  {day === today && <span className="visually-hidden"> (aujourd'hui)</span>}
                </div>
              ))}

              {rows.map((minutes, row) => (
                <div
                  key={`t${minutes}`}
                  className={minutes % 60 === 0 ? 'planning-time is-hour' : 'planning-time'}
                  style={{ gridRow: row + 2 }}
                  aria-hidden="true"
                >
                  {fromMinutes(minutes)}
                </div>
              ))}

              {days.map((day, column) =>
                rows.map((minutes, row) => (
                  <div
                    key={`${day}-${minutes}`}
                    className={minutes % 60 === 0 ? 'planning-cell is-hour' : 'planning-cell'}
                    style={{ gridColumn: column + 2, gridRow: row + 2 }}
                    aria-hidden="true"
                  />
                )),
              )}

              {planning.entries.map((entry) => {
                const column = days.indexOf(entry.day)
                if (column === -1) return null
                return (
                  <div
                    key={`${entry.kind}-${entry.id}-${entry.day}`}
                    className={entryClass(entry)}
                    style={{ gridColumn: column + 2, gridRow: `${rowOf(entry.start)} / ${rowOf(entry.end)}` }}
                    title={entryText(entry)}
                  >
                    <span className="visually-hidden">{formatShortDay(entry.day)}, </span>
                    <strong>
                      {shortTime(entry.start)} – {shortTime(entry.end)}
                    </strong>
                    <span className="planning-entry-label">{entry.label}</span>
                    {entry.detail && <span className="planning-entry-detail">{entry.detail}</span>}
                    {entry.holder_name && <span className="planning-entry-detail">{entry.holder_name}</span>}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {planning && planning.entries.length === 0 && (
          <p className="planning-empty">
            Aucune réservation ni blocage {view === 'week' ? 'cette semaine' : 'ce jour-là'} : la salle est libre de{' '}
            {shortTime(planning.opening)} à {shortTime(planning.closing)}.
          </p>
        )}
        {loading && !planning && <p className="loading">Chargement du planning…</p>}
      </section>
    </>
  )
}
