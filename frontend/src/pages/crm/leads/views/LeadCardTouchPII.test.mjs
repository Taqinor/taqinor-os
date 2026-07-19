// LB17 — Tactile (cibles ≥44px par STYLESHEET, jamais une taille inline) + PII.
// La case de sélection est enveloppée d'un label `.kb-check-hit` (zone de
// frappe 44×44 en pointeur coarse via ::before, sans décaler la mise en page) ;
// le menu ••• et les actions rapides passent à 44px au toucher ; quand
// `lead.pii_masked` (le serializer nullifie tel/whatsapp sans la permission
// client_pii_voir), un cadenas 12px tooltipé remplace les actions d'appel.
// Verified against SOURCE + la feuille de style (no node_modules ici).
//   node --test src/pages/crm/leads/views/LeadCardTouchPII.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')
const CSS = readFileSync(join(HERE, '../../../../index.css'), 'utf8')

test('LB17 : la case de sélection est enveloppée du label .kb-check-hit (cible ≥44px, pas de taille inline)', () => {
  assert.match(SRC, /<label\s*\n?\s*className="kb-check-hit"/)
  assert.match(SRC, /className="kb-card-check"/)
  // La case n'impose AUCUNE taille inline (interdit par la règle coarse-pointer).
  const checkStart = SRC.indexOf('className="kb-card-check"')
  const checkBlock = SRC.slice(checkStart, checkStart + 300)
  assert.doesNotMatch(checkBlock, /style=\{\{/)
})

test('LB17 : les cibles tactiles 44px vivent dans la feuille de style (pointer: coarse)', () => {
  assert.match(CSS, /@media \(pointer: coarse\)/)
  assert.match(CSS, /\.kb-check-hit::before[\s\S]{0,200}width: 44px/)
  // menu ••• et actions rapides passent aussi à 44px au toucher.
  assert.match(CSS, /\.kb-quick-tel,\s*\n\s*\.kb-quick-wa,\s*\n\s*\.kb-flash\.kb-quick-btn \{\s*\n\s*width: 44px/)
})

test('LB17 : PII masquée → cadenas tooltipé « Coordonnées masquées (permission PII) »', () => {
  assert.match(SRC, /import \{[^}]*\bLock\b[^}]*\} from 'lucide-react'/)
  assert.match(SRC, /\{lead\.pii_masked \? \(/)
  assert.match(SRC, /className="kb-quick-lock"/)
  assert.match(SRC, /title="Coordonnées masquées \(permission PII\)"/)
  assert.match(SRC, /<Lock size=\{12\} aria-hidden="true" \/>/)
})
