// Rejeu en direct des tâches ADEV119 (modale « Refuser » sans motif archivé) et ADEV120 (générateur : conso C&I
// connue dès que l'aperçu serveur sert `feuille_consommation_retenue`), lot 7. Société = celle de demo_admin.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADEV', ['ADEV119'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

async function devisEnvoye(r, m) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADEV4 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adev4_${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ADEV4 ${m}`, prix_vente: '1000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  return d
}

async function ouvrirRefus(page, d) {
  await page.goto(`/ventes/devis?q=${encodeURIComponent(d.reference)}`)
  const ligne = page.getByRole('row').filter({ hasText: d.reference })
  await expect(ligne.first(), 'devis listé').toBeVisible({ timeout: 60_000 })
  await ligne.first().getByRole('button', { name: /Refuser/ }).click()
  await expect(page.getByLabel('Motif du refus'), 'modale « Refuser »').toBeVisible({ timeout: 30_000 })
}

etape('V4.119', ['ADEV119'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  await lireJson(await r.post(`${API}/crm/motifs-perte/`, { ...T, data: { nom: `Prix ${m}` } }), 'motif Prix')
  const delai = await lireJson(await r.post(`${API}/crm/motifs-perte/`, { ...T, data: { nom: `Délai ${m}` } }), 'motif Délai')
  // Archiver « Délai » depuis Paramètres › Leads (geste de l'écran).
  await page.goto('/parametres?onglet=leads')
  const rangee = page.locator('div').filter({ has: page.locator(`input[value="Délai ${m}"]`) }).filter({ has: page.getByRole('button', { name: 'Archiver le motif' }) }).last()
  await expect(rangee, 'motif listé dans Paramètres').toBeVisible({ timeout: 60_000 })
  const [arch] = await Promise.all([
    page.waitForResponse((x) => x.url().includes(`/crm/motifs-perte/${delai.id}/`) && x.request().method() === 'PATCH'),
    rangee.getByRole('button', { name: 'Archiver le motif' }).click(),
  ])
  expect(arch.status(), 'archivage').toBe(200)
  expect((await lireJson(await r.get(`${API}/crm/motifs-perte/${delai.id}/`, T), 'motif relu')).archived, 'Délai archivé').toBe(true)
  // « Refuser » un devis envoyé : « Prix » seul (parmi les deux), refus 200.
  const d = await devisEnvoye(r, m)
  await ouvrirRefus(page, d)
  await page.getByLabel('Motif du refus').click()
  await expect(page.getByRole('option', { name: `Prix ${m}` }), 'motif actif listé').toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('option', { name: `Délai ${m}` }), 'motif archivé absent').toHaveCount(0)
  await page.getByRole('option', { name: `Prix ${m}` }).click()
  const [refus] = await Promise.all([
    page.waitForResponse((x) => new RegExp(`/ventes/devis/${d.id}/refuser/?$`).test(new URL(x.url()).pathname)),
    page.getByRole('button', { name: 'Confirmer le refus' }).click(),
  ])
  expect(refus.status(), `refus avec « Prix » : ${(await refus.text()).slice(0, 200)}`).toBe(200)
  expect((await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')).statut, 'devis refusé').toBe('refuse')
  // Aucun motif actif ⇒ « Aucun motif configuré » (motifs actifs archivés le temps du geste, puis restaurés).
  const actifs = await py(`from apps.crm.models import MotifPerte
ids = list(MotifPerte.objects.filter(company_id=${SOC}, archived=False).values_list('id', flat=True))
MotifPerte.objects.filter(id__in=ids).update(archived=True)
sortie(ids)`)
  try {
    const d2 = await devisEnvoye(r, `${m}b`)
    await ouvrirRefus(page, d2)
    await expect(page.getByText(/Aucun motif configuré/), 'aucun motif actif').toBeVisible({ timeout: 30_000 })
  } finally {
    await py(`from apps.crm.models import MotifPerte
MotifPerte.objects.filter(id__in=${JSON.stringify(actifs)}).update(archived=False)
sortie(1)`)
  }
  suivi.verifie(5)
})
