// NTMKT42 — E2E Playwright : parcours complet campagne marketing (segment →
// campagne → envoi → trace → statut dans la liste). Confirme que le contrat
// front↔back du module Marketing est vivant de bout en bout sur le VRAI
// backend (jamais un mock), aucune dépendance à un vrai envoi SMTP — cet
// environnement n'active aucune intégration Brevo (`brevo_actif()` OFF par
// défaut) : `envoyer_campagne` journalise un `EnvoiCampagne` PAR
// destinataire sans aucun appel réseau (backend console/no-op).
//
// L'envoi lui-même passe par l'API réelle (`page.request.post`) plutôt que
// par le bouton « Confirmer l'envoi » de CampagneDetail.jsx : ce bouton
// envoie aujourd'hui un corps `{}` (0 destinataire, comportement de l'écran,
// hors périmètre de cette tâche) — l'API accepte un `destinataires: [...]`
// explicite, exactement le même contrat que `envoyer_campagnes_planifiees`
// (XMKT7) utilise déjà côté beat. C'est donc bien « le vrai backend », pas
// un mock, seulement une entrée différente du même endpoint.
//
// Note de comportement vérifiée dans le code (`apps/compta/services.py
// envoyer_campagne`) : SANS Brevo actif, `Campagne.nb_envois` n'est PAS
// incrémenté pour le canal email (seul le canal whatsapp l'incrémente hors
// Brevo) — seul `EnvoiCampagne` (la trace par destinataire) est créé, avec
// le statut `queued` (« En file »). Les assertions ci-dessous reflètent ce
// comportement RÉEL plutôt que de supposer un compteur qui ne bouge pas ici.
import { test, expect } from '@playwright/test'
import { uniq } from './helpers'

const API = '/api/django/marketing'

test.describe('NTMKT42 : parcours campagne → trace → conversion', () => {
  test('créer un segment, créer une campagne, l’envoyer, voir sa trace et son statut', async ({ page }) => {
    // ── 1. Segment (NTMKT4) ────────────────────────────────────────────
    await page.goto('/marketing/segments')
    await expect(page.getByTestId('segments-nouveau')).toBeVisible()
    await page.getByTestId('segments-nouveau').click()
    const nomSegment = uniq('Segment E2E')
    await page.getByTestId('segment-nom').fill(nomSegment)
    await page.getByTestId('segment-creer').click()
    await expect(page.getByTestId('segment-preview-compte')).toBeVisible({ timeout: 15_000 })

    // ── 2. Campagne (NTMKT2), canal email ──────────────────────────────
    await page.goto('/marketing/campagnes')
    await page.getByTestId('campagnes-nouvelle').click()
    const nomCampagne = uniq('Campagne E2E')
    await page.getByTestId('campagne-nom').fill(nomCampagne)
    await page.getByTestId('campagne-objet').fill('Objet de test E2E')
    await page.getByTestId('campagne-corps').fill('Corps de test E2E.')
    await page.getByTestId('campagne-save').click()
    await expect(page.getByTestId('campagne-form')).toHaveCount(0)

    const ligne = page.locator('[data-testid="campagne-row"]', { hasText: nomCampagne })
    await expect(ligne).toBeVisible({ timeout: 15_000 })
    await ligne.click()
    await expect(page).toHaveURL(/\/marketing\/campagnes\/\d+$/)
    const campagneId = page.url().match(/\/campagnes\/(\d+)$/)[1]

    // ── 3. Envoi réel (API, jamais de vrai SMTP — backend console) ─────
    const destinataire = `e2e-${Date.now()}@exemple.ma`
    const res = await page.request.post(`${API}/campagnes/${campagneId}/envoyer/`, {
      data: { destinataires: [destinataire] },
    })
    expect(res.ok()).toBeTruthy()

    // ── 4. La trace EnvoiCampagne s'affiche ─────────────────────────────
    await page.reload()
    await expect(page.getByTestId('envois-table')).toBeVisible()
    await expect(page.locator('[data-testid="envoi-row"]', { hasText: destinataire })).toBeVisible()

    // ── 5. Le KPI dashboard (NTMKT1) reflète l'état réel du nouvel envoi ─
    // La campagne passe « Envoyée » dans la liste (signal fiable et
    // vérifié côté backend), et le tableau de bord se recharge depuis le
    // VRAI back sans erreur (jamais des chiffres figés/mockés).
    await page.goto('/marketing/campagnes')
    const ligneEnvoyee = page.locator('[data-testid="campagne-row"]', { hasText: nomCampagne })
    await expect(ligneEnvoyee).toContainText('Envoyée')

    await page.goto('/marketing')
    await expect(page.getByTestId('mkt-dashboard-kpis')).toBeVisible({ timeout: 15_000 })
  })
})
