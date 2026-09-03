/* SOL11 — MIROIR des `sku` et libellés FR déclarés par les manifestes backend.
   ----------------------------------------------------------------------------
   La SOURCE est `backend/django_core/apps/<x>/apps.py::module_manifest`
   (champs `sku` et `label`, SOL1). Ce fichier en est le miroir côté client,
   parce que la grille « Applications » doit être triée AU PREMIER RENDU, avant
   tout appel réseau : aller chercher `/api/django/core/modules/` ferait sauter
   l'ordre des tuiles sous les yeux de l'utilisateur à chaque ouverture.

   Ce qu'il apporte :
     • l'ORDRE produit — les modules `solar_core` (le métier d'un installateur)
       en tête, puis le socle `generic`, puis les `optional` ;
     • la SECTION « Extensions » — les modules `optional`, livrés mais éteints à
       la création d'un tenant (SOL8), à activer en un clic ;
     • l'ABSENCE des verticaux `vertical_*` — parqués hors de l'édition solaire
       (SOL6) ; en édition complète ils restent visibles, sauf plan de licence
       ou ModuleToggle contraire (SOL9/ODX6), ce qui est géré en amont.

   Une clé ABSENTE de cette table (module frontend sans manifeste backend, ex.
   `magasin`, `admin`, `workflow`) est traitée comme `generic` : elle garde sa
   place historique, jamais masquée par ce fichier. La garde
   `appSkus.test.jsx` vérifie que toute clé du registre est connue ou
   volontairement tolérée. */

export const SKU_SOLAR_CORE = 'solar_core'
export const SKU_GENERIC = 'generic'
export const SKU_OPTIONAL = 'optional'
export const PREFIXE_VERTICAL = 'vertical_'

