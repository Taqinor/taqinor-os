// QJR37 (audit L3 29/08/2026, origine QJF6) — `buildDimensionnementAvec`
// lisait `backendAvec?.nb_panneaux` là où le moteur horaire (réponse de
// POST /ventes/etude-horaire/preview/, blocs `dimensionnement.recommandation`
// / `dimensionnement.recommandation_avec`) émet `panneaux` — la clé lue
// n'existait JAMAIS dans la réponse serveur, donc la branche censée reprendre
// le compte de panneaux AVEC du moteur était MORTE : le compte retombait
// TOUJOURS sur l'arrondi local (kWc × 1000 / wattage écran).
//
// Vérifié contre le contrat RÉEL (jamais une supposition) :
// apps/ventes/contract_samples/etude_horaire.json porte
// `"recommandation_avec": {"panneaux": 17, …}` — AUCUNE clé `nb_panneaux`
// dans ce bloc.
//
// Le `nb_panneaux` qui reste dans `buildDimensionnementAvec` est une AUTRE
// clé : celle de la forme de SORTIE envoyée à POST /ventes/devis/composition/
// (contract_samples/devis_composition.json, champ d'entrée
// `dimensionnement_avec: {nb_panneaux?, kwc?, batterie_kwh?}`) — une clé
// différente, dans l'autre sens, volontairement inchangée par ce correctif.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE, même patron que les autres
// tests QJR de ce fichier.
//
// Run : node --test src/pages/ventes/DevisGeneratorBuildDimensionnementAvec.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')
const CONTRACT_PATH = join(
  HERE, '../../../../backend/django_core/apps/ventes/contract_samples/etude_horaire.json')

test('QJR37 — preuve de contrat : recommandation_avec émet `panneaux`, jamais `nb_panneaux`', () => {
  const contrat = JSON.parse(readFileSync(CONTRACT_PATH, 'utf8'))
  const reco = contrat.exemple?.dimensionnement?.recommandation_avec
  assert.ok(reco, 'recommandation_avec introuvable dans le contrat etude_horaire.json')
  assert.equal(typeof reco.panneaux, 'number', 'recommandation_avec.panneaux doit être un nombre')
  assert.equal(reco.nb_panneaux, undefined,
    'recommandation_avec ne doit PORTER AUCUNE clé nb_panneaux (jamais une supposition)')
  // Même vérification côté `recommandation` (option SANS), pour prouver que
  // c'est bien la forme générale du moteur, pas un accident d'un seul bloc.
  const recoSans = contrat.exemple?.dimensionnement?.recommandation
  assert.equal(typeof recoSans.panneaux, 'number')
  assert.equal(recoSans.nb_panneaux, undefined)
})

test('QJR37 — buildDimensionnementAvec lit backendAvec.panneaux (plus jamais backendAvec.nb_panneaux)', () => {
  const idx = DG.indexOf('const buildDimensionnementAvec = (kwpAvec) => {')
  assert.ok(idx > -1, 'buildDimensionnementAvec introuvable')
  const bloc = DG.slice(idx, idx + 900)
  assert.match(bloc,
    /const nbPanneauxAvec = Number\(backendAvec\?\.panneaux\) > 0\s*\n\s*\? Math\.round\(Number\(backendAvec\.panneaux\)\)/,
    'la lecture doit porter sur backendAvec.panneaux')
  assert.doesNotMatch(bloc, /backendAvec\?\.nb_panneaux|backendAvec\.nb_panneaux/,
    'backendAvec.nb_panneaux ne doit plus être lu (clé jamais émise par le moteur)')
})

test('QJR37 — la clé de SORTIE envoyée à composerDevis (dimensionnement_avec.nb_panneaux) reste `nb_panneaux`, forme différente volontairement inchangée', () => {
  const idx = DG.indexOf('const buildDimensionnementAvec = (kwpAvec) => {')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx, idx + 1200)
  assert.match(bloc, /const dims = \{ nb_panneaux: nbPanneauxAvec, kwc: kwpAvec \}/,
    'le corps envoyé au dry-run doit continuer à porter nb_panneaux (contrat devis_composition.json)')
})

test('QJR37 — rejoué : quand le moteur répond un compte AVEC, il est repris TEL QUEL (jamais re-dérivé par arrondi wattage)', () => {
  // Reproduit EXACTEMENT la formule verrouillée par le 2ᵉ test.
  const buildNbPanneauxAvec = (backendAvec, kwpAvec, panelWNum) =>
    (Number(backendAvec?.panneaux) > 0)
      ? Math.round(Number(backendAvec.panneaux))
      : Math.round((kwpAvec * 1000) / panelWNum)

  // Réponse serveur réelle (forme du contrat) : 17 panneaux.
  assert.equal(buildNbPanneauxAvec({ panneaux: 17 }, 12.07, 710), 17,
    'le compte AVEC du moteur doit être repris tel quel, jamais re-arrondi')
  // Absence de réponse serveur (kwpAvec === kwp, ou étude non chargée) :
  // repli sur la conversion kWc→panneaux du wattage écran — comportement
  // hors-ligne inchangé.
  assert.equal(buildNbPanneauxAvec(undefined, 7.1, 710), 10)
  // Une clé nb_panneaux orpheline (jamais émise en pratique) ne doit JAMAIS
  // être lue : seule `panneaux` compte.
  assert.equal(buildNbPanneauxAvec({ nb_panneaux: 999 }, 7.1, 710), 10,
    'une clé nb_panneaux ne doit jamais être lue, même si présente par erreur')
})
