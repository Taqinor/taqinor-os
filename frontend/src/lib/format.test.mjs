import test from 'node:test'
import assert from 'node:assert/strict'
import {
  toNumber, formatMAD, formatNumber, formatPercent,
  formatDate, formatDateTime, formatPhoneMA, canonicalPhoneMA, normalizeMaPhone,
  timeAgo, nbsp,
} from './format.js'

// Intl fr-FR utilise des espaces insécables variables (U+00A0 / U+202F) comme
// séparateur de milliers — on normalise pour des assertions stables.
const norm = (s) => s.replace(/[  \s]/g, ' ').trim()

test('toNumber: nombres, chaînes fr/en, invalides', () => {
  assert.equal(toNumber(1234.5), 1234.5)
  assert.equal(toNumber('1234.56'), 1234.56)
  assert.equal(toNumber('1 234,56'), 1234.56)
  assert.equal(toNumber('1.234,56'), 1234.56)
  assert.equal(toNumber('19 %'), 19)
  assert.equal(toNumber(''), null)
  assert.equal(toNumber(null), null)
  assert.equal(toNumber('abc'), null)
  assert.equal(toNumber(NaN), null)
})

// ERR106 — Sans virgule décimale, un point est un VRAI point décimal : un
// nombre technique « 1.234 » reste 1,234 et n'est PAS écrasé en 1234. Les
// points de milliers ne sont retirés que dans la notation fr (virgule présente).
test('toNumber: décimale « 1.234 » préservée (pas un séparateur de milliers)', () => {
  assert.equal(toNumber('1.234'), 1.234)
  assert.equal(toNumber('0.500'), 0.5)
  assert.equal(toNumber('12.000'), 12) // vraie décimale .000
  // Notation fr avec virgule : le point RESTE un séparateur de milliers.
  assert.equal(toNumber('1.234,5'), 1234.5)
  assert.equal(toNumber('1.234.567,89'), 1234567.89)
})

test('formatMAD: 2 décimales + suffixe MAD, tiret si invalide', () => {
  assert.equal(norm(formatMAD(1234.5)), '1 234,50 MAD')
  assert.equal(norm(formatMAD(0)), '0,00 MAD')
  assert.equal(norm(formatMAD('1234.5', { decimals: 0 })), '1 235 MAD')
  assert.equal(norm(formatMAD(1000, { withSymbol: false })), '1 000,00')
  assert.equal(formatMAD(null), '—')
  assert.equal(formatMAD('xx'), '—')
})

test('formatNumber + formatPercent', () => {
  assert.equal(norm(formatNumber(1234567)), '1 234 567')
  assert.equal(norm(formatNumber(3.14159, { decimals: 2 })), '3,14')
  assert.equal(norm(formatPercent(19)), '19 %')
  assert.equal(norm(formatPercent(0.5, { decimals: 1 })), '0,5 %')
  assert.equal(formatPercent(null), '—')
})

test('formatDate / formatDateTime jj/mm/aaaa', () => {
  const iso = '2026-06-18T14:05:00Z'
  assert.equal(formatDate('2026-06-18'), '18/06/2026')
  assert.match(formatDate(iso, { long: true }), /juin 2026/)
  assert.match(formatDateTime(iso), /18\/06\/2026/)
  assert.equal(formatDate(null), '—')
  assert.equal(formatDate('pas une date'), '—')
})

// VX75 — variante longue de formatDateTime (« 18 juin 2026, 14:05 »), ajoutée
// pour éliminer le dernier toLocaleString natif ad hoc (AppointmentBooker.jsx).
test('formatDateTime: variante long= « 18 juin 2026, 14:05 »', () => {
  const iso = '2026-06-18T14:05:00Z'
  assert.match(formatDateTime(iso, { long: true }), /juin 2026/)
  assert.match(formatDateTime(iso, { long: true }), /14:05|15:05/)
  assert.equal(formatDateTime(null, { long: true }), '—')
})

// VX30 — timeAgo() extrait de TicketsPage.jsx en util partagé (bandeau de
// fraîcheur du mur de flotte + chatter tickets).
test('timeAgo: instant / minutes / heures / repli date', () => {
  const now = Date.now()
  assert.equal(timeAgo(new Date(now - 10 * 1000)), "à l'instant")
  assert.equal(timeAgo(new Date(now - 5 * 60 * 1000)), 'il y a 5 min')
  assert.equal(timeAgo(new Date(now - 3 * 3600 * 1000)), 'il y a 3 h')
  // Au-delà de 24 h : repli sur formatDate (jj/mm/aaaa), jamais un
  // toLocaleDateString brut.
  const huit_jours = new Date(now - 8 * 24 * 3600 * 1000)
  assert.equal(timeAgo(huit_jours), formatDate(huit_jours))
  assert.equal(timeAgo(null), '—')
  assert.equal(timeAgo('pas une date'), '—')
})

