import { formatNumber } from '../../../lib/format'

/* ACAL405 — le préfixe des références écrites par « Appliquer aux réglages
   vides » : écrit UNE fois côté écran, égal à `prefixe_reference` du contrat
   `calepinage_profil_depart.json` (un test les compare). */
export const PREFIXE_PROFIL_DEPART = 'Profil de départ — '

export const MENTION_PUBLIEE = 'valeur publiée, non mesurée'

/** Vrai quand la référence figée est celle d'une valeur du profil de départ. */
export const estProfilDepart = (reference) =>
  typeof reference === 'string' && reference.startsWith(PREFIXE_PROFIL_DEPART)

/* ── Maquette « Démarrage rapide » : des mots de tous les jours ────────────
   Chaque réglage du profil de départ (`data/profil_depart.json`) a ici un NOM
   en français courant et une phrase d'aide. Aucune valeur, aucune source n'est
   écrite ici : seuls les mots changent, les valeurs viennent du serveur. Une clé
   absente de cette table s'affiche « Autre réglage » — jamais sa clé technique. */
export const LIBELLES_REGLAGES = {
  b0_iam: ['Reflets du verre', 'Le soleil rasant rebondit sur la vitre du panneau'],
  modele_iam: ['Façon de calculer les reflets', 'Méthode de calcul de la lumière perdue quand le soleil arrive de biais'],
  regle_qualite_module: ['Qualité des panneaux à la sortie d’usine', 'Lue dans la tolérance de puissance de la fiche du module ; sans tolérance publiée, le tri usuel 0 % à +3 % est supposé'],
  mismatch_fabricant_pct: ['Écarts entre panneaux', 'Deux panneaux d’une chaîne ne sont jamais tout à fait égaux'],
  thermique_par_pose: ['Échauffement selon la pose', 'Plus le panneau chauffe, moins il produit'],
  albedo_mensuel: ['Réflexion du sol', 'Lumière renvoyée par le sol vers les panneaux'],
  bifacial_mismatch_arriere_pct: ['Panneaux double face : écart de la face arrière', 'Perte propre aux panneaux qui captent aussi la lumière par l’arrière'],
  resolution_minutes: ['Pas de temps du calcul', 'Le calcul avance par tranches de temps de cette durée'],
  tolerance_polystring_acceptable_pct: ['Écart acceptable entre chaînes', 'Écart de tension toléré entre deux chaînes branchées ensemble'],
  tolerance_polystring_bloquante_pct: ['Écart bloquant entre chaînes', 'Au-delà de cet écart de tension, le câblage est refusé'],
  seuil_bas_dc_ac: ['Taille minimale des panneaux face à l’onduleur', 'Puissance des panneaux rapportée à celle de l’onduleur'],
  salissure_mensuelle_pct: ['Poussière sur les panneaux', 'La poussière retient une part du soleil entre deux nettoyages'],
  lid_par_techno: ['Perte des premières heures de soleil', 'Un panneau neuf perd un peu de puissance dès sa première exposition, selon sa technologie'],
  indisponibilite_forfait_pct: ['Arrêts de l’installation', 'Part de la production perdue quand l’installation est à l’arrêt (panne, entretien)'],
  ohmique_dc_conception_pct: ['Câbles entre les panneaux et l’onduleur', 'Chaleur perdue dans les câbles tant que leurs longueurs réelles ne sont pas connues'],
  ohmique_ac_conception_pct: ['Câble entre l’onduleur et le tableau', 'Chaleur perdue dans ce câble tant que sa longueur réelle n’est pas connue'],
}

/** `{ nom, aide }` d'une clé du profil ; « Autre réglage » si elle n'est pas dans la table. */
export function libelleReglage(cle) {
  const [nom, aide] = LIBELLES_REGLAGES[cle] || ['Autre réglage', '']
  return { nom, aide }
}

/* Les valeurs TEXTE du profil, dites en français. */
const VALEURS_TEXTE = {
  fresnel: 'Fresnel',
  quart_pvsyst: 'Un quart de l’écart, comme PVsyst',
}

const NOMBRE = (n) => formatNumber(Number(n), { maxDecimals: 3 })

/** Un nombre et son unité à la française : « 2 % », « 60 minutes », « 0,2 ». */
export function nombreAvecUnite(valeur, unite) {
  if (unite === '%') return `${NOMBRE(valeur)} %`
  return unite ? `${NOMBRE(valeur)} ${unite}` : NOMBRE(valeur)
}

