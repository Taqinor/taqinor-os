// QJR91 (M4, audit L3 du 29/08/2026) — PARITÉ DES CLASSIFIEURS : ÉCRAN vs PDF.
//
// CE QUE CE FICHIER PROTÈGE, ET POURQUOI IL EXISTE.
// `frontend/src/features/ventes/solar.js` et
// `backend/django_core/apps/ventes/quote_engine/builder.py` classifient CHACUN
// de leur côté la MÊME désignation de ligne de devis, sans jamais lire une
// table commune. Le commentaire de `builder.py:258-261` PRÉTEND être le
// « miroir de solar.js » — et c'est FAUX depuis le 19/08 : exactement le mode
// d'échec qu'un commentaire ne peut jamais prévenir et qu'une fixture partagée
// prévient toujours. La fixture QJR2
// (`apps/ventes/contract_samples/classification_lignes.json`) est cette table
// commune ; ce fichier en est la moitié ÉCRAN, son jumeau Python
// (`apps/ventes/tests/test_classification_parite.py`) la moitié PDF. Mêmes
// entrées, mêmes valeurs attendues, un seul fichier source de vérité.
//
// ÉTAT ATTENDU AUJOURD'HUI (QJR91 pose la garde, QJR92 met au vert) :
//   • ROUGE ici — cas « Module PV 550 W », colonne `panneau`. `solar.js:947
//     isPanel` ne teste que le mot « panneau » ; `builder.py:343 _is_panel`
//     accepte « module » + un qualificatif panneau. LE PDF A RAISON : à
//     l'écran, un devis dont la seule ligne panneau s'appelle ainsi est refusé
//     à l'enregistrement comme n'ayant aucun panneau. QJR92a élargit `isPanel`.
//   • VERT ici — cas « Batterie Deye BOS-B-Pack » : `batteryKwhFromLines`
//     contribue 0 (règle BAT5DEF du 26/08, « zéro chiffre inventé »). C'est
//     le BACKEND qui est rouge sur ce cas (`BATTERY_DEFAULT_KWH = 5.0`, un
//     nombre fabriqué publié sur un PDF client) — QJR92b l'y retire.
//
// Run : node --test src/features/ventes/classifieurs.parite.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  isPanel, isBattery, isHybridInverter, isReseauInverter, isAnyInverter,
  parseKwh, batteryKwhFromLines, classifyProduct,
  texteClassement, appartientAuPanierSans, appartientAuPanierAvec, inverterCostFromLines,
  optionTotalsTTC, avecBatterieAvailability,
} from './solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const CONTRAT = join(
  HERE,
  '../../../../backend/django_core/apps/ventes/contract_samples/classification_lignes.json')

const FIXTURE = JSON.parse(readFileSync(CONTRAT, 'utf8'))
const CAS = FIXTURE.exemple?.cas ?? []

// Les six colonnes que les DEUX moitiés doivent reproduire à l'identique
// (`notes.colonnes` de la fixture).
const COLONNES = [
  'designation', 'panneau', 'batterie',
  'onduleur_hybride', 'onduleur_reseau', 'kwh_lisible',
]

test('QJR91 — la fixture de parité QJR2 est lisible et complète', () => {
  assert.ok(CAS.length > 0, 'classification_lignes.json ne porte aucun cas')
  for (const cas of CAS) {
    for (const col of COLONNES) {
      assert.ok(col in cas,
        `le cas « ${cas.designation} » ne porte pas la colonne ${col}`)
    }
  }
})

