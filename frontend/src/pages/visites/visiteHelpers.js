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

// VTA9 — lien de navigation NATIF du téléphone (`geo:`) : Android ouvre le
// sélecteur d'applis de navigation (Maps, Waze, OsmAnd…) au lieu d'imposer un
// site web. Sans coordonnées exploitables → null (l'écran n'affiche alors
// aucun lien, il n'en invente pas un sur l'adresse textuelle).
export function geoUrl(lat, lng, libelle) {
  if (lat == null || lng == null) return null
  const q = libelle ? `?q=${lat},${lng}(${encodeURIComponent(libelle)})` : ''
  return `geo:${lat},${lng}${q}`
}

// VTA9 — heure courte d'un horodatage SERVEUR (`en_route_le`/`arrivee_le`).
// L'écran n'horodate JAMAIS localement : il réaffiche ce que le serveur a
// écrit. Valeur absente/illisible → chaîne vide (aucune heure inventée).
export function heureServeur(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

// VISITE-QUALIF — schéma des 6 questions à un tap de la « Qualification
// client » (fin de visite terrain). Chaque question porte un DÉFAUT
// (`defaut`) TOUJOURS pré-sélectionné à l'écran (rapide, mains gantées) — les
// clés/valeurs sont EXACTEMENT celles du contrat serveur
// `POST .../qualification/` (jamais de valeur inventée ici). `devis_details`
// (texte, requis seulement si `devis` ≠ 'convient') et `conseil_closing`
// (texte libre optionnel) ne sont pas des questions à choix — elles sont
// gérées à part par le formulaire.
export const QUALIFICATION_SCHEMA = [
  {
    key: 'temperature',
    question: 'Le client est…',
    defaut: 'tiede',
    options: [
      { value: 'chaud', label: 'Chaud — prêt à signer' },
      { value: 'tiede', label: 'Tiède' },
      { value: 'froid', label: 'Froid' },
    ],
  },
  {
    key: 'devis',
    question: 'Le devis ?',
    defaut: 'convient',
    options: [
      { value: 'convient', label: 'Le devis convient' },
      { value: 'a_modifier', label: 'À modifier' },
      { value: 'nouveau', label: 'Veut un nouveau devis' },
    ],
  },
  {
    key: 'decideur',
    question: 'Qui décide ?',
    defaut: 'seul',
    options: [
      { value: 'seul', label: 'Seul' },
      { value: 'conjoint_famille', label: 'Avec conjoint / famille' },
      { value: 'associe_direction', label: 'Avec associé / direction' },
    ],
  },
  {
    key: 'frein',
    question: 'Frein principal',
    defaut: 'aucun',
    options: [
      { value: 'aucun', label: 'Aucun' },
      { value: 'prix', label: 'Prix' },
      { value: 'compare', label: 'Compare d’autres devis' },
      { value: 'timing', label: 'Timing' },
      { value: 'technique', label: 'Technique' },
      { value: 'confiance', label: 'Confiance' },
    ],
  },
  {
    key: 'declencheur',
    question: 'Ce qui l’a le plus accroché',
    defaut: 'economies',
    options: [
      { value: 'economies', label: 'Les économies' },
      { value: 'coupures', label: 'Les coupures / autonomie' },
      { value: 'ecologie', label: 'L’écologie' },
      { value: 'technologie', label: 'La technologie' },
    ],
  },
  {
    key: 'rappel',
    question: 'Quand rappeler ?',
    defaut: 'demain_matin',
    aide: 'Le rappel de closing se calera dessus.',
    options: [
      { value: 'demain_matin', label: 'Demain matin' },
      { value: 'demain_soir', label: 'Demain soir' },
      { value: 'cette_semaine', label: 'Cette semaine' },
    ],
  },
]

// Valeurs par défaut {champ: valeur} dérivées du schéma ci-dessus — jamais
// dupliquées à la main ailleurs.
export const QUALIFICATION_DEFAULTS = Object.fromEntries(
  QUALIFICATION_SCHEMA.map((q) => [q.key, q.defaut]),
)

// Libellé FR d'une valeur de qualification — jamais la valeur brute affichée
// si un libellé existe ; repli sur la valeur brute pour ne rien avaler si le
// serveur renvoie un jour une valeur hors schéma.
export function labelQualification(champ, valeur) {
  const q = QUALIFICATION_SCHEMA.find((s) => s.key === champ)
  const opt = q?.options.find((o) => o.value === valeur)
  return opt?.label ?? valeur ?? '—'
}

// Ligne compacte lecture seule (revue bureau d'études) : les 6 libellés
// choisis, séparés par « · ». Chaîne vide si aucune qualification enregistrée
// — l'écran décide alors seul du texte de repli, jamais recalculé ici.
export function ligneQualification(qualification) {
  if (!qualification) return ''
  return QUALIFICATION_SCHEMA
    .map((q) => labelQualification(q.key, qualification[q.key]))
    .join(' · ')
}
