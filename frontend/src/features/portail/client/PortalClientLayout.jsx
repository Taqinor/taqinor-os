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
     - Consommation      → NTPRT15
     - Contrats          → NTPRT16
     - Équipe            → NTPRT17 (dépend de NTPRT6, invitations)
   ========================================================================== */

// Non exporté : utilisé uniquement dans ce fichier (fast-refresh).
// NTPRT34 — `labelAr` = libellé arabe de l'onglet ; sans lui, le shell rend
// le français (jamais une clé technique).
const NAV_CLIENT = [
  { to: '/portail/client', label: 'Tableau de bord', labelAr: 'لوحة التحكم', end: true },
  { to: '/portail/client/devis', label: 'Devis', labelAr: 'عروض الأسعار' },
  { to: '/portail/client/factures', label: 'Commandes & Factures', labelAr: 'الطلبات والفواتير' },
  // WIR216 — le lien de l'email de livraison (FG228/XSTK22) pointait vers
  // une section qui n'existait pas encore.
  { to: '/portail/client/livraisons', label: 'Livraisons', labelAr: 'التسليمات' },
  // NTPRT14 — timeline (jalons portail CHT10/CHT11) + galerie photos.
  // `labelAr` volontairement absent : repli français documenté ci-dessus, le
  // libellé arabe de cet onglet reste à faire valider (jamais inventé ici).
  { to: '/portail/client/chantiers', label: 'Chantiers' },
]

export default function PortalClientLayout({ children }) {
  return (
    <PortalLayout titre="Espace client" titreAr="فضاء العميل"
                  items={NAV_CLIENT}>
      {children}
    </PortalLayout>
  )
}
