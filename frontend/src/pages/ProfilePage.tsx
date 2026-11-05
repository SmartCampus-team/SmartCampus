// Mon profil : nom, téléphone, photo et préférences de notification (SC-19, EF-AUTH-06).

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import { requestPasswordReset } from '../api/passwords'
import {
  CHANNEL_LABELS,
  deletePhoto,
  fetchProfile,
  MAX_PHOTO_BYTES,
  PHOTO_CHANGED_EVENT,
  updateProfile,
  uploadPhoto,
  type NotificationChannel,
  type Profile,
} from '../api/profile'
import { ROLE_LABELS, type Session, type SessionUser } from '../auth/session'
import Avatar, { useProfilePhoto } from '../components/Avatar'
import { CameraIcon, KeyIcon, MailIcon, ShieldIcon, TrashIcon } from '../components/icons'
import './ProfilePage.css'

interface Props {
  session: Session
  onUserUpdated: (user: SessionUser) => void
}

const CHANNELS = Object.keys(CHANNEL_LABELS) as NotificationChannel[]
const PHONE_PATTERN = /^\+?[0-9][0-9 .-]{5,18}$/

export default function ProfilePage({ session, onUserUpdated }: Props) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [channel, setChannel] = useState<NotificationChannel>('les_deux')
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [photoMessage, setPhotoMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [photoBusy, setPhotoBusy] = useState(false)
  const [resetMessage, setResetMessage] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const photoUrl = useProfilePhoto(session)

  useEffect(() => {
    fetchProfile(session)
      .then((loaded) => {
        setProfile(loaded)
        setFullName(loaded.full_name)
        setPhone(loaded.phone ?? '')
        setChannel(loaded.notification_channel)
      })
      .catch((error) => setLoadError(errorMessage(error)))
    // Chargé une fois par jeton : la page garde ensuite ses propres modifications
  }, [session.accessToken])

  function applyProfile(updated: Profile) {
    setProfile(updated)
    onUserUpdated({ id: updated.id, email: updated.email, full_name: updated.full_name, role: updated.role })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaved(false)
    const name = fullName.trim()
    if (name.length < 2) {
      setFormError('Indiquez votre nom complet.')
      return
    }
    if (phone.trim() && !PHONE_PATTERN.test(phone.trim())) {
      setFormError('Numéro de téléphone invalide : chiffres, espaces et + initial (ex. 06 12 34 56 78).')
      return
    }
    setFormError(null)
    setBusy(true)
    try {
      applyProfile(await updateProfile(session, { full_name: name, phone: phone.trim() || null, notification_channel: channel }))
      setSaved(true)
    } catch (error) {
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  async function handlePhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = '' // permet de choisir à nouveau le même fichier
    if (!file) return
    if (!['image/png', 'image/jpeg'].includes(file.type)) {
      setPhotoMessage({ ok: false, text: 'Format refusé : choisissez une image PNG ou JPEG.' })
      return
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setPhotoMessage({ ok: false, text: 'Photo trop lourde : 2 Mo au plus.' })
      return
    }
    setPhotoBusy(true)
    setPhotoMessage(null)
    try {
      applyProfile(await uploadPhoto(session, file))
      window.dispatchEvent(new Event(PHOTO_CHANGED_EVENT))
      setPhotoMessage({ ok: true, text: 'Photo mise à jour.' })
    } catch (error) {
      setPhotoMessage({ ok: false, text: errorMessage(error) })
    } finally {
      setPhotoBusy(false)
    }
  }

  async function handleRemovePhoto() {
    setPhotoBusy(true)
    setPhotoMessage(null)
    try {
      await deletePhoto(session)
      if (profile) setProfile({ ...profile, has_photo: false })
      window.dispatchEvent(new Event(PHOTO_CHANGED_EVENT))
      setPhotoMessage({ ok: true, text: 'Photo retirée.' })
    } catch (error) {
      setPhotoMessage({ ok: false, text: errorMessage(error) })
    } finally {
      setPhotoBusy(false)
    }
  }

  async function handlePasswordLink() {
    setResetMessage(null)
    try {
      setResetMessage(await requestPasswordReset(session.user.email))
    } catch (error) {
      setResetMessage(errorMessage(error))
    }
  }

  const user = session.user

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Mon profil</h1>
          <p>Vos informations personnelles et la façon dont SmartCampus vous prévient.</p>
        </div>
      </header>

      {loadError && (
        <p className="notice notice-error" role="alert">
          {loadError}
        </p>
      )}

      <div className="profile-layout">
        <aside className="panel profile-card" aria-label="Identité">
          <Avatar name={user.full_name} photoUrl={photoUrl} className="profile-avatar" />
          <h2>{user.full_name}</h2>
          <span className="badge badge-info">{ROLE_LABELS[user.role]}</span>
          <p className="profile-email">
            <MailIcon />
            {user.email}
          </p>

          <div className="profile-photo-actions">
            <input
              ref={fileInput}
              id="photo-input"
              className="visually-hidden"
              type="file"
              accept="image/png,image/jpeg"
              onChange={handlePhoto}
            />
            <button
              type="button"
              className="button-secondary"
              onClick={() => fileInput.current?.click()}
              disabled={photoBusy}
            >
              <CameraIcon />
              {profile?.has_photo ? 'Changer la photo' : 'Ajouter une photo'}
            </button>
            {profile?.has_photo && (
              <button
                type="button"
                className="icon-button is-danger"
                onClick={handleRemovePhoto}
                disabled={photoBusy}
                aria-label="Retirer la photo"
                title="Retirer la photo"
              >
                <TrashIcon />
              </button>
            )}
          </div>
          <p className="field-hint">PNG ou JPEG, 2 Mo au plus.</p>
          {photoMessage && (
            <p className={photoMessage.ok ? 'notice notice-success' : 'notice notice-error'} role="status">
              {photoMessage.text}
            </p>
          )}
        </aside>

        <div className="profile-main">
          <form className="panel" onSubmit={handleSubmit} noValidate aria-labelledby="profile-info-title">
            <h2 id="profile-info-title" className="panel-title">
              Informations
            </h2>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="profile-name">Nom complet</label>
                <input
                  id="profile-name"
                  className="input"
                  autoComplete="name"
                  maxLength={150}
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  disabled={!profile}
                />
              </div>
              <div className="field">
                <label htmlFor="profile-phone">Téléphone (facultatif)</label>
                <input
                  id="profile-phone"
                  className="input"
                  type="tel"
                  autoComplete="tel"
                  placeholder="06 12 34 56 78"
                  maxLength={20}
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  disabled={!profile}
                />
              </div>
              <div className="field field-wide">
                <label htmlFor="profile-email">E-mail institutionnel</label>
                <input id="profile-email" className="input" value={user.email} disabled readOnly />
                <p className="field-hint">C'est votre identifiant : seul l'administrateur peut le modifier.</p>
              </div>
            </div>

            <fieldset className="profile-channels">
              <legend>Recevoir les notifications</legend>
              {CHANNELS.map((value) => (
                <label key={value} className="check">
                  <input
                    type="radio"
                    name="channel"
                    value={value}
                    checked={channel === value}
                    onChange={() => setChannel(value)}
                    disabled={!profile}
                  />
                  {CHANNEL_LABELS[value]}
                </label>
              ))}
              <p className="field-hint">Enregistrées dès maintenant ; les notifications elles-mêmes arrivent au Sprint 5.</p>
            </fieldset>

            {formError && (
              <p className="notice notice-error" role="alert">
                {formError}
              </p>
            )}
            {saved && !formError && (
              <p className="notice notice-success" role="status">
                Profil enregistré.
              </p>
            )}

            <div className="form-actions">
              <button type="submit" className="button-primary" disabled={busy || !profile}>
                {busy ? 'Enregistrement…' : 'Enregistrer'}
              </button>
            </div>
          </form>

          <section className="panel" aria-labelledby="profile-security-title">
            <h2 id="profile-security-title" className="panel-title">
              <ShieldIcon className="panel-title-icon" />
              Mot de passe
            </h2>
            <p className="profile-text">
              Pour changer votre mot de passe, recevez un lien valable 30 minutes à votre adresse institutionnelle.
            </p>
            <button type="button" className="button-secondary" onClick={handlePasswordLink}>
              <KeyIcon />
              Recevoir un lien par e-mail
            </button>
            {resetMessage && (
              <p className="notice notice-info" role="status">
                {resetMessage}
              </p>
            )}
          </section>
        </div>
      </div>
    </>
  )
}
