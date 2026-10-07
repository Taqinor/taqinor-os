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
import { API_DJANGO, lireJson, listeDe, uniq } from './helpers'

// CAD177 : la liste des tickets (TicketsPage) est servie sur '/sav' (features/sav/
// module.config.jsx) ; '/sav/tickets' n'a jamais été une route.
const ECRAN_TICKETS = '/sav'

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

// CAD177 : `seed_demo` ne pose AUCUN ticket « Planifié » (TCK-DEMO-0001..3 =
// nouveau / en cours / clôturé) — le spec dépendait d'une donnée que le seed
// n'a jamais promise (run nocturne 37573380397 : « trouvé : 0 »). Il crée donc
// ses propres 3 tickets, puis les planifie par l'action GARDÉE `planifier`
// (YDOCF1 — jamais un PATCH de `statut`, qui est en lecture seule).
async function creerTicketsPlanifies(page, nombre) {
  const clients = listeDe(await lireJson(
    await page.request.get(`${API_DJANGO}/crm/clients/`), 'liste des clients'))
  let clientId = clients[0]?.id
  if (!clientId) {
    clientId = (await lireJson(await page.request.post(`${API_DJANGO}/crm/clients/`, {
      data: { nom: uniq('Client NTUX37') },
    }), 'création du client')).id
  }
  for (let i = 0; i < nombre; i += 1) {
    const ticket = await lireJson(await page.request.post(`${API_DJANGO}/sav/tickets/`, {
      data: { client: clientId, description: uniq('NTUX37 ticket') },
    }), 'création du ticket')
    const res = await page.request.post(`${API_DJANGO}/sav/tickets/${ticket.id}/planifier/`)
    expect(res.status(), `planifier le ticket ${ticket.id}`).toBe(200)
  }
}

test('NTUX37: édition en masse du statut de 3 tickets, puis annulation dans la fenêtre de 10 s', async ({ page }) => {
  await creerTicketsPlanifies(page, 3)
  await page.goto(ECRAN_TICKETS)
  await expect(statutChip(page, 'Planifié')).toBeVisible()

  const avant = await chipCount(page, 'Planifié')
  expect(
    avant,
    `les 3 tickets « Planifié » créés par ce test doivent être comptés (trouvé : ${avant})`,
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