/** La valeur proposée, lisible : jamais de JSON. Les trois formes du profil —
    nombre (avec son unité), texte nommé, et le tableau « par pose » (uc de chaque
    pose rangé dans l'ordre du serveur). */
export function valeurLisible(valeur, unite = '') {
  if (typeof valeur === 'number') return nombreAvecUnite(valeur, unite)
  if (typeof valeur === 'string') return VALEURS_TEXTE[valeur] || valeur
  if (valeur && typeof valeur === 'object') {
    const poses = Object.values(valeur)
      .map((p) => p?.uc_w_m2k)
      .filter((v) => typeof v === 'number')
    if (poses.length) return `${poses.map(NOMBRE).join(' · ')} W/m²K`
    const pertes = Object.values(valeur)
      .map((p) => p?.pct)
      .filter((v) => typeof v === 'number')
    if (pertes.length) return `${pertes.map(NOMBRE).join(' · ')} %`
    return 'Plusieurs valeurs'
  }
  return '—'
}

/** Sous la valeur « par pose » : les poses dans l'ordre servi (« Pose libre · dos isolé »). */
const POSES = { pose_libre: 'libre', dos_isole: 'dos isolé' }
const CELLULES = { perc: 'PERC', topcon: 'TOPCon', hjt: 'HJT', inconnue: 'autre' }
export function precisionValeur(valeur) {
  if (!valeur || typeof valeur !== 'object') return ''
  const noms = Object.keys(valeur).map((k) => POSES[k]).filter(Boolean)
  if (noms.length) return `Pose ${noms.join(' · ')}`
  const cellules = Object.keys(valeur).map((k) => CELLULES[k]).filter(Boolean)
  return cellules.length ? `Cellules ${cellules.join(' · ')}` : ''
}

/** « PVsyst » — l'éditeur nommé en tête de la référence (« Profil de départ — PVsyst, … »). */
export function sourceCourte(reference) {
  const sans = String(reference || '').replace(PREFIXE_PROFIL_DEPART, '')
  const nom = sans.split(/,| : /)[0].trim()
  return nom || 'Source'
}

/** Date AAAA-MM-JJ → « 20/11/2026 ». */
export const dateFr = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''))
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso || '')
}

/* Les réglages LAISSÉS SANS VALEUR faute de source publiée (`sans_source`) : leur nom en français, celui du
   registre des réglages (`services/parametres_cles.py`). Un test vérifie qu’aucune clé servie n’y manque. */
