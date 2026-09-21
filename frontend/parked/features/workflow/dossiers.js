/* ============================================================================
   NTWFL19/21/22 — logique pure de l'écran dossier transverse (testable sans
   React/DOM) : catalogues d'options, routage des objets liés, calcul de
   retard, tons visuels, filtre combiné.
   ========================================================================== */

// NTWFL17 — cartes cliquables vers l'objet réel : la cible n'est désignée que
// par `app_label.model` (`core` reste fondation, aucun import métier côté
// serveur) ; cette table est le SEUL endroit qui traduit une clé connue vers
// une route déjà existante de l'écran cible. Une clé absente reste affichée
// mais non cliquable (jamais un lien mort).
const ROUTE_PAR_CLE_MODELE = {
  'crm.lead': (id) => `/crm/leads/${id}`,
  'ventes.devis': (id) => `/ventes/devis?id=${id}`,
  'sav.ticket': (id) => `/sav?id=${id}`,
  'installations.installation': (id) => `/chantiers?id=${id}`,
}

/** `'crm.lead'` + `object_id` → route réelle, ou `null` si la cible n'a pas
 * (encore) de mapping connu — l'écran affiche alors le libellé SANS lien. */
export function routeForLien(cleModele, objectId) {
  const fabrique = ROUTE_PAR_CLE_MODELE[String(cleModele || '').toLowerCase()]
  return fabrique ? fabrique(objectId) : null
}

// source-choix: core.Dossier.type_dossier
// Catalogue FERMÉ (jamais une valeur inventée côté écran — le serializer
// renvoie déjà les libellés via `*_label`, ces catalogues ne servent
// qu'aux SÉLECTEURS de filtre/création).
export const TYPE_DOSSIER_OPTIONS = [
  { value: 'reclamation_complexe', label: 'Réclamation complexe' },
  { value: 'onboarding_grand_compte', label: 'Onboarding grand compte' },
  { value: 'litige', label: 'Litige' },
  { value: 'projet_transverse', label: 'Projet transverse' },
  { value: 'autre', label: 'Autre' },
]

export const STATUT_DOSSIER_OPTIONS = [
  { value: 'ouvert', label: 'Ouvert' },
  { value: 'en_cours', label: 'En cours' },
  { value: 'en_attente', label: 'En attente' },
  { value: 'clos', label: 'Clos' },
  { value: 'abandonne', label: 'Abandonné' },
]

export const PRIORITE_DOSSIER_OPTIONS = [
  { value: 'basse', label: 'Basse' },
  { value: 'normale', label: 'Normale' },
  { value: 'haute', label: 'Haute' },
  { value: 'critique', label: 'Critique' },
]

const STATUTS_FERMES = new Set(['clos', 'abandonne'])

const PRIORITE_TONE = {
  basse: 'neutral', normale: 'info', haute: 'warning', critique: 'danger',
}

/** Ton de badge pour une priorité — repli neutre sur une valeur inconnue. */
export function prioriteTone(priorite) {
  return PRIORITE_TONE[priorite] ?? 'neutral'
}

// NTWFL21 — badge « en retard » : échéance dépassée ET statut non terminal.
// `aujourdHui` est TOUJOURS passé par l'appelant (chaîne ISO `AAAA-MM-JJ`,
// comparable lexicographiquement à `dossier.echeance`) — jamais un `new
// Date()` lu en profondeur, pour rester déterministe et testable.
export function estEnRetard(dossier, aujourdHui) {
  if (!dossier?.echeance || STATUTS_FERMES.has(dossier?.statut)) return false
  return dossier.echeance < aujourdHui
}

// NTWFL22 — filtre combiné appliqué CÔTÉ ÉCRAN : le serveur ne filtre que
// `statut`/`type_dossier` (`DossierViewSet.get_queryset`) ; priorité et
// « en retard uniquement » se recoupent ici. `dossiers` doit être la liste
// COMPLÈTE (toutes les pages DRF, cf. `fetchTousLesDossiers` dans
// `DossierList.jsx`) — un appelant qui ne passerait qu'une page tronquée
// ferait remonter « Aucun dossier » à tort dès que le vrai résultat vit sur
// une page suivante. La recherche libre (propriétaire/titre) reste déléguée
// au `searchable` du `<DataTable>`, jamais dupliquée ici.
export function filtrerDossiers(dossiers, filtres, aujourdHui) {
  const liste = Array.isArray(dossiers) ? dossiers : []
  return liste.filter((d) => {
    if (filtres?.priorite && d.priorite !== filtres.priorite) return false
    if (filtres?.enRetardSeulement && !estEnRetard(d, aujourdHui)) return false
    return true
  })
}
