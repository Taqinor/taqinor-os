import PortalLayout from '../PortalLayout'

/* ============================================================================
   NTPRT27 — Shell du PORTAIL PARTENAIRE (`/portail/partenaire`).
   ----------------------------------------------------------------------------
   Structure identique à NTPRT8/NTPRT20, scopée `partenaire_id`. La nav ne
   liste que les écrans construits ; les suivants viennent avec LEUR tâche :
     - Mes leads distribués                  → NTPRT29
     - Ressources marketing                  → NTPRT31
   ========================================================================== */

// Non exporté : utilisé uniquement dans ce fichier (fast-refresh).
const NAV_PARTENAIRE = [
  { to: '/portail/partenaire', label: 'Tableau de bord', end: true },
  // NTPRT28 — deal registration : enregistrer une affaire + suivi.
  { to: '/portail/partenaire/affaires', label: 'Mes affaires' },
  // NTPRT30 — relevé de commissions (écran + export PDF).
  { to: '/portail/partenaire/commissions', label: 'Mes commissions' },
]

export default function PortalPartenaireLayout({ children }) {
  return (
    <PortalLayout titre="Espace partenaire" items={NAV_PARTENAIRE}>
      {children}
    </PortalLayout>
  )
}
