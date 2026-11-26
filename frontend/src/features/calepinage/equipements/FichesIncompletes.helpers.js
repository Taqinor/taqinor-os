// ENF22 — helpers extraits de FichesIncompletes.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/* ── L'IMPACT, champ par champ ─────────────────────────────────────────────
   Chaque entrée dit ce que le calepinage NE PEUT PAS produire sans ce champ.
   Les clés sont celles du contrat CAL243 (les specs du bloc `specs`, telles
   que `apps.stock.selectors.specs_for_produit` les publie), pas les clés
   préfixées du catalogue — la correspondance est faite par `PREFIXE_FICHE`. */
const IMPACT = {
  panneau: {
    longueur_mm: 'sans longueur : aucun calepinage — le pas de pose est inconnu',
    largeur_mm: 'sans largeur : aucun calepinage — le pas de pose est inconnu',
    epaisseur_mm: 'sans épaisseur : pas de hauteur de rail ni de garde au vent',
    poids_kg: 'sans poids : aucune descente de charge sur la toiture',
    pmax_wc: 'sans Pmax : aucune puissance crête, donc aucun productible',
    rendement_pct: 'sans rendement : aucune surface utile par kWc',
    voc_v: 'sans Voc : aucun verdict de tension de chaîne',
    vmp_v: 'sans Vmp : aucun placement dans la plage MPPT',
    isc_a: 'sans Isc : aucun verdict de courant d’entrée',
    imp_a: 'sans Imp : aucun courant de chaîne au point de puissance',
    temp_coeff_voc_pct_c: 'sans coefficient de température Voc : aucune tension à froid, donc aucun verdict de tension maximale',
    temp_coeff_pmax_pct_c: 'sans coefficient de température Pmax : aucune perte thermique, donc un productible surévalué',
    noct_c: 'sans NOCT : pas de modèle thermique — la température de cellule n’est pas calculable',
    uc_w_m2k: 'sans coefficient Uc : pas de modèle thermique au vent (Faiman)',
    uv_w_m3sk: 'sans coefficient Uv : pas de modèle thermique au vent (Faiman)',
    techno_cellule: 'sans technologie de cellule : aucun modèle de faible éclairement',
    bifacial: 'sans le caractère bifacial : aucun gain de face arrière n’est pris en compte',
    bifacialite_pct: 'sans taux de bifacialité : aucun gain de face arrière chiffré',
    degradation_annuelle_pct: 'sans dégradation annuelle : aucun productible à 10 ou 25 ans',
    degradation_annee1_pct: 'sans dégradation de première année : aucun productible d’année 1',
    garantie_pct_a_10_ans: 'sans garantie à 10 ans : aucun plancher de production contractuel à 10 ans',
    garantie_pct_a_25_ans: 'sans garantie à 25 ans : aucun plancher de production contractuel à 25 ans',
    // CALX60 — champs lus par la chaîne de pertes (lot 3)
    rendement_par_irradiance: 'sans courbe de rendement par irradiance : l’étape « niveau d’irradiance » s’omet, aucune perte à faible éclairement',
    tolerance_pmax_min_pct: 'sans tolérance Pmax minimale : aucune perte de mismatch fabricant chiffrée',
    tolerance_pmax_max_pct: 'sans tolérance Pmax maximale : aucune perte de mismatch fabricant chiffrée',
  },
  onduleur: {
    n_mppt: 'sans nombre de MPPT : aucune répartition des chaînes',
    mppt_v_min: 'sans tension MPPT minimale : aucun verdict de plage MPPT à chaud',
    mppt_v_max: 'sans tension MPPT maximale : aucun verdict de plage MPPT à froid',
    v_max_abs: 'sans tension maximale absolue : aucun verdict de sécurité de tension',
    v_demarrage_v: 'sans tension de démarrage : aucune heure de démarrage au lever du jour',
    i_max_mppt_a: 'sans courant MPPT maximal : aucun verdict de courant par entrée',
    isc_max_mppt_a: 'sans Isc maximal par MPPT : aucun verdict de courant de court-circuit',
    entrees_par_mppt: 'sans entrées par MPPT : aucun câblage de chaînes vérifiable',
    chaines_max_par_mppt: 'sans chaînes maximales par MPPT : aucun verdict de nombre de chaînes',
    ac_kw: 'sans puissance AC : aucun taux de surdimensionnement DC/AC',
    dc_max_kwc: 'sans puissance DC admissible : aucune limite de champ photovoltaïque',
    s_max_kva: 'sans puissance apparente maximale : aucun dimensionnement de raccordement',
    phases: 'sans nombre de phases : aucun verdict de raccordement mono/triphasé',
    rendement_euro_pct: 'sans rendement européen : aucune perte de conversion au productible',
    bat_max_charge_kw: 'sans puissance de charge batterie : aucun profil de charge',
    bat_max_decharge_kw: 'sans puissance de décharge batterie : aucun profil de décharge',
    // CALX60 — champs lus par la chaîne de pertes (lot 3)
    rendement_par_charge: 'sans courbe de rendement par charge : l’étape « onduleur » s’omet, aucune perte de conversion heure par heure',
    rendement_max_pct: 'sans rendement maximal : aucune perte de conversion à pleine charge',
    rendement_cec_pct: 'sans rendement CEC : aucune perte de conversion pondérée au profil réel',
    conso_nuit_w: 'sans consommation de nuit : aucune perte d’auxiliaires nocturne',
  },
  batterie: {
    kwh_nominal: 'sans capacité nominale : aucune autonomie calculable',
    dod_pct: 'sans profondeur de décharge : aucune énergie réellement utilisable',
    kwh_utile: 'sans énergie utile : aucune autonomie calculable',
    v_nominal: 'sans tension nominale : aucun verdict de compatibilité onduleur',
    p_charge_kw: 'sans puissance de charge : aucun temps de recharge',
    p_decharge_kw: 'sans puissance de décharge : aucune pointe soutenable',
    cycles: 'sans nombre de cycles : aucune durée de vie chiffrée',
    rendement_pct: 'sans rendement : aucune perte de stockage au bilan',
  },
  optimiseur: {
    p_max_wc: 'sans puissance maximale : aucun appairage au panneau',
    v_entree_max: 'sans tension d’entrée maximale : aucun verdict de compatibilité panneau',
    v_sortie_max: 'sans tension de sortie maximale : aucune longueur de chaîne admissible',
    i_entree_max_a: 'sans courant d’entrée maximal : aucun verdict de courant',
    rendement_pct: 'sans rendement : aucune perte d’optimisation au bilan',
  },
}

