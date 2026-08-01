// Métadonnées de routes partagées par la coquille (Header, fil d'Ariane,
// barre d'onglets mobile). Source unique des titres FR pour CHAQUE route — le
// header et le fil d'Ariane en dérivent, plus aucun titre anglais périmé.
//
// `PAGE_TITLES` est ordonné du plus spécifique au plus général : on prend la
// PREMIÈRE clé dont `pathname` commence par elle (les sous-routes d'abord).

// UX1 — Titres/libellés des modules « coquille », fournis par chaque
// `features/<module>/module.config.jsx` (aucun couplage ici).
import { moduleTitles, moduleSectionLabels } from '../../router/moduleRoutes'

const BASE_PAGE_TITLES = [
  ['/dashboard', 'Tableau de bord'],

  // Stock
  ['/stock/modeles-bcf', 'Modèles de bon de commande'],
  ['/stock/bons-commande-fournisseur', 'Bons de commande fournisseur'],
  ['/stock/receptions-fournisseur', 'Réceptions fournisseur'],
  ['/stock/factures-fournisseur', 'Factures fournisseur'],
  ['/stock/retours-fournisseur', 'Retours fournisseur'],
  ['/stock/fournisseurs', 'Fournisseurs'],
  ['/stock/categories', 'Catégories & marques'],
  ['/stock/ocr-import', 'Import OCR'],
  ['/stock/mouvements', 'Mouvements de stock'],
  // WIR109 — inventaire/stock avancé.
  ['/stock/lots-entrepot', 'Lots en entrepôt (FEFO)'],
  ['/stock/inventaires-annuels', 'Inventaires annuels'],
  ['/stock/revalorisations', 'Revalorisations de stock'],
  ['/stock/conditionnements', 'Conditionnements produit'],
  ['/stock', 'Stock'],

  // CRM
  // ODY5 — `/crm/cockpit` (ODY15) et `/crm/forecast` n'avaient AUCUN titre
  // déclaré nulle part : ils héritaient donc du préfixe générique `/crm` et
  // s'intitulaient « Clients » en en-tête. Les déclarer ici les rend visibles
  // au `titleFor` le plus spécifique (cf. sa note sur le plus long préfixe).
  ['/crm/cockpit', 'Cockpit CRM'],
  ['/crm/forecast', 'Forecast'],
  ['/crm/leads', 'Leads'],
  ['/crm/parrainage', 'Parrainage'],
  ['/crm/profils-site', 'Profils site'],
  ['/crm', 'Clients'],
  ['/activites', 'Mes activités'],
  ['/calendrier', 'Calendrier'],

  // Ventes
  ['/ventes/devis/nouveau', 'Nouveau devis solaire'],
  ['/ventes/devis', 'Devis'],
  ['/ventes/bons-commande', 'Bons de commande'],
  ['/ventes/factures', 'Factures'],
  ['/ventes/avoirs', 'Avoirs'],
  ['/ventes/paiements', 'Encaissements'],
  ['/ventes/relances', 'Relances / Impayés'],
  ['/ventes/listes-prix', 'Listes de prix'],
  ['/ventes/dossiers-reglementaires', 'Dossiers réglementaires'],

  // Chantiers
  ['/chantiers/approvisionnement', 'Approvisionnement avancé'],
  ['/chantiers', 'Chantiers'],
  ['/ma-journee', 'Ma journée'],
  ['/interventions', 'Interventions'],
  ['/planification/astreintes', 'Astreintes & indisponibilités'],
  ['/planification/suivi-gps', 'Suivi GPS terrain'],
  ['/parc', 'Parc installé'],
  ['/production', 'Production'],

  // Après-vente
  // ODY5 — même correctif qu'au CRM ci-dessus : `/sav/cockpit` (ODY19) était
  // titré « SAV » par héritage du préfixe générique.
  ['/sav/cockpit', 'Cockpit SAV'],
  ['/sav/contrats', 'Contrats de maintenance'],
  ['/sav', 'SAV'],
  ['/equipements', 'Équipements'],

  // Intelligence
  ['/ia/ocr', 'Traitement OCR'],
  ['/ia/agent', 'Agent IA conversationnel'],

  // Analyse
  ['/reporting/balance-agee', 'Balance âgée'],
  ['/reporting/quote-to-cash', 'Quote-to-Cash'],
  ['/reporting/archive/client', 'Archive client'],
  ['/reporting/archive/chantier', 'Archive chantier'],
  ['/reporting/dashboards/partage', 'Partage de dashboards'],
  ['/reporting/classeurs', 'Classeur'],
  ['/reporting/sav-sla', 'SLA SAV'],
  ['/reporting/field-service', 'Analytics terrain'],
  ['/reporting/scorecard-technicien', 'Scorecard technicien'],
  ['/reporting', 'Reporting & analytics'],
  ['/rapports', 'Rapports'],
  ['/approbations', 'Approbations'],
  ['/dashboards-tv', 'Dashboards TV'],

  // Administration
  ['/admin/users', 'Utilisateurs'],
  ['/admin/roles', 'Rôles'],
  ['/admin/securite-identite', 'Sécurité & Identité'],
  ['/admin/gouvernance-acces', 'Gouvernance des accès'],
  ['/parametres/notifications', 'Préférences de notifications'],
  ['/parametres/alertes-kpi', 'Alertes KPI'],
  ['/parametres', 'Paramètres'],
]

