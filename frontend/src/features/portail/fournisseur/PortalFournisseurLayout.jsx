import PortalLayout from '../PortalLayout'

/* ============================================================================
   NTPRT20 — Shell du PORTAIL FOURNISSEUR (`/portail/fournisseur`).
   ----------------------------------------------------------------------------
   Symétrique du shell client (NTPRT8) : même `PortalLayout`, même garde de
   route côté routeur, seule la portée change. La nav ne liste que les écrans
   RÉELLEMENT construits ; les suivants s'ajoutent avec LEUR tâche :
     - Livraisons (ASN)     → NTPRT22
     - Mes factures         → NTPRT23
     - Ma performance       → NTPRT26
   ========================================================================== */

// Non exporté : utilisé uniquement dans ce fichier (fast-refresh).
const NAV_FOURNISSEUR = [
  { to: '/portail/fournisseur', label: 'Tableau de bord', end: true },
  // NTPRT21 — « Mes bons de commande » (liste + confirmation de date).
  { to: '/portail/fournisseur/commandes', label: 'Mes commandes' },
]

export default function PortalFournisseurLayout({ children }) {
  return (
    <PortalLayout titre="Espace fournisseur" items={NAV_FOURNISSEUR}>
      {children}
    </PortalLayout>
  )
}
