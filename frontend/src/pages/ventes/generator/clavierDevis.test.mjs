// EDC5 — module pur `clavierDevis.js` : Entrée n'enregistre JAMAIS le devis ;
// Entrée dans une cellule passe à la ligne suivante (ou ajoute une ligne sur la
// dernière) ; Ctrl/Cmd+S et Ctrl/Cmd+Entrée enregistrent.
// Aucun navigateur : un mini-DOM (closest/matches/querySelectorAll/children)
// suffit, le module ne lit rien d'autre.
// Exécuté en CI : node --test src/pages/ventes/generator/clavierDevis.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  decisionTouche, ligneSuivante, champCorrespondant, DECISIONS,
} from './clavierDevis.js'

// ── Mini-DOM ────────────────────────────────────────────────────────────────
// Sélecteurs simples : `tag`, `[attr]`, `[attr="v"]`, `:not([…])`, listes `,`.
function correspond(el, simple) {
  const m = simple.trim().match(/^([a-z]*)(.*)$/i)
  if (m[1] && el.tagName !== m[1].toUpperCase()) return false
  const re = /(:not\()?\[([\w-]+)(?:="([^"]*)")?\]\)?/g
  let t
  while ((t = re.exec(m[2]))) {
    const [, non, nom, valeur] = t
    const present = valeur === undefined ? nom in el.attrs : el.attrs[nom] === valeur
    if (non ? present : !present) return false
  }
  return true
}
class El {
  constructor(tag, attrs = {}, enfants = []) {
    this.tagName = tag.toUpperCase()
    this.attrs = attrs
    this.type = attrs.type
    this.parent = null
    this.children = []
    for (const e of enfants) { e.parent = this; this.children.push(e) }
  }
  get nextElementSibling() {
    const freres = this.parent?.children ?? []
    return freres[freres.indexOf(this) + 1] ?? null
  }
  getAttribute(n) { return n in this.attrs ? this.attrs[n] : null }
  matches(sel) { return sel.split(',').some((s) => correspond(this, s)) }
  closest(sel) { for (let n = this; n; n = n.parent) if (n.matches(sel)) return n; return null }
  contains(n) { for (; n; n = n.parent) if (n === this) return true; return false }
  querySelectorAll(sel) {
    const out = []
    const visite = (n) => { for (const c of n.children) { if (c.matches(sel)) out.push(c); visite(c) } }
    visite(this)
    return out
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] ?? null }
}
const h = (tag, attrs, ...enfants) => new El(tag, attrs, enfants)

/** Une ligne produit : Désignation, Produit (bouton), Qté, Prix, TVA (+ base légale). */
function ligneProduit(cle, { baseLegale = false } = {}) {
  return h('tr', { 'data-line-key': cle },
    h('td', { 'data-label': 'Désignation' }, h('input', { type: 'text' })),
    h('td', { 'data-label': 'Produit (stock)' }, h('button', { type: 'button' })),
    h('td', { 'data-label': 'Qté' }, h('input', { type: 'number', 'data-role': 'line-qty' })),
    h('td', { 'data-label': 'Prix unit. TTC' }, h('input', { type: 'number' })),
    h('td', { 'data-label': 'TVA %' }, h('input', { type: 'number' }),
      ...(baseLegale ? [h('input', { type: 'text', id: `base-${cle}` })] : [])),
  )
}
/** Une ligne de section (XSAL14) : une cellule pleine largeur, sans « Qté ». */
const ligneSection = (cle) => h('tr', { 'data-line-key': cle, 'data-line-type': 'section' },
  h('td', { 'data-label': 'Section', colspan: '6' }, h('input', { type: 'text' })),
  h('td', {}, h('button', { type: 'button' })))

