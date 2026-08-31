// QJR213/DV3 (audit L3 30/08/2026) — les QUATRE cartes indus/commercial
// nourries par le miroir LOCAL `features/ventes/solar.js`
// (`computeEtudeIndustrielle`) portent une pastille « estimation locale » ;
// les 9 AUTRES cartes `CarteMetrique` de l'écran (résidentiel) sont
// cosmétiques et n'ont AUCUNE tâche — décision DV3, restent inchangées à
// l'octet. CONTRAINTE D10 (mot du fondateur) : étiquetage SEULEMENT — cette
// tâche ne serverise rien, ne touche à AUCUN appel réseau.
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
// inchangées à l'octet (aucun `badge="estimation locale"` ajouté).
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

test('QJR213 — les 4 cartes du miroir local portent EXACTEMENT "estimation locale"', () => {
  for (const label of LABELS_MIROIR_LOCAL) {
    const bloc = blocDeCarte(label)
    assert.match(bloc, /badge="estimation locale"/,
      `carte "${label}" : pastille "estimation locale" attendue (DV3)`)
  }
})

test('QJR213 — les 4 cartes visées sont bien nourries par etudeCI (miroir local, pas le serveur)', () => {
  const idx = DG.indexOf('{etudeCI && (')
  assert.ok(idx > -1, 'le bloc conditionnel etudeCI est introuvable')
  const bloc = DG.slice(idx, idx + 2200)
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

test('QJR213 — les 9 autres cartes restent INCHANGÉES : aucun badge="estimation locale" ajouté', () => {
  for (const label of LABELS_HORS_PERIMETRE) {
    const bloc = blocDeCarte(label)
    assert.doesNotMatch(bloc, /badge="estimation locale"/,
      `carte "${label}" : hors périmètre DV3, ne doit RIEN gagner`)
  }
  // "Économies"/"ROI"/"Coût" apparaissent 2 fois chacune (Sans/Avec) : aucune
  // des 6 occurrences ne doit porter la nouvelle pastille.
  for (const label of LABELS_HORS_PERIMETRE_DOUBLES) {
    let from = 0
    let count = 0
    for (;;) {
      const idx = DG.indexOf(`<CarteMetrique label="${label}"`, from)
      if (idx === -1) break
      count += 1
      const bloc = DG.slice(idx, idx + 400)
      assert.doesNotMatch(bloc, /badge="estimation locale"/,
        `carte "${label}" (occurrence ${count}) : hors périmètre DV3, ne doit RIEN gagner`)
      from = idx + 1
    }
    assert.equal(count, 2, `"${label}" doit apparaître exactement 2 fois (Sans/Avec)`)
  }
})

test('QJR213 — 13 cartes CarteMetrique au total (chiffre R3), 4 marquées + 9 non marquées', () => {
  const total = (DG.match(/<CarteMetrique label=/g) || []).length
  assert.equal(total, 13, 'le nombre total de sites CarteMetrique a changé — revoir le périmètre DV3')
  const marquees = (DG.match(/badge="estimation locale"/g) || []).length
  assert.equal(marquees, 4, 'exactement 4 cartes doivent porter la pastille DV3')
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
