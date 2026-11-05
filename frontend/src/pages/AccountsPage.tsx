// Gestion des comptes : créer, modifier, attribuer un rôle, désactiver (SC-17, EF-AUTH-07, ENF-03).

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { errorMessage } from '../api/client'
import { fetchAccounts, updateAccount, type Account, type AccountFilters } from '../api/users'
import { ROLE_LABELS, type Role, type Session } from '../auth/session'
import Dialog from '../components/Dialog'
import { PencilIcon, PlusIcon, UsersIcon } from '../components/icons'
import AccountFormDialog from './AccountFormDialog'
import './AccountsPage.css'

interface Props {
  session: Session
}

const ROLES = Object.keys(ROLE_LABELS) as Role[]

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
}

function StatusBadge({ account }: { account: Account }) {
  if (!account.is_active) return <span className="badge badge-neutral">Désactivé</span>
  return <span className="badge badge-success">Actif</span>
}

export default function AccountsPage({ session }: Props) {
  const [accounts, setAccounts] = useState<Account[] | null>(null)
  const [filters, setFilters] = useState<AccountFilters>({ q: '', role: '', active: '' })
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState<Account | 'new' | null>(null)
  const [toggling, setToggling] = useState<Account | null>(null)
  const [toggleError, setToggleError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    return fetchAccounts(session, filters)
      .then((list) => {
        setAccounts(list)
        setError(null)
      })
      .catch((err) => setError(errorMessage(err)))
  }, [session, filters])

  useEffect(() => {
    load()
  }, [load])

  // La recherche part 300 ms après la dernière frappe
  useEffect(() => {
    const timer = window.setTimeout(() => setFilters((current) => ({ ...current, q: query.trim() })), 300)
    return () => window.clearTimeout(timer)
  }, [query])

  function handleSaved(account: Account, created: boolean) {
    setEditing(null)
    setMessage(created ? `Compte de ${account.full_name} créé.` : `Compte de ${account.full_name} modifié.`)
    load()
  }

  async function handleToggle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!toggling) return
    setBusy(true)
    setToggleError(null)
    try {
      const saved = await updateAccount(session, toggling.id, { is_active: !toggling.is_active })
      setToggling(null)
      setMessage(`Compte de ${saved.full_name} ${saved.is_active ? 'réactivé' : 'désactivé'}.`)
      load()
    } catch (err) {
      setToggleError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  function closeToggle() {
    setToggling(null)
    setToggleError(null)
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Gestion des comptes</h1>
          <p>Créez les comptes, attribuez les rôles et désactivez les comptes qui ne doivent plus se connecter.</p>
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
          Nouveau compte
        </button>
      </header>

      {message && (
        <p className="notice notice-success page-message" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="notice notice-error page-message" role="alert">
          {error}
        </p>
      )}

      <div className="toolbar">
        <div className="toolbar-filters">
          <div className="field">
            <label htmlFor="accounts-search">Rechercher</label>
            <input
              id="accounts-search"
              className="input"
              type="search"
              placeholder="Nom ou e-mail"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="accounts-role">Rôle</label>
            <select
              id="accounts-role"
              className="select"
              value={filters.role}
              onChange={(event) => setFilters((current) => ({ ...current, role: event.target.value as Role | '' }))}
            >
              <option value="">Tous les rôles</option>
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {ROLE_LABELS[role]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="accounts-status">État</label>
            <select
              id="accounts-status"
              className="select"
              value={filters.active}
              onChange={(event) =>
                setFilters((current) => ({ ...current, active: event.target.value as AccountFilters['active'] }))
              }
            >
              <option value="">Tous</option>
              <option value="true">Actifs</option>
              <option value="false">Désactivés</option>
            </select>
          </div>
        </div>
        {accounts && (
          <p className="toolbar-count">
            {accounts.length} compte{accounts.length > 1 ? 's' : ''}
          </p>
        )}
      </div>

      {accounts === null && !error && <p className="loading">Chargement des comptes…</p>}
      {accounts !== null && accounts.length === 0 && (
        <p className="empty-state">
          <UsersIcon className="empty-icon" />
          Aucun compte ne correspond à ces critères.
        </p>
      )}

      {accounts && accounts.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">Comptes SmartCampus</caption>
            <thead>
              <tr>
                <th scope="col">Nom</th>
                <th scope="col">E-mail</th>
                <th scope="col">Rôle</th>
                <th scope="col">État</th>
                <th scope="col" className="col-optional">
                  Créé le
                </th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => {
                const isSelf = account.id === session.user.id
                return (
                  <tr key={account.id} className={account.is_active ? undefined : 'is-muted'}>
                    <td className="cell-strong">
                      {account.full_name}
                      {isSelf && <span className="cell-muted"> (vous)</span>}
                    </td>
                    <td>{account.email}</td>
                    <td>{ROLE_LABELS[account.role]}</td>
                    <td>
                      <StatusBadge account={account} />
                    </td>
                    <td className="cell-muted col-optional">{formatDate(account.created_at)}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          type="button"
                          className="icon-button"
                          onClick={() => {
                            setMessage(null)
                            setEditing(account)
                          }}
                          aria-label={`Modifier le compte de ${account.full_name}`}
                          title="Modifier"
                        >
                          <PencilIcon />
                        </button>
                        {!isSelf && (
                          <button
                            type="button"
                            className={account.is_active ? 'button-secondary is-compact is-danger' : 'button-secondary is-compact'}
                            onClick={() => {
                              setMessage(null)
                              setToggling(account)
                            }}
                          >
                            {account.is_active ? 'Désactiver' : 'Réactiver'}
                            <span className="visually-hidden"> le compte de {account.full_name}</span>
                          </button>
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
        <AccountFormDialog
          session={session}
          account={editing === 'new' ? null : editing}
          isSelf={editing !== 'new' && editing.id === session.user.id}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}

      <Dialog
        open={toggling !== null}
        size="small"
        title={
          toggling?.is_active
            ? `Désactiver le compte de ${toggling.full_name} ?`
            : `Réactiver le compte de ${toggling?.full_name ?? ''} ?`
        }
        description={
          toggling?.is_active
            ? 'La personne ne pourra plus se connecter et ses sessions en cours seront coupées. Le compte et son historique sont conservés.'
            : 'La personne pourra de nouveau se connecter avec son mot de passe.'
        }
        onClose={closeToggle}
        onSubmit={handleToggle}
        footer={
          <>
            <button type="button" className="button-secondary" onClick={closeToggle}>
              Annuler
            </button>
            <button type="submit" className={toggling?.is_active ? 'button-danger' : 'button-primary'} disabled={busy}>
              {busy ? 'Enregistrement…' : toggling?.is_active ? 'Désactiver' : 'Réactiver'}
            </button>
          </>
        }
      >
        {toggleError && (
          <p className="notice notice-error" role="alert">
            {toggleError}
          </p>
        )}
      </Dialog>
    </>
  )
}
