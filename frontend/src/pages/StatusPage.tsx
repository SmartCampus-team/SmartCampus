// Page affichée pour une adresse inconnue ou un accès refusé (SC-17).

import { InfoIcon } from '../components/icons'
import { Link } from '../router'

interface Props {
  title: string
  message: string
}

export default function StatusPage({ title, message }: Props) {
  return (
    <section className="status-page" aria-labelledby="status-title">
      <span className="status-icon" aria-hidden="true">
        <InfoIcon />
      </span>
      <h1 id="status-title">{title}</h1>
      <p>{message}</p>
      <Link to="/" className="button-secondary">
        Retour à l'accueil
      </Link>
    </section>
  )
}
