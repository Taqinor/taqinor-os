// ADSENGINT3 — E2E Playwright de la console « Publicité » (adsengine).
// ----------------------------------------------------------------------------
// La SEULE validation du contrat front↔back : les tests unitaires (RTL + Django)
// mockent LES DEUX côtés, donc le contrat n'a jamais été vérifié bout-en-bout.
// Ici, le front construit (vite preview) parle au VRAI backend Django (même
// origine, cf. playwright.config.js webServer), pré-authentifié en admin démo.
//
// On couvre les trois surfaces du Done de ADSENGINT3 :
//   1. Connexion Meta — identifiants WRITE-ONLY (écrits, jamais relus) + le
//      statut de connexion lu du vrai back.
//   2. Dashboard — le HÉRO « coût par signature » rendu depuis l'API metrics
//      réelle (jamais un chiffre mocké), + le drill-down des leads réels.
//   3. Boîte d'approbation — approve ET reject bout-en-bout, la transition
//      persistée côté back (proposée → approuvée / rejetée).
//
// Le seed des EngineAction passe par l'API RÉELLE (cookie admin, patron
// receivables.spec.js / comptes-justes.spec.js) — pas de mock. La base
// seed_demo est partagée en workers:1, donc on nettoie tout en afterAll.
import { test, expect } from '@playwright/test'

const API = '/api/django/adsengine'
const createdActionIds = []

test.describe('ADSENGINT3: console Publicité (contrat front↔back réel)', () => {
  test.afterAll(async ({ request }) => {
    // Nettoyage best-effort : une suppression en échec ne bloque pas les autres.
    await Promise.all(createdActionIds.map((id) => (
      request.delete(`${API}/actions/${id}/`).catch(() => null)
    )))
  })

  test('Connexion Meta : identifiants write-only, statut lu du vrai back', async ({ page }) => {
    const token = `e2e-secret-token-${Date.now()}`
    const account = `act_e2e_${Date.now().toString().slice(-6)}`

    await page.goto('/publicite/connexion')
    await expect(
      page.getByRole('heading', { name: 'Connexion & garde-fous' }),
    ).toBeVisible({ timeout: 20_000 })

    // Écrit un jeton + un compte pub (WRITE-ONLY) via le vrai formulaire.
    await page.getByTestId('ae-conn-cred-access_token').fill(token)
    await page.getByTestId('ae-conn-cred-ad_account_id').fill(account)
    await page.getByTestId('ae-conn-cred-save').click()

    // Le back a persisté puis le front relit le STATUT (jamais le secret).
    await expect(page.getByTestId('ae-conn-msg')).toBeVisible()
    await expect(page.getByTestId('ae-conn-status')).toContainText('Connecté')

    // Write-only prouvé : le champ secret repart vide et le jeton n'est jamais
    // réaffiché nulle part dans la page (l'API `connection.get` ne rend qu'un
    // statut, jamais un secret).
    await expect(page.getByTestId('ae-conn-cred-access_token')).toHaveValue('')
    await expect(page.locator('body')).not.toContainText(token)
  })

  test('Dashboard : le coût par signature vient du vrai back (jamais un mock)', async ({ page }) => {
    await page.goto('/publicite/tableau-de-bord')
    await expect(
      page.getByRole('heading', { name: 'Tableau de bord publicitaire' }),
    ).toBeVisible({ timeout: 20_000 })

    // Le HÉRO = coût par signature ; sa valeur est celle de l'API metrics réelle.
    const hero = page.getByTestId('ae-hero')
    await expect(hero).toContainText('Coût par signature')
    await expect(page.getByTestId('ae-value-cost_per_signature')).toBeVisible()

    // Traçabilité (Northbeam) : cliquer le chiffre lit les leads RÉELS derrière
    // (2ᵉ appel au vrai back — `metrics.leads('signature')`).
    await hero.click()
    await expect(page.getByTestId('ae-drill-panel')).toBeVisible()
  })

  test("Boîte d'approbation : approve / reject bout-en-bout sur le vrai back", async ({ page }) => {
    // Seed via l'API RÉELLE (cookie admin) — deux actions PROPOSÉES sûres
    // (`pause` : aucun appel Meta à l'approbation, la boucle n'applique rien ici).
    const mk = async (reason) => {
      const res = await page.request.post(`${API}/actions/`, {
        data: { kind: 'pause', reason_fr: reason, payload: {} },
      })
      expect(res.ok(), `création action (${res.status()})`).toBeTruthy()
      const body = await res.json()
      createdActionIds.push(body.id)
      return body.id
    }
    const approveId = await mk(`E2E à approuver ${Date.now()}`)
    const rejectId = await mk(`E2E à rejeter ${Date.now()}`)

    await page.goto('/publicite/approbations')
    await expect(
      page.getByRole('heading', { name: "Boîte d'approbation" }),
    ).toBeVisible({ timeout: 20_000 })

    // Les deux actions RÉELLES sont affichées : le front a bien lu le vrai back.
    await expect(page.getByTestId(`ae-approve-${approveId}`)).toBeVisible()
    await expect(page.getByTestId(`ae-approve-${rejectId}`)).toBeVisible()

    // Approuver bout-en-bout → l'action quitte la boîte.
    await page.getByTestId(`ae-approve-${approveId}`).click()
    await expect(page.getByTestId(`ae-approve-${approveId}`)).toHaveCount(0)

    // Rejeter via le motif STRUCTURÉ (select, jamais du chat) → quitte la boîte.
    await page.getByTestId(`ae-reject-${rejectId}`).click()
    await expect(page.getByTestId(`ae-reject-confirm-${rejectId}`)).toBeVisible()
    await page.getByTestId(`ae-reject-confirm-${rejectId}`).click()
    await expect(page.getByTestId(`ae-reject-${rejectId}`)).toHaveCount(0)

    // Le vrai back a PERSISTÉ les transitions (la preuve du bout-en-bout).
    const approved = await page.request.get(`${API}/actions/${approveId}/`)
    expect(approved.ok()).toBeTruthy()
    expect((await approved.json()).status).toBe('approuvee')
    const rejected = await page.request.get(`${API}/actions/${rejectId}/`)
    expect(rejected.ok()).toBeTruthy()
    expect((await rejected.json()).status).toBe('rejetee')
  })
})
