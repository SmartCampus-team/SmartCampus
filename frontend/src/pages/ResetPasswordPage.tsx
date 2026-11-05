// Choix du nouveau mot de passe depuis le lien reçu par e-mail (SC-18, EF-AUTH-05).
// Adresse : #/reinitialiser?token=… ; le lien est valable 30 min et ne sert qu'une fois.

import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, errorMessage } from '../api/client'
import { checkResetLink, passwordProblem, resetPassword } from '../api/passwords'
import AuthLayout from '../components/AuthLayout'
import { ArrowIcon, EyeIcon, EyeOffIcon, LockIcon } from '../components/icons'
import { Link, navigate } from '../router'

interface Props {
  token: string | null
}

export default function ResetPasswordPage({ token }: Props) {
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [linkInvalid, setLinkInvalid] = useState(!token)
  const [checking, setChecking] = useState(!!token)
  const [busy, setBusy] = useState(false)

  // Le lien est vérifié dès son ouverture : expiré ou déjà utilisé, il est refusé tout de suite
  useEffect(() => {
    if (!token) return
    let active = true
    checkResetLink(token)
      .catch((err) => {
        if (active && err instanceof ApiError && err.status === 400) setLinkInvalid(true)
      })
      .finally(() => active && setChecking(false))
    return () => {
      active = false
    }
  }, [token])

  const problem = password ? passwordProblem(password) : null

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token) return
    const rule = passwordProblem(password)
    if (rule) {
      setError(`Mot de passe trop faible : ${rule.toLowerCase()}`)
      return
    }
    if (password !== confirmation) {
      setError('Les deux mots de passe ne sont pas identiques.')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await resetPassword(token, password)
      navigate('/?motdepasse=modifie', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 400 && err.detail?.includes('lien')) setLinkInvalid(true)
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (checking) {
    return (
      <AuthLayout>
        <div className="login-card">
          <p className="loading">Vérification du lien…</p>
        </div>
      </AuthLayout>
    )
  }

  if (linkInvalid) {
    return (
      <AuthLayout>
        <div className="login-card">
          <div className="login-card-icon">
            <LockIcon />
          </div>
          <h2>Lien expiré</h2>
          <p className="login-card-subtitle">Ce lien de réinitialisation n'est plus valable</p>
          <p className="login-text">
            Un lien ne fonctionne qu'une fois, pendant 30 minutes, et un nouveau lien remplace le précédent.
          </p>
          <Link to="/mot-de-passe-oublie" className="button-primary login-submit">
            Demander un nouveau lien
            <ArrowIcon className="login-submit-arrow" />
          </Link>
          <Link to="/" className="login-back">
            Retour à la connexion
          </Link>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <form className="login-card" onSubmit={handleSubmit} noValidate>
        <div className="login-card-icon">
          <LockIcon />
        </div>
        <h2>Nouveau mot de passe</h2>
        <p className="login-card-subtitle">Choisissez le mot de passe de votre compte</p>

        <label htmlFor="new-password">Nouveau mot de passe</label>
        <div className="login-field login-field-password">
          <LockIcon className="login-field-icon" />
          <input
            id="new-password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby="password-rules"
            required
            autoFocus
          />
          <button
            type="button"
            className="login-eye"
            onClick={() => setShowPassword((shown) => !shown)}
            aria-label={showPassword ? 'Masquer les mots de passe' : 'Afficher les mots de passe'}
            aria-pressed={showPassword}
          >
            {showPassword ? <EyeOffIcon /> : <EyeIcon />}
          </button>
        </div>
        <p id="password-rules" className={problem ? 'password-rules is-error' : 'password-rules'}>
          De 8 à 64 caractères, dont au moins une lettre et un chiffre.
        </p>

        <label htmlFor="confirm-password">Confirmation</label>
        <div className="login-field">
          <LockIcon className="login-field-icon" />
          <input
            id="confirm-password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            required
          />
        </div>

        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="login-submit" disabled={busy || !password || !confirmation}>
          {busy ? 'Enregistrement…' : 'Changer le mot de passe'}
          <ArrowIcon className="login-submit-arrow" />
        </button>

        <Link to="/" className="login-back">
          Retour à la connexion
        </Link>
      </form>
    </AuthLayout>
  )
}
