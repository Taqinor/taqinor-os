// AARG — 2e spec d'acceptation en direct : le rejeu PA4 (AARG45, AARG50 nominal) et la porte du portail admin (AARG8). Les
// étapes négatives d'AARG50 sont celles d'`aarg.spec.js`, rejouées vertes le 03/11/2026 (enregistrement 2026-11-03-369cf21d8).
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, connexionApi, assurerSessionPage } from '../helpers.js'

const etape = groupe('AARG', ['AARG8', 'AARG45', 'AARG50'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const python = (args) => spawnSync('python', args, { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })

etape('PA4.nominal', ['AARG50'], async () => {
  const s = python(['scripts/sonde.py', 'AARG/parcours-PA4'])
  expect(s.stdout, 'nominal : aucun écart du montant').toContain('"repro": false')
})

async function devisEnvoye(r) {
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AARG ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur AARG ${m}`, prix_vente: '1000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  return d
}

etape('PA4.rejeu', ['AARG45'], async ({ page }) => {
  const d = await devisEnvoye(page.request)
  const dry = python(['scripts/rejouer_parcours.py', 'PA4', '--enregistrement', String(d.id), '--dry-run', '--sans-enregistrement'])
  expect(dry.stdout + dry.stderr, 'programme : modèles de la table').toMatch(/ventes\.Devis|modeles/)
  expect(dry.stdout + dry.stderr, 'pas de bruit kb/contrats dans les modèles comptés').not.toMatch(/"modeles"[^\]]*kb\./)
  const reel = python(['scripts/rejouer_parcours.py', 'PA4', '--enregistrement', String(d.id), '--sans-enregistrement'])
  const sortie = `${reel.stdout}\n${reel.stderr}`
  expect(sortie, 'le rejeu ne meurt pas sur kb/contrats').not.toMatch(/doesn't have a '(kbarticle|contrat)' model[\s\S]*ÉCHEC : sonde/)
  test.info().annotations.push({ type: 'rejeu PA4', description: sortie.slice(-800) })
  expect(sortie, `rejeu rendu : ${sortie.slice(-600)}`).toMatch(/PA4-0\d|étape/i)
})

etape('P.rapprocher', ['AARG8'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const d = await devisEnvoye(r)
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AARG8' } }), 'accepter')
  const ac = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'acompte', emettre: true } }), 'facture émise')
  const intent = await py(`from apps.portail.models import PaiementFacturePortail as P
from apps.ventes.models import Facture
f = Facture.objects.get(pk=${ac.facture.id})
p = P.objects.create(company=f.company, facture=f, montant=100, statut='initie')
sortie(p.pk)`)
  const session = async (nom, role) => {
    await py(`compte(${JSON.stringify(nom)}, role=${role}); sortie(1)`)
    const c = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
    await connexionApi(c, { username: nom, password: MDP_ESSAI })
    return c
  }
  const m = marque()
  const url = `${API}/portail/paiements-facture-portail/${intent}/rapprocher/`
  const tech = await session(`aarg8t_${m}`, 6)
  const rh = await session(`aarg8r_${m}`, 71)
  expect((await tech.post(url, { ...T, data: {} })).status(), 'Technicien : 403').toBe(403)
  expect((await rh.post(url, { ...T, data: {} })).status(), 'Admin RH : 403').toBe(403)
  const nb = () => py(`from apps.ventes.models import Paiement
from apps.portail.models import PaiementFacturePortail as P
sortie({'n': Paiement.objects.filter(facture_id=${ac.facture.id}).count(), 's': P.objects.get(pk=${intent}).statut})`)
  const avant = await nb()
  expect(avant, 'rien écrit').toEqual({ n: 0, s: 'initie' })
  const ok = await r.post(url, { ...T, data: {} })
  expect(ok.status(), `Directeur : 200 (${(await ok.text()).slice(0, 160)})`).toBe(200)
  const apres = await nb()
  expect(apres, 'intention payée, un Paiement').toEqual({ n: 1, s: 'paye' })
  await page.goto('/parametres/portail/paiements').catch(() => undefined)
  suivi.verifie(5)
})
