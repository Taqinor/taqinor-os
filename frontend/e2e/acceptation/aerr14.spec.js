// Preuve en direct ÉCRAN d'AERR169 (groupe AERR, contre-visite du 14/11) après le correctif de la double lecture :
// `ParametresEntreprise.jsx` démontait puis remontait les sections à chaque relecture du profil (`if (loading)`),
// d'où DEUX lectures des règles de routage et deux toasts (rejeu aerr8 du 15/11, « fini quand » non atteint).
// Ici le « fini quand » est affirmé tel quel : une lecture rejetée 500 ⇒ UNE lecture, UN toast (global) ; 404 ⇒ UNE
// lecture, UN toast (local). Compte demo_admin (Directeur, palier admin) ; panne injectée par route Playwright
// déclarée AVANT au suivi ; rechargé sans panne ⇒ aucun message d'échec. Lecture seule : aucune donnée créée.
import { expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage } from '../helpers.js'

const etape = groupe('AERR', ['AERR169'])
fermerDjangoApresTout()
const J = JSON.stringify
const REGLES = /\/api\/django\/notifications\/routing-rules\/(\?|$)/

/** Panne injectée sur les GET d'URL `re` (déclarée au suivi avant) ; compte les lectures. */
async function panne(p, suivi, re, statut, corps) {
  suivi.attendre(re, statut)
  const hits = { n: 0 }
  const h = async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    hits.n += 1
    return route.fulfill({ status: statut, contentType: 'application/json', body: J(corps) })
  }
  await p.route(re, h)
  return { hits, lever: () => p.unroute(re, h) }
}

etape('PF12.1-AERR169-une-lecture', ['AERR169'], async ({ page, suivi }) => {
  await assurerSessionPage(page)
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* privé */ }
  })
  const toasts = page.locator('[data-sonner-toast]')
  const ouvrir = async () => {
    await page.goto('/parametres?onglet=notifications')
    await expect(page.getByRole('heading').first()).toBeVisible({ timeout: 60_000 })
    await page.waitForTimeout(3_000)
    await page.waitForLoadState('networkidle').catch(() => undefined)
  }

  // 1) 500 : une lecture, un toast — celui du serveur (global), pas de toast local en plus.
  const c500 = await panne(page, suivi, REGLES, 500, { detail: 'Panne simulée AERR169 (règles).' })
  await ouvrir()
  const t500 = await toasts.allInnerTexts()
  console.log(`[AERR169] 500 : lectures ${c500.hits.n}, toasts ${J(t500)}`)
  expect(c500.hits.n, '500 : les règles ne sont lues qu’UNE fois à l’ouverture').toBe(1)
  expect(t500.length, `500 : un seul toast (${J(t500)})`).toBe(1)
  expect(t500[0], '500 : le message du serveur').toContain('Panne simulée AERR169')
  await c500.lever()

  // 2) 404 : une lecture, un toast (local, le global se tait).
  const c404 = await panne(page, suivi, REGLES, 404, { detail: 'Pas trouvé.' })
  await ouvrir()
  const t404 = await toasts.allInnerTexts()
  console.log(`[AERR169] 404 : lectures ${c404.hits.n}, toasts ${J(t404)}`)
  expect(c404.hits.n, '404 : une seule lecture').toBe(1)
  expect(t404.length, `404 : un seul toast (${J(t404)})`).toBe(1)
  await c404.lever()

  // 3) Persistance (lecture) : panne levée, rechargé ⇒ aucun message d'échec.
  await ouvrir()
  await expect(toasts.filter({ hasText: /impossible|Panne|Pas trouvé/ }), 'rechargé sans panne : aucun échec').toHaveCount(0)
})
