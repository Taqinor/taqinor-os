// Rejeu en direct d'ACNC15 (groupe ACNC, parcours PF9) : ligne de facture jamais re-postée après une réponse perdue,
// onglet périmé ⇒ 409 `conflit_version` sans écriture, et le message « modifié par quelqu'un d'autre… Rechargez-le ».
// Fichier séparé de acnc.spec.js : au rejeu runner du 14/11/2026 (run 43540956204) l'écran affiche « code : conflit_version »
// au lieu de la phrase serveur (FactureForm.jsx, dans les Files d'ACNC15) — étape ROUGE, gardée telle quelle pour le
// rejeu qui suivra la correction ; même montage que acnc.spec.js (`_acnc.js`).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { lireJson } from '../helpers.js'
import {
  monter,
  API,
  T,
  marque,
  AUJ,
  note,
  bd,
  acteur,
  navigateur,
  onglet,
  couper,
  venteAcceptee,
  lireF,
  ligneFacture,
} from './_acnc.js'

const etape = groupe('ACNC', ['ACNC15'])
monter()
// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC15 — ligne de facture jamais re-postée après une réponse perdue ; onglet périmé ⇒ 409
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.15', ['ACNC15'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom } = await acteur(testInfo, 'acnc15', 'Directeur')
  const m = marque()
  const v = await venteAcceptee(r, r, m, { prixHt: '1000.00' })
  const f = await lireJson(await r.post(`${API}/ventes/factures/`, { ...T, data: { client: v.client, date_emission: AUJ() } }), 'brouillon')
  for (const des of ['Ligne A', 'Ligne B']) {
    await lireJson(await r.post(`${API}/ventes/factures-lignes/`, { ...T, data: { facture: f.id, produit: v.produitId, designation: des, quantite: '1', prix_unitaire: '1000.00', remise: '0', taux_tva: '20.00' } }), des)
  }
  const fr = await lireF(r, f.id)
  expect([fr.statut, fr.lignes.length], 'Given : brouillon à 2 lignes').toEqual(['brouillon', 2])
  const etat = () => bd(`f = Facture.objects.get(pk=${f.id})
sortie({'lignes': sorted(LigneFacture.objects.filter(facture=f).values_list('designation', flat=True)), 'note': f.note or '', 'version': f.lock_version})`)
  const ctx = await navigateur(page, testInfo, nom)
  const pA = await onglet(page, suivi, ctx)
  const pB = suivi.surveiller(await ctx.newPage())
  const editer = async (p) => {
    const ligne = await ligneFacture(p, fr.reference, f.id)
    await ligne.getByRole('button', { name: 'Éditer' }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: `Éditer — ${fr.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    return dlg
  }
  const dlgB = await editer(pB) // onglet B ouvert AVANT la modification de l'onglet A
  const dlgA = await editer(pA)
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
  // « Enregistrer » de nouveau (formulaire rouvert) : toujours 3 lignes.
  await pA.reload()
  const dlgA2 = await editer(pA)
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
})
