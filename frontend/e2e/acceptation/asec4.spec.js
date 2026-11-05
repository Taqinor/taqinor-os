// Rejeu en direct des tâches ASEC66-84 (vérifie ASEC VER4, lot 7) : chaque étape rejoue la sonde du constat quand
// elle existe (`scripts/sonde.py`, transaction annulée) ET joue le geste par l'API réelle sous de vrais comptes
// connectés : refus du rôle privé du code, passage inchangé des rôles légitimes. Société = celle de demo_admin
// (jamais un id en dur) ; rôles système relus par leur nom.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ASEC', ['ASEC66', 'ASEC67', 'ASEC68', 'ASEC69', 'ASEC70'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

/** Rejoue une sonde d'audit (transaction annulée) et renvoie son dict observé. */
function sonde(chemin) {
  const r = spawnSync('python', ['scripts/sonde.py', chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000 })
  const lignes = (r.stdout || '').split('\n')
  const ligne = lignes.filter((l) => l.startsWith('{')).pop() || lignes.filter((l) => l.startsWith('observé : {')).map((l) => l.slice(10)).pop()
  expect(ligne, `sonde ${chemin} : ${(r.stdout || '').slice(-600)} ${(r.stderr || '').slice(-400)}`).toBeTruthy()
  expect(r.stdout, 'base inchangée après la sonde').toContain('base inchangée : oui')
  return JSON.parse(ligne)
}

/** pk d'un rôle (système ou personnalisé) de la société de demo_admin ; `perms` crée/aligne un rôle personnalisé. */
async function role(nom, perms = null) {
  if (!perms) return py(`from apps.roles.models import Role
sortie(Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nom)}).pk)`)
  return py(`from apps.roles.models import Role
r, _ = Role.objects.get_or_create(company_id=${SOC}, nom=${JSON.stringify(nom)}, defaults=dict(permissions=[]))
r.permissions = ${JSON.stringify(perms)}; r.est_systeme = False; r.save(); sortie(r.pk)`)
}

/** Permissions d'un rôle système relu par son nom, moins `sans`. */
const permsSans = (nom, sans) => py(`from apps.roles.models import Role
sortie(sorted(set(Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nom)}).permissions) - set(${JSON.stringify(sans)})))`)

