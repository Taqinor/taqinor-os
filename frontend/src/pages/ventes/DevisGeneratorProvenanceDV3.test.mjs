// QJR213/DV3 (audit L3 30/08/2026) — les QUATRE cartes indus/commercial
// nourries par le miroir LOCAL `features/ventes/solar.js`
// (`computeEtudeIndustrielle`) portent une pastille les identifiant comme
// non-autoritatives ; les 9 AUTRES cartes `CarteMetrique` de l'écran
// (résidentiel) sont cosmétiques et n'ont AUCUNE tâche — décision DV3,
// restent inchangées à l'octet. CONTRAINTE D10 (mot du fondateur) :
// étiquetage SEULEMENT — cette tâche ne serverise rien, ne touche à AUCUN
// appel réseau.
//
// QJR426 (02/09/2026) — DR5 a fait passer les 13 cartes de la prop `value=`
// littérale à la prop `valeur=` SIGNÉE (`moteur`/`apercu`, `quote/valeur.js`).
// Ces 4 cartes portent désormais `valeur={apercu(...)}` au lieu du littéral
// `badge="estimation locale"` : `CarteMetrique` déballe la valeur signée et
// pose AUTOMATIQUEMENT sa puce `PUCE_APERCU` (« estimation d'exemple ») —
// le même MOTIF que « estimation locale » (chiffre local, pas une mesure),
// sous le libellé canonique de la primitive partagée plutôt qu'un texte ad
// hoc. Ce test vérifie donc `valeur={apercu(` au lieu du littéral `badge=`.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE (même patron que
// DevisGeneratorCompositionSourceLocale.test.mjs).
//
// Run : node --test src/pages/ventes/DevisGeneratorProvenanceDV3.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

// Les QUATRE cartes visées par DV3 (nourries par `etudeCI`, dérivé de
// `computeEtudeIndustrielle` — le miroir local, jamais le serveur).
const LABELS_MIROIR_LOCAL = [
  "Taux d'autoconsommation",
  'Taux de couverture',
  'Économies annuelles (étude)',
  'Payback (étude)',
]

// Les NEUF autres cartes de l'écran — hors périmètre DV3, DOIVENT rester
// hors de la puce d'aperçu locale (aucune ne signe sa valeur en `apercu()`
// SANS CONDITION — deux d'entre elles, Économies/ROI, la portent seulement
// de façon CONDITIONNELLE via `signerEcoOuRoi`, jamais en dur, cf. plus bas).
const LABELS_HORS_PERIMETRE = [
  'Production annuelle',
  "Taux d'autoconsommation (sans)",
  'Taux de couverture (sans)',
]
const LABELS_HORS_PERIMETRE_DOUBLES = ['Économies', 'ROI', 'Coût'] // apparaissent 2× (Sans/Avec)

function blocDeCarte(label) {
  const idx = DG.indexOf(`<CarteMetrique label="${label}"`)
  assert.ok(idx > -1, `carte "${label}" introuvable`)
  // Une carte tient sur quelques lignes ; une fenêtre de 400 caractères
  // couvre largement value/unit/accent/badge sans déborder sur la carte suivante.
  return DG.slice(idx, idx + 400)
}

