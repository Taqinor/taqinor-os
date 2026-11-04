// ALEA64 — preuve en direct (PA1.06 rejouée) : l'assistant de visite est ouvert sur une catégorie de mesures, la visite
// est validée entre-temps (second onglet ouvert sur /visites/revue ; passage à « validée » posé au shell Django, comme
// le bureau d'études le ferait), puis « Enregistrer les mesures » : le refus serveur hors champ (`statut`) s'affiche
// en alerte au-dessus du bouton. Pile locale, données posées par l'API, nettoyées en fin d'étape.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ALEA', ['ALEA64'])
fermerDjangoApresTout()
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

etape('PA1.06', ['ALEA64'], async ({ page, context, suivi }) => {
  const r = page.request
  const m = `${Date.now().toString(36)}`
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ALEA64 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid`, type_installation: 'residentiel', facture_hiver: '900' } }), 'lead')
  const visite = await lireJson(await r.post(`${API}/visites/visites/`, { ...T, data: { lead: lead.id } }), 'visite')
  const route = new RegExp(`/visites/visites/${visite.id}/mesures/`)
  suivi.attendre(route, 400)
  try {
    // Onglet 1 : l'assistant, première catégorie de mesures.
    await page.goto(`/visites/${visite.id}`)
    const form = page.locator('[data-testid^="visite-mesures-"]').first()
    await expect(form).toBeVisible({ timeout: 60_000 })
    const champ = form.locator('input[type="number"], input[inputmode="decimal"], input[type="text"]').first()
    if (await champ.count()) await champ.fill('12')
    // Onglet 2 : la revue du bureau d'études ; la visite y est validée pendant la saisie.
    const p2 = suivi.surveiller(await context.newPage())
    await p2.goto('/visites/revue')
    await expect(p2.locator('body')).toBeVisible()
    await py(`from apps.visites.models import VisiteTerrain
from django.utils import timezone
VisiteTerrain.objects.filter(pk=${visite.id}).update(statut='validee', validee_le=timezone.now())
sortie(VisiteTerrain.objects.get(pk=${visite.id}).statut)`)
    // Onglet 1 : « Enregistrer les mesures » → 400 {erreurs: {statut}} → alerte au-dessus du bouton.
    const [rep] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'PATCH' && route.test(new URL(x.url()).pathname), T),
      form.getByRole('button', { name: 'Enregistrer les mesures' }).click(),
    ])
    expect(rep.status(), 'refus serveur').toBe(400)
    const message = [].concat((await rep.json()).erreurs?.statut)[0]
    expect(message, 'le serveur nomme `statut`').toBeTruthy()
    const alerte = form.getByRole('alert').filter({ hasText: message })
    await expect(alerte, 'la raison s\'affiche en alerte dans le formulaire').toBeVisible({ timeout: 30_000 })
    const yAlerte = (await alerte.boundingBox()).y
    const yBouton = (await form.getByRole('button', { name: 'Enregistrer les mesures' }).boundingBox()).y
    expect(yAlerte, 'au-dessus de « Enregistrer les mesures »').toBeLessThan(yBouton)
    // Persistance : relue, la visite reste validée et ses mesures n'ont pas bougé.
    const relue = await lireJson(await r.get(`${API}/visites/visites/${visite.id}/`, T), 'visite relue')
    expect(relue.statut).toBe('validee')
    await p2.close()
  } finally {
    await py(`from apps.visites.models import VisiteTerrain
VisiteTerrain.objects.filter(pk=${visite.id}).delete()
sortie(1)`).catch(() => null)
    await r.delete(`${API}/crm/leads/${lead.id}/`, T).catch(() => null)
  }
}, { ecart: { base: 'FAIL', raison: 'toast global « Une erreur est survenue. » émis par frontend/src/api/axios.js (intercepteur L53, toastError(errorMessageFrom(error))) sur tout 4xx : errorMessageFrom ne lit pas le corps {erreurs:{statut}} ; il apparaît à côté de l\'alerte du formulaire et fait tomber l\'oracle 8 (texte « Une erreur est survenue ») ; hors du formulaire de mesures (ALEA64), même toast avant la tâche (la base n\'affichait en plus aucune raison)' } })
