// LB17 — Tactile (cibles ≥44px par STYLESHEET, jamais une taille inline) + PII.
// La case de sélection est enveloppée d'un label `.kb-check-hit` (zone de
// frappe 44×44 en pointeur coarse via ::before, sans décaler la mise en page) ;
// le menu ••• et les actions rapides passent à 44px au toucher ; quand
// `lead.pii_masked` (le serializer nullifie tel/whatsapp sans la permission
// client_pii_voir), un cadenas 12px tooltipé remplace les actions d'appel.
// La moitié DOM (case .kb-check-hit, cadenas PII) est montée dans KanbanView.test.jsx (ENF15) ; reste ici la feuille de style.
//   node --test src/pages/crm/leads/views/LeadCardTouchPII.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { resolveCss } from '../../../../test/readCss.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const CSS = resolveCss(join(HERE, '../../../../index.css'))

test('LB17 : les cibles tactiles 44px vivent dans la feuille de style (pointer: coarse)', () => {
  assert.match(CSS, /@media \(pointer: coarse\)/)
  assert.match(CSS, /\.kb-check-hit::before[\s\S]{0,200}width: 44px/)
  // menu ••• et actions rapides passent aussi à 44px au toucher.
  assert.match(CSS, /\.kb-quick-tel,\s*\n\s*\.kb-quick-wa,\s*\n\s*\.kb-flash\.kb-quick-btn \{\s*\n\s*width: 44px/)
})