// Les titres des modules (préfixes distincts, ex. `/comptabilite`) sont ajoutés
// APRÈS les titres de base : `titleFor` prend la première correspondance, et les
// modules ordonnent déjà leurs propres titres du plus spécifique au plus général.
export const PAGE_TITLES = [...BASE_PAGE_TITLES, ...moduleTitles]

// N93 — clé i18n par chemin de base : quand un traducteur est fourni à
// `titleFor`, on préfère la valeur traduite ; sinon on retombe sur le libellé FR
// défini ci-dessus (comportement inchangé pour locale=fr et pour les modules,
// qui n'ont pas encore de clés dédiées).
const TITLE_KEYS = {
  '/dashboard': 'title.dashboard',
  '/stock/modeles-bcf': 'title.stock.modeles_bcf',
  '/stock/bons-commande-fournisseur': 'title.stock.bons_commande_fournisseur',
  '/stock/receptions-fournisseur': 'title.stock.receptions_fournisseur',
  '/stock/factures-fournisseur': 'title.stock.factures_fournisseur',
  '/stock/retours-fournisseur': 'title.stock.retours_fournisseur',
  '/stock/fournisseurs': 'title.stock.fournisseurs',
  '/stock/categories': 'title.stock.categories',
  '/stock/ocr-import': 'title.stock.ocr_import',
  '/stock/mouvements': 'title.stock.mouvements',
  '/stock': 'title.stock',
  '/crm/leads': 'title.crm.leads',
  '/crm/parrainage': 'title.crm.parrainage',
  '/crm/profils-site': 'title.crm.profils_site',
  '/crm': 'title.crm',
  '/activites': 'title.activites',
  '/calendrier': 'title.calendrier',
  '/ventes/devis/nouveau': 'title.ventes.devis_nouveau',
  '/ventes/devis': 'title.ventes.devis',
  '/ventes/bons-commande': 'title.ventes.bons_commande',
  '/ventes/factures': 'title.ventes.factures',
  '/ventes/avoirs': 'title.ventes.avoirs',
  '/ventes/paiements': 'title.ventes.paiements',
  '/ventes/relances': 'title.ventes.relances',
  '/ventes/listes-prix': 'title.ventes.listes_prix',
  '/ventes/dossiers-reglementaires': 'title.ventes.dossiers_reglementaires',
  '/chantiers': 'title.chantiers',
  '/ma-journee': 'title.ma_journee',
  '/interventions': 'title.interventions',
  '/parc': 'title.parc',
  '/production': 'title.production',
  '/sav/contrats': 'title.sav.contrats',
  '/sav': 'title.sav',
  '/equipements': 'title.equipements',
  '/ia/ocr': 'title.ia.ocr',
  '/ia/agent': 'title.ia.agent',
  '/reporting/balance-agee': 'title.reporting.balance_agee',
  '/reporting/quote-to-cash': 'title.reporting.quote_to_cash',
  '/reporting/archive/client': 'title.reporting.archive_client',
  '/reporting/archive/chantier': 'title.reporting.archive_chantier',
  '/reporting/dashboards/partage': 'title.reporting.dashboards_partage',
  '/reporting/classeurs': 'title.reporting.classeurs',
  '/reporting/sav-sla': 'title.reporting.sav_sla',
  '/reporting/field-service': 'title.reporting.field_service',
  '/reporting/scorecard-technicien': 'title.reporting.scorecard_technicien',
  '/reporting': 'title.reporting',
  '/rapports': 'title.rapports',
  '/approbations': 'title.approbations',
  '/dashboards-tv': 'title.dashboards_tv',
  '/admin/users': 'title.admin.users',
  '/admin/roles': 'title.admin.roles',
  '/parametres/notifications': 'title.parametres.notifications',
  '/parametres/alertes-kpi': 'title.parametres.alertes_kpi',
  '/parametres': 'title.parametres',
}