test('QJR426 — les 4 cartes du miroir local portent la valeur SIGNÉE apercu() (miroir de l’ancienne pastille locale)', () => {
  for (const label of LABELS_MIROIR_LOCAL) {
    const bloc = blocDeCarte(label)
    assert.match(bloc, /valeur=\{apercu\(/,
      `carte "${label}" : valeur signée apercu() attendue (DV3/QJR426)`)
    // Le littéral d'hier a disparu — plus jamais deux mécanismes de marquage
    // pour la même carte (règle permanente 2 : jamais deux implémentations).
    assert.doesNotMatch(bloc, /badge="estimation locale"/,
      `carte "${label}" : le badge littéral doit avoir disparu (QJR426)`)
  }
})

test('QJR213 — les 4 cartes visées sont bien nourries par etudeCI (miroir local, pas le serveur)', () => {
  const idx = DG.indexOf('{etudeCI && (')
  assert.ok(idx > -1, 'le bloc conditionnel etudeCI est introuvable')
  const bloc = DG.slice(idx, idx + 2700)
  for (const label of LABELS_MIROIR_LOCAL) {
    assert.match(bloc, new RegExp(`<CarteMetrique label="${label.replace(/[().]/g, '\\$&')}"`),
      `carte "${label}" doit vivre dans le bloc etudeCI`)
  }
  // etudeCI == etudeIndustrielle || etudeCommerciale, tous deux dérivés de
  // computeEtudeIndustrielle (le miroir local `solar.js`, jamais un appel réseau).
  assert.match(DG, /const etudeCI = etudeIndustrielle \|\| etudeCommerciale/)
  assert.match(DG, /computeEtudeIndustrielle,\r?\n/, 'computeEtudeIndustrielle doit être importé')
  assert.match(DG, /\} from '\.\.\/\.\.\/features\/ventes\/solar'/,
    'computeEtudeIndustrielle doit venir du miroir local solar.js, jamais du serveur')
})

test('QJR213/QJR426 — les 9 autres cartes ne signent JAMAIS en dur avec apercu()', () => {
  for (const label of LABELS_HORS_PERIMETRE) {
    const bloc = blocDeCarte(label)
    assert.doesNotMatch(bloc, /valeur=\{apercu\(/,
      `carte "${label}" : hors périmètre DV3, ne doit RIEN gagner`)
  }
  // "Économies"/"ROI"/"Coût" apparaissent 2 fois chacune (Sans/Avec) : aucune
  // des 6 occurrences ne signe en dur avec apercu() — Économies/ROI passent
  // par `signerEcoOuRoi` (conditionnel, cf. test dédié plus bas), Coût par
  // `moteur()` (jamais de pastille).
  for (const label of LABELS_HORS_PERIMETRE_DOUBLES) {
    let from = 0
    let count = 0
    for (;;) {
      const idx = DG.indexOf(`<CarteMetrique label="${label}"`, from)
      if (idx === -1) break
      count += 1
      const bloc = DG.slice(idx, idx + 400)
      assert.doesNotMatch(bloc, /valeur=\{apercu\(/,
        `carte "${label}" (occurrence ${count}) : hors périmètre DV3, ne doit RIEN gagner`)
      from = idx + 1
    }
    assert.equal(count, 2, `"${label}" doit apparaître exactement 2 fois (Sans/Avec)`)
  }
})

test('QJR213/QJR426 — 13 cartes CarteMetrique au total (chiffre R3), 4 marquées apercu() + 9 non marquées', () => {
  const total = (DG.match(/<CarteMetrique label=/g) || []).length
  assert.equal(total, 13, 'le nombre total de sites CarteMetrique a changé — revoir le périmètre DV3')
  const marquees = (DG.match(/valeur=\{apercu\(/g) || []).length
  assert.equal(marquees, 4, 'exactement 4 cartes doivent signer en dur avec apercu() (DV3)')
  // Toutes les 13 cartes doivent être passées à la prop signée `valeur=` —
  // le littéral `value=` d'hier a disparu de CHAQUE site CarteMetrique.
  const total_valeur = (DG.match(/<CarteMetrique label="[^"]*"\s*\r?\n\s*valeur=\{/g) || []).length
  assert.equal(total_valeur, 13, 'les 13 appels doivent tous porter `valeur=` (QJR426/DR5)')
})

test('QJR213 — aucun nouveau composant, aucun nouvel appel réseau (D10 : étiquetage SEULEMENT)', () => {
  // Le mécanisme réutilisé est le `badge` existant de CarteMetrique.jsx —
  // aucun nouveau composant de pastille introduit.
  const cm = readFileSync(join(HERE, 'generator', 'CarteMetrique.jsx'), 'utf8')
  assert.match(cm, /badge/, 'CarteMetrique.jsx doit toujours porter le mécanisme badge existant')
  // Étiquetage seulement : aucun appel réseau nouveau autour du bloc etudeCI.
  const idx = DG.indexOf('{etudeCI && (')
  const bloc = DG.slice(idx, idx + 1400)
  assert.doesNotMatch(bloc, /ventesApi\.|fetch\(|await /,
    'D10 : aucun appel serveur ne doit être introduit pour ces 4 cartes')
})
