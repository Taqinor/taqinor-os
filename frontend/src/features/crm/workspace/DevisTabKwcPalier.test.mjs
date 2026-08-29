// QJR41 (audit L3 29/08/2026, origine generator-frontend-13/R4-B2.14) — le
// calage à 5 kWc du chemin auto est la doctrine fondateur du 18/08
// (`autoQuote.js:146-152`, `arrondirAuPasKwc`) : aucun devis auto ne sort une
// taille hors palier de 5 kWc. Ce n'est PAS retiré ici. Le champ « Puissance
// cible (kWc) » de cet onglet (commentaire EZ5, `DevisTab.jsx`) promet lui-même
// « ce champ ne rejette ni n'arrondit jamais une saisie » — et RIEN dans
// l'interface ne disait au commercial qu'un 6,5 tapé deviendrait 5. Ce
// correctif ajoute UNIQUEMENT la notice ; aucun changement de la règle
// d'arrondi (vérifié ci-dessous par un import RÉEL de `arrondirAuPasKwc`,
// pas une formule recopiée).
//
// DevisTab.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules pour son propre rendu React : la partie « source » de ce test
// lit donc le fichier en texte, même patron que ToitureDesignCibleAvec.test.mjs
// / DevisGeneratorBuildDimensionnementAvec.test.mjs. `solar.js`, lui, est un
// module PUR (aucun JSX, aucune dépendance React — voir son en-tête
// « Pure functions, no I/O ») : la partie « comportement » importe donc la
// VRAIE fonction `arrondirAuPasKwc`, pas une réplique qui pourrait diverger.
//
// Run : node --test src/features/crm/workspace/DevisTabKwcPalier.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { arrondirAuPasKwc } from '../../ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisTab.jsx'), 'utf8')

test('QJR41 — DevisTab.jsx importe la VRAIE arrondirAuPasKwc de solar.js (jamais une formule dupliquée)', () => {
  assert.match(SRC, /import \{ arrondirAuPasKwc \} from '\.\.\/\.\.\/ventes\/solar'/,
    'DevisTab.jsx doit lire le palier depuis la même source que autoQuote.js (solar.js), jamais un calcul propre')
})

test('QJR41 — le calage à 5 kWc (autoQuote.js:146-152) n\'est PAS retiré : le champ EZ5 « ne rejette ni n\'arrondit jamais une saisie » reste intact', () => {
  assert.match(SRC, /ce champ ne rejette ni n'arrondit jamais une saisie/,
    'le commentaire EZ5 doit rester : le champ continue de ne rien arrondir lui-même')
  // `value={kwcCible}` doit rester la valeur BRUTE tapée par le commercial —
  // jamais `kwcPalierApplique` (qui, lui, n'alimente que la notice).
  assert.match(SRC, /value=\{kwcCible\}\s*\n\s*onChange=\{\(e\) => setKwcCible\(e\.target\.value\)\}/,
    'le champ doit continuer à porter/écrire la saisie brute, sans arrondi')
})

test('QJR41 — une notice FR nomme le palier appliqué, visible seulement quand la saisie et le palier divergent', () => {
  assert.match(SRC, /const kwcPalierApplique = kwcCibleNum > 0 \? arrondirAuPasKwc\(kwcCibleNum\) : null/,
    'kwcPalierApplique doit être dérivé de kwcCible via arrondirAuPasKwc, jamais une constante')
  assert.match(SRC, /const kwcPalierDivergent = kwcPalierApplique != null && kwcPalierApplique !== kwcCibleNum/,
    'la notice doit être conditionnée à une VRAIE divergence saisie/palier')
  assert.match(SRC, /\{kwcPalierDivergent && \(/,
    'la notice doit être masquée quand la saisie est déjà sur un palier (ou vide)')
  assert.match(SRC, /data-testid="lw-devis-kwc-palier"/,
    'la notice doit porter un data-testid stable')
  assert.match(SRC, /Palier appliqué : <strong>\{kwcPalierApplique\} kWc<\/strong>/,
    'la notice doit nommer explicitement le palier APPLIQUÉ')
})

test('QJR41 — rejoué avec la VRAIE arrondirAuPasKwc importée de solar.js : 6,5 → notice « Palier appliqué : 5 kWc »', () => {
  // Reproduit EXACTEMENT la dérivation verrouillée par le 3ᵉ test ci-dessus,
  // mais avec l'implémentation réelle importée (pas une copie).
  const derive = (kwcCible) => {
    const kwcCibleNum = parseFloat(kwcCible)
    const kwcPalierApplique = kwcCibleNum > 0 ? arrondirAuPasKwc(kwcCibleNum) : null
    const kwcPalierDivergent = kwcPalierApplique != null && kwcPalierApplique !== kwcCibleNum
    return { kwcCibleNum, kwcPalierApplique, kwcPalierDivergent }
  }

  // Cas nommé par le « Done = » de QJR41 : saisir 6,5 → devis auto à 5 kWc,
  // notice visible nommant le palier 5.
  const cas65 = derive('6.5')
  assert.equal(cas65.kwcPalierApplique, 5, 'le devis auto (autoQuote.js) sort bien à 5 kWc pour une saisie de 6,5')
  assert.equal(cas65.kwcPalierDivergent, true, 'la notice doit être visible : 6,5 ≠ 5')

  // Saisie DÉJÀ sur un palier : aucune notice (comportement inchangé).
  const cas5 = derive('5')
  assert.equal(cas5.kwcPalierApplique, 5)
  assert.equal(cas5.kwcPalierDivergent, false, 'aucune notice quand la saisie est déjà un palier exact')

  // Champ vide (mode historique — dimensionnement serveur/lead) : aucune notice.
  const casVide = derive('')
  assert.equal(casVide.kwcPalierApplique, null)
  assert.equal(casVide.kwcPalierDivergent, false, 'champ vide = comportement historique inchangé, jamais de notice')

  // Autre palier que 5 (12 → 10) : la notice généralise, pas un cas isolé.
  const cas12 = derive('12')
  assert.equal(cas12.kwcPalierApplique, 10)
  assert.equal(cas12.kwcPalierDivergent, true)

  // Saisie négative/0 : jamais de notice (même garde que arrondirAuPasKwc,
  // qui ne rend jamais 0).
  const casZero = derive('0')
  assert.equal(casZero.kwcPalierApplique, null)
  assert.equal(casZero.kwcPalierDivergent, false)
})

test('QJR41 — la notice affiche la saisie en notation FR (virgule), jamais le point brut du champ number', () => {
  assert.match(SRC, /String\(kwcCible\)\.trim\(\)\.replace\('\.', ','\)/,
    'la saisie affichée dans la notice doit convertir le point (input type=number) en virgule FR')
})
