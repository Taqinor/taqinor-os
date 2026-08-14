// NTIDE59/60/61 — module Innovation (boîte à idées interne) : proposer une
// idée, voter, et le cycle examiner→retenir (admin). Un seul fichier — même
// esprit que activities.spec.js/doublons.spec.js : plusieurs scénarios liés
// au même module, DB seedée partagée (E2E_BASE_URL, seed_demo), donc chaque
// idée créée porte un titre `uniq()` pour ne jamais collisionner entre runs.
import { test, expect } from '@playwright/test'
import { uniq, ADMIN, SECOND_USER, uiLogin } from './helpers'

// ── NTIDE59 — proposer une idée ──────────────────────────────────────────────
test('NTIDE59: propose une idée, redirige vers le détail, apparaît dans « Mes idées »', async ({ page }) => {
  const titre = uniq('Idée E2E')

  await page.goto('/innovation/proposer')
  await expect(page.getByRole('heading', { name: 'Proposer une idée' })).toBeVisible()

  await page.getByLabel('Titre').fill(titre)
  await page.getByLabel('Description').fill('Décrite par le test E2E NTIDE59.')
  await page.getByRole('button', { name: "Proposer l'idée" }).click()

  // Redirection vers le détail (NTIDE8/NTIDE5) — le titre y est le heading.
  await expect(page).toHaveURL(/\/innovation\/idees\/\d+$/)
  await expect(page.getByRole('heading', { name: titre })).toBeVisible()

  // Apparaît dans « Mes idées » (NTIDE15, filtre owner = utilisateur connecté).
  // DataTable rend TOUJOURS desktop (table) + mobile (cartes) dans le DOM,
  // basculés par CSS uniquement (data-dt-table/data-dt-cards) — scoper à la
  // table desktop pour éviter un double-match strict-mode.
  await page.goto('/innovation/mes-idees')
  await expect(page.getByRole('heading', { name: 'Mes idées' })).toBeVisible()
  await expect(page.locator('[data-dt-table]').getByText(titre)).toBeVisible()
})

// ── NTIDE60 — voter une idée ──────────────────────────────────────────────────
test('NTIDE60: le vote incrémente le compteur, un second vote du même votant est refusé', async ({ page, browser }) => {
  const titre = uniq('Idée à voter')

  // Créée par ADMIN (session pré-authentifiée, storageState).
  await page.goto('/innovation/proposer')
  await page.getByLabel('Titre').fill(titre)
  await page.getByRole('button', { name: "Proposer l'idée" }).click()
  await expect(page).toHaveURL(/\/innovation\/idees\/(\d+)$/)
  const ideeId = page.url().match(/\/idees\/(\d+)$/)[1]

  // L'auteur ne peut pas voter pour sa propre idée (règle métier serveur) :
  // le vote se fait donc depuis une SECONDE session (demo_resp), dans un
  // contexte navigateur séparé (le contexte par défaut reste authentifié
  // ADMIN via storageState, cf. playwright.config.js).
  const voterContext = await browser.newContext()
  const voterPage = await voterContext.newPage()
  try {
    await uiLogin(voterPage, { username: SECOND_USER, password: ADMIN.password })
    // ODY3 — la connexion ouvre le Menu d'accueil `/apps` (« on ouvre l'ERP,
    // on voit SES apps »), plus `/dashboard` : même preuve (la seconde session
    // est bien authentifiée avant de voter), sur la vraie destination.
    await expect(voterPage).toHaveURL(/\/apps/)

    await voterPage.goto(`/innovation/idees/${ideeId}`)
    await expect(voterPage.getByRole('heading', { name: titre })).toBeVisible()
    // « Votes » (DefinitionList dt/dd, cf. IdeeDetail.jsx) démarre à 0 — scopé
    // à la ligne dt/dd « Votes » (jamais un ``getByText('0')`` nu : trop de
    // « 0 » possibles ailleurs sur la page pour rester fiable).
    const votesRow = voterPage.locator('dl > div', { has: voterPage.locator('dt', { hasText: 'Votes' }) })
    await expect(votesRow.locator('dd')).toHaveText('0')

    await voterPage.getByRole('button', { name: 'Voter' }).click()
    await expect(voterPage.getByText('Vote enregistré.')).toBeVisible()
    // Le compteur passe à 1 SANS rechargement de page (re-fetch client,
    // « incrément en temps réel » du critère d'acceptation).
    await expect(votesRow.locator('dd')).toHaveText('1')

    // Un second vote du MÊME votant est refusé (unicité idee/votant, NTIDE2) —
    // affichage distinct pour le votant : le serveur répond 400, la toast
    // d'erreur remplace la toast de succès (aucun bouton « déjà voté » dédié
    // n'est câblé côté client aujourd'hui — le compteur reste la preuve
    // visible que le second clic n'a pas été compté deux fois).
    await voterPage.getByRole('button', { name: 'Voter' }).click()
    await expect(voterPage.getByText('Vous avez déjà voté')).toBeVisible()
    await expect(votesRow.locator('dd')).toHaveText('1')
  } finally {
    await voterContext.close()
  }
})

// ── NTIDE61 — cycle admin examiner→retenir ───────────────────────────────────
test('NTIDE61: admin examine puis retient une idée — chatter loggé, statut mis à jour', async ({ page }) => {
  const titre = uniq('Idée à examiner')

  await page.goto('/innovation/proposer')
  await page.getByLabel('Titre').fill(titre)
  await page.getByRole('button', { name: "Proposer l'idée" }).click()
  await expect(page).toHaveURL(/\/innovation\/idees\/\d+$/)

  // Statut de départ : « Ouvert ».
  await expect(page.getByText('Ouvert', { exact: true })).toBeVisible()

  // ── Examiner (ouvert → examinée) ──
  await page.getByRole('button', { name: 'Examiner' }).click()
  await expect(page.getByText('Statut mis à jour.')).toBeVisible()
  await expect(page.getByText('Examinée', { exact: true })).toBeVisible()

  // Chatter loggé (onglet Historique — Radix tabs, activation au clic réel).
  await page.getByRole('tab', { name: /Historique/ }).click()
  await expect(page.getByText('Ouvert → Examinée')).toBeVisible()

  // ── Retenir (examinée → retenue) ──
  await page.getByRole('button', { name: 'Retenir' }).click()
  await expect(page.getByText('Statut mis à jour.')).toBeVisible()
  await expect(page.getByText('Retenue', { exact: true })).toBeVisible()
  await expect(page.getByText('Examinée → Retenue')).toBeVisible()

  // Notification du proposant (NTIDE52 — ici l'admin est son propre
  // proposant : la cloche de notifications, dans l'en-tête, doit porter la
  // ligne « idée retenue »).
  await page.reload()
  await page.locator('.nb-btn').click()
  await expect(page.locator('.nb-panel')).toBeVisible()
  await expect(page.locator('.nb-panel').getByText(titre)).toBeVisible()
})
