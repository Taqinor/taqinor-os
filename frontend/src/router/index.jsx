/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration du routeur (lazy imports + loaders), pas un module
   de composants : le fast-refresh ne s'y applique pas. */
import { createBrowserRouter, Navigate, redirect, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { store } from '../store'
import { fetchMe } from '../features/auth/store/authSlice'
import Layout from '../components/layout/Layout'
// Providers UX dépendant du contexte routeur (useNavigate) → montés DANS le
// router, au chokepoint commun des écrans authentifiés (WithLayout).
import { CommandPalette } from '../providers/CommandPalette'
import { ShortcutsProvider } from '../providers/ShortcutsProvider'
// O65 — Repli « skeleton-first » pendant le chargement lazy d'un bundle de page.
import RouteFallback from '../components/RouteFallback'
// L880 — Error-boundary de route globale : écran FR de récupération au lieu
// d'une application blanche sur une erreur de rendu non capturée.
import RouteErrorBoundary from '../components/RouteErrorBoundary'
// UX1 — Registre de modules : chaque module « coquille » (Compta, Paie, RH,
// Flotte, QHSE, Contrats, Projet, GED, KB, Litiges…) enregistre ses routes via
// un fichier `features/<module>/module.config.jsx`, sans toucher ce fichier.
import { buildModuleRoutes } from './moduleRoutes'

// ── Pages lazy ────────────────────────────────────────────────────────────────
const Landing = lazy(() => import('../pages/Landing'))
const Login = lazy(() => import('../pages/Login'))
const Dashboard = lazy(() => import('../pages/Dashboard').then(m => ({ default: m.Component })))
const Reporting = lazy(() => import('../pages/Reporting').then(m => ({ default: m.Component })))
const Rapports = lazy(() => import('../pages/Rapports').then(m => ({ default: m.Component })))
const ContratsMaintenance = lazy(() => import('../pages/sav/ContratsMaintenance').then(m => ({ default: m.Component })))
const ClientList = lazy(() => import('../pages/crm/ClientList'))
const LeadsPage = lazy(() => import('../pages/crm/leads/LeadsPage'))
const DevisList = lazy(() => import('../pages/ventes/DevisList'))
const DevisGenerator = lazy(() => import('../pages/ventes/DevisGenerator'))
const ToitureDesign = lazy(() => import('../pages/ventes/ToitureDesign'))
const RoofViewerPage = lazy(() => import('../pages/ventes/RoofViewerPage'))
const FactureList = lazy(() => import('../pages/ventes/FactureList'))
const VentesKanban = lazy(() => import('../pages/ventes/VentesKanban'))
const ListesPrixPage = lazy(() => import('../pages/ventes/ListesPrixPage'))
const InstallationsPage = lazy(() => import('../pages/installations/InstallationsPage'))
const DemandesAchatList = lazy(() => import('../pages/installations/DemandesAchatList'))
const InterventionsPage = lazy(() => import('../pages/interventions/InterventionsPage'))
const MaJourneePage = lazy(() => import('../pages/interventions/MaJourneePage'))
const ParcInstallePage = lazy(() => import('../pages/installations/ParcInstallePage'))
const PlanificationPage = lazy(() => import('../pages/installations/PlanificationPage'))
const AteliersPage = lazy(() => import('../pages/installations/AteliersPage'))
const OutillagePage = lazy(() => import('../pages/outillage/OutillagePage'))
const ProductionPage = lazy(() => import('../pages/monitoring/ProductionPage'))
const FleetPage = lazy(() => import('../pages/monitoring/FleetPage'))
const OmAnalyticsPage = lazy(() => import('../pages/monitoring/OmAnalyticsPage'))
const WarrantiesPage = lazy(() => import('../pages/monitoring/WarrantiesPage'))
const Co2Page = lazy(() => import('../pages/monitoring/Co2Page'))
const CleaningsPage = lazy(() => import('../pages/monitoring/CleaningsPage'))
const OmReportPage = lazy(() => import('../pages/monitoring/OmReportPage'))
const ClientPortalPage = lazy(() => import('../pages/monitoring/ClientPortalPage'))
const EquipementsPage = lazy(() => import('../pages/sav/EquipementsPage'))
const TicketsPage = lazy(() => import('../pages/sav/TicketsPage'))
const WarrantyClaimsPage = lazy(() => import('../pages/sav/WarrantyClaimsPage'))
const SavParametresPage = lazy(() => import('../pages/sav/SavParametresPage'))
const SavSlaReportPage = lazy(() => import('../pages/sav/SavSlaReportPage'))
const SavAlarmesPage = lazy(() => import('../pages/sav/SavAlarmesPage'))
const SavActionBoardPage = lazy(() => import('../pages/sav/SavActionBoardPage'))
const KbArticlesPage = lazy(() => import('../pages/sav/KbArticlesPage'))
const AgentChat = lazy(() => import('../pages/ia/AgentChat'))
const OcrUpload = lazy(() => import('../pages/ia/OcrUpload'))
const UsersManagement = lazy(() => import('../pages/admin/UsersManagement'))
const RolesManagement = lazy(() => import('../pages/admin/RolesManagement'))
const TenantsConsole = lazy(() => import('../pages/admin/TenantsConsole'))
const ParametresEntreprise = lazy(() => import('../pages/parametres/ParametresEntreprise'))
const ExportSauvegarde = lazy(() => import('../pages/parametres/ExportSauvegarde'))
const NotificationsPreferences = lazy(() => import('../pages/parametres/NotificationsPreferences'))
const Journal = lazy(() => import('../pages/Journal'))
const MesActivitesPage = lazy(() => import('../pages/activities/MesActivitesPage'))
const CalendarPage = lazy(() => import('../pages/CalendarPage'))
const CartePage = lazy(() => import('../pages/CartePage'))
const ParrainagePage = lazy(() => import('../pages/crm/ParrainagePage'))
const AvoirsPage = lazy(() => import('../pages/ventes/AvoirsPage'))
const RelancesPage = lazy(() => import('../pages/ventes/RelancesPage'))
const PaiementsPage = lazy(() => import('../pages/ventes/PaiementsPage'))
const BalanceAgeePage = lazy(() => import('../pages/reporting/BalanceAgeePage'))
const ArchiveClientPage = lazy(() => import('../pages/reporting/ArchiveClientPage'))
const ArchiveChantierPage = lazy(() => import('../pages/reporting/ArchiveChantierPage'))
const CommercialDashboard = lazy(() => import('../pages/reporting/CommercialDashboard'))
const CohortsPage = lazy(() => import('../pages/reporting/CohortsPage'))
const DashboardConfigPage = lazy(() => import('../pages/reporting/DashboardConfigPage'))
// XPLT10 — partage de dashboard (liens publics tokenisés, créer/révoquer).
const DashboardSharePage = lazy(() => import('../pages/reporting/DashboardSharePage'))
// XKB1/ZCTR7-9 — boîte d'approbations centralisée cross-app (5 sources).
const ApprobationsPage = lazy(() => import('../pages/approbations/ApprobationsPage'))
// XPLT6 — CRUD des alertes de seuil sur KPI agrégés.
const KpiAlertesPage = lazy(() => import('../pages/parametres/KpiAlertesPage'))
// XPLT22 — classeur léger embarqué (mini-spreadsheet BI, données live).
const ClasseursListPage = lazy(() => import('../pages/reporting/ClasseursListPage'))
const ClasseurPage = lazy(() => import('../pages/reporting/ClasseurPage'))
// XPLT10 — kiosque TV public des dashboards partagés (sans layout ERP).
const DashboardsTvPage = lazy(() => import('../pages/reporting/DashboardsTvPage'))
// XSAV8 — conformité SLA + KPI SAV avancés.
const SavSlaPage = lazy(() => import('../pages/reporting/SavSlaPage'))
// XFSM16 — analytics field service consolidés.
const FieldServiceReportPage = lazy(() => import('../pages/reporting/FieldServiceReportPage'))
// XFSM17 — scorecard coaching par technicien vs moyenne équipe.
const TechnicienScorecardPage = lazy(() => import('../pages/reporting/TechnicienScorecardPage'))
const AgentActions = lazy(() => import('../pages/ia/AgentActions'))
// Vitrine interne du système UI (refonte, P68) — référence vivante des primitifs.
const UIShowcase = lazy(() => import('../pages/ui/UIShowcase'))
// XSAL17 — page publique de réservation de visite (placeholder {lien_rdv}).
const PublicBookingPage = lazy(() => import('../pages/crm/PublicBookingPage'))
// XCTR14 — portail client public « Mes contrats » (token, sans login).
const PortailContratsPage = lazy(() => import('../features/contrats/PortailContratsPage'))
// XGED1/XGED2 — cérémonie de signature électronique publique (sans login).
const PublicSignaturePage = lazy(() => import('../pages/ged/PublicSignaturePage'))
// XGED7 — dépôt public de fichier (upload-request, sans login).
const PublicDepotPage = lazy(() => import('../pages/ged/PublicDepotPage'))
// XRH10 — guichet kiosque de pointage (device-token, sans session ni layout ERP).
const KiosquePointage = lazy(() => import('../features/rh/Kiosque'))
// XSAV19 — page publique « Signaler un problème » via QR équipement.
const EquipementSignalerPage = lazy(() => import('../pages/sav/EquipementSignalerPage'))
// XSAV10/FG86 — page publique de suivi client d'un ticket SAV + CSAT.
const TicketSuiviPage = lazy(() => import('../pages/sav/TicketSuiviPage'))
// XKB19 — page publique de consultation d'un article KB partagé (lien tokenisé).
const PublicArticlePage = lazy(() => import('../pages/kb/PublicArticlePage'))
const ChatPage = lazy(() => import('../pages/messaging/ChatPage'))
const DocumentsPage = lazy(() => import('../pages/ged/DocumentsPage'))

// ── Auth loader ────────────────────────────────────────────────────────────────
// Verifie la session via le cookie httpOnly — aucun token cote client.
//
// I37 (bug « C7 ») — Robustesse du tout premier chargement à froid sur desktop :
// au démarrage l'app pouvait nécessiter un 2e chargement. La cause : plusieurs
// loaders de routes (et le double-montage StrictMode en dev) déclenchaient
// CHACUN un `fetchMe()` concurrent au lieu de PARTAGER l'amorçage de session.
// On dédoublonne désormais via une UNIQUE promesse d'amorçage : le premier
// loader lance `fetchMe`, les suivants attendent le MÊME résultat. La première
// vue authentifiée n'est rendue qu'une fois la session résolue — un seul
// chargement suffit.
let bootstrapPromise = null

const ensureSession = async () => {
  const state = store.getState().auth
  if (state.isAuthenticated) return true
  // Une amorce est déjà en cours (autre loader / double-montage) → on attend la
  // même, sans relancer un second appel réseau.
  if (!bootstrapPromise) {
    bootstrapPromise = store
      .dispatch(fetchMe())
      .then((result) => fetchMe.fulfilled.match(result))
      .finally(() => { bootstrapPromise = null })
  }
  return bootstrapPromise
}

const authLoader = async () => {
  const ok = await ensureSession()
  return ok ? null : redirect('/login')
}

// ERR27 — Garde de rôle/permission sur les routes d'administration. Reflète
// EXACTEMENT le gating du menu (Sidebar.jsx) : une route n'est accessible que si
// le rôle (menu_tier) figure dans `roles` ET — si une permission est exigée —
// qu'elle est présente dans les permissions de l'utilisateur. Sinon, l'utilisateur
// authentifié mais non autorisé est renvoyé vers `/dashboard` (accessible à tous),
// au lieu de monter la page d'admin via un lien direct.
const roleLoader = (roles, perm) => async () => {
  const ok = await ensureSession()
  if (!ok) return redirect('/login')
  const { role, permissions } = store.getState().auth
  const tier = role || 'normal'
  const allowed = roles.includes(tier) && (!perm || (permissions || []).includes(perm))
  return allowed ? null : redirect('/dashboard')
}

// O65 — squelette de page (en-tête + contenu) au lieu d'un texte brut, pour un
// chargement « skeleton-first » sur toutes les routes (publiques et authentifiées).
const Fallback = () => <RouteFallback />

function WithLayout({ children }) {
  // ShortcutsProvider + CommandPalette vivent ici : ils ont besoin du contexte
  // routeur (navigation clavier / ouverture d'un enregistrement) et ne
  // concernent que les écrans authentifiés. La palette s'ouvre sur ⌘K et sur
  // l'événement window émis par le bouton ⌘K du Header (autre lane).
  //
  // L880 — La page est enveloppée d'une error-boundary keyée par chemin : une
  // erreur de rendu non capturée affiche un écran FR de récupération (« Une
  // erreur est survenue — recharger ») au lieu d'une app blanche, et naviguer
  // ailleurs réinitialise la barrière (nouvelle key).
  const { pathname } = useLocation()
  return (
    <ShortcutsProvider>
      <Layout>
        <RouteErrorBoundary key={pathname}>
          <Suspense fallback={<Fallback />}>{children}</Suspense>
        </RouteErrorBoundary>
      </Layout>
      <CommandPalette />
    </ShortcutsProvider>
  )
}

const router = createBrowserRouter([
  // Entrée de l'OS : un visiteur non connecté arrive DIRECTEMENT sur le login.
  // La landing reste dans le code (route /landing) mais n'est plus l'entrée.
  { path: '/',      element: <Suspense fallback={<Fallback />}><Login /></Suspense> },
  { path: '/landing', element: <Suspense fallback={<Fallback />}><Landing /></Suspense> },
  { path: '/login',  element: <Suspense fallback={<Fallback />}><Login /></Suspense> },
  // Référence interne du design system (sans auth ni layout : page autonome).
  { path: '/ui', element: <Suspense fallback={<Fallback />}><UIShowcase /></Suspense> },
  // XSAL17 — réservation de visite publique (sans login, sans layout ERP).
  { path: '/rdv/:token', element: <Suspense fallback={<Fallback />}><PublicBookingPage /></Suspense> },
  // XCTR14 — portail client public « Mes contrats » (sans login, sans layout ERP).
  { path: '/portail-contrats/:token', element: <Suspense fallback={<Fallback />}><PortailContratsPage /></Suspense> },
  // XGED1 — cérémonie de signature publique (mono-signataire), sans login.
  { path: '/ged/signature/:token', element: <Suspense fallback={<Fallback />}><PublicSignaturePage mode="signature" /></Suspense> },
  // XGED2 — cérémonie de signature publique d'un destinataire (multi-signataires).
  { path: '/ged/signataire/:token', element: <Suspense fallback={<Fallback />}><PublicSignaturePage mode="signataire" /></Suspense> },
  // XGED7 — dépôt public de fichier (upload-request), sans login.
  { path: '/ged/depot/:token', element: <Suspense fallback={<Fallback />}><PublicDepotPage /></Suspense> },
  // XRH10 — kiosque de pointage (jeton de device en localStorage, sans session).
  { path: '/kiosque', element: <Suspense fallback={<Fallback />}><KiosquePointage /></Suspense> },
  // XSAV19 — « Signaler un problème » via QR équipement (sans login, sans layout ERP).
  { path: '/e/:token', element: <Suspense fallback={<Fallback />}><EquipementSignalerPage /></Suspense> },
  // XSAV10/FG86 — suivi client d'un ticket SAV + CSAT (sans login, sans layout ERP).
  { path: '/suivi/:token', element: <Suspense fallback={<Fallback />}><TicketSuiviPage /></Suspense> },
  // XPLT10 — kiosque TV plein écran des dashboards partagés (authentifié,
  // sans layout ERP — rotation/rafraîchissement pilotés côté écran).
  { path: '/dashboards-tv', loader: authLoader, element: <Suspense fallback={<Fallback />}><DashboardsTvPage /></Suspense> },
  // XKB19 — consultation publique d'un article KB partagé (sans login, sans layout ERP).
  { path: '/kb/public/:token', element: <Suspense fallback={<Fallback />}><PublicArticlePage /></Suspense> },

  { path: '/dashboard', loader: authLoader, element: <WithLayout><Dashboard /></WithLayout> },
  { path: '/messages', loader: authLoader, element: <WithLayout><ChatPage /></WithLayout> },

  // Stock — migré vers frontend/src/features/stock/module.config.jsx (ARC48).

  // CRM
  { path: '/crm', loader: authLoader, element: <WithLayout><ClientList /></WithLayout> },
  { path: '/crm/leads', loader: authLoader, element: <WithLayout><LeadsPage /></WithLayout> },
  { path: '/activites', loader: authLoader, element: <WithLayout><MesActivitesPage /></WithLayout> },
  { path: '/calendrier', loader: authLoader, element: <WithLayout><CalendarPage /></WithLayout> },
  { path: '/carte', loader: authLoader, element: <WithLayout><CartePage /></WithLayout> },
  { path: '/crm/parrainage', loader: authLoader, element: <WithLayout><ParrainagePage /></WithLayout> },

  // Ventes
  { path: '/ventes/devis', loader: authLoader, element: <WithLayout><DevisList /></WithLayout> },
  { path: '/ventes/devis/nouveau', loader: authLoader, element: <WithLayout><DevisGenerator /></WithLayout> },
  // QG12 — Design 3D d'un devis en LECTURE SEULE, plein écran, ouvrable dans une fenêtre.
  { path: '/ventes/devis/:id/3d', loader: authLoader, errorElement: <RouteErrorBoundary />, element: <WithLayout><RoofViewerPage /></WithLayout> },
  // Conception 3D de la toiture (héberge le builder roofPro11 du site, en ERP).
  { path: '/devis-design/:id', loader: authLoader, errorElement: <RouteErrorBoundary />, element: <WithLayout><ToitureDesign /></WithLayout> },
  { path: '/ventes/bons-commande', loader: authLoader, element: <WithLayout><VentesKanban /></WithLayout> },
  { path: '/ventes/factures', loader: authLoader, element: <WithLayout><FactureList /></WithLayout> },
  { path: '/ventes/avoirs', loader: authLoader, element: <WithLayout><AvoirsPage /></WithLayout> },
  { path: '/ventes/relances', loader: authLoader, element: <WithLayout><RelancesPage /></WithLayout> },
  { path: '/ventes/paiements', loader: authLoader, element: <WithLayout><PaiementsPage /></WithLayout> },
  // XSAL1-2 — administration des listes de prix clients (écriture Responsable/Admin, gardée serveur).
  { path: '/ventes/listes-prix', loader: authLoader, element: <WithLayout><ListesPrixPage /></WithLayout> },

  // Chantiers / Installations
  { path: '/chantiers', loader: authLoader, element: <WithLayout><InstallationsPage /></WithLayout> },
  { path: '/chantiers/demandes-achat', loader: authLoader, element: <WithLayout><DemandesAchatList /></WithLayout> },
  { path: '/interventions', loader: authLoader, element: <WithLayout><InterventionsPage /></WithLayout> },
  { path: '/planification', loader: authLoader, element: <WithLayout><PlanificationPage /></WithLayout> },
  { path: '/ma-journee', loader: authLoader, element: <WithLayout><MaJourneePage /></WithLayout> },
  { path: '/parc', loader: authLoader, element: <WithLayout><ParcInstallePage /></WithLayout> },
  { path: '/atelier', loader: authLoader, element: <WithLayout><AteliersPage /></WithLayout> },
  { path: '/production', loader: authLoader, element: <WithLayout><ProductionPage /></WithLayout> },
  { path: '/production/parc', loader: authLoader, element: <WithLayout><FleetPage /></WithLayout> },
  { path: '/production/analytique', loader: authLoader, element: <WithLayout><OmAnalyticsPage /></WithLayout> },
  { path: '/production/garanties', loader: authLoader, element: <WithLayout><WarrantiesPage /></WithLayout> },
  { path: '/production/co2', loader: authLoader, element: <WithLayout><Co2Page /></WithLayout> },
  { path: '/production/nettoyages', loader: authLoader, element: <WithLayout><CleaningsPage /></WithLayout> },
  { path: '/production/rapports', loader: authLoader, element: <WithLayout><OmReportPage /></WithLayout> },
  { path: '/production/portail-client', loader: authLoader, element: <WithLayout><ClientPortalPage /></WithLayout> },
  { path: '/outillage', loader: authLoader, element: <WithLayout><OutillagePage /></WithLayout> },

  // GED — gestion documentaire (navigateur arborescent)
  { path: '/ged', loader: authLoader, element: <WithLayout><DocumentsPage /></WithLayout> },

  // Après-vente : parc d'équipements & tickets SAV
  { path: '/equipements', loader: authLoader, element: <WithLayout><EquipementsPage /></WithLayout> },
  { path: '/sav', loader: authLoader, element: <WithLayout><TicketsPage /></WithLayout> },
  { path: '/sav/contrats', loader: authLoader, element: <WithLayout><ContratsMaintenance /></WithLayout> },
  // FG83 — réclamations garantie fournisseur (flux RMA).
  { path: '/sav/warranty-claims', loader: authLoader, element: <WithLayout><WarrantyClaimsPage /></WithLayout> },
  // ZSAV2/ZMFG1/ZMFG2/XSAV14/XSAV23 — référentiels SAV (responsable/admin, écriture gardée côté serveur).
  { path: '/sav/parametres', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><SavParametresPage /></WithLayout> },
  // XSAV8 — rapport de conformité SLA + KPI avancés.
  { path: '/sav/sla-rapport', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><SavSlaReportPage /></WithLayout> },
  // Alarmes onduleur (FG280).
  { path: '/sav/alarmes', loader: authLoader, element: <WithLayout><SavAlarmesPage /></WithLayout> },
  // ZSAV6 — file d'action (tickets ouverts groupés par action attendue).
  { path: '/sav/action-requise', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><SavActionBoardPage /></WithLayout> },
  // FG87 — base de connaissances SAV (articles KB).
  { path: '/sav/kb', loader: authLoader, element: <WithLayout><KbArticlesPage /></WithLayout> },

  // IA
  { path: '/ia/agent', loader: authLoader, element: <WithLayout><AgentChat /></WithLayout> },
  { path: '/ia/actions', loader: authLoader, element: <WithLayout><AgentActions /></WithLayout> },
  { path: '/ia/ocr', loader: authLoader, element: <WithLayout><OcrUpload /></WithLayout> },

  // Reporting
  { path: '/reporting', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><Reporting /></WithLayout> },
  { path: '/rapports', loader: authLoader, element: <WithLayout><Rapports /></WithLayout> },
  { path: '/reporting/balance-agee', loader: authLoader, element: <WithLayout><BalanceAgeePage /></WithLayout> },
  { path: '/reporting/commercial', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><CommercialDashboard /></WithLayout> },
  { path: '/reporting/cohortes', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><CohortsPage /></WithLayout> },
  { path: '/reporting/dashboards', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><DashboardConfigPage /></WithLayout> },
  // XPLT10 — partage de dashboard (liens publics tokenisés).
  { path: '/reporting/dashboards/partage', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><DashboardSharePage /></WithLayout> },
  { path: '/reporting/archive/client/:id', loader: authLoader, element: <WithLayout><ArchiveClientPage /></WithLayout> },
  { path: '/reporting/archive/chantier/:id', loader: authLoader, element: <WithLayout><ArchiveChantierPage /></WithLayout> },
  // XKB1/ZCTR7-9 — boîte d'approbations centralisée (toutes sources), accessible
  // à tout rôle (chacun peut avoir des demandes en attente sur son périmètre).
  { path: '/approbations', loader: authLoader, element: <WithLayout><ApprobationsPage /></WithLayout> },
  // XPLT22 — classeur léger embarqué (mini-spreadsheet BI, données live).
  { path: '/reporting/classeurs', loader: authLoader, element: <WithLayout><ClasseursListPage /></WithLayout> },
  { path: '/reporting/classeurs/:id', loader: authLoader, element: <WithLayout><ClasseurPage /></WithLayout> },
  // XSAV8 — conformité SLA + KPI SAV avancés (responsable/admin).
  { path: '/reporting/sav-sla', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><SavSlaPage /></WithLayout> },
  // XFSM16 — analytics field service consolidés (responsable/admin).
  { path: '/reporting/field-service', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><FieldServiceReportPage /></WithLayout> },
  // XFSM17 — scorecard coaching par technicien (responsable/admin uniquement,
  // jamais visible du technicien lui-même — cf. permission backend).
  { path: '/reporting/scorecard-technicien', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><TechnicienScorecardPage /></WithLayout> },

  // Administration
  { path: '/admin/users', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><UsersManagement /></WithLayout> },
  { path: '/admin/roles', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><RolesManagement /></WithLayout> },
  // SCA22 — console fondateur des tenants (le serveur exige superuser : 403 sinon).
  { path: '/admin/tenants', loader: roleLoader(['admin']), element: <WithLayout><TenantsConsole /></WithLayout> },
  { path: '/parametres', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><ParametresEntreprise /></WithLayout> },
  { path: '/parametres/export', loader: authLoader, element: <WithLayout><ExportSauvegarde /></WithLayout> },
  { path: '/parametres/notifications', loader: authLoader, element: <WithLayout><NotificationsPreferences /></WithLayout> },
  // XPLT6 — CRUD des alertes de seuil sur KPI agrégés (réservé responsable/admin,
  // reflète `IsResponsableOrAdmin` côté backend).
  { path: '/parametres/alertes-kpi', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><KpiAlertesPage /></WithLayout> },
  { path: '/journal', loader: roleLoader(['normal', 'responsable', 'admin'], 'journal_activite_voir'), element: <WithLayout><Journal /></WithLayout> },

  // UX1 — Routes des modules « coquille » enregistrées via le registre. Chaque
  // route est gatée par le même authLoader/roleLoader que le reste de l'app.
  ...buildModuleRoutes({ WithLayout, authLoader, roleLoader }),

  // Catch-all
  { path: '*', element: <Navigate to="/dashboard" replace /> },
])

export default router

