// Acceptation en direct — groupe AACQ, second lot : AACQ107 (devise estampillée par un montant soumis) et AACQ108
// (champ « Seuil » de l'écran Règles). Format : `_format.md`. Pile locale, base jetable erp_live2 : une connexion Meta
// de TEST en USD (jamais de jeton réel, aucun appel sortant) est posée pour l'étape puis RETIRÉE en `finally`.
import { expect, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import { API_DJANGO, assurerSessionPage, executerDansDjango, lireJson } from '../helpers.js'

test.describe.configure({ timeout: 300_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
const etape = groupe('AACQ', ['AACQ107', 'AACQ108'])
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

function py(code) {
  const m = String(executerDansDjango(code)).match(/@@JSON@@(.*)/)
  if (!m) throw new Error('sortie Django sans JSON')
  return JSON.parse(m[1])
}
const poserUsd = () => py(`
import json
from apps.adsengine.models import GuardrailConfig, MetaConnection, RulePolicy
from django.contrib.auth import get_user_model
co = get_user_model().objects.get(username='demo_admin').company
MetaConnection.objects.filter(company=co).delete()
GuardrailConfig.objects.filter(company=co).delete()
RulePolicy.objects.filter(company=co).delete()
MetaConnection.objects.create(company=co, enabled=True, ad_account_id='act_000000', currency='USD',
                              credentials={'access_token': 'ACCEPTATION-AACQ107-FAUX'})
print('@@JSON@@' + json.dumps({'ok': True}))
`)
const retirer = () => py(`
import json
from apps.adsengine.models import GuardrailConfig, MetaConnection, RulePolicy
from django.contrib.auth import get_user_model
co = get_user_model().objects.get(username='demo_admin').company
MetaConnection.objects.filter(company=co, ad_account_id='act_000000').delete()
GuardrailConfig.objects.filter(company=co).delete()
RulePolicy.objects.filter(company=co).delete()
print('@@JSON@@' + json.dumps({'ok': True}))
`)

etape('P3.2-garde-fous', ['AACQ107'], async ({ page }) => {
  poserUsd()
  try {
    await page.goto('/publicite/connexion')
    const alerte = page.getByTestId('ae-conn-guard-devise-alert')
    await expect(alerte).toBeVisible({ timeout: 30_000 })
    await expect(alerte).toContainText('Plafond saisi en MAD, compte facturé en USD')
    await page.getByTestId('ae-conn-guard-save').click()
    await expect(alerte).toBeHidden({ timeout: 30_000 })
    const g = await lireJson(await page.request.get(`${API_DJANGO}/adsengine/guardrail/`), 'garde-fous')
    expect(g.ceiling_currency, 'devise estampillée').toBe('USD')
    expect(Number(g.max_daily_budget_mad)).toBe(100)
    await page.reload()
    await expect(page.getByText(/Plafond quotidien actuel/)).toContainText(/100/, { timeout: 30_000 })
    await expect(page.getByText(/USD/).first()).toBeVisible()
    await expect(page.getByTestId('ae-conn-guard-devise-alert')).toHaveCount(0)
  } finally { retirer() }
})

etape('P3.2-seuil', ['AACQ108'], async ({ page }) => {
  poserUsd()
  try {
    await page.goto('/publicite/regles')
    await page.getByTestId('ae-rule-arm-stop_loss_cpl').click()
    const confirmer = page.getByTestId('ae-rule-arm-confirm-btn-stop_loss_cpl')
    await expect(confirmer).toBeVisible({ timeout: 30_000 })
    await confirmer.click()
    const badge = page.getByTestId('ae-rule-threshold-currency-stop_loss_cpl')
    await expect(badge).toBeVisible({ timeout: 30_000 })
    await expect(badge).toContainText('Seuil en MAD')
    const champ = page.getByTestId('ae-rule-threshold-input-stop_loss_cpl')
    await expect(champ).toBeVisible()
    await champ.fill('40')
    await page.getByTestId('ae-rule-threshold-save-stop_loss_cpl').click()
    await expect(badge).toContainText('Seuil en USD', { timeout: 30_000 })
    const regles = await lireJson(await page.request.get(`${API_DJANGO}/adsengine/regles/`), 'règles')
    const liste = Array.isArray(regles) ? regles : regles.results ?? []
    const stop = liste.find((r) => r.template_key === 'stop_loss_cpl')
    expect(Number(stop?.params?.threshold_mad), 'seuil enregistré').toBe(40)
    expect(stop?.threshold_currency).toBe('USD')
    await page.reload()
    await expect(page.getByTestId('ae-rule-threshold-input-stop_loss_cpl')).toHaveValue('40', { timeout: 30_000 })
    await expect(page.getByTestId('ae-rule-threshold-currency-stop_loss_cpl')).toContainText('Seuil en USD')
  } finally { retirer() }
})
