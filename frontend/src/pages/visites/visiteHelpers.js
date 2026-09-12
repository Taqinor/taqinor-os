// Groupe VT — helpers PURS partagés par les écrans de visite technique
// (wizard commercial VT5/VT6/VT7, revue bureau d'études VT8, calage VT11).
// Rien ici n'appelle l'API ni ne lit le DOM : testable directement (VT10).
//
// RÈGLE : la complétude/les manquants viennent TOUJOURS du serveur
// (`visite.completude`) — ce fichier ne fait que LIRE ces champs, jamais les
// redériver. Le schéma de formulaire ci-dessous (labels/unités) ne porte
// aucun chiffre métier : ce sont les clés déjà présentes dans le contrat
// `apps/crm/contract_samples/visite_terrain.json` (PACT10).

// Schéma d'affichage des mesures par catégorie — clé → {label, unite, type}.
// `type` pilote le rendu du champ : 'number' | 'text' | 'bool' | 'select'.
export const MESURES_SCHEMA = {
  toiture: [
    { key: 'longueur_m', label: 'Longueur de la zone utile', unite: 'm', type: 'number' },
    { key: 'largeur_m', label: 'Largeur de la zone utile', unite: 'm', type: 'number' },
    { key: 'toit_plat', label: 'Toit plat', unite: '', type: 'bool' },
    { key: 'pente_deg', label: 'Pente', unite: '°', type: 'number' },
    {
      key: 'orientation', label: 'Orientation', unite: '', type: 'select',
      options: [
        { value: 'nord', label: 'Nord' }, { value: 'nord-est', label: 'Nord-Est' },
        { value: 'est', label: 'Est' }, { value: 'sud-est', label: 'Sud-Est' },
        { value: 'sud', label: 'Sud' }, { value: 'sud-ouest', label: 'Sud-Ouest' },
        { value: 'ouest', label: 'Ouest' }, { value: 'nord-ouest', label: 'Nord-Ouest' },
      ],
    },
    { key: 'type_couverture', label: 'Type de couverture', unite: '', type: 'text' },
    { key: 'etat_couverture', label: 'État de la couverture', unite: '', type: 'text' },
    { key: 'obstacles_notes', label: 'Obstacles / ombrages (notes)', unite: '', type: 'text' },
  ],
  tableau: [
    { key: 'calibre_disjoncteur_a', label: 'Calibre du disjoncteur principal', unite: 'A', type: 'number' },
    {
      key: 'type_alimentation', label: 'Type d’alimentation', unite: '', type: 'select',
      options: [{ value: 'mono', label: 'Monophasé' }, { value: 'tri', label: 'Triphasé' }],
    },
    { key: 'emplacements_libres', label: 'Emplacements disjoncteurs libres', unite: '', type: 'number' },
  ],
  local_onduleur: [
    { key: 'largeur_mur_cm', label: 'Largeur du mur libre', unite: 'cm', type: 'number' },
    { key: 'hauteur_mur_cm', label: 'Hauteur du mur libre', unite: 'cm', type: 'number' },
    { key: 'profondeur_degagement_cm', label: 'Profondeur de dégagement', unite: 'cm', type: 'number' },
    { key: 'distance_tableau_m', label: 'Distance au tableau électrique', unite: 'm', type: 'number' },
    { key: 'local_abrite', label: 'Local abrité', unite: '', type: 'bool' },
    { key: 'local_ventile', label: 'Local ventilé', unite: '', type: 'bool' },
  ],
  cheminement: [
    { key: 'longueur_estimee_m', label: 'Longueur estimée du cheminement', unite: 'm', type: 'number' },
  ],
  general: [],
}

// Ordre d'affichage du wizard (toiture → tableau → local onduleur →
// cheminement [optionnel] → général) — SECOURS uniquement si le serveur ne
// renvoie pas déjà `checklist` dans cet ordre ; on trie sur cette clé mais on
// garde toute catégorie inconnue du serveur À LA FIN plutôt que de la perdre.
const ORDRE_CATEGORIES = ['toiture', 'tableau', 'local_onduleur', 'cheminement', 'general']

export function trierCategories(checklist) {
  if (!Array.isArray(checklist)) return []
  return [...checklist].sort((a, b) => {
    const ia = ORDRE_CATEGORIES.indexOf(a.categorie)
    const ib = ORDRE_CATEGORIES.indexOf(b.categorie)
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
  })
}

// Avancement de la partie PHOTOS, dérivé UNIQUEMENT de champs serveur
// (`slot.requis`, `slot.etat`) — jamais une règle de complétude réinventée ;
// la décision « complet » reste TOUJOURS `visite.completude.complet`.
export function progressionPhotos(checklist) {
  const slots = (checklist ?? []).flatMap((c) => c.slots ?? [])
  const requis = slots.filter((s) => s.requis)
  const ok = requis.filter((s) => s.etat === 'ok')
  return { done: ok.length, total: requis.length }
}

export function manquantsMesures(completude) {
  return (completude?.manquants ?? []).filter((m) => m.type === 'mesure')
}

export function manquantsPhotos(completude) {
  return (completude?.manquants ?? []).filter((m) => m.type === 'photo' || m.type === 'photo_a_refaire')
}

export const ETAT_SLOT_LABEL = {
  manquant: 'Manquant',
  ok: 'OK',
  a_refaire: 'À refaire',
}

export const ETAT_SLOT_TONE = {
  manquant: 'neutral',
  ok: 'success',
  a_refaire: 'warning',
}

export const STATUT_VISITE_LABEL = {
  brouillon: 'Brouillon',
  en_cours: 'En cours',
  terminee: 'Terminée — à revoir',
  validee: 'Validée',
  a_refaire: 'À refaire',
}

// wa.me — même normalisation que le reste de l'app (chiffres uniquement,
// indicatif compris) : ne construit JAMAIS d'URL sans numéro exploitable.
export function whatsappUrl(numero) {
  const digits = String(numero ?? '').replace(/[^\d]/g, '')
  return digits ? `https://wa.me/${digits}` : null
}

export function mapsUrl(lat, lng) {
  if (lat == null || lng == null) return null
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`
}