/** Compte d'essai de la société connecté par la vraie route `/token/` ; renvoie {ctx, id}. */
async function session(testInfo, nom, roleId) {
  const id = await py(`u = compte(${JSON.stringify(nom)}, role=${roleId}, societe=${SOC})
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { ctx, id }
}

const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64')

etape('V4.66', ['ASEC66'], async ({ testInfo }) => {
  const s = sonde('ASEC/C-ASEC-VER4-001')
  expect([s.repro, s.reinit[0], s.reinit[1]?.code, s.hash_change], 'sonde : refus role_plus_large, rien changé').toEqual([false, 403, 'role_plus_large', false])
  const m = marque()
  const tr = await session(testInfo, `asec66tr_${m}`, await role('Technicien responsable'))
  const cr = await session(testInfo, `asec66cr_${m}`, await role('Commercial responsable'))
  const co = await session(testInfo, `asec66co_${m}`, await role('Commercial'))
  const di = await session(testInfo, `asec66di_${m}`, await role('Directeur'))
  const etat = () => py(`u = U.objects.get(pk=${cr.id})
sortie([u.check_password(${JSON.stringify(MDP_ESSAI)}), u.email, u.is_active, bool(getattr(u, 'avatar_key', '') or getattr(u, 'avatar', ''))])`)
  const avant = await etat()
  // Les 4 portes : 403 role_plus_large.
  const portes = [
    await tr.ctx.post(`${API}/users/${cr.id}/reinitialiser-mot-de-passe/`, { ...T, data: { password: 'Qz7#wLp2!vR9-mK4@tH6' } }),
    await tr.ctx.patch(`${API}/users/${cr.id}/`, { ...T, data: { email: `pirate_${m}@example.invalid` } }),
    await tr.ctx.post(`${API}/users/${cr.id}/avatar/`, { ...T, multipart: { avatar: { name: 'a.png', mimeType: 'image/png', buffer: PNG } } }),
    await tr.ctx.delete(`${API}/users/${cr.id}/`, T),
  ]
  for (const [i, x] of portes.entries()) {
    const corps = await x.text()
    expect(x.status(), `porte ${i} : ${corps.slice(0, 200)}`).toBe(403)
    expect(corps, `porte ${i} : code`).toContain('role_plus_large')
  }
  expect(await etat(), 'cible relue : mot de passe, e-mail, actif, avatar inchangés').toEqual(avant)
  // Rôles légitimes inchangés : Commercial responsable → Commercial, Directeur → Commercial responsable, soi-même.
  const a = await cr.ctx.post(`${API}/users/${co.id}/reinitialiser-mot-de-passe/`, { ...T, data: { password: 'Nw4!kPz8#rT2-vQ6@mL9' } })
  expect(a.status(), `Commercial resp → Commercial : ${(await a.text()).slice(0, 200)}`).toBe(200)
  const b = await di.ctx.post(`${API}/users/${cr.id}/reinitialiser-mot-de-passe/`, { ...T, data: { password: 'Hj5@xRt7!pW3-zK8#nB2' } })
  expect(b.status(), `Directeur → Commercial resp : ${(await b.text()).slice(0, 200)}`).toBe(200)
  const c = await tr.ctx.patch(`${API}/users/${tr.id}/`, { ...T, data: { email: `asec66tr_${m}@accept.test` } })
  expect(c.status(), `soi-même : ${(await c.text()).slice(0, 200)}`).toBe(200)
  for (const x of [tr, cr, co, di]) await x.ctx.dispose()
})

/** Vente acceptée : lead + devis créés par `cree` (porté par lui), produit et acceptation par demo_admin. */
async function venteAcceptee(r, cree, m, prix = '1000.00', tva = '20.00', email = null) {
  const l = await lireJson(await cree.post(`${API}/crm/leads/`, { ...T, data: { nom: `ASEC4 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: email || `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ASEC4 ${m}`, prix_vente: prix, prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: tva, remise_globale: '0', lead: l.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: prix, remise: '0.00', taux_tva: tva, type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client' } }), 'accepter')
  return { devis: d, lead: l }
}
const nbFactures = () => py(`from apps.facturation.models import Facture
sortie(Facture.objects.filter(company_id=${SOC}).count())`)
const nbAvoirs = () => py(`from apps.facturation.models import Avoir
sortie(Avoir.objects.filter(company_id=${SOC}).count())`)

etape('V4.67', ['ASEC67'], async ({ page, testInfo }) => {
  const s = sonde('ASEC/C-ASEC-VER4-010')
  expect([s.repro, s.generer_facture, s.consolider, s.factures_d1.length, s.facture_consolidee.length], 'sonde : 403 aux deux portes, aucune facture').toEqual([false, 403, 403, 0, 0])
  const r = page.request
  const m = marque()
  // Rôle Commercial privé d'`encaisser`, connecté : 403 aux deux portes, factures de la société inchangées.
  const sans = await session(testInfo, `asec67sans_${m}`, await role('ASEC67 Commercial sans encaisser', await permsSans('Commercial', ['encaisser'])))
  const v1 = await venteAcceptee(r, sans.ctx, `${m}a`)
  const v2 = await venteAcceptee(r, sans.ctx, `${m}b`, '1000.00', '20.00', v1.lead.email)
  const avant = await nbFactures()
  const g = await sans.ctx.post(`${API}/ventes/devis/${v1.devis.id}/generer-facture/`, { ...T, data: {} })
  expect([g.status(), (await g.json()).detail], 'generer-facture sans encaisser').toEqual([403, "Émettre ou encaisser une facture exige le droit d'encaissement."])
  const c = await sans.ctx.post(`${API}/ventes/factures/consolider/`, { ...T, data: { devis_ids: [v1.devis.id, v2.devis.id] } })
  expect(c.status(), 'consolider sans encaisser').toBe(403)
  expect(await nbFactures(), 'aucune facture créée').toBe(avant)
  // Légitimes inchangés : Commercial du registre (porte `encaisser`) génère ; Directeur consolide.
  const com = await session(testInfo, `asec67com_${m}`, await role('Commercial'))
  const v3 = await venteAcceptee(r, com.ctx, `${m}c`)
  const g2 = await com.ctx.post(`${API}/ventes/devis/${v3.devis.id}/generer-facture/`, { ...T, data: {} })
  expect(g2.status(), `Commercial generer-facture : ${(await g2.text()).slice(0, 300)}`).toBe(201)
  const dir = await session(testInfo, `asec67dir_${m}`, await role('Directeur'))
  const w1 = await venteAcceptee(r, dir.ctx, `${m}d`)
  const w2 = await venteAcceptee(r, dir.ctx, `${m}e`, '1000.00', '20.00', w1.lead.email)
  const c2 = await dir.ctx.post(`${API}/ventes/factures/consolider/`, { ...T, data: { devis_ids: [w1.devis.id, w2.devis.id] } })
  expect(c2.status(), `Directeur consolider : ${(await c2.text()).slice(0, 300)}`).toBe(201)
  for (const x of [sans, com, dir]) await x.ctx.dispose()
})

etape('V4.68', ['ASEC68'], async ({ page, testInfo }) => {
  const s = sonde('ASEC/C-ASEC-VER4-011')
  expect([s.repro, s.temoin_creer_avoir, s.A_confirme, s.A_avoirs_crees], 'sonde : Admin Ventes 403, aucun avoir').toEqual([false, 403, 403, 0])
  const r = page.request
  const m = marque()
  const av = await session(testInfo, `asec68av_${m}`, await role('Admin Ventes'))
  const dir = await session(testInfo, `asec68dir_${m}`, await role('Directeur'))
  const v = await venteAcceptee(r, dir.ctx, m, '54500.00', '20.00')
  const d = v.devis
  const fid = (await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture')).facture_id
  await r.post(`${API}/ventes/factures/${fid}/emettre/`, { ...T, data: {} })
  expect((await lireJson(await r.get(`${API}/ventes/factures/${fid}/`, T), 'facture')).statut, 'facture émise').toBe('emise')
  const avant = await nbAvoirs()
  // Admin Ventes : aperçu 200 (lecture), appliquer + confirmer_avoir 403, ni V2 ni avoir.
  const ap = await av.ctx.post(`${API}/ventes/devis/${d.id}/prix-negocie/`, { ...T, data: { mode: 'apercu', prix_ttc: '49000.00' } })
  expect(ap.status(), `aperçu Admin Ventes : ${(await ap.text()).slice(0, 200)}`).toBe(200)
  const x = await av.ctx.post(`${API}/ventes/devis/${d.id}/prix-negocie/`, { ...T, data: { mode: 'appliquer', prix_ttc: '49000.00', confirmer_avoir: true } })
  expect([x.status(), (await x.json()).detail], 'appliquer + avoir sans encaisser').toEqual([403, "Émettre ou encaisser une facture exige le droit d'encaissement."])
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  expect([relu.statut, relu.version ?? 1], 'V1 active, version 1').toEqual(['accepte', 1])
  expect(await nbAvoirs(), 'aucun avoir créé').toBe(avant)
  // Directeur (porte `encaisser`) : inchangé — 201 et l'avoir émis.
  const ok = await dir.ctx.post(`${API}/ventes/devis/${d.id}/prix-negocie/`, { ...T, data: { mode: 'appliquer', prix_ttc: '49000.00', confirmer_avoir: true } })
  expect(ok.status(), `Directeur appliquer : ${(await ok.text()).slice(0, 300)}`).toBe(201)
  expect(await nbAvoirs(), 'un avoir émis par le Directeur').toBe(avant + 1)
  for (const y of [av, dir]) await y.ctx.dispose()
})

etape('V4.69', ['ASEC69'], async ({ testInfo }) => {
  const s = sonde('ASEC/C-ASEC-VER4-020')
  expect([s.repro, s.etapes.patch_demandeur[0], s.etapes.decisions_apres_patch, s.payload_final.montant], 'sonde : PATCH 409 après la 1re décision').toEqual([false, 409, 1, 100])
  const m = marque()
  const dem = await session(testInfo, `asec69dem_${m}`, await role('Utilisateur'))
  const r1 = await session(testInfo, `asec69r1_${m}`, await role('Responsable'))
  const req = await py(`from apps.automation.models import ApprovalRequest, ApprovalRequestType
t = ApprovalRequestType.objects.create(company_id=${SOC}, nom='ASEC69 double contrôle ${m}', min_approbations=2)
q = ApprovalRequest.objects.create(company_id=${SOC}, request_type=t, demandeur=U.objects.get(pk=${dem.id}), payload={'montant': 50})
sortie(q.pk)`)
  const B = `${API}/automation/approval-requests`
  // Avant toute décision : PATCH du demandeur 200 (inchangé).
  const p0 = await dem.ctx.patch(`${B}/${req}/`, { ...T, data: { payload: { montant: 100 } } })
  expect(p0.status(), `PATCH avant décision : ${(await p0.text()).slice(0, 300)}`).toBe(200)
  const a = await r1.ctx.post(`${B}/${req}/approve/`, { ...T, data: { note: 'ok pour 100' } })
  expect(a.status(), `approbation resp1 : ${(await a.text()).slice(0, 300)}`).toBe(200)
  const p1 = await dem.ctx.patch(`${B}/${req}/`, { ...T, data: { payload: { montant: 100000 } } })
  expect(p1.status(), `PATCH après 1re décision : ${(await p1.text()).slice(0, 300)}`).toBe(409)
  const relu = await py(`from apps.automation.models import ApprovalRequest
q = ApprovalRequest.objects.get(pk=${req})
sortie([q.payload.get('montant'), q.decisions.count(), q.status])`)
  expect(relu, 'montant 100, 1 décision, en attente').toEqual([100, 1, 'pending'])
  for (const x of [dem, r1]) await x.ctx.dispose()
})

etape('V4.70', ['ASEC70'], async ({ page, testInfo }) => {
  const s = sonde('ASEC/C-ASEC-VER4-040')
  expect([s.repro, s.sans_stock_export.produits_export_xlsx[0], s.sans_stock_export.mouvements_export_xlsx[0], s.avec_stock_export.produits_export_xlsx[0]], 'sonde : stock_voir seul 403, porteur 200').toEqual([false, 403, 403, 200])
  const r = page.request
  const m = marque()
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Câble ASEC70 ${m}`, prix_vente: '10.00', prix_achat: '1.00' } }), 'produit')
  const exporter = async (ctx) => [
    (await ctx.post(`${API}/stock/produits/export-xlsx/`, { ...T, data: { ids: [p.id] } })).status(),
    (await ctx.post(`${API}/stock/mouvements/export-xlsx/`, { ...T, data: {} })).status(),
  ]
  const cas = [
    ['ASEC70 stock_voir seul', ['stock_voir'], 403],
    ['Directeur', null, 200], ['Technicien responsable', null, 200],
    ['Commercial', null, 403], ['Commercial responsable', null, 403],
  ]
  for (const [i, [nom, perms, statut]] of cas.entries()) {
    const u = await session(testInfo, `asec70_${i}_${m}`, await role(nom, perms))
    const obtenu = await exporter(u.ctx)
    expect(obtenu.map((x) => (x === 202 ? 200 : x)), `${nom} : exports produits / mouvements`).toEqual([statut, statut])
    await u.ctx.dispose()
  }
})
