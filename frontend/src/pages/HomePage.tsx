// Accueil de SmartCampus (SC-11, SC-17) : la barre du haut est dans AppLayout ;
// chaque service devient un lien quand son écran est livré.

import type { ComponentType } from 'react'
import { ROLE_LABELS, type SessionUser } from '../auth/session'
import {
  ArrowIcon,
  BuildingIcon,
  CalendarCheckIcon,
  CalendarIcon,
  FileIcon,
  MailIcon,
  SearchIcon,
  UserIcon,
  type IconProps,
} from '../components/icons'
import { Link } from '../router'

interface Props {
  user: SessionUser
}

interface Service {
  title: string
  description: string
  Icon: ComponentType<IconProps>
  to?: string // page disponible
  sprint?: number // sinon, sprint qui la livre (cahier des charges, chapitre 8)
}

const SERVICES: Service[] = [
  {
    title: 'Recherche de salle',
    description: "Consultez la disponibilité des salles et trouvez l'espace adapté à vos besoins.",
    Icon: SearchIcon,
    to: '/salles',
  },
  {
    title: 'Réservation de salle',
    description: 'Réservez une salle en quelques clics pour vos cours, réunions ou événements.',
    Icon: CalendarCheckIcon,
    sprint: 3,
  },
  {
    title: 'Démarches administratives',
    description: "Effectuez vos demandes administratives en ligne et suivez leur état d'avancement.",
    Icon: FileIcon,
    sprint: 4,
  },
]

function formatToday(): string {
  const label = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export default function HomePage({ user }: Props) {
  const firstName = user.full_name.trim().split(/\s+/)[0] || user.full_name
  const roleLabel = ROLE_LABELS[user.role]

  return (
    <>
      <section className="home-greeting">
        <div>
          <div className="home-title-row">
            <h1>Bonjour, {firstName}</h1>
          </div>
          <p className="home-subtitle">Bon retour sur SmartCampus</p>
        </div>

        <div className="home-meta">
          <p className="home-meta-date">
            <CalendarIcon />
            {formatToday()}
          </p>
        </div>
      </section>

      <section className="home-hero" aria-labelledby="hero-title">
        <div className="home-hero-text">
          <h2 id="hero-title">Tout votre campus, au même endroit.</h2>
          <p>Réservez vos espaces, effectuez vos démarches et suivez vos demandes en toute simplicité.</p>
          <span className="home-hero-rule" aria-hidden="true" />
        </div>
        <div className="home-hero-art" aria-hidden="true">
          <img src="/login-illustration.svg" alt="" />
        </div>
      </section>

      <section id="services" className="home-section" aria-labelledby="services-title">
        <h2 id="services-title" className="home-section-title">
          Services campus
        </h2>
        <ul className="service-grid">
          {SERVICES.map(({ title, description, Icon, to, sprint }) => (
            <li key={title} className={to ? 'service-card is-available' : 'service-card'}>
              <span className="service-icon">
                <Icon />
              </span>
              <div>
                <h3>
                  {to ? (
                    <Link to={to} className="service-link">
                      {title}
                      <ArrowIcon className="service-link-arrow" />
                    </Link>
                  ) : (
                    title
                  )}
                </h3>
                {sprint && <span className="sprint-badge">Sprint {sprint}</span>}
                <p>{description}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="home-section" aria-labelledby="account-title">
        <h2 id="account-title" className="home-section-title">
          Votre compte
        </h2>
        <div className="account-card">
          <div className="account-person">
            <span className="account-avatar">
              <UserIcon />
            </span>
            <div>
              <strong>{user.full_name}</strong>
              <span>{roleLabel}</span>
            </div>
          </div>
          <dl className="account-details">
            <div className="account-item">
              <dt>
                <MailIcon />
                E-mail institutionnel
              </dt>
              <dd>{user.email}</dd>
            </div>
            <div className="account-item">
              <dt>
                <BuildingIcon />
                Établissement
              </dt>
              <dd>ENSA Khouribga</dd>
            </div>
          </dl>
        </div>
      </section>
    </>
  )
}
