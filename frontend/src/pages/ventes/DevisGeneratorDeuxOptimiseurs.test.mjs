// L-2OPT (fondateur 24/08/2026) — « deux optimiseurs indépendants ». Un devis
// résidentiel « Les deux (Sans + Avec) » compose SANS et AVEC séparément
// (chacun son propre kWc payback-optimal) puis fusionne les deux tableaux de
// lignes en une seule table taguée `variante`.
//
// QJR108 — CE FICHIER A CESSÉ DE LIRE LE SOURCE. Il épinglait par expression
// régulière trois fichiers (`DevisGenerator.jsx`, `solar.js`,
// `DevisLineRow.jsx`) : la mise en page d'un `if`, la présence littérale de
// `return kwp`, l'ordre de deux `indexOf`. Le sélecteur qu'il visait —
// `deuxValeursDim` / `paireDimensionnement` — vivait en haut de l'écran, NON
// exporté (react-refresh), donc littéralement intestable ; il vit désormais
// dans le module pur `features/ventes/quote/paireDimensionnement.js`
// (déplacement seul, pas une ligne de logique changée) et est ici EXÉCUTÉ.
// Les règles de panier / totaux / capacité batterie sont, elles, déjà pures
// dans `solar.js` : elles sont appelées, plus décrites.
//
// CE QUI RESTE HORS DE PORTÉE D'UN TEST PUR (pas revendiqué ici) : le badge de
// variante rendu par `DevisLineRow` et le surlignage de la ligne
// `recommandation_avec` dans le tableau de dimensionnement — deux rendus
// React, donc du domaine des specs RTL.
//
// Run : node --test src/pages/ventes/DevisGeneratorDeuxOptimiseurs.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  deuxValeursDim, paireDimensionnement, valeurMoteurDim, RIEN_A_CHIFFRER,
} from '../../features/ventes/quote/paireDimensionnement.js'
import { estFait } from '../../features/ventes/quote/valeur.js'
import {
  sizingReducer, ETAT_INITIAL, SCENARIO_LES_DEUX, SCENARIO_AVEC, SCENARIO_SANS,
} from '../../features/ventes/quote/sizingReducer.js'
import {
  appartientAuPanierSans, appartientAuPanierAvec, optionTotalsTTC,
  batteryKwhFromLines, batteryCapaciteInconnue, comptePanneauxOption,
} from '../../features/ventes/solar.js'

const SRV_SANS = { panneaux: 12, kwc: 8.52 }
const SRV_AVEC = { panneaux: 16, kwc: 11.36 }
const dim = (d) => ({ dimensionnement: d })

// ── LE SÉLECTEUR `deuxValeursDim` ───────────────────────────────────────────

test('les DEUX recommandations du moteur donnent la paire complète', () => {
  const paire = deuxValeursDim('residentiel',
    dim({ recommandation: SRV_SANS, recommandation_avec: SRV_AVEC }))
  assert.deepEqual(paire.sans, { nbPanneaux: 12, kwc: 8.52 })
  assert.deepEqual(paire.avec, { nbPanneaux: 16, kwc: 11.36 })
})

test('une seule branche chiffrée sort SEULE — « sans » d’abord, comme la cascade historique', () => {
  const seulSans = deuxValeursDim('residentiel', dim({ recommandation: SRV_SANS }))
  assert.deepEqual(seulSans.sans, { nbPanneaux: 12, kwc: 8.52 })
  assert.equal(seulSans.avec, null)
  const seulAvec = deuxValeursDim('residentiel', dim({ recommandation_avec: SRV_AVEC }))
  assert.equal(seulAvec.sans, null)
  assert.deepEqual(seulAvec.avec, { nbPanneaux: 16, kwc: 11.36 })
})

test('F3 — hors résidentiel il n’y a PAS de seconde option : jamais un chiffre « avec » fabriqué', () => {
  for (const marche of ['industriel', 'commercial', 'agricole']) {
    const paire = deuxValeursDim(marche,
      dim({ recommandation: SRV_SANS, recommandation_avec: SRV_AVEC }))
    assert.deepEqual(paire, { sans: null, avec: null }, `marché ${marche}`)
  }
})

