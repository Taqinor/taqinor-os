// AMET90 — écrivain de l'ENREGISTREMENT d'acceptation (contrat AMET88 :
// docstring de `scripts/check_acceptation.py`, qui le relit). Pur Node, sans
// Playwright : la spec l'appelle en `afterAll`, l'orchestrateur en CLI pour
// fusionner ses étapes jouées hors spec (P1-P4 d'un groupe) :
//   node e2e/acceptation/_enregistrement.js <G> --etapes-supplementaires <fichier.json>
// (<fichier.json> = liste d'étapes au format results.json, ou {couvre, etapes}).
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const RACINE = fileURLToPath(new URL('../../../', import.meta.url))
export const ORACLES = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
const DOSSIER = 'docs/audits/acceptation'
const CAPTURES = 'docs/qa-explorer/captures'

/** Date LOCALE du rejeu (AAAA-MM-JJ). */
export function aujourdHui(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Sha rejoué : ACCEPTATION_SHA, sinon `git rev-parse HEAD` du dépôt. */
export function shaRejoue() {
  if (process.env.ACCEPTATION_SHA) return process.env.ACCEPTATION_SHA.trim()
  return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: RACINE, encoding: 'utf8' }).trim()
}

/** Chemin (relatif au dépôt) de la capture d'une étape. */
export function cheminCapture(groupe, id, date = aujourdHui()) {
  return `${CAPTURES}/${date}/ACCEPTATION-${groupe}-${id}.jpg`
}

const etapeComplete = (e) => !!(e && e.id && e.taches?.length && ['PASS', 'FAIL'].includes(e.verdict)
  && e.trace && ORACLES.every((o) => ['PASS', 'FAIL', 'NA'].includes(e.oracles?.[o])))

/** Construit {res, md} : results.json (fait foi) + vue humaine à en-tête YAML. */
export function composer({ groupe, sha, date, couvre, couvreAvecEcart = [], etapes }) {
  const vues = new Set(etapes.flatMap((e) => e.taches || []))
  const sansEtape = couvre.filter((t) => !vues.has(t))
  const ok = etapes.length > 0 && sansEtape.length === 0
    && etapes.every((e) => etapeComplete(e) && e.verdict === 'PASS')
  const res = {
    sha, date, groupe, verdict: ok ? 'PASS' : 'FAIL',
    // Un id sans étape rendrait l'enregistrement non conforme : il est retiré
    // de `couvre` (et nommé dans la vue humaine), le verdict tombe à FAIL.
    couvre: couvre.filter((t) => vues.has(t)),
    couvre_avec_ecart: couvreAvecEcart.filter((t) => vues.has(t)),
    etapes,
  }
  const liste = (xs) => `[${xs.join(', ')}]`
  const tete = [
    '---', `sha: ${sha}`, `date: ${date}`, `groupe: ${groupe}`, `couvre: ${liste(res.couvre)}`,
    `couvre_avec_ecart: ${liste(res.couvre_avec_ecart)}`, `verdict: ${res.verdict}`, 'etapes:',
    ...etapes.flatMap((e) => [`  - id: ${e.id}`, `    tache: ${liste(e.taches || [])}`,
      `    verdict: ${e.verdict}`]),
    '---',
  ]
  const corps = [
    '', `# Acceptation ${groupe} — ${date} (${sha.slice(0, 9)})`, '',
    'Produit par `frontend/e2e/acceptation/_enregistrement.js` (AMET90) ; le `.results.json` frère fait foi ;',
    'relu par `python scripts/check_acceptation.py`. Oracles = qa-explorer 1-10 (`_format.md`).', '',
    `| Étape | Tâches | Verdict | ${ORACLES.join(' | ')} | Trace |`,
    `|---|---|---|${ORACLES.map(() => '---').join('|')}|---|`,
    ...etapes.map((e) => `| ${e.id} | ${(e.taches || []).join(', ')} | ${e.verdict} | `
      + `${ORACLES.map((o) => e.oracles?.[o] ?? '?').join(' | ')} | ${e.trace || '—'} |`),
    '',
    ...etapes.filter((e) => e.notes).map((e) => `- ${e.id} : ${e.notes}`),
    ...(sansEtape.length ? [`- NON COUVERTS (aucune étape) : ${sansEtape.join(', ')}`] : []),
    '',
  ]
  return { res, md: [...tete, ...corps].join('\n') }
}

/** Écrit (ou complète) l'enregistrement du groupe pour ce sha et ce jour.
 *  Les étapes déjà présentes d'une autre source (P1-P4 de l'orchestrateur) sont
 *  conservées ; une étape de même id est remplacée. Renvoie les chemins. */
export function ecrire({ groupe, couvre, couvreAvecEcart = [], etapes, sha = shaRejoue(), date = aujourdHui() }) {
  const dossier = join(RACINE, DOSSIER, groupe)
  const base = join(dossier, `${date}-${sha.slice(0, 9)}`)
  let precedent = { couvre: [], couvre_avec_ecart: [], etapes: [] }
  if (existsSync(`${base}.results.json`)) precedent = JSON.parse(readFileSync(`${base}.results.json`, 'utf8'))
  const ids = new Set(etapes.map((e) => e.id))
  const toutes = [...precedent.etapes.filter((e) => !ids.has(e.id)), ...etapes]
  const union = (a, b) => [...new Set([...(a || []), ...(b || [])])]
  const { res, md } = composer({
    groupe, sha, date, etapes: toutes,
    couvre: union(precedent.couvre, couvre),
    couvreAvecEcart: union(precedent.couvre_avec_ecart, couvreAvecEcart),
  })
  mkdirSync(dossier, { recursive: true })
  writeFileSync(`${base}.results.json`, `${JSON.stringify(res, null, 2)}\n`, 'utf8')
  writeFileSync(`${base}.md`, md, 'utf8')
  return { md: `${base}.md`, json: `${base}.results.json`, verdict: res.verdict }
}

// ── CLI : fusion d'étapes jouées hors spec ────────────────────────────────────
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [groupe, option, fichier] = process.argv.slice(2)
  if (!groupe || option !== '--etapes-supplementaires' || !fichier) {
    console.error('usage : node e2e/acceptation/_enregistrement.js <G> --etapes-supplementaires <fichier.json>')
    process.exit(2)
  }
  const lu = JSON.parse(readFileSync(fichier, 'utf8'))
  const etapes = Array.isArray(lu) ? lu : lu.etapes || []
  const incompletes = etapes.filter((e) => !etapeComplete(e)).map((e) => e?.id || '?')
  if (incompletes.length) {
    console.error(`étape(s) vide(s) ou incomplète(s) : ${incompletes.join(', ')}`)
    process.exit(1)
  }
  const sortie = ecrire({ groupe, couvre: Array.isArray(lu) ? [] : lu.couvre || [], etapes })
  console.log(`${sortie.verdict} — ${sortie.md}`)
}