// VX11 — Libellé de la section parente (premier segment) pour le fil d'Ariane,
// désormais `{ label, to }` : `to` pointe vers le cockpit du module quand il en
// a un (rend le 1er segment du breadcrumb CLIQUABLE, cf. Breadcrumbs.jsx qui
// sait déjà rendre un lien quand `to` est renseigné) ; `to: null` = repli
// inchangé (texte, non cliquable) pour les sections sans cockpit unique.
const BASE_SECTION_LABELS = {
  stock: { label: 'Stock', to: '/stock' },
  crm: { label: 'CRM', to: '/crm' },
  ventes: { label: 'Ventes', to: '/ventes/devis' },
  chantiers: { label: 'Chantiers', to: '/chantiers' },
  parc: { label: 'Chantiers', to: '/chantiers' },
  production: { label: 'Chantiers', to: '/chantiers' },
  equipements: { label: 'Après-vente', to: '/sav' },
  sav: { label: 'Après-vente', to: '/sav' },
  // ODY23 — le cockpit /ia (features/ia/module.config.jsx) existe désormais :
  // le 1er segment du fil d'Ariane devient cliquable, comme les autres apps.
  ia: { label: 'Intelligence', to: '/ia' },
  reporting: { label: 'Analyse', to: '/reporting' },
  rapports: { label: 'Analyse', to: '/reporting' },
  approbations: { label: 'Analyse', to: '/reporting' },
  'dashboards-tv': { label: 'Analyse', to: '/reporting' },
  admin: { label: 'Administration', to: '/parametres' },
  parametres: { label: 'Administration', to: '/parametres' },
  activites: { label: 'CRM', to: '/crm' },
  calendrier: { label: 'CRM', to: '/crm' },
  dashboard: { label: 'Tableau de bord', to: null },
}

// UX1 — libellés de section des modules « coquille » : chaque
// `module.config.jsx` déclare `sectionLabels: { <segment>: 'Libellé' }` (une
// CHAÎNE, pas encore `{label, to}` — on ne retouche pas ces 15+ fichiers pour
// cette tâche). Normalisé ici en `{ label, to: null }` : repli EXACT au
// comportement d'avant (texte de section, non cliquable) tant qu'un module ne
// migre pas vers la forme enrichie.
const NORMALIZED_MODULE_SECTION_LABELS = Object.fromEntries(
  Object.entries(moduleSectionLabels).map(([seg, value]) => [
    seg,
    typeof value === 'string' ? { label: value, to: null } : value,
  ]),
)

// Fusion : chaque segment est distinct (garanti par convention UX1), jamais de
// conflit entre base et modules.
export const SECTION_LABELS = {
  ...BASE_SECTION_LABELS,
  ...NORMALIZED_MODULE_SECTION_LABELS,
}

