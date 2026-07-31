import PortalLayout from '../PortalLayout'

/* ============================================================================
   NTPRT27 — Shell du PORTAIL PARTENAIRE (`/portail/partenaire`).
   ----------------------------------------------------------------------------
   Structure identique à NTPRT8/NTPRT20, scopée `partenaire_id`. La nav ne
   liste que les écrans construits ; les suivants viennent avec LEUR tâche :
     - Soumettre un lead (deal registration) → NTPRT28
     - Mes leads distribués                  → NTPRT29
     - Mes commissions (relevé + PDF)        → NTPRT30
     - Ressources marketing                  → NTPRT31
   ========================================================================== */

// Non exporté : utilisé uniquement dans ce fichier (fast-refresh).
const NAV_PARTENAIRE = [
  { to: '/portail/partenaire', label: 'Tableau de bord', end: true },
]

export default function PortalPartenaireLayout({ children }) {
  return (
    <PortalLayout titre="Espace partenaire" items={NAV_PARTENAIRE}>
      {children}
    </PortalLayout>
  )
}
