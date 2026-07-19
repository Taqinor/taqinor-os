// PUB14 — E2E des écrans « Publicité » NON couverts (Playwright ne couvrait
// que 5/17 écrans avant ce fichier : connexion/dashboard/approbations
// `adsengine.spec.js`, cockpit/EDIT_COPY/commentaires/dashboard-v2
// `adsengine-extended.spec.js`). Chaque `test()` ici couvre AU MOINS un
// écran manquant, en LISANT UNE VRAIE DONNÉE — soit via une VRAIE écriture
// publique (règles, arbre, plan de vol, simulation, créathèque : chacun a un
// endpoint d'écriture accessible, on seed pour de vrai comme
// `adsengine.spec.js`), soit — quand l'écran ne lit QUE des miroirs Meta sans
// aucune porte de seed publique (campagnes/instagram/backlog/brief, même
// contrainte que le cockpit/commentaires déjà couverts) — via le MÊME
// mock ciblé sanctionné par `adsengine-extended.spec.js` (page.route sur
// l'endpoint GET exact que l'écran appelle, jamais un mock générique).
//
// Même auth que le reste (storageState projet `chromium`, admin démo,
// aucun login réécrit ici).
import { test, expect } from '@playwright/test'

const API = '/api/django/adsengine'

test.describe('PUB14 — Règles & anomalies : catalogue (réel) + armement (réel) + journal', () => {
  const createdRuleIds = []

  test.afterAll(async ({ request }) => {
    await Promise.all(createdRuleIds.map((id) => (
      request.delete(`${API}/regles/${id}/`).catch(() => null)
    )))
  })

  test('le catalogue est réel, armer une règle la persiste, le journal se charge', async ({ page }) => {
    await page.goto('/publicite/regles')
    await expect(page.getByRole('heading', { name: 'Règles & anomalies' })).toBeVisible({ timeout: 20_000 })

    // Catalogue = données RÉELLES du backend (rule_templates.RULE_TEMPLATES).
    const templates = page.getByTestId('ae-rule-template')
    await expect(templates.first()).toBeVisible()

    // Armer la PREMIÈRE règle du catalogue (PUB23, cycle réel : confirmation
    // -> POST/PATCH réel -> RulePolicy persistée -> état visible « Armée »).
    const first = templates.first()
    const armBtn = first.locator('[data-testid^="ae-rule-arm-"]')
    await armBtn.click()
    const confirmBtn = first.locator('[data-testid^="ae-rule-arm-confirm-btn-"]')
    const [armResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/regles/')
        && ['POST', 'PATCH'].includes(r.request().method())),
      confirmBtn.click(),
    ])
    // Nettoyage UNIQUEMENT si ceci a CRÉÉ la ligne (jamais supprimer une
    // RulePolicy préexistante que ce test se contenterait de PATCHer).
    if (armResp.request().method() === 'POST' && armResp.ok()) {
      const created = await armResp.json()
      createdRuleIds.push(created.id)
    }
    await expect(first.locator('[data-testid^="ae-rule-state-"]')).toContainText('Armée', { timeout: 15_000 })

    // Journal d'exécution — section réelle (vide tant qu'aucune évaluation
    // planifiée n'a tourné, mais LUE depuis le vrai backend).
    await expect(page.getByTestId('ae-rules-journal')).toBeVisible()
  })
})

test.describe('PUB14 — Reporting : audit de compte à la demande (réel, 100% lecture)', () => {
  test('lancer l\'audit calcule les 5 sections depuis le vrai backend', async ({ page }) => {
    await page.goto('/publicite/reporting')
    await expect(page.getByRole('heading', { name: 'Reporting' })).toBeVisible({ timeout: 20_000 })

    await page.getByTestId('ae-reports-tab-audit').click()
    await page.getByTestId('ae-audit-lancer').click()

    // 100% lecture (ADSDEEP63) : jamais de mock, le calcul vient des miroirs
    // réels de la société démo (même vides, le statut 'inconnu' EST réel).
    const sections = page.locator('[data-testid^="ae-audit-section-"]')
    await expect(sections.first()).toBeVisible({ timeout: 20_000 })
    await expect(sections).toHaveCount(5)
  })

  test('le classement créatifs se charge (surface leaderboard/scatter)', async ({ page }) => {
    // Données spend-weighted par tag : chaîne complexe (AdMirror + tags +
    // InsightSnapshot) sans porte de seed publique — même exception
    // documentée que le cockpit/commentaires (adsengine-extended.spec.js).
    await page.route(`**${API}/reporting/creatifs/classement/**`, (route) => route.fulfill({
      json: {
        dimension: 'hook',
        untagged_count: 1,
        classement: [
          { id: 'hook-pub14', tag: 'Preuve sociale', spend: 620, results: 14, cost_per_result: 44.3, hook_rate_weighted: 0.31, ad_count: 3 },
        ],
      },
    }))
    await page.route(`**${API}/reporting/creatifs/nuage/**`, (route) => route.fulfill({
      json: { points: [], median_hook_rate: null, median_spend: null },
    }))

    await page.goto('/publicite/reporting')
    await expect(page.getByRole('heading', { name: 'Reporting' })).toBeVisible({ timeout: 20_000 })
    await page.getByTestId('ae-reports-tab-creatifs').click()

    await expect(page.getByTestId('ae-creatifs-leaderboard-row')).toContainText('Preuve sociale')
  })
})

