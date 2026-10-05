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
    // ERR-QAH-VISITES-COUVERTURE-ENUM-SANS-AFFORDANCE — ces deux champs
    // n'acceptaient QUE les codes serveur (`apps/visites/visite_checklist.py`)
    // tout en s'affichant comme des textes libres sans liste ni placeholder :
    // un technicien qui tapait « Tuile »/« Bon état » recevait un 400 sans
    // jamais voir les valeurs permises. Même patron que « Orientation »
    // ci-dessus — les `value` sont les codes EXACTS du serveur (le backend
    // normalise en plus la casse/les accents/« état », donc une vieille
    // réponse hors-liste reste acceptée si elle matche).
    {
      key: 'type_couverture', label: 'Type de couverture', unite: '', type: 'select',
      options: [
        { value: 'tuile', label: 'Tuile' }, { value: 'tole', label: 'Tôle' },
        { value: 'bac_acier', label: 'Bac acier' }, { value: 'beton', label: 'Béton' },
        { value: 'fibrociment', label: 'Fibrociment' }, { value: 'autre', label: 'Autre' },
      ],
    },
    {
      key: 'etat_couverture', label: 'État de la couverture', unite: '', type: 'select',
      options: [
        { value: 'bon', label: 'Bon' }, { value: 'moyen', label: 'Moyen' },
        { value: 'mauvais', label: 'Mauvais' },
      ],
    },
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
  // AGR422 — gabarit « relevé du point d'eau » (contrat AGR5,
  // `visite_terrain.json` → `gabarit_point_eau`) : codes et choix repris TELS
  // QUELS, jamais renommés (le serveur les valide). Les cases « non mesurable »
  // sont de vraies cases ; tout autre booléen est un tri-état (Oui / Non /
  // pas encore relevé) — jamais un « Non » enregistré sans réponse. Aucun
  // seuil ni verdict : le module montre, le bureau d'études juge (VT1).
  point_eau: [
    {
      key: 'source_eau', label: 'Source d\'eau', unite: '', type: 'select',
      options: [{ value: 'puits', label: 'Puits' }, { value: 'forage', label: 'Forage' }, { value: 'bassin', label: 'Bassin' }, { value: 'riviere', label: 'Rivière' }],
    },
    { key: 'niveau_statique_m', label: 'Niveau statique (pompe arrêtée)', unite: 'm', type: 'number' },
    { key: 'niveau_non_mesurable', label: 'Niveau non mesurable sur place', unite: '', type: 'bool' },
    { key: 'niveau_dynamique_m', label: 'Niveau dynamique (pompe en marche)', unite: 'm', type: 'number' },
    { key: 'debit_mesure_m3h', label: 'Débit mesuré', unite: 'm³/h', type: 'number' },
    { key: 'debit_non_mesurable', label: 'Débit non mesurable sur place', unite: '', type: 'bool' },
    {
      key: 'debit_methode', label: 'Méthode de mesure du débit', unite: '', type: 'select',
      options: [{ value: 'essai_pompage', label: 'Essai de pompage' }, { value: 'seau_chronometre', label: 'Seau chronométré' }, { value: 'compteur', label: 'Compteur' }, { value: 'declaration_foreur', label: 'Déclaration du foreur' }],
    },
    { key: 'profondeur_forage_m', label: 'Profondeur du forage', unite: 'm', type: 'number' },
    { key: 'diametre_tubage_mm', label: 'Diamètre du tubage', unite: 'mm', type: 'number' },
    { key: 'hauteur_refoulement_m', label: 'Hauteur de refoulement', unite: 'm', type: 'number' },
    { key: 'longueur_conduite_m', label: 'Longueur de la conduite', unite: 'm', type: 'number' },
    { key: 'diametre_conduite_mm', label: 'Diamètre de la conduite', unite: 'mm', type: 'number' },
    { key: 'bassin_volume_m3', label: 'Volume du bassin', unite: 'm³', type: 'number' },
  ],
  pompe_existante: [
    { key: 'pompe_presente', label: 'Une pompe est-elle déjà installée ?', unite: '', type: 'tribool' },
    {
      key: 'pompe_actuelle_type', label: 'Type de la pompe actuelle', unite: '', type: 'select',
      options: [{ value: 'immergee', label: 'Immergée' }, { value: 'surface', label: 'De surface' }, { value: 'ne_sait_pas', label: 'Ne sait pas' }],
    },
    { key: 'pompe_actuelle_cv', label: 'Puissance de la pompe actuelle', unite: 'CV', type: 'number' },
    { key: 'tension_v', label: 'Tension de la pompe actuelle', unite: 'V', type: 'number' },
    {
      key: 'alimentation', label: 'Alimentation de la pompe actuelle', unite: '', type: 'select',
      options: [{ value: 'mono', label: 'Monophasé' }, { value: 'tri', label: 'Triphasé' }],
    },
  ],
  electricite: [
    {
      key: 'electricite_sur_place', label: 'Électricité sur place', unite: '', type: 'select',
      options: [{ value: 'aucune', label: 'Aucune' }, { value: 'monophase', label: 'Monophasé' }, { value: 'triphase', label: 'Triphasé' }, { value: 'ne_sait_pas', label: 'Ne sait pas' }],
    },
  ],
  site_pv: [
    { key: 'distance_forage_champ_m', label: 'Distance forage → zone de pose', unite: 'm', type: 'number' },
    {
      key: 'type_pose', label: 'Type de pose', unite: '', type: 'select',
      options: [{ value: 'sol', label: 'Au sol' }, { value: 'ombriere', label: 'Ombrière' }],
    },
    { key: 'cloture', label: 'Zone clôturée', unite: '', type: 'tribool' },
    { key: 'gardiennage', label: 'Site gardé', unite: '', type: 'tribool' },
    { key: 'ombrage_notes', label: 'Ombrages (arbres, bâtiments)', unite: '', type: 'text' },
  ],
  administratif: [
    {
      key: 'autorisation_prelevement', label: 'Autorisation de prélèvement ABH', unite: '', type: 'select',
      options: [{ value: 'oui', label: 'Oui' }, { value: 'non', label: 'Non' }, { value: 'en_cours', label: 'En cours' }, { value: 'ne_sait_pas', label: 'Ne sait pas' }],
    },
    { key: 'autorisation_numero', label: 'Numéro d\'autorisation', unite: '', type: 'text' },
    { key: 'autorisation_debit_l_s', label: 'Débit autorisé', unite: 'L/s', type: 'number' },
    { key: 'autorisation_volume_m3_an', label: 'Volume annuel autorisé', unite: 'm³/an', type: 'number' },
    { key: 'compteur_eau', label: 'Compteur d\'eau sur le forage', unite: '', type: 'tribool' },
    { key: 'justificatif_foncier', label: 'Justificatif foncier', unite: '', type: 'text' },
    { key: 'foreur_permis', label: 'Permis du foreur (forage neuf)', unite: '', type: 'text' },
  ],
  general: [],
}

