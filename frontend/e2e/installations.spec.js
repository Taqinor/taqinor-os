// CHT28 — le module chantier a enfin ses tests de parcours : remplace
// l'unique `test.fixme` (jamais exécuté, cf. l'historique de ce fichier) par
// 3 specs stables et AUTONOMES — chaque test crée ses PROPRES données via
// l'API (`page.request`, patron comptes-justes.spec.js/receivables.spec.js),
// jamais une dépendance à un autre spec ni à un état de seed préalable
// (leçon leads.spec). Nettoyage systématique en `afterEach` : la suite roule
// sur une base `seed_demo` partagée.
//
// Sélecteurs : ce module n'expose PAS de `data-testid` dédiés (patron
// helpers.js — texte visible/rôles ARIA/hooks RÉELS déjà posés ailleurs,
// jamais un hook inventé). `ch6-blocked-reasons` (ChantierGateTimeline /
// CHT22) est le SEUL testid réel du module chantier, réutilisé tel quel.
import { test, expect } from '@playwright/test'
import { uniq } from './helpers'

const createdChantiers = []
const createdInterventions = []

test.afterEach(async ({ request }) => {
  // Nettoyage best-effort : chaque suppression est indépendante, une erreur
  // isolée ne doit pas empêcher de nettoyer le reste (patron comptes-justes).
  await Promise.all(createdInterventions.splice(0).map((id) => (
    request.delete(`/api/django/installations/interventions/${id}/`).catch(() => null)
  )))
  await Promise.all(createdChantiers.splice(0).map((id) => (
    request.delete(`/api/django/installations/chantiers/${id}/`).catch(() => null)
  )))
})

test('E-INSTALL-1: /chantiers?id= ouvre la fiche en Sheet', async ({ page }) => {
  const ville = uniq('CHT28Ville')
  const res = await page.request.post('/api/django/installations/chantiers/', {
    data: { site_ville: ville },
  })
  expect(res.ok()).toBeTruthy()
  const { id } = await res.json()
  createdChantiers.push(id)

  await page.goto(`/chantiers?id=${id}`)
  await expect(page.getByRole('dialog')).toBeVisible()
  // Preuve que la fiche OUVERTE est bien CELLE demandée (pas une autre) :
  // une valeur unique à ce chantier, saisie à la création.
  await expect(page.locator('#ch-ville')).toHaveValue(ville)
})

test("E-INSTALL-2: transition bloquée par un gate -> les raisons s'affichent", async ({ page }) => {
  // AUD326 — un chantier CLÔTURÉ ne peut reculer SANS motif explicite : gate
  // TOUJOURS actif (aucune configuration société requise), donc déterministe
  // et 100% autonome — contrairement aux gates CH1/CH2 qui dépendent d'étapes
  // configurées PAR SOCIÉTÉ (état partagé qu'un spec e2e ne doit jamais
  // muter). Cette 400 `{statut: [...]}` est exactement celle que CHT22 a
  // appris à rendre en liste à puces (ch6-blocked-reasons) côté Select
  // legacy, au lieu d'un message brut.
  const res = await page.request.post('/api/django/installations/chantiers/', {
    data: { statut: 'cloture' },
  })
  expect(res.ok()).toBeTruthy()
  const { id } = await res.json()
  createdChantiers.push(id)

  await page.goto(`/chantiers?id=${id}`)
  await expect(page.getByRole('dialog')).toBeVisible()

  // Le Select natif est un Radix Select réel ici (portail + pointer events —
  // le piège RTL n'existe pas sous Playwright, qui pilote un vrai navigateur) :
  // ouvrir le trigger puis choisir l'option, jamais un `selectOption` natif.
  await page.locator('#ch-statut').click()
  await page.getByRole('option', { name: 'Réceptionné' }).click()
  await page.getByRole('button', { name: 'Mettre à jour' }).click()

  const raisons = page.getByTestId('ch6-blocked-reasons')
  await expect(raisons).toBeVisible()
  await expect(raisons).toContainText('CLÔTURÉ')
})

test('E-INSTALL-3: /interventions?id= ouvre la fiche', async ({ page }) => {
  const chantierRes = await page.request.post('/api/django/installations/chantiers/', { data: {} })
  expect(chantierRes.ok()).toBeTruthy()
  const chantier = await chantierRes.json()
  createdChantiers.push(chantier.id)

  const intervRes = await page.request.post('/api/django/installations/interventions/', {
    data: { installation: chantier.id, type_intervention: 'controle' },
  })
  expect(intervRes.ok()).toBeTruthy()
  const interv = await intervRes.json()
  createdInterventions.push(interv.id)

  await page.goto(`/interventions?id=${interv.id}`)
  await expect(page.getByRole('dialog')).toBeVisible()
  // Le titre du Sheet est `{typeLabel} — {installation_reference|#id}` : on
  // vérifie le TYPE (unique à cette création, pas de collision de heading).
  await expect(page.getByRole('dialog')).toContainText('Contrôle')
})