test('aucune réponse du moteur : la paire est VIDE, jamais un défaut inventé (règle #4)', () => {
  assert.deepEqual(deuxValeursDim('residentiel', null), { sans: null, avec: null })
  assert.deepEqual(deuxValeursDim('residentiel', {}), { sans: null, avec: null })
  assert.deepEqual(deuxValeursDim('residentiel', dim({})), { sans: null, avec: null })
})

test('une recommandation à ZÉRO panneau n’est pas une recommandation', () => {
  const paire = deuxValeursDim('residentiel',
    dim({ recommandation: { panneaux: 0, kwc: 0 }, recommandation_avec: SRV_AVEC }))
  assert.equal(paire.sans, null, 'zéro panneau ne doit jamais s’afficher comme une taille')
  assert.deepEqual(paire.avec, { nbPanneaux: 16, kwc: 11.36 })
})

test('QJR102 — la SOURCE est unique : le sélecteur ne lit QUE le moteur (aucun balayage local n’y entre)', () => {
  // La branche locale supprimée par QJR102 se manifestait par une paire
  // MIXTE : un côté serveur, l'autre local. Le sélecteur ne prend qu'un seul
  // argument de données — il ne PEUT plus mélanger deux méthodes de calcul.
  assert.equal(deuxValeursDim.length, 2,
    'le sélecteur ne reçoit que le marché et la réponse du MOTEUR')
  const paire = deuxValeursDim('residentiel', {
    dimensionnement: { recommandation: SRV_SANS },
    // Un balayage local présent dans la charge utile n'a aucune influence.
    sizingInfo: { nbPanneaux: 99, kwcOptimal: 70 },
  })
  assert.equal(paire.avec, null, 'aucun repli local ne doit remplir la branche AVEC')
})

test('la valeur signée porte un MOTIF d’absence, jamais un chiffre de remplacement', () => {
  const rien = valeurMoteurDim(null)
  assert.equal(estFait(rien), false)
  assert.equal(rien.motif, RIEN_A_CHIFFRER)
  assert.equal(estFait(valeurMoteurDim(SRV_SANS)), true)
})

test('une recommandation AVEC à zéro panneau n’efface pas la branche SANS chiffrée', () => {
  const paire = deuxValeursDim('residentiel',
    dim({ recommandation: SRV_SANS, recommandation_avec: { panneaux: 0, kwc: 0 } }))
  assert.deepEqual(paire.sans, { nbPanneaux: 12, kwc: 8.52 })
  assert.equal(paire.avec, null)
})

test('un compte de panneaux servi en TEXTE est lu comme un nombre (le serveur sérialise parfois en chaîne)', () => {
  const paire = deuxValeursDim('residentiel',
    dim({ recommandation: { panneaux: '12', kwc: '8.52' } }))
  assert.equal(paire.sans.nbPanneaux, '12', 'la valeur est reportée TELLE QUELLE, jamais reformatée')
  assert.notEqual(paire.sans, null)
})

test('paireDimensionnement est PURE : deux appels sur les mêmes entrées donnent le même résultat', () => {
  const a = paireDimensionnement(SRV_SANS, SRV_AVEC)
  const b = paireDimensionnement(SRV_SANS, SRV_AVEC)
  assert.deepEqual(a, b)
  assert.notEqual(a, b, 'chaque appel rend un objet neuf — aucun état partagé')
})

// ── LE REDUCER : LE SCÉNARIO QUI COMMANDE LES DEUX OPTIMISEURS ──────────────

test('résidentiel : « Les deux » est le défaut fondateur (24/08) — c’est lui qui déclenche L-2OPT', () => {
  assert.equal(ETAT_INITIAL.scenario, SCENARIO_LES_DEUX)
  assert.equal(ETAT_INITIAL.modeInstallation, 'residentiel')
})

test('industriel / commercial retombent sur « Sans batterie » : le double optimum n’y est pas servable', () => {
  for (const marche of ['industriel', 'commercial']) {
    const etat = sizingReducer(ETAT_INITIAL, { type: 'MARCHE_CHANGE', mode: marche })
    assert.equal(etat.scenario, SCENARIO_SANS, `marché ${marche}`)
  }
})

