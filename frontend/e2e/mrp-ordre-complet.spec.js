// NTMFG37 — E2E : parcours complet « créer OF → réserver → produire →
// clôturer avec contrôle qualité ».
//
// ADAPTATION DE PÉRIMÈTRE (documentée) : le plan nomme ce fichier
// `mrp-ordre-complet.spec.ts`, mais AUCUN spec `.ts` n'existe dans cette
// suite — les 45+ specs existants (E1-16 et au-delà) sont tous `.js`, sans
// tsconfig e2e dédié. Écrit en `.js` pour rester byte-identique à la
// convention réelle du dossier (même motif qu'un `ParametresSCM` posé en
// OneToOne plutôt que dans `apps/parametres` — adaptation de périmètre
// documentée, jamais un écart silencieux).
//
// « point de contrôle qualité obligatoire (NTMFG13) » — NTMFG13 (blocage QC
// bloquant, `ParametresMRP.blocage_qc_force_motif_obligatoire`) n'est PAS
// encore construit dans ce dépôt (round 1/2 : « NTMFG13 hors périmètre de ce
// lot », voir `apps/mrp/selectors.py`). Le point de contrôle qualité RÉEL qui
// existe aujourd'hui est la saisie quantité bonne/rebut + motif obligatoire
// du terminal atelier (NTMFG8, `OperationCard.terminer()` — un rebut sans
// motif est refusé côté UI ET service). Ce scénario mappe donc « un succès,
// un échec forcé » sur les DEUX opérations de l'OF : la première terminée
// 100 % bonne (succès), la seconde terminée avec un rebut + motif (échec
// forcé) — le même mécanisme de contrôle qualité qui existe réellement,
// jamais une fonctionnalité inventée pour ce test.
//
// Aucune donnée MRP (poste de charge / gamme / nomenclature) n'est seedée
// par `seed_demo_company` : ce spec seed ses PROPRES prérequis via
// `page.request` (cookie admin déjà authentifié — patron
// `comptes-justes.spec.js`) avant de piloter l'écran, exactement comme
// l'assistant NTMFG26 ne sait pas créer un poste de charge/une gamme depuis
// l'UI (aucun écran dédié n'existe pour ça).
import { test, expect } from '@playwright/test'

