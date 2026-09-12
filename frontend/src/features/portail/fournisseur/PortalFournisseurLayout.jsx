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
// NTPRT34 — `labelAr` = libellé arabe de l'onglet (repli français si absent).
const NAV_FOURNISSEUR = [
  { to: '/portail/fournisseur', label: 'Tableau de bord', labelAr: 'لوحة التحكم', end: true },
  // NTPRT21 — « Mes bons de commande » (liste + confirmation de date).
  { to: '/portail/fournisseur/commandes', label: 'Mes commandes', labelAr: 'طلبياتي' },
]

export default function PortalFournisseurLayout({ children }) {
  return (
    <PortalLayout titre="Espace fournisseur" titreAr="فضاء المورّد"
                  items={NAV_FOURNISSEUR}>
      {children}
    </PortalLayout>
  )
}