test('agricole ne TOUCHE PAS le scénario (ni batterie ni onduleur en pompage)', () => {
  const etat = sizingReducer(ETAT_INITIAL, { type: 'MARCHE_CHANGE', mode: 'agricole' })
  assert.equal(etat.modeInstallation, 'agricole')
  assert.equal(etat.scenario, SCENARIO_LES_DEUX, 'le scénario reste celui d’avant, non redéfini')
})

test('un scénario CHOISI par le commercial survit à un changement de marché', () => {
  const etat = [
    { type: 'SAISI', champ: 'scenario', valeur: SCENARIO_AVEC },
    { type: 'MARCHE_CHANGE', mode: 'industriel' },
  ].reduce(sizingReducer, ETAT_INITIAL)
  assert.equal(etat.scenario, SCENARIO_AVEC, 'le défaut du marché ne doit pas jeter un choix explicite')
  assert.equal(etat.touche.scenario, true)
})

test('la réouverture d’un brouillon « Les deux » ferme le drapeau scénario (l’enregistrement suivant ne l’écrase plus)', () => {
  const etat = sizingReducer(ETAT_INITIAL, {
    type: 'REOUVERTURE',
    devis: { mode_installation: 'industriel', panneaux: 20, scenario: SCENARIO_LES_DEUX },
  })
  assert.equal(etat.scenario, SCENARIO_LES_DEUX)
  assert.equal(etat.touche.scenario, true)
  assert.equal(etat.nbPanneaux, '20')
})

test('« Appliquer cette taille » d’une ligne du tableau pose CETTE ligne et relance la composition', () => {
  // Le tableau de dimensionnement affiche les deux recommandations (sans /
  // avec) : choisir une ligne doit poser SA taille, fermer l'attente moteur et
  // relancer la composition — même si le compte retombe sur le même nombre.
  const etat = sizingReducer(ETAT_INITIAL, {
    type: 'TAILLE_APPLIQUEE',
    ligne: { panneaux: 16, kwc: 11.36, panel_watt: 710 },
  })
  assert.equal(etat.nbPanneaux, '16')
  assert.equal(etat.kwcCible, '11.36')
  assert.equal(etat.panelW, '710')
  assert.equal(etat.touche.nbPanneaux, true, 'un choix explicite EST une saisie')
  assert.equal(etat.attenteMoteur, false)
  assert.equal(etat.compositionSeq, ETAT_INITIAL.compositionSeq + 1,
    'la composition doit repartir même si le compte n’a pas bougé')
})

test('une ligne SANS panneaux ne s’applique pas (jamais une taille vide posée par un clic)', () => {
  const etat = sizingReducer(ETAT_INITIAL, { type: 'TAILLE_APPLIQUEE', ligne: {} })
  assert.equal(etat, ETAT_INITIAL)
})

// ── LES DEUX PANIERS : CE QUE `variante` CHANGE RÉELLEMENT ──────────────────
// F14 (26/08/2026) — une ligne DÉCLARÉE tranche SEULE (miroir exact de
// `builder.py _repartir_options`) ; une ligne SANS `variante` retombe sur les
// mots-clés, mot pour mot comme avant L-2OPT.

const PANNEAU = { designation: 'Panneau JA Solar 710W', quantite: '12',
                  prix_unit_ttc: '1000', taux_tva: '20' }
const BATTERIE = { designation: 'Batterie Deye 16 kWh', quantite: '1',
                   prix_unit_ttc: '30000', taux_tva: '20' }
const HYBRIDE = { designation: 'Onduleur hybride Deye SG05LP3', quantite: '1',
                  prix_unit_ttc: '15000', taux_tva: '20' }
const RESEAU = { designation: 'Onduleur réseau injection', quantite: '1',
                 prix_unit_ttc: '9000', taux_tva: '20' }

