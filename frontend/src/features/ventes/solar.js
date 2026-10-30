// Solar math + catalogue auto-fill, ported 1:1 from RedaSolar/devis-simulator
// (constants.py, roi_router.py, autofill.py / autofill_router.py, app.js).
// The simulator is the source of truth: prices are handled in TTC (like the
// simulator UI) and only converted to HT at save time. Pure functions, no I/O.
// The premium PDF engine computes its own figures server-side — never fed here.

import { formatMAD } from '../../lib/format.js'
import {
  _norm, _produitDeLigne, classifyProduct, isBattery, isPanel, parseKwh, parseWatt, texteClassement,
} from './calc/classification.js'

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