/** La phrase d'impact d'un champ. Jamais un message générique de remplissage. */
export function impactChamp(famille, champ) {
  return IMPACT[famille]?.[champ] ?? null
}

/* ACAL1740 — LE NOM FRANÇAIS D'UN CHAMP DE FICHE, avec son unité. Une clé
   brute (`noct_c`, `vmp_v`) n'est jamais lue à l'écran. Une table commune,
   plus un jeu par famille pour les clés dont le sens change (`rendement_pct`).
   Une clé inconnue reste lisible : underscores retirés, majuscule initiale. */
const LIBELLES_COMMUNS = {
  longueur_mm: 'Longueur (mm)',
  largeur_mm: 'Largeur (mm)',
  epaisseur_mm: 'Épaisseur (mm)',
  poids_kg: 'Poids (kg)',
  pmax_wc: 'Puissance maximale Pmax (Wc)',
  voc_v: 'Tension à vide Voc (V)',
  vmp_v: 'Tension au point de puissance Vmp (V)',
  isc_a: 'Courant de court-circuit Isc (A)',
  imp_a: 'Courant au point de puissance Imp (A)',
  temp_coeff_voc_pct_c: 'Coefficient de température de Voc (%/°C)',
  temp_coeff_pmax_pct_c: 'Coefficient de température de Pmax (%/°C)',
  noct_c: 'Température nominale de la cellule (°C)',
  uc_w_m2k: 'Coefficient thermique constant Uc (W/m²K)',
  uv_w_m3sk: 'Coefficient thermique au vent Uv (W·s/m³K)',
  techno_cellule: 'Technologie de cellule',
  bifacial: 'Module bifacial',
  bifacialite_pct: 'Bifacialité (%)',
  degradation_annuelle_pct: 'Dégradation annuelle (%)',
  degradation_annee1_pct: 'Dégradation de la première année (%)',
  garantie_pct_a_10_ans: 'Production garantie à 10 ans (%)',
  garantie_pct_a_25_ans: 'Production garantie à 25 ans (%)',
  rendement_par_irradiance: 'Rendement selon l’éclairement',
  tolerance_pmax_min_pct: 'Tolérance de Pmax minimale (%)',
  tolerance_pmax_max_pct: 'Tolérance de Pmax maximale (%)',
  n_mppt: 'Nombre de MPPT',
  mppt_v_min: 'Tension MPPT minimale (V)',
  mppt_v_max: 'Tension MPPT maximale (V)',
  v_max_abs: 'Tension maximale absolue (V)',
  v_demarrage_v: 'Tension de démarrage (V)',
  i_max_mppt_a: 'Courant maximal par MPPT (A)',
  isc_max_mppt_a: 'Courant de court-circuit maximal par MPPT (A)',
  entrees_par_mppt: 'Entrées par MPPT',
  chaines_max_par_mppt: 'Chaînes maximales par MPPT',
  ac_kw: 'Puissance AC (kW)',
  dc_max_kwc: 'Puissance DC admissible (kWc)',
  s_max_kva: 'Puissance apparente maximale (kVA)',
  phases: 'Nombre de phases',
  rendement_euro_pct: 'Rendement européen (%)',
  bat_max_charge_kw: 'Puissance de charge de la batterie (kW)',
  bat_max_decharge_kw: 'Puissance de décharge de la batterie (kW)',
  rendement_par_charge: 'Rendement selon la charge',
  rendement_max_pct: 'Rendement maximal (%)',
  rendement_cec_pct: 'Rendement CEC (%)',
  conso_nuit_w: 'Consommation de nuit (W)',
  kwh_nominal: 'Capacité nominale (kWh)',
  dod_pct: 'Profondeur de décharge (%)',
  kwh_utile: 'Énergie utile (kWh)',
  v_nominal: 'Tension nominale (V)',
  p_charge_kw: 'Puissance de charge (kW)',
  p_decharge_kw: 'Puissance de décharge (kW)',
  cycles: 'Nombre de cycles',
  p_max_wc: 'Puissance maximale (Wc)',
  v_entree_max: 'Tension d’entrée maximale (V)',
  v_sortie_max: 'Tension de sortie maximale (V)',
  i_entree_max_a: 'Courant d’entrée maximal (A)',
  rendement_pct: 'Rendement (%)',
  v_in_max: 'Tension d’entrée maximale (V)',
  i_in_max_a: 'Courant d’entrée maximal (A)',
  pmax_in_w: 'Puissance d’entrée maximale (W)',
}
const LIBELLES_PAR_FAMILLE = {
  panneau: { rendement_pct: 'Rendement du module (%)' },
  batterie: { rendement_pct: 'Rendement de la batterie (%)' },
  optimiseur: { rendement_pct: 'Rendement de l’optimiseur (%)' },
}

/** Le nom français (avec unité) d'un champ de fiche. */
export function libelleChamp(champ, famille) {
  const brut = String(champ ?? '')
  const lu = LIBELLES_PAR_FAMILLE[famille]?.[brut] ?? LIBELLES_COMMUNS[brut]
  if (lu) return lu
  const sans = brut.replace(/_/g, ' ').trim()
  return sans ? sans.charAt(0).toUpperCase() + sans.slice(1) : brut
}