test.describe('PUB14 — L\'Arbre : nœud d\'hypothèse réel', () => {
  const createdNodeIds = []

  test.afterAll(async ({ request }) => {
    await Promise.all(createdNodeIds.map((id) => (
      request.delete(`${API}/noeuds-hypothese/${id}/`).catch(() => null)
    )))
  })

  test('un nœud créé via l\'API réelle apparaît dans son groupe de statut', async ({ page, request }) => {
    const enonce = `PUB14 — nœud e2e ${Date.now()}`
    const res = await request.post(`${API}/noeuds-hypothese/`, {
      data: { classe: 'creatif', enonce_fr: enonce },
    })
    expect(res.ok()).toBeTruthy()
    const node = await res.json()
    createdNodeIds.push(node.id)

    await page.goto('/publicite/arbre')
    await expect(page.getByRole('heading', { name: "L'Arbre" })).toBeVisible({ timeout: 20_000 })

    // Statut par défaut du modèle = 'assumed' -> groupe « Supposé ».
    const group = page.getByTestId('ae-tree-group-assumed')
    await expect(group).toBeVisible()
    await expect(group).toContainText(enonce)

    // Drill 1 (nœud -> tests) — lu depuis le vrai backend, vide mais réel.
    await page.getByTestId(`ae-tree-node-toggle-${node.id}`).click()
    await expect(page.getByTestId(`ae-tree-node-tests-${node.id}`)).toBeVisible()
  })
})

test.describe('PUB14 — Plan de vol : gabarits/préflight réels + validation réelle', () => {
  test('composer un plan depuis un gabarit réel et le valider (feu vert ou refus réel)', async ({ page }) => {
    await page.goto('/publicite/plan-de-vol')
    await expect(page.getByTestId('ae-flightplan')).toBeVisible({ timeout: 20_000 })

    // Préflight = calcul réel des portes d'autonomie (ADSENG38), toujours présent.
    await expect(page.getByTestId('ae-fp-preflight-verdict')).toBeVisible()

    const templateSelect = page.getByTestId('ae-fp-template')
    const optionCount = await templateSelect.locator('option').count()
    // Gabarits statiques RÉELS (launch_templates) : au moins « Choisir… » + 1.
    expect(optionCount).toBeGreaterThan(1)
    await templateSelect.selectOption({ index: 1 })

    await expect(page.getByTestId('ae-fp-phases')).toBeVisible()
    await page.getByTestId('ae-fp-nom').fill(`PUB14 plan ${Date.now()}`)

    // Validation RÉELLE (POST plans-vol/validate/) — feu vert ou refus, les
    // deux sont un résultat réel exploitable par le test.
    await page.getByTestId('ae-fp-validate').click()
    await expect(page.getByTestId('ae-fp-valid').or(page.getByTestId('ae-fp-refusal')))
      .toBeVisible({ timeout: 15_000 })
  })
})

test.describe('PUB14 — Simulation : catalogue de scénarios réel', () => {
  test('sélectionner un scénario réel affiche son rapport (même vide, réel)', async ({ page }) => {
    await page.goto('/publicite/simulation')
    await expect(page.getByRole('heading', { name: 'Visionneuse de simulation' })).toBeVisible({ timeout: 20_000 })

    // Catalogue statique RÉEL (simulator.EXPECTED_VERDICT) — jamais un mock.
    const runs = page.getByTestId('ae-sim-runs')
    await expect(runs).toBeVisible()
    const firstRun = runs.locator('button').first()
    await expect(firstRun).toBeVisible()
    await firstRun.click()

    await expect(page.getByTestId('ae-sim-report')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByTestId('ae-sim-scenarios')).toBeVisible()
  })
})

