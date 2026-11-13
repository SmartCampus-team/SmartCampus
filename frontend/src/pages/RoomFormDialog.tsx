// Formulaire de création ou de modification d'une salle (SC-20, EF-ROOM-04).
// SC-31 (EF-ROOM-05) : le gestionnaire coche les équipements de la salle, pris dans le catalogue.

import { useEffect, useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import { fetchEquipment, setRoomEquipment, sortByLabel, type Equipment } from '../api/equipment'
import { createRoom, ROOM_TYPE_LABELS, ROOM_TYPES, updateRoom, type Room, type RoomInput, type RoomType } from '../api/rooms'
import type { Session } from '../auth/session'
import Dialog from '../components/Dialog'

interface Props {
  session: Session
  room: Room | null // null : nouvelle salle
  buildings: string[]
  onClose: () => void
  onSaved: (room: Room, created: boolean) => void
}

interface FormState {
  code: string
  building: string
  roomType: RoomType
  capacity: string
  description: string
}

function initialState(room: Room | null): FormState {
  return {
    code: room?.code ?? '',
    building: room?.building ?? '',
    roomType: room?.room_type ?? 'salle_td',
    capacity: room ? String(room.capacity) : '',
    description: room?.description ?? '',
  }
}

function validate(form: FormState): Partial<Record<keyof FormState, string>> {
  const errors: Partial<Record<keyof FormState, string>> = {}
  if (!/^[A-Za-z0-9][A-Za-z0-9-]*$/.test(form.code.trim())) {
    errors.code = 'Lettres, chiffres et tirets, sans espace (ex. A-104).'
  }
  if (form.building.trim().length < 2) errors.building = 'Indiquez le bâtiment.'
  const capacity = Number(form.capacity)
  if (!Number.isInteger(capacity) || capacity < 1 || capacity > 500) {
    errors.capacity = 'Un nombre entier de 1 à 500.'
  }
  return errors
}

export default function RoomFormDialog({ session, room, buildings, onClose, onSaved }: Props) {
  const [form, setForm] = useState<FormState>(() => initialState(room))
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // Équipements (SC-31) : le catalogue et ceux cochés pour cette salle
  const [catalogue, setCatalogue] = useState<Equipment[] | null>(null)
  const [equipment, setEquipment] = useState<number[]>(() => room?.equipment.map((item) => item.id) ?? [])

  useEffect(() => {
    fetchEquipment(session)
      .then((list) => setCatalogue(sortByLabel(list)))
      .catch(() => setCatalogue([]))
  }, [session])

  function toggleEquipment(id: number) {
    setEquipment((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]))
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }


  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validate(form)
    setErrors(found)
    setServerError(null)
    if (Object.keys(found).length > 0) return

    const input: RoomInput = {
      code: form.code.trim().toUpperCase(),
      building: form.building.trim(),
      room_type: form.roomType,
      capacity: Number(form.capacity),
      description: form.description.trim(),
    }
    setBusy(true)
    try {
      let saved = room ? await updateRoom(session, room.id, input) : await createRoom(session, input)
      // Équipements enregistrés seulement s'ils ont changé
      const before = (room?.equipment ?? []).map((item) => item.id).sort().join(',')
      if ([...equipment].sort().join(',') !== before) {
        saved = await setRoomEquipment(session, saved.id, equipment)
      }
      onSaved(saved, room === null)
    } catch (error) {
      setServerError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open
      title={room ? `Modifier la salle ${room.code}` : 'Nouvelle salle'}
      description={room ? 'Les changements sont visibles aussitôt par tous les utilisateurs.' : 'La salle est créée « active » et apparaît aussitôt dans la liste.'}
      onClose={onClose}
      onSubmit={handleSubmit}
      footer={
        <>
          <button type="button" className="button-secondary" onClick={onClose}>
            Annuler
          </button>
          <button type="submit" className="button-primary" disabled={busy}>
            {busy ? 'Enregistrement…' : room ? 'Enregistrer' : 'Créer la salle'}
          </button>
        </>
      }
    >
      <div className="form-grid room-form-grid">
        <div className="field">
          <label htmlFor="room-code">Code</label>
          <input
            id="room-code"
            className="input"
            value={form.code}
            maxLength={20}
            placeholder="A-104"
            onChange={(event) => update('code', event.target.value)}
            aria-invalid={!!errors.code}
            aria-describedby={errors.code ? 'room-code-error' : undefined}
            data-autofocus
          />
          {errors.code && (
            <p id="room-code-error" className="field-error">
              {errors.code}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="room-building">Bâtiment</label>
          <input
            id="room-building"
            className="input"
            list="room-buildings"
            value={form.building}
            maxLength={80}
            placeholder="Bâtiment A"
            onChange={(event) => update('building', event.target.value)}
            aria-invalid={!!errors.building}
            aria-describedby={errors.building ? 'room-building-error' : undefined}
          />
          <datalist id="room-buildings">
            {buildings.map((building) => (
              <option key={building} value={building} />
            ))}
          </datalist>
          {errors.building && (
            <p id="room-building-error" className="field-error">
              {errors.building}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="room-type">Type</label>
          <select
            id="room-type"
            className="select"
            value={form.roomType}
            onChange={(event) => update('roomType', event.target.value as RoomType)}
          >
            {ROOM_TYPES.map((type) => (
              <option key={type} value={type}>
                {ROOM_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="room-capacity">Capacité (places)</label>
          <input
            id="room-capacity"
            className="input"
            type="number"
            min={1}
            max={500}
            inputMode="numeric"
            value={form.capacity}
            onChange={(event) => update('capacity', event.target.value)}
            aria-invalid={!!errors.capacity}
            aria-describedby={errors.capacity ? 'room-capacity-error' : undefined}
          />
          {errors.capacity && (
            <p id="room-capacity-error" className="field-error">
              {errors.capacity}
            </p>
          )}
        </div>
        <div className="field field-wide">
          <label htmlFor="room-description">Description (facultatif)</label>
          <textarea
            id="room-description"
            className="textarea"
            maxLength={500}
            value={form.description}
            onChange={(event) => update('description', event.target.value)}
          />
        </div>
      </div>

      <fieldset className="chip-fieldset">
        <legend>Équipements</legend>
        {catalogue === null && <p className="field-hint">Chargement du catalogue…</p>}
        {catalogue !== null && catalogue.length === 0 && (
          <p className="field-hint">Le catalogue est vide : ajoutez des équipements depuis « Catalogue d'équipements ».</p>
        )}
        {catalogue !== null && catalogue.length > 0 && (
          <div className="chip-group">
            {catalogue.map((item) => (
              <label key={item.id} className="chip">
                <input
                  type="checkbox"
                  checked={equipment.includes(item.id)}
                  onChange={() => toggleEquipment(item.id)}
                />
                {item.label}
              </label>
            ))}
          </div>
        )}
      </fieldset>

      {serverError && (
        <p className="notice notice-error" role="alert">
          {serverError}
        </p>
      )}
    </Dialog>
  )
}