test('formatPhoneMA: local + international', () => {
  assert.equal(formatPhoneMA('0612345678'), '06 12 34 56 78')
  assert.equal(formatPhoneMA('06 12-34 56 78'), '06 12 34 56 78')
  assert.equal(formatPhoneMA('+212612345678'), '+212 6 12 34 56 78')
  assert.equal(formatPhoneMA('00212612345678'), '+212 6 12 34 56 78')
  assert.equal(formatPhoneMA('212612345678'), '+212 6 12 34 56 78')
  assert.equal(formatPhoneMA(''), '')
  // non reconnu → renvoyé tel quel, sans exception
  assert.equal(formatPhoneMA('1234'), '1234')
})

test('canonicalPhoneMA: forme de stockage/dédup', () => {
  assert.equal(canonicalPhoneMA('0612345678'), '+212612345678')
  assert.equal(canonicalPhoneMA('+212 6 12 34 56 78'), '+212612345678')
  assert.equal(canonicalPhoneMA('06 12-34 56 78'), '+212612345678')
  assert.equal(canonicalPhoneMA('0712345678'), '+212712345678')
  assert.equal(canonicalPhoneMA(''), '')
})

// L853 — miroir exact de normalize_ma_phone (apps/ventes/utils/phone.py) :
// sert à valider/désactiver le bouton WhatsApp côté front.
test('normalizeMaPhone: format wa.me 212XXXXXXXXX ou null', () => {
  assert.equal(normalizeMaPhone('0612345678'), '212612345678')
  assert.equal(normalizeMaPhone('+212612345678'), '212612345678')
  assert.equal(normalizeMaPhone(' +212 (6) 12-34-56-78 '), '212612345678')
  assert.equal(normalizeMaPhone('00212612345678'), '212612345678')
  assert.equal(normalizeMaPhone('612345678'), '212612345678')
  // vide / non normalisable → null (bouton désactivé)
  assert.equal(normalizeMaPhone(''), null)
  assert.equal(normalizeMaPhone(null), null)
  assert.equal(normalizeMaPhone('   '), null)
  assert.equal(normalizeMaPhone('abc'), null)
})

// LW7 (recon 05 P2#6) — avant, TOUTE suite de chiffres passait
// (`normalizeMaPhone('123')` renvoyait « 212123 ») : leadPhoneOk/waPhoneOk
// étaient vrais pour du bruit, le bouton WhatsApp s'armait sur un numéro
// invalide et l'envoi partait au 400 serveur. La validation est désormais
// alignée sur canonicalPhoneMA : 9 chiffres locaux commençant par 5/6/7.
test('LW7 : normalizeMaPhone rejette (null) tout ce qui n\'est pas un numéro marocain valide', () => {
  assert.equal(normalizeMaPhone('123'), null) // trop court, bruit
  assert.equal(normalizeMaPhone('0812345678'), null) // préfixe local 8 : ni 5, 6 ni 7
  assert.equal(normalizeMaPhone('06123456789'), null) // trop long (10 chiffres locaux)
  assert.equal(normalizeMaPhone('0612345'), null) // trop court (7 chiffres locaux)
  // formats valides, y compris avec espaces/parenthèses/indicatif complet.
  assert.equal(normalizeMaPhone('+212 6 12 34 56 78'), '212612345678')
  assert.equal(normalizeMaPhone('0512345678'), '212512345678') // fixe (5) valide aussi
  assert.equal(normalizeMaPhone('0712345678'), '212712345678')
  // alignée sur canonicalPhoneMA : un numéro que canonicalPhoneMA rejette
  // (renvoyé tel quel, sans le former en « +212… ») est aussi null ici.
  assert.equal(canonicalPhoneMA('0812345678'), '0812345678')
  assert.equal(normalizeMaPhone('0812345678'), null)
})

// VX122 — finesse française : espace fine insécable (U+202F) devant : ; ! ?
test('nbsp: espace fine insécable devant la ponctuation double', () => {
  assert.equal(nbsp('Priorité :'), 'Priorité :')
  assert.equal(nbsp('Priorité :').codePointAt(8), 0x202f)
  assert.equal(nbsp('Attention !'), 'Attention !')
  assert.equal(nbsp('Vraiment ?'), 'Vraiment ?')
  assert.equal(nbsp('a; b'), 'a ; b')
  // idempotent : n'accumule pas une seconde espace fine
  assert.equal(nbsp(nbsp('Priorité :')), 'Priorité :')
  // remplace une espace normale/insécable existante, ne l'ajoute pas en plus
  assert.equal(nbsp('Titre :'), 'Titre :')
  assert.equal(nbsp(''), '')
  assert.equal(nbsp(null), null)
})
