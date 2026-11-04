// ACVI75 — preuve en direct : la sonde de parcours `docs/audits/sondes/ACVI/parcours-PA1.py` rejouée sur la pile locale
// (scripts/sonde.py : transaction annulée, base inchangée) — chaque étape de la table PA1 rafraîchie (création → cadence
// contact → qualification → visite planifiée → terminée → validée, négatifs société B) passe sans 5xx ni fuite
// `prix_achat` (`repro: false` = aucun écart) ; puis la garde `scripts/check_parcours.py` relit la table.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { assurerSessionPage } from '../helpers.js'

const etape = groupe('ACVI', ['ACVI75'])
test.describe.configure({ timeout: 600_000 })

const lancer = (args) => spawnSync('python', args, { cwd: RACINE, encoding: 'utf-8', timeout: 540_000 })

etape('PA1.sonde', ['ACVI75'], async ({ page }) => {
  const s = lancer(['scripts/sonde.py', 'ACVI/parcours-PA1', '--timeout', '400'])
  const sortie = `${s.stdout}\n${s.stderr}`
  const ligne = sortie.split('\n').find((l) => l.startsWith('observé : ')) || ''
  expect(ligne, `sortie de la sonde : ${sortie.slice(-600)}`).not.toBe('')
  const obs = JSON.parse(ligne.slice('observé : '.length))
  expect(obs.repro, `aucun écart sur le parcours PA1 (${JSON.stringify(obs.observe?.erreurs)})`).toBe(false)
  expect(obs.observe.erreurs).toEqual([])
  expect(obs.observe.fuites_prix_achat).toEqual([])
  expect(obs.observe.revue.statut_visite).toBe('validee')
  expect(obs.observe.apres_terminee.visite_effectuee, '`visite_effectuee` écrit à « terminer » (table PA1)').toBe(true)
  expect(obs.observe.societe_B_codes).toEqual([404, 404, 404, 404])
  expect(sortie, 'base inchangée').toMatch(/base inchangée : oui/)
  const g = lancer(['scripts/check_parcours.py'])
  expect(g.status, `check_parcours : ${g.stdout}${g.stderr}`).toBe(0)
  // Trace écran : la liste des leads (aucun objet de la sonde ne survit, transaction annulée).
  await assurerSessionPage(page)
  await page.goto('/crm/leads')
  await expect(page.locator('body')).toBeVisible()
})