// Ordre d'affichage du wizard (toiture → tableau → local onduleur →
// cheminement [optionnel] → général) — SECOURS uniquement si le serveur ne
// renvoie pas déjà `checklist` dans cet ordre ; on trie sur cette clé mais on
// garde toute catégorie inconnue du serveur À LA FIN plutôt que de la perdre.
// AGR422 — le gabarit `point_eau` suit l'ordre servi : point_eau → pompe_existante
// → electricite → site_pv → administratif → general.
const ORDRE_CATEGORIES = [
  'toiture', 'tableau', 'local_onduleur', 'cheminement',
  'point_eau', 'pompe_existante', 'electricite', 'site_pv', 'administratif',
  'general',
]

// AGR422 — gabarit servi par la visite (`visite.gabarit`) ; absent = toiture.
export const GABARIT_POINT_EAU = 'point_eau'

// Les catégories PROPRES au gabarit point_eau (le gabarit toiture ne les porte pas).
export const CATEGORIES_POINT_EAU = [
  'point_eau', 'pompe_existante', 'electricite', 'site_pv', 'administratif',
]

export function estVisitePointEau(visite) {
  return visite?.gabarit === GABARIT_POINT_EAU
}

// Titre de l'écran : « Visite de relevé du point d'eau » pour le gabarit
// point_eau, sinon le nom du client (inchangé).
export function titreVisite(visite) {
  if (estVisitePointEau(visite)) return 'Visite de relevé du point d’eau'
  return visite?.client_panel?.lead_nom ?? `Visite #${visite?.id}`
}

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

// wa.me — QJR635 : ré-export du constructeur UNIQUE (`lib/contactLinks.js`
// waHref, qui normalise « 06… » → 2126…) ; jamais d'URL sans numéro
// exploitable.
export { waHref as whatsappUrl } from '../../lib/contactLinks.js'

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
