// VX22 — Vérification structurelle (node --test, sans vitest/jsdom disponible
// dans ce worktree) : la fiche lead doit être adressable via une vraie route
// `/crm/leads/:id`, distincte de la liste `/crm/leads`, chargeant sa propre
// page dédiée (LeadDetailPage) plutôt que de dépendre du cache de la liste.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const configSrc = readFileSync(path.join(__dirname, 'module.config.jsx'), 'utf8')

test('module.config.jsx importe LeadDetailPage en lazy', () => {
  assert.match(
    configSrc,
    /const LeadDetailPage = lazy\(\(\)\s*=>\s*import\('\.\.\/\.\.\/pages\/crm\/leads\/LeadDetailPage'\)\)/,
  )
})

test('la route /crm/leads/:id est enregistrée et pointe sur LeadDetailPage', () => {
  assert.match(
    configSrc,
    /\{\s*path:\s*'\/crm\/leads\/:id',\s*component:\s*LeadDetailPage\s*\}/,
  )
})

test('la route liste /crm/leads reste distincte (LeadsPage, jamais écrasée)', () => {
  assert.match(configSrc, /\{\s*path:\s*'\/crm\/leads',\s*component:\s*LeadsPage\s*\}/)
})
