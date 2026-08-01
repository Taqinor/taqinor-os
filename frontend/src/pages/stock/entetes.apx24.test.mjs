// APX24 — UN seul idiome d'en-tête pour les écrans Stock.
// État d'avant : 12 pages en `<h1>` nu, 3 en `<h2>` nu — chacune avec son
// propre `<header>` réécrit à la main (icône parfois là, parfois pas ; accent
// jamais). Note : le plan annonçait « 7 déjà sur PageHeader » — le code disait
// ZÉRO (aucun fichier de pages/stock/ n'importait le composant).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const read = (f) => readFileSync(path.join(__dirname, f), 'utf8')

// Les 15 écrans balayés (les autres fichiers du dossier sont des composants,
// pas des pages : tableau, formulaire, sélecteur…).
const BALAYES = [
  'BonsCommandeFournisseur.jsx', 'CategoriesStock.jsx', 'ConditionnementsProduit.jsx',
  'FacturesFournisseur.jsx', 'FournisseurFiche360.jsx', 'FournisseursStock.jsx',
  'InventairesAnnuels.jsx', 'LotsEntrepot.jsx', 'ModelesBcf.jsx',
  'MouvementsPage.jsx', 'OcrStockImport.jsx', 'ReceptionsFournisseur.jsx',
  'RetoursFournisseur.jsx', 'RevalorisationsStock.jsx', 'StockList.jsx',
]

test('plus aucun en-tête de page écrit à la main dans pages/stock/', () => {
  const offenders = []
  for (const f of readdirSync(__dirname)) {
    if (!f.endsWith('.jsx') || f.includes('.test.')) continue
    const src = read(f)
    // Un `<header>` de page réécrit à la main, ou un titre de page nu.
    if (/<header[\s>]/.test(src)) offenders.push(`${f} (<header> maison)`)
    if (/<h1 className="font-display/.test(src)) offenders.push(`${f} (<h1> nu)`)
    if (/<h2 className="font-display text-xl/.test(src)) offenders.push(`${f} (<h2> nu)`)
  }
  assert.deepEqual(offenders, [], offenders.join(', '))
})

test('les 15 écrans rendent l’en-tête unique ui/PageHeader', () => {
  for (const f of BALAYES) {
    const src = read(f)
    assert.match(src, /import \{ PageHeader \} from '\.\.\/\.\.\/ui\/PageHeader'/, `${f} : import`)
    assert.match(src, /<PageHeader\b/, `${f} : non rendu`)
  }
})

test('chaque en-tête porte une icône ET l’accent de la famille inventaire', () => {
  for (const f of BALAYES) {
    const src = read(f)
    assert.match(src, /<PageHeader[\s\S]{0,400}?icon=\{/, `${f} : icône absente`)
    assert.match(src, /'--module-accent': INVENTAIRE_ACCENT/, `${f} : accent absent`)
    // L'accent vient de la source unique, jamais d'une couleur en dur.
    assert.doesNotMatch(src, /'--module-accent': '#/, `${f} : couleur en dur`)
  }
})

test('le niveau de titre n’est pas rétrogradé en silence', () => {
  // Les écrans qui portaient un <h1> le gardent (PageHeader a gagné un
  // `headingAs` optionnel, défaut 'h2' — donc byte-identique pour tous les
  // consommateurs existants).
  const kit = readFileSync(path.join(__dirname, '..', '..', 'ui', 'PageHeader.jsx'), 'utf8')
  assert.match(kit, /headingAs = 'h2'/)
  assert.match(kit, /const Heading = headingAs === 'h1' \? 'h1' : 'h2'/)
  for (const f of ['BonsCommandeFournisseur.jsx', 'CategoriesStock.jsx',
    'FournisseurFiche360.jsx', 'InventairesAnnuels.jsx', 'LotsEntrepot.jsx',
    'RevalorisationsStock.jsx']) {
    assert.match(read(f), /headingAs="h1"/, `${f} : niveau de titre perdu`)
  }
  // Ceux qui portaient un <h2> restent en h2 (défaut) : pas de `headingAs`.
  for (const f of ['MouvementsPage.jsx', 'StockList.jsx', 'OcrStockImport.jsx']) {
    assert.doesNotMatch(read(f), /headingAs="h1"/, `${f} : niveau de titre changé`)
  }
})
