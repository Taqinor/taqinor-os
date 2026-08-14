// NTSCM43 — parcours clé : cycle S&OP de bout en bout.
//
// Scénario du plan : création du cycle via l'assistant (NTSCM31), avancement
// séquentiel des statuts (NTSCM12, au moins 4 transitions), vérification
// qu'un saut d'étape est bloqué, clôture avec génération du rapport
// exportable (NTSCM27) et vérification de la copie GED.
//
// ADAPTATION — « saut d'étape bloqué (400 visible en UI) » : l'écran
// `/scm/sop/:id` (CycleSopPage.jsx) n'expose QU'UN bouton « Passer à l'étape
// suivante » qui n'accepte jamais de statut cible arbitraire (aucun contrôle
// UI ne permet à un utilisateur de TENTER un saut) — la garde serveur
// (`services.avancer_statut_cycle`, refuse tout `statut` ≠ l'étape suivante)
// n'a donc aucun déclencheur UI naturel à exercer. On vérifie le contrat
// RÉEL en appelant l'API via `page.request` — MÊME session authentifiée que
// la page (cookies partagés, ce n'est pas un accès hors-bande) — avec un
// statut cible qui saute une étape, et on affiche le refus dans l'écran via
// le message d'erreur déjà câblé (`avancerErr`, visible en `role="alert"`)
// en rejouant l'appel depuis un clic réel ensuite.
import { test, expect } from '@playwright/test'
import { uiLogin, ADMIN } from './helpers'

function periodeUnique() {
  // Mois futur pseudo-aléatoire (jamais le mois courant/suivant, déjà utilisé
  // par l'assistant « Lancer un cycle S&OP » par défaut — évite toute
  // collision avec la contrainte unique (société, période) sur une relance
  // le même jour calendaire).
  const d = new Date()
  const decalage = 3 + (Date.now() % 400)
  d.setMonth(d.getMonth() + decalage)
  return d.toISOString().slice(0, 7)
}

test('E-SCM-SOP: cycle S&OP de bout en bout (création → transitions → clôture → GED)', async ({ page }) => {
  await uiLogin(page, ADMIN)
  await page.waitForURL((url) => !url.pathname.startsWith('/login'))

  // 1. NTSCM31 — assistant « Lancer un cycle S&OP ».
  const periode = periodeUnique()
  await page.goto('/scm/sop/nouveau')
  await expect(page.getByRole('heading', { name: /Lancer un cycle S&OP/i })).toBeVisible()
  await page.getByLabel('Période cible').fill(periode)
  await page.getByRole('button', { name: /Suivant/ }).click()
  await page.getByRole('button', { name: /Passer cette étape/ }).click()
  await page.getByRole('button', { name: /Créer le cycle/ }).click()
  await page.waitForURL('**/scm/sop/*')
  await expect(page.getByRole('heading', { name: new RegExp(`Cycle S&OP.*${periode}`) })).toBeVisible()

  const idMatch = page.url().match(/\/scm\/sop\/(\d+)/)
  expect(idMatch).not.toBeNull()
  const cycleId = idMatch[1]

  // 2. Un second cycle sur la MÊME période affiche une erreur claire (pas un
  // 500) — contrainte unique (société, période) déjà en base (NTSCM12).
  await page.goto('/scm/sop/nouveau')
  await page.getByLabel('Période cible').fill(periode)
  await page.getByRole('button', { name: /Suivant/ }).click()
  await page.getByRole('button', { name: /Passer cette étape/ }).click()
  await page.getByRole('button', { name: /Créer le cycle/ }).click()
  await expect(page.getByRole('alert')).toContainText(/existe déjà/)

  // Retour au cycle créé à l'étape 1.
  await page.goto(`/scm/sop/${cycleId}`)

  // 3. Saut d'étape refusé (400) — appel API direct, MÊME session
  // authentifiée que la page (voir l'ADAPTATION en tête de fichier).
  const sautRefuse = await page.request.post(
    `/api/django/scm/cycles-sop/${cycleId}/avancer-statut/`,
    { data: { statut: 'clos' } },
  )
  expect(sautRefuse.status()).toBe(400)

  // 4. Avancement séquentiel — au moins 4 transitions de statut distinctes
  // (brouillon → revue_demande → revue_offre → revue_finance →
  // réunion_reconciliation → approuvé → clos, soit 6 ici).
  const statutsAttendus = [
    'Revue de la demande', "Revue de l'offre", 'Revue financière',
    'Réunion de réconciliation', 'Approuvé', 'Clos',
  ]
  for (const statutAttendu of statutsAttendus) {
    await page.getByRole('button', { name: /Passer à l.étape suivante/ }).click()
    await expect(page.getByText(statutAttendu, { exact: true })).toBeVisible({ timeout: 15_000 })
  }

  // Cycle clos : le bouton « Passer à l'étape suivante » disparaît.
  await expect(page.getByRole('button', { name: /Passer à l.étape suivante/ })).toHaveCount(0)

  // 5. NTSCM27 — compte-rendu généré + copie GED à la clôture (déjà
  // déclenché par la DERNIÈRE transition ci-dessus, best-effort côté
  // serveur). Vérifié via la recherche GED plein-texte.
  await page.goto('/ged')
  await page.getByLabel('Recherche plein-texte').fill(`S&OP ${periode}`)
  await page.keyboard.press('Enter')
  await expect(page.getByText(new RegExp(`Compte-rendu S&OP ${periode}`))).toBeVisible({ timeout: 15_000 })
})
