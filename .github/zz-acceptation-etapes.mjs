// TEMPORAIRE (zz-scratch-acc-l5-preuves2) : compose les étapes ACAL440 (perf avant/après) et ACAL482 (téléphone
// WebKit) au format results.json, fusionnées par `frontend/e2e/acceptation/_enregistrement.js`. Supprimé au dernier commit.
import { readFileSync, writeFileSync } from 'node:fs'

const lire = (f) => { try { return readFileSync(f, 'utf8') } catch { return '' } }
const env = process.env
const run = `run ${env.GITHUB_RUN_ID} (sha ${String(env.ACCEPTATION_SHA).slice(0, 9)})`
const na = Object.fromEntries(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'].map((o) => [o, 'NA']))
const budgets = (t) => [...t.matchAll(/\[ACAL440\] (.+)$/gm)].map((m) => m[1].trim())
const resume = (t) => (t.match(/^\s+\d+ (passed|failed|skipped|flaky|did not run).*$/gm) || []).map((x) => x.trim()).join(' ; ')
const lignesTests = (t) => (t.match(/^\s+(✓|✘|-)\s+\d+ .*$/gm) || []).map((l) => l.trim())
const [pa, pv, tel] = [lire('/tmp/perf-apres.log'), lire('/tmp/perf-avant.log'), lire('/tmp/tel.log')]
const [ba, bv] = [budgets(pa), budgets(pv)]
const rel = env.CAPT.replace(/^\.\.\//, '')

const ok440 = env.APRES === '0' && env.AVANT === '0' && ba.length === 2 && bv.length === 2
const t440 = `${rel}/ACCEPTATION-ACAL-PA2.3-ACAL440-perf-avant-apres.txt`
writeFileSync(`../${t440}`, [
  `ACAL440 — frontend/e2e/calepinage-perf.spec.js sur runner GitHub (CI=1, projet chromium, fond de repli), ${run}.`,
  "Glissé d'un PANNEAU sur 20 pas souris (mode « Déplacer les panneaux », note du mode disposition relue, centre de",
  "carte inchangé) ; 500 modules posés verbatim (placement libre) sur un toit de 68 × 56 m autour de l'épingle de",
  "l'exemple, résumé « 500 panneaux » vérifié avant la mesure. Plafond CI = seuil « mauvais » INP de vitals.js.",
  '', `Après ACAL431+433 (code courant) — ${resume(pa)} :`, ...ba.map((b) => `  ${b}`), ...lignesTests(pa).map((l) => `  ${l}`),
  '', `Avant ACAL431+433 (commits 68e485efd1 et 9abfad83d9 retirés de ciel.ts/scene3d.ts/panelTexture.ts, front reconstruit) — ${resume(pv)} :`,
  ...bv.map((b) => `  ${b}`), ...lignesTests(pv).map((l) => `  ${l}`), '',
].join('\n'))

const okTel = env.TEL === '0'
const t482 = `${rel}/ACCEPTATION-ACAL-PA2.6-ACAL482-telephone-webkit.txt`
writeFileSync(`../${t482}`, [
  `ACAL482 — frontend/e2e/calepinage-atelier-telephone.spec.js (test.use iPhone 13, 390 × 844 → WebKit) sur runner, ${run}.`,
  `Résultat : ${resume(tel)}`, ...lignesTests(tel), '',
].join('\n'))

const axe = lire('/tmp/a11y.log')
const okAxe = env.AXE === '0' && !/\d+ (skipped|failed|did not run)/.test(resume(axe)) && /\d+ passed/.test(resume(axe))
const t439 = `${rel}/ACCEPTATION-ACAL-PA2.6-ACAL439-a11y-axe.txt`
writeFileSync(`../${t439}`, [
  `ACAL439 — frontend/e2e/calepinage-a11y.spec.js (axe-core, WCAG 2.1 A/AA, toute gravité, thèmes clair et sombre) sur runner, ${run}.`,
  `Résultat : ${resume(axe)}`, ...lignesTests(axe), '',
].join('\n'))

const etapes = [
  {
    id: 'PA2.6-ACAL439-a11y-axe', taches: ['ACAL439'], verdict: okAxe ? 'PASS' : 'FAIL', base_verdict: null,
    corps: okAxe ? 'PASS' : 'FAIL', oracles: na, trace: t439,
    notes: `axe-core sur liste, création, atelier (rail), onglets Production et Documents, clair et sombre, ${run} : ${resume(axe) || 'aucun résultat'} (0 violation exigée, aucun test sauté)`,
  },
  {
    id: 'PA2.3-ACAL440-perf-500-modules', taches: ['ACAL440'], verdict: ok440 ? 'PASS' : 'FAIL', base_verdict: null,
    corps: ok440 ? 'PASS' : 'FAIL', oracles: na, trace: t440,
    notes: `glissé d'un panneau (mode disposition) sur 500 modules, ${run} — après ACAL431+433 : ${ba.join(' ; ') || 'aucune mesure'} ; avant : ${bv.join(' ; ') || 'aucune mesure'}`,
  },
  {
    id: 'PA2.6-ACAL482-telephone-webkit', taches: ['ACAL482'], verdict: okTel ? 'PASS' : 'FAIL', base_verdict: null,
    corps: okTel ? 'PASS' : 'FAIL', oracles: { ...na, 3: okTel ? 'PASS' : 'FAIL' }, trace: t482,
    notes: `spec téléphone sous WebKit réel (iPhone 13, 390 × 844), ${run} : ${resume(tel) || 'aucun résultat'} ; liste, fiche et onglet releve sans défilement horizontal ; oracle 3 = pageerror relevé par la spec`,
  },
]
writeFileSync('/tmp/etapes-supp.json', JSON.stringify(etapes, null, 2))
console.log(JSON.stringify(etapes.map((e) => [e.id, e.verdict])))
