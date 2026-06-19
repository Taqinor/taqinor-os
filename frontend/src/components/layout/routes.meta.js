// Métadonnées de routes partagées par la coquille (Header, fil d'Ariane,
// barre d'onglets mobile). Source unique des titres FR pour CHAQUE route — le
// header et le fil d'Ariane en dérivent, plus aucun titre anglais périmé.
//
// `PAGE_TITLES` est ordonné du plus spécifique au plus général : on prend la
// PREMIÈRE clé dont `pathname` commence par elle (les sous-routes d'abord).

export const PAGE_TITLES = [
  ['/dashboard', 'Tableau de bord'],

  // Stock
  ['/stock/bons-commande-fournisseur', 'Bons de commande fournisseur'],
  ['/stock/ocr-import', 'Import OCR'],
  ['/stock/mouvements', 'Mouvements de stock'],
  ['/stock', 'Stock'],

  // CRM
  ['/crm/leads', 'Leads'],
  ['/crm/parrainage', 'Parrainage'],
  ['/crm', 'Clients'],
  ['/activites', 'Mes activités'],
  ['/calendrier', 'Calendrier'],

  // Ventes
  ['/ventes/devis/nouveau', 'Nouveau devis solaire'],
  ['/ventes/devis', 'Devis'],
  ['/ventes/bons-commande', 'Bons de commande'],
  ['/ventes/factures', 'Factures'],
  ['/ventes/avoirs', 'Avoirs'],
  ['/ventes/relances', 'Relances / Impayés'],

  // Chantiers
  ['/chantiers', 'Chantiers'],
  ['/interventions', 'Interventions'],
  ['/parc', 'Parc installé'],
  ['/production', 'Production'],

  // Après-vente
  ['/sav/contrats', 'Contrats de maintenance'],
  ['/sav', 'SAV'],
  ['/equipements', 'Équipements'],

  // Intelligence
  ['/ia/ocr', 'Traitement OCR'],
  ['/ia/agent', 'Agent IA conversationnel'],

  // Analyse
  ['/reporting/balance-agee', 'Balance âgée'],
  ['/reporting/archive/client', 'Archive client'],
  ['/reporting/archive/chantier', 'Archive chantier'],
  ['/reporting', 'Reporting & analytics'],
  ['/rapports', 'Rapports'],

  // Administration
  ['/admin/users', 'Utilisateurs'],
  ['/admin/roles', 'Rôles'],
  ['/parametres', 'Paramètres'],
]

// Libellé de la section parente (premier segment) pour le fil d'Ariane.
export const SECTION_LABELS = {
  stock: 'Stock',
  crm: 'CRM',
  ventes: 'Ventes',
  chantiers: 'Chantiers',
  parc: 'Chantiers',
  production: 'Chantiers',
  equipements: 'Après-vente',
  sav: 'Après-vente',
  ia: 'Intelligence',
  reporting: 'Analyse',
  rapports: 'Analyse',
  admin: 'Administration',
  parametres: 'Administration',
  activites: 'CRM',
  calendrier: 'CRM',
  dashboard: 'Tableau de bord',
}

// Titre de page : première entrée dont le pathname commence par la clé.
export function titleFor(pathname) {
  const hit = PAGE_TITLES.find(([path]) => pathname.startsWith(path))
  return hit ? hit[1] : 'ERP Agentique'
}

// Fil d'Ariane dérivé du chemin : [{ label, to }] du plus général au courant.
// On ne navigue jamais vers un segment intermédiaire inexistant : seul le
// dernier élément (la page courante) porte le titre complet ; les parents
// servent de contexte (libellé de section), sans lien si la route n'existe pas.
export function breadcrumbsFor(pathname) {
  const title = titleFor(pathname)
  const seg = pathname.split('/').filter(Boolean)[0]
  const section = seg ? SECTION_LABELS[seg] : null
  const crumbs = []
  // La section n'est affichée que si elle diffère du titre de la page (évite
  // « Tableau de bord › Tableau de bord »).
  if (section && section !== title) crumbs.push({ label: section, to: null })
  crumbs.push({ label: title, to: pathname, current: true })
  return crumbs
}
