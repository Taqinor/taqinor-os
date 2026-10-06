// QJR602 (D-QJR5-13, fondateur 30/09/2026) — une taille EXPLICITE est
// respectée TELLE QUELLE par le devis automatique : plus d'arrondi au palier
// de 5 kWc. L'avis « Palier appliqué » de cet onglet (QJR41/QJR245) n'a donc
// plus d'objet et disparaît : la cible tapée ici est celle qui part.
//
// Historique : QJR41 puis QJR245 avaient ajouté une notice parce que 6,5 kWc
// devenait 5 kWc au bouton pendant que le serveur en composait 10 panneaux.
// Le comportement exécuté de `createAutoQuote` est verrouillé dans
// `src/features/ventes/autoQuote.tailleExplicite.test.jsx`.
//
// DevisTab.jsx est du JSX non exécutable par `node --test` : la partie
// « source » lit le fichier en texte (fichier gelé du cliquet CRM CRX41) ;
// la conversion kWc → panneaux, elle, est exécutée avec la VRAIE fonction.
//
// Run : node --test src/features/crm/workspace/DevisTabKwcPalier.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { panneauxPourKwc, PANEL_W_DEFAUT } from '../../ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisTab.jsx'), 'utf8')

test('QJR602 — plus aucun avis de palier dans DevisTab.jsx', () => {
  assert.doesNotMatch(SRC, /noticePalierKwc/,
    'le devis auto n\'arrondit plus : aucun avis de palier à annoncer')
  assert.doesNotMatch(SRC, /lw-devis-kwc-palier/)
  assert.doesNotMatch(SRC, new RegExp(['arrondir', 'AuPasKwc'].join('')))
})

test('QJR41 — le champ EZ5 « ne rejette ni n\'arrondit jamais une saisie » reste intact', () => {
  assert.match(SRC, /ce champ ne rejette ni n'arrondit jamais une saisie/)
  assert.match(SRC, /value=\{kwcCible\}\s*\n\s*onChange=\{\(e\) => setKwcCible\(e\.target\.value\)\}/,
    'le champ doit continuer à porter/écrire la saisie brute, sans arrondi')
})

test('QJR602 — 6,5 kWc tapés → 10 panneaux de 710 W (jamais le palier 5 kWc = 8 panneaux)', () => {
  assert.equal(PANEL_W_DEFAUT, 710)
  assert.equal(panneauxPourKwc(6.5, PANEL_W_DEFAUT), 10)
  assert.notEqual(panneauxPourKwc(6.5, PANEL_W_DEFAUT), panneauxPourKwc(5, PANEL_W_DEFAUT))
})
