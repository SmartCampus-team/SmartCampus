// Catalogue d'équipements (SC-31, EF-ROOM-05) : le gestionnaire crée et renomme les équipements ;
// il les affecte ensuite aux salles depuis le formulaire de chaque salle (« Gestion des salles »).
// Adresse : #/gestion/equipements

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import {
  createEquipment,
  EQUIPMENT_CATEGORIES,
  EQUIPMENT_CATEGORY_LABELS,
  fetchEquipment,
  sortByLabel,
  updateEquipment,
  type CatalogueItem,
  type EquipmentCategory,
} from '../api/equipment'
import type { Session } from '../auth/session'
import Dialog from '../components/Dialog'
import { ChevronLeftIcon, PencilIcon, PlusIcon } from '../components/icons'
import { Link } from '../router'

interface Props {
  session: Session
}

interface FormProps {
  session: Session
  item: CatalogueItem | null // null : nouvel équipement
  onClose: () => void
  onSaved: (label: string, created: boolean) => void
}

function EquipmentFormDialog({ session, item, onClose, onSaved }: FormProps) {
  const [label, setLabel] = useState(item?.label ?? '')
  const [category, setCategory] = useState<EquipmentCategory>(item?.category ?? 'audiovisuel')
  const [error, setError] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const clean = label.trim().replace(/\s+/g, ' ')
    setError(clean.length < 2 ? 'Indiquez le libellé (2 caractères au moins).' : null)
    setServerError(null)
    if (clean.length < 2) return
    setBusy(true)
    try {
      const saved = item
        ? await updateEquipment(session, item.id, { label: clean, category })
        : await createEquipment(session, { label: clean, category })
      onSaved(saved.label, item === null)
    } catch (err) {
      setServerError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open
      size="small"
      title={item ? `Modifier « ${item.label} »` : 'Nouvel équipement'}
      description={
        item
          ? 'Le nouveau libellé s’affiche aussitôt sur les salles équipées.'
          : 'Il apparaîtra dans le catalogue ; cochez-le ensuite sur les salles équipées.'
      }
      onClose={onClose}
      onSubmit={handleSubmit}
      footer={
        <>
          <button type="button" className="button-secondary" onClick={onClose}>
            Annuler
          </button>
          <button type="submit" className="button-primary" disabled={busy}>
            {busy ? 'Enregistrement…' : item ? 'Enregistrer' : "Créer l'équipement"}
          </button>
        </>
      }
    >
      <div className="form-grid">
        <div className="field">
          <label htmlFor="equipment-label">Libellé</label>
          <input
            id="equipment-label"
            className="input"
            value={label}
            maxLength={80}
            placeholder="Vidéoprojecteur"
            onChange={(event) => setLabel(event.target.value)}
            aria-invalid={!!error}
            aria-describedby={error ? 'equipment-label-error' : undefined}
            data-autofocus
          />
          {error && (
            <p id="equipment-label-error" className="field-error">
              {error}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="equipment-category">Catégorie</label>
          <select
            id="equipment-category"
            className="select"
            value={category}
            onChange={(event) => setCategory(event.target.value as EquipmentCategory)}
          >
            {EQUIPMENT_CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {EQUIPMENT_CATEGORY_LABELS[value]}
              </option>
            ))}
          </select>
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

export default function EquipmentPage({ session }: Props) {
  const [items, setItems] = useState<CatalogueItem[] | null>(null)
  const [editing, setEditing] = useState<CatalogueItem | 'new' | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    return fetchEquipment(session)
      .then((list) => {
        // Par catégorie (dans l'ordre du menu), puis par libellé
        const order = (item: CatalogueItem) => EQUIPMENT_CATEGORIES.indexOf(item.category)
        setItems(sortByLabel(list).sort((a, b) => order(a) - order(b)))
        setError(null)
      })
      .catch((err) => setError(errorMessage(err)))
  }, [session])

  useEffect(() => {
    load()
  }, [load])

  function handleSaved(label: string, created: boolean) {
    setEditing(null)
    setMessage(created ? `Équipement « ${label} » ajouté au catalogue.` : `Équipement « ${label} » modifié.`)
    load()
  }

  return (
    <>
      <Link to="/gestion/salles" className="back-link">
        <ChevronLeftIcon />
        Retour à la gestion des salles
      </Link>

      <header className="page-head">
        <div>
          <h1>Catalogue d'équipements</h1>
          <p>
            Les équipements cochés sur une salle s'affichent sur sa fiche et servent de filtre à la recherche. Pour les
            affecter, modifiez la salle dans « Gestion des salles ».
          </p>
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
          Nouvel équipement
        </button>
      </header>

      {message && (
        <p className="notice notice-success manage-message" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}

      {items === null && !error && <p className="loading">Chargement du catalogue…</p>}
      {items !== null && items.length === 0 && (
        <p className="empty-state">Le catalogue est vide : ajoutez le premier équipement.</p>
      )}

      {items !== null && items.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">Équipements du catalogue</caption>
            <thead>
              <tr>
                <th scope="col">Libellé</th>
                <th scope="col">Catégorie</th>
                <th scope="col">Salles équipées</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="cell-strong">{item.label}</td>
                  <td>
                    <span className="badge badge-info">{EQUIPMENT_CATEGORY_LABELS[item.category]}</span>
                  </td>
                  <td>{item.room_count}</td>
                  <td>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="icon-button"
                        onClick={() => {
                          setMessage(null)
                          setEditing(item)
                        }}
                        aria-label={`Modifier l'équipement ${item.label}`}
                        title="Modifier"
                      >
                        <PencilIcon />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <EquipmentFormDialog
          session={session}
          item={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}
    </>
  )
}
