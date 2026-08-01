// APX12 — UN seul langage de KPI d'argent dans Ventes.
// Trois implémentations de carte KPI coexistaient : le bandeau 5 statuts de
// DevisList (des `<div>` nus), le cockpit trésorerie de FactureList (qui
// régressait VX129 avec des glyphes TEXTE `▲`/`▼` — seul site du dossier), et
// le rail du générateur dont le total héros ne portait NI `.num` NI chiffres
// tabulaires. Les trois passent par `ui/Stat.jsx`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const read = (f) => readFileSync(path.join(__dirname, f), 'utf8')

const SURFACES = ['DevisList.jsx', 'FactureList.jsx', 'DevisGenerator.jsx']

test('plus aucun glyphe de tendance en TEXTE dans pages/ventes/ (VX129)', () => {
  const offenders = []
  for (const f of readdirSync(__dirname)) {
    if (!f.endsWith('.jsx')) continue
    if (/[▲▼]/.test(read(f))) offenders.push(f)
  }
  assert.deepEqual(offenders, [], `glyphe ▲/▼ encore présent : ${offenders.join(', ')}`)
})

test('les 3 surfaces KPI parlent le même langage (ui/Stat)', () => {
  for (const f of SURFACES) {
    const src = read(f)
    assert.match(src, /\n\s*Stat,/, `${f} : Stat non importé depuis le kit`)
    assert.match(src, /<Stat\b/, `${f} : Stat non rendu`)
  }
})

test('le total héros du rail du générateur est bien un Stat (donc .num tabulaire)', () => {
  const src = read('DevisGenerator.jsx')
  assert.match(src, /<Stat[\s\S]{0,300}?data-testid="gen-rail-total"/)
  // `tone="impact"` pose l'accent de module sur le montant héros.
  assert.match(src, /<Stat\s+tone="impact"/)
  // Le montant n'est plus un `<div className="text-2xl font-bold">` maison.
  assert.doesNotMatch(src, /text-2xl font-bold text-foreground">\{formatMoney\(kpiTotal\)\}/)
})

test('le bandeau 5 statuts de DevisList n’est plus fait de div nus', () => {
  const src = read('DevisList.jsx')
  assert.doesNotMatch(src, /<div key=\{key\} className="rounded-lg border border-border bg-card p-3">/)
  assert.match(src, /<Stat[\s\S]{0,200}?key=\{key\}/)
})

test('le cockpit trésorerie rend ses 4 cartes en Stat', () => {
  const src = read('FactureList.jsx')
  const start = src.indexOf('cockpit trésorerie : 4 cartes KPI')
  assert.ok(start > 0, 'bloc trésorerie introuvable')
  const treso = src.slice(start, src.indexOf('Tabs + vues enregistrées', start))
  // Une carte = une balise ouvrante suivie d'un saut de ligne (les mentions
  // `<Stat>` en prose dans les commentaires ne comptent pas).
  const cards = (treso.match(/<Stat\r?\n/g) || []).length
  assert.equal(cards, 4, 'les 4 cartes trésorerie doivent être des <Stat>')
})
