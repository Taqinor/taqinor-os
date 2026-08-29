// QJR39 (audit L3 29/08/2026, origine generator-frontend-12 / R4-B2.13) — le
// générateur initialise `quoteLogic.productible: null` (QX38, commentaire à
// l'état initial), mais le fetch des réglages société (`parametresApi.
// getProfile()`) reconstruisait l'objet entier avec `setQuoteLogic({...})`
// SANS jamais lire `data?.productible_kwh_kwc` (CompanyProfile.
// productible_kwh_kwc, exposé tel quel — CompanyProfileSerializer,
// `fields = '__all__'`) : la surcharge société n'était donc JAMAIS appliquée
// à l'écran, et l'écran + le PDF pouvaient citer deux productibles différents
// pour le même devis. Le réglage exposé côté Paramètres était mort.
//
// Correctif : lire `data?.productible_kwh_kwc`, le poser dans `quoteLogic.
// productible` — repli EXPLICITE sur `null` (jamais une constante d'écran,
// `productibleForCity` sait déjà retomber sur le PVGIS par ville).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE, même patron que les autres
// tests QJR de ce fichier.
//
// Run : node --test src/pages/ventes/DevisGeneratorProductibleSociete.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { productibleForCity } from '../../features/ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('QJR39 — quoteLogic.productible est initialisé à null (surcharge société absente par défaut)', () => {
  assert.match(DG, /const \[quoteLogic, setQuoteLogic\] = useState\(\{[\s\S]{0,700}productible: null,/)
})

test('QJR39 — le fetch des réglages société lit productible_kwh_kwc et le pose dans quoteLogic (setQuoteLogic ne l\'omet plus)', () => {
  const idx = DG.indexOf("const prod = parseFloat(data?.productible_kwh_kwc)")
  assert.ok(idx > -1, 'la lecture de productible_kwh_kwc est introuvable')
  const bloc = DG.slice(idx, idx + 700)
  assert.match(bloc, /setQuoteLogic\(\{/)
  assert.match(bloc,
    /productible: \(Number\.isFinite\(prod\) && prod > 0\) \? prod : null,/,
    'productible doit être posé avec repli EXPLICITE sur null, jamais une constante')
  // Les 4 autres champs restent posés dans le MÊME appel setQuoteLogic (pas
  // un second setState qui pourrait arriver dans un ordre différent).
  assert.match(bloc, /kwhPrice:/)
  assert.match(bloc, /efficiency:/)
  assert.match(bloc, /tvaStandard:/)
  assert.match(bloc, /tvaPanneaux:/)
})

test('QJR39 — quoteLogic.productible alimente déjà productibleForCity (ROI + ROI avec) : le point de lecture existant profite du correctif sans autre changement', () => {
  const occurrences = DG.match(/productibleForCity\(\s*\n\s*selectedLead\?\.ville \|\| '', quoteLogic\.productible\)/g) || []
  assert.equal(occurrences.length, 2,
    'productibleForCity(ville, quoteLogic.productible) doit rester appelé aux 2 sites existants (roi + roiAvec)')
})

test('QJR39 — rejoué avec le VRAI productibleForCity(solar.js) : société avec surcharge → productible de la société ; société sans surcharge (absente ou 1600 pile) → comportement inchangé (PVGIS ville)', () => {
  // Reproduit la résolution verrouillée par le 2ᵉ test.
  const resoudreProductible = (dataProductibleKwhKwc) => {
    const prod = parseFloat(dataProductibleKwhKwc)
    return (Number.isFinite(prod) && prod > 0) ? prod : null
  }

  // Société AVEC surcharge réelle (≠ 1600) : l'écran doit citer CETTE valeur,
  // quelle que soit la ville du lead.
  const surcharge = resoudreProductible('1750.0')
  assert.equal(surcharge, 1750)
  assert.equal(productibleForCity('casablanca', surcharge), 1750,
    'une surcharge société réelle doit primer sur le PVGIS de la ville')
  assert.equal(productibleForCity('marrakech', surcharge), 1750)

  // Société SANS réglage (champ absent du profil, ex. company jamais éditée) :
  // repli null → productibleForCity retombe sur le PVGIS par ville, comme
  // avant ce correctif (comportement STRICTEMENT inchangé).
  const sansReglage = resoudreProductible(undefined)
  assert.equal(sansReglage, null)
  assert.equal(productibleForCity('casablanca', sansReglage),
    productibleForCity('casablanca', null),
    'sans surcharge, le résultat doit être identique au comportement historique (override=null)')

  // Société dont le champ vaut littéralement 1600 (le défaut backend même
  // quand rien n'a été personnalisé, selectors.py) : `productibleForCity`
  // le traite comme « pas une vraie surcharge » (écart < 0,5) → PVGIS ville,
  // byte-identique au cas sans réglage.
  const defautBackend = resoudreProductible('1600.0')
  assert.equal(productibleForCity('casablanca', defautBackend),
    productibleForCity('casablanca', null))
})
