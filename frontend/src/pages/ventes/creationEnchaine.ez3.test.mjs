// EZ3 — Créer un devis mène à l'ENVOYER (fin de l'abandon post-création).
// Audit des 5 trajets : devis 3 kWc → WhatsApp coûtait 8-9 clics, dont un
// ABANDON juste après la création — `finish()` en pleine page renvoyait sur la
// liste NUE en JETANT l'id du devis qu'on venait de construire, obligeant à le
// re-chercher. (Le mode embarqué, lui, recevait déjà `onDone(devisId)`.)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const gen = readFileSync(path.join(__dirname, 'DevisGenerator.jsx'), 'utf8')
const liste = readFileSync(path.join(__dirname, 'DevisList.jsx'), 'utf8')

test('l’id du devis créé n’est plus jeté', () => {
  assert.doesNotMatch(gen, /const finish = \(devisId\) => \{[\s\S]{0,160}?navigate\('\/ventes\/devis'\)/)
  assert.match(gen, /const finish = \(devisId, devisData\) => \{/)
  // Le panneau de succès porte le numéro ET le total du devis.
  assert.match(gen, /data-testid="devis-succes"/)
  assert.match(gen, /\{succes\.reference \|\| '—'\}/)
  assert.match(gen, /formatMoney\(succes\.total\)/)
})

test('le mode EMBARQUÉ est byte-identique (il recevait déjà l’id)', () => {
  assert.match(gen, /if \(embedded\) \{ onDone\?\.\(devisId\); return \}/)
  // Le panneau de succès ne s'affiche jamais en embarqué.
  assert.match(gen, /if \(succes && !embedded\) \{/)
})

test('l’action SUIVANTE est offerte : envoyer, aperçu, retour ciblé', () => {
  assert.match(gen, /data-testid="succes-whatsapp"[\s\S]{0,80}?|\/ventes\/devis\?devis=\$\{succes\.id\}&envoyer=1/)
  assert.match(gen, /navigate\(`\/ventes\/devis\?devis=\$\{succes\.id\}&envoyer=1`\)/)
  assert.match(gen, /navigate\(`\/ventes\/devis\?devis=\$\{succes\.id\}&apercu=1`\)/)
  // Le retour à la liste pointe le devis (surlignage QX12 déjà livré).
  assert.match(gen, /navigate\(`\/ventes\/devis\?devis=\$\{succes\.id\}`\)/)
})

test('la liste enchaîne sur les flux EXISTANTS, jamais un second chemin', () => {
  assert.match(liste, /searchParams\.get\('envoyer'\) === '1'/)
  assert.match(liste, /searchParams\.get\('apercu'\) === '1'/)
  // `envoyer` réutilise handleEnvoyer (aperçu WhatsApp existant, QX22) et
  // `apercu` le panneau PDF inline d'APX14 — aucun nouveau flux.
  assert.match(liste, /if \(envoyer\) handleEnvoyer\(highlightedDevis\)/)
  assert.match(liste, /else setPreviewDevis\(highlightedDevis\)/)
  // L'enchaînement ne se déclenche qu'UNE fois et consomme son paramètre.
  assert.match(liste, /enchaineFait\.current = true/)
  assert.match(liste, /next\.delete\('envoyer'\)/)
})

test('budget de clics : création → WhatsApp prêt en 2 clics', () => {
  // 1) « Envoyer par WhatsApp » du panneau de succès → la liste s'ouvre avec
  //    l'aperçu WhatsApp du bon devis DÉJÀ affiché ;
  // 2) « Ouvrir WhatsApp » dans cet aperçu (le seul geste qui envoie vraiment,
  //    QX22 — la modale ne marque JAMAIS « envoyé » à l'ouverture).
  assert.match(liste, /const openWhatsApp = async \(\) => \{/)
  // Aucune recherche intermédiaire : l'id voyage dans l'URL.
  assert.match(gen, /succes\.id/)
})
