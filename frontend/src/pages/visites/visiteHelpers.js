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
// CIQ609 — le gabarit `ci` (site professionnel) : socle commun puis, une fois
// `general` passé, le supplément MT servi par le serveur (CIQ660).
const ORDRE_CATEGORIES = [
  'site_commerce',
  'toiture', 'toiture_ci', 'tableau', 'tableau_general', 'comptage',
  'local_onduleur', 'cheminement', 'acces_securite', 'autres_autorisations',
  'point_eau', 'pompe_existante', 'electricite', 'site_pv', 'administratif',
  'general',
  'poste_mt', 'factures_mt', 'reactif_secours', 'charges_principales',
  'reseau_assurance',
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

// CIQ609 — gabarit `ci` : la visite d'un site professionnel (lead commercial
// ou industriel). Les gabarits toiture et point_eau restent rendus à l'identique.
export const GABARIT_CI = 'ci'

export function estVisiteCi(visite) {
  return visite?.gabarit === GABARIT_CI
}

// Titre de l'écran : « Visite de relevé du point d'eau » pour le gabarit
// point_eau, sinon le nom du client (inchangé).
export function titreVisite(visite) {
  if (estVisitePointEau(visite)) return 'Visite de relevé du point d’eau'
  if (estVisiteCi(visite)) return 'Visite technique — site professionnel'
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
      { value: 'proprietaire_tiers', label: 'Le propriétaire (un tiers) décide' },
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


// ── CIQ609 — gabarit `ci` : schéma des mesures d'un site professionnel ───────
//
// Codes, libellés et choix repris TELS QUELS du contrat CIQ5
// (`apps/visites/contract_samples/visite_terrain.json` → `gabarit_ci`) ; le
// serveur les valide, la complétude vient TOUJOURS de lui (`completude`). Aucun
// seuil, aucun verdict : le module montre, le bureau d'études juge. Les
// booléens sont des TRI-ÉTATS (Oui / Non / pas encore relevé) : jamais un
// « Non » enregistré sans réponse. Une clé `list` porte `forme` (les champs
// d'UN élément) ; `id` = préfixe des identifiants d'élément (zones : z1, z2…) ;
// `nonReleve` marque un champ d'élément qui peut être « non relevé ».
const OUI_NON = { type: 'tribool' }

export const MESURES_SCHEMA_CI = {
  // CIQ653 — « site commerce » (contrat `gabarit_ci_site_commerce`) : horaires,
  // circuits critiques, secours existant, accès, besoin de continuité. La pièce
  // « accord du propriétaire » est une tuile photo SERVIE par le serveur (lead
  // locataire seulement) : l'écran ne la décide jamais.
  site_commerce: [
    {
      key: 'categorie', label: 'Catégorie du site', unite: '', type: 'select',
      options: [
        { value: 'hotel', label: 'Hôtel / riad' }, { value: 'restaurant', label: 'Restaurant / café' },
        { value: 'commerce', label: 'Commerce / supermarché' }, { value: 'bureau', label: 'Bureaux' },
        { value: 'sante', label: 'Santé (clinique, cabinet)' }, { value: 'ecole', label: 'École' },
        { value: 'hammam', label: 'Hammam / spa / salle de sport' }, { value: 'boulangerie', label: 'Boulangerie' },
        { value: 'froid', label: 'Froid / entrepôt frigorifique' }, { value: 'autre', label: 'Autre' },
      ],
    },
    { key: 'horaires_constates', label: "Horaires et jours d'ouverture", unite: '', type: 'text' },
    { key: 'equipements_principaux', label: 'Équipements principaux', unite: '', type: 'text' },
    {
      key: 'circuits_critiques', label: 'Circuits critiques', type: 'list',
      itemLabel: 'Circuit', addLabel: 'Ajouter un circuit critique',
      forme: [
        {
          key: 'circuit', label: 'Circuit critique', unite: '', type: 'select',
          options: [
            { value: 'froid', label: 'Froid' }, { value: 'medical', label: 'Matériel médical' },
            { value: 'informatique', label: 'Informatique' }, { value: 'cuisine', label: 'Cuisine' },
            { value: 'autre', label: 'Autre' },
          ],
        },
        { key: 'precision', label: 'Précision', unite: '', type: 'text' },
      ],
    },
    { key: 'secours_groupe', label: 'Groupe électrogène existant', unite: '', ...OUI_NON },
    { key: 'secours_ups', label: 'Onduleur UPS existant', unite: '', ...OUI_NON },
    { key: 'secours_inverseur', label: 'Inverseur de source existant', unite: '', ...OUI_NON },
    { key: 'acces_pendant_ouverture', label: "Contraintes d'accès pendant l'ouverture", unite: '', type: 'text' },
    { key: 'besoin_continuite_service', label: 'Besoin de continuité de service', unite: '', ...OUI_NON },
  ],
  toiture_ci: [
    {
      key: 'zones_toiture', label: 'Zones de toiture (une par pan / bâtiment)', type: 'list',
      itemLabel: 'Zone', addLabel: 'Ajouter une zone', id: 'z',
      forme: [
        { key: 'libelle', label: 'Nom de la zone', unite: '', type: 'text' },
        { key: 'batiment', label: 'Bâtiment', unite: '', type: 'text' },
        { key: 'longueur_m', label: 'Longueur', unite: 'm', type: 'number' },
        { key: 'largeur_m', label: 'Largeur', unite: 'm', type: 'number' },
        { key: 'surface_utile_m2', label: 'Surface utile', unite: 'm²', type: 'number', nonReleve: true },
        { key: 'pente_deg', label: 'Pente', unite: '°', type: 'number', nonReleve: true },
        {
          key: 'orientation', label: 'Orientation du pan', unite: '', type: 'select', nonReleve: true,
          options: [
            { value: 'nord', label: 'Nord' }, { value: 'nord_est', label: 'Nord-Est' },
            { value: 'est', label: 'Est' }, { value: 'sud_est', label: 'Sud-Est' },
            { value: 'sud', label: 'Sud' }, { value: 'sud_ouest', label: 'Sud-Ouest' },
            { value: 'ouest', label: 'Ouest' }, { value: 'nord_ouest', label: 'Nord-Ouest' },
          ],
        },
        {
          key: 'couverture', label: 'Type de couverture', unite: '', type: 'select', nonReleve: true,
          options: [
            { value: 'bac_acier', label: 'Bac acier' }, { value: 'beton', label: 'Béton' },
            { value: 'fibrociment', label: 'Fibrociment' }, { value: 'tole', label: 'Tôle' },
            { value: 'tuile', label: 'Tuile' }, { value: 'autre', label: 'Autre' },
          ],
        },
        { key: 'age_ans', label: 'Âge de la couverture', unite: 'ans', type: 'number' },
        {
          key: 'structure', label: 'Structure porteuse', unite: '', type: 'select', nonReleve: true,
          options: [
            { value: 'portique', label: 'Portique' }, { value: 'ferme', label: 'Ferme' },
            { value: 'dalle', label: 'Dalle' }, { value: 'autre', label: 'Autre' },
          ],
        },
        { key: 'portee_pannes_m', label: 'Portée des pannes', unite: 'm', type: 'number' },
        { key: 'entraxe_pannes_m', label: 'Entraxe des pannes', unite: 'm', type: 'number' },
        { key: 'epaisseur_bac_mm', label: 'Épaisseur du bac', unite: 'mm', type: 'number' },
        {
          key: 'etancheite', label: 'Étanchéité', type: 'objet',
          forme: [
            { key: 'type', label: "Type d'étanchéité", unite: '', type: 'text' },
            { key: 'age_ans', label: "Âge de l'étanchéité", unite: 'ans', type: 'number' },
            { key: 'sous_garantie', label: 'Étanchéité sous garantie', unite: '', ...OUI_NON },
          ],
        },
        { key: 'lanterneaux_exutoires', label: 'Lanterneaux et exutoires', unite: '', type: 'text' },
        { key: 'ligne_de_vie_existante', label: 'Ligne de vie existante', unite: '', ...OUI_NON },
        // DÉCLARÉE seulement, avec sa pièce : l'application ne juge jamais que
        // la charge « suffit ».
        { key: 'charge_admissible_declaree_kg_m2', label: 'Charge admissible déclarée', unite: 'kg/m²', type: 'number', nonReleve: true },
        { key: 'charge_admissible_piece', label: 'Pièce justifiant la charge admissible (bureau de contrôle ou propriétaire)', unite: '', type: 'piece' },
        { key: 'fibrociment', label: 'Amiante possible — diagnostic requis', unite: '', ...OUI_NON },
      ],
    },
  ],
  tableau_general: [
    { key: 'calibre_a', label: "Calibre de l'appareil de tête (A)", unite: '', type: 'number' },
    { key: 'depart_disponible', label: 'Départ disponible pour le PV', unite: '', ...OUI_NON },
    {
      key: 'regime_neutre', label: 'Régime de neutre', unite: '', type: 'select',
      options: [
        { value: 'TT', label: 'TT' }, { value: 'TN', label: 'TN' },
        { value: 'IT', label: 'IT' }, { value: 'inconnu', label: 'Inconnu' },
      ],
    },
    { key: 'parafoudre_existant', label: 'Parafoudre existant', unite: '', ...OUI_NON },
  ],
  comptage: [
    { key: 'type_compteur', label: 'Type de compteur', unite: '', type: 'text' },
    {
      key: 'niveau_tension_constate', label: 'Niveau de tension constaté', unite: '', type: 'select',
      options: [
        { value: 'bt', label: 'Basse tension (BT)' }, { value: 'mt', label: 'Moyenne tension (MT)' },
        { value: 'inconnu', label: 'Inconnu' },
      ],
    },
    { key: 'puissance_souscrite_kva_constatee', label: 'Puissance souscrite constatée (plaque / contrat)', unite: 'kVA', type: 'number' },
  ],
  cheminement: [
    {
      key: 'trajets', label: 'Trajets de câbles', type: 'list',
      itemLabel: 'Trajet', addLabel: 'Ajouter un trajet',
      forme: [
        { key: 'libelle', label: 'Trajet', unite: '', type: 'text' },
        { key: 'longueur_dc_m', label: 'Longueur DC', unite: 'm', type: 'number', nonReleve: true },
        { key: 'longueur_ac_m', label: 'Longueur AC', unite: 'm', type: 'number', nonReleve: true },
      ],
    },
  ],
  acces_securite: [
    { key: 'escalier', label: "Escalier d'accès", unite: '', ...OUI_NON },
    { key: 'echelle', label: 'Échelle nécessaire', unite: '', ...OUI_NON },
    { key: 'nacelle', label: 'Nacelle nécessaire', unite: '', ...OUI_NON },
    { key: 'grue_possible', label: 'Grue possible', unite: '', ...OUI_NON },
    { key: 'horaires_acces', label: "Horaires d'accès au site", unite: '', type: 'text' },
    { key: 'zones_fragiles', label: 'Zones fragiles (lanterneaux, bac corrodé…)', unite: '', type: 'text' },
  ],
  autres_autorisations: [
    { key: 'texte', label: 'Autres autorisations à confirmer avec le client (décret 2.25.100 art. 26)', unite: '', type: 'text' },
  ],
  general: [],
  // CIQ661 — supplément d'un site raccordé en MOYENNE tension (contrat
  // `gabarit_ci_supplement_mt`). Le serveur ne le sert que lorsque le relevé
  // `comptage.niveau_tension_constate` vaut `mt` : l'écran n'ajoute ni ne
  // retire jamais ces catégories de lui-même. Que des faits : aucun seuil,
  // aucun verdict, aucune alerte cos φ.
  poste_mt: [
    { key: 'cellule_protection', label: 'Cellule et protection existantes', unite: '', type: 'text' },
    {
      key: 'transformateurs', label: 'Transformateurs', type: 'list',
      itemLabel: 'Transformateur', addLabel: 'Ajouter un transformateur',
      forme: [
        { key: 'nb', label: 'Nombre', unite: '', type: 'number' },
        { key: 'kva', label: 'Puissance', unite: 'kVA', type: 'number' },
      ],
    },
    { key: 'tgbt_courant_assigne_a', label: 'TGBT : courant assigné (A)', unite: '', type: 'number' },
    { key: 'tgbt_jeu_de_barres', label: 'TGBT : jeu de barres', unite: '', type: 'text' },
  ],
  factures_mt: [
    {
      key: 'registres', label: '12 factures : registres pointe / pleines / creuses (photos)', type: 'list',
      itemLabel: 'Facture', addLabel: 'Ajouter une facture',
      forme: [
        { key: 'mois', label: 'Mois (AAAA-MM)', unite: '', type: 'text' },
        { key: 'pointe_kwh', label: 'Pointe', unite: 'kWh', type: 'number' },
        { key: 'pleines_kwh', label: 'Pleines', unite: 'kWh', type: 'number' },
        { key: 'creuses_kwh', label: 'Creuses', unite: 'kWh', type: 'number' },
      ],
    },
    { key: 'cos_phi_constate', label: 'cos φ constaté', unite: '', type: 'number' },
    {
      key: 'source_cos_phi', label: 'Source du cos φ', unite: '', type: 'select',
      options: [
        { value: 'facture', label: 'Facture' }, { value: 'mesure', label: 'Mesure' },
        { value: 'inconnu', label: 'Inconnue' },
      ],
    },
  ],
  reactif_secours: [
    { key: 'condensateurs_kvar', label: 'Batterie de condensateurs (kvar)', unite: '', type: 'number' },
    { key: 'condensateurs_etat', label: 'État de la batterie de condensateurs', unite: '', type: 'text' },
    { key: 'groupe_kva', label: 'Groupe électrogène (kVA)', unite: '', type: 'number' },
    { key: 'groupe_inverseur', label: 'Inverseur de source', unite: '', ...OUI_NON },
  ],
  charges_principales: [
    {
      key: 'charges', label: 'Charges principales (moteurs, variateurs, fours, soudage)', type: 'list',
      itemLabel: 'Charge', addLabel: 'Ajouter une charge',
      forme: [
        { key: 'libelle', label: 'Charge', unite: '', type: 'text' },
        { key: 'puissance_kw', label: 'Puissance', unite: 'kW', type: 'number' },
      ],
    },
  ],
  reseau_assurance: [
    { key: 'poste_source', label: 'Poste source', unite: '', type: 'text' },
    // Saisie MANUELLE : aucun scraping de la plateforme (règle #5).
    { key: 'capacite_poste_source', label: 'Capacité lue sur la plateforme ANRE (saisie manuelle, aucun scraping — règle #5)', unite: '', type: 'text' },
    { key: 'capacite_consultee_le', label: 'Date de consultation de la plateforme', unite: '', type: 'date' },
    { key: 'assureur', label: 'Assureur du site', unite: '', type: 'text' },
    { key: 'exigences_assureur_piece', label: "Exigences écrites de l'assureur", unite: '', type: 'piece' },
    { key: 'compartimentage_sprinklers', label: 'Compartimentage / sprinklers', unite: '', type: 'text' },
    { key: 'profil_charge_mesure_fichier', label: 'Fichier de profil de charge mesuré (facultatif)', unite: '', type: 'piece' },
  ],
}

// Le schéma d'affichage d'une catégorie SELON le gabarit de la visite : la
// catégorie `cheminement` n'a pas les mêmes champs en toiture (longueur
// estimée) et en `ci` (trajets). Gabarit toiture / point_eau : inchangé.
export function schemaMesures(categorie, gabarit) {
  if (gabarit === GABARIT_CI && MESURES_SCHEMA_CI[categorie]) return MESURES_SCHEMA_CI[categorie]
  return MESURES_SCHEMA[categorie] ?? []
}

// CIQ601 — motifs FERMÉS de « non relevé » (contrat `non_releves_motifs`) et
// leur libellé lisible.
export const MOTIFS_NON_RELEVE = [
  { value: 'acces_refuse', label: 'Accès refusé' },
  { value: 'dangereux', label: 'Dangereux' },
  { value: 'site_ferme', label: 'Site fermé' },
  { value: 'a_faire_par_electricien', label: 'À faire par un électricien' },
  { value: 'non_applicable', label: 'Non applicable' },
]

export function libelleMotifNonReleve(motif) {
  return MOTIFS_NON_RELEVE.find((m) => m.value === motif)?.label ?? motif
}

// Clé « non relevé » d'une mesure (`calibre_a`) ou d'un champ d'élément de
// liste (`zones_toiture[z1].pente_deg`, `trajets.longueur_dc_m`) — format du
// contrat (`exemple_ci._non_releves`).
export function cleNonReleve(listeKey, ligneId, champKey) {
  if (!listeKey) return champKey
  if (ligneId) return `${listeKey}[${ligneId}].${champKey}`
  return `${listeKey}.${champKey}`
}

// ── Valeurs d'un formulaire de mesures ↔ charge utile du PATCH ──────────────
// Aller-retour STABLE : enregistrer → rouvrir → enregistrer sans toucher
// envoie exactement le même PATCH (les nombres partent en nombres, jamais en
// chaînes qui dépendent de la frappe).

const vide = (v) => v == null || v === ''

export function valeurVersForm(champ, v) {
  if (champ.type === 'tribool') return v === true ? 'oui' : v === false ? 'non' : ''
  if (champ.type === 'bool') return Boolean(v)
  if (champ.type === 'list') {
    return (Array.isArray(v) ? v : []).map((ligne) => ({
      ...(champ.id ? { id: ligne?.id ?? '' } : {}),
      ...formDepuisValeurs(champ.forme, ligne),
    }))
  }
  if (champ.type === 'objet') return formDepuisValeurs(champ.forme, v)
  return vide(v) ? '' : String(v)
}

export function formDepuisValeurs(schema, valeurs) {
  const out = {}
  for (const champ of schema) out[champ.key] = valeurVersForm(champ, valeurs?.[champ.key])
  return out
}

export function valeurVersPayload(champ, v) {
  if (champ.type === 'tribool') return v === 'oui' ? true : v === 'non' ? false : null
  if (champ.type === 'bool') return Boolean(v)
  if (champ.type === 'list') {
    return (Array.isArray(v) ? v : []).map((ligne) => ({
      ...(champ.id && ligne.id ? { id: ligne.id } : {}),
      ...payloadDepuisForm(champ.forme, ligne),
    }))
  }
  if (champ.type === 'objet') return payloadDepuisForm(champ.forme, v ?? {})
  if (vide(v)) return null
  if (champ.type === 'number') {
    const n = Number(v)
    // Une saisie illisible part TELLE QUELLE : c'est le serveur qui la refuse,
    // avec son message sous le champ (jamais un nombre « corrigé » ici).
    return Number.isFinite(n) && String(v).trim() !== '' ? n : v
  }
  return v
}

export function payloadDepuisForm(schema, form) {
  const out = {}
  for (const champ of schema) out[champ.key] = valeurVersPayload(champ, form?.[champ.key])
  return out
}

// Une nouvelle ligne d'une liste : champs vides + identifiant libre suivant
// (`z1`, `z2`…) pour les listes à identifiants.
export function nouvelleLigne(champ, lignes) {
  const base = formDepuisValeurs(champ.forme, {})
  if (!champ.id) return base
  const utilises = new Set((lignes ?? []).map((l) => l.id))
  let n = (lignes ?? []).length + 1
  while (utilises.has(`${champ.id}${n}`)) n += 1
  return { id: `${champ.id}${n}`, ...base }
}

// Les états « non relevé » d'UNE catégorie, depuis la table à plat du serveur
// (`visite._non_releves` : `{'<categorie>.<clé>': motif}`).
export function nonRelevesDeCategorie(plats, categorie) {
  const prefixe = `${categorie}.`
  const out = {}
  for (const [cle, motif] of Object.entries(plats ?? {})) {
    if (cle.startsWith(prefixe)) out[cle.slice(prefixe.length)] = motif
  }
  return out
}

// Libellé lisible d'une clé « non relevé » (récap bureau d'études).
export function libelleCleNonReleve(schema, cle) {
  const m = /^([a-z0-9_]+)(?:\[([^\]]+)\])?(?:\.([a-z0-9_]+))?$/.exec(cle ?? '')
  if (!m) return cle
  const champ = schema.find((c) => c.key === m[1])
  if (!champ) return cle
  if (!m[3]) return champ.label
  const sous = champ.forme?.find((c) => c.key === m[3])
  return `${champ.label} — ${sous?.label ?? m[3]}`
}

// CIQ609 — lignes du tableau déclaré / constaté / écart de la revue bureau
// d'études. SERVIES par le serveur (`visite.releve_ci`, CIQ606) : rien n'est
// recalculé ici, seul l'affichage est mis en forme.
export const LIGNES_RELEVE_CI = [
  { key: 'niveau_tension', label: 'Niveau de tension', unite: '' },
  { key: 'puissance_souscrite_kva', label: 'Puissance souscrite', unite: 'kVA' },
  { key: 'type_toiture', label: 'Type de toiture', unite: '' },
  { key: 'surface_utile', label: 'Surface utile', unite: 'm²' },
  { key: 'statut_occupation', label: 'Statut d’occupation', unite: '' },
]

export function valeurReleve(valeur, unite) {
  if (valeur == null || valeur === '') return '—'
  return unite ? `${valeur} ${unite}` : String(valeur)
}

// `ecart` : true = différent, false = égal, null = non comparable.
export function libelleEcart(ecart) {
  if (ecart === true) return 'Écart'
  if (ecart === false) return 'Concordant'
  return 'Non comparable'
}
