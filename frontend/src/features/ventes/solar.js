// Solar math + catalogue auto-fill, ported 1:1 from RedaSolar/devis-simulator
// (constants.py, roi_router.py, autofill.py / autofill_router.py, app.js).
// The simulator is the source of truth: prices are handled in TTC (like the
// simulator UI) and only converted to HT at save time. Pure functions, no I/O.
// The premium PDF engine computes its own figures server-side — never fed here.

import { formatMAD } from '../../lib/format.js'

// ── Constantes Maroc (irradiance GHI mensuelle + tarif ONEE) ──────────────────
// DC9 — MIROIR de la source Python unique
// (backend apps/ventes/quote_engine/constants.py GHI). Les deux tables DOIVENT
// rester identiques : un test de parité (test_dc9_ghi_parity.py) échoue sinon.
// Ne jamais éditer l'une sans répercuter l'autre à l'identique.
export const GHI = [
  83.99, 96.79, 133.43, 155.30, 175.28, 179.62,
  179.56, 161.17, 137.03, 111.59, 81.91, 74.61,
]
// Libellés des mois : grille des factures (complets) vs graphique (courts),
// exactement comme dans le simulateur (MONTHS_FR vs labels du chart).
export const MONTHS_FR = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc',
]
export const CHART_MONTHS = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
  'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc',
]
export const EFFICIENCY = 0.8 // rendement global
export const KWH_PRICE = 1.75 // MAD/kWh ONEE — usage interne, jamais affiché

// ── QX38 — productible CANONIQUE (kWh/kWc/an) par ville, source PVGIS ─────────
// MIROIR EXACT de backend apps/ventes/quote_engine/productible.py
// (PRODUCTIBLE_PAR_VILLE + DEFAULT_PRODUCTIBLE) et de apps/web yieldTable.ts
// (aspect Sud, inclinaison optimale). Les trois DOIVENT rester alignés :
// l'écran, le PDF et la proposition web affichent alors la MÊME production/
// économies pour les mêmes entrées. Ne jamais éditer l'un sans les deux autres.
export const PRODUCTIBLE_PAR_VILLE = {
  agadir: 1687,
  marrakech: 1651,
  casablanca: 1651,
  rabat: 1630,
  tanger: 1634,
}
export const DEFAULT_PRODUCTIBLE = 1651 // Casablanca (centre zone de service)

// ── Pertes système : 20 % AU TOTAL (ordre fondateur, 18/08) — MIROIR pricing.py
// Les productibles ci-dessus sont des sorties PVGIS demandées à `loss=14`
// (cf. backend apps/parametres/pvgis.py) : 14 % de pertes sont DÉJÀ dedans.
// Le fondateur fixe le total à 20 % → on applique le seul COMPLÉMENT,
// (1 − 20 %)/(1 − 14 %) ≈ 0,9302, pour passer d'un productible « net à 14 % »
// à un productible « net à 20 % ». Le chemin historique GHI × EFFICIENCY (0,8)
// porte DÉJÀ les 20 % : il n'est pas touché (sinon on compterait deux fois).
export const SYSTEM_LOSS_TOTAL = 0.20   // pertes système TOTALES (fondateur 18/08)
export const PVGIS_BUILTIN_LOSS = 0.14  // pertes déjà incluses dans le productible
export const PRODUCTIBLE_NET_FACTOR = (1 - SYSTEM_LOSS_TOTAL) / (1 - PVGIS_BUILTIN_LOSS)
const _CITY_ALIASES = {
  casa: 'casablanca', kenitra: 'rabat', sale: 'rabat', salé: 'rabat',
  mohammedia: 'casablanca', 'el jadida': 'casablanca', essaouira: 'agadir',
  safi: 'casablanca', temara: 'rabat', témara: 'rabat', tetouan: 'tanger',
  tétouan: 'tanger', settat: 'casablanca', benguerir: 'marrakech',
  berrechid: 'casablanca',
}

// Productible canonique pour une ville. `override` = productible société
// (CompanyProfile) : renseigné (> 0, 1600 compris — AMOT64, D-AMOT-3 = a), il
// prime ; vide (null) on lit le productible PVGIS de la ville (repli DEFAULT).
// Même règle que productible.py::productible_for_city (aucune sentinelle 1600).
export function productibleForCity(city, override = null) {
  const ov = parseFloat(override)
  if (Number.isFinite(ov) && ov > 0) {
    return ov
  }
  const key = String(city || '').trim().toLowerCase()
  if (!key) return DEFAULT_PRODUCTIBLE
  const norm = _CITY_ALIASES[key] || key
  return PRODUCTIBLE_PAR_VILLE[norm] ?? DEFAULT_PRODUCTIBLE
}

// Factures mensuelles affichées au chargement (initApp du simulateur)
export const DEFAULT_MONTHLY_BILLS = [500, 450, 400, 380, 360, 500, 700, 680, 580, 480, 430, 480]

// Autoconsommation par défaut selon le type d'installation. CIQ128 — plus
// d'entrée commerciale ni industrielle : le profil de charge C&I est DÉCLARÉ
// au moteur serveur (`etude-ci/preview`), jamais une part diurne d'écran.
export const DAY_USAGE_DEFAULTS = {
  'Résidentielle': 60,
  'Agricole': 100,
}

// ── QX44 — catégories commerciales et leurs questions (libellés de SAISIE) ──
// CIQ128 — la part diurne par catégorie (table et fonction de day-share) est
// SUPPRIMÉE : la catégorie et ses réponses partent au
// moteur serveur C&I (`rythme.categorie_commerciale`), qui choisit l'archétype.
// Miroir informatif du questionnaire webhook (QX51) — clés snake_case.
// Décision fondateur 26/10/2026 — 23 commerces (crm.Lead.CategorieCommerciale).
export const COMMERCIAL_CATEGORIES = [
  { value: 'hotel', label: 'Hôtel / Riad' }, { value: 'restaurant', label: 'Restaurant' }, { value: 'cafe', label: 'Café / salon de thé / glacier' },
  { value: 'boulangerie', label: 'Boulangerie / pâtisserie' }, { value: 'commerce', label: 'Commerce / boutique' },
  { value: 'supermarche', label: 'Supermarché / épicerie (avec frigos)' }, { value: 'boucherie', label: 'Boucherie / poissonnerie' },
  { value: 'pharmacie', label: 'Pharmacie' }, { value: 'coiffure', label: 'Coiffure / esthétique' }, { value: 'pressing', label: 'Pressing / laverie' },
  { value: 'bureau', label: 'Bureau / Siège' }, { value: 'sante', label: 'Santé (clinique / cabinet)' }, { value: 'ecole', label: 'École privée' },
  { value: 'salle_sport', label: 'Salle de sport' }, { value: 'hammam', label: 'Hammam / Spa' },
  { value: 'garage', label: 'Garage / atelier mécanique' }, { value: 'atelier', label: 'Atelier (menuiserie, ferronnerie, couture)' },
  { value: 'imprimerie', label: 'Imprimerie' }, { value: 'station_service', label: 'Station-service' },
  { value: 'entrepot', label: 'Entrepôt / logistique (sans froid)' }, { value: 'froid', label: 'Entrepôt froid' },
  { value: 'mosquee', label: 'Mosquée / association' }, { value: 'autre', label: 'Autre commerce' },
]