// Titre de page : entrée dont le préfixe est le PLUS SPÉCIFIQUE (le plus long)
// à correspondre au chemin.
// ODY5 — c'était auparavant la PREMIÈRE entrée correspondante, ce qui marchait
// tant que la liste restait triée du spécifique au général… mais faisait
// SILENCIEUSEMENT masquer par un préfixe générique toute sous-route déclarée
// APRÈS lui : un module ajoutant `['/crm/cockpit', 'Cockpit']` à ses `titles`
// (ajoutés à la fin de PAGE_TITLES) voyait son titre écrasé par le `['/crm',
// 'Clients']` de la liste de base — l'écran s'intitulait « Clients ». Même
// travers pour `/crm/forecast`. Le plus long préfixe gagne désormais ; à
// longueur ÉGALE la PREMIÈRE entrée l'emporte (précédence de la liste de base
// sur les modules, inchangée).
// N93 — `t` optionnel : si fourni ET qu'une clé i18n existe pour ce chemin, on
// renvoie la traduction ; sinon on garde le libellé FR (repli). Appelé sans `t`,
// le comportement est identique à avant (FR partout).
export function titleFor(pathname, t) {
  let hit = null
  for (const entry of PAGE_TITLES) {
    if (!pathname.startsWith(entry[0])) continue
    if (!hit || entry[0].length > hit[0].length) hit = entry
  }
  if (!hit) return t ? t('title.fallback') : 'ERP Agentique'
  if (t) {
    const key = TITLE_KEYS[hit[0]]
    // t() retombe déjà sur la clé si manquante ; on garde le libellé FR comme
    // repli plus lisible quand il n'y a pas de clé i18n (modules « coquille »).
    if (key) {
      const translated = t(key)
      if (translated && translated !== key) return translated
    }
  }
  return hit[1]
}

// Fil d'Ariane dérivé du chemin : [{ label, to }] du plus général au courant.
// VX11 — le premier segment est CLIQUABLE quand `SECTION_LABELS[seg].to` est
// renseigné (cockpit du module) ; `to: null` reste le repli inchangé (texte de
// contexte, non cliquable) pour les sections sans cockpit unique. On ne navigue
// jamais vers un segment intermédiaire inexistant : seul le dernier élément (la
// page courante) porte le titre complet et n'est jamais un lien (`current`).
// ODY5 — `app` OPTIONNEL : `{label, to}` de l'app active (immersion). Quand il
// est fourni, le 1er segment devient l'APP et pointe vers SON cockpit — le fil
// reste la HIÉRARCHIE lisible « app › section › fiche » (jamais la pile
// d'historique d'Odoo, dont les tickets #46616/#41891 documentent la confusion :
// un fil qui empile les écrans visités ne dit plus OÙ l'on est). Le libellé de
// section reste préféré quand il existe (« Ventes », « Après-vente » : plus
// lisible que le nom d'app en capitales) ; le nom d'app sert de repli pour les
// segments sans libellé déclaré. Appelée SANS `app`, la fonction est identique
// à avant (aucune régression pour ses appelants existants).
export function breadcrumbsFor(pathname, app) {
  const title = titleFor(pathname)
  const seg = pathname.split('/').filter(Boolean)[0]
  const section = seg ? SECTION_LABELS[seg] : null
  const label = section?.label ?? app?.label ?? null
  const target = app?.to ?? section?.to ?? null
  const crumbs = []
  // La section n'est affichée que si elle diffère du titre de la page (évite
  // « Tableau de bord › Tableau de bord »).
  if (label && label !== title) {
    // Ne jamais poser `to` == pathname courant (éviterait un lien vers soi-même
    // quand on est DÉJÀ sur le cockpit).
    const to = target && target !== pathname ? target : null
    crumbs.push({ label, to })
  }
  crumbs.push({ label: title, to: pathname, current: true })
  return crumbs
}
