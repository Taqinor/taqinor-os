// Parity tests for the solar generator math against the devis-simulator
// (source of truth). Run with: node --test src/features/ventes/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
// QJR109 — le garde-fou « le lead ne réinitialise pas le marché choisi » est
// désormais EXÉCUTÉ sur le reducer pur, au lieu d'être cherché dans le source.
import {
  sizingReducer, ETAT_INITIAL,
} from './quote/sizingReducer.js'
import {
  DEFAULT_MONTHLY_BILLS, estimerMois, formatMoney, ttcFromHt, htFromTtc, groupProduitsByCategory, PRODUCTIBLE_NET_FACTOR, batteryKwhFromLines,
} from './solar.js'
// STKCAT10 — sélecteur de structures piloté par le catalogue (SPL202 : calc/lignesDefaut.js).
import { structureRoleForName, structureChoisie } from './calc/lignesDefaut.js'
import {
  isReseauInverter, batterieCompatible,
  plageBatterieOnduleur, isBattery, isHybridInverter, isAnyInverter, inverterCostFromLines,
} from './calc/classification.js'
import { FALLBACK_KWH_PRICE, twoBillsSavings } from './calc/tarifs.js'

// Reflet du catalogue seedé (prix HT = TTC simulateur / 1.2, 2 décimales)
const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
// BATHOMO/F4 (fondateur 26/08/2026) — `quantite_stock` par défaut à 500,
// même convention que le catalogue seedé (`seed_catalogue.py`) : le stock-
// gating batterie n'exclut QUE ce qu'un test met explicitement à 0, jamais
// les fixtures existantes qui ne parlaient pas encore de stock.
const P = (nom, ttc, qty = 500) => ({ id: ++_id, nom, prix_vente: ht(ttc), quantite_stock: qty })
const SEEDED = [
  P('Onduleur réseau Huawei 5kW Monophasé', 14000),
  P('Onduleur réseau Huawei 10kW Monophasé', 18000),
  P('Onduleur réseau Huawei 10kW Triphasé', 20000),
  P('Onduleur réseau Huawei 12kW Monophasé', 20000),
  P('Onduleur réseau Huawei 15kW Triphasé', 23000),
  P('Onduleur réseau Huawei 20kW Triphasé', 28000),
  P('Onduleur réseau Huawei 25kW Triphasé', 35000),
  P('Onduleur réseau Huawei 50kW Triphasé', 55000),
  P('Onduleur réseau Huawei 100kW Triphasé', 78000),
  P('Onduleur réseau Huawei 150kW Triphasé', 123000),
  P('Onduleur hybride Deye 5kW Monophasé', 17000),
  P('Onduleur hybride Deye 10kW Monophasé', 28000),
  P('Onduleur hybride Deye 10kW Triphasé', 28000),
  P('Onduleur hybride Deye 15kW Triphasé', 36000),
  P('Onduleur hybride Deye 20kW Triphasé', 48000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Panneau Jinko 710W', 1400),
  P('Batterie Dyness 5 kWh', 17000),
  P('Batterie Dyness 10 kWh', 30000),
  P('Batterie Lithium 5 kWh', 15500),
  P('Batterie Gel 2.2 kWh', 5000),
  P('Structures acier', 500),
  P('Structures aluminium', 850),
  P('Socles', 80),
  P('Smart Meter', 1800),
  P('Wifi Dongle', 1200),
  P('Accessoires', 2000),
  P('Tableau De Protection AC/DC', 2000),
  P('Installation', 4800),
  P('Transport', 1000),
  P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
]

const CLEAN_INT = (v) => Number.isInteger(v)

test('estimateur de factures : marches hiver / été du moteur (AGNR34), valeurs entières', () => {
  const months = estimerMois(600, 400)
  assert.equal(months.length, 12)
  months.forEach(v => assert.ok(CLEAN_INT(v), `mois non entier: ${v}`))
  assert.deepEqual(months, [600, 600, 600, 600, 400, 400, 400, 400, 400, 400, 600, 600])
})

test('estimateur : été vide → 12 mois plats', () => {
  assert.deepEqual(estimerMois(500, 0), Array(12).fill(500))
})

test('factures par défaut : la série saisonnière du simulateur', () => {
  assert.deepEqual(DEFAULT_MONTHLY_BILLS,
    [500, 450, 400, 380, 360, 500, 700, 680, 580, 480, 430, 480])
  DEFAULT_MONTHLY_BILLS.forEach(v => assert.ok(CLEAN_INT(v)))
})

test('formatMoney : toujours arrondi à l\'entier (jamais de partie fractionnaire)', () => {
  // Le séparateur de milliers dépend de l'ICU (espace ou point) — ce qui
  // compte est que la valeur formatée soit l'entier arrondi, sans fraction.
  for (const v of [0, 833.333, 19600.056, 1400.004, 121224]) {
    const s = formatMoney(v)
    assert.ok(s.endsWith(' MAD'))
    assert.equal(s.replace(/\D/g, ''), String(Math.round(v)),
      `valeur fractionnaire dans ${s}`)
  }
  assert.equal(formatMoney(null), '0 MAD')
})

test('prix TTC depuis le HT du stock : retombe sur le TTC catalogue exact', () => {
  for (const ttc of [1400, 14000, 20000, 17000, 500, 80, 1000, 4800, 5000]) {
    assert.equal(ttcFromHt(ht(ttc)), ttc)
  }
})

test('prix saisi librement : aller-retour TTC → HT stocké → TTC sans dérive', () => {
  // Un prix arbitraire tapé par l'utilisateur (pas un multiple de 10/100)
  // doit revenir exactement après enregistrement HT et réaffichage TTC.
  for (const typed of [1453, 999, 1, 7, 123457, 2849, 18351]) {
    const stockedHt = htFromTtc(typed)            // ce que la base enregistre
    assert.equal(String(stockedHt), Number(stockedHt).toFixed(2))  // 2 décimales (modèle)
    assert.equal(ttcFromHt(stockedHt), typed,
      `TTC ${typed} a dérivé via HT ${stockedHt}`)
  }
  // TVA non standard : même garantie
  assert.equal(Math.round(parseFloat(htFromTtc(1453, 10)) * 1.10), 1453)
})

test('sélecteur produits : groupé selon les catégories du catalogue simulateur', () => {
  const groups = groupProduitsByCategory([
    ...SEEDED,
    // Les deux câbles Nexans au mètre ont leurs propres groupes depuis le 18/08.
    { id: 998, nom: 'Câble solaire Nexans 6 mm² (au mètre)', prix_vente: '12.00' },
    { id: 999, nom: 'Câble de terre Nexans 6 mm² (au mètre)', prix_vente: '12.00' },
    // …et un produit non classable alimente toujours « Autres ».
    { id: 1000, nom: 'Échafaudage roulant', prix_vente: '850' },
  ])
  const labels = groups.map(g => g.label)
  assert.deepEqual(labels, [
    'Onduleur Injection', 'Onduleur Hybride', 'Panneaux', 'Batterie',
    'Structures acier', 'Structures aluminium', 'Socles',
    'Câble solaire DC', 'Câble de terre AC', 'Smart Meter',
    'Wifi Dongle', 'Accessoires', 'Tableau De Protection AC/DC',
    'Installation', 'Transport',
    'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 'Autres',
  ])
  const by = (label) => groups.find(g => g.label === label)
  assert.equal(by('Onduleur Injection').items.length, 10)
  assert.equal(by('Onduleur Hybride').items.length, 5)
  assert.equal(by('Panneaux').items.length, 2)
  assert.equal(by('Batterie').items.length, 4)
  assert.equal(by('Structures acier').items.length, 1)
  assert.equal(by('Structures aluminium').items.length, 1)
  // les deux câbles au mètre tombent chacun dans SON groupe, jamais « Autres »
  assert.equal(by('Câble solaire DC').items.length, 1)
  assert.equal(by('Câble de terre AC').items.length, 1)
  // produit non solaire → groupe Autres
  assert.equal(by('Autres').items[0].nom, 'Échafaudage roulant')
})

// QJR109 — CETTE GARDE-CI RESTE UNE LECTURE DU SOURCE, ET C'EST DÉLIBÉRÉ.
// Elle porte sur des ATTRIBUTS DOM (`noValidate` du formulaire, `step="any"`
// sur chaque champ nombre) : c'est une règle FONDATEUR (« l'écran ne doit
// JAMAIS snapper ni rejeter un nombre tapé ») dont la seule autre expression
// possible est un rendu React (spec RTL). La convertir en pur est IMPOSSIBLE ;
// la retirer DESSERRERAIT la garde. Elle reste donc telle quelle, nommée pour
// que la prochaine passe ne la prenne pas pour un oubli.
// QJR101 — les champs nombres du marché ont suivi les quatre panneaux
// (`generator/Panneau*.jsx`). La garde les SUIT au lieu de rester verte en ne
// regardant plus qu'une fraction de l'écran : sans ce recalage elle passait de
// 20 champs surveillés à 3. Un cinquième panneau de marché rejoint cette liste.
// QJR244 — la carte « Factures Électriques » (factures hiver/été, grille des
// 12 mois, bloc facture réelle du client) a quitté les trois panneaux réseau
// pour un composant partagé unique (`CarteFacturesElectriques.jsx`) : ses
// champs nombre ne sont plus lus TROIS FOIS (une fois par panneau copié-collé)
// mais UNE seule fois — la garde ajoute ce fichier, sinon elle retomberait
// silencieusement de 34 à ~4 champs surveillés.
const SURFACES_SAISIE = [
  '../../pages/ventes/DevisGenerator.jsx',
  '../../pages/ventes/generator/PanneauResidentiel.jsx',
  '../../pages/ventes/generator/PanneauIndustriel.jsx',
  '../../pages/ventes/generator/PanneauCommercial.jsx',
  '../../pages/ventes/generator/PanneauAgricole.jsx',
  '../../pages/ventes/generator/CarteFacturesElectriques.jsx',
  // QJR5 (lot 4) — conso annuelle + grille MT des panneaux Industriel et
  // Commercial, désormais UN composant partagé.
  '../../pages/ventes/generator/BlocEtudeReseau.jsx',
  // QJR624 — l'échéancier éditable de l'Édition complète.
  '../../pages/ventes/generator/CarteEcheancier.jsx',
  // QJR667 — le formulaire « Lots / multi-sites » (champ ordre).
  './LotsMultiSites.jsx',
  // SPL55 — la carte « Paramètres Techniques » (puissance cible, panneaux,
  // puissance panneau) a quitté la coquille : ses 3 champs nombre restent sous garde.
  '../../pages/ventes/generator/CarteParametresTechniques.jsx',
  // R1-09 / R1-10 (22/11) — les champs d'argent sont des `ChampDecimal` (texte à
  // clavier décimal : un Chrome en anglais filtrait la virgule d'un champ
  // « number », 12,5 → 125). La table de lignes et le rail d'argent rejoignent
  // la garde, qui compte ces champs au même titre.
  '../../pages/ventes/DevisLineRow.jsx',
  '../../pages/ventes/generator/RailArgent.jsx',
  // R1-09 (22/11) — le taux d'actualisation C&I est un `ChampDecimal` : la carte rejoint la garde.
  '../../pages/ventes/generator/CarteEconomieCi.jsx',
]
const CHAMP_DECIMAL = '../../pages/ventes/generator/ChampDecimal.jsx'

test('garde-fou : plus aucune contrainte step restrictive sur l\'écran', () => {
  const ici = dirname(fileURLToPath(import.meta.url))
  const lire = (rel) => readFileSync(join(ici, rel), 'utf-8')
  assert.ok(lire(SURFACES_SAISIE[0]).includes('noValidate'),
    'le formulaire doit être noValidate (aucun rejet navigateur)')
  let champsNombre = 0
  for (const rel of SURFACES_SAISIE) {
    const jsx = lire(rel)
    for (const bad of ['step="100"', 'step="10"', 'step="1"', 'step="0.01"']) {
      assert.ok(!jsx.includes(bad), `contrainte de saisie restrictive dans ${rel} : ${bad}`)
    }
    // Seul le curseur (type="range") garde un pas ; aucun champ nombre n'en a.
    const numberSteps = jsx.split('type="number"').slice(1)
      .map(chunk => /step="([^"]+)"/.exec(chunk)?.[1])
    numberSteps.forEach(s => assert.equal(s, 'any', `${rel} : champ nombre sans step="any"`))
    champsNombre += numberSteps.length
    // R1-09 — un `ChampDecimal` porte `step="any"` lui-même ; un appelant ne
    // lui en impose jamais un autre (le `/>` borne l'élément).
    const decimaux = jsx.split('<ChampDecimal').slice(1).map(c => c.slice(0, c.indexOf('/>')))
    decimaux.forEach(c => assert.ok(!/step=/.test(c), `${rel} : un ChampDecimal reçoit un step`))
    champsNombre += decimaux.length
  }
  // ACAL1210 — aucun champ de saisie du générateur n'est plus un `type="number"`
  // natif (un Chrome en anglais lit « 12,5 » comme 125) : seules les lignes de
  // commentaire peuvent encore citer la chaîne.
  for (const rel of SURFACES_SAISIE.filter(r => r.includes('/generator/'))) {
    const champsNatifs = lire(rel).split('\n')
      .filter(l => !/^\s*(\/\/|\*|\{?\/\*)/.test(l) && l.includes('type="number"'))
    assert.deepEqual(champsNatifs, [], `${rel} : champ type="number" natif restant`)
  }
  // Le champ décimal lui-même : texte à clavier décimal, `step="any"`, rien ne
  // le borne (ni min, ni max, ni pattern).
  const champ = lire(CHAMP_DECIMAL)
  const balise = champ.slice(champ.indexOf('<Champ type='), champ.indexOf('/>', champ.indexOf('<Champ type=')))
  assert.ok(balise.includes('type="text" inputMode="decimal" step="any"'),
    'ChampDecimal : texte, clavier décimal, step="any"')
  assert.doesNotMatch(balise, /\b(min|max|pattern)=/)
  // Cliquet : 26 champs nombres mesurés sur les SIX surfaces (recalé par
  // QJR244, qui a fait passer le socle des factures — hiver/été + grille des
  // 12 mois (une seule expression `.map()` en SOURCE, jamais comptée 12 fois)
  // + facture réelle, 4 occurrences en source — de « recopié dans les trois
  // panneaux réseau » (compté 3 fois, 12 occurrences) à « un seul composant
  // partagé » (compté 1 fois, 4 occurrences) : 34 − 12 + 4 = 26. Un champ qui
  // migrerait vers un fichier absent de la liste ci-dessus ferait tomber ce
  // compte au lieu de sortir de la garde en silence.
  // Recalé à 25 par le lot 4 QJR5 : conso annuelle + grille MT, recopiées
  // dans Industriel ET Commercial (4 occurrences), passent dans le composant
  // partagé `BlocEtudeReseau.jsx` (ajouté à la liste) — 2 champs + 1 mention
  // `type="number"` de son commentaire d'en-tête = 3 : 26 − 4 + 3 = 25.
  // Recalé à 46 par R1-09/R1-10 (22/11) : 41 occurrences mesurées sur les dix
  // surfaces d'avant (le cliquet à 25 avait pris du retard) ; les 4 champs
  // d'argent de la carte factures passent de « number » à `ChampDecimal`
  // (comptés à l'identique) ; la table de lignes (3) et le rail d'argent (2)
  // entrent sous garde : 41 + 5 = 46. Puis 45 : les 9 champs du panneau
  // Agricole passent aussi en `ChampDecimal` (comptés à l'identique) et la
  // mention `type="number"` de son commentaire d'en-tête (jamais un champ) a
  // disparu : 46 − 1 = 45. Puis 42 : Industriel, Commercial et le reste de
  // `BlocEtudeReseau.jsx` passent en `ChampDecimal` (comptés à l'identique) ;
  // seules les trois mentions `type="number"` de leurs commentaires d'en-tête
  // (jamais des champs) disparaissent : 45 − 3 = 42. Puis 43 (mesuré) : les trois
  // champs de `CarteParametresTechniques.jsx` passent en `ChampDecimal` (comptés à
  // l'identique) et la carte C&I `CarteEconomieCi.jsx` (taux d'actualisation,
  // 1 champ) entre sous garde : 42 + 1 = 43.
  assert.ok(champsNombre >= 43,
    `seulement ${champsNombre} champs nombres sous garde (43 attendus)`)
})

// QJR109 — CETTE GARDE A CESSÉ DE LIRE LE SOURCE. Elle cherchait la chaîne
// `!sizing.touche.mode` à moins de 120 caractères de `LEAD_TYPE_TO_MODE` dans
// `DevisGenerator.jsx` : une épingle qui rougit sur un reformatage et reste
// verte si le garde-fou est déplacé dans une branche morte. Depuis QJR87/QJR99
// le garde-fou est un ÉTAT du reducer PUR — il est ici EXÉCUTÉ.
test('garde-fou : choisir un lead ne réinitialise JAMAIS le mode choisi', () => {
  // Le commercial a choisi son marché à la main…
  const choisi = sizingReducer(ETAT_INITIAL,
    { type: 'MARCHE_CHANGE', mode: 'industriel' })
  assert.equal(choisi.modeInstallation, 'industriel')
  assert.equal(choisi.touche.mode, true,
    'un choix UTILISATEUR doit marquer le drapeau')

  // …puis il sélectionne un lead d'un AUTRE marché : le choix tient.
  const apresLead = sizingReducer(choisi, {
    type: 'LEAD_APPLIQUE', lead: { type_installation: 'residentiel' } })
  assert.equal(apresLead.modeInstallation, 'industriel',
    'le lead ne doit pas réinitialiser le marché déjà choisi')

  // Sans choix préalable, le lead pose bien le marché (le garde-fou ne gèle
  // pas l'écran) — et ne marque PAS le drapeau : ce n'est pas un choix.
  const vierge = sizingReducer(ETAT_INITIAL, {
    type: 'LEAD_APPLIQUE', lead: { type_installation: 'agricole' } })
  assert.equal(vierge.modeInstallation, 'agricole')
  assert.equal(vierge.touche.mode, false)

  // Un `type_installation` inconnu ne change rien (jamais un marché inventé).
  assert.equal(
    sizingReducer(ETAT_INITIAL,
      { type: 'LEAD_APPLIQUE', lead: { type_installation: 'sous-marin' } })
      .modeInstallation,
    'residentiel')
})

// ── Tolérance d'orthographe Dyness / Deyness (fondateur, 2026-08-18) ─────────
// La marque s'écrit « Dyness » ; le catalogue a longtemps écrit « Deyness ».
// Une base pas encore migrée (ou un produit saisi à la main) doit continuer
// d'alimenter le vivier batterie — sinon l'auto-remplissage retomberait sur
// TOUTES les batteries du catalogue et proposerait un module Gel ou Lithium
// générique à la place du bon.
// ── PVG4 — garde HAUTE TENSION (BAT-DYN-HV-16, miroir EXACT du garde backend
// _is_battery_basse_tension, fondateur 2026-08-18) ────────────────────────────
// La batterie Dyness haute tension (16 kWh) est réservée aux dossiers haute
// tension : jamais auto-choisie en kit résidentiel, même moins chère et même
// si sa capacité coïncide par coïncidence avec la cible basse tension.
// ── BATHOMO/F4 (fondateur 26/08/2026, revue adversariale) — MIROIR EXACT du
// moteur serveur (apps/ventes/services.py::composition_residentielle) :
// homogène par calibre, EN STOCK seulement, prix TTC total le plus bas,
// plafond de modules respecté. Mêmes cas que
// apps/ventes/tests/test_bathomo_banque_homogene.py côté backend.
// ── PVOND — garde batterie PILOTÉ PAR LA DONNÉE + verrou de complétude ──────
// Les deux tests PVG4 ci-dessus restent VRAIS et inchangés : sans
// `specs_solaire` au catalogue (fixtures ci-dessus), le repli mot-clé garde la
// main à l'identique. Les tests qui suivent vérifient ce que le mot-clé ne
// savait PAS faire.
const _specs = (p, specs) => ({
  ...p,
  specs_solaire: {
    famille: null, plage_batterie_v: null, v_nominal: null, manquantes: [],
    ...specs,
  },
})

// ── PVOND — LE REPLI MOT-CLÉ N'EST PLUS UN RATTRAPAGE UNIVERSEL ─────────────
// Règle corrigée (fondateur 2026-08-18) : le mot-clé ne parle QUE lorsque
// l'ONDULEUR ne déclare aucune plage. Dès qu'une plage existe, une candidate
// sans tension nominale — ou avec une tension nulle, donc une donnée INVALIDE —
// est exclue. Miroir exact de `_batterie_compatible` (apps/ventes/services.py).
test('PVOND — plage déclarée + batterie SANS fiche ⇒ exclue (jamais le mot-clé)', () => {
  const sansFiche = P('Batterie Dyness 5 kWh', 16000)
  assert.equal(batterieCompatible(sansFiche, [40, 60]), false)
  // …mais SANS plage déclarée, le repli mot-clé garde la main à l'identique.
  assert.equal(batterieCompatible(sansFiche, null), true)
})

test('PVOND — v_nominal = 0 est une donnée INVALIDE, pas une absence', () => {
  const zero = _specs(P('Batterie Dyness 5 kWh', 16000),
                      { famille: 'batterie', v_nominal: 0 })
  // Python teste `40 <= 0.0 <= 60` et REFUSE : le JS refuse désormais aussi.
  assert.equal(batterieCompatible(zero, [40, 60]), false)
})

test('PVOND — le repli mot-clé exige « batterie » dans le nom (miroir Python)', () => {
  // `_is_battery_basse_tension` exige "batterie" ET pas "haute tension".
  assert.equal(batterieCompatible(P('Batterie Dyness 5 kWh', 16000), null), true)
  assert.equal(
    batterieCompatible(P('Batterie Dyness haute tension 16 kWh', 48000), null),
    false)
  // Un produit qui n'est pas une batterie n'est jamais « compatible ».
  assert.equal(batterieCompatible(P('Onduleur hybride Deye 10kW', 28000), null),
               false)
})

// ── PVOND — CONTRAT CONDITIONNEL À LA FAMILLE (ordre fondateur 18/08/2026) ──
// La plage de tension batterie décrit un PORT qui n'existe pas sur un onduleur
// RÉSEAU : la réclamer grisait la moitié du bandeau « Onduleur(s) non
// chiffrable(s) » pour cette SEULE variable. Elle n'est donc exigée que des
// HYBRIDES (et des familles indéterminées). Miroir de
// `stock.selectors.plage_batterie_onduleur` / `famille_onduleur`.
test('PVOND — un onduleur RÉSEAU sans plage déclarée vaut « aucune batterie »', () => {
  const reseau = P('Onduleur réseau Huawei 10kW Triphasé', 20000)
  assert.deepEqual(plageBatterieOnduleur(reseau), [0, 0])
  // …et aucune batterie ne s'y accroche : le mot-clé ne reprend PAS la main.
  assert.equal(
    batterieCompatible(P('Batterie Dyness 5 kWh', 16000), plageBatterieOnduleur(reseau)),
    false)
})

test('PVOND — un onduleur HYBRIDE sans plage reste « non déclarée » (repli intact)', () => {
  const hybride = P('Onduleur hybride Deye 10kW Triphasé', 28000)
  assert.equal(plageBatterieOnduleur(hybride), null)
  // Sans plage, le repli mot-clé PVG4 garde la main, byte-identique à hier.
  assert.equal(
    batterieCompatible(P('Batterie Dyness 5 kWh', 16000), plageBatterieOnduleur(hybride)),
    true)
})

test('PVOND — « hybride » l\'emporte sur « réseau » dans le nom (miroir Python)', () => {
  // Même ORDRE que `classer_produit` / `famille_onduleur` : un hybride qui
  // mentionne aussi l'injection réseau reste un HYBRIDE, plage EXIGÉE.
  assert.equal(plageBatterieOnduleur(P('Onduleur hybride injection réseau 10kW', 1)), null)
  // Une référence nue (famille indéterminée) reste exigeante elle aussi.
  assert.equal(plageBatterieOnduleur(P('Onduleur Deye SUN-10K', 1)), null)
})

test('PVOND — une plage SERVIE par l\'API l\'emporte sur le défaut de famille', () => {
  // Le jour où un Huawei est vendu AVEC stockage, la fenêtre déclarée est lue.
  const reseauAvecBatterie = _specs(P('Onduleur réseau Huawei 5kW Monophasé', 14000),
                                    { famille: 'onduleur', plage_batterie_v: [350, 560] })
  assert.deepEqual(plageBatterieOnduleur(reseauAvecBatterie), [350, 560])
})

// ── QX19 — autoFillLines surface le wattage RÉEL + nb panneaux (anti-mismatch)
// ── QF8 — Smart Meter + Clé Wifi UNIQUEMENT sur onduleur Huawei ─────────────
// ══ Multi-marchés ═════════════════════════════════════════════════════════════
import {
  expectedTvaForDesignation,
} from './solar.js'

// ══ Classification pompe (le moteur pompage JS est retiré, AGR132) ═══════════

const OSP_CURVE_30_8 = { debits_m3h: [0, 12, 24, 30, 36, 39], hmt_m: [91, 85, 70, 60, 43, 34] }
const OSP_CURVE_30_13 = { debits_m3h: [0, 12, 24, 30, 36, 39], hmt_m: [148, 138, 114, 98, 70, 55] }

const VEICHI_FIXTURE = [
  { id: 901, nom: 'AFFICHEUR VARIATEUR SI22', prix_vente: '350.00', pompe_kw: null, tension_v: null },
  { id: 902, nom: 'VARIATEUR VEICHI SI22 2.2KW 220V', prix_vente: '1316.67', pompe_kw: '2.2', tension_v: 220 },
  { id: 903, nom: 'VARIATEUR VEICHI SI23 2.2KW 220V', prix_vente: '2108.33', pompe_kw: '2.2', tension_v: 220 },
  { id: 904, nom: 'VARIATEUR VEICHI SI23 5.5KW 380V', prix_vente: '2708.33', pompe_kw: '5.5', tension_v: 380 },
  { id: 905, nom: 'VARIATEUR VEICHI SI23 7.5KW 380V', prix_vente: '3333.33', pompe_kw: '7.5', tension_v: 380 },
  { id: 906, nom: 'VARIATEUR VEICHI SI23 11KW 380V', prix_vente: '4125.00', pompe_kw: '11', tension_v: 380 },
]

const ospPump = (overrides = {}) => ({
  id: 950, nom: 'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)',
  prix_vente: '12500.00', pompe_cv: '10', pompe_kw: '7.5', tension_v: 380,
  courbe_pompe: OSP_CURVE_30_8, ...overrides,
})
const ospPump13 = (overrides = {}) => ({
  id: 951, nom: 'Pompe immergée OSP 30/13 — 15 CV / 11 kW (3", 380V)',
  prix_vente: '0.00', pompe_cv: '15', pompe_kw: '11', tension_v: 380,
  courbe_pompe: OSP_CURVE_30_13, ...overrides,
})

// ── QJR130 — jamais de repli silencieux sur un matériel sous-dimensionné ──────
// ── QJR131 — `_hasPrix` couvre AUSSI panneaux/structures/socles/câble/
// installation/transport (avant : réservé pompe/variateur/afficheur) : un
// candidat sans prix n'est plus jamais chiffré, repli sur un placeholder
// (aucun `produit`, jamais un article gratuit à id réel) ─────────────────────
const POMPAGE_ARGS = {
  cv: '5.5', alim: 'tri', typePompe: 'immergee', distance: '35', structureType: 'acier',
}
const zeroed = (produits, matches) => produits.map(p =>
  matches.some(m => p.nom.includes(m)) ? { ...p, prix_vente: '0.00' } : p)

// ══ Réforme TVA 2024–2026 : 10 % panneaux PV, 20 % le reste ═════════════════
import { ttcFromHt as _ttc, htFromTtc as _htf, tauxTvaOf } from './solar.js'

test('TVA 10 % panneau : aller-retour TTC↔HT lossless (1 400 ↔ 1 272,73)', () => {
  assert.equal(_htf(1400, 10), '1272.73')
  assert.equal(_ttc('1272.73', 10), 1400)
  // taux du produit : 10 pour un panneau seedé, 20 par défaut
  assert.equal(tauxTvaOf({ tva: '10.00' }), 10)
  assert.equal(tauxTvaOf({ tva: '20.00' }), 20)
  assert.equal(tauxTvaOf({}), 20)
  assert.equal(tauxTvaOf(null), 20)
  // tout TTC tapé à la dirham près reste exact aux deux taux
  for (const ttc of [999, 1400, 13571, 250000]) {
    assert.equal(_ttc(_htf(ttc, 10), 10), ttc)
    assert.equal(_ttc(_htf(ttc, 20), 20), ttc)
  }
})

// ── DC4 — TVA panneaux société surcharge le défaut, sinon 10 %/20 % ───────────
test('DC4 expectedTvaForDesignation : config société surcharge, défauts sinon', () => {
  // Défauts réforme : panneau 10, autre 20
  assert.equal(expectedTvaForDesignation('Panneau 710W'), 10)
  assert.equal(expectedTvaForDesignation('Onduleur réseau'), 20)
  // Config société : panneaux 7, standard 19
  const cfg = { tvaPanneaux: 7, tvaStandard: 19 }
  assert.equal(expectedTvaForDesignation('Panneau 710W', cfg), 7)
  assert.equal(expectedTvaForDesignation('Onduleur', cfg), 19)
  // Config invalide (0/NaN) → repli défauts
  assert.equal(expectedTvaForDesignation('Panneau', { tvaPanneaux: 0 }), 10)
})

// ── DC6/DC7 — tauxTvaOf : produit.tva autoritaire, repli sur standard société ─
test('DC6/DC7 tauxTvaOf : Produit.tva prioritaire, repli standard société', () => {
  // DC7 — produit.tva renseigné = autoritaire, ignore le standard société
  assert.equal(tauxTvaOf({ tva: '10' }, 19), 10)
  assert.equal(tauxTvaOf({ tva: '20' }), 20)
  // DC6 — sans taux produit, repli sur le standard société (défaut 20)
  assert.equal(tauxTvaOf({}, 19), 19)
  assert.equal(tauxTvaOf({}), 20)
  // repli invalide (0) → 20
  assert.equal(tauxTvaOf({}, 0), 20)
})

// ── QX40 — pompage : compatibilité phase/tension pompe ↔ variateur ──────────
const _curvePump = (nom, kw, tension, prix, courbe) => ({
  id: ++_id, nom, pompe_kw: kw, tension_v: tension, prix_vente: prix,
  courbe_pompe: courbe,
})
// courbe simple : à HMT 60 m délivre 40 m³/h (≥ le débit demandé de 30)
const _COURBE = { debits_m3h: [0, 40, 60], hmt_m: [90, 60, 30] }

const ETUDE_BASE = {
  kwp: 300, consoMensuelleKwh: 20000, dayUsagePct: 80,
  totalTtc: 900000, kwhPrice: 1.4, efficiency: 0.8,
}

// STKCAT24 — `groupProduitsByCategory` bucket sur le rôle EFFECTIF résolu
// côté serveur (`role_devis_effectif`, STKCAT21) quand il est présent, mots-
// clés du nom en repli. Pin explicite : la fixture SEEDED existante (aucun
// produit n'y porte `role_devis_effectif`) doit grouper à l'IDENTIQUE
// d'avant STKCAT24 — même sélecteur, même compte par étiquette que le test
// « sélecteur produits : groupé selon les catégories du catalogue simulateur »
// ci-dessus (jamais retouché).
test('STKCAT24 — sans role_devis_effectif (fixture ancienne) : groupage byte-identique à avant', () => {
  const groups = groupProduitsByCategory(SEEDED)
  const by = (label) => groups.find(g => g.label === label)
  assert.equal(by('Onduleur Injection').items.length, 10)
  assert.equal(by('Onduleur Hybride').items.length, 5)
  assert.equal(by('Panneaux').items.length, 2)
  assert.equal(by('Batterie').items.length, 4)
  assert.equal(by('Structures acier').items.length, 1)
  assert.equal(by('Structures aluminium').items.length, 1)
  // Un `role_devis_effectif` explicitement NULL (et pas seulement absent) doit
  // suivre exactement le même repli que le champ absent.
  const avecNull = SEEDED.map(p => ({ ...p, role_devis_effectif: null }))
  const groupsNull = groupProduitsByCategory(avecNull)
  assert.deepEqual(
    groupsNull.map(g => [g.label, g.items.length]),
    groups.map(g => [g.label, g.items.length]))
})

test('STKCAT24 — role_devis_effectif="panneau" sans mot-clé dans le nom : bucketé Panneaux', () => {
  const sansMotCle = { id: 9001, nom: 'Module ABC-550', prix_vente: '750',
    role_devis_effectif: 'panneau' }
  const groups = groupProduitsByCategory([...SEEDED, sansMotCle])
  const panneaux = groups.find(g => g.label === 'Panneaux')
  assert.ok(panneaux.items.some(p => p.id === 9001),
    'le produit sans mot-clé mais au rôle effectif "panneau" doit rejoindre le groupe Panneaux')
})

test('STKCAT24 — structure : rôle effectif générique + mot-clé matière du nom (acier/alu/aucun)', () => {
  const acier = { id: 9010, nom: 'Charpente acier galvanisée', prix_vente: '400',
    role_devis_effectif: 'structure' }
  const alu = { id: 9011, nom: 'Support aluminium sur mesure', prix_vente: '450',
    role_devis_effectif: 'structure' }
  const generique = { id: 9012, nom: 'Pergola', prix_vente: '500',
    role_devis_effectif: 'structure' }
  const groups = groupProduitsByCategory([acier, alu, generique])
  const by = (label) => groups.find(g => g.label === label)
  assert.equal(by('Structures acier')?.items?.[0]?.id, 9010)
  assert.equal(by('Structures aluminium')?.items?.[0]?.id, 9011)
  // Aucun mot-clé matière dans le nom → seau générique 'structure', rendu
  // sous l'étiquette 'Structures' (clé ajoutée par STKCAT2 à PRODUCT_CATEGORIES).
  assert.equal(by('Structures')?.items?.[0]?.id, 9012)
})

test('STKCAT24 — structure_acier/alu DÉCLARÉ explicitement : bucketé tel quel, jamais re-décidé par le nom', () => {
  // Le nom ne dit ni « acier » ni « alu » — seul le rôle DÉCLARÉ tranche.
  const declareAcier = { id: 9020, nom: 'Charpente sur mesure', prix_vente: '400',
    role_devis_effectif: 'structure_acier' }
  const declareAlu = { id: 9021, nom: 'Support sur mesure', prix_vente: '450',
    role_devis_effectif: 'structure_alu' }
  const groups = groupProduitsByCategory([declareAcier, declareAlu])
  const by = (label) => groups.find(g => g.label === label)
  assert.equal(by('Structures acier')?.items?.[0]?.id, 9020)
  assert.equal(by('Structures aluminium')?.items?.[0]?.id, 9021)
})

/* ── STKCAT10 — LE SÉLECTEUR DE STRUCTURES PILOTÉ PAR LE CATALOGUE ──────────
   Décision fondateur 16/09/2026 : le bouton acier/aluminium est remplacé par
   un choix de PRODUIT. Les trois garanties épinglées ici :
     1. SANS produit choisi, la composition est BYTE-IDENTIQUE à l'historique
        (la paire acier + alu, l'une à nbPanneaux, l'autre à 0) ;
     2. AVEC un produit choisi, UNE SEULE ligne structure, au nom du produit ;
     3. le RÔLE émis suit le NOM du produit, exactement comme le serveur
        (`composition.py::role_structure_du_produit`) — donc une pergola porte
        le rôle GÉNÉRIQUE `structure`, jamais `structure_acier` par défaut. */

// Une PERGOLA : catégorie TYPÉE `structure`, mais dont le NOM ne contient ni
// « structure », ni « acier », ni « alu » — invisible pour le classifieur par
// mots-clés, atteignable UNIQUEMENT par son id (c'est tout le chantier).
const PERGOLA = {
  ...P('Pergola bioclimatique 4x3', 12000),
  categorie_type: 'structure',
  categorie: { nom: 'Pergolas', ordre: 5, type_equipement: 'structure' },
}
const SEEDED_PERGOLA = [...SEEDED, PERGOLA]
const KWP14 = 14 * 710 / 1000

test('STKCAT10 — structureRoleForName : MIROIR EXACT de role_structure_du_produit (serveur)', () => {
  assert.equal(structureRoleForName('Structures acier'), 'structure_acier')
  assert.equal(structureRoleForName('Structures aluminium'), 'structure_alu')
  // Ni l'un ni l'autre ⇒ rôle GÉNÉRIQUE (STKCAT2), jamais acier par défaut.
  assert.equal(structureRoleForName('Pergola bioclimatique 4x3'), 'structure')
  assert.equal(structureRoleForName('Bac lesté béton'), 'structure')
  // `voulu` départage un nom qui porte LES DEUX mots-clés…
  assert.equal(structureRoleForName('Structure acier et aluminium', 'aluminium'), 'structure_alu')
  assert.equal(structureRoleForName('Structure acier et aluminium', 'acier'), 'structure_acier')
  // …et c'est aussi le rôle rendu quand aucun nom n'est lisible.
  assert.equal(structureRoleForName('', 'aluminium'), 'structure_alu')
  assert.equal(structureRoleForName(null), 'structure_acier')
})

test('STKCAT10 — structureChoisie : id résolu sur le catalogue COMPLET, après la garde de prix', () => {
  assert.equal(structureChoisie(SEEDED_PERGOLA, PERGOLA.id).nom, 'Pergola bioclimatique 4x3')
  // Chaîne ou entier, même résolution (l'écran envoie des chaînes).
  assert.equal(structureChoisie(SEEDED_PERGOLA, String(PERGOLA.id)).id, PERGOLA.id)
  // Id inconnu / vide ⇒ rien (on retombe sur le bouton acier/alu).
  assert.equal(structureChoisie(SEEDED_PERGOLA, 99999), null)
  assert.equal(structureChoisie(SEEDED_PERGOLA, ''), null)
  assert.equal(structureChoisie(SEEDED_PERGOLA, null), null)
  // Produit NON TARIFÉ ⇒ rien : une composition ne cote jamais un prix absent
  // (même garde que le serveur, qui résout l'id APRÈS `_has_price`).
  const sansPrix = {
    id: 7777, nom: 'Carport (prix à renseigner)', prix_vente: '0',
    categorie_type: 'structure',
  }
  assert.equal(structureChoisie([...SEEDED_PERGOLA, sansPrix], 7777), null)
})

// ADEV69 — second composeur supprimé (D-QJR5-9) : la composition vit au serveur (apps/ventes/domain/composition.py, testée côté backend).
// Tests retirés (ils ne protégeaient QUE `autoFillLines`) :
//   · auto-fill 14 panneaux × 710 W : équipements et prix identiques au simulateur
//   · auto-fill 24 panneaux × 710 W : batterie homogène 3×5 kWh (jamais 10+5), structures alu
//   · auto-fill petit système 5 panneaux : onduleur 5 kW Monophasé préféré
//   · auto-fill : un catalogue encore écrit « Deyness » alimente le même vivier
//   · auto-fill : batterie « haute tension » jamais auto-choisie même moins chère
//   · auto-fill : les batteries 5/10 kWh restent choisies (homogène) malgré une HV au catalogue
//   · F4 — prix RÉELS fondateur : 2×5 kWh (28 000 TTC) bat 1×10 kWh (30 000 TTC) pour une cible de 10 kWh
//   · F4 — jusqu\
//   · F4 — un calibre à 0 en stock est EXCLU du choix économique
//   · F4 — max_modules_par_banc (specs_solaire) rejette une candidate qui le dépasse, jamais un mélange
//   · PVOND — une batterie hors plage est refusée même si son nom ne dit rien
//   · PVOND — une batterie haute tension EST retenue sous un onduleur haute tension
//   · PVOND — un onduleur au contrat incomplet est écarté ET nommé
//   · PVOND — vivier batterie VIDE sous une plage : la composition AVERTIT
//   · PVOND — aucune alerte batterie quand le vivier sert normalement
//   · PVOND — un RÉSEAU complet n\
//   · QX19 — autoFillLines expose actualPanelW / nbPanneaux / kwcReel
//   · QX19 — nbPanneaux override (taille souhaitée kWc) pilote le nb de panneaux
//   · QX19 — substitution de wattage : actualPanelW reflète le panneau retenu
//   · QF8 — catalogue 100% Deye (réseau + hybride) : Smart Meter et Wifi Dongle qté 0
//   · QF8 — réseau Huawei mais hybride Deye : Smart Meter/Wifi attachés (réseau Huawei suffit)
//   · QF8 — réseau Deye mais hybride Huawei : Smart Meter/Wifi attachés (hybride Huawei suffit)
//   · STKCAT10 — SANS produit choisi : composition BYTE-IDENTIQUE à l historique
//   · STKCAT10 — AVEC une pergola choisie : UNE ligne, à son nom, rôle générique structure
//   · STKCAT10 — un produit choisi qui porte encore « aluminium » garde le rôle structure_alu
//   · STKCAT10 — un produit choisi ne déclenche AUCUNE « marque introuvable » de structure

// AGEN13 (D-ACAL-97, contrôle C4-E8) — plus aucun moteur de production ou
// d'économie dans le navigateur : l'écran lit la conception servie (AGEN11).
// Gardés car encore lus par un appelant de production que la tâche ne remplace
// pas : `estimerMois` (répartition des deux factures en 12 mois : écran devis,
// useLeadClientEcran, etatDevis) et `PRODUCTIBLE_NET_FACTOR` (Paramètres →
// Avancé, AvanceSection.jsx). Mutant : ré-exporter `computeROI` ⇒ rouge.
test('AGEN13 — aucun export de production n’est un moteur de production ou d’économie', async () => {
  const solar = await import('./solar.js')
  for (const nom of ['GHI', 'EFFICIENCY', 'KWH_PRICE', 'PRODUCTIBLE_PAR_VILLE', 'DEFAULT_PRODUCTIBLE',
    'productibleForCity', 'computeROI', 'paybackMoteurHoraire']) {
    assert.equal(nom in solar, false, `solar.js exporte encore ${nom}`)
  }
  await assert.rejects(import('./calc/roi.js'), 'calc/roi.js (computeROI, paybackMoteurHoraire) doit avoir disparu')
})
