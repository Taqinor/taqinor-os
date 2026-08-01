// APX6 — INVERSÉ par le fondateur (2026-08-01) : « tu as rajouté une case
// grise en haut de chaque étape, des fois grise et rouge — enlève ça ».
// La barre segmentée d'activité des en-têtes de colonne est RETIRÉE ; ce
// fichier devient le CONTRAT D'ABSENCE : il rougit si la barre (ou son
// mécanisme de filtre par colonne) revient sans nouvelle décision fondateur.
// La somme `.num` de l'en-tête (LB9) et la pastille d'activité DE LA CARTE
// (kb-act-<state>, budget de signaux APX2) ne sont PAS concernées.
//   node --test src/pages/crm/leads/views/KanbanActivityBar.apx6.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8')
const CSS = readFileSync(join(HERE, '../../../../index.css'), 'utf8')

test("la barre segmentée d'activité n'existe plus (JSX)", () => {
  assert.doesNotMatch(SRC, /kb-col-activite|kb-act-seg/)
  assert.doesNotMatch(SRC, /repartitionActivite|ACTIVITE_SEAUX|activiteSeau/)
  assert.doesNotMatch(SRC, /activiteFiltre|onFiltrerActivite|activiteParEtape/)
  // La décision est documentée sur place.
  assert.match(SRC, /APX6 — RETIRÉ sur ordre fondateur/)
})

test("la barre segmentée n'existe plus (CSS) — la somme LB9 reste", () => {
  assert.doesNotMatch(CSS, /\.kb-act-seg|\.kb-col-activite \{/)
  assert.match(CSS, /\.kb-col-money/)
})

test("l'en-tête garde compteur + somme (LB9) — rien d'autre n'a bougé", () => {
  assert.match(SRC, /kb-col-count/)
  assert.match(SRC, /kb-col-money num/)
})