// ── Un test par cas, une sous-assertion par colonne ──────────────────────────
// Sous-tests : un cas rouge nomme EXACTEMENT la colonne qui diverge, et les
// autres colonnes du même cas continuent d'être vérifiées.
for (const cas of CAS) {
  const d = cas.designation
  const div = cas.divergence_actuelle || null
  const etiquette = div
    ? ` [DIVERGENCE ${div.champ} — ROUGE ATTENDU jusqu'à QJR92]`
    : ''

  test(`QJR91 écran — « ${d} »${etiquette}`, async (t) => {
    await t.test('panneau (isPanel)', () => {
      assert.equal(isPanel(d), cas.panneau,
        `isPanel(« ${d} ») attendu ${cas.panneau} (contrat QJR2)`)
    })
    await t.test('batterie (isBattery)', () => {
      assert.equal(isBattery(d), cas.batterie,
        `isBattery(« ${d} ») attendu ${cas.batterie} (contrat QJR2)`)
    })
    await t.test('onduleur_hybride (isHybridInverter)', () => {
      assert.equal(isHybridInverter(d), cas.onduleur_hybride,
        `isHybridInverter(« ${d} ») attendu ${cas.onduleur_hybride} (contrat QJR2)`)
    })
    await t.test('onduleur_reseau (isReseauInverter)', () => {
      assert.equal(isReseauInverter(d), cas.onduleur_reseau,
        `isReseauInverter(« ${d} ») attendu ${cas.onduleur_reseau} (contrat QJR2)`)
    })
    await t.test('kwh_lisible (parseKwh)', () => {
      assert.equal(parseKwh(d) ?? null, cas.kwh_lisible ?? null,
        `parseKwh(« ${d} ») attendu ${cas.kwh_lisible} (contrat QJR2)`)
    })
    // Sens UNIQUE, jamais l'inverse : un onduleur classé hybride ou réseau est
    // forcément un onduleur. La réciproque est fausse par construction (un
    // micro-onduleur est `isAnyInverter` sans être ni l'un ni l'autre) — ne
    // jamais l'affirmer ici, la fixture ne porte pas ce cas.
    await t.test('cohérence isAnyInverter', () => {
      if (cas.onduleur_hybride || cas.onduleur_reseau) {
        assert.equal(isAnyInverter(d), true,
          `isAnyInverter(« ${d} ») doit être vrai pour un onduleur classé`)
      }
    })
  })
}

// ── batteryKwhFromLines : la capacité totale, ligne par ligne ────────────────
// BAT5DEF (26/08/2026, règle fondateur « zéro chiffre inventé ») — une ligne
// batterie sans kWh lisible contribue 0, JAMAIS un défaut fabriqué. C'est ce
// que le jumeau backend doit adopter (QJR92b retire `BATTERY_DEFAULT_KWH`).
for (const cas of CAS.filter(c => c.batterie)) {
  const attendu = cas.kwh_lisible ?? 0
  test(`QJR91 écran — batteryKwhFromLines([« ${cas.designation} » × 1]) = ${attendu}`, () => {
    const total = batteryKwhFromLines([{ designation: cas.designation, quantite: 1 }])
    assert.ok(Math.abs(total - attendu) < 1e-9,
      `attendu ${attendu} kWh (contrat QJR2), obtenu ${total}`)
  })
}

test('QJR91 écran — capacité TOTALE de la fixture : aucune ligne n\'invente de kWh', () => {
  const lignes = CAS.map(c => ({ designation: c.designation, quantite: 1 }))
  const attendu = CAS.filter(c => c.batterie)
    .reduce((s, c) => s + (c.kwh_lisible ?? 0), 0)
  const total = batteryKwhFromLines(lignes)
  assert.ok(Math.abs(total - attendu) < 1e-9,
    `capacité totale attendue ${attendu} kWh (somme des kWh RÉELLEMENT lisibles), obtenu ${total}`)
})

// ── STKCAT19 — colonne `role` (classifyProduct) ──────────────────────────────
// Comportement MOT-CLÉ COURANT, REPLI DERRIÈRE LE RÔLE DÉCLARÉ (voir
// `notes.role_stkcat19` de la fixture) : STKCAT21 fera du rôle produit DÉCLARÉ
// la source prioritaire, ce classifieur par mot-clé n'en restera qu'un repli
// pour les produits sans rôle déclaré. `role` n'est porté QUE par les cas
// structure/accessoire ajoutés par STKCAT19 (pas par les neuf cas résidentiels
// ci-dessus, hors périmètre de cette colonne) — on ne teste donc que ceux-là.
const CAS_AVEC_ROLE = CAS.filter((c) => 'role' in c)

