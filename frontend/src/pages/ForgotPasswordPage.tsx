// Mot de passe oublié : demande d'un lien par e-mail (SC-18, EF-AUTH-05).

import { useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import { requestPasswordReset } from '../api/passwords'
import AuthLayout from '../components/AuthLayout'
import { ArrowIcon, KeyIcon, MailIcon } from '../components/icons'
import { Link } from '../router'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      setSent(await requestPasswordReset(email.trim()))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <form className="login-card" onSubmit={handleSubmit} noValidate>
        <div className="login-card-icon">
          <KeyIcon />
        </div>
        <h2>Mot de passe oublié</h2>

        {sent ? (
          <>
            <p className="login-card-subtitle">Vérifiez votre boîte de réception</p>
            <p className="notice notice-success login-notice" role="status">
              {sent}
            </p>
            <p className="login-text">
              Pensez à regarder dans les courriers indésirables. Le lien ne fonctionne qu'une fois.
            </p>
            <button type="button" className="button-secondary" onClick={() => setSent(null)}>
              Renvoyer un lien
            </button>
          </>
        ) : (
          <>
            <p className="login-card-subtitle">Recevez un lien pour choisir un nouveau mot de passe</p>

            <label htmlFor="forgot-email">E-mail institutionnel</label>
            <div className="login-field">
              <MailIcon className="login-field-icon" />
              <input
                id="forgot-email"
                type="email"
                autoComplete="username"
                placeholder="prenom.nom@usms.ac.ma"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                autoFocus
              />
            </div>

            {error && (
              <p className="alert" role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="login-submit" disabled={busy || !email.trim()}>
              {busy ? 'Envoi…' : 'Envoyer le lien'}
              <ArrowIcon className="login-submit-arrow" />
            </button>
          </>
        )}

        <Link to="/" className="login-back">
          Retour à la connexion
        </Link>
      </form>
    </AuthLayout>
  )
}
