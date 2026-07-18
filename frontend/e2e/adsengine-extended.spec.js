// ADSDEEP64 — E2E Playwright de la console « Publicité » ÉTENDUE (ADSENGINT3).
// ----------------------------------------------------------------------------
// `adsengine.spec.js` (ADSENGINT1/2) fait exprès de parler au VRAI backend
// Django, sans aucun mock : c'est possible parce que ses trois surfaces
// (connexion, dashboard « un chiffre », approbations) se seedent bout-en-bout
// via l'API RÉELLE (connection.save écrit un jeton write-only ; EngineAction
// se crée par un POST public /adsengine/actions/).
//
// Les QUATRE surfaces ADSDEEP couvertes ICI n'ont PAS cette porte de seed
// publique : le cockpit par ad / la boîte de réception des commentaires / le
// Dashboard v2 lisent des données MIROITÉES depuis Meta (AdMirror,
// CommentMirror, conversations CTWA) que seule une synchronisation Meta réelle
// alimente — aucun endpoint d'écriture n'existe pour les poser en seed de
// test. On mocke donc précisément les endpoits GET que CHAQUE écran appelle
// (vérifiés dans adsengineApi.js + les screens eux-mêmes), tout en réutilisant
// EXACTEMENT le même mécanisme d'auth que adsengine.spec.js (storageState du
// projet `chromium`, déjà authentifié en admin démo — aucun login réécrit
// ici). L'approbation EDIT_COPY, elle, PEUT rester proche du réel : seule sa
// liste (`actions.pending`) et son `approve` sont mockés, exactement la même
// forme de payload que EditCopyComposer.jsx écrit réellement.
import { test, expect } from '@playwright/test'

const pathnameOf = (url) => new URL(url).pathname

// URL fraîche générique pour tout média (vidéo/image) résolu à l'affichage —
// jamais persistée (ADSDEEP12) ; le contenu réel de l'URL n'importe pas ici.
async function mockMedia(page) {
  await page.route('**/api/django/adsengine/media/**', (route) =>
    route.fulfill({ json: { url: 'https://cdn.example.test/mock-media.jpg' } }))
}

