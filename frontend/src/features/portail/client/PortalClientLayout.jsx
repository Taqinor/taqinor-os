import PortalLayout from '../PortalLayout'

/* ============================================================================
   NTPRT8 — Shell du PORTAIL CLIENT (`/portail/client`).
   ----------------------------------------------------------------------------
   Nav volontairement RÉDUITE aux sections RÉELLEMENT construites : un onglet
   qui pointerait vers un écran inexistant enverrait le client sur un 404. Les
   sections restantes du plan NTPRT arrivent avec LEUR tâche et s'ajoutent ici
   en une ligne :
     - SAV               → NTPRT12
     - Documents         → NTPRT13
     - Chantiers         → NTPRT14
     - Consommation      → NTPRT15
     - Contrats          → NTPRT16
     - Équipe            → NTPRT17 (dépend de NTPRT6, invitations)
   ========================================================================== */

// Non exporté : utilisé uniquement dans ce fichier (fast-refresh).
const NAV_CLIENT = [
  { to: '/portail/client', label: 'Tableau de bord', end: true },
  { to: '/portail/client/devis', label: 'Devis' },
  { to: '/portail/client/factures', label: 'Commandes & Factures' },
  // WIR216/XSTK22 — le lien de l'email de transition de livraison pointait
  // vers une section inexistante ; elle existe maintenant et rejoint le menu.
  { to: '/portail/client/livraisons', label: 'Livraisons' },
]

export default function PortalClientLayout({ children }) {
  return (
    <PortalLayout titre="Espace client" items={NAV_CLIENT}>
      {children}
    </PortalLayout>
  )
}
