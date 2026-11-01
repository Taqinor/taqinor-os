// SONDE = {constat: "C-AANA-VER-006", sha: "32375fe65",
//   attendu: "/reporting, conversion {10 devis, 3 acceptés, 15 factures} : la barre « Factures émises » affiche 150 % et la barre « Devis acceptés » recalcule le taux à l écran"}
// Sonde Node (source réelle de Reporting.jsx + formatPercent) : `node docs/audits/sondes/AANA/C-AANA-VER-006.mjs .` ; sortie 0 = REPRO.
// Sonde AANA29 : sur le fixture de la tâche {10,3,15}, l'écran /reporting affiche-t-il encore un % > 100 ?
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
export async function sonde(repo) {
  const src = readFileSync(`${repo}/frontend/src/pages/Reporting.jsx`, 'utf8')
  const { formatPercent } = await import(pathToFileURL(`${repo}/frontend/src/lib/format.js`).href)
  const m = src.match(/function ConversionBar\(\{[^}]*\}\)\s*\{\s*const pct = ([^\n]+)/)
  const pctOf = new Function('value', 'max', `return ${m[1]}`)
  const conversion = { nb_devis: 10, nb_acceptes: 3, nb_factures: 15, taux_acceptation_pct: 30 }
  const barres = [...src.matchAll(/<ConversionBar label="([^"]+)" value=\{conversion\.(\w+)\} max=\{conversion\.(\w+)\}/g)]
    .map(([, label, v, mx]) => ({ label, affiche: formatPercent(pctOf(conversion[v], conversion[mx])) }))
  const fact = barres.find(b => b.label === 'Factures émises')
  return { repro: !!fact && /150/.test(fact.affiche), barres }
}
const r = await sonde(process.argv[2] || '.'); console.log(JSON.stringify(r)); console.log('verdict : ' + (r.repro ? 'REPRO' : 'NON REPRODUIT')); process.exit(r.repro ? 0 : 1)
