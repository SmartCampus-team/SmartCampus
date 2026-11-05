// Création ou modification d'un compte par l'administrateur (SC-17, EF-AUTH-07, RG-11).
// Pas de mot de passe ici : le titulaire choisit le sien avec le lien de réinitialisation (SC-18).

import { useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import { createAccount, updateAccount, type Account } from '../api/users'
import { ROLE_LABELS, type Role, type Session } from '../auth/session'
import Dialog from '../components/Dialog'

interface Props {
  session: Session
  account: Account | null // null : nouveau compte
  isSelf: boolean
  onClose: () => void
  onSaved: (account: Account, created: boolean) => void
}

const ROLES = Object.keys(ROLE_LABELS) as Role[]
const DOMAIN = '@usms.ac.ma'

type Errors = Partial<Record<'email' | 'fullName', string>>

export default function AccountFormDialog({ session, account, isSelf, onClose, onSaved }: Props) {
  const [email, setEmail] = useState(account?.email ?? '')
  const [fullName, setFullName] = useState(account?.full_name ?? '')
  const [role, setRole] = useState<Role>(account?.role ?? 'etudiant')
  const [errors, setErrors] = useState<Errors>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function validate(): Errors {
    const found: Errors = {}
    if (!email.trim().toLowerCase().endsWith(DOMAIN)) found.email = `Adresse de l'établissement (${DOMAIN}).`
    if (fullName.trim().length < 2) found.fullName = 'Indiquez le nom complet.'
    return found
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    setServerError(null)
    if (Object.keys(found).length > 0) return
    const input = { email: email.trim(), full_name: fullName.trim(), role }
    setBusy(true)
    try {
      const saved = account ? await updateAccount(session, account.id, input) : await createAccount(session, input)
      onSaved(saved, account === null)
    } catch (error) {
      setServerError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open
      title={account ? `Modifier le compte de ${account.full_name}` : 'Nouveau compte'}
      description={
        account
          ? "Un changement de rôle s'applique dès la prochaine action de la personne."
          : "Le compte est créé actif. Son titulaire choisit son mot de passe avec « Mot de passe oublié ? » sur l'écran de connexion."
      }
      onClose={onClose}
      onSubmit={handleSubmit}
      footer={
        <>
          <button type="button" className="button-secondary" onClick={onClose}>
            Annuler
          </button>
          <button type="submit" className="button-primary" disabled={busy}>
            {busy ? 'Enregistrement…' : account ? 'Enregistrer' : 'Créer le compte'}
          </button>
        </>
      }
    >
      <div className="form-grid account-form-grid">
        <div className="field field-wide">
          <label htmlFor="account-email">E-mail institutionnel</label>
          <input
            id="account-email"
            className="input"
            type="email"
            autoComplete="off"
            placeholder={`prenom.nom${DOMAIN}`}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? 'account-email-error' : undefined}
            data-autofocus
          />
          {errors.email && (
            <p id="account-email-error" className="field-error">
              {errors.email}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="account-name">Nom complet</label>
          <input
            id="account-name"
            className="input"
            autoComplete="off"
            maxLength={150}
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            aria-invalid={!!errors.fullName}
            aria-describedby={errors.fullName ? 'account-name-error' : undefined}
          />
          {errors.fullName && (
            <p id="account-name-error" className="field-error">
              {errors.fullName}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="account-role">Rôle</label>
          <select
            id="account-role"
            className="select"
            value={role}
            onChange={(event) => setRole(event.target.value as Role)}
            disabled={isSelf}
            aria-describedby={isSelf ? 'account-self-hint' : undefined}
          >
            {ROLES.map((value) => (
              <option key={value} value={value}>
                {ROLE_LABELS[value]}
              </option>
            ))}
          </select>
          {isSelf && (
            <p id="account-self-hint" className="field-hint">
              Vous ne pouvez pas retirer vos propres droits d'administrateur.
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
