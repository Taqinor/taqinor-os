// VX60 — Gate e2e « comptes justes » : verrouille VX54 (pagination DRF
// complète) pour toujours. On seed >100 produits ET >100 devis via
// `page.request` (cookie admin, patron receivables.spec.js:14), on ouvre
// /stock et le Dashboard, puis on asserte que le compte AFFICHÉ = le total
// RÉEL — jamais bloqué à 100 (PAGE_SIZE DRF) comme avant VX54.
//
// La suite roule sur UNE base seed_demo partagée en `workers:1` — on NE
// PEUT PAS laisser les >200 lignes créées ici polluer les specs suivants ni
// fausser les baselines `@visual` de release-verify. Donc : nettoyage
// complet en `afterAll` (DELETE de tout ce qu'on a créé), y compris si des
// assertions échouent en cours de route.
import { test, expect } from '@playwright/test'

const N = 120 // > PAGE_SIZE (100) côté DRF — la marge couvre les seeds existants

// Même formatage que `frontend/src/lib/format.js#formatNumber` (fr-FR, espace
// fine comme séparateur de milliers) — on ne matche jamais un nombre brut,
// au cas où le total dépasse 1000 et se fait grouper.
function fmt(n) {
  return new Intl.NumberFormat('fr-FR').format(n)
}

const produitIds = []
const devisIds = []

test.describe('VX60: comptes justes (>100 enregistrements, page complète)', () => {
  test.afterAll(async ({ request }) => {
    // Nettoyage best-effort : chaque suppression est indépendante, une
    // erreur isolée ne doit pas empêcher de nettoyer le reste.
    await Promise.all(devisIds.map((id) => (
      request.delete(`/api/django/ventes/devis/${id}/`).catch(() => null)
    )))
    await Promise.all(produitIds.map((id) => (
      request.delete(`/api/django/stock/produits/${id}/`).catch(() => null)
    )))
  })

  test('stock: le compteur du catalogue = le total réel (pas 100)', async ({ page }) => {
    // Total AVANT seed, pour calculer le total ATTENDU après (la base démo a
    // déjà des produits — on ne suppose pas qu'elle est vide).
    const before = await page.request.get('/api/django/stock/produits/')
    expect(before.ok()).toBeTruthy()
    const beforeCount = (await before.json()).count

    for (let i = 0; i < N; i += 1) {
      const res = await page.request.post('/api/django/stock/produits/', {
        data: { nom: `VX60 Produit ${i} ${Date.now()}`, prix_vente: '10.00' },
      })
      expect(res.ok()).toBeTruthy()
      const { id } = await res.json()
      produitIds.push(id)
    }

    const expectedTotal = beforeCount + N

    await page.goto('/stock')
    // Le badge "Tout le catalogue" affiche `actifs.length` — TOUTES les pages
    // lues côté client (fetchAllPages), jamais tronqué à la page 1 DRF.
    const allCatalogueRow = page.locator('button', { hasText: 'Tout le catalogue' })
    await expect(allCatalogueRow).toBeVisible({ timeout: 20_000 })
    await expect(allCatalogueRow).toContainText(fmt(expectedTotal), { timeout: 20_000 })

    // Le KPI Dashboard "Produits en stock" doit refléter le même total réel.
    await page.goto('/dashboard')
    const kpiCard = page.locator('div[role="button"]', { hasText: 'Produits en stock' })
    await expect(kpiCard).toBeVisible({ timeout: 20_000 })
    await expect(kpiCard).toContainText(fmt(expectedTotal), { timeout: 20_000 })
  })

  test('ventes: le KPI devis Dashboard = le total réel (pas 100)', async ({ page }) => {
    const clientsRes = await page.request.get('/api/django/crm/clients/')
    expect(clientsRes.ok()).toBeTruthy()
    const clientsData = await clientsRes.json()
    const clients = clientsData.results ?? clientsData
    expect(clients.length).toBeGreaterThan(0)
    const clientId = clients[0].id

    const before = await page.request.get('/api/django/ventes/devis/')
    expect(before.ok()).toBeTruthy()
    const beforeCount = (await before.json()).count

    for (let i = 0; i < N; i += 1) {
      const res = await page.request.post('/api/django/ventes/devis/', {
        data: { client: clientId, taux_tva: '20.00' },
      })
      expect(res.ok()).toBeTruthy()
      const { id } = await res.json()
      devisIds.push(id)
    }

    const expectedTotal = beforeCount + N

    await page.goto('/dashboard')
    // "Devis par statut" affiche `${formatNumber(devis.length)} devis au
    // total` — toutes les pages lues (fetchAllPages), jamais tronqué à 100.
    await expect(page.getByText(`${fmt(expectedTotal)} devis au total`)).toBeVisible({ timeout: 20_000 })
  })
})
