// LW1 — P0 : le corps de la fiche lead ne scrollait pas (le `<form>` L1264
// n'avait aucune classe, la règle morte `.modal > form` d'index.css ne
// matchait plus rien depuis VX89 → `.modal-body` n'était jamais borné, le
// bouton « Enregistrer »/submit était inatteignable sur petit viewport, en
// Dialog ET en Sheet mobile). Fix : donner au `<form>` la classe explicite
// `flex flex-col flex-1 min-h-0 overflow-hidden` (fonctionne en parent grid
// ET flex, comme `.modal > form` le faisait pour le shell legacy).
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormLW1ScrollFix.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const FORM_SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')
const CSS_SRC = readFileSync(join(HERE, '../../index.css'), 'utf8')

test('LW1 : le <form> porte les classes qui le bornent en hauteur (flex parent ET grid parent)', () => {
  assert.match(
    FORM_SRC,
    /<form onSubmit=\{handleSubmit\} noValidate className="flex flex-col flex-1 min-h-0 overflow-hidden">/,
  )
})

test('LW1 : la règle `.modal > form` d\'index.css reste intacte (portée par UsersManagement, VX89)', () => {
  assert.match(CSS_SRC, /\.modal > form \{/)
  // Elle garde son couple flex:1 + min-height:0 + overflow:hidden — la même
  // recette que la classe posée sur le <form> de LeadForm.
  const ruleMatch = CSS_SRC.match(/\.modal > form \{[^}]*\}/)
  assert.ok(ruleMatch, 'la règle .modal > form doit exister')
  assert.match(ruleMatch[0], /flex:\s*1/)
  assert.match(ruleMatch[0], /min-height:\s*0/)
  assert.match(ruleMatch[0], /overflow:\s*hidden/)
})

test('LW1 : .modal-body garde flex:1 + overflow-y:auto (le conteneur qui doit défiler)', () => {
  const bodyMatch = CSS_SRC.match(/\.modal-body \{[^}]*\}/)
  assert.ok(bodyMatch, '.modal-body doit exister')
  assert.match(bodyMatch[0], /flex:\s*1/)
  assert.match(bodyMatch[0], /overflow-y:\s*auto/)
})
