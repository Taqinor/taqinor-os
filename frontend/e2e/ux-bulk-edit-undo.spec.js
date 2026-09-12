// NTUX37 — édition en masse avec annulation (NTUX5/NTUX6) : sélectionner
// plusieurs tickets, éditer leur statut en lot avec aperçu AVANT/APRÈS
// (BulkEditDialog), confirmer, puis cliquer « Annuler » sur le toast dans la
// fenêtre de 10 s et vérifier que les lignes sont revenues à leur statut
// d'origine.
//
// ÉCRAN : `/sav/tickets` (TicketsPage.jsx), pas `/ventes/devis`. Vérifié dans
// le code (`grep bulkEdit= frontend/src/pages`) avant d'écrire ce spec :
// TicketsPage est le SEUL écran qui câble `<DataTable bulkEdit={…}>` (NTUX5,
// aperçu avant/après) aujourd'hui — DevisList n'utilise sa sélection que pour
// la génération PDF par lot, jamais l'édition en masse générique.
//
// L'ANNULATION (NTUX6) n'était PAS câblée sur cet écran avant ce lot :
// `notifyBulkUpdateWithUndo` (le toast « Annuler ») existait déjà
// (ui/datatable/notifyBulkUpdateWithUndo.js) mais n'avait ZÉRO consommateur
// en production — un test contre une fonctionnalité non branchée aurait été
// un faux contrat. Câblée dans TicketsPage.jsx dans CE MÊME lot
// (`ticketsBulkEdit.onDone` + `revertBulkStatut`), sur le champ Statut, en
// s'appuyant sur la machine d'états gardée serveur
// (apps/sav/machine_etats.py) qui autorise TOUJOURS un recul d'une étape —
// donc PLANIFIE -> EN_COURS (avant) puis EN_COURS -> PLANIFIE (annulation)
// sont l'un et l'autre des transitions valides, jamais un contournement de
// la garde métier.
//
// VÉRIFICATION : plutôt que de traquer 3 références individuelles, le test
// s'appuie sur les PASTILLES DE COMPTE PAR STATUT déjà affichées par l'écran
// (L306/L314, `counts.map` — un chip par statut, ex. « Planifié 7 ») : filtrer
// sur « Planifié », noter son compte N, éditer 3 lignes vers « En cours »
// (le compte Planifié doit tomber à N-3), annuler (il doit revenir à N).
import { test, expect } from '@playwright/test'

const ECRAN_TICKETS = '/sav/tickets'

function statutChip(page, libelle) {
  // Chip = <button><span class="dot"/>{label}<span class="count">{n}</span></button>
  // — cible le bouton PAR SON TEXTE (libellé + un nombre), jamais un index.
  return page.locator('button', { hasText: libelle }).filter({ hasText: /\d+/ })
}

async function chipCount(page, libelle) {
  const texte = await statutChip(page, libelle).innerText()
  const m = texte.match(/(\d+)\s*$/)
  return m ? Number(m[1]) : NaN
}

test('NTUX37: édition en masse du statut de 3 tickets, puis annulation dans la fenêtre de 10 s', async ({ page }) => {
  await page.goto(ECRAN_TICKETS)
  await expect(statutChip(page, 'Planifié')).toBeVisible()

  const avant = await chipCount(page, 'Planifié')
  expect(
    avant,
    `la société de démonstration doit avoir au moins 3 tickets « Planifié » pour ce test (trouvé : ${avant})`,
  ).toBeGreaterThanOrEqual(3)

  // ── 1) Filtre sur « Planifié » (chip cliquable, L306) ───────────────────
  await statutChip(page, 'Planifié').click()
  await expect(page.getByRole('checkbox', { name: 'Sélectionner la ligne 1' })).toBeVisible()

  // ── 2) Sélectionne les 3 premières lignes visibles ──────────────────────
  await page.getByRole('checkbox', { name: 'Sélectionner la ligne 1' }).click()
  await page.getByRole('checkbox', { name: 'Sélectionner la ligne 2' }).click()
  await page.getByRole('checkbox', { name: 'Sélectionner la ligne 3' }).click()
  await expect(page.getByRole('region', { name: '3 ligne(s) sélectionnée(s)' })).toBeVisible()

  // ── 3) Ouvre l'action « Statut → En cours » (inline ou dans « Plus ») ───
  const actionLabel = 'Statut → En cours'
  const inlineAction = page.getByRole('button', { name: actionLabel })
  if (await inlineAction.count() === 0) {
    await page.getByRole('button', { name: 'Plus' }).click()
    await page.getByRole('menuitem', { name: actionLabel }).click()
  } else {
    await inlineAction.click()
  }

  // ── 4) Aperçu AVANT/APRÈS (BulkEditDialog, NTUX5) puis confirme ─────────
  await expect(page.getByRole('heading', { name: /Modifier Statut — 3 lignes/ })).toBeVisible()
  await expect(page.getAllByTestId('bed-preview-row')).toHaveCount(3)
  await page.getByRole('button', { name: 'Confirmer' }).click()

  // Les 3 lignes éditées ne sont plus "Planifié" : le compte du chip tombe à
  // N-3 (toujours filtré sur Planifié, la table se vide d'autant).
  await expect
    .poll(() => chipCount(page, 'Planifié'), { timeout: 10_000 })
    .toBe(avant - 3)

  // ── 5) Annule DANS la fenêtre de 10 s (toast sonner, bouton « Annuler ») ─
  const toaster = page.locator('[data-sonner-toaster]')
  await expect(toaster.getByText(/mise.*à jour/)).toBeVisible()
  await toaster.getByRole('button', { name: 'Annuler' }).click()
  await expect(page.getByText('Édition en masse annulée.')).toBeVisible()

  // ── 6) Les 3 tickets sont revenus à « Planifié » : le compte remonte à N ─
  await expect.poll(() => chipCount(page, 'Planifié'), { timeout: 10_000 }).toBe(avant)
})
