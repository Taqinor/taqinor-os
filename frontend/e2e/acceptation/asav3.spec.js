// ASAV125, ASAV126 — rejeu en direct : lier un ticket à un problème par sa référence ; pièce jointe et checklist du doublon
// visibles sur le principal sans recharger la page après la fusion.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage, PNG_1PX } from '../helpers.js'

const etape = groupe('ASAV', ['ASAV125', 'ASAV126'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const clientEssai = async (r, m) => lireJson(await r.post(`${API}/crm/clients/`, { ...T, data: { nom: `ASAV ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'client')
const ticketEssai = async (r, client, texte) => lireJson(await r.post(`${API}/sav/tickets/`, { ...T, data: { client: client.id, type: 'correctif', description: texte } }), 'ticket')

etape('P125.1', ['ASAV125'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const client = await clientEssai(r, m)
  const t1 = await ticketEssai(r, client, `ASAV125 ${m} un`)
  const t2 = await ticketEssai(r, client, `ASAV125 ${m} deux`)
  const prob = await lireJson(await r.post(`${API}/sav/problemes/`, { ...T, data: { titre: `ASAV125 ${m}` } }), 'problème')
  await page.goto('/sav/problemes')
  const gerer = () => page.locator('tr', { hasText: `ASAV125 ${m}` }).getByRole('button', { name: 'Gérer' }).click({ timeout: 60_000 })
  await gerer()
  const combo = page.getByRole('combobox', { name: 'Ticket à lier' })
  await combo.click()
  // La fin de la référence, comme un responsable qui lit « 0042 ».
  const fin = t1.reference.split('-').pop()
  await page.getByPlaceholder('Rechercher un ticket…').fill(t1.reference)
  await page.getByRole('option', { name: new RegExp(t1.reference) }).click({ timeout: 30_000 })
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.url().includes(`/sav/problemes/${prob.id}/`) && x.request().method() === 'POST', T),
    page.getByRole('button', { name: 'Lier un ticket' }).click(),
  ])
  expect(rep.status(), (await rep.text()).slice(0, 200)).toBeLessThan(300)
  expect(JSON.stringify(rep.request().postDataJSON()), 'l\'id du ticket choisi part').toContain(String(t1.id))
  await expect(page.getByRole('button', { name: `Délier ${t1.reference}` }), 'les liés montrent la référence').toBeVisible()
  await expect(page.getByRole('button', { name: `Délier ${t2.reference}` })).toHaveCount(0)
  await page.reload()
  await gerer()
  await expect(page.getByRole('button', { name: `Délier ${t1.reference}` }), `persistance (…${fin})`).toBeVisible({ timeout: 30_000 })
  suivi.verifie(5)
})

etape('P126.1', ['ASAV126'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const client = await clientEssai(r, m)
  const principal = await ticketEssai(r, client, `ASAV126 ${m} principal`)
  const doublon = await ticketEssai(r, client, `ASAV126 ${m} doublon`)
  const nomPhoto = `photo-onduleur-${m}.png`
  await lireJson(await r.post(`${API}/records/attachments/`, { ...T, multipart: { model: 'sav.ticket', id: String(doublon.id), file: { name: nomPhoto, mimeType: 'image/png', buffer: PNG_1PX } } }), 'pièce du doublon')
  // Modèle de checklist et item du doublon : posés au shell (paramétrage hors de l'étape).
  const libelle = `Serrage MC4 ${m}`
  await py(`from apps.sav.models import TicketChecklistItem
TicketChecklistItem.objects.create(company_id=1, ticket_id=${doublon.id}, cle='mc4_${m}', libelle='${libelle}')
sortie(1)`)
  await page.goto(`/sav?id=${principal.id}`)
  await expect(page.getByText('Fusionner un ticket doublon'), 'la fiche du principal').toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(nomPhoto), 'avant : aucune pièce du doublon').toHaveCount(0)
  await expect(page.getByText(libelle), 'avant : aucun item du doublon').toHaveCount(0)
  await page.getByPlaceholder('ID du ticket doublon').fill(String(doublon.id))
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.url().includes(`/sav/tickets/${principal.id}/fusionner/`), T),
    page.getByRole('button', { name: 'Fusionner', exact: true }).click(),
  ])
  expect(rep.status(), (await rep.text()).slice(0, 200)).toBe(200)
  await expect(page.getByText(nomPhoto).first(), 'la photo apparaît sans recharger').toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(libelle).first(), 'l\'item apparaît sans recharger').toBeVisible({ timeout: 30_000 })
  await page.reload()
  await expect(page.getByText(nomPhoto).first(), 'persistance : photo').toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(libelle).first(), 'persistance : item').toBeVisible({ timeout: 30_000 })
  suivi.verifie(5)
})