function formulaire(...lignes) {
  const tbody = h('tbody', {}, ...lignes)
  const form = h('form', { id: 'gen-form' },
    h('input', { type: 'text', id: 'remise' }),
    h('textarea', { id: 'note' }),
    h('input', { type: 'checkbox', id: 'composition-libre' }),
    h('button', { type: 'submit', id: 'creer' }),
    h('div', { role: 'combobox' }, h('input', { type: 'text', id: 'dans-combobox' })),
    h('div', { role: 'dialog' }, h('input', { type: 'text', id: 'dans-dialogue' })),
    h('table', {}, tbody),
  )
  return form
}
const par = (form, id) => form.querySelector(`[id="${id}"]`)
const qte = (ligne) => ligne.children[2].children[0]
const touche = (target, form, extra = {}) => ({ key: 'Enter', target, currentTarget: form, ...extra })

// ── Décisions ───────────────────────────────────────────────────────────────

test('les décisions possibles sont exactement cinq', () => {
  assert.deepEqual([...DECISIONS], ['ignorer', 'bloquer', 'ligne-suivante', 'ajouter-ligne', 'enregistrer'])
})

test('Entrée dans un champ simple (remise, facture…) : BLOQUÉE, jamais une soumission', () => {
  const form = formulaire(ligneProduit('a'))
  assert.equal(decisionTouche(touche(par(form, 'remise'), form)), 'bloquer')
})

test('Entrée dans une case à cocher : bloquée (elle y déclencherait la soumission implicite)', () => {
  const form = formulaire(ligneProduit('a'))
  assert.equal(decisionTouche(touche(par(form, 'composition-libre'), form)), 'bloquer')
})

test('Entrée dans « Qté » d’une ligne qui n’est pas la dernière : ligne suivante', () => {
  const a = ligneProduit('a')
  const form = formulaire(a, ligneProduit('b'))
  assert.equal(decisionTouche(touche(qte(a), form)), 'ligne-suivante')
})

test('Entrée sur la DERNIÈRE ligne : ajouter une ligne', () => {
  const b = ligneProduit('b')
  const form = formulaire(ligneProduit('a'), b)
  assert.equal(decisionTouche(touche(qte(b), form)), 'ajouter-ligne')
  assert.equal(decisionTouche(touche(b.children[0].children[0], form)), 'ajouter-ligne')
})

test('Maj+Entrée dans une cellule : bloquée, sans navigation', () => {
  const a = ligneProduit('a')
  const form = formulaire(a, ligneProduit('b'))
  assert.equal(decisionTouche(touche(qte(a), form, { shiftKey: true })), 'bloquer')
})

test('Entrée laissée à son sens propre : textarea, bouton, submit, combobox, dialogue imbriqué', () => {
  const form = formulaire(ligneProduit('a'))
  assert.equal(decisionTouche(touche(par(form, 'note'), form)), 'ignorer')
  assert.equal(decisionTouche(touche(par(form, 'creer'), form)), 'ignorer')
  assert.equal(decisionTouche(touche(form.querySelector('[data-label="Produit (stock)"]').children[0], form)), 'ignorer')
  assert.equal(decisionTouche(touche(par(form, 'dans-combobox'), form)), 'ignorer')
  assert.equal(decisionTouche(touche(par(form, 'dans-dialogue'), form)), 'ignorer')
})

test('cible HORS du formulaire (portail React : ProduitPicker ouvert, dialogue porté) : ignorée', () => {
  const form = formulaire(ligneProduit('a'))
  const portail = h('div', { 'data-radix-popper-content-wrapper': '' },
    h('input', { type: 'text', role: 'combobox' }))
  const recherche = portail.children[0]
  assert.equal(decisionTouche(touche(recherche, form)), 'ignorer')
  // Même avec Ctrl+S : un geste fait dans un popover porté ne soumet rien.
  assert.equal(decisionTouche(touche(recherche, form, { key: 's', ctrlKey: true })), 'ignorer')
})

test('le panneau Sheet (role="dialog") qui CONTIENT le formulaire ne le neutralise pas', () => {
  const form = formulaire(ligneProduit('a'))
  h('div', { role: 'dialog' }, form)
  assert.equal(decisionTouche(touche(par(form, 'remise'), form)), 'bloquer')
})