test.describe('PUB14 — Bibliothèque créative (créathèque) : asset réel + policy-check réel', () => {
  const createdAssetIds = []

  test.afterAll(async ({ request }) => {
    await Promise.all(createdAssetIds.map((id) => (
      request.delete(`${API}/creatifs/${id}/`).catch(() => null)
    )))
  })

  test('un asset créé via l\'API réelle se vérifie de bout en bout (checklist humaine)', async ({ page, request }) => {
    const res = await request.post(`${API}/creatifs/`, { data: { asset_type: 'static' } })
    expect(res.ok()).toBeTruthy()
    const asset = await res.json()
    createdAssetIds.push(asset.id)

    await page.goto('/publicite/creatifs')
    await expect(page.getByRole('heading', { name: 'Bibliothèque créative' })).toBeVisible({ timeout: 20_000 })

    const card = page.getByTestId('ae-creative-card').filter({ hasText: 'Créatif' }).first()
    await expect(card).toBeVisible()
    await expect(page.getByTestId(`ae-creative-status-${asset.id}`)).toContainText('À vérifier')

    // Checklist humaine RÉELLE (ENG16) : confirmer chaque règle puis valider
    // -> POST policy-check RÉEL -> statut passe à « Vérifié ».
    await page.getByTestId(`ae-creative-check-${asset.id}`).click()
    const checklist = page.getByTestId(`ae-creative-checklist-${asset.id}`)
    await expect(checklist).toBeVisible()
    const boxes = checklist.locator('input[type="checkbox"]')
    const count = await boxes.count()
    for (let i = 0; i < count; i += 1) {
      await boxes.nth(i).check()
    }
    await page.getByTestId(`ae-creative-validate-${asset.id}`).click()
    await expect(page.getByTestId(`ae-creative-status-${asset.id}`)).toContainText('Vérifié', { timeout: 15_000 })
  })
})

test.describe('PUB14 — Campagnes : drill 3 niveaux (mock ciblé, données miroir Meta)', () => {
  // AdCampaignMirror/AdSetMirror/AdMirror ne s'alimentent QUE par synchro Meta
  // réelle : aucune porte de seed publique, même contrainte que le cockpit
  // déjà couvert (adsengine-extended.spec.js) — mock ciblé sur les 2 GET
  // exacts que l'écran appelle (campaigns.list + campaigns.hierarchy).
  test('Campagnes -> Ad sets -> Ads, fil d\'Ariane fonctionnel', async ({ page }) => {
    await page.route(`**${API}/campaigns/**`, async (route) => {
      const url = new URL(route.request().url())
      if (url.pathname.endsWith('/hierarchie/')) {
        return route.fulfill({
          json: {
            id: 901, nom: 'Campagne PUB14', statut_display: 'Active', objectif: 'OUTCOME_LEADS',
            budget_quotidien_mad: '200.00', meta_id: 'camp-901', nb_leads: 9,
            adsets: [
              {
                id: 9011, nom: 'Ad set PUB14', statut_display: 'Active',
                learning_badge: { label: 'En apprentissage' }, budget_quotidien_mad: '200.00',
                depense_mad: '80.00', nb_leads: 4,
                ads: [
                  { id: 90111, nom: 'Ad PUB14 A', statut_display: 'Active', depense_mad: '50.00', nb_leads: 3 },
                  { id: 90112, nom: 'Ad PUB14 B', statut_display: 'En pause', depense_mad: '30.00', nb_leads: 1 },
                ],
              },
            ],
          },
        })
      }
      if (route.request().url().includes('creative-ranking')) {
        return route.fulfill({ json: [] })
      }
      return route.fulfill({ json: [
        { id: 901, nom: 'Campagne PUB14', statut_display: 'Active', budget_quotidien_mad: '200.00', depense_mad: '80.00' },
      ] })
    })

    await page.goto('/publicite/campagnes')
    await expect(page.getByRole('heading', { name: 'Campagnes' })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('ae-camp-row')).toContainText('Campagne PUB14')

    // Niveau 1 -> 2.
    await page.getByTestId('ae-camp-open').click()
    await expect(page.getByTestId('ae-camp-hierarchy')).toBeVisible()
    await expect(page.getByTestId('ae-camp-adset-row')).toContainText('Ad set PUB14')

    // Niveau 2 -> 3.
    await page.getByTestId('ae-camp-adset-open').click()
    const adRows = page.getByTestId('ae-camp-ad-row')
    await expect(adRows).toHaveCount(2)
    await expect(adRows.first()).toContainText('Ad PUB14 A')

    // Fil d'Ariane : remonte au niveau 2 sans recharger la liste.
    await page.getByTestId('ae-camp-breadcrumb-campaign').click()
    await expect(page.getByTestId('ae-camp-adset-row')).toBeVisible()
  })
})

