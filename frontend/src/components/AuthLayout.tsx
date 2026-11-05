// Décor des pages sans session (SC-18) : illustration et présentation à gauche, carte à droite.
// Repris de la page de connexion (SC-11) pour le mot de passe oublié et la réinitialisation.

import type { ReactNode } from 'react'
import { CheckIcon } from './icons'
import './AuthLayout.css'

const PERKS = ['Rapide et sécurisé', 'Accessible partout', 'Conçu pour la communauté ENSA']

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="login-page">
      <img className="login-illustration" src="/login-illustration.svg" alt="" />

      <section className="login-hero">
        <div className="login-brand">
          <span className="login-wordmark">
            Smart<span>Campus</span>
          </span>
        </div>

        <h1>Simplifiez votre vie universitaire.</h1>
        <p className="login-lead">Réservation de salles, demandes administratives et bien plus encore.</p>

        <ul className="login-perks">
          {PERKS.map((perk) => (
            <li key={perk}>
              <CheckIcon className="login-check" />
              {perk}
            </li>
          ))}
        </ul>
      </section>

      {children}
    </main>
  )
}