/** Miroir des manifestes backend : { clé: { sku, libelle, installable } }. */
export const MANIFESTES = {
  accessreview: { sku: 'generic', libelle: 'Revue des accès', installable: false },
  achats: { sku: 'solar_core', libelle: 'Achats', installable: true },
  adminops: { sku: 'generic', libelle: 'Administration', installable: true },
  adsengine: { sku: 'generic', libelle: 'Publicité', installable: false },
  agent: { sku: 'generic', libelle: 'Agent', installable: true },
  agriculture: { sku: 'vertical_agriculture', libelle: 'Agriculture', installable: true },
  ai_governance: { sku: 'generic', libelle: 'Gouvernance IA', installable: true },
  ao: { sku: 'solar_core', libelle: 'Appels d\'offres', installable: true },
  assurances: { sku: 'generic', libelle: 'Assurances', installable: true },
  audit: { sku: 'generic', libelle: 'Journal d\'activité', installable: false },
  authentication: { sku: 'generic', libelle: 'Authentification', installable: false },
  automation: { sku: 'generic', libelle: 'Automatisations', installable: true },
  btp_chantier: { sku: 'solar_core', libelle: 'BTP Chantier', installable: true },
  chat: { sku: 'generic', libelle: 'Messagerie', installable: true },
  compta: { sku: 'generic', libelle: 'Comptabilité', installable: true },
  contacts: { sku: 'generic', libelle: 'Contacts multi-rôles', installable: true },
  contrats: { sku: 'generic', libelle: 'Contrats', installable: true },
  conversation_ai: { sku: 'generic', libelle: 'Conversations commerciales', installable: true },
  core: { sku: 'generic', libelle: 'Fondation', installable: false },
  cpq: { sku: 'solar_core', libelle: 'CPQ', installable: true },
  credit: { sku: 'generic', libelle: 'Crédit client', installable: true },
  crm: { sku: 'solar_core', libelle: 'CRM', installable: true },
  customfields: { sku: 'generic', libelle: 'Champs personnalisés', installable: false },
  dataimport: { sku: 'generic', libelle: 'Import / Export', installable: false },
  documents: { sku: 'generic', libelle: 'Documents après-vente', installable: true },
  douane: { sku: 'optional', libelle: 'Douane', installable: true },
  ecommerce_connect: { sku: 'vertical_ecommerce', libelle: 'Connecteur e-commerce', installable: true },
  education: { sku: 'vertical_education', libelle: 'Éducation', installable: true },
  einvoice: { sku: 'optional', libelle: 'E-invoicing DGI', installable: true },
  entites: { sku: 'generic', libelle: 'Entités', installable: true },
  esg: { sku: 'generic', libelle: 'ESG / RSE', installable: true },
  extensions: { sku: 'generic', libelle: 'Extensions', installable: true },
  facturation: { sku: 'solar_core', libelle: 'Facturation', installable: true },
  fiscal: { sku: 'optional', libelle: 'Conformité fiscale', installable: true },
  flotte: { sku: 'generic', libelle: 'Flotte', installable: true },
  fpa: { sku: 'generic', libelle: 'FP&A', installable: true },
  frais: { sku: 'generic', libelle: 'Notes de frais', installable: true },
  ged: { sku: 'generic', libelle: 'GED', installable: true },
  gestion_projet: { sku: 'solar_core', libelle: 'Gestion de projet', installable: true },
  hospitality: { sku: 'vertical_hospitality', libelle: 'Hôtellerie', installable: true },
  identity: { sku: 'generic', libelle: 'Identité & accès', installable: false },
  immobilier: { sku: 'vertical_immobilier', libelle: 'Immobilier', installable: true },
  innovation: { sku: 'generic', libelle: 'Innovation', installable: true },
  installations: { sku: 'solar_core', libelle: 'Chantiers', installable: true },
  kb: { sku: 'generic', libelle: 'Base de connaissances', installable: true },
  litiges: { sku: 'generic', libelle: 'Réclamations & litiges', installable: true },
  marketing: { sku: 'generic', libelle: 'Marketing', installable: true },
  migration: { sku: 'generic', libelle: 'Migration', installable: true },
  monitoring: { sku: 'solar_core', libelle: 'Supervision', installable: true },
  mrp: { sku: 'vertical_manufacturing', libelle: 'Production (MRP)', installable: true },
  notifications: { sku: 'generic', libelle: 'Notifications', installable: true },
  offlinesync: { sku: 'generic', libelle: 'Synchronisation hors-ligne', installable: false },
  onboarding: { sku: 'generic', libelle: 'Onboarding produit', installable: true },
  outillage: { sku: 'solar_core', libelle: 'Outillage', installable: true },
  paie: { sku: 'optional', libelle: 'Paie', installable: true },
  parametres: { sku: 'generic', libelle: 'Paramètres', installable: false },
  portail: { sku: 'generic', libelle: 'Portail client', installable: true },
  pos: { sku: 'optional', libelle: 'Vente comptoir', installable: true },
  promotions: { sku: 'optional', libelle: 'Promotions', installable: true },
  publicapi: { sku: 'generic', libelle: 'API publique', installable: false },
  qhse: { sku: 'generic', libelle: 'QHSE', installable: true },
  records: { sku: 'generic', libelle: 'Activités & pièces jointes', installable: false },
  reporting: { sku: 'generic', libelle: 'Rapports', installable: true },
  rh: { sku: 'generic', libelle: 'Ressources humaines', installable: true },
  roles: { sku: 'generic', libelle: 'Rôles & permissions', installable: false },
  sante: { sku: 'vertical_sante', libelle: 'Santé', installable: true },
  sav: { sku: 'solar_core', libelle: 'Après-vente', installable: true },
  scm: { sku: 'optional', libelle: 'Planification supply chain', installable: true },
  stock: { sku: 'solar_core', libelle: 'Stock', installable: true },
  territoires: { sku: 'generic', libelle: 'Territoires commerciaux', installable: true },
  tiers: { sku: 'generic', libelle: 'Tiers', installable: true },
  transport: { sku: 'optional', libelle: 'Transport', installable: true },
  trash: { sku: 'generic', libelle: 'Corbeille', installable: false },
  uxviews: { sku: 'generic', libelle: 'Vues UX', installable: false },
  veille_ao: { sku: 'solar_core', libelle: 'Veille appels d\'offres', installable: true },
  ventes: { sku: 'solar_core', libelle: 'Ventes', installable: true },
  voip: { sku: 'generic', libelle: 'Téléphonie', installable: true },
}

/* Rang de tri d'un sku : plus petit = plus haut dans la grille.
   Les verticaux ne sont pas classés — ils sont filtrés en amont. */
const RANGS = {
  [SKU_SOLAR_CORE]: 0,
  [SKU_GENERIC]: 1,
  [SKU_OPTIONAL]: 2,
}

/** sku d'un module (défaut `generic` pour une clé sans manifeste backend). */
export function skuDe(key) {
  return MANIFESTES[key]?.sku ?? SKU_GENERIC
}

/** Libellé FR court du manifeste, ou `null` si la clé n'en a pas. */
export function libelleManifeste(key) {
  return MANIFESTES[key]?.libelle ?? null
}

export function estVertical(key) {
  return skuDe(key).startsWith(PREFIXE_VERTICAL)
}

export function estOptionnel(key) {
  return skuDe(key) === SKU_OPTIONAL
}

export function estSolarCore(key) {
  return skuDe(key) === SKU_SOLAR_CORE
}

/** Rang de tri d'une clé de module (un vertical est mis en toute fin). */
export function rangDe(key) {
  return RANGS[skuDe(key)] ?? 3
}