test('sans `variante`, les paniers se décident aux MOTS-CLÉS — comportement legacy intact', () => {
  assert.equal(appartientAuPanierSans(PANNEAU), true)
  assert.equal(appartientAuPanierSans(BATTERIE), false)
  assert.equal(appartientAuPanierSans(HYBRIDE), false)
  assert.equal(appartientAuPanierSans(RESEAU), true)
  assert.equal(appartientAuPanierAvec(RESEAU), false)
  assert.equal(appartientAuPanierAvec(BATTERIE), true)
  assert.equal(appartientAuPanierAvec(HYBRIDE), true)
})

test('une ligne DÉCLARÉE tranche seule — la déclaration prime sur les mots-clés', () => {
  // Le cas exact que F14 a corrigé : une batterie taguée 'sans' était encore
  // retirée du panier « sans » par un second filtre mot-clé, alors que le PDF
  // la facturait dans ce panier — écran et PDF divergeaient.
  assert.equal(appartientAuPanierSans({ ...BATTERIE, variante: 'sans' }), true)
  assert.equal(appartientAuPanierAvec({ ...BATTERIE, variante: 'sans' }), false)
  assert.equal(appartientAuPanierAvec({ ...RESEAU, variante: 'avec' }), true)
  assert.equal(appartientAuPanierSans({ ...RESEAU, variante: 'avec' }), false)
})

test('une ligne commune (`variante: \'\'`) compte dans les DEUX paniers', () => {
  const commun = { ...PANNEAU, variante: '' }
  assert.equal(appartientAuPanierSans(commun), true)
  assert.equal(appartientAuPanierAvec(commun), true)
})

test('les totaux par option appliquent les paniers — deux compositions divergentes ne se mélangent pas', () => {
  const lignes = [
    { ...PANNEAU, quantite: '12', variante: 'sans' },
    { ...PANNEAU, quantite: '16', variante: 'avec' },
    { ...RESEAU, variante: 'sans' },
    { ...HYBRIDE, variante: 'avec' },
    { ...BATTERIE, variante: 'avec' },
  ]
  const t = optionTotalsTTC(lignes, 0)
  assert.equal(t.totalSansBrut, 12 * 1000 + 9000)
  assert.equal(t.totalAvecBrut, 16 * 1000 + 15000 + 30000)
  assert.notEqual(t.totalSansBrut, t.totalAvecBrut,
    'deux optimiseurs indépendants doivent donner deux totaux différents')
})

test('la remise globale s’applique aux DEUX options, chacune sur SON total', () => {
  const lignes = [{ ...PANNEAU, quantite: '10', variante: '' }]
  const t = optionTotalsTTC(lignes, 10)
  assert.equal(t.totalSansBrut, 10000)
  assert.equal(t.totalSans, 9000)
  assert.equal(t.totalAvec, 9000)
})

test('une ligne batterie taguée « sans » ne compte JAMAIS dans une capacité batterie', () => {
  assert.equal(batteryKwhFromLines([{ ...BATTERIE, variante: 'avec' }]), 16)
  assert.equal(batteryKwhFromLines([{ ...BATTERIE, variante: 'sans' }]), 0,
    'une quantité issue de la composition SANS n’a aucun sens en capacité')
  assert.equal(batteryCapaciteInconnue([
    { designation: 'Batterie sans kWh lisible', quantite: '1', variante: 'sans' },
  ]), false, 'une ligne exclue ne doit pas non plus déclencher l’avertissement')
})

test('BAT5DEF — une batterie sans kWh lisible compte 0 et le DIT (jamais un défaut de 5 kWh)', () => {
  const lignes = [{ designation: 'Batterie Pylontech', quantite: '2', variante: 'avec' }]
  assert.equal(batteryKwhFromLines(lignes), 0)
  assert.equal(batteryCapaciteInconnue(lignes), true)
})

test('le compte de panneaux est PROPRE à chaque option — sinon l’écran chiffre une économie avec le kWc de l’autre', () => {
  const lignes = [
    { ...PANNEAU, quantite: '12', variante: 'sans' },
    { ...PANNEAU, quantite: '16', variante: 'avec' },
    { ...PANNEAU, quantite: '2', variante: '' },
  ]
  assert.equal(comptePanneauxOption(lignes, 'sans'), 14, 'commun + sans')
  assert.equal(comptePanneauxOption(lignes, 'avec'), 18, 'commun + avec')
})