test('QJR91/STKCAT19 — la colonne role est présente sur les cas structure/accessoire', () => {
  assert.ok(CAS_AVEC_ROLE.length > 0,
    'aucun cas ne porte la colonne role (STKCAT19) — classification_lignes.json a régressé')
})

for (const cas of CAS_AVEC_ROLE) {
  const d = cas.designation
  test(`STKCAT19 écran — role (classifyProduct) « ${d} »`, () => {
    assert.equal(classifyProduct(d), cas.role,
      `classifyProduct(« ${d} ») attendu ${JSON.stringify(cas.role)} (contrat QJR2/STKCAT19)`)
  })
}

// ── AGNR36 — section `cas_ligne_produit` (AGNR2) : la LIGNE se classe sur
// désignation + nom du produit lié (`texteClassement`, miroir de
// `utils/options.texte_classement`), jamais sur la désignation seule. Chaque
// prédicat de ligne reçoit la liste des produits de l'écran.
const CAS_LIGNE = FIXTURE.exemple?.cas_ligne_produit ?? []

test('AGNR36 — la section cas_ligne_produit est présente', () => {
  assert.ok(CAS_LIGNE.length > 0, 'classification_lignes.json ne porte aucun cas_ligne_produit')
})

for (const cas of CAS_LIGNE) {
  test(`AGNR36 écran — ligne « ${cas.designation} » / produit « ${cas.produit_nom} »`, () => {
    const produits = cas.produit_nom ? [{ id: 1, nom: cas.produit_nom }] : []
    const l = {
      designation: cas.designation, produit: cas.produit_nom ? '1' : '', quantite: '1',
      prix_unit_ttc: '1000', taux_tva: '20', variante: '',
    }
    assert.equal(texteClassement(l, produits).trim(), `${cas.designation} ${cas.produit_nom}`.trim())
    assert.equal(appartientAuPanierSans(l, produits), cas.panier_sans, 'panier_sans')
    assert.equal(appartientAuPanierAvec(l, produits), cas.panier_avec, 'panier_avec')
    assert.equal(batteryKwhFromLines([l], produits) || null, cas.kwh_batterie, 'kwh_batterie')
    assert.equal(inverterCostFromLines([l], produits) != null, cas.provision_onduleur, 'provision_onduleur')
    assert.equal(isPanel(cas.designation, cas.produit_nom), cas.est_panneau, 'est_panneau')
  })
}

test('AGNR36 — DEV-DEMO-0003 : désignations retouchées, totaux par option inchangés', () => {
  const produits = [
    { id: 1, nom: 'Panneau Canadian Solar 710W' },
    { id: 2, nom: 'Onduleur réseau Huawei 5kW Monophasé' },
    { id: 3, nom: 'Onduleur hybride Deye 5kW Monophasé' },
    { id: 4, nom: 'Batterie Dyness 5 kWh' },
  ]
  const L = (produit, designation, quantite, ttc) => ({
    produit: String(produit), designation, quantite: String(quantite), prix_unit_ttc: String(ttc),
    taux_tva: '20', variante: '',
  })
  const avant = [
    L(1, 'Panneau Canadian Solar 710W', 8, 1500), L(2, 'Onduleur réseau Huawei 5kW Monophasé', 1, 9000),
    L(3, 'Onduleur hybride Deye 5kW Monophasé', 1, 14000), L(4, 'Batterie Dyness 5 kWh', 1, 16000),
  ]
  const retouche = [
    avant[0], avant[1],
    { ...avant[2], designation: 'Onduleur Deye 5kW (garantie 10 ans)' },
    { ...avant[3], designation: 'Stockage Dyness 5 kWh' },
  ]
  const ref = optionTotalsTTC(avant, 0, { produits })
  const t = optionTotalsTTC(retouche, 0, { produits })
  assert.equal(t.totalSans, ref.totalSans)
  assert.equal(t.totalAvec, ref.totalAvec)
  assert.equal(batteryKwhFromLines(retouche, produits), 5)
  assert.equal(avecBatterieAvailability(retouche, produits, 5.68).available, true)
})
