// 25/08/2026 — LANE NUMÉROS INTERNATIONAUX (ordre fondateur : « accepter les
// numéros non marocains »). Avant cette date, `normalizeMaPhone` (donc
// `waArmed`/`leadPhoneOk`/`waPhoneOk`/le bouton WhatsApp) rejetait TOUT
// numéro étranger, même à indicatif explicite — ces tests échouaient sur
// `main` avant l'ajout de `normalizePhoneE164` ci-dessous.
import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizePhoneE164, normalizeMaPhone } from './format.js'
import { parsePastedPhone } from './paste.js'

test('normalizePhoneE164 : marocain reconnu → 212XXXXXXXXX (même forme que normalizeMaPhone)', () => {
  assert.equal(normalizePhoneE164('0612345678'), '212612345678')
  assert.equal(normalizePhoneE164('+212612345678'), '212612345678')
  assert.equal(normalizePhoneE164('00212612345678'), '212612345678')
  assert.equal(normalizePhoneE164('612345678'), '212612345678')
  assert.equal(normalizePhoneE164('0512345678'), '212512345678')
})

test('normalizePhoneE164 : étranger à indicatif EXPLICITE (+ ou 00) accepté', () => {
  assert.equal(normalizePhoneE164('+33612345678'), '33612345678')
  assert.equal(normalizePhoneE164('+33 6 12 34 56 78'), '33612345678')
  assert.equal(normalizePhoneE164('0033612345678'), '33612345678')
  assert.equal(normalizePhoneE164('+34600123456'), '34600123456')
  assert.equal(normalizePhoneE164('+1 415 555 2671'), '14155552671')
})

test('normalizePhoneE164 : local ambigu SANS indicatif reste rejeté (jamais deviné étranger)', () => {
  assert.equal(normalizePhoneE164('33612345678'), null) // pas de + ni 00
  assert.equal(normalizePhoneE164('0812345678'), null) // ambigu, préfixe 8 marocain invalide
  assert.equal(normalizePhoneE164(''), null)
  assert.equal(normalizePhoneE164(null), null)
  assert.equal(normalizePhoneE164('abc'), null)
  assert.equal(normalizePhoneE164('+2126123456'), null) // 212 malformé, jamais glissé en "étranger"
  assert.equal(normalizePhoneE164('002126123456'), null) // même garde côté "00" international
})

// 25/08/2026 — finding 10 : régression collatérale de la lane numéros
// internationaux. La réécriture avait perdu le `lstrip('0')` post-212 — les
// graphies RÉELLES où l'usager retape le 0 local après l'indicatif
// (« +212 (0)6… », « +212 06… », « 00212 0… », usage marocain courant)
// désarmaient le bouton WhatsApp de fiches EXISTANTES qui marchaient avant.
// Miroir exact de apps.ventes.tests.test_phone_international.
// TestNormalizePhoneE164.test_212_prefix_with_rewritten_leading_zero_still_recognized.
test('normalizePhoneE164 : 212 + zéro local retapé toujours reconnu (finding 10a)', () => {
  assert.equal(normalizePhoneE164('+212 (0)6 12 34 56 78'), '212612345678')
  assert.equal(normalizePhoneE164('+212 06 12 34 56 78'), '212612345678')
  assert.equal(normalizePhoneE164('00212 0612345678'), '212612345678')
})

// 25/08/2026 — finding 10(b) : le nettoyage ne retirait que `[\s.\-()]`
// (contrairement au backend qui retire TOUT non-chiffre) — un numéro
// marocain valide saisi avec `/` ou une mention « Tel: » était donc rejeté
// ici alors que le backend l'acceptait déjà. Ajoute les cas '/' et 'Tel:'
// absents du miroir backend.
test('normalizePhoneE164 : séparateurs "/" et libellé "Tel:" reconnus (finding 10b)', () => {
  assert.equal(normalizePhoneE164('06/12/34/56/78'), '212612345678')
  assert.equal(normalizePhoneE164('Tel: 0612345678'), '212612345678')
  assert.equal(normalizePhoneE164('Tel: 06/12/34/56/78'), '212612345678')
})

test('normalizeMaPhone : délègue à normalizePhoneE164, rejette toujours l\'étranger (contrat wa.me marocain inchangé)', () => {
  // Chemins marocains — comportement historique préservé (aucune régression).
  assert.equal(normalizeMaPhone('0612345678'), '212612345678')
  assert.equal(normalizeMaPhone('123'), null)
  assert.equal(normalizeMaPhone('0812345678'), null)
  // Un étranger valide (accepté par normalizePhoneE164) reste null ici : ce
  // normaliseur reste le filtre "marocain uniquement" pour les usages qui en
  // ont explicitement besoin.
  assert.equal(normalizeMaPhone('+33612345678'), null)
})

test('parsePastedPhone : accepte/prévisualise un étranger à indicatif explicite (avant : silencieusement ignoré)', () => {
  assert.equal(parsePastedPhone('+33 6 12 34 56 78'), '+33612345678')
  assert.equal(parsePastedPhone('00 33 6 12 34 56 78'), '+33612345678')
  // Toujours rien pour un texte non reconnaissable, ou un local ambigu sans
  // indicatif (jamais de valeur inventée).
  assert.equal(parsePastedPhone('0812345678'), null)
  assert.equal(parsePastedPhone('Ahmed Alami'), null)
  // Le chemin marocain existant n'est pas affecté.
  assert.equal(parsePastedPhone('0612345678'), '+212612345678')
})
