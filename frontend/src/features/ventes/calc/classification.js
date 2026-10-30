// SPL207 — Classification des produits et des lignes de l'écran devis
// (panneau, batterie, familles d'onduleurs, PVOND, parse*, classifyProduct,
// isPompe). Les mots-clés sont ceux du moteur PDF (quote_engine/builder.py,
// règle #4) — INCHANGÉS. DÉPLACEMENT PUR depuis features/ventes/solar.js
// (aucune logique changée).

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

const _isPompe = (n) => n.includes('pompe ') || n.startsWith('pompe')

// QX20 — classification « pompe » exposée (garde d'équipement du générateur) :
// une désignation de ligne est une pompe si son nom normalisé le dit. Utilise
// le même _norm que les autres classificateurs.
export function isPompe(designation) {
  return _isPompe(_norm(designation || ''))
}

// AGNR18 — le produit lié d'une ligne d'écran (catalogue chargé), sinon null.
export function _produitDeLigne(l, produits) {
  if (!l?.produit || !Array.isArray(produits) || !produits.length) return null
  return produits.find(p => String(p.id) === String(l.produit)) || null
}
