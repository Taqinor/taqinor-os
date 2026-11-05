// Rejeu en direct des tâches ATOT56, ATOT59, ATOT60, ATOT62 (vérifie ATOT VER4, lot 7). Révision à la baisse par
// les VRAIES routes : V1 40 000 HT à 10 % + 60 000 HT à 20 % acceptée, facturée en entier et émise ; `reviser` ⇒ V2,
// `replace-lines` (10 % → 30 000), envoi, `accepter` ⇒ avoir de 11 000 TTC en attente de confirmation (VNT64).
// Société = celle de demo_admin (jamais un id en dur).
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ATOT', ['ATOT56', 'ATOT59', 'ATOT62', 'ATOT60'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

function sonde(chemin) {
  const r = spawnSync('python', ['scripts/sonde.py', chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000 })
  const lignes = (r.stdout || '').split('\n')
  const ligne = lignes.filter((l) => l.startsWith('{')).pop() || lignes.filter((l) => l.startsWith('observé : {')).map((l) => l.slice(10)).pop()
  expect(ligne, `sonde ${chemin} : ${(r.stdout || '').slice(-600)} ${(r.stderr || '').slice(-400)}`).toBeTruthy()
  expect(r.stdout, 'base inchangée après la sonde').toContain('base inchangée : oui')
  return JSON.parse(ligne)
}

