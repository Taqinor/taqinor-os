// APX26 — UNE seule timeline de chantier + bandeau « Prochaine action » partagé.
// Verrouille : (1) la fiche ne monte plus qu'un composant de timeline ;
// (2) les jalons datés vivent dans le stepper, y compris quand aucune étape
// n'est configurée (rien n'est perdu) ; (3) la progression « n/total » est en
// tête ; (4) les DEUX sites consomment `ui/NextActionBanner` en conservant
// leurs `data-testid` d'origine (ch6-next-action / mj-next-action).
//
//   node --test src/pages/installations/ChantierTimelineFusion.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (p) => readFileSync(join(HERE, p), 'utf8')

const FICHE = read('InstallationDetail.jsx')
const GATE = read('ChantierGateTimeline.jsx')
const BANNER = read('../../ui/NextActionBanner.jsx')
const JOURNEE = read('../interventions/MaJourneePage.jsx')
const UI_INDEX = read('../../ui/index.js')

test('la fiche chantier ne monte plus qu\'UNE timeline', () => {
  assert.equal(FICHE.includes('<ChantierTimeline'), false,
    'ChantierTimeline est encore monté directement dans la fiche')
  assert.equal(/import ChantierTimeline from/.test(FICHE), false,
    'import mort de ChantierTimeline dans la fiche')
  assert.equal((FICHE.match(/<ChantierGateTimeline/g) ?? []).length, 1)
  assert.match(FICHE, /<ChantierGateTimeline installationId=\{id\} installation=\{current\}/)
})

test('les jalons datés sont rendus par le stepper — même sans étape configurée', () => {
  assert.match(GATE, /import ChantierTimeline from '\.\/ChantierTimeline'/)
  assert.match(GATE, /function JalonsBand\(\{ installation \}\)/)
  assert.equal((GATE.match(/<JalonsBand/g) ?? []).length, 2,
    'JalonsBand rendu deux fois : cas dégradé + cas nominal')
  const degrade = GATE.slice(GATE.indexOf('if (stages.length === 0)'), GATE.indexOf('const rang ='))
  assert.match(degrade, /<JalonsBand installation=\{installation\} \/>/,
    'les jalons disparaîtraient quand aucune étape n\'est configurée')
  // Le contrat de la spec CH6 existante : pas de `ch6-gate-timeline` en dégradé.
  assert.equal(degrade.includes('ch6-gate-timeline'), false)
})

test('progression « n/total » en tête du stepper', () => {
  assert.match(GATE, /data-testid="ch6-progress"/)
  assert.match(GATE, /<Progress/)
  assert.match(GATE, /\{rang\}\/\{stages\.length\}/)
  // Le rang est celui de l'étape courante (1-indexé), pas un compteur inventé.
  assert.match(GATE, /const rang = idx >= 0 \? idx \+ 1 :/)
})

test('un seul bandeau « Prochaine action » partagé par les deux surfaces', () => {
  assert.match(UI_INDEX, /export \* from '\.\/NextActionBanner'/)
  assert.match(BANNER, /export function NextActionBanner/)
  // Le libellé n'est écrit qu'UNE fois, dans le composant partagé.
  assert.match(BANNER, /Prochaine action/)
  for (const [nom, src] of [['ChantierGateTimeline', GATE], ['MaJourneePage', JOURNEE]]) {
    assert.match(src, /<NextActionBanner/, `${nom} n'utilise pas le composant partagé`)
    assert.equal(/<strong className="text-info">Prochaine action/.test(src), false,
      `${nom} rend encore son propre bandeau`)
  }
  // Les crochets e2e/tests existants survivent.
  assert.match(GATE, /data-testid="ch6-next-action"/)
  assert.match(JOURNEE, /data-testid="mj-next-action"/)
  assert.match(GATE, /data-testid="ch6-avancer-btn"/)
})

test('le bandeau partagé ne pose pas d\'encre illisible sur le fond info clair', () => {
  // `--info-foreground` est fait pour un fond info PLEIN (blanc en clair) :
  // sur `bg-info/10` il serait blanc sur blanc.
  assert.equal(BANNER.includes('text-info-foreground'), false)
  assert.match(BANNER, /bg-info\/10/)
})
