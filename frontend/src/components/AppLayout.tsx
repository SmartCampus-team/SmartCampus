// Mise en page des pages connectées (SC-17, SC-20, SC-21, SC-19) : barre du haut, navigation selon le rôle,
// déconnexion (SC-15) et retour à la connexion quand le jeton expire.

import { useEffect, useState, type ComponentType, type ReactNode } from 'react'
import { fetchMe, logout, setUnauthorizedHandler } from '../api/client'
import { clearSession, isExpired, ROLE_LABELS, type Role, type Session, type SessionUser } from '../auth/session'
import { Link } from '../router'
import Avatar, { useProfilePhoto } from './Avatar'
import { FileIcon, HomeIcon, LogoutIcon, SearchIcon, SettingsIcon, UsersIcon, type IconProps } from './icons'

interface NavItem {
  to: string
  label: string
  Icon: ComponentType<IconProps>
  roles?: Role[] // absent : tous les rôles
  isActive: (path: string) => boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Accueil', Icon: HomeIcon, isActive: (path) => path === '/' },
  {
    to: '/salles',
    label: 'Salles',
    Icon: SearchIcon,
    isActive: (path) => path === '/salles' || path.startsWith('/salles/'),
  },
  {
    to: '/gestion/salles',
    label: 'Gestion des salles',
    Icon: SettingsIcon,
    roles: ['gestionnaire'],
    isActive: (path) => path === '/gestion/salles',
  },
  {
    to: '/admin/comptes',
    label: 'Comptes',
    Icon: UsersIcon,
    roles: ['administrateur'],
    isActive: (path) => path === '/admin/comptes',
  },
]

interface Props {
  session: Session
  path: string
  onLoggedOut: () => void
  onUserUpdated: (user: SessionUser) => void
  children: ReactNode
}

export default function AppLayout({ session, path, onLoggedOut, onUserUpdated, children }: Props) {
  const [busy, setBusy] = useState(false)
  const { user } = session
  const photoUrl = useProfilePhoto(session)

  useEffect(() => {
    setUnauthorizedHandler(onLoggedOut)

    const checkExpiry = () => {
      if (isExpired(session)) {
        clearSession()
        onLoggedOut()
      }
    }
    window.addEventListener('focus', checkExpiry)
    document.addEventListener('visibilitychange', checkExpiry)

    return () => {
      setUnauthorizedHandler(null)
      window.removeEventListener('focus', checkExpiry)
      document.removeEventListener('visibilitychange', checkExpiry)
    }
    // Relancé seulement si le jeton change : modifier le nom affiché ne recrée pas les écouteurs
  }, [session.accessToken, onLoggedOut])

  // Rafraîchit le nom et le rôle affichés (un administrateur a pu les modifier)
  useEffect(() => {
    fetchMe(session)
      .then(onUserUpdated)
      .catch(() => {
        // Profil non rafraîchi : celui de la session reste affiché
      })
  }, [session.accessToken, onUserUpdated])

  async function handleLogout() {
    setBusy(true)
    try {
      await logout(session)
    } catch {
      // Même si l'API est injoignable, la session locale est effacée (voir logout)
    } finally {
      onLoggedOut()
    }
  }

  const items = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(user.role))

  return (
    <div className="app-shell">
      {/* Lien d'évitement : l'ancre de l'URL sert à la navigation, d'où le focus posé à la main */}
      <a
        className="skip-link"
        href="#contenu"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('contenu')?.focus()
        }}
      >
        Aller au contenu
      </a>

      <header className="topbar">
        <div className="topbar-inner home-container">
          <Link to="/" className="topbar-brand wordmark-link" aria-label="SmartCampus, accueil">
            <span className="wordmark">
              Smart<span>Campus</span>
            </span>
          </Link>

          <nav className="topnav" aria-label="Navigation principale">
            {items.map(({ to, label, Icon, isActive }) => {
              const active = isActive(path)
              return (
                <Link
                  key={to}
                  to={to}
                  className={active ? 'topnav-link is-active' : 'topnav-link'}
                  aria-current={active ? 'page' : undefined}
                >
                  <Icon />
                  {label}
                </Link>
              )
            })}
            {user.role === 'etudiant' && (
              <span className="topnav-link is-soon" aria-disabled="true" title="Disponible au Sprint 4">
                <FileIcon />
                Mes demandes
                <span className="visually-hidden"> (disponible au Sprint 4)</span>
              </span>
            )}
          </nav>

          <Link
            to="/profil"
            className={path === '/profil' ? 'topbar-user topbar-user-link is-active' : 'topbar-user topbar-user-link'}
            aria-label={`Mon profil : ${user.full_name}, ${ROLE_LABELS[user.role]}`}
            aria-current={path === '/profil' ? 'page' : undefined}
            title="Mon profil"
          >
            <Avatar name={user.full_name} photoUrl={photoUrl} />
            <span className="topbar-user-text" aria-hidden="true">
              <strong>{user.full_name}</strong>
              <span>{ROLE_LABELS[user.role]}</span>
            </span>
          </Link>

          <button type="button" className="button-secondary logout" onClick={handleLogout} disabled={busy}>
            <LogoutIcon />
            <span className="logout-label">{busy ? 'Déconnexion…' : 'Se déconnecter'}</span>
          </button>
        </div>
      </header>

      <main id="contenu" className="app-main home-container" tabIndex={-1}>
        {children}
      </main>
    </div>
  )
}
