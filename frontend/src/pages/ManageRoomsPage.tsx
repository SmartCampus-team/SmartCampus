// Gestion des salles par le gestionnaire : créer, modifier, archiver (SC-20, EF-ROOM-04, ENF-03).
// SC-23 : lien vers le planning, y compris d'une salle archivée (réservations passées).

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import { archiveRoom, fetchRooms, ROOM_STATUS_LABELS, ROOM_TYPE_LABELS, type Room } from '../api/rooms'
import type { Session } from '../auth/session'
import Dialog from '../components/Dialog'
import { ArchiveIcon, CalendarIcon, PencilIcon, PlusIcon } from '../components/icons'
import { Link } from '../router'
import { planningPath } from './RoomPlanningPage'
import RoomFormDialog from './RoomFormDialog'
import './ManageRoomsPage.css'

interface Props {
  session: Session
}

const STATUS_BADGE: Record<Room['status'], string> = {
  active: 'badge badge-success',
  hors_service: 'badge badge-warning',
  archivee: 'badge badge-neutral',
}

export default function ManageRoomsPage({ session }: Props) {
  const [rooms, setRooms] = useState<Room[] | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [filter, setFilter] = useState('')
  const [editing, setEditing] = useState<Room | 'new' | null>(null)
  const [archiving, setArchiving] = useState<Room | null>(null)
  const [archiveError, setArchiveError] = useState<string | null>(null)
  const [archiveBusy, setArchiveBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const load = useCallback(() => {
    return fetchRooms(session, { includeArchived: showArchived })
      .then((list) => {
        setRooms(list)
        setLoadError(null)
      })
      .catch((error) => setLoadError(errorMessage(error)))
  }, [session, showArchived])

  useEffect(() => {
    load()
  }, [load])


  const buildings = useMemo(
    () => Array.from(new Set((rooms ?? []).map((room) => room.building))).sort(),
    [rooms],
  )

  const visibleRooms = useMemo(() => {
    const text = filter.trim().toLowerCase()
    if (!rooms || !text) return rooms ?? []
    return rooms.filter((room) => `${room.code} ${room.building}`.toLowerCase().includes(text))
  }, [rooms, filter])

  function handleSaved(room: Room, created: boolean) {
    setEditing(null)
    setMessage(created ? `Salle ${room.code} créée.` : `Salle ${room.code} modifiée.`)
    load()
  }

  async function handleArchive(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!archiving) return
    setArchiveBusy(true)
    setArchiveError(null)
    try {
      const room = await archiveRoom(session, archiving.id)
      setArchiving(null)
      setMessage(`Salle ${room.code} archivée.`)
      load()
    } catch (error) {
      setArchiveError(errorMessage(error))
    } finally {
      setArchiveBusy(false)
    }
  }

  function closeArchive() {
    setArchiving(null)
    setArchiveError(null)
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Gestion des salles</h1>
          <p>Créez, modifiez et archivez les salles du campus. Une salle archivée n'est jamais supprimée.</p>
        </div>
        <button
          type="button"
          className="button-primary"
          onClick={() => {
            setMessage(null)
            setEditing('new')
          }}
        >
          <PlusIcon />
          Nouvelle salle
        </button>
      </header>

      {message && (
        <p className="notice notice-success manage-message" role="status">
          {message}
        </p>
      )}
      {loadError && (
        <p className="notice notice-error" role="alert">
          {loadError}
        </p>
      )}

      <div className="toolbar">
        <div className="toolbar-filters">
          <div className="field">
            <label htmlFor="manage-filter">Rechercher</label>
            <input
              id="manage-filter"
              className="input"
              type="search"
              placeholder="Code ou bâtiment"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)}
            />
            Afficher les salles archivées
          </label>
        </div>
        {rooms && (
          <p className="toolbar-count">
            {visibleRooms.length} salle{visibleRooms.length > 1 ? 's' : ''}
          </p>
        )}
      </div>

      {rooms === null && !loadError && <p className="loading">Chargement des salles…</p>}
      {rooms !== null && visibleRooms.length === 0 && (
        <p className="empty-state">
          {rooms.length === 0 ? 'Aucune salle pour le moment : créez la première.' : 'Aucune salle ne correspond.'}
        </p>
      )}

      {visibleRooms.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">Salles du campus</caption>
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Type</th>
                <th scope="col">Bâtiment</th>
                <th scope="col">Capacité</th>
                <th scope="col">Statut</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleRooms.map((room) => {
                const archived = room.status === 'archivee'
                return (
                  <tr key={room.id} className={archived ? 'is-muted' : undefined}>
                    <td className="cell-strong">{room.code}</td>
                    <td>{ROOM_TYPE_LABELS[room.room_type]}</td>
                    <td>{room.building}</td>
                    <td>{room.capacity}</td>
                    <td>
                      <span className={STATUS_BADGE[room.status]}>{ROOM_STATUS_LABELS[room.status]}</span>
                    </td>
                    <td>
                      <div className="table-actions">
                        <Link
                          to={planningPath(room.id, { back: '/gestion/salles' })}
                          className="icon-button"
                          aria-label={`Planning de la salle ${room.code}`}
                          title="Planning"
                        >
                          <CalendarIcon />
                        </Link>
                        {!archived && (
                          <>
                            <button
                              type="button"
                              className="icon-button"
                              onClick={() => {
                                setMessage(null)
                                setEditing(room)
                              }}
                              aria-label={`Modifier la salle ${room.code}`}
                              title="Modifier"
                            >
                              <PencilIcon />
                            </button>
                            <button
                              type="button"
                              className="icon-button is-danger"
                              onClick={() => {
                                setMessage(null)
                                setArchiving(room)
                              }}
                              aria-label={`Archiver la salle ${room.code}`}
                              title="Archiver"
                            >
                              <ArchiveIcon />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <RoomFormDialog
          session={session}
          room={editing === 'new' ? null : editing}
          buildings={buildings}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}

      <Dialog
        open={archiving !== null}
        size="small"
        title={`Archiver la salle ${archiving?.code ?? ''} ?`}
        description="Elle disparaîtra de la liste et de la recherche. Ses réservations passées restent en base. Cette action est définitive."
        onClose={closeArchive}
        onSubmit={handleArchive}
        footer={
          <>
            <button type="button" className="button-secondary" onClick={closeArchive}>
              Annuler
            </button>
            <button type="submit" className="button-danger" disabled={archiveBusy}>
              <ArchiveIcon />
              {archiveBusy ? 'Archivage…' : 'Archiver'}
            </button>
          </>
        }
      >
        {archiveError && (
          <p className="notice notice-error" role="alert">
            {archiveError}
          </p>
        )}
      </Dialog>
    </>
  )
}