test.describe('ADSDEEP64 : console Publicité étendue (mocks ciblés, ADSENGINT3)', () => {
  test('Cockpit par ad : une ligne par ad, table triable, drill créatif', async ({ page }) => {
    const ROWS = [
      {
        id: 1, meta_id: 'ad-1', nom: 'Reel toiture', statut: 'ACTIVE', statut_display: 'Active',
        learning_badge: { status: 'LEARNING', label: 'En apprentissage', tone: 'info' },
        thumbnail_ref: 'vid-123', thumbnail_kind: 'video',
        depense_mad: '900.00', conversations: 12, nb_leads: 5, cpl_mad: '180.00',
        signatures: 1, cost_per_signature_mad: '900.00', frequency: '2.10',
        fatigue: { fired: true, insufficient_data: false, severity: 'critique', message_fr: 'Fatigue confirmée' },
      },
      {
        id: 2, meta_id: 'ad-2', nom: 'Statique prix', statut: 'ACTIVE', statut_display: 'Active',
        learning_badge: { status: 'SUCCESS', label: 'Optimisé', tone: 'success' },
        thumbnail_ref: 'img-hash-1', thumbnail_kind: 'image',
        depense_mad: '300.00', conversations: 20, nb_leads: 8, cpl_mad: '37.50',
        signatures: 2, cost_per_signature_mad: '150.00', frequency: '1.20',
        fatigue: { fired: false, insufficient_data: false, severity: 'avertissement', message_fr: '' },
      },
      {
        id: 3, meta_id: 'ad-3', nom: 'Explainer', statut: 'PAUSED', statut_display: 'En pause',
        learning_badge: { status: '', label: 'Inconnu', tone: 'neutral' },
        thumbnail_ref: null, thumbnail_kind: 'image',
        depense_mad: '50.00', conversations: 0, nb_leads: 0, cpl_mad: null,
        signatures: 0, cost_per_signature_mad: null, frequency: null,
        fatigue: { fired: false, insufficient_data: true, severity: 'info', message_fr: '' },
      },
    ]
    await mockMedia(page)
    await page.route('**/api/django/adsengine/metrics/ads-cockpit/**', (route) =>
      route.fulfill({ json: ROWS }))

    await page.goto('/publicite/cockpit')
    await expect(page.getByRole('heading', { name: 'Cockpit par ad' })).toBeVisible({ timeout: 20_000 })

    // Une ligne PAR ad, tri par défaut = dépense décroissante -> Reel toiture en tête.
    const rows = page.getByTestId('ae-cockpit-row')
    await expect(rows).toHaveCount(3)
    await expect(rows.nth(0)).toContainText('Reel toiture')
    await expect(rows.nth(1)).toContainText('Statique prix')
    await expect(rows.nth(2)).toContainText('Explainer')

    // Tri sur une autre colonne : clic sur « Leads » -> croissant (0, 5, 8).
    await page.getByTestId('ae-cockpit-sort-nb_leads').click()
    await expect(rows.nth(0)).toContainText('Explainer')
    await expect(rows.nth(1)).toContainText('Reel toiture')
    await expect(rows.nth(2)).toContainText('Statique prix')
    // Reclic -> décroissant (8, 5, 0).
    await page.getByTestId('ae-cockpit-sort-nb_leads').click()
    await expect(rows.nth(0)).toContainText('Statique prix')

    // Drill-down : « Détail » descend jusqu'au panneau créatif (ADSDEEP14).
    await page.getByTestId('ae-cockpit-open').first().click()
    await expect(page.getByTestId('ae-cockpit-detail')).toBeVisible()
    await expect(page.getByTestId('ae-creative-panel')).toBeVisible()
  })

  test("EDIT_COPY dans la boîte d'approbation : avertissements + diff avant/après", async ({ page }) => {
    const EDIT_ACTION = {
      id: 21, type: 'edit_copy', reason_fr: "Rafraîchir l'accroche.",
      payload: {
        warnings: [
          "Édition significative : cette action réinitialise la phase d'apprentissage "
          + "de l'ad set (Meta ré-explore — coûts instables pendant quelques jours).",
          'Changer le texte crée un NOUVEAU post : la preuve sociale déjà accumulée '
          + '(J’aime, commentaires, partages) est perdue.',
        ],
        current_creative: { body: 'Ancien texte fatigué, à rafraîchir.' },
        creative_spec: { title: 'Nouveau', body: 'Nouveau texte frais, accroche revue.' },
      },
    }
    let approved = false
    await page.route('**/api/django/adsengine/actions/**', async (route) => {
      const req = route.request()
      const pathname = pathnameOf(req.url())
      if (req.method() === 'POST' && pathname.endsWith('/actions/21/approve/')) {
        approved = true
        return route.fulfill({ json: { ...EDIT_ACTION, status: 'approuvee' } })
      }
      if (req.method() === 'GET' && pathname.endsWith('/adsengine/actions/')) {
        return route.fulfill({ json: approved ? [] : [EDIT_ACTION] })
      }
      return route.continue()
    })

    await page.goto('/publicite/approbations')
    await expect(page.getByRole('heading', { name: "Boîte d'approbation" })).toBeVisible({ timeout: 20_000 })

    // Avertissements portés par le backend, rendus en chips (JAMAIS recalculés).
    const chips = page.getByTestId('ae-warning-chip')
    await expect(chips).toHaveCount(2)
    await expect(chips.first()).toContainText("réinitialise la phase d'apprentissage")
    await expect(chips.nth(1)).toContainText('preuve sociale')

    // Diff avant/après CÔTE À CÔTE (ADSDEEP35).
    const diff = page.getByTestId('ae-edit-copy-diff')
    await expect(diff).toBeVisible()
    await expect(page.getByTestId('ae-edit-copy-before')).toContainText('Ancien texte fatigué')
    await expect(page.getByTestId('ae-edit-copy-after')).toContainText('Nouveau texte frais')

    // Approuver bout-en-bout (mocké) -> quitte la boîte.
    await page.getByTestId('ae-approve-21').click()
    await expect(page.getByTestId('ae-action-card')).toHaveCount(0)
  })

  test("Boîte de réception des commentaires : badge « caché-vérifié » + actions inline", async ({ page }) => {
    const COMMENTS = [
      {
        id: 501, object_meta_id: 'ad-777', source: 'ad',
        is_hidden: true, hidden_verified: true, answered: false,
        from_name: 'Karim B.', message: 'Ce produit a l’air suspect, remboursement ?',
        created_time: new Date().toISOString(),
      },
      {
        id: 502, object_meta_id: 'post-321', source: 'post',
        is_hidden: false, hidden_verified: false, answered: false,
        from_name: 'Sara L.', message: 'Combien coûte l’installation pour une villa ?',
        created_time: new Date().toISOString(),
      },
    ]
    await page.route('**/api/django/adsengine/commentaires/**', async (route) => {
      const req = route.request()
      if (req.method() === 'POST' && pathnameOf(req.url()).endsWith('/masquer/')) {
        return route.fulfill({ json: { status: 'proposed' } })
      }
      if (req.method() === 'GET') {
        return route.fulfill({ json: COMMENTS })
      }
      return route.continue()
    })

    await page.goto('/publicite/commentaires')
    await expect(page.getByRole('heading', { name: 'Commentaires' })).toBeVisible({ timeout: 20_000 })

    // Le read-back backend CONFIRME le masquage -> badge « caché-vérifié ».
    await expect(page.getByTestId('ae-hidden-verified-501')).toContainText('Caché — vérifié')
    // Le second commentaire n'est pas masqué : pas de badge sur lui.
    await expect(page.getByTestId('ae-hidden-unverified-502')).toHaveCount(0)
    await expect(page.getByTestId('ae-hidden-verified-502')).toHaveCount(0)

    // Compteur cockpit cohérent (2 au total, 1 masqué).
    await expect(page.getByTestId('ae-count-total')).toContainText('2 au total')
    await expect(page.getByTestId('ae-count-hidden')).toContainText('1 masqué')

    // Action INLINE = une PROPOSITION (règle #3, jamais une écriture Meta directe).
    await page.getByTestId('ae-comment-hide-502').click()
    await expect(page.getByTestId('ae-proposed-502')).toContainText(
      "Proposé — à approuver dans la boîte d'approbation.")
  })

  test('Dashboard v2 : conversations réelles + MER mixte, deux devises JAMAIS fusionnées', async ({ page }) => {
    const V2 = {
      window_days: 14,
      conversations: {
        total: 47,
        sparkline: Array.from({ length: 14 }, (_, i) => ({ date: `2026-07-${i + 1}`, value: 2 + (i % 5) })),
      },
      mer: {
        spend: 5200, spend_currency: 'USD',
        signed_ca_mad: 148000, signed_ca_currency: 'MAD',
        // Devises différentes -> l'API ne calcule PAS de ratio : le front ne
        // doit rien fusionner/convertir lui-même (doctrine ADSDEEP61).
        mer_ratio: null,
        note: 'Dépense Meta (USD) et CA signé (MAD) : devises différentes, non converties.',
        spend_sparkline: Array.from({ length: 14 }, (_, i) => ({ date: `2026-07-${i + 1}`, value: 300 + i * 10 })),
        signed_ca_sparkline: Array.from({ length: 14 }, (_, i) => ({ date: `2026-07-${i + 1}`, value: 8000 + i * 500 })),
      },
    }
    await page.route('**/api/django/adsengine/metrics/dashboard/**', (route) =>
      route.fulfill({ json: { cost_per_signature: 900, spend: 5200, cpl: 120, frequency: 1.8, currency: 'USD' } }))
    await page.route('**/api/django/adsengine/alertes/**', (route) => route.fulfill({ json: [] }))
    await page.route('**/api/django/adsengine/metrics/dashboard-v2/**', (route) => route.fulfill({ json: V2 }))

    await page.goto('/publicite/tableau-de-bord')
    await expect(page.getByRole('heading', { name: 'Tableau de bord publicitaire' })).toBeVisible({ timeout: 20_000 })

    const dv2 = page.getByTestId('ae-dv2')
    await expect(dv2).toBeVisible()

    // Conversations WhatsApp réelles + sparkline.
    await expect(page.getByTestId('ae-dv2-conversations-total')).toContainText('47')
    await expect(page.getByTestId('ae-dv2-conversations-sparkline')).toBeVisible()

    // MER mixte : LES DEUX devises visibles côte à côte, jamais fusionnées.
    await expect(page.getByTestId('ae-dv2-mer-spend')).toContainText('USD')
    await expect(page.getByTestId('ae-dv2-mer-ca')).toContainText('MAD')
    // Aucun ratio combiné affiché puisque l'API n'en a pas fourni (devises
    // différentes) : la preuve que rien n'est silencieusement converti.
    await expect(page.getByTestId('ae-dv2-mer-ratio')).toHaveCount(0)
    await expect(page.getByTestId('ae-dv2-mer-spend-sparkline')).toBeVisible()
    await expect(page.getByTestId('ae-dv2-mer-ca-sparkline')).toBeVisible()
  })
})
