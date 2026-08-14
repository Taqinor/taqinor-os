/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  LayoutDashboard, CalendarDays, Megaphone, Workflow, Users2, ListChecks,
  CalendarClock, ClipboardList, Gift, FormInput, PhoneCall,
  Send, Star, Gauge, MessageCircle, Link2, PieChart,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   MARKETING (XMKT30, NTMKT1) — configuration du module « Marketing »
   (auto-enregistré).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/marketing/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta. Gatée « responsable / admin », comme les autres écrans de
   pilotage commercial/comptable (compta, flotte). Écrans chargés en lazy
   (code-splitting préservé).

   NTMKT1 — le moteur backend `apps/marketing` (34 modèles, ~28 endpoints REST,
   voir `frontend/src/api/marketingApi.js`) n'exposait qu'UN SEUL écran
   (calendrier). Comble le vide : sous-menu à 9 écrans (Campagnes, Séquences,
   Segments, Listes, Événements, Enquêtes, Fidélité, Domaine d'envoi,
   Calendrier — inchangé) + `MarketingDashboard.jsx` en page d'accueil du
   module (`/marketing`, PAS dans le sous-menu — landing implicite, cohérent
   avec le compte de 9 de l'écran de vérification NTMKT1). Les écrans de
   détail (`/marketing/campagnes/:id`, `/marketing/sequences/:id`,
   `/marketing/evenements/:id`, `/marketing/enquetes/:id`) et
   `SupportsOffline.jsx` (NTMKT10, lié depuis Paramètres → Marketing) ne sont
   pas des entrées de sous-menu — ouverts par clic depuis leur liste.
   ========================================================================== */

/* EXTENSION `.jsx` OBLIGATOIRE sur `MarketingDashboard`/`CampagneDetail` : le
   dossier contient AUSSI les modules de logique pure `marketingDashboard.js` et
   `campagneDetail.js`. Sans extension, Vite essaie `.js` AVANT `.jsx`, et sur un
   système de fichiers insensible à la casse (Windows, macOS par défaut)
   `./MarketingDashboard` résout vers `marketingDashboard.js` — un module sans
   export `default` : l'écran se monte alors avec un composant `undefined` et la
   route plante (« Element type is invalid »). Ne jamais retirer l'extension. */
const MarketingDashboard = lazy(() => import('./MarketingDashboard.jsx'))
const MarketingCalendarScreen = lazy(() => import('./MarketingCalendarScreen'))
// NTMKT2/3 — liste + détail campagnes (drill-down envois, test A/B XMKT14).
const CampagnesList = lazy(() => import('./CampagnesList'))
const CampagneDetail = lazy(() => import('./CampagneDetail.jsx'))
// NTMKT4 — segments dynamiques (XMKT6) avec prévisualisation live.
const SegmentsList = lazy(() => import('./SegmentsList'))
// NTMKT5 — listes de diffusion + import CSV/XLSX (XMKT5).
const ListesDiffusion = lazy(() => import('./ListesDiffusion'))
// NTMKT6 — séquences de relance (FG202/XMKT1/18/19/20) + vue participant.
const SequencesList = lazy(() => import('./SequencesList'))
const SequenceDetail = lazy(() => import('./SequenceDetail'))
// NTMKT7 — événements marketing (XMKT28) + check-in + QR par inscrit.
const EvenementsList = lazy(() => import('./EvenementsList'))
const EvenementDetail = lazy(() => import('./EvenementDetail'))
// NTMKT8 — enquêtes configurables (XMKT27) + page résultats.
const EnquetesList = lazy(() => import('./EnquetesList'))
const EnqueteResultats = lazy(() => import('./EnqueteResultats'))
// NTMKT9 — fidélité (points/mouvements, FG240) + règles d'upsell (FG241).
const FideliteList = lazy(() => import('./FideliteList'))
// NTMKT10 — supports offline QR (XMKT29), lié depuis Paramètres → Marketing
// (`DomaineEnvoi.jsx`, `frontend/src/features/parametres/`) — pas de nav ici.
const SupportsOffline = lazy(() => import('./SupportsOffline'))
// WIR64/FG206 — formulaires d'intake (landing publique de capture de lead).
const FormulairesIntakeList = lazy(() => import('./FormulairesIntakeList'))
// WIR161 — journal d'appels commercial (click-to-call log, FG208).
const JournalAppelsScreen = lazy(() => import('./JournalAppelsScreen'))
// PACT106 — avis clients + routage Google Reviews (FG239).
const AvisClients = lazy(() => import('./AvisClients'))
// PACT107 — enquêtes NPS post-installation (FG238), distinctes du Pulse eNPS.
const EnquetesNps = lazy(() => import('./EnquetesNps'))
// PACT108 — journal des messages WhatsApp entrants (FG207), lecture seule.
const MessagesWhatsapp = lazy(() => import('./MessagesWhatsapp'))
// NTMKT25 — générateur d'URL de campagne (tags UTM, hors campagne ERP).
const UtmBuilder = lazy(() => import('./UtmBuilder'))
// NTMKT21 — rapport comparatif multi-modèle d'attribution (adossé à NTMKT20).
// Écran de plein droit (il porte sa propre saisie de devis quand aucun
// `devisId` ne lui est passé), donc une entrée de sous-menu, pas un détail.
const AttributionReport = lazy(() => import('./AttributionReport'))
// NTMKT29/30/32 — wizards guidés (campagne/séquence/enquête), ouverts par le
// bouton « (guidé) » de leur liste respective (jamais une entrée de sous-menu
// séparée — même traitement que les écrans de détail ci-dessus).
const CampagneWizard = lazy(() => import('./CampagneWizard.jsx'))
const SequenceWizard = lazy(() => import('./SequenceWizard.jsx'))
const EnqueteWizard = lazy(() => import('./EnqueteWizard.jsx'))
// NTMKT31 — réglages tenant du module Marketing (dérogation de périmètre :
// vit ici plutôt que sous `features/parametres/`, voir le fichier).
const MarketingParametres = lazy(() => import('./MarketingParametres.jsx'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'marketing',
  order: 55,
  nav: {
    label: 'MARKETING',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Send),
    accent: 'brass', // VX8 — commercial/croissance = accent brass (dérivé)
    items: [
      { to: '/marketing/campagnes', label: 'Campagnes', icon: <Megaphone size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/sequences', label: 'Séquences', icon: <Workflow size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/segments', label: 'Segments', icon: <Users2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/listes', label: 'Listes de diffusion', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/evenements', label: 'Événements', icon: <CalendarClock size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/enquetes', label: 'Enquêtes', icon: <ClipboardList size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/fidelite', label: 'Fidélité', icon: <Gift size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/formulaires-intake', label: "Formulaires d'intake", icon: <FormInput size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/appels', label: "Journal d'appels", icon: <PhoneCall size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/avis-clients', label: 'Avis clients', icon: <Star size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/enquetes-nps', label: 'Enquêtes NPS', icon: <Gauge size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/messages-whatsapp', label: 'Messages WhatsApp', icon: <MessageCircle size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/generateur-url', label: "Générateur d'URL", icon: <Link2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      // NTMKT21 — rapport d'attribution (comparaison des 4 modèles NTMKT20).
      { to: '/marketing/attribution', label: "Rapport d'attribution", icon: <PieChart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/parametres/marketing', label: "Domaine d'envoi", icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      // NTMKT31 — réglages tenant (expéditeur/fenêtre silencieuse/plafond/langue).
      { to: '/marketing/parametres', label: 'Paramètres marketing', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/calendrier', label: 'Calendrier marketing', icon: <CalendarDays size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta — du plus spécifique au plus général.
  titles: [
    ['/marketing/calendrier', 'Calendrier marketing'],
    // NTMKT29/30/32 — wizards guidés : plus spécifique que les listes
    // ci-dessous, donc listés AVANT elles (ordre du plus spécifique au plus
    // général exigé par routes.meta).
    ['/marketing/campagnes/nouveau', 'Créer une campagne (guidé)'],
    ['/marketing/campagnes', 'Campagnes marketing'],
    ['/marketing/sequences/nouveau', 'Configurer une séquence (guidé)'],
    ['/marketing/sequences', 'Séquences de relance'],
    ['/marketing/segments', 'Segments marketing'],
    ['/marketing/listes', 'Listes de diffusion'],
    ['/marketing/evenements', 'Événements marketing'],
    ['/marketing/enquetes/nouveau', 'Créer une enquête (guidé)'],
    ['/marketing/enquetes', 'Enquêtes'],
    ['/marketing/fidelite', 'Fidélité'],
    ['/marketing/formulaires-intake', "Formulaires d'intake"],
    ['/marketing/appels', "Journal d'appels"],
    ['/marketing/avis-clients', 'Avis clients'],
    ['/marketing/enquetes-nps', 'Enquêtes NPS'],
    ['/marketing/messages-whatsapp', 'Messages WhatsApp entrants'],
    ['/marketing/supports-offline', 'Supports offline (QR)'],
    ['/marketing/generateur-url', "Générateur d'URL de campagne"],
    ['/marketing/attribution', "Rapport d'attribution"],
    // NTMKT31 — réglages tenant.
    ['/marketing/parametres', 'Paramètres marketing'],
    ['/marketing', 'Tableau de bord marketing'],
  ],
  sectionLabels: { marketing: 'Marketing' },
  routes: [
    { path: '/marketing', component: MarketingDashboard, roles: ROLES },
    { path: '/marketing/calendrier', component: MarketingCalendarScreen, roles: ROLES },
    { path: '/marketing/campagnes', component: CampagnesList, roles: ROLES },
    // NTMKT29 — segment statique, priorisé automatiquement sur `:id` par le
    // scoring de react-router (segment statique > dynamique).
    { path: '/marketing/campagnes/nouveau', component: CampagneWizard, roles: ROLES },
    { path: '/marketing/campagnes/:id', component: CampagneDetail, roles: ROLES },
    { path: '/marketing/segments', component: SegmentsList, roles: ROLES },
    { path: '/marketing/listes', component: ListesDiffusion, roles: ROLES },
    { path: '/marketing/sequences', component: SequencesList, roles: ROLES },
    // NTMKT30 — idem, statique avant `:id`.
    { path: '/marketing/sequences/nouveau', component: SequenceWizard, roles: ROLES },
    { path: '/marketing/sequences/:id', component: SequenceDetail, roles: ROLES },
    { path: '/marketing/evenements', component: EvenementsList, roles: ROLES },
    { path: '/marketing/evenements/:id', component: EvenementDetail, roles: ROLES },
    { path: '/marketing/enquetes', component: EnquetesList, roles: ROLES },
    // NTMKT32 — idem, statique avant `:id`.
    { path: '/marketing/enquetes/nouveau', component: EnqueteWizard, roles: ROLES },
    { path: '/marketing/enquetes/:id', component: EnqueteResultats, roles: ROLES },
    { path: '/marketing/fidelite', component: FideliteList, roles: ROLES },
    { path: '/marketing/formulaires-intake', component: FormulairesIntakeList, roles: ROLES },
    { path: '/marketing/appels', component: JournalAppelsScreen, roles: ROLES },
    { path: '/marketing/avis-clients', component: AvisClients, roles: ROLES },
    { path: '/marketing/enquetes-nps', component: EnquetesNps, roles: ROLES },
    { path: '/marketing/messages-whatsapp', component: MessagesWhatsapp, roles: ROLES },
    { path: '/marketing/supports-offline', component: SupportsOffline, roles: ROLES },
    { path: '/marketing/generateur-url', component: UtmBuilder, roles: ROLES },
    { path: '/marketing/attribution', component: AttributionReport, roles: ROLES },
    // NTMKT31 — réglages tenant.
    { path: '/marketing/parametres', component: MarketingParametres, roles: ROLES },
  ],
}

export default config
