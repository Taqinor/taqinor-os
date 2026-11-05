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

const etape = groupe('ATOT', ['ATOT56'])
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
