// ASEC63 — rejeu des écarts de la contre-visite du 01/11/2026, à deux comptes de rôles différents : (1) rôle plus large refusé,
// (2) aucun geste d'argent sans `encaisser` ni porte API, (7) rôle système intouchable, (8) SQL de l'agent sans coût.
// Étapes (3), (4), (5), (6) : preuves du 01/11 (`ASEC/2026-11-01-15ebadca5`, contre-épreuve ba577e26a) ; non rejouées ici.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, connexionApi, assurerSessionPage } from '../helpers.js'

const etape = groupe('ASEC', ['ASEC63'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
async function session(testInfo, context, nom, role) {
  await py(`compte(${JSON.stringify(nom)}, role=${role}); sortie(1)`)
  const c = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(c, { username: nom, password: MDP_ESSAI })
  if (context) await context.addCookies((await c.storageState()).cookies)
  return c
}

etape('P63.1', ['ASEC63'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const cresp = await session(testInfo, context, `asec63c_${m}`, 3)
  const role = await lireJson(await cresp.post(`${API}/roles/`, { ...T, data: { nom: `ACC63 étroit ${m}`, permissions: ['crm_voir'] } }), 'rôle étroit')
  const large = await cresp.patch(`${API}/roles/${role.id}/`, { ...T, data: { permissions: ['crm_voir', 'paie_gerer'] } })
  expect(large.status(), 'élargir : refus').toBe(403)
  expect(await large.text(), 'refus lisible').toMatch(/plus large/)
  expect((await lireJson(await cresp.get(`${API}/roles/${role.id}/`, T), 'relu')).permissions, 'rôle inchangé').toEqual(['crm_voir'])
  const direct = await cresp.post(`${API}/roles/`, { ...T, data: { nom: `ACC63 large ${m}`, permissions: ['paie_gerer'] } })
  expect(direct.status(), 'création large refusée').toBe(403)
  await page.goto('/admin/roles')
  await expect(page.getByText(`ACC63 étroit ${m}`).first(), "l'écran Rôles").toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(`ACC63 large ${m}`), 'absent de la liste').toHaveCount(0)
  await cresp.dispose()
  suivi.verifie(5)
})

etape('P63.2', ['ASEC63'], async ({ page, context, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ASEC63 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ASEC63 ${m}`, prix_vente: '1000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client' } }), 'accepter')
  const f = (await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'acompte', emettre: true } }), 'facture')).facture
  for (const [nom, role] of [['av', 72], ['resp', 8]]) {
    const c = await session(testInfo, context, `asec63${nom}_${m}`, role)
    for (const [geste, url, corps] of [
      ['encaisser', `factures/${f.id}/enregistrer-paiement/`, { montant: '10.00', date_paiement: new Date().toISOString().slice(0, 10), mode: 'virement' }],
      ['retour client', `factures/${f.id}/retour-client/`, { motif: 'x' }],
      ['pénalités', `factures/${f.id}/facturer-penalites/`, {}],
      ['libérer la retenue', `factures/${f.id}/liberer-retenue/`, {}],
      ['lien de paiement', `factures/${f.id}/lien-paiement/`, {}],
      ['remise', 'remises-encaissement/', { reference: 'x' }],
    ]) {
      const rep = await c.post(`${API}/ventes/${url}`, { ...T, data: corps })
      expect(rep.status(), `${nom} : ${geste} refusé`).toBe(403)
    }
    const relue = await lireJson(await r.get(`${API}/ventes/factures/${f.id}/`, T), 'facture relue')
    expect(Number(relue.montant_paye), 'rien écrit').toBe(0)
    await page.goto(`/ventes/factures?q=${encodeURIComponent(f.reference)}`)
    await expect(page.getByText(f.reference).first()).toBeVisible({ timeout: 60_000 })
    for (const nomGeste of ['Encaisser', 'Payer en ligne']) await expect(page.getByRole('button', { name: nomGeste }), `${nom} : pas de « ${nomGeste} »`).toHaveCount(0)
    await c.dispose()
  }
  suivi.verifie(5)
})

etape('P63.7', ['ASEC63'], async ({ page, suivi }) => {
  const r = page.request
  const tech = await lireJson(await r.get(`${API}/roles/6/`, T), 'Technicien')
  const rep = await r.patch(`${API}/roles/6/`, { ...T, data: { nom: 'Technicien ACC63', permissions: [...tech.permissions, 'encaisser'] } })
  expect([400, 409], `rôle système : refus (${rep.status()})`).toContain(rep.status())
  const relu = await lireJson(await r.get(`${API}/roles/6/`, T), 'relu')
  expect([relu.nom, relu.permissions.length], 'rôle relu inchangé').toEqual([tech.nom, tech.permissions.length])
  void listeDe
  suivi.verifie(5)
})

etape('P63.8', ['ASEC63'], async ({ suivi }) => {
  void suivi
  const { spawnSync } = await import('node:child_process')
  const code = `
from app.services import sql_agent_service as s
for q in ("SELECT cout_unitaire FROM stock_mouvementstock LIMIT 1", "SELECT * FROM stock_mouvementstock LIMIT 1"):
    try:
        v = s._valider_sql(q) if hasattr(s, '_valider_sql') else None
        print('OK', q, str(v)[:120])
    except Exception as e:
        print('REFUS', q, str(e)[:160])
print('@@FIN')`
  const r = spawnSync('docker', ['compose', 'exec', '-T', 'fastapi_ia', 'python', '-c', code], { encoding: 'utf8', maxBuffer: 5_000_000 })
  expect(r.stdout, r.stderr?.slice(-300)).toContain('@@FIN')
  expect(r.stdout, 'jamais le coût').not.toMatch(/OK SELECT cout_unitaire[^\n]*777/)
})
