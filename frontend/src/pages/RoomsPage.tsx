// Salles : la liste des salles du campus (SC-21, EF-ROOM-01) et la recherche d'une salle libre
// sur un créneau (SC-22, EF-ROOM-02), avec un lien vers le planning de chaque salle (SC-23).
// Les critères de recherche sont dans l'URL :
// #/salles?date=2026-11-02&debut=10:00&fin=12:00&participants=20

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import {
  fetchRooms,
  ROOM_STATUS_LABELS,
  ROOM_TYPE_LABELS,
  ROOM_TYPES,
  searchAvailableRooms,
  type Availability,
  type Room,
  type RoomType,
} from '../api/rooms'
import type { Session } from '../auth/session'
import { ArrowIcon, BuildingIcon, MapPinIcon, SearchIcon, UsersIcon } from '../components/icons'
import {
  CLOSING,
  defaultSlot,
  formatLongDate,
  isOpenDay,
  isValidIsoDate,
  OPENING,
  STEP_MINUTES,
  timeOptions,
  toMinutes,
} from '../dates'
import { Link, navigate, withQuery, type Location } from '../router'
import { planningPath } from './RoomPlanningPage'
import './RoomsPage.css'

interface Props {
  session: Session
  location: Location
}

interface Criteria {
  date: string
  start: string
  end: string
  participants: string
  type: RoomType | ''
  building: string
}

const START_OPTIONS = timeOptions(OPENING, '19:30')
const END_OPTIONS = timeOptions('08:30', CLOSING)

function criteriaFromQuery(query: URLSearchParams): { criteria: Criteria; searched: boolean } {
  const fallback = defaultSlot()
  const date = query.get('date')
  const start = query.get('debut')
  const end = query.get('fin')
  const searched = isValidIsoDate(date) && !!start && !!end
  const type = query.get('type')
  return {
    searched,
    criteria: {
      date: searched ? date : fallback.date,
      start: searched ? start : fallback.start,
      end: searched ? end : fallback.end,
      participants: query.get('participants') ?? '',
      type: ROOM_TYPES.includes(type as RoomType) ? (type as RoomType) : '',
      building: query.get('batiment') ?? '',
    },
  }
}

function criteriaToPath(criteria: Criteria): string {
  return withQuery('/salles', {
    date: criteria.date,
    debut: criteria.start,
    fin: criteria.end,
    participants: criteria.participants,
    type: criteria.type,
    batiment: criteria.building,
  })
}

/** Erreur à afficher sans lancer la recherche (RG-03), ou null si le créneau est valable. */
function checkCriteria(criteria: Criteria): string | null {
  if (!isValidIsoDate(criteria.date)) return 'Choisissez une date.'
  if (!isOpenDay(criteria.date)) return 'Le campus est fermé le dimanche : choisissez un jour du lundi au samedi.'
  for (const time of [criteria.start, criteria.end]) {
    if (toMinutes(time) % STEP_MINUTES !== 0) return `Les créneaux vont par pas de ${STEP_MINUTES} min.`
    if (toMinutes(time) < toMinutes(OPENING) || toMinutes(time) > toMinutes(CLOSING)) {
      return `Les créneaux vont de ${OPENING} à ${CLOSING}.`
    }
  }
  if (toMinutes(criteria.end) <= toMinutes(criteria.start)) return "L'heure de fin doit être après l'heure de début."
  const participants = Number(criteria.participants)
  if (criteria.participants && (!Number.isInteger(participants) || participants < 1)) {
    return 'Le nombre de participants doit être un nombre entier positif.'
  }
  return null
}

export function RoomCard({ room, planningTo }: { room: Room; planningTo?: string }) {
  return (
    <article className="room-card">
      <header className="room-card-head">
        <h3>{room.code}</h3>
        <span className={room.status === 'active' ? 'badge badge-success' : 'badge badge-warning'}>
          {ROOM_STATUS_LABELS[room.status]}
        </span>
      </header>
      <p className="room-type">{ROOM_TYPE_LABELS[room.room_type]}</p>
      <ul className="room-meta">
        <li>
          <MapPinIcon />
          {room.building}
        </li>
        <li>
          <UsersIcon />
          {room.capacity} places
        </li>
      </ul>
      {/* Le catalogue d'équipements arrive avec SC-31 (Sprint 3) */}
      <p className="room-equipment">Équipements : aucun renseigné</p>
      {room.description && <p className="room-description">{room.description}</p>}
      {planningTo && (
        <Link to={planningTo} className="room-card-link">
          Voir le planning
          <ArrowIcon />
        </Link>
      )}
    </article>
  )
}

