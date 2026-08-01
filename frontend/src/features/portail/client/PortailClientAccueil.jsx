import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { FileText, Receipt } from 'lucide-react'
import { Card } from '../../../ui'

/* ============================================================================
   NTPRT8 — Accueil du portail client.
   ----------------------------------------------------------------------------
   Point d'entrée du shell : orientation vers les sections disponibles. Les
   CARTES CHIFFRÉES (devis en attente, factures impayées, tickets, prochain
   jalon) appartiennent à NTPRT9, qui branchera ici les selectors
   `ventes`/`sav`/`installations` scopés au client connecté — cet écran ne
   fabrique donc AUCUN chiffre local en attendant (un chiffre inventé côté
   portail serait pire qu'un chiffre absent).
   ========================================================================== */

const SECTIONS = [
  {
    to: '/portail/client/devis',
    icone: FileText,
    titre: 'Mes devis',
    texte: 'Consulter vos propositions et les accepter en ligne.',
  },
  {
    to: '/portail/client/factures',
    icone: Receipt,
    titre: 'Mes commandes & factures',
    texte: 'Suivre vos factures et leur règlement.',
  },
]

export default function PortailClientAccueil() {
  const user = useSelector((s) => s.auth.user)

  return (
    <>
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Bonjour{user?.first_name ? ` ${user.first_name}` : ''}
      </h1>
      <p className="text-sm text-muted-foreground">
        Bienvenue dans votre espace client.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {SECTIONS.map((section) => {
          const { to, icone: Icone, titre, texte } = section
          return (
          <Card key={to} className="p-4">
            <Link to={to} className="flex items-start gap-3">
              <Icone className="mt-0.5 size-5 text-muted-foreground"
                     aria-hidden="true" />
              <span>
                <span className="block font-medium">{titre}</span>
                <span className="block text-sm text-muted-foreground">
                  {texte}
                </span>
              </span>
            </Link>
          </Card>
          )
        })}
      </div>
    </>
  )
}