test.describe('PUB14 — Instagram : médias + commentaires (mock ciblé, données miroir Meta)', () => {
  // InstagramMediaMirror/InstagramCommentMirror : même contrainte (Meta-sync
  // uniquement). La proposition (toggle commentaires) reste réelle côté
  // FORME (mêmes payloads que le code appelle) mais interceptée en réseau.
  test('grille de médias réelle-forme + toggle commentaires -> proposition', async ({ page }) => {
    await page.route(`**${API}/instagram/medias/**`, async (route) => {
      if (route.request().method() === 'POST') {
        return route.fulfill({ json: { status: 'proposed' } })
      }
      return route.fulfill({ json: [
        { id: 701, meta_id: 'ig-701', caption: 'Chantier terminé — Casablanca', like_count: 12,
          comments_count: 1, comment_enabled: true, media_type: 'IMAGE' },
      ] })
    })
    await page.route(`**${API}/instagram/commentaires/**`, (route) => route.fulfill({ json: [] }))
    await page.route(`**${API}/instagram/quota/**`, (route) => route.fulfill({ json: { used: 3, total: 50, remaining: 47 } }))

    await page.goto('/publicite/instagram')
    await expect(page.getByRole('heading', { name: 'Instagram' })).toBeVisible({ timeout: 20_000 })

    await expect(page.getByTestId('ae-ig-quota')).toContainText('3/50')
    const card = page.getByTestId('ae-ig-media-card')
    await expect(card).toContainText('Chantier terminé')

    // Légende LECTURE SEULE, jamais éditable.
    await expect(page.getByTestId('ae-ig-caption-readonly-701')).toBeVisible()

    await page.getByTestId('ae-ig-toggle-comments-701').click()
    await expect(page.getByTestId('ae-ig-proposed-m-701')).toContainText('Proposé')
  })
})

test.describe('PUB14 — Backlog créatif : runway + lot (mock ciblé, chaîne campagne+recombinaison)', () => {
  test('runway/diversité affichés, approbation d\'un lot bout-en-bout', async ({ page }) => {
    await page.route(`**${API}/backlog/**`, async (route) => {
      const url = route.request().url()
      if (url.includes('/lots/') && route.request().method() === 'POST') {
        return route.fulfill({ json: { id: 601, statut: 'approuve' } })
      }
      return route.fulfill({ json: [
        {
          id: 801, campagne: 'Campagne PUB14 backlog', runway_jours: 4, runway_cible: 14,
          diversite_hooks: 0.35,
          lots: [{ id: 601, nom: 'Lot recombinaison A', statut: 'en_attente', statut_display: 'En attente',
            assets: [{ id: 1 }, { id: 2 }], nb_hooks: 2 }],
        },
      ] })
    })

    await page.goto('/publicite/backlog')
    await expect(page.getByRole('heading', { name: 'Backlog créatif' })).toBeVisible({ timeout: 20_000 })

    const campaign = page.getByTestId('ae-backlog-campaign')
    await expect(campaign).toContainText('Campagne PUB14 backlog')
    await expect(page.getByTestId('ae-backlog-runway')).toContainText('4 j sur 14 j')

    await page.getByTestId('ae-backlog-approve-lot-601').click()
    await expect(page.getByTestId('ae-backlog-lot-status-601')).toContainText('Approuvé')
  })
})

test.describe('PUB14 — Brief hebdomadaire : dernier brief (mock ciblé, généré par tâche planifiée)', () => {
  // WeeklyBrief n'a pas de porte d'écriture publique (généré par
  // generate_weekly_brief, celery) — mock ciblé sur brief/latest.
  test('affiche quoi/pourquoi/suggestion + lien vers l\'approbation', async ({ page }) => {
    await page.route(`**${API}/brief/**`, (route) => route.fulfill({
      json: {
        periode: 'Semaine du 13 au 19 juillet 2026',
        resume: 'Dépense stable, 2 signatures, 1 anomalie détectée.',
        items: [
          {
            id: 1, quoi: 'La campagne « Résidentiel Casa » a dépassé son plafond de fréquence.',
            pourquoi: 'Fréquence à 4.2 sur 7 jours (seuil 3.5).',
            suggestion: 'Faire tourner une nouvelle création.',
            action_id: 55,
          },
        ],
      },
    }))

    await page.goto('/publicite/brief')
    await expect(page.getByRole('heading', { name: 'Brief hebdomadaire' })).toBeVisible({ timeout: 20_000 })

    await expect(page.getByTestId('ae-brief-periode')).toContainText('13 au 19 juillet 2026')
    const card = page.getByTestId('ae-brief-card')
    await expect(card).toContainText('dépassé son plafond de fréquence')
    await expect(card).toContainText('Faire tourner une nouvelle création')
    await expect(page.getByTestId('ae-brief-approve-link')).toHaveAttribute('href', '/publicite/approbations')
  })
})