export const LIBELLES_SANS_SOURCE = {
  fenetre_annees: "Fenêtre d’années météo",
  mode_meteo: "Mode météo (année type ou fenêtre pluriannuelle)",
  sigma_modele_pct: "Incertitude de simulation (σ modèle)",
  sigma_biais_meteo_pct: "Biais long terme de la source météo (σ)",
  sigma_meteo_saisi_pct: "Variabilité interannuelle saisie (σ météo)",
  tolerance_validation_pct: "Tolérance d’écart admise face à PVGIS",
  annees_exploitation: "Durée d’exploitation simulée",
  modele_degradation: "Modèle de dégradation pluriannuelle",
  attenuation_horizon: "Atténuation appliquée au profil d’horizon",
  indisponibilite_fenetres: "Fenêtres d’arrêt de l’installation (début, fin, motif)",
  auxiliaires_w_constants: "Auxiliaires — terme constant en marche",
  auxiliaires_w_par_kw: "Auxiliaires — terme proportionnel à la production",
  auxiliaires_w_nuit: "Auxiliaires — consommation de nuit",
  bifacial_hauteur_pose_m: "Hauteur de pose de la face arrière au-dessus du sol (repli quand le document ne la porte pas)",
  bifacial_taux_occupation: "Taux d’occupation du sol (GCR) retenu pour la face arrière (repli quand le document ne le porte pas)",
  bifacial_pas_rangee_m: "Pas entre rangées retenu pour la face arrière (repli quand le document ne le porte pas)",
  seuil_derivation_acces: "Seuil d’accès solaire sous lequel un module est dérivé de sa chaîne",
  plafond_modules_simules: "Plafond de modules simulés un par un (au-delà, seul l’agrégat est publié)",
  seuil_desequilibre_pct: "Seuil de déséquilibre entre chaînes",
  borne_usuelle_dc_ac: "Borne usuelle du rapport DC/AC",
  seuil_alerte_dc_ac: "Seuil d’alerte du rapport DC/AC",
  correspondances_nomenclature: "Correspondances de nomenclature du bordereau",
  regle_bom_structure: "Règle de sortie de la structure hors bordereau électrique",
  cos_phi_par_defaut: "Cos φ retenu à défaut de mesure",
  neige_mensuelle_pct: "Perte de neige, mois par mois (12 valeurs, ou une seule pour les douze)",
  modele_transposition: "Modèle de transposition d’un fichier météo horizontal vers le plan",
  modele_decomposition: "Modèle de décomposition d’un fichier météo au global seul (direct/diffus)",
  rendement_specifique_min_kwh_kwc: "Rendement spécifique vraisemblable, borne basse",
  rendement_specifique_max_kwh_kwc: "Rendement spécifique vraisemblable, borne haute",
  seuil_acces_retrait: "Accès solaire sous lequel on propose de retirer un module",
  ombrage_borne_courant_pct: "Perte d’ombrage à partir de laquelle on la dit courante",
  ombrage_borne_importante_pct: "Perte d’ombrage à partir de laquelle on la dit importante",
  nettoyages_par_an: "Nettoyages des panneaux par an",
  inclinaison_autonettoyage_deg: "Inclinaison à partir de laquelle la pluie lave les panneaux",
  batterie_seuil_nuits_pct: "Part de nuits au plancher à partir de laquelle la batterie est dite trop petite",
  batterie_seuil_jours_pleine_pct: "Part de jours pleine en dessous de laquelle la batterie est dite trop grande",
  facteur_regroupement: "Facteur de regroupement appliqué au courant admissible des câbles",
  temperature_service_cable_c: "Température de service des câbles (résistivité de la chute de tension)",
  alpha_cuivre_par_c: "Coefficient de température de la résistivité du cuivre (α)",
  tolerance_orientation_pans_deg: "Tolérance d’orientation pour câbler une chaîne sur deux pans",
  consigne_dc_plan_cablage: "Consigne DC imprimée sur le plan de câblage",
  distance_separation_foudre_min_m: "Distance de séparation foudre minimale (paratonnerre ↔ champ)",
  boucle_dc_max_m2: "Surface maximale d’une boucle de chaîne",
  seuil_orientations_micro: "Nombre d’orientations à partir duquel étudier des micro-onduleurs",
  seuil_ecart_acces_optimiseur: "Écart d’accès solaire dans une chaîne à partir duquel étudier des optimiseurs",
  gabarit_verification_max_jours: "Nombre de jours au-delà duquel un gabarit vérifié est à redemander",
  fiche_ecart_pmax_pct: "Écart toléré entre Pmax et Vmp × Imp d’une fiche module importée",
  seuil_acces_optimiseur: "Accès solaire sous lequel un module est proposé pour un optimiseur",
  // ACAL1624 — les douze réglages de lestage (registre servi `registre.lestage`), sans valeur publiée.
  vitesse_vent_reference_m_s: 'Vitesse de vent de référence',
  categorie_terrain: 'Catégorie de terrain',
  coefficient_terrain: 'Coefficient de terrain',
  coefficient_pression_soulevement: 'Coefficient de pression (soulèvement)',
  coefficient_pression_horizontal: 'Coefficient de pression (horizontal)',
  coefficient_frottement: 'Coefficient de frottement',
  charge_neige_kn_m2: 'Charge de neige',
  masse_structure_kg_par_module: 'Masse de structure par module (kit)',
  largeur_bande_rive_m: 'Largeur de la bande de rive',
  largeur_coin_m: 'Largeur de coin',
  lest_rive_kg_par_module: 'Lest additionnel en rive',
  lest_coin_kg_par_module: 'Lest additionnel en coin',
}

/** Le nom lisible d une clé sans source (jamais la clé elle-même). */
export const nomSansSource = (cle) => LIBELLES_SANS_SOURCE[cle] || libelleReglage(cle).nom

/** Vrai pour un réglage que le démarrage rapide laisse SANS valeur faute de source publiée : « Remplir » ne le
    remplira pas. L'écran des résultats incomplets s'aligne dessus pour ne compter que ce que « Remplir » remplit. */
export const estSansSource = (cle) => Object.prototype.hasOwnProperty.call(LIBELLES_SANS_SOURCE, cle)