export default function RoomsPage({ session, location }: Props) {
  const { criteria: initial, searched } = useMemo(() => criteriaFromQuery(location.query), [location.query])
  const [criteria, setCriteria] = useState<Criteria>(initial)
  const [result, setResult] = useState<Availability | null>(null)
  const [searching, setSearching] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [buildings, setBuildings] = useState<string[]>([])

  const [rooms, setRooms] = useState<Room[] | null>(null)
  const [query, setQuery] = useState('')
  const [roomType, setRoomType] = useState<RoomType | ''>('')
  const [filters, setFilters] = useState({ q: '', room_type: '' as RoomType | '' })
  const [error, setError] = useState<string | null>(null)

  // Le formulaire suit l'URL (bouton Précédent, lien partagé)
  useEffect(() => setCriteria(initial), [initial])

  // Bâtiments proposés dans le formulaire de recherche
  useEffect(() => {
    fetchRooms(session)
      .then((all) => setBuildings(Array.from(new Set(all.map((room) => room.building))).sort()))
      .catch(() => setBuildings([]))
  }, [session])

  // Recherche lancée par l'URL ; les erreurs de l'API (créneau refusé) s'affichent sous le formulaire
  useEffect(() => {
    if (!searched) {
      setResult(null)
      return
    }
    let active = true
    setSearching(true)
    setFormError(null)
    searchAvailableRooms(session, {
      date: initial.date,
      start: initial.start,
      end: initial.end,
      min_capacity: initial.participants ? Number(initial.participants) : null,
      room_type: initial.type,
      building: initial.building,
    })
      .then((availability) => active && setResult(availability))
      .catch((err) => {
        if (!active) return
        setResult(null)
        setFormError(errorMessage(err))
      })
      .finally(() => active && setSearching(false))
    return () => {
      active = false
    }
  }, [session, searched, initial])

  // Liste des salles (SC-21) : la recherche par texte part 300 ms après la dernière frappe
  useEffect(() => {
    const timer = window.setTimeout(() => setFilters({ q: query.trim(), room_type: roomType }), 300)
    return () => window.clearTimeout(timer)
  }, [query, roomType])

  useEffect(() => {
    if (searched) return
    let active = true
    fetchRooms(session, filters)
      .then((list) => {
        if (!active) return
        setRooms(list)
        setError(null)
      })
      .catch((err) => active && setError(errorMessage(err)))
    return () => {
      active = false
    }
  }, [session, filters, searched])

  function update<K extends keyof Criteria>(key: K, value: Criteria[K]) {
    setCriteria((current) => ({ ...current, [key]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    // Créneau refusé : le message s'affiche et la recherche ne part pas
    const problem = checkCriteria(criteria)
    setFormError(problem)
    if (!problem) navigate(criteriaToPath(criteria))
  }

  function handleReset() {
    setFormError(null)
    setCriteria(criteriaFromQuery(new URLSearchParams()).criteria)
    navigate('/salles')
  }

  const filtered = filters.q !== '' || filters.room_type !== ''

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Salles</h1>
          <p>Trouvez une salle libre sur un créneau, ou parcourez toutes les salles du campus.</p>
        </div>
      </header>

      <form className="panel room-search" onSubmit={handleSubmit} noValidate aria-labelledby="search-title">
        <h2 id="search-title" className="panel-title">
          Trouver une salle libre
        </h2>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="search-date">Date</label>
            <input
              id="search-date"
              className="input"
              type="date"
              value={criteria.date}
              onChange={(event) => update('date', event.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="search-start">Début</label>
            <select
              id="search-start"
              className="select"
              value={criteria.start}
              onChange={(event) => update('start', event.target.value)}
            >
              {START_OPTIONS.map((time) => (
                <option key={time}>{time}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="search-end">Fin</label>
            <select
              id="search-end"
              className="select"
              value={criteria.end}
              onChange={(event) => update('end', event.target.value)}
            >
              {END_OPTIONS.map((time) => (
                <option key={time}>{time}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="search-participants">Participants</label>
            <input
              id="search-participants"
              className="input"
              type="number"
              min={1}
              inputMode="numeric"
              placeholder="Tous"
              value={criteria.participants}
              onChange={(event) => update('participants', event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="search-type">Type de salle</label>
            <select
              id="search-type"
              className="select"
              value={criteria.type}
              onChange={(event) => update('type', event.target.value as RoomType | '')}
            >
              <option value="">Tous les types</option>
              {ROOM_TYPES.map((type) => (
                <option key={type} value={type}>
                  {ROOM_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="search-building">Bâtiment</label>
            <select
              id="search-building"
              className="select"
              value={criteria.building}
              onChange={(event) => update('building', event.target.value)}
            >
              <option value="">Tous</option>
              {buildings.map((building) => (
                <option key={building}>{building}</option>
              ))}
            </select>
          </div>
        </div>

        {formError && (
          <p className="notice notice-error" role="alert">
            {formError}
          </p>
        )}

        <div className="form-actions">
          <button type="button" className="button-secondary" onClick={handleReset}>
            Réinitialiser
          </button>
          <button type="submit" className="button-primary" disabled={searching}>
            <SearchIcon />
            {searching ? 'Recherche…' : 'Rechercher'}
          </button>
        </div>
      </form>

      {searched ? (
        <section className="room-results" aria-labelledby="results-title" aria-busy={searching}>
          <div className="results-head">
            <div>
              <h2 id="results-title">
                {result
                  ? `${result.rooms.length} salle${result.rooms.length > 1 ? 's' : ''} libre${result.rooms.length > 1 ? 's' : ''}`
                  : 'Salles libres'}
              </h2>
              <p>
                {formatLongDate(initial.date)} · {initial.start} – {initial.end}
                {initial.participants ? ` · ${initial.participants} participants` : ''} · la plus petite salle adaptée
                d'abord
              </p>
            </div>
            <button type="button" className="button-link" onClick={handleReset}>
              Voir toutes les salles
            </button>
          </div>

          {result && result.rooms.length === 0 && (
            <div className="empty-state">
              <SearchIcon className="empty-icon" />
              <p>Aucune salle libre ne correspond à ce créneau. Essayez un autre horaire ou retirez un filtre.</p>
            </div>
          )}
          {result && result.rooms.length > 0 && (
            <ul className="room-grid">
              {result.rooms.map((room) => (
                <li key={room.id}>
                  <RoomCard
                    room={room}
                    planningTo={planningPath(room.id, { date: initial.date, back: criteriaToPath(initial) })}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : (
        <section className="room-results" aria-labelledby="catalogue-title">
          <div className="results-head">
            <div>
              <h2 id="catalogue-title">Toutes les salles</h2>
              <p>Bâtiment, type, capacité et statut de chaque salle du campus.</p>
            </div>
          </div>

          <div className="toolbar">
            <div className="toolbar-filters">
              <div className="field">
                <label htmlFor="rooms-search">Rechercher</label>
                <input
                  id="rooms-search"
                  className="input"
                  type="search"
                  placeholder="Code ou bâtiment"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="rooms-type">Type de salle</label>
                <select
                  id="rooms-type"
                  className="select"
                  value={roomType}
                  onChange={(event) => setRoomType(event.target.value as RoomType | '')}
                >
                  <option value="">Tous les types</option>
                  {ROOM_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {ROOM_TYPE_LABELS[type]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {rooms && (
              <p className="toolbar-count" aria-live="polite">
                {rooms.length} salle{rooms.length > 1 ? 's' : ''}
              </p>
            )}
          </div>

          {error && (
            <p className="notice notice-error" role="alert">
              {error}
            </p>
          )}

          {rooms === null && !error && <p className="loading">Chargement des salles…</p>}

          {rooms !== null && rooms.length === 0 && (
            <div className="empty-state">
              <BuildingIcon className="empty-icon" />
              {filtered ? (
                <p>Aucune salle ne correspond à ces critères.</p>
              ) : (
                <>
                  <p>Aucune salle n'est encore enregistrée.</p>
                  {session.user.role === 'gestionnaire' && (
                    <Link to="/gestion/salles" className="button-secondary">
                      Créer une salle
                    </Link>
                  )}
                </>
              )}
            </div>
          )}

          {rooms !== null && rooms.length > 0 && (
            <ul className="room-grid">
              {rooms.map((room) => (
                <li key={room.id}>
                  <RoomCard room={room} planningTo={planningPath(room.id)} />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  )
}