// Questions 2-4 par catégorie (recherche 2026-07-16). key = clé snake_case
// envoyée au moteur C&I dans `rythme.reponses_categorie` (jamais à plat dans
// etude_params, CIQ129) et acceptée par le webhook QX51. type =
// 'number' | 'bool' | 'select' (+ options).
export const COMMERCIAL_CATEGORY_QUESTIONS = {
  hotel: [
    { key: 'chambres', label: 'Nombre de chambres', type: 'number' },
    { key: 'occupation_pct', label: "Taux d'occupation annuel (%)", type: 'number' },
    { key: 'piscine', label: 'Piscine chauffée', type: 'bool' },
  ],
  restaurant: [
    { key: 'chambres_froides', label: 'Chambres froides', type: 'number' },
    {
      key: 'horaires', label: 'Horaires', type: 'select', options: [
        { value: 'midi', label: 'Midi' }, { value: 'soir', label: 'Soir' },
        { value: 'continu', label: 'Continu' },
      ],
    },
    {
      key: 'cuisson', label: 'Cuisson', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
  ],
  commerce: [
    { key: 'surface_vente_m2', label: 'Surface de vente (m²)', type: 'number' },
    { key: 'chambres_froides', label: 'Meubles / chambres froids', type: 'number' },
  ],
  bureau: [
    { key: 'effectif', label: 'Effectif (postes)', type: 'number' },
    { key: 'clim', label: 'Climatisation centralisée', type: 'bool' },
  ],
  sante: [
    { key: 'lits', label: 'Nombre de lits', type: 'number' },
    { key: 'garde_nuit', label: 'Garde de nuit', type: 'bool' },
  ],
  ecole: [
    { key: 'effectif', label: 'Effectif (élèves)', type: 'number' },
    { key: 'internat', label: 'Internat', type: 'bool' },
    { key: 'fermeture_estivale', label: 'Fermeture estivale', type: 'bool' },
  ],
  hammam: [
    { key: 'surface_m2', label: 'Surface (m²)', type: 'number' },
    {
      key: 'chauffe', label: 'Chauffe eau', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
  ],
  boulangerie: [
    {
      key: 'four', label: 'Four', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
    { key: 'cuisson_nocturne', label: 'Cuisson nocturne', type: 'bool' },
  ],
  froid: [
    { key: 'temperature_consigne', label: 'Température de consigne (°C)', type: 'number' },
    { key: 'volume_m3', label: 'Volume froid (m³)', type: 'number' },
    { key: 'saisonnalite_recolte', label: 'Pic saisonnier (récolte)', type: 'bool' },
  ],
  autre: [],
}

// ── Format monétaire (port exact de formatMoney) ─────────────────────────────
export function formatMoney(val) {
  if (val === null || val === undefined || isNaN(val)) return '0 MAD'
  return formatMAD(val, { decimals: 0 })
}

// ── Estimation des factures mensuelles depuis hiver/été ──────────────────────
// AGNR34 (D-AGNR-1 option (a)) — les MARCHES du moteur, plus de rampe : la
// facture d'été sur mai → octobre (indices 4 à 9), celle d'hiver ailleurs —
// même série que `horaire/conso.py::serie_mad_mensuelle`. Ces mois sont
// « estimés » : ils ne partent jamais en `factures_mensuelles_reelles`.
const MOIS_ETE_FACTURE = [4, 5, 6, 7, 8, 9]

// Les mois affichés sont toujours arrondis à l'entier (renderMonthlyInputs)
export function estimerMois(hiver, ete) {
  const h = hiver > 0 ? hiver : (ete || 0)
  const e = ete > 0 ? ete : h
  return Array.from({ length: 12 }, (_, m) => Math.round(MOIS_ETE_FACTURE.includes(m) ? e : h))
}

// CIQ128 — la doctrine de paliers ÉCRAN (pas de 5 kWc, tranche de 900 MAD,
// besoin lu sur la facture, balayage au payback) est SUPPRIMÉE : le C&I est dimensionné par le moteur serveur (CIQ107-CIQ122,
// pas de 5 kWc et horizon marginal côté `moteur_ci/taille.py`), le résidentiel
// par le moteur horaire serveur (U3-MOTEUR).

// ── Métrés de câble (règle fondateur 18/08, câble DC révisé 19/08 — PVCBL) ──
// Câble de terre AC 6 mm² : 25 m de base + 15 m par palier de 5 kWc — soit 40 m
// pour 5 kWc et 55 m pour 10 kWc, les deux cotes données par le fondateur.
// Câble solaire DC 6 mm² : voir `metreCableDcParPaires` ci-dessous — la règle
// « 60 m par palier » est SUPERSEDÉE par la règle par PAIRE de MPPT (19/08).
export const CABLE_DC_M_PAR_PALIER = 60
export const CABLE_TERRE_M_BASE = 25
export const CABLE_TERRE_M_PAR_PALIER = 15

// ── PVCBL (fondateur 19/08/2026) — métrage câble DC PAR PAIRE de MPPT ───────
// Bug constaté : un devis auto avait chiffré un ROULEAU de 100 m (produit au
// conditionnement rouleau, pas au mètre) avec une quantité en MÈTRES (60) →
// 71 400 MAD d'aberration (« who said 100m??? i wanted cable DC 6mm2 per
// metre »). Deux corrections ORTHOGONALES :
//  1. le produit retenu doit être vendu AU MÈTRE — voir `pickCable` dans
//     `autoFillLines`, qui exclut désormais tout conditionnement rouleau/
//     touret (jamais un repli silencieux sur un autre conditionnement) ;
//  2. le MÉTRAGE suit les PAIRES de câbles qui descendent du toit (30 m rouge
//     + 30 m noir = 60 m par paire), pas le palier de 5 kWc. Le nombre de
//     paires = le nombre d'entrées MPPT RÉELLEMENT UTILISÉES par l'onduleur
//     retenu — un calcul qui vit dans le moteur électrique
//     (apps/ventes/solar_design.py::string_design, core/electrique/chaines.py,
//     PV34) et exige des données que la composition simple (kWc + nb de
//     panneaux, sans plan de toiture ni fiche technique complète) n'a pas à ce
//     stade (`specs_solaire` ne sert pas encore `n_mppt` au frontend).
//     `nbPaires` est donc un paramètre EXPLICITE : un appelant qui a déjà ce
//     calcul (ex. l'écran Conception électrique, une fois branché) le
//     transmet ; SANS lui, repli fondateur EXPLICITEMENT AUTORISÉ : 1 paire —
//     jamais un calcul deviné.
export function metreCableDcParPaires(nbPaires = 1) {
  const n = Math.max(1, Math.round(Number(nbPaires) || 0) || 1)
  return n * CABLE_DC_M_PAR_PALIER
}

/** Longueur de câble de terre AC (m) pour `paliers` blocs de 5 kWc. */
export function metreCableTerre(paliers) {
  const n = Math.max(1, Math.round(Number(paliers) || 0))
  return CABLE_TERRE_M_BASE + n * CABLE_TERRE_M_PAR_PALIER
}

// ── Classification des lignes/produits (mêmes mots-clés que le moteur PDF) ───
// STKCAT15 — exportée telle quelle (aucun nouveau module) : la recherche
// transverse du catalogue (stock/catalogue.js) la réutilise pour normaliser
// accents/casse des deux côtés (requête ET botte de foin produit), au lieu
// de dupliquer une seconde normalisation qui pourrait diverger.
export const _norm = (s) =>
  (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export const isBattery = (d) => _norm(d).includes('batterie')
export const isHybridInverter = (d) => _norm(d).includes('onduleur') && _norm(d).includes('hybride') && !_norm(d).includes('cable')
// OFFGRID (fondateur, ajout produit onduleur hors réseau) — MÊME CONTRAT que
// le backend (apps/ventes/services.py côté serveur) : mot pour mot les mêmes
// mots-clés, jamais un seul divergent. « Onduleur hors réseau » contient le
// sous-mot « reseau » : sans l'exclusion NOT hybride ci-dessous et la garde
// symétrique dans `isReseauInverter`, cette désignation était classée
// (à tort) comme onduleur RÉSEAU — la ligne partait au panier « sans »,
// jamais composée, jamais reconnue en auto-remplissage.
const OFFGRID_KEYWORDS = ['off-grid', 'off grid', 'offgrid', 'hors reseau', 'autonome']
// AMOT57 — « hors-réseau », « off_grid » : trait d'union et souligné valent une
// espace AVANT tout test de mot-clé (même règle que `solar_classification.py`
// et le seeder, contrat `classification_lignes.json`).
const _sansSeparateurs = (s) => _norm(s).replace(/[-_]+/g, ' ')
const _isOffgridDesignation = (n) => OFFGRID_KEYWORDS.some(k => _sansSeparateurs(n).includes(_sansSeparateurs(k)))
// Incident fondateur 01/09 (round 2) — les VRAIS produits catalogue s'appellent
// « Deye off-Grid 6kw », SANS le mot « onduleur » : le prédicat strict
// ci-dessus (exigeant « onduleur ») les rendait invisibles (0 onduleur
// off-grid détecté, auto-remplissage en échec permanent). Élargi SANS perdre
// la précision : un nom off-grid qui ne dit pas « onduleur » n'est retenu que
// s'il n'appartient à AUCUNE AUTRE FAMILLE de produit — sinon (« Batterie
// off-grid », « Kit solaire off-grid », « Câble off-grid ») ce n'est
// manifestement pas l'onduleur lui-même.
const OTHER_FAMILY_KEYWORDS = [
  'batterie', 'panneau', 'panneaux', 'module', 'pompe', 'variateur',
  'structure', 'cable', 'coffret', 'disjoncteur', 'differentiel',
  'parafoudre', 'compteur', 'smart meter', 'wifi', 'kit', 'chargeur',
]
export const isOffgridInverter = (d) => {
  const n = _sansSeparateurs(d)
  if (!_isOffgridDesignation(n) || n.includes('hybride')) return false
  if (n.includes('onduleur')) return true
  return !OTHER_FAMILY_KEYWORDS.some(k => n.includes(k))
}
export const isReseauInverter = (d) => {
  const n = _sansSeparateurs(d)
  return n.includes('onduleur') && (n.includes('reseau') || n.includes('injection'))
    && !_isOffgridDesignation(n) && !n.includes('cable')
}
// Q1 (fondateur 20/08/2026) — TOUT onduleur, hybride/réseau/non classé (ex.
// micro-onduleur) : miroir exact de builder.py `_is_inverter` (« onduleur »
// suffit). Sert à repérer la ligne dont le prix réel provisionne le
// remplacement à l'année 12 — jamais un forfait sur l'investissement.
// AMOT57 — union des familles : « Deye off-Grid 6kw » est un onduleur.
export const isAnyInverter = (d) => !_norm(d).includes('cable') && (_norm(d).includes('onduleur') || isOffgridInverter(d))

// ── QJR92a (29/08/2026) — DÉTECTION PANNEAU ÉLARGIE CÔTÉ ÉCRAN ──────────────
// Le seul mot « panneau » rejetait les désignations que les vendeurs écrivent
// vraiment (« Module PV 550 W », « Canadian Solar TOPHiKu7 710 Wc ») : l'écran
// comptait alors 0 panneau et REFUSAIT l'enregistrement d'un devis dont la
// seule ligne panneau s'appelle ainsi, pendant que le PDF la classait
// correctement. La table de référence est la fixture de contrat
// `apps/ventes/contract_samples/classification_lignes.json` (QJR2), et le test
// de parité QJR91 fait tourner ces prédicats sur chacun de ses cas.
// Les marques ne suffisent JAMAIS seules : Canadian Solar, Huawei et consorts
// vendent aussi des onduleurs — il faut un watt lisible en plus.
const PANEL_MODULE_QUALIFIERS = ['pv', 'photovolta', 'solaire', 'solar']
const PANEL_BRANDS = [
  'canadian solar', 'canadien solar', 'jinko', 'longi', 'trina',
  'ja solar', 'risen', 'sunpower', 'qcells', 'q cells', 'astronergy',
  'znshine',
]
export const isPanel = (d, produitNom = '') => {
  const blob = _norm(`${d ?? ''} ${produitNom ?? ''}`)
  if (blob.includes('panneau')) return true
  // Exclusions d'abord : un onduleur / une batterie / un accessoire n'est
  // jamais un panneau, quelle que soit la marque écrite dessus.
  if (blob.includes('onduleur') || blob.includes('batterie')
      || blob.includes('smart meter') || blob.includes('wifi')
      || blob.includes('dongle')) return false
  if (blob.includes('module')
      && PANEL_MODULE_QUALIFIERS.some(q => blob.includes(q))) return true
  // Marque de panneau ET puissance lisible : sans watt, une marque seule reste
  // ambiguë — on préfère l'omission à un faux positif.
  return PANEL_BRANDS.some(b => blob.includes(b)) && WATT_RE.test(blob)
}

// F14 (26/08/2026) — panier « sans »/« avec » d'UNE ligne, MIROIR EXACT du
// moteur PDF canonique (quote_engine/builder.py `_repartir_options`,
// ligne 499-541) et de son jumeau serveur (`apps/ventes/utils/options.py`
// `_garder_dans_sans`/`_garder_dans_avec`) : une ligne DÉCLARÉE
// (`variante === 'sans'`/`'avec'`) TRANCHE SEULE et ne repasse JAMAIS par le
// filtre mot-clé — avant ce correctif, une batterie taguée 'sans' était
// encore retirée du panier « sans » par un second filtre mot-clé, alors que
// le PDF la facturait dans ce panier (F14 : écran et PDF divergeaient). Une
// ligne SANS `variante` ('' — tout devis hors « Les deux ») retombe sur les
// mots-clés, mot pour mot comme avant.
// AGNR36 — LE texte qui classe une LIGNE : désignation + nom du produit lié,
// miroir exact de `apps/ventes/utils/options.texte_classement` (QJR301). Une
// désignation retouchée à la main (« Stockage Dyness 5 kWh ») ne fait plus
// sortir la ligne de son panier. `produits` : catalogue de l'écran ; absent
// (ou non tableau — un `.filter(fn)` passe l'index) ⇒ désignation seule.
export function texteClassement(l, produits) {
  const nom = (Array.isArray(produits) ? _produitDeLigne(l, produits)?.nom : null)
    || l?.produit_nom || ''
  return `${l?.designation ?? ''} ${nom}`
}

export function appartientAuPanierSans(l, produits) {
  const v = l?.variante
  if (v === 'avec') return false
  if (v === 'sans') return true
  const t = texteClassement(l, produits)
  return !isBattery(t) && !isHybridInverter(t) && !isOffgridInverter(t)
}
export function appartientAuPanierAvec(l, produits) {
  const v = l?.variante
  if (v === 'sans') return false
  if (v === 'avec') return true
  return !isReseauInverter(texteClassement(l, produits))
}

// Q1 — prix TTC RÉEL des lignes onduleur d'une option, ou `null` si aucune
// identifiable. Miroir exact de builder.py `_cout_onduleur` : Σ qty × prix
// unitaire TTC des lignes onduleur — jamais un pourcentage de repli.
export function inverterCostFromLines(lines, produits) {
  let total = 0
  for (const l of lines || []) {
    if (!isAnyInverter(texteClassement(l, produits))) continue
    const qty = parseFloat(l.quantite) || 0
    const pu = parseFloat(l.prix_unit_ttc) || 0
    if (qty > 0 && pu > 0) total += qty * pu
  }
  return total > 0 ? Math.round(total * 100) / 100 : null
}

// ── PVOND — CONTRAT ONDULEUR & garde batterie PILOTÉ PAR LA DONNÉE ──────────
//
// MIROIR EXACT du backend (`apps/ventes/services.py` :
// `_batterie_compatible` / `_pick_batterie`, et le contrat lui-même dans
// `apps/stock/selectors.py`). Les deux côtés lisent la MÊME donnée, servie par
// l'API dans `produit.specs_solaire` :
//
//   { famille, plage_batterie_v: [min, max] | null, v_nominal, manquantes[] }
//
// Ce qui change par rapport au garde d'hier : une batterie ne s'accroche plus
// à un onduleur parce que son NOM ne dit pas « haute tension », mais parce que
// sa TENSION NOMINALE tombe dans la PLAGE BATTERIE que l'onduleur déclare.
// Le repli mot-clé reste EN PLACE et n'est pas un vestige : dès qu'une des deux
// données manque (catalogue ancien, produit saisi à la main, fixture de test),
// on retombe MOT POUR MOT sur le comportement PVG4 — jamais de régression
// silencieuse.

// Repli PVG4 : une batterie dont le nom dit « haute tension » n'est jamais
// auto-choisie pour un kit résidentiel basse tension.
// MIROIR EXACT de `_is_battery_basse_tension` (apps/ventes/services.py) : le
// prédicat Python exige AUSSI le mot « batterie » dans le nom. Le tronquer
// faisait de `batterieCompatible` — fonction EXPORTÉE, donc appelable hors du
// vivier pré-classé — une fonction qui ne se comporte pas comme sa jumelle.
const _batterieBasseTensionParMotCle = (p) => {
  const n = _norm(p?.nom)
  return n.includes('batterie') && !n.includes('haute tension')
}

// Fenêtre de tension batterie déclarée par un onduleur :
//   [min, max] → fenêtre réelle ; [0, 0] → « aucune batterie » (réseau) ;
//   null      → non déclarée (l'appelant retombe sur le mot-clé).
//
// RÈGLE CORRIGÉE (ordre fondateur 18/08/2026) — MIROIR EXACT de
// `stock.selectors.plage_batterie_onduleur` : un onduleur RÉSEAU (string
// on-grid) n'a PAS de port batterie. Rien de déclaré sur lui n'est pas un trou,
// c'est le cas nominal : sa FAMILLE vaut déclaration « aucune » ⇒ [0, 0].
// Le backend sert déjà cette valeur dans `specs_solaire.plage_batterie_v` ; ce
// repli local couvre le catalogue servi SANS bloc `specs_solaire` (produit
// saisi à la main, fixture) — sans lui, le mot-clé reprenait la main et pouvait
// accrocher une batterie à un onduleur réseau.
//
// L'ORDRE des deux mots-clés est signifiant et strictement celui de
// `stock.selectors.famille_onduleur` / `ventes.services.classer_produit` :
// « hybride » l'emporte sur « réseau », donc un « onduleur hybride injection
// réseau » reste un HYBRIDE (et sa plage reste EXIGÉE).
const _estOnduleurReseau = (nom) => isReseauInverter(nom) && !isHybridInverter(nom)

export function plageBatterieOnduleur(produit) {
  const plage = produit?.specs_solaire?.plage_batterie_v
  const replisReseau = () => (_estOnduleurReseau(produit?.nom) ? [0, 0] : null)
  if (!Array.isArray(plage) || plage.length !== 2) return replisReseau()
  const bas = Number(plage[0]); const haut = Number(plage[1])
  if (!Number.isFinite(bas) || !Number.isFinite(haut)) return replisReseau()
  return bas <= haut ? [bas, haut] : [haut, bas]
}

// La batterie entre-t-elle dans la plage de l'onduleur ? (miroir exact de
// `_batterie_compatible` côté backend, replis compris).
//
// RÈGLE CORRIGÉE (fondateur 2026-08-18) : le repli mot-clé ne s'applique QUE
// lorsque L'ONDULEUR ne déclare aucune plage. Dès qu'une plage existe, une
// candidate sans tension nominale — ou avec une tension nulle/illisible, donc
// une donnée INVALIDE — est EXCLUE. L'ancien repli acceptait, sous un onduleur
// 160-700 V, des batteries 48 V et plomb-gel 12 V sans aucune fiche technique,
// tout en écartant celles qui étaient correctement documentées : le garde-fou
// produisait exactement la composition qu'il devait empêcher.
export function batterieCompatible(batterie, plage) {
  if (!Array.isArray(plage)) return _batterieBasseTensionParMotCle(batterie)
  const [vMin, vMax] = plage
  if (!(vMax > 0)) return false        // onduleur réseau : aucune batterie
  const tension = Number(batterie?.specs_solaire?.v_nominal)
  // Plage EXIGÉE + tension inconnue/invalide ⇒ exclue (jamais le mot-clé).
  if (!Number.isFinite(tension) || tension <= 0) return false
  return tension >= vMin && tension <= vMax
}

// VERROU DE COMPLÉTUDE — les variables du contrat qui manquent à cet onduleur
// (liste vide = complet). Même patron que « prix à renseigner » : un onduleur
// incomplet est EXCLU de l'auto-composition et affiché grisé avec son motif,
// mais reste sélectionnable à la main.
//
// LA LISTE EST CALCULÉE PAR LE BACKEND (`stock.selectors.onduleur_specs_
// manquantes`, servie dans `specs_solaire.manquantes`) : c'est la source
// UNIQUE de la règle, donc les deux moitiés ne peuvent pas diverger. Depuis
// l'ordre fondateur du 18/08/2026 elle applique le contrat CONDITIONNEL —
// la « plage de tension batterie (V) » est réclamée aux onduleurs HYBRIDES
// (et aux familles indéterminées), jamais aux onduleurs RÉSEAU qui n'ont pas
// de port batterie. Un hybride sans plage reste écarté ET nommé.
export function onduleurSpecsManquantes(produit) {
  const manquantes = produit?.specs_solaire?.manquantes
  return Array.isArray(manquantes) ? manquantes : []
}

// Défauts TVA (réforme : 10 % panneaux PV, 20 % le reste).
export const TVA_PANNEAUX_DEFAUT = 10
export const TVA_STANDARD_DEFAUT = 20

// Taux TVA attendu d'après la désignation (réforme : 10 % panneaux PV, 20 % le
// reste). Sert UNIQUEMENT à signaler une incohérence à l'écran — jamais à
// recaler la valeur tapée (la frappe reste souveraine).
// DC4 — un objet {tvaPanneaux, tvaStandard} (repères société, Paramètres) peut
// surcharger les défauts ; sans lui, comportement historique inchangé.
export function expectedTvaForDesignation(designation, tvaConfig) {
  const panneaux = Number(tvaConfig?.tvaPanneaux) > 0
    ? Number(tvaConfig.tvaPanneaux) : TVA_PANNEAUX_DEFAUT
  const standard = Number(tvaConfig?.tvaStandard) > 0
    ? Number(tvaConfig.tvaStandard) : TVA_STANDARD_DEFAUT
  return isPanel(designation) ? panneaux : standard
}

// ── U1 (fondateur 20/08/2026) — LE COMPTE DE PANNEAUX EST UN PLAFOND ────────
// « 7 panneaux pour 5 kW : ça a TOUJOURS été 8 panneaux par 5 kW ». L'arrondi
// AU PLUS PROCHE (`Math.round`) sortait 7 panneaux pour 5 kWc en 710 Wc
// (round(7,042) = 7) : l'installation livrée était SOUS la puissance vendue.
// La règle est le PLAFOND : on ne descend jamais sous la cible annoncée.
//
// ÉPSILON — un compte de panneaux fait ALLER-RETOUR par le kWc
// (`kwp = nb * 710 / 1000`, puis re-dérivation), et 8 × 710 / 1000 × 1000 / 710
// vaut 8.000000000000002 en flottant : sans garde, le plafond ajouterait un
// 9ᵉ panneau fantôme à chaque aller-retour. La tolérance ramène un « à peine
// au-dessus d'un entier » sur cet entier ; elle ne peut PAS masquer un vrai
// besoin partiel (7,042 reste bien au-dessus de 7).
export const PANNEAUX_CEIL_EPS = 1e-9

export function plafondPanneaux(valeur) {
  const v = Number(valeur)
  if (!Number.isFinite(v) || v <= 0) return 0
  return Math.ceil(v - PANNEAUX_CEIL_EPS)
}

// Nombre de panneaux pour une taille cible (kWc) à la puissance panneau donnée.
// Utilisé pour préremplir depuis lead.taille_souhaitee_kwc. Au moins 1 panneau.
// QJR576 — LE wattage panneau par défaut (référence du simulateur), une
// seule constante au lieu de « 710 » recopié à chaque site.
export const PANEL_W_DEFAUT = 710

// QJR576 — inverse EXACT de `panneauxPourKwc` : kWc = n × W / 1000 (aucun
// arrondi ici — l'affichage arrondit, jamais la conversion). Compte ou
// wattage illisible → 0.
export function kwcPourPanneaux(nbPanneaux, panelW = PANEL_W_DEFAUT) {
  const n = parseFloat(nbPanneaux) || 0
  const w = parseFloat(panelW) || 0
  if (!(n > 0) || !(w > 0)) return 0
  return n * w / 1000
}

export function panneauxPourKwc(kwc, panelW = PANEL_W_DEFAUT) {
  const k = parseFloat(kwc) || 0
  const w = parseFloat(panelW) || PANEL_W_DEFAUT
  if (!(k > 0) || !(w > 0)) return 0
  return Math.max(1, plafondPanneaux(k * 1000 / w))
}

const WATT_RE = /(\d{3,4})\s*(?:wc|w)\b/i
const KW_RE = /(\d+(?:[.,]\d+)?)\s*(?:kw|kva)\b/i
const KWH_RE = /(\d+(?:[.,]\d+)?)\s*kwh\b/i

export function parseWatt(text) {
  const m = WATT_RE.exec(text || '')
  return m ? parseInt(m[1], 10) : null
}
export function parseKw(text) {
  // " 5 kWh" matcherait kW — exclure les kWh d'abord
  const cleaned = (text || '').replace(KWH_RE, ' ')
  const m = KW_RE.exec(cleaned)
  return m ? parseFloat(m[1].replace(',', '.')) : null
}
export function parseKwh(text) {
  const m = KWH_RE.exec(text || '')
  return m ? parseFloat(m[1].replace(',', '.')) : null
}
// Phase depuis le nom produit ; défaut Monophase comme le catalogue simulateur
export function parsePhaseIsTri(text) {
  return /tri\s*phas/i.test(text || '')
}

export function classifyProduct(nom) {
  const n = _norm(nom)
  if (!n) return null
  if (n.includes('cable')) return (n.includes('terre') || n.includes('mise a la terre')) ? 'cable_terre' : 'cable_dc'
  if (n.includes('onduleur') && n.includes('hybride')) return 'onduleur_hybride'
  // Hors réseau (site isolé) — AVANT le test réseau/injection ci-dessous :
  // « onduleur hors réseau » contient le sous-mot « réseau », il faut donc le
  // détourner vers cette famille avant que le test suivant ne le happe.
  if (isOffgridInverter(n)) return 'onduleur_offgrid'
  // mêmes mots-clés que le moteur PDF : un onduleur sans « réseau/injection »
  // (ex. micro-onduleur) n'est pas classé et reste sélectionnable à la main
  if (n.includes('onduleur') && (n.includes('reseau') || n.includes('injection'))) {
    return 'onduleur_reseau'
  }
  // STKCAT22 (paire indissociable avec classer_produit côté serveur) — la
  // reconnaissance élargie isPanel (panneau, module + qualifiant PV, marque +
  // wattage) remplace le seul mot « panneau ».
  if (isPanel(nom)) return 'panneau'
  if (n.includes('batterie')) return 'batterie'
  if (n.includes('structure')) return 'structure'
  if (n.includes('socle')) return 'socle'
  // Câbles (règle fondateur 18/08) : le câble de TERRE se distingue du câble
  // solaire DC par son mot-clé, sinon tout « câble » est un câble solaire DC.
  if (n.includes('smart meter')) return 'smart_meter'
  if (n.includes('wifi') || n.includes('dongle')) return 'wifi_dongle'
  if (n.includes('accessoire')) return 'accessoires'
  if (n.includes('tableau')) return 'tableau'
  if (n.includes('suivi')) return 'suivi'
  if (n.includes('installation')) return 'installation'
  if (n.includes('transport')) return 'transport'
  return null
}

// Prix TTC affiché depuis le prix de vente HT du stock.
// DC6 — le taux 20 n'est qu'un DÉFAUT de repli ; le taux réel (10 % panneaux,
// 20 % le reste, ou le taux standard édité de la société) est toujours passé
// par l'appelant via tauxTva.
// AGR216 — un taux 0 % saisi RESTE 0 % : seuls null / '' / NaN retombent sur le
// défaut (0 est « faux » en JS, `|| 20` le réécrivait en 20).
export function tauxTvaOuDefaut(taux, defaut = TVA_STANDARD_DEFAUT) {
  const t = parseFloat(taux)
  return Number.isFinite(t) ? t : defaut
}

export function ttcFromHt(prixVenteHt, tauxTva = TVA_STANDARD_DEFAUT) {
  const factor = 1 + tauxTvaOuDefaut(tauxTva) / 100
  return Math.round((parseFloat(prixVenteHt) || 0) * factor)
}

// ERR-QAH-FIG-EDITION-PU-TTC-ARRONDI — TTC unitaire AU CENTIME d'un prix HT
// DÉJÀ PERSISTÉ (réouverture `?edit=`). `ttcFromHt` arrondit au dirham — juste
// pour un prix catalogue, faux pour un prix enregistré : l'erreur (≤ 0,5 MAD
// par unité) était multipliée par la quantité (36 828 à l'écran contre
// 36 873,11 au devis) puis PERSISTÉE au ré-enregistrement. Au centime,
// `htFromTtc` retrouve exactement le HT d'origine (erreur < 0,005 ÷ (1 + t)).
// ATOT28 — le TTC affiché est le PLUS SIMPLE (entier, puis dixième, puis
// centime) que `htFromTtc` ramène EXACTEMENT au HT : un TTC entier tapé
// (1 160 @10 % → 1 054,55 HT) se rouvre 1 160, jamais 1 160,01 ; un prix
// catalogue 1 234,56 HT s'affiche 1 481,47 et revient 1 234,56.
export function ttcExactFromHt(prixHt, tauxTva = TVA_STANDARD_DEFAUT) {
  const taux = tauxTvaOuDefaut(tauxTva)
  const factor = 1 + taux / 100
  const ht = parseFloat(prixHt) || 0
  const brut = ht * factor
  const htAttendu = ht.toFixed(2)
  for (const echelle of [1, 10]) {
    const candidat = Math.round(brut * echelle) / echelle
    if (htFromTtc(candidat, taux) === htAttendu) return candidat
  }
  return Math.round(brut * 100) / 100
}

// ATOT28 — LA ligne d'écran née d'un produit du catalogue : TTC affiché au
// centime (`ttcExactFromHt`) et HT d'origine PORTÉ (`prixHtOrigine`), renvoyé
// tel quel à l'enregistrement tant que le vendeur n'a pas tapé de prix
// (`lignesEcranVersPayload`) — un prix catalogue repris sans retouche est
// stocké exactement et n'est pas « négocié ».
export function ligneProduitCatalogue(p, quantite) {
  const taux = tauxTvaOf(p)
  return {
    produit: String(p.id),
    designation: p.nom,
    quantite,
    prix_unit_ttc: ttcExactFromHt(p.prix_vente, taux),
    taux_tva: taux,
    prixHtOrigine: (parseFloat(p.prix_vente) || 0).toFixed(2),
  }
}

// Taux TVA d'un produit (réforme 2024–2026 : 10 % panneaux PV, 20 % le reste).
// DC7 — `Produit.tva` est la source AUTORITAIRE par ligne ; on la prend telle
// quelle quand elle est renseignée. DC6 — le repli n'est plus 20 en dur : il
// suit le taux standard de la société (tvaStandard, Paramètres), défaut 20.
export function tauxTvaOf(produit, tvaStandard) {
  const t = parseFloat(produit?.tva)
  if (Number.isFinite(t) && t >= 0) return t
  const std = Number(tvaStandard) > 0 ? Number(tvaStandard) : TVA_STANDARD_DEFAUT
  return std
}

// Conversion inverse au moment de l'enregistrement : le modèle stocke des
// prix HT à 2 décimales. Pour tout TTC saisi à la dirham près, l'aller-retour
// TTC → HT(2 déc.) → TTC réaffiché redonne exactement la valeur tapée.
export function htFromTtc(ttc, tauxTva = TVA_STANDARD_DEFAUT) {
  const factor = 1 + tauxTvaOuDefaut(tauxTva) / 100
  return ((parseFloat(ttc) || 0) / factor).toFixed(2)
}

// Capacité batterie totale depuis les lignes (port de app.js).
// BAT5DEF (26/08/2026) — RÈGLE FONDATEUR « zéro chiffre inventé » : avant ce
// correctif, une ligne batterie dont la désignation ne portait pas de kWh
// lisible contribuait un défaut FABRIQUÉ de 5,0 kWh (jamais dérivé d'aucune
// donnée réelle). Elle contribue désormais 0 — voir `batteryCapaciteInconnue`
// ci-dessous pour SIGNALER ce cas à l'écran plutôt que de le taire.
export function batteryKwhFromLines(lines, produits) {
  return lines.reduce((sum, l) => {
    const t = texteClassement(l, produits)
    if (!isBattery(t)) return sum
    // L-2OPT — une ligne taguée 'sans' (voir fusionnerVariantes) porte une
    // quantité issue de la composition SANS batterie, jamais destinée à
    // compter dans quelque capacité que ce soit ; sans tag (comportement
    // historique) ce garde-fou est un no-op (`undefined !== 'sans'`).
    if (l.variante === 'sans') return sum
    const qty = parseFloat(l.quantite) || 0
    return sum + qty * (parseKwh(t) ?? 0)
  }, 0)
}

// BAT5DEF — au moins une ligne batterie COMPTÉE (mêmes exclusions que
// `batteryKwhFromLines` : ni une ligne taguée 'sans') n'a pas de kWh lisible
// dans sa désignation → la capacité rendue par `batteryKwhFromLines`
// SOUS-ESTIME la vraie capacité (elle vaut 0 pour cette ligne, jamais un
// défaut inventé). Sert à afficher un avertissement honnête plutôt que de
// laisser croire que le chiffre est complet. `false` = soit aucune ligne
// batterie, soit toutes lisibles : comportement historique inchangé.
export function batteryCapaciteInconnue(lines, produits) {
  return (lines || []).some(l => {
    const t = texteClassement(l, produits)
    return isBattery(t) && l.variante !== 'sans' && parseKwh(t) == null
  })
}

// L-2OPT — nombre de PANNEAUX d'une option, avec la MÊME règle d'exclusion
// que `optionTotalsTTC`/`batteryKwhFromLines` : l'option SANS ignore les
// lignes taguées 'avec', l'option AVEC ignore celles taguées 'sans' ; une
// ligne sans tag (tout l'historique, et le cas non divergent de
// `fusionnerVariantes`) compte dans les DEUX. Sert à dériver le kWc PROPRE à
// chaque option depuis les lignes — sans quoi l'écran chiffre l'économie
// d'une composition avec le kWc de l'autre.
export function comptePanneauxOption(lines, option, produits = []) {
  const exclu = option === 'avec' ? 'sans' : 'avec'
  return (lines || []).reduce((sum, l) => {
    // AGNR18 — `isPanel` (désignation + nom du produit lié, comme
    // `builder.panneaux_et_watt_lu`), jamais le seul `/panneau/i` qui
    // ignorait « JA Solar 550 Wc ».
    if (!isPanel(l?.designation || '', _produitDeLigne(l, produits)?.nom || '')) return sum
    if (l.variante === exclu) return sum
    return sum + (parseFloat(l.quantite) || 0)
  }, 0)
}

// AGNR18 — le produit lié d'une ligne d'écran (catalogue chargé), sinon null.
function _produitDeLigne(l, produits) {
  if (!l?.produit || !Array.isArray(produits) || !produits.length) return null
  return produits.find(p => String(p.id) === String(l.produit)) || null
}

// AGNR18 — watt UNITAIRE LU d'une ligne panneau, même ordre que le serveur
// (`builder.panneaux_et_watt_lu`) : fiche technique du produit
// (Pmax) puis désignation puis nom du produit. `null` si illisible.
function _wattLigne(l, produits) {
  const p = _produitDeLigne(l, produits)
  const fiche = parseFloat(p?.fiche_technique?.pmax_wc ?? p?.pmax_wc ?? p?.puissance_wc)
  if (fiche > 0) return fiche
  return parseWatt(l?.designation || '') || parseWatt(p?.nom || '') || null
}

// AGNR18 — kWc des lignes panneau d'une option : somme quantité × watt LU de
// CHAQUE ligne ; `panelW` n'est que le repli d'une ligne au watt illisible.
// `null` sans ligne panneau ou sans aucun watt (lu ou repli).
export function kwcPanneauxOption(lines, option, panelW, produits = []) {
  const exclu = option === 'avec' ? 'sans' : 'avec'
  const repliW = parseFloat(panelW) || 0
  let n = 0
  let watts = 0
  for (const l of lines || []) {
    if (!isPanel(l?.designation || '', _produitDeLigne(l, produits)?.nom || '')) continue
    if (l.variante === exclu) continue
    const q = parseFloat(l.quantite) || 0
    const w = _wattLigne(l, produits) || repliW
    if (!(q > 0) || !(w > 0)) continue
    n += q
    watts += q * w
  }
  return n > 0 ? watts / 1000 : null
}

// QJR568 — le kWc réellement FACTURÉ par les lignes (branche SANS : commun +
// 'sans'), celui que le PDF dérive des lignes (builder.py). Le champ « nb
// panneaux » reste la CIBLE du dimensionnement (dry-run) ; ce kWc-ci alimente
// prix/kWc, prix cible, études C&I et l'aperçu horaire. `repli` (la cible)
// quand aucune ligne panneau ou aucun wattage lisible — jamais un 0 inventé.
// AGNR18 — le watt de CHAQUE ligne (fiche / désignation / produit), `panelW`
// seulement pour une ligne au watt illisible.
export function kwcFactureDesLignes(lines, panelW, repli, produits = []) {
  const kwc = kwcPanneauxOption(lines, 'sans', panelW, produits)
  return kwc != null && kwc > 0 ? kwc : repli
}

// ── L-2OPT — deux optimiseurs indépendants (fondateur 24/08) ─────────────────
// Un devis résidentiel « Les deux (Sans + Avec) » ne dimensionne plus les
// deux options sur le MÊME kWc : `autoFillLines` est appelé une fois par
// optimum (sans-batterie / avec-batterie, chacun son propre kWc — le moteur
// horaire serveur, `recommandation_avec`) et les deux
// compositions résultantes sont FUSIONNÉES ici, ligne par ligne (les deux
// tableaux partagent le même ordre de rôles canonique — `ordreLignes`/
// `marques` identiques des deux côtés — donc un appariement POSITIONNEL est
// fiable) :
//   • ligne identique (produit, désignation, prix unitaire TTC, taux TVA,
//     quantité) → UNE ligne commune, `variante: ''` ;
//   • ligne de RÔLE (correctif orchestrateur 25/08, aligné sur le backend
//     `services.fusionner_kits`) : batterie et onduleur hybride appartiennent
//     au panier AVEC, l'onduleur réseau au panier SANS — en cas de
//     divergence, seul le panier PROPRIÉTAIRE fait foi (UNE ligne, sa
//     variante), jamais deux exemplaires. Sans cela, une batterie taguée
//     'sans' (résidu de la composition superset) serait rangée — ET FACTURÉE
//     — côté « Sans batterie » par le PDF/l'aval, dont la règle est « la
//     déclaration prime sur les mots-clés » ;
//   • quantité (ou produit) divergente sur une ligne ordinaire → DEUX lignes,
//     `variante: 'sans'` / `'avec'`, chacune portant SA composition ;
//   • présente d'un seul côté (défensif) → la variante de son RÔLE d'abord,
//     celle de son côté sinon.
// Repli de sécurité : deux compositions IDENTIQUES (même kWc des deux côtés,
// le cas le plus courant) fusionnent en lignes 100 % `variante: ''` —
// résultat BYTE-IDENTIQUE à l'ancienne composition unique, aucune ligne
// variantée. Fonction PURE, testable indépendamment de l'écran.
function _memeLigne(a, b) {
  if (!a || !b) return false
  return String(a.produit ?? '') === String(b.produit ?? '')
    && String(a.designation ?? '') === String(b.designation ?? '')
    && (parseFloat(a.prix_unit_ttc) || 0) === (parseFloat(b.prix_unit_ttc) || 0)
    && (parseFloat(a.taux_tva) || 0) === (parseFloat(b.taux_tva) || 0)
    && (parseFloat(a.quantite) || 0) === (parseFloat(b.quantite) || 0)
}

// Rôle d'appartenance d'une ligne : 'avec' (batterie/onduleur hybride —
// panier avec batterie), 'sans' (onduleur réseau), '' (ligne ordinaire).
// Mêmes mots-clés que le split historique (`optionTotalsTTC`/builder.py).
function _roleVariante(l) {
  if (!l) return null
  const d = l.designation
  if (isBattery(d) || isHybridInverter(d) || isOffgridInverter(d)) return 'avec'
  if (isReseauInverter(d)) return 'sans'
  return ''
}

// ── QJR570 (D-QJR5-4) — RECOMPOSER FUSIONNE, ne remplace plus ───────────────
// Auto-remplir, « Appliquer cette taille » et « Recalculer » remplaçaient les
// lignes d'un bloc : un prix tapé, une section, une note, une option ou un
// produit ajouté à la main disparaissaient. `fusionnerRecomposition` apparie
// les anciennes lignes aux lignes générées PAR ID PRODUIT et :
//   • reporte prix_unit_ttc + prixManuel quand le prix avait été tapé ;
//   • prend la `variante` de la ligne générée (le découpage d'options est
//     celui de la nouvelle composition) ;
//   • réinsère à leur position relative les anciennes lignes absentes de la
//     composition qui portent une saisie humaine : sections, notes,
//     optionnelles, prix ou quantité figés, produits ajoutés à la main
//     (quantité > 0, pas issus d'une composition précédente — marqueur
//     écran `compose`) ; une ligne composée HIER et absente aujourd'hui, un
//     placeholder sans produit ou une ligne à quantité nulle ne survivent pas ;
//   • une quantité FIGÉE (`quantiteManuelle`) qui diffère de la quantité
//     recalculée est GARDÉE et remontée dans `conflits` (jamais en silence :
//     l'appelant le dit au vendeur, qui a confirmé avant la recomposition).
// Toute ligne générée porte `compose: true` (marqueur d'écran, jamais envoyé
// au serveur). Fonction PURE.
const _estLigneProduit = (l) => (l?.typeLigne ?? l?.type_ligne ?? 'produit') === 'produit'

export function lignesQuantiteFigee(lignes) {
  return (lignes || []).filter(l => _estLigneProduit(l) && l.quantiteManuelle && l.produit)
}

// Lignes en CONFLIT possible avec une nouvelle composition : seules les
// quantités figées à la main. Un prix tapé ou une option ajoutée sont gardés
// d'office par la fusion, sans question ; une ligne `compose` n'en est jamais une.
export function lignesManuellesEnConflitPossible(lignes) {
  return lignesQuantiteFigee(lignes)
}

// Applique une composition générée : 'garder' fusionne (saisies conservées),
// 'recalcule' ne garde EXACTEMENT que les lignes recalculées.
export function appliquerRecomposition(anciennes, generees, mode = 'garder') {
  if (mode === 'recalcule') {
    return {
      lignes: (Array.isArray(generees) ? generees : []).map(g => ({ ...g, compose: true })),
      conflits: [],
    }
  }
  return fusionnerRecomposition(anciennes, generees)
}

function _ancienneLigneAGarder(l) {
  if (!_estLigneProduit(l)) return true            // section / note
  if (l.optionnelle || l.prixManuel || l.quantiteManuelle) return true
  if (l.compose) return false                      // composition précédente
  return Boolean(l.produit) && (parseFloat(l.quantite) || 0) > 0
}

export function fusionnerRecomposition(anciennes, generees) {
  const olds = Array.isArray(anciennes) ? anciennes : []
  const gens = Array.isArray(generees) ? generees : []
  // File d'anciennes lignes produit par id (appariement dans l'ordre).
  const files = new Map()
  olds.forEach((l, i) => {
    if (!_estLigneProduit(l) || !l.produit) return
    const k = String(l.produit)
    if (!files.has(k)) files.set(k, [])
    files.get(k).push(i)
  })
  const appariee = new Map() // index ancienne → index générée
  const conflits = []
  const fusionnees = gens.map((g, gi) => {
    const file = g?.produit ? files.get(String(g.produit)) : null
    const oi = file && file.length ? file.shift() : null
    if (oi == null) return { ...g, compose: true }
    appariee.set(oi, gi)
    const o = olds[oi]
    // AGNR20 — la ligne ANCIENNE appariée est la base : la composition
    // n'écrase que ce qu'elle POSSÈDE — le produit, la quantité (si elle
    // n'est pas figée), la variante et le prix (s'il n'est pas tapé). Taux
    // de TVA (0 % + base légale), désignation, remise de ligne, groupe villa,
    // lot, rôle… restent ceux du vendeur. Une clé que seule la composition
    // porte est reprise d'elle.
    const base = {
      ...g,
      ...o,
      compose: true,
      produit: g.produit,
      variante: g.variante ?? '',
      quantite: g.quantite,
      prix_unit_ttc: g.prix_unit_ttc,
    }
    if (o.prixManuel) {
      base.prix_unit_ttc = o.prix_unit_ttc
      base.prixManuel = true
    }
    if (o.optionnelle) base.optionnelle = true
    if (o.quantiteManuelle) {
      base.quantiteManuelle = true
      if ((parseFloat(o.quantite) || 0) !== (parseFloat(g.quantite) || 0)) {
        conflits.push({
          designation: o.designation || g.designation || '',
          figee: String(o.quantite),
          recalculee: String(g.quantite),
        })
      }
      base.quantite = o.quantite
    }
    return base
  })
  // Réinsertion des anciennes lignes gardées à leur position RELATIVE.
  const apres = gens.map(() => [])
  const avant = gens.map(() => [])
  const fin = []
  olds.forEach((l, i) => {
    if (appariee.has(i) || !_ancienneLigneAGarder(l)) return
    for (let j = i - 1; j >= 0; j--) {
      if (appariee.has(j)) { apres[appariee.get(j)].push(l); return }
    }
    for (let j = i + 1; j < olds.length; j++) {
      if (appariee.has(j)) { avant[appariee.get(j)].push(l); return }
    }
    fin.push(l)
  })
  const lignes = []
  fusionnees.forEach((l, gi) => { lignes.push(...avant[gi], l, ...apres[gi]) })
  lignes.push(...fin)
  return { lignes, conflits }
}

export function fusionnerVariantes(lignesSans, lignesAvec) {
  const sans = Array.isArray(lignesSans) ? lignesSans : []
  const avec = Array.isArray(lignesAvec) ? lignesAvec : []
  const n = Math.max(sans.length, avec.length)
  const out = []
  for (let i = 0; i < n; i++) {
    const s = sans[i]
    const a = avec[i]
    const rs = _roleVariante(s)
    const ra = _roleVariante(a)
    if (s && a && rs === ra && rs === 'avec') {
      // Batterie / onduleur hybride : le panier AVEC fait foi. Identiques →
      // ligne commune (split mots-clés historique) ; divergents → SA version,
      // taguée — jamais un exemplaire fantôme dimensionné pour « sans ».
      out.push(_memeLigne(s, a) ? { ...s, variante: '' } : { ...a, variante: 'avec' })
      continue
    }
    if (s && a && rs === ra && rs === 'sans') {
      // Onduleur réseau : le panier SANS fait foi (symétrique du cas avec).
      out.push(_memeLigne(s, a) ? { ...s, variante: '' } : { ...s, variante: 'sans' })
      continue
    }
    if (s && !a) { out.push({ ...s, variante: rs || 'sans' }); continue }
    if (a && !s) { out.push({ ...a, variante: ra || 'avec' }); continue }
    if (_memeLigne(s, a)) { out.push({ ...s, variante: '' }); continue }
    // Paire ordinaire divergente (ou dérive défensive de rôles) : chaque côté
    // garde sa version — taguée par son RÔLE quand il en a un.
    out.push({ ...s, variante: rs || 'sans' })
    out.push({ ...a, variante: ra || 'avec' })
  }
  return out
}

// ── Catégories du catalogue simulateur (clés de brand_catalog.json) ──────────
// Le sélecteur de produits est groupé exactement selon ces catégories.
export const PRODUCT_CATEGORIES = [
  ['onduleur_reseau', 'Onduleur Injection'],
  ['onduleur_hybride', 'Onduleur Hybride'],
  ['onduleur_offgrid', 'Onduleurs hors réseau'],
  ['panneau', 'Panneaux'],
  ['batterie', 'Batterie'],
  // STKCAT2 — rôle GÉNÉRIQUE de structure (émis pour un produit dont le nom
  // ne dit ni « acier » ni « alu »), puis ses deux alias DÉPRÉCIÉS, conservés
  // pour toujours : un réglage de marque enregistré hier reste lisible.
  ['structure', 'Structures'],
  ['structure_acier', 'Structures acier'],
  ['structure_alu', 'Structures aluminium'],
  ['socle', 'Socles'],
  ['cable_dc', 'Câble solaire DC'],
  ['cable_terre', 'Câble de terre AC'],
  ['smart_meter', 'Smart Meter'],
  ['wifi_dongle', 'Wifi Dongle'],
  ['accessoires', 'Accessoires'],
  ['tableau', 'Tableau De Protection AC/DC'],
  ['installation', 'Installation'],
  ['transport', 'Transport'],
  ['suivi', 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans'],
]

// STKCAT24 — bucket sur le rôle EFFECTIF résolu côté serveur
// (`role_devis_effectif`, STKCAT21 : déclaré → catégorie → mots-clés du nom)
// quand il est présent ; repli sur `classifyProduct(nom)` sinon — un produit
// sans ce champ (fixture ancienne, écran pas encore rechargé) garde un
// comportement BYTE-IDENTIQUE à avant STKCAT24.
export function groupProduitsByCategory(produits) {
  const buckets = new Map(PRODUCT_CATEGORIES.map(([key]) => [key, []]))
  const autres = []
  for (const p of produits) {
    const effectif = p.role_devis_effectif
    let type = effectif ?? classifyProduct(p.nom)
    if (type === 'structure') {
      if (effectif) {
        // Rôle EFFECTIF générique : la matière (acier/alu) ne se lit QUE dans
        // le nom, jamais un défaut « acier » silencieux — sans l'un ni
        // l'autre mot-clé, la ligne reste dans le seau générique `structure`
        // (label PRODUCT_CATEGORIES ci-dessus : « Structures »).
        if (_norm(p.nom).includes('acier')) type = 'structure_acier'
        else if (_norm(p.nom).includes('alu')) type = 'structure_alu'
      } else {
        // Repli mots-clés historique (rôle effectif absent/null) — byte-
        // identique à avant STKCAT24 : défaut ACIER sans mot-clé « alu ».
        type = _norm(p.nom).includes('alu') ? 'structure_alu' : 'structure_acier'
      }
    }
    if (type && buckets.has(type)) buckets.get(type).push(p)
    else autres.push(p)
  }
  const groups = PRODUCT_CATEGORIES
    .map(([key, label]) => ({ label, items: buckets.get(key) }))
    .filter(g => g.items.length)
  if (autres.length) groups.push({ label: 'Autres', items: autres })
  return groups
}

// Libellé FR d'un rôle ROLES_AUTO_COMPOSITION (mirroir des clés PRODUCT_CATEGORIES).
// STKCAT2 — le repli ne montre JAMAIS la clé BRUTE au commercial : avant que
// le rôle générique `structure` n'entre dans PRODUCT_CATEGORIES,
// `roleLabel('structure')` affichait « structure » en toutes lettres dans le
// message « marque épinglée introuvable au stock ». Un rôle hors miroir est
// désormais humanisé en français (underscores → espaces, capitale initiale).
export function roleLabel(role) {
  const trouve = PRODUCT_CATEGORIES.find(([key]) => key === role)
  if (trouve) return trouve[1]
  const brut = String(role ?? '').replace(/_/g, ' ').trim()
  if (!brut) return 'Équipement'
  return brut.charAt(0).toUpperCase() + brut.slice(1)
}

// ── PVORD (fondateur 19/08/2026) — ordre PAR DÉFAUT des lignes de devis ──────
// Frontend de `ParametresGammes.ordre_lignes` (apps/ventes/models.py) : une
// liste de rôles PRODUCT_CATEGORIES/ROLES_AUTO_COMPOSITION dans l'ordre voulu
// pour les PROCHAINS devis. Sans préférence (absente/vide) : ordre CANONIQUE
// de composition inchangé — zéro régression tant que rien n'est enregistré.

// Trie une liste de lignes TAGUÉES `[role, ligne]` par préférence de rôle.
// Un rôle PRÉSENT dans `ordreLignes` est classé à sa position ; un rôle
// ABSENT garde son rang canonique mais TOUJOURS après tout rôle
// explicitement préféré — tri STABLE (jamais un ex-æquo aléatoire) : les
// deux lignes « batterie » (5 kWh / 10 kWh) gardent leur ordre relatif entre
// elles quand leur rôle est préféré, ou l'un envers l'autre à la fin sinon.
export function orderLinesByRolePreference(taggedLines, ordreLignes) {
  if (!Array.isArray(ordreLignes) || !ordreLignes.length) {
    return taggedLines.map(([, ligne]) => ligne)
  }
  const rang = (role) => {
    const idx = ordreLignes.indexOf(role)
    return idx === -1 ? Infinity : idx
  }
  return taggedLines
    .map((entree, i) => ({ entree, i }))
    .sort((a, b) => {
      const ra = rang(a.entree[0])
      const rb = rang(b.entree[0])
      return ra !== rb ? ra - rb : a.i - b.i
    })
    .map(({ entree }) => entree[1])
}

// Dérive la séquence de rôles depuis les lignes COURANTES de l'écran (bouton
// « Enregistrer cet ordre comme ordre par défaut ») : classification RÉUTILISÉE
// (aucun nouveau mot-clé — même classifyProduct que groupProduitsByCategory),
// dédupliquée en gardant la PREMIÈRE occurrence (l'ordre écran des DEUX lignes
// batterie 5/10 kWh ne compte que pour un seul rang « batterie »), et les
// lignes sans classification reconnue (section/note, désignation libre) sont
// simplement ignorées — jamais un rôle inventé.
export function deriveRoleOrderFromLines(lines) {
  const seen = new Set()
  const order = []
  for (const l of (lines ?? [])) {
    let role = classifyProduct(l.designation)
    if (!role) continue
    // STKCAT10 — MÊME règle d'émission que la composition (écran ET serveur) :
    // un libellé qui ne dit ni « acier » ni « alu » (une pergola) donne le rôle
    // GÉNÉRIQUE `structure`, jamais `structure_acier` par défaut — sinon
    // l'ordre enregistré ne retrouverait jamais la ligne réellement composée.
    if (role === 'structure') role = structureRoleForName(l.designation)
    if (seen.has(role)) continue
    seen.add(role)
    order.push(role)
  }
  return order
}

// ── PVMRQ — marque préférée par gamme/rôle (fondateur 18/08/2026) ────────────
// Frontend de `ParametresGammes.marques` (backend, ROLES_AUTO_COMPOSITION —
// MIROIR EXACT des clés `PRODUCT_CATEGORIES` ci-dessus) : quand une marque est
// épinglée pour un rôle, elle GAGNE TOUJOURS — le vivier de candidats de ce
// rôle est restreint À ELLE SEULE avant toute autre logique (wattage/prix/
// compatibilité). Sans marque réglée pour ce rôle (clé absente ou vide),
// comportement byte-identique à l'historique.

// Marque épinglée pour ce rôle dans la carte `marques` ({role: marque}) de la
// gamme active, ou '' si aucune préférence — ne lève jamais.
function _marqueEpinglee(marques, role) {
  const carte = marques && typeof marques === 'object' ? marques : null
  const m = carte ? carte[role] : null
  return typeof m === 'string' ? m.trim() : ''
}

// Le produit porte-t-il la marque épinglée ? MIROIR EXACT de
// `_marque_correspond` (apps/ventes/services.py) : `produit.marque` (champ
// structuré) prioritaire, égalité EXACTE une fois normalisée ; à défaut (marque
// non renseignée sur la fiche), son `nom` DOIT seulement CONTENIR la marque,
// jamais l'égaler. Réutilise `_norm` (accents/casse) — le backend ne compare
// que la casse (`casefold`), mais un accent divergent ne doit pas non plus
// faire manquer une marque bien réelle côté écran.
function _marqueCorrespond(produit, marque) {
  const cible = _norm(marque)
  if (!cible) return false
  const marqueProduit = _norm(produit?.marque)
  if (marqueProduit) return marqueProduit === cible
  return _norm(produit?.nom).includes(cible)
}

// Restreint un vivier de candidats à la marque épinglée pour `role` (carte
// `marques` de la gamme active). Sans préférence réglée : vivier RENVOYÉ TEL
// QUEL (comportement historique). Marque réglée mais AUCUN candidat ne la
// porte : vivier VIDE — JAMAIS un repli silencieux sur une autre marque — et
// l'entrée `{ role, marque }` est consignée dans `manquantes` (dédupliquée par
// rôle, même patron que `onduleursIncomplets`).
function _filtrerParMarque(pool, role, marques, manquantes, vusRoles) {
  const source = pool ?? []
  const marque = _marqueEpinglee(marques, role)
  if (!marque) return source
  const filtres = source.filter(p => _marqueCorrespond(p, marque))
  if (!filtres.length && vusRoles && !vusRoles.has(role)) {
    vusRoles.add(role)
    manquantes.push({ role, marque })
  }
  return filtres
}

// ── Indexation par type des produits du stock ─────────────────────────────────
// STKCAT24 — même repli que `groupProduitsByCategory` : `role_devis_effectif`
// (STKCAT21) d'abord, mots-clés du nom ENSUITE, seulement quand le champ est
// absent/null — un produit sans ce champ indexe exactement comme avant.
function indexProduits(produits) {
  const byType = {}
  for (const p of produits) {
    const type = p.role_devis_effectif ?? classifyProduct(p.nom)
    if (!type) continue
    if (!byType[type]) byType[type] = []
    byType[type].push(p)
  }
  return byType
}

const lineFrom = (p, quantite, ttcOverride = null) => ((p && ttcOverride == null)
  // ATOT28 — prix catalogue repris tel quel (HT d'origine porté).
  ? ligneProduitCatalogue(p, quantite)
  : {
      produit: p ? String(p.id) : '',
      designation: p ? p.nom : '',
      quantite,
      prix_unit_ttc: p || ttcOverride != null ? ttcOverride : 0,
      taux_tva: p ? tauxTvaOf(p) : 20,
    })

// Ligne vide placeholder (désignation canonique, pas de produit)
const placeholder = (designation, quantite) => ({
  produit: '', designation, quantite, prix_unit_ttc: 0, taux_tva: 20,
})

// ── Table par défaut au chargement (port de getDefaultProductLines) ──────────
// Quantités par défaut du simulateur ; les lignes « spéciales » (onduleurs,
// panneaux, batteries) restent à choisir, les autres pointent sur le produit
// canonique du stock avec son prix TTC (équivalent de autofillRowPrice).
// PVORD — `ordreLignes` (optionnel, `ParametresGammes.ordre_lignes`) réordonne
// le résultat par rôle préféré ; absent/vide = ordre canonique ci-dessous,
// byte-identique à l'historique (voir `orderLinesByRolePreference`).
export function defaultProductLines(produits, ordreLignes) {
  const byType = indexProduits(produits)
  // AGNR27 — garde « aucun produit sans prix » : un rôle pointe le premier
  // produit PRIX CONNU, ou reste sans produit (placeholder) — jamais un
  // article à 0 MAD (ex. « Structure bac acier C&I » du seed C&I).
  const first = (type) => (byType[type] ?? []).find(_hasPrix) ?? null
  const exactOr = (type, needle) => {
    const pool = byType[type] ?? []
    return pool.find(p => _hasPrix(p) && _norm(p.nom).includes(needle)) ?? null
  }
  const row = (p, designation, quantite) =>
    p ? lineFrom(p, quantite) : placeholder(designation, quantite)

  const tagged = [
    ['onduleur_reseau', placeholder('Onduleur réseau', 1)],
    ['onduleur_hybride', placeholder('Onduleur hybride', 1)],
    ['smart_meter', row(first('smart_meter'), 'Smart Meter', 0)],
    ['wifi_dongle', row(first('wifi_dongle'), 'Wifi Dongle', 0)],
    ['panneau', placeholder('Panneaux', 0)],
    ['batterie', placeholder('Batterie', 1)],
    ['batterie', placeholder('Batterie', 0)],
    ['structure_acier', row(exactOr('structure', 'acier'), 'Structures acier', 0)],
    ['structure_alu', row(exactOr('structure', 'alu'), 'Structures aluminium', 0)],
    ['socle', row(first('socle'), 'Socles', 0)],
    ['accessoires', row(first('accessoires'), 'Accessoires', 1)],
    ['tableau', row(first('tableau'), 'Tableau De Protection AC/DC', 1)],
    ['installation', row(first('installation'), 'Installation', 1)],
    ['transport', row(first('transport'), 'Transport', 1)],
    ['suivi', row(first('suivi'), 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 1)],
  ]
  return orderLinesByRolePreference(tagged, ordreLignes)
}

/* STKCAT10 — LE RÔLE ÉMIS POUR LA LIGNE STRUCTURE, MIROIR EXACT DU SERVEUR
   (`apps/ventes/domain/composition.py::role_structure_du_produit`, règle
   d'émission écrite au contrat `contract_samples/devis_composition.json`) :
   le rôle suit le NOM DU PRODUIT RETENU, jamais le bouton demandé.
     · le nom porte encore « acier »          ⇒ `structure_acier` ;
     · le nom porte encore « alu »/« aluminium » ⇒ `structure_alu` ;
     · ni l'un ni l'autre (pergola, carport, bac lesté…) ⇒ le rôle GÉNÉRIQUE
       `structure` (déjà inscrit dans PRODUCT_CATEGORIES par STKCAT2).
   `voulu` départage un nom qui porterait LES DEUX mots-clés, et c'est aussi
   le rôle rendu quand aucun nom n'est lisible — comportement d'hier, au
   caractère près. */
export function structureRoleForName(nom, voulu = 'acier') {
  const prefere = _norm(voulu).startsWith('alu') ? 'alu' : 'acier'
  const autre = prefere === 'alu' ? 'acier' : 'alu'
  const role = { alu: 'structure_alu', acier: 'structure_acier' }
  const n = _norm(nom)
  if (!n) return role[prefere]
  if (n.includes(prefere)) return role[prefere]
  if (n.includes(autre)) return role[autre]
  return 'structure'
}

/* STKCAT10 — LE PRODUIT DE STRUCTURE EXPLICITEMENT CHOISI, résolu comme le
   serveur le résout : dans le catalogue COMPLET déjà scopé société (pas dans
   le vivier « structures nommées », sinon une pergola resterait invisible) et
   APRÈS la garde de prix — un id qui désignerait un produit non tarifé, ou
   celui d'une autre société, ne résout RIEN et la composition retombe sur le
   bouton acier/alu. Ni le filtre par mot-clé ni la marque épinglée du rôle ne
   s'y appliquent : un choix explicite ne se re-choisit pas. */
export function structureChoisie(produits, structureProduitId) {
  if (structureProduitId == null || structureProduitId === '') return null
  const cible = String(structureProduitId)
  return (produits ?? []).find(
    (p) => String(p?.id) === cible && _hasPrix(p)) ?? null
}

// ADEV69 — `autoFillLines`, le second composeur résidentiel (sans appelant de
// production depuis CIQ126/CIQ128), est SUPPRIMÉ : D-QJR5-9 « un seul
// composeur, côté serveur » — le survivant est `apps/ventes/domain/composition.py`
// (dry-run `POST /ventes/devis/composition/`, appliqué par useCompositionEcran).
// Son absence est épinglée par `solar.codeMortAdev69.test.mjs`.

// ══ Multi-marchés (2026-06) ═══════════════════════════════════════════════════

// CIQ228 — la valorisation C&I écran (rachat 82-21 net, injection) est
// SUPPRIMÉE : la revente MT et ses mentions viennent UNIQUEMENT du serveur
// (`economie_ci.revente`). `KWH_PRICE` reste : le RÉSIDENTIEL le lit encore
// (repli de `computeROI` et défaut `quoteLogic.kwhPrice` du générateur).

// ── Pompage solaire (mode Agricole) ───────────────────────────────────────────
// AGNR26 — `HEURES_POMPAGE_DEFAUT` retiré : plus rien ne le lisait depuis
// AGR114/AGR130 (production heure par heure côté serveur).

// QJR546 — exporté : le générateur saute (et nomme) les lignes d'un modèle
// dont le produit n'a plus de prix, avec la MÊME garde que l'auto-remplissage.
export const _hasPrix = (p) => (parseFloat(p.prix_vente) || 0) > 0

const _isPompe = (n) => n.includes('pompe ') || n.startsWith('pompe')

// QX20 — classification « pompe » exposée (garde d'équipement du générateur) :
// une désignation de ligne est une pompe si son nom normalisé le dit. Utilise
// le même _norm que les autres classificateurs.
export function isPompe(designation) {
  return _isPompe(_norm(designation || ''))
}