async function session(testInfo, nom, roleNom) {
  const id = await py(`from apps.roles.models import Role
u = compte(${JSON.stringify(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(roleNom)}).pk, societe=${SOC})
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { ctx, id }
}

const ligne = (p, prix, tva, ordre) => ({ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: prix, remise: '0.00', taux_tva: tva, type_ligne: 'produit', ordre })

/** V2 à la baisse acceptée normalement sur une vente facturée en entier ; renvoie {v1, v2}. */
async function revisionAConfirmer(r, m) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ATOT4 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `atot4_${m}@example.invalid` } }), 'lead')
  const p10 = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Équipement à 10 ${m}`, prix_vente: '40000.00', prix_achat: '1.00' } }), 'produit 10 %')
  const p20 = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Installation à 20 ${m}`, prix_vente: '60000.00', prix_achat: '1.00' } }), 'produit 20 %')
  const v1 = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [ligne(p10, '40000.00', '10.00', 0), ligne(p20, '60000.00', '20.00', 1)] } }), 'V1')
  await lireJson(await r.post(`${API}/ventes/devis/${v1.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi V1')
  await lireJson(await r.post(`${API}/ventes/devis/${v1.id}/accepter/`, { ...T, data: { nom: 'Client ATOT4' } }), 'accepter V1')
  const fid = (await lireJson(await r.post(`${API}/ventes/devis/${v1.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture')).facture_id
  await r.post(`${API}/ventes/factures/${fid}/emettre/`, { ...T, data: {} })
  const f = await lireJson(await r.get(`${API}/ventes/factures/${fid}/`, T), 'facture relue')
  expect([f.statut, f.total_ttc], 'V1 facturée en entier et émise').toEqual(['emise', '116000.00'])
  const v2 = await lireJson(await r.post(`${API}/ventes/devis/${v1.id}/reviser/`, { ...T, data: {} }), 'reviser')
  await lireJson(await r.post(`${API}/ventes/devis/${v2.id}/replace-lines/`, { ...T, data: { lignes: [ligne(p10, '30000.00', '10.00', 0), ligne(p20, '60000.00', '20.00', 1)] } }), 'replace-lines V2')
  await lireJson(await r.post(`${API}/ventes/devis/${v2.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi V2')
  await lireJson(await r.post(`${API}/ventes/devis/${v2.id}/accepter/`, { ...T, data: { nom: 'Client ATOT4' } }), 'accepter V2')
  return { v1, v2, lead }
}
const avoirsDe = (lead) => py(`from apps.facturation.models import Avoir
sortie([[a.type, str(a.montant_ht), str(a.montant_tva), str(a.montant_ttc), str(a.taux_tva)] for a in Avoir.objects.filter(company_id=${SOC}, facture__devis__lead_id=${lead}).order_by('id')])`)

etape('V4.56', ['ATOT56'], async () => {
  const s = sonde('ATOT/C-ATOT-VER4-010')
  expect(s.repro, 'sonde : aucune base créditée au-delà de la facture à ce taux').toBe(false)
  const paniers10 = s.avoirs.map((a) => a.paniers.filter((p) => p[0] === '10.00').map((p) => [p[1], p[2]])).flat()
  expect(paniers10, `deux avoirs 8 000 / 800 puis 2 000 / 200 à 10 % (${JSON.stringify(s.avoirs).slice(0, 600)})`).toEqual([['8000.00', '800.00'], ['2000.00', '200.00']])
  expect(new Set(s.avoirs.map((a) => a.facture)).size, 'sur deux tranches distinctes').toBe(2)
  for (const a of s.avoirs) for (const p of a.paniers) expect(Number(p[1]), 'aucune base négative').toBeGreaterThanOrEqual(0)
})

etape('V4.59', ['ATOT59'], async ({ page, testInfo }) => {
  const r = page.request
  const m = marque()
  const { v2, lead } = await revisionAConfirmer(r, m)
  expect(await avoirsDe(lead.id), 'aucun avoir avant confirmation').toEqual([])
  const vente = (await lireJson(await r.get(`${API}/ventes/devis/${v2.id}/`, T), 'détail V2')).vente
  expect(vente?.peut?.confirmer_avoir_revision, `peut.confirmer_avoir_revision (${JSON.stringify(vente?.peut)})`).toBe(true)
  expect(vente.raison_bloquee, 'raison_bloquee nomme le montant').toContain('11000.00 MAD TTC')
  // Rôle sans palier vente : drapeau faux, phrase absente.
  const vu = await session(testInfo, `atot59viewer_${m}`, 'Viewer')
  const lu = await vu.ctx.get(`${API}/ventes/devis/${v2.id}/`, T)
  if (lu.status() === 200) {
    const v = (await lu.json()).vente
    expect([v?.peut?.confirmer_avoir_revision ?? false, String(v?.raison_bloquee || '').includes('11000.00')], 'Viewer : faux, phrase absente').toEqual([false, false])
  } else {
    expect([403, 404], `Viewer ne lit pas la V2 (${lu.status()})`).toContain(lu.status())
  }
  await vu.ctx.dispose()
  // Avoir confirmé : drapeau faux, phrase absente (recalculé au GET).
  await lireJson(await r.post(`${API}/ventes/devis/${v2.id}/confirmer-avoir-revision/`, { ...T, data: {} }), 'confirmation')
  const apres = (await lireJson(await r.get(`${API}/ventes/devis/${v2.id}/`, T), 'détail V2 relu')).vente
  expect([apres.peut?.confirmer_avoir_revision, String(apres.raison_bloquee || '').includes('11000.00 MAD TTC')], 'après confirmation : faux, phrase absente').toEqual([false, false])
})

etape('V4.62', ['ATOT62'], async ({ page, testInfo }) => {
  const r = page.request
  const m = marque()
  const { v2, lead } = await revisionAConfirmer(r, m)
  const url = `${API}/ventes/devis/${v2.id}/confirmer-avoir-revision/`
  // Rôle normal (sans palier vente) : 403, rien d'écrit.
  const normal = await session(testInfo, `atot62norm_${m}`, 'Utilisateur')
  const x = await normal.ctx.post(url, { ...T, data: {} })
  expect(x.status(), `rôle normal : ${(await x.text()).slice(0, 200)}`).toBe(403)
  expect(await avoirsDe(lead.id), 'rien d\'écrit').toEqual([])
  await normal.ctx.dispose()
  // Responsable (demo_admin) : 200, un avoir CORRECTION 10 000 HT / 1 000 TVA à 10 %.
  const ok = await r.post(url, { ...T, data: {} })
  const corps = await ok.json()
  expect(ok.status(), JSON.stringify(corps).slice(0, 300)).toBe(200)
  expect(corps.avoirs?.map((a) => a.montant_ttc), 'avoir de 11 000 TTC').toEqual(['11000.00'])
  const avoirs = await avoirsDe(lead.id)
  expect(avoirs.map(([type, ht, tva, , taux]) => [type, ht, tva, Number(taux)]), 'un avoir CORRECTION 10 000 / 1 000 à 10 %').toEqual([['correction', '10000.00', '1000.00', 10]])
  // Second POST : 409 aucun_avoir_a_confirmer, rien d'écrit ; relu : un seul avoir.
  const encore = await r.post(url, { ...T, data: {} })
  expect([encore.status(), (await encore.json()).code], 'second appel').toEqual([409, 'aucun_avoir_a_confirmer'])
  expect((await avoirsDe(lead.id)).length, 'relu : un seul avoir').toBe(1)
})

etape('V4.60', ['ATOT60'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const { v2, lead } = await revisionAConfirmer(r, m)
  await page.goto(`/ventes/devis?q=${encodeURIComponent(v2.reference)}`)
  const puce = page.getByRole('button', { name: new RegExp(`^Vente de ${v2.reference.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`) })
  await expect(puce, 'puce de vente de la V2').toBeVisible({ timeout: 60_000 })
  await puce.click()
  const panneau = page.getByTestId('panneau-vente').filter({ hasText: '11000.00' })
  await expect(panneau, 'raison affichée avec le montant serveur').toContainText('11000.00 MAD TTC', { timeout: 30_000 })
  const bouton = panneau.getByRole('button', { name: "Confirmer l'avoir" })
  await expect(bouton, 'bouton « Confirmer l\'avoir »').toBeVisible()
  const appels = []
  page.on('request', (q) => { if (/confirmer-avoir-revision/.test(q.url())) appels.push(q.method()) })
  const [rep] = await Promise.all([
    page.waitForResponse((x) => /confirmer-avoir-revision/.test(x.url())),
    bouton.click(),
  ])
  expect(rep.status(), 'POST confirmer-avoir-revision').toBe(200)
  // Relecture de la vente : le bouton disparaît (drapeau recalculé faux).
  await expect(page.getByRole('button', { name: "Confirmer l'avoir" }), 'bouton retiré après relecture').toHaveCount(0, { timeout: 30_000 })
  expect(appels, 'appelé une seule fois').toEqual(['POST'])
  expect((await avoirsDe(lead.id)).length, 'un avoir émis').toBe(1)
  // Persistance : rechargement ⇒ aucun bouton.
  await page.reload()
  const puce2 = page.getByRole('button', { name: new RegExp(`^Vente de ${v2.reference.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`) })
  await expect(puce2).toBeVisible({ timeout: 60_000 })
  await puce2.click()
  await expect(page.getByTestId('panneau-vente').first()).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('button', { name: "Confirmer l'avoir" }), 'après rechargement : aucun bouton').toHaveCount(0)
  suivi.verifie(5)
})
