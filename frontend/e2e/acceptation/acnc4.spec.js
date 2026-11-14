// Preuve en direct ACNC65 (groupe ACNC, parcours PF9) : un 409 `conflit_version` remonte la phrase `detail`
// (« …modifié par quelqu'un d'autre… Rechargez-le… ») dans l'erreur générale du formulaire de facture, jamais un
// faux champ « code : conflit_version » — et, comme la clause le demande, le rejeu de l'étape PF9.15 d'acnc3.spec.js
// (ACNC15, restée rouge le 14/11 sur ce seul message), qui coche ACNC15 avec cette tâche. Même montage que
// acnc.spec.js / acnc3.spec.js (`_acnc.js` : comptes de rôles du registre, contextes connectés par /token/).
import { expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { lireJson } from '../helpers.js'
import {
  monter,
  API,
  T,
  marque,
  AUJ,
  bd,
  acteur,
  navigateur,
  onglet,
  couper,
  venteAcceptee,
  lireF,
  ligneFacture,
} from './_acnc.js'

const etape = groupe('ACNC', ['ACNC15', 'ACNC65'])
monter()

const MESSAGE = /Cet enregistrement a été modifié par quelqu.un d.autre depuis son ouverture\. Rechargez-le avant d.enregistrer\./

/** Brouillon de facture à 2 lignes (créé par demo_admin `r`). */
async function brouillon(r, m) {
  const v = await venteAcceptee(r, r, m, { prixHt: '1000.00' })
  const f = await lireJson(await r.post(`${API}/ventes/factures/`, { ...T, data: { client: v.client, date_emission: AUJ() } }), 'brouillon')
  for (const des of ['Ligne A', 'Ligne B']) {
    await lireJson(await r.post(`${API}/ventes/factures-lignes/`, { ...T, data: { facture: f.id, produit: v.produitId, designation: des, quantite: '1', prix_unitaire: '1000.00', remise: '0', taux_tva: '20.00' } }), des)
  }
  const fr = await lireF(r, f.id)
  expect([fr.statut, fr.lignes.length], 'Given : brouillon à 2 lignes').toEqual(['brouillon', 2])
  return { v, f, fr }
}
const editer = async (p, fr, id) => {
  const ligne = await ligneFacture(p, fr.reference, id)
  await ligne.getByRole('button', { name: 'Éditer' }).click()
  const dlg = p.getByRole('dialog').filter({ hasText: `Éditer — ${fr.reference}` })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  return dlg
}

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC65 — même brouillon dans deux onglets : B enregistre, A enregistre ⇒ 409, la phrase `detail`, sans « code : »
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.65', ['ACNC65'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom } = await acteur(testInfo, 'acnc65', 'Directeur')
  const m = marque()
  const { f, fr } = await brouillon(r, m)
  const etat = () => bd(`f = Facture.objects.get(pk=${f.id})
sortie({'note': f.note or '', 'version': f.lock_version})`)
  const ctx = await navigateur(page, testInfo, nom)
  const pA = await onglet(page, suivi, ctx)
  const pB = suivi.surveiller(await ctx.newPage())
  const dlgA = await editer(pA, fr, f.id) // onglet A ouvert AVANT l'enregistrement de B
  const dlgB = await editer(pB, fr, f.id)
  // B enregistre en premier.
  await dlgB.locator('#fc-note').fill(`note de l'onglet B ${m}`)
  await dlgB.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(dlgB, 'onglet B : enregistré').toBeHidden({ timeout: 60_000 })
  const apresB = await etat()
  expect(apresB.note, 'base : note de B').toBe(`note de l'onglet B ${m}`)
  // A (périmé) enregistre ensuite ⇒ bannière, puis forcé ⇒ 409 conflit_version, rien écrit.
  await dlgA.locator('#fc-note').fill(`note de l'onglet A ${m}`)
  await dlgA.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(dlgA.getByText(/pendant votre édition/), 'bannière d\'édition périmée').toBeVisible({ timeout: 30_000 })
  const rxF = new RegExp(`/ventes/factures/${f.id}/$`)
  suivi.attendre(rxF, 409)
  const [rep] = await Promise.all([pA.waitForResponse((x) => ['PUT', 'PATCH'].includes(x.request().method()) && rxF.test(new URL(x.url()).pathname), T),
    dlgA.getByRole('button', { name: 'Enregistrer quand même' }).click()])
  const corps = await rep.json()
  expect([rep.status(), corps.code], `onglet A : ${JSON.stringify(corps).slice(0, 200)}`).toEqual([409, 'conflit_version'])
  expect(corps.detail, 'corps servi : la phrase detail').toMatch(MESSAGE)
  await expect.poll(async () => (await dlgA.getByRole('alert').allInnerTexts()).join(' | '),
    { timeout: 30_000, message: 'bandeau de A : « …modifié par quelqu\'un d\'autre… Rechargez-le »' }).toMatch(MESSAGE)
  const bandeau = (await dlgA.getByRole('alert').allInnerTexts()).join(' | ')
  expect(bandeau, 'jamais « code : » au bandeau').not.toMatch(/code\s*:/i)
  expect(await dlgA.innerText(), 'jamais « conflit_version » à l\'écran').not.toContain('conflit_version')
  expect(await etat(), 'aucune écriture de l\'onglet A (note, version)').toEqual(apresB)
  // Persistance : l'onglet A (saisie non enregistrée : sa garde beforeunload est légitime) est refermé sans
  // décharger, un onglet neuf relit le brouillon ⇒ la note de B.
  await pA.close()
  const pA2 = suivi.surveiller(await ctx.newPage())
  const dlgA2 = await editer(pA2, fr, f.id)
  await expect(dlgA2.locator('#fc-note'), 'après rechargement : la note de B').toHaveValue(`note de l'onglet B ${m}`)
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC15 (rejeu de PF9.15 d'acnc3.spec.js) — ligne jamais re-postée après une réponse perdue ; onglet périmé ⇒ 409
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.15', ['ACNC15', 'ACNC65'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom } = await acteur(testInfo, 'acnc15', 'Directeur')
  const m = marque()
  const { v, f, fr } = await brouillon(r, m)
  const etat = () => bd(`f = Facture.objects.get(pk=${f.id})
sortie({'lignes': sorted(LigneFacture.objects.filter(facture=f).values_list('designation', flat=True)), 'note': f.note or '', 'version': f.lock_version})`)
  const ctx = await navigateur(page, testInfo, nom)
  const pA = await onglet(page, suivi, ctx)
  const pB = suivi.surveiller(await ctx.newPage())
  const dlgB = await editer(pB, fr, f.id) // onglet B ouvert AVANT la modification de l'onglet A
  const dlgA = await editer(pA, fr, f.id)
  await dlgA.getByRole('button', { name: 'Ajouter une ligne' }).click()
  const neuve = dlgA.locator('tr[data-line-key]').last()
  await neuve.getByRole('button', { name: /Produit/ }).click()
  await pA.getByPlaceholder('Chercher un produit… (Entrée = premier résultat)').fill(v.produitNom)
  await expect(pA.getByRole('option').filter({ hasText: v.produitNom }).first()).toBeVisible({ timeout: 30_000 })
  await pA.getByPlaceholder('Chercher un produit… (Entrée = premier résultat)').press('Enter')
  await neuve.getByPlaceholder('Désignation').fill('Ligne C')
  await neuve.locator('[data-role="line-qty"]').fill('1')
  // La création de la 3e ligne atteint le serveur, sa réponse est perdue (délai dépassé simulé).
  const rxL = /\/factures-lignes\/$/
  const envois = await couper(pA, rxL, suivi)
  await dlgA.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(dlgA, 'ligne perdue relue et rapprochée : enregistrement terminé').toBeHidden({ timeout: 60_000 })
  await pA.unroute(rxL)
  expect(envois.length, 'la ligne neuve n\'a été postée qu\'UNE fois').toBe(1)
  let e = await etat()
  expect(e.lignes, '3 lignes en base (pas 4)').toEqual(['Ligne A', 'Ligne B', 'Ligne C'])
  await pA.reload()
  const dlgA2 = await editer(pA, fr, f.id)
  await dlgA2.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(dlgA2).toBeHidden({ timeout: 60_000 })
  e = await etat()
  expect(e.lignes, 'ré-enregistré : toujours 3 lignes').toEqual(['Ligne A', 'Ligne B', 'Ligne C'])
  // Onglet B (périmé) : il modifie la note et enregistre ⇒ bannière, puis forcé ⇒ 409 conflit_version, rien écrit.
  await dlgB.locator('#fc-note').fill(`écrasement onglet périmé ${m}`)
  await dlgB.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(dlgB.getByText(/pendant votre édition/), 'bannière d\'édition périmée').toBeVisible({ timeout: 30_000 })
  const rxF = new RegExp(`/ventes/factures/${f.id}/$`)
  suivi.attendre(rxF, 409)
  const [rep] = await Promise.all([pB.waitForResponse((x) => ['PUT', 'PATCH'].includes(x.request().method()) && rxF.test(new URL(x.url()).pathname), T),
    dlgB.getByRole('button', { name: 'Enregistrer quand même' }).click()])
  const corps = await rep.json()
  expect([rep.status(), corps.code], `onglet périmé : ${JSON.stringify(corps).slice(0, 200)}`).toEqual([409, 'conflit_version'])
  const apres = await etat()
  expect(apres, 'aucune écriture de l\'onglet périmé (lignes, note, version)').toEqual(e)
  await expect.poll(async () => (await dlgB.getByRole('alert').allInnerTexts()).join(' | '), { timeout: 30_000, message: 'message « modifié par quelqu\'un d\'autre… Rechargez-le » affiché' }).toMatch(/modifié par quelqu.un d.autre/)
  expect((await dlgB.getByRole('alert').allInnerTexts()).join(' | '), 'jamais « code : » au bandeau').not.toMatch(/code\s*:/i)
})