function uniq(prefix) {
  return `${prefix} ${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
}

let posteId
let produitFiniId
let composantId
let kitId
let gammeId
let ofId

test.describe('NTMFG37: parcours OF complet (créer -> réserver -> produire -> clôturer)', () => {
  test.afterAll(async ({ request }) => {
    // Nettoyage best-effort (patron comptes-justes.spec.js) : une erreur
    // isolée ne doit jamais empêcher de nettoyer le reste. Ordre imposé par
    // les FK PROTECT (OF avant gamme avant produits/poste).
    if (ofId) await request.delete(`/api/django/mrp/ordres-fabrication/${ofId}/`).catch(() => null)
    if (gammeId) await request.delete(`/api/django/mrp/gammes/${gammeId}/`).catch(() => null)
    if (kitId) await request.delete(`/api/django/stock/kits/${kitId}/`).catch(() => null)
    if (produitFiniId) await request.delete(`/api/django/stock/produits/${produitFiniId}/`).catch(() => null)
    if (composantId) await request.delete(`/api/django/stock/produits/${composantId}/`).catch(() => null)
    if (posteId) await request.delete(`/api/django/mrp/postes-charge/${posteId}/`).catch(() => null)
  })

  test('créer OF -> réserver -> terminal atelier -> clôturer', async ({ page }) => {
    const nomProduitFini = uniq('E2E OF Panneau')
    const nomComposant = uniq('E2E OF Cadre')
    const nomPoste = uniq('E2E OF Poste')

    // ── Seed des prérequis (aucun écran dédié pour poste/nomenclature) ────
    const posteRes = await page.request.post('/api/django/mrp/postes-charge/', {
      data: { code: nomPoste, nom: nomPoste, capacite_heures_jour: '8' },
    })
    expect(posteRes.ok(), await posteRes.text()).toBeTruthy()
    posteId = (await posteRes.json()).id

    const composantRes = await page.request.post('/api/django/stock/produits/', {
      data: { nom: nomComposant, prix_vente: '10.00', quantite_stock: 100 },
    })
    expect(composantRes.ok(), await composantRes.text()).toBeTruthy()
    composantId = (await composantRes.json()).id

    const produitFiniRes = await page.request.post('/api/django/stock/produits/', {
      data: { nom: nomProduitFini, prix_vente: '500.00' },
    })
    expect(produitFiniRes.ok(), await produitFiniRes.text()).toBeTruthy()
    produitFiniId = (await produitFiniRes.json()).id

    const kitRes = await page.request.post('/api/django/stock/kits/', {
      data: {
        nom: `Nomenclature ${nomProduitFini}`,
        composants: [{ produit: composantId, quantite: '2' }],
      },
    })
    expect(kitRes.ok(), await kitRes.text()).toBeTruthy()
    kitId = (await kitRes.json()).id

    const gammeRes = await page.request.post('/api/django/mrp/gammes/', {
      data: { nom: `Gamme ${nomProduitFini}`, produit: produitFiniId, kit_source: kitId },
    })
    expect(gammeRes.ok(), await gammeRes.text()).toBeTruthy()
    gammeId = (await gammeRes.json()).id

    const op1Res = await page.request.post('/api/django/mrp/operations-gamme/', {
      data: {
        gamme: gammeId, ordre: 1, poste_charge: posteId, libelle: 'Assemblage',
        temps_prepa_min: '5', temps_unitaire_min: '1',
      },
    })
    expect(op1Res.ok(), await op1Res.text()).toBeTruthy()
    const op2Res = await page.request.post('/api/django/mrp/operations-gamme/', {
      data: {
        gamme: gammeId, ordre: 2, poste_charge: posteId, libelle: 'Contrôle final',
        temps_prepa_min: '2', temps_unitaire_min: '1',
      },
    })
    expect(op2Res.ok(), await op2Res.text()).toBeTruthy()

    // ── Étape 1 : créer l'OF via l'assistant guidé (NTMFG26) ──────────────
    await page.goto('/mrp/assistant-creation-of')
    await expect(page.getByRole('heading', { name: 'Assistant nouvel OF' })).toBeVisible()

    await page.locator('#assistant-produit').click()
    await page.getByRole('searchbox').fill(nomProduitFini)
    await expect(page.getByRole('option', { name: nomProduitFini })).toBeVisible({ timeout: 10_000 })
    await page.getByRole('option', { name: nomProduitFini }).click()
    await page.getByRole('button', { name: /Suivant/ }).click()

    await expect(page.locator('#assistant-gamme')).toBeVisible()
    await page.locator('#assistant-gamme').selectOption(String(gammeId))
    await page.locator('#assistant-quantite').fill('2')
    await page.getByRole('button', { name: /Suivant/ }).click()

    await expect(page.getByText(nomProduitFini)).toBeVisible()
    await page.getByRole('button', { name: "Créer l'OF" }).click()
    const creeMessage = page.getByText(/^OF-\d+ créé \(brouillon\)\.$/)
    await expect(creeMessage).toBeVisible({ timeout: 15_000 })
    const texteOf = await creeMessage.textContent()
    ofId = Number(texteOf.match(/OF-(\d+)/)[1])
    expect(ofId).toBeGreaterThan(0)

    // ── Étape 2 : confirmer -> vérifier réservation composants (NTMFG6) ──
    await page.goto('/mrp/ordres-fabrication')
    await expect(page.getByText(`OF-${ofId}`)).toBeVisible({ timeout: 15_000 })
    await page.getByText(`OF-${ofId}`).click()
    await expect(page.getByRole('button', { name: 'Confirmer' })).toBeVisible()
    await page.getByRole('button', { name: 'Confirmer' }).click()

    // La page ne se rafraîchit pas seule après confirmation (pas de refetch
    // câblé sur ce bouton) : on recharge pour lire l'état serveur à jour.
    await page.reload()
    await expect(page.getByText(`OF-${ofId}`)).toBeVisible({ timeout: 15_000 })
    await page.getByText(`OF-${ofId}`).click()
    await expect(page.getByText('planifie')).toBeVisible({ timeout: 10_000 })
    // Réservation composants (NTMFG6) : le composant de la nomenclature
    // (2 unités/panneau × quantité 2 = 4) apparaît réservé — assertion
    // scopée à la LIGNE de réservation (pas un « 4 » nu ailleurs sur la page).
    const ligneReservation = page.locator('div', { hasText: `Produit #${composantId}` }).last()
    await expect(ligneReservation).toBeVisible()
    await expect(ligneReservation).toContainText('4')

    // ── Étape 3 : terminal atelier (NTMFG8) — démarrer/terminer chaque
    //    opération, une bonne (succès), une en rebut + motif (échec forcé) ─
    await page.goto('/mrp/terminal')
    await expect(page.getByRole('heading', { name: 'Terminal atelier' })).toBeVisible()
    await page.getByRole('combobox').first().click()
    await page.getByRole('option', { name: nomPoste }).click()

    // Opération 1 — « Assemblage » : succès (quantité bonne uniquement).
    const carteAssemblage = page.locator('.mb-3', { hasText: 'Assemblage' }).first()
    await expect(carteAssemblage).toBeVisible({ timeout: 15_000 })
    await carteAssemblage.getByRole('button', { name: /Démarrer/ }).click()
    await expect(carteAssemblage.getByRole('button', { name: /Terminer/ })).toBeVisible({ timeout: 10_000 })
    await carteAssemblage.getByRole('button', { name: /Terminer/ }).click()
    await carteAssemblage.locator('input[type="number"]').first().fill('2')
    await carteAssemblage.getByRole('button', { name: 'Valider' }).click()
    await expect(carteAssemblage).toBeHidden({ timeout: 10_000 })

    // Opération 2 — « Contrôle final » : échec forcé (rebut + motif requis).
    const carteControle = page.locator('.mb-3', { hasText: 'Contrôle final' }).first()
    await expect(carteControle).toBeVisible({ timeout: 15_000 })
    await carteControle.getByRole('button', { name: /Démarrer/ }).click()
    await expect(carteControle.getByRole('button', { name: /Terminer/ })).toBeVisible({ timeout: 10_000 })
    await carteControle.getByRole('button', { name: /Terminer/ }).click()
    const quantiteInputs = carteControle.locator('input[type="number"]')
    await quantiteInputs.nth(1).fill('2') // quantité rebut > 0.
    // Sans motif, la validation est refusée (contrôle qualité obligatoire).
    await carteControle.getByRole('button', { name: 'Valider' }).click()
    await expect(carteControle.getByText('Motif de rebut requis.')).toBeVisible()
    await carteControle.getByRole('combobox').click()
    await page.getByRole('option', { name: 'Défaut' }).click()
    await carteControle.getByRole('button', { name: 'Valider' }).click()
    await expect(carteControle).toBeHidden({ timeout: 10_000 })

    // ── Étape 4 : clôturer -> vérifier mouvement de stock + statut termine ─
    await page.goto('/mrp/ordres-fabrication')
    await expect(page.getByText(`OF-${ofId}`)).toBeVisible({ timeout: 15_000 })
    await page.getByText(`OF-${ofId}`).click()
    await expect(page.getByRole('button', { name: 'Clôturer' })).toBeVisible()

    const composantAvant = await page.request.get(`/api/django/stock/produits/${composantId}/`)
    const stockAvant = (await composantAvant.json()).quantite_stock

    await page.getByRole('button', { name: 'Clôturer' }).click()

    // NTMFG4 — le backflush est asynchrone-adjacent côté écran (pas de
    // refetch câblé non plus) : on interroge l'API directement, la source de
    // vérité du statut final ET du mouvement de stock.
    await expect(async () => {
      const ofRes = await page.request.get(`/api/django/mrp/ordres-fabrication/${ofId}/`)
      expect((await ofRes.json()).statut).toBe('termine')
    }).toPass({ timeout: 15_000 })

    const composantApres = await page.request.get(`/api/django/stock/produits/${composantId}/`)
    const stockApres = (await composantApres.json()).quantite_stock
    // Backflush NTMFG4 : 2 unités composant/panneau × 2 panneaux = 4
    // consommées (mouvement de stock réel, une seule fois).
    expect(stockAvant - stockApres).toBe(4)
  })
})
