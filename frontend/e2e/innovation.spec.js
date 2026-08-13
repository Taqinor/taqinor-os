// NTIDE59/60/61/62/63 — module Innovation (boîte à idées interne) : proposer
// une idée, voter, le cycle examiner→retenir (admin), le lancement d'une
// campagne ciblée et le canal feedback produit. Un seul fichier — même
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
    await expect(voterPage).toHaveURL(/\/dashboard/)

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

// ── NTIDE62 — créer puis LANCER une campagne ciblée ──────────────────────────
test('NTIDE62: admin crée une campagne, la lance, le segment est notifié et l\'incitation s\'affiche', async ({ page }) => {
  const nom = uniq('Campagne E2E')
  const incitation = `Parlez-nous de vos idées — ${nom}.`

  await page.goto('/innovation/campagnes')
  await expect(page.getByRole('heading', { name: 'Campagnes innovation' })).toBeVisible()

  // ── Création (nom / segment / message d'incitation) ──
  await page.getByRole('button', { name: 'Nouvelle campagne' }).click()
  const dialogue = page.getByRole('dialog')
  await expect(dialogue).toBeVisible()
  await dialogue.getByLabel('Nom').fill(nom)
  await dialogue.getByLabel("Message d'incitation").fill(incitation)

  // Segment : MultiSelect (trigger role=combobox, options role=option). On
  // cible les DEUX rôles que `init_roles` peut attribuer au compte demo_admin
  // (« Administrateur », ou « Directeur » s'il est propriétaire/superuser) —
  // sinon le test dépendrait d'un détail de seed et deviendrait instable.
  await dialogue.getByRole('combobox').click()
  await page.getByRole('option', { name: 'Administrateur', exact: true }).click()
  await page.getByRole('option', { name: 'Directeur', exact: true }).click()
  await page.keyboard.press('Escape')

  await dialogue.getByRole('button', { name: 'Créer (brouillon)' }).click()
  await expect(page.getByText('Campagne créée.')).toBeVisible()

  // La campagne apparaît en « Brouillon » (statut initial serveur, NTIDE25).
  const ligne = page.locator('[data-dt-table] tbody tr', { hasText: nom })
  await expect(ligne).toBeVisible()
  await expect(ligne.getByText('Brouillon')).toBeVisible()

  // ── Lancement (brouillon → active) ──
  await ligne.getByRole('button', { name: 'Lancer' }).click()
  await expect(page.getByText('Campagne lancée.')).toBeVisible()
  await expect(ligne.getByText('Active')).toBeVisible()

  // Les utilisateurs du segment reçoivent la notification de lancement
  // (NTIDE31 — l'admin appartient lui-même au segment ciblé ici).
  await page.reload()
  await page.locator('.nb-btn').click()
  await expect(page.locator('.nb-panel')).toBeVisible()
  await expect(page.locator('.nb-panel').getByText(nom)).toBeVisible()

  // Le formulaire « Proposer une idée » affiche le message d'incitation
  // (NTIDE27 — la campagne la PLUS RÉCENTE qui cible l'utilisateur gagne,
  // donc bien celle que ce test vient de lancer).
  await page.goto('/innovation/proposer')
  await expect(page.getByText(incitation)).toBeVisible()
})

// ── NTIDE63 — envoyer un retour produit, le retrouver côté admin ─────────────
test('NTIDE63: un retour envoyé depuis le menu profil arrive sur le tableau de bord admin', async ({ page }) => {
  const titre = uniq('Retour E2E')

  await page.goto('/dashboard')
  // ORDRE FONDATEUR 2026-08-04 — plus de bouton flottant : la modale de
  // feedback (NTIDE37) s'ouvre depuis le menu profil de l'en-tête.
  await page.getByRole('button', { name: 'Menu utilisateur' }).click()
  await page.getByRole('menuitem', { name: 'Envoyer un retour' }).click()

  const modale = page.getByRole('dialog')
  await expect(modale.getByText('Envoyer un retour')).toBeVisible()
  await modale.getByLabel('Titre').fill(titre)
  await modale.getByLabel('Description').fill('Décrit par le test E2E NTIDE63.')
  await modale.getByLabel('Thème').selectOption('ux')
  // NTIDE42 — ressenti optionnel, renseigné ici pour vérifier qu'il traverse.
  await modale.getByLabel('Ressenti (optionnel)').selectOption('negatif')
  await modale.getByRole('button', { name: 'Envoyer' }).click()
  await expect(page.getByText('Merci pour votre retour !')).toBeVisible()

  // Reçu sur le tableau de bord admin (NTIDE38 — liste réservée au palier
  // Directeur/Admin ; demo_admin en fait partie).
  await page.goto('/innovation/retours-produit')
  await expect(page.getByRole('heading', { name: 'Retours produit' })).toBeVisible()
  const ligne = page.locator('[data-dt-table] tbody tr', { hasText: titre })
  await expect(ligne).toBeVisible()
  await expect(ligne.getByText('UX')).toBeVisible()
  // Trace serveur de la consultation : le retour part « Envoyé » (jamais
  // encore ouvert par l'admin) — c'est la lecture du détail qui le bascule.
  await expect(ligne.getByText('Envoyé')).toBeVisible()
})
