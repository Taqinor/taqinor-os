// APX7 — Telephone ET tablette : 5+ leads par etape, `hover:none` servi a
// TOUTE largeur.
// ----------------------------------------------------------------------------
// Le COMPTAGE (>=5 cartes en 390x844, >=4 sur le projet tablet) appartient a la
// gate e2e APX8. Ce fichier verrouille la REGLE qui rend ce comptage possible
// sur les deux appareils a la fois, et qu'une future edition casserait sans
// bruit : l'anatomie tactile est pilotee par `hover:none`, JAMAIS par une
// largeur d'ecran — sinon l'iPad (large, mais sans survol) retomberait sur
// l'anatomie « bureau » et ses actions deviendraient inatteignables (VX68).
//   node --test src/pages/crm/leads/views/LeadCardTouchAnatomy.apx7.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const SRC = lf(readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8'))
const CSS = lf(readFileSync(join(HERE, '../../../../index.css'), 'utf8'))

const bloc = () => {
  const i = CSS.indexOf('APX7 — TELEPHONE ET TABLETTE')
  assert.ok(i > -1, 'bloc CSS APX7 introuvable')
  const debut = CSS.lastIndexOf('/*', i)
  const suivant = CSS.indexOf('/* ====', i)
  return suivant > -1 ? CSS.slice(debut, suivant) : CSS.slice(debut)
}
const declarations = () => bloc().replace(/\/\*[\s\S]*?\*\//g, '')

test('APX7 : AUCUNE largeur d\'ecran ne pilote l\'anatomie — uniquement hover/pointer', () => {
  const d = declarations()
  const medias = d.match(/@media[^{]+/g) ?? []
  assert.ok(medias.length >= 2, 'le bloc APX7 doit contenir au moins les deux media queries hover')
  for (const m of medias) {
    assert.doesNotMatch(m, /width/, `APX7 ne doit JAMAIS dependre d'une largeur : ${m.trim()}`)
    assert.match(m, /hover:\s*(hover|none)|pointer:\s*coarse/)
  }
  // Les deux mondes sont bien couverts.
  assert.match(d, /@media \(hover: none\)/)
  assert.match(d, /@media \(hover: hover\)/)
})

test('APX7 : les actions rapides vivent sur la LIGNE DU MONTANT (L2), plus dans la zone revelee', () => {
  const valueStart = SRC.indexOf('<div className="kb-card-value">')
  const valueEnd = SRC.indexOf('{/* ── L3 / PIED', valueStart)
  assert.ok(valueEnd > valueStart, 'zone valeur introuvable')
  assert.match(SRC.slice(valueStart, valueEnd), /<div className="kb-quick" aria-label="Actions rapides">/)
  // Et plus dans la zone revelee.
  const revealStart = SRC.indexOf('<div className="kb-card-reveal">')
  assert.doesNotMatch(SRC.slice(revealStart), /className="kb-quick"/)
})

test('APX7 : UN SEUL exemplaire des liens tel/WhatsApp dans le DOM (aucun doublon tactile)', () => {
  // Un doublon « version tactile » dupliquerait le nom accessible et casserait
  // le contrat « les hrefs tel/wa sont toujours dans le DOM, une fois ».
  assert.equal((SRC.match(/className="kb-quick-btn kb-quick-tel"/g) || []).length, 1)
  assert.equal((SRC.match(/className="kb-quick-btn kb-quick-wa"/g) || []).length, 1)
  assert.equal((SRC.match(/aria-label=\{`Appeler \$\{nomComplet\}`\}/g) || []).length, 1)
})

test('APX7 : au TOUCHER la zone revelee se referme (c\'est elle qui coutait ~36 px/carte)', () => {
  const d = declarations()
  const touch = d.slice(d.indexOf('@media (hover: none)'))
  assert.match(touch, /\.kb-card--lead > \.kb-card-reveal \{[^}]*max-height: 0;/s)
  assert.match(touch, /\.kb-card--lead \.kb-card-value > \.kb-quick \{[^}]*opacity: 1;/s)
  assert.match(touch, /\.kb-card--lead \.kb-card-value \{[^}]*min-height: 44px;/s)
})

test('APX7 : le focus CLAVIER DEPLIE toujours reellement, meme en pointeur grossier', () => {
  // Tablette + clavier externe : rien ne doit devenir « tabbable invisible ».
  // (F) — mais `:focus-within` ne distinguait pas le clavier du DOIGT : sur
  // iOS, taper un controle interne lui donne le focus, et la carte depliait
  // ses 14rem animees sous le pouce a chaque tap. `:has(:focus-visible)` porte
  // exactement l'intention d'origine (le focus que le navigateur juge devoir
  // MONTRER = clavier externe, pas le tap).
  const d = declarations()
  const touch = d.slice(d.indexOf('@media (hover: none)'))
  assert.match(touch, /\.kb-card--lead:has\(:focus-visible\) > \.kb-card-reveal \{[^}]*max-height: 14rem;/s)
  assert.doesNotMatch(touch, /:focus-within > \.kb-card-reveal/)
})

test('APX7 : en pointeur FIN, les actions n\'occupent aucune largeur au repos', () => {
  // Dans une rangee flex, `max-height: 0` ne suffit pas : sans annuler la
  // largeur, les boutons pousseraient le montant meme invisibles.
  const d = declarations()
  const fin = d.slice(d.indexOf('@media (hover: hover)'))
  assert.match(fin, /\.kb-card--lead \.kb-card-value > \.kb-quick \{[^}]*max-width: 0;/s)
  assert.match(fin, /:hover \.kb-card-value > \.kb-quick,\s*\n\s*\.kb-card--lead:focus-within \.kb-card-value > \.kb-quick \{[^}]*max-width: none;/s)
})

test('APX7 : toutes les cibles tactiles restent >= 44 px (regle LB17 conservee)', () => {
  // La regle LB17 `@media (pointer: coarse)` couvre tel/wa/flash.
  assert.match(CSS, /@media \(pointer: coarse\) \{[\s\S]{0,900}?\.kb-quick-tel,\s*\n\s*\.kb-quick-wa,[\s\S]{0,200}?width: 44px;/)
  // Le menu ••• et la case gardent leur overlay 44x44.
  assert.match(CSS, /\.kb-check-hit::before,\s*\n\s*\.kb-card-menu-btn::before/)
})

test('APX7 : « Devis auto » ne double pas le menu ••• sur la ligne tactile', () => {
  const d = declarations()
  const touch = d.slice(d.indexOf('@media (hover: none)'))
  assert.match(touch, /\.kb-card--lead \.kb-card-value > \.kb-quick > \.kb-flash \{\s*\n\s*display: none;\s*\n\s*\}/)
  // ... parce que l'item existe bel et bien dans le menu.
  assert.match(SRC, /\{onAutoQuote && lead\.devis_auto\?\.pret && \(\s*\n\s*<DropdownMenuItem onSelect=\{\(\) => onAutoQuote\(lead\)\}>/)
})

test('APX7 : acquis intacts — swipe LB17 inerte, snap LB42, PII, clic-carte', () => {
  assert.match(SRC, /inert=\{swipe\.offset === 0\}/)
  assert.match(SRC, /resolveSwipeSnap/)
  assert.match(SRC, /\{lead\.pii_masked \? \(/)
  assert.match(SRC, /onClick=\{onOpen \? \(\) => onOpen\(lead\) : undefined\}/)
})

test('APX7 : aucun hex en dur', () => {
  assert.doesNotMatch(declarations(), /#[0-9a-fA-F]{3,8}\b/)
})
