// VX222 — « Relancer ce devis » : le pendant devis de la relance facture.
// Un devis « Envoyé » propose « Relancer » → MÊME modale WhatsApp en mode
// relance (message de rappel, pas envoi initial) + note au chatter (VX97) ;
// aperçu-puis-clic, jamais d'envoi automatique ; l'action n'existe que sur
// `statut === 'envoye'`. Test SOURCE (aucun node_modules dans ce worktree).
//   node --test src/pages/ventes/DevisListVX222Relance.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { lireSourcesDevisList } from './devisList/lireSources.mjs'

// SPL203 — DevisList.jsx + devisList/*.{js,jsx} (le code suit ses déplacements).
const SRC = lireSourcesDevisList()

test('VX222 : un bouton « Relancer » n\'apparaît que sur un devis « envoye »', () => {
  // SPL203 — épingle sur le commentaire du BOUTON (DevisRow), unique dans les
  // sources concaténées (le handler porte aussi « VX222 — « Relancer » »).
  const btn = SRC.slice(SRC.indexOf('VX222 — « Relancer » : pendant devis'),
    SRC.indexOf('VX222 — « Relancer » : pendant devis') + 700)
  assert.match(btn, /d\.statut === 'envoye'/)
  assert.match(btn, /onClick=\{\(\) => handleRelancer\(d\)\}/)
  assert.match(btn, /Relancer/)
})

test('VX222 : « Relancer » rouvre l\'aperçu WhatsApp EXISTANT en mode relance (lecture seule)', () => {
  // handleRelancer arme le mode relance PUIS réutilise handleEnvoyer
  // (whatsappPreviewDevis) — aucune action mutante à l\'ouverture.
  assert.match(SRC, /const handleRelancer = \(d\) => \{ setRelanceMode\(true\); handleEnvoyer\(d\) \}/)
  assert.match(SRC, /const \[relanceMode, setRelanceMode\] = useState\(false\)/)
})

test('VX222 : fermer la modale réinitialise le mode relance (un « Envoyer » ultérieur repart en mode initial)', () => {
  const closeBody = SRC.slice(SRC.indexOf('const closeWaModal ='),
    SRC.indexOf('const closeWaModal =') + 160)
  assert.match(closeBody, /setRelanceMode\(false\)/)
})

test('VX222 : le clic réel « Ouvrir WhatsApp » en mode relance porte un message de RAPPEL', () => {
  const openBody = SRC.slice(SRC.indexOf('const openWhatsApp = async'),
    SRC.indexOf('const openWhatsApp = async') + 900)
  assert.match(openBody, /if \(relanceMode\)/)
  assert.match(openBody, /buildRelanceWaUrl\(waData, waTarget\.reference\)/)
})

test('VX222 : la relance est consignée au chatter du devis (noterDevis) et jamais bloquante', () => {
  const openBody = SRC.slice(SRC.indexOf('const openWhatsApp = async'),
    SRC.indexOf('const openWhatsApp = async') + 1200)
  assert.match(openBody, /ventesApi\.noterDevis\(/)
  assert.match(openBody, /Relance du devis/)
  assert.match(openBody, /\.catch\(\(\) => \{\}\)/)
})

test('VX222 : le message de rappel réutilise le lien public déjà émis (waData.url), pas de nouvel appel', () => {
  const helper = SRC.slice(SRC.indexOf('function buildRelanceMessage'),
    SRC.indexOf('function buildRelanceMessage') + 500)
  assert.match(helper, /waData\?\.url/)
  assert.match(helper, /petit rappel concernant votre devis/)
})