test('composition IME en cours, ou touche déjà traitée par le champ : ignorée', () => {
  const form = formulaire(ligneProduit('a'))
  assert.equal(decisionTouche(touche(par(form, 'remise'), form, { isComposing: true })), 'ignorer')
  // L'événement synthétique React ne porte pas `isComposing` : seul le natif le dit.
  assert.equal(decisionTouche(touche(par(form, 'remise'), form, { nativeEvent: { isComposing: true } })), 'ignorer')
  assert.equal(decisionTouche(touche(par(form, 'remise'), form, { keyCode: 229 })), 'ignorer')
  assert.equal(decisionTouche(touche(par(form, 'remise'), form, { defaultPrevented: true })), 'ignorer')
})

test('Ctrl/Cmd+S et Ctrl/Cmd+Entrée enregistrent, n’importe où dans le formulaire', () => {
  const a = ligneProduit('a')
  const form = formulaire(a)
  for (const cible of [par(form, 'remise'), par(form, 'note'), qte(a), par(form, 'composition-libre')]) {
    assert.equal(decisionTouche(touche(cible, form, { key: 's', ctrlKey: true })), 'enregistrer')
    assert.equal(decisionTouche(touche(cible, form, { key: 'S', metaKey: true })), 'enregistrer')
    assert.equal(decisionTouche(touche(cible, form, { key: 'Enter', ctrlKey: true })), 'enregistrer')
    assert.equal(decisionTouche(touche(cible, form, { key: 'Enter', metaKey: true })), 'enregistrer')
  }
  // Touche maintenue : les répétitions sont avalées (un seul enregistrement).
  assert.equal(decisionTouche(touche(par(form, 'remise'), form, { key: 's', ctrlKey: true, repeat: true })), 'bloquer')
  // Ctrl+Alt+S n'est pas un raccourci d'enregistrement.
  assert.equal(decisionTouche(touche(par(form, 'remise'), form, { key: 's', ctrlKey: true, altKey: true })), 'ignorer')
})

test('les autres touches (lettres, Tab, flèches) : ignorées', () => {
  const form = formulaire(ligneProduit('a'))
  for (const key of ['a', 'Tab', 'ArrowDown', 'Escape', 's']) {
    assert.equal(decisionTouche(touche(par(form, 'remise'), form, { key })), 'ignorer')
  }
})

// ── Navigation de cellule ───────────────────────────────────────────────────

test('ligneSuivante : saute ce qui n’est pas une ligne de devis, null sur la dernière', () => {
  const a = ligneProduit('a')
  const intrus = h('tr', {})
  const b = ligneProduit('b')
  formulaire(a, intrus, b)
  assert.equal(ligneSuivante(a), b)
  assert.equal(ligneSuivante(b), null)
})

test('champCorrespondant : même cellule, même rang de champ, ligne suivante', () => {
  const a = ligneProduit('a', { baseLegale: true })
  const b = ligneProduit('b', { baseLegale: true })
  formulaire(a, b)
  assert.equal(champCorrespondant(qte(a)), qte(b))
  // Base légale (2ᵉ champ de la cellule TVA) → base légale de la ligne suivante.
  assert.equal(champCorrespondant(a.children[4].children[1]), b.children[4].children[1])
})

test('champCorrespondant : une ligne de section (sans « Qté ») est sautée', () => {
  const a = ligneProduit('a')
  const s = ligneSection('s')
  const b = ligneProduit('b')
  formulaire(a, s, b)
  assert.equal(champCorrespondant(qte(a)), qte(b))
})

test('champCorrespondant : rien de comparable plus bas → premier champ de la ligne suivante', () => {
  const a = ligneProduit('a')
  const s = ligneSection('s')
  formulaire(a, s)
  assert.equal(champCorrespondant(qte(a)), s.children[0].children[0])
  // Dernière ligne : pas de ligne suivante (le générateur en AJOUTE une).
  assert.equal(champCorrespondant(s.children[0].children[0]), null)
})
