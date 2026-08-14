// AOF187 (1/3) — Parcours AO de bout en bout : création d'une affaire, import
// d'un plan PDF, calibrage, traçage, pose de 3 obstacles, lancement du
// calepinage et lecture du verdict.
//
// Repose sur les hooks `data-ao-*` figés par AOF8 et sur l'environnement
// planté par `seed_ao_demo` (AOF186) — l'affaire elle-même est créée FRAÎCHE
// ici (via `uniq()`) pour rester rejouable sans collision entre exécutions,
// exactement comme les autres specs de cette suite créent leur propre lead/
// devis plutôt que de muter un enregistrement partagé.
//
// Stabilité (Done= AOF187) : aucune assertion sur la date du jour, aucun nom
// accessible dérivé d'une icône — voir le commentaire d'en-tête de helpers.js.
//
// ── CORRECTION 14/08/2026 — l'atelier toiture est un ONGLET, pas un lien ─────
// `getByRole('link', { name: /Toiture/ })` ne pouvait pas atteindre la section
// « Toitures & relevés » de la fiche (onglet Radix `role="tab"`, rendu par
// `AffaireDetail.jsx` → `RecordShell` → `ui/Tabs.jsx`) : il résolvait vers
// l'entrée de nav GLOBALE du module, qui mène à `/ao/toitures` — l'atelier de
// TOUTE la société, hors du contexte de l'affaire qu'on vient de créer.
import { test, expect } from '@playwright/test'
import {
  uniq, gotoAo, AO_ROUTES, ouvrirOngletAffaire, selectAoOutil, clickAoCanvas,
  waitAoVerdict,
} from './helpers'

// Même fixture PDF minimale (1 page, valide) que attachments.spec.js — aucun
// fichier binaire ajouté au dépôt.
const PDF_BYTES = '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'

test('AOF187: créer une affaire → importer un plan → calibrer → tracer → 3 obstacles → verdict', async ({ page }) => {
  await gotoAo(page, AO_ROUTES.affaires)

  const nomAffaire = uniq('AOF187 Affaire')
  await page.getByRole('button', { name: /\+ Nouvelle affaire/ }).click()
  await page.locator('#ao-affaire-nom').fill(nomAffaire)
  await page.getByRole('button', { name: 'Créer', exact: true }).click()

  // L'affaire fraîchement créée s'ouvre (fiche projet), puis on rejoint son
  // atelier toiture — la « porte d'entrée » n°1 du plan (plan fourni).
  await expect(page.getByText(nomAffaire)).toBeVisible()
  await ouvrirOngletAffaire(page, 'Toitures & relevés')

  // Porte n°1 : import d'un plan PDF/image calibré à 2 points.
  await page.getByRole('button', { name: /Importer un plan/ }).click()
  await page.locator('input[type="file"]').setInputFiles({
    name: `aof187-${Date.now()}.pdf`,
    mimeType: 'application/pdf',
    buffer: Buffer.from(PDF_BYTES),
  })

  // Calibrage à 2 points : deux clics sur le canvas puis la distance réelle.
  await selectAoOutil(page, 'calibrer')
  await clickAoCanvas(page, { x: 40, y: 40 })
  await clickAoCanvas(page, { x: 240, y: 40 })
  await page.locator('#ao-calibrage-distance').fill('10')
  await page.getByRole('button', { name: 'Valider le calibrage' }).click()

  // Traçage du contour (fermeture topo) : quelques points puis fermeture.
  await selectAoOutil(page, 'tracer')
  await clickAoCanvas(page, { x: 40, y: 40 })
  await clickAoCanvas(page, { x: 240, y: 40 })
  await clickAoCanvas(page, { x: 240, y: 200 })
  await clickAoCanvas(page, { x: 40, y: 200 })
  await clickAoCanvas(page, { x: 40, y: 40 }) // ferme le contour

  // Pose de 3 obstacles typés.
  await selectAoOutil(page, 'obstacle')
  await clickAoCanvas(page, { x: 80, y: 80 })
  await clickAoCanvas(page, { x: 140, y: 80 })
  await clickAoCanvas(page, { x: 200, y: 140 })
  await expect(page.locator('[data-ao-repere]')).toHaveCount(3)

  // Lancement du calepinage puis lecture du verdict — un recalcul serveur,
  // jamais une estimation côté client (asynchrone : `waitAoVerdict` attend le
  // vrai rendu, pas un délai arbitraire).
  await page.getByRole('button', { name: /Lancer le calepinage/ }).click()
  const etat = await waitAoVerdict(page)
  expect(['ok', 'avertissement', 'bloquant']).toContain(etat)
  await expect(page.locator('[data-ao-compte]')).not.toHaveText('')
})
