// ESSAI TEMPORAIRE (13/11/2026) — fusionne dans UN enregistrement ATST (contrat AMET88) :
//   * l'enregistrement écrit par la spec navigateur `frontend/e2e/acceptation/atst.spec.js` (ATST27) ;
//   * les étapes hors navigateur de `.github/zz-scratch-atst/rejeu.py` (hote + django).
// Supprimé avec le workflow au dernier commit.
//   node .github/zz-scratch-atst/fusion.mjs <dossier_artefacts>
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { ecrire, ORACLES, RACINE } from '../../frontend/e2e/acceptation/_enregistrement.js'

const ART = process.argv[2]
const SHA = process.env.ACCEPTATION_SHA
const G = 'ATST'

function* fichiers(dossier) {
  if (!existsSync(dossier)) return
  for (const n of readdirSync(dossier, { withFileTypes: true })) {
    const p = join(dossier, n.name)
    if (n.isDirectory()) yield* fichiers(p)
    else yield p
  }
}

// 1. Enregistrement de la spec (artefacts `atst-spec-enr` = docs/audits/acceptation/ATST/,
//    `atst-spec-captures` = docs/qa-explorer/captures/) : il fixe la DATE (jour du rejeu navigateur).
const tous = [...fichiers(ART)]
const specMd = tous.find((p) => /atst-spec-enr[\/]\d{4}-\d{2}-\d{2}-[0-9a-f]{9}\.results\.json$/.test(p))
const date = specMd ? specMd.match(/(\d{4}-\d{2}-\d{2})-[0-9a-f]{9}\.results\.json$/)[1] : new Date().toISOString().slice(0, 10)
const dossierG = join(RACINE, 'docs/audits/acceptation', G)
mkdirSync(dossierG, { recursive: true })
for (const p of tous) {
  const m = p.match(/atst-spec-(enr|captures)[\/](.+)$/)
  if (!m) continue
  const dest = join(RACINE, m[1] === 'enr' ? `docs/audits/acceptation/${G}` : 'docs/qa-explorer/captures', m[2])
  mkdirSync(join(dest, '..'), { recursive: true })
  copyFileSync(p, dest)
}
console.log(`date = ${date} ; spec : ${specMd || 'ABSENTE'}`)

// 2. Étapes hors navigateur : une trace texte par étape (journal complet du rejeu).
const traces = `docs/audits/acceptation/${G}/traces/${date}`
mkdirSync(join(RACINE, traces), { recursive: true })
const etapes = []
for (const section of ['hote', 'django']) {
  const json = tous.find((p) => p.includes(`atst-${section}`) && p.endsWith('etapes.json'))
  if (!json) { console.log(`section ${section} : etapes.json ABSENT`); continue }
  for (const e of JSON.parse(readFileSync(json, 'utf8'))) {
    const trace = `${traces}/${e.id}.txt`
    copyFileSync(join(json, '..', e.log), join(RACINE, trace))
    etapes.push({
      id: e.id, taches: e.taches, verdict: e.verdict, base_verdict: null, trace,
      // Hors navigateur : aucun des oracles 1-10 n'est observable (ni page, ni réseau, ni console).
      oracles: Object.fromEntries(ORACLES.map((o) => [o, 'NA'])),
      notes: `rejeu runner (${section}, .github/zz-scratch-atst/rejeu.py @ ${SHA.slice(0, 9)}) : ${e.notes}`,
    })
  }
}
const sortie = ecrire({ groupe: G, couvre: [...new Set(etapes.flatMap((e) => e.taches))], etapes, sha: SHA, date })
console.log(`${sortie.verdict} — ${sortie.md}`)
