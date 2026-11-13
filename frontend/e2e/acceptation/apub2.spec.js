// Preuves en direct du groupe APUB, lot 2 (audit PF5 « accès publics et à lien », dossier
// docs/audits/2026-11-11-parcours-PF5.md) : APUB1, 3, 4, 5, 13, 14, 33, 46, 54, 55, 57, 71.
// Chaque étape joue le geste par la VRAIE route sous de vrais comptes connectés par /token/ (rôles LIVRÉS relus
// du registre `apps/roles/permissions_registre.py`), et l'écran quand la tâche en nomme un. Accès PUBLICS : le
// visiteur est un contexte de navigateur NEUF (aucun cookie) muni du vrai jeton, puis le cas refusé (jeton coupé,
// expiré, d'un autre seau). Données propres créées par l'API ou le shell Django, retirées en fin d'étape quand
// c'est possible ; persistance = relecture (écran rechargé, base relue) après le geste.
// Les sondes AST du dossier (C-APUB-001/003/010/037) ne se rejouent plus sur l'arbre corrigé (bouchons périmés :
// garde déplacée dans `list()`, helper absent du jeu extrait, `__mro_entries__`, module `_sonde_stock`) : elles ne
// sont PAS comptées comme preuve ; la preuve est le geste réel ci-dessous.
import { test, expect, request as pwRequest } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, PNG_1PX } from '../helpers.js'

const etape = groupe('APUB', ['APUB1', 'APUB3', 'APUB4', 'APUB5', 'APUB13', 'APUB14', 'APUB33', 'APUB46', 'APUB54', 'APUB55', 'APUB57', 'APUB71'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

// Contextes de navigateur ouverts par une étape : gardés ouverts jusqu'à la capture de fin d'étape, fermés après.
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await c.close().catch(() => undefined) })

/** pk du rôle LIVRÉ `nom` de la société `soc` (créé depuis le registre vivant s'il manque). */
const roleLivre = (nom, soc = SOC) => py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, CANONICAL_PORTAIL_ROLES
perms = dict(list(CANONICAL_SYSTEM_ROLES) + list(CANONICAL_PORTAIL_ROLES))[${JSON.stringify(nom)}]
r, _ = Role.objects.get_or_create(company_id=${soc}, nom=${JSON.stringify(nom)}, defaults=dict(permissions=list(perms), est_systeme=True))
sortie(r.pk)`)

/** Compte d'essai connecté par la vraie route `/token/` (contexte API) ; renvoie {ctx, id, nom}. */
async function session(testInfo, nom, roleId, soc = SOC) {
  const id = await py(`u = compte(${JSON.stringify(nom)}, role=${roleId}, societe=${soc})
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { ctx, id, nom }
}

/** Navigateur connecté sous `nom` (contexte neuf, service worker bloqué), page observée par les oracles. */
async function navigateur(context, suivi, testInfo, nom) {
  const ctx = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', viewport: { width: 1440, height: 900 } })
  ouverts.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  if (nom) await connexionApi(p.request, { username: nom, password: MDP_ESSAI })
  return p
}

/** Visiteur SANS session : contexte de navigateur neuf, aucun cookie. */
async function visiteur(context, suivi, testInfo) {
  const ctx = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', storageState: { cookies: [], origins: [] } })
  ouverts.push(ctx)
  return suivi.surveiller(await ctx.newPage())
}

// ── APUB1 / APUB3 : export de réversibilité ────────────────────────────────────────────────────────
/** Run « prêt » de la société démo : vrai ZIP posé dans le seau de réversibilité (MinIO du job), son lien
 *  signé, plus un second lien du seau `erp-uploads` (export de stock). */
const exportPret = (m) => py(`from core.export_registry import ExportReversibiliteRun
from core import signed_download
from core.tasks import REVERSIBILITE_BUCKET
from core.backup import _minio_client
from authentication.models import Company
co = Company.objects.get(pk=${SOC})
c = _minio_client()
try:
    c.head_bucket(Bucket=REVERSIBILITE_BUCKET)
except Exception:
    c.create_bucket(Bucket=REVERSIBILITE_BUCKET)
cle = 'apub/${m}/export.zip'
c.put_object(Bucket=REVERSIBILITE_BUCKET, Key=cle, Body=b'PK\\x03\\x04apub-${m}')
lien = signed_download.creer_lien(co, REVERSIBILITE_BUCKET, cle, taille_octets=13)
run = ExportReversibiliteRun.objects.create(company=co, statut=ExportReversibiliteRun.Statut.PRET, token=lien.token, fichier_key=cle, taille_octets=13, expire_le=lien.expire_le)
autre = signed_download.creer_lien(co, 'erp-uploads', 'exports/${m}/stock.xlsx')
sortie({'run': run.pk, 'tok': lien.token, 'autre': autre.token})`)
const TELECHARGER = `${API}/core/export-reversibilite/telecharger`

etape('PF5.1-APUB1', ['APUB1'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const e = await exportPret(m)
  // Historique : Commercial et Commercial responsable 403 sans jeton ; Directeur 200 avec le jeton.
  const comptes = {}
  for (const [nom, cle, attendu] of [['Commercial', 'co', 403], ['Commercial responsable', 'cr', 403], ['Directeur', 'di', 200]]) {
    const s = await session(testInfo, `apub1${cle}_${m}`, await roleLivre(nom))
    comptes[cle] = s
    const r = await s.ctx.get(`${API}/core/export-reversibilite/historique/`, T)
    const corps = await r.text()
    expect(r.status(), `${nom} : historique → ${corps.slice(0, 200)}`).toBe(attendu)
    if (attendu === 403) expect(corps, `${nom} : aucun jeton servi`).not.toContain(e.tok)
    else expect(JSON.parse(corps).find((x) => x.id === e.run)?.token, 'Directeur : jeton du run prêt').toBe(e.tok)
  }
  // Lien public, visiteur sans session : ZIP du seau de réversibilité servi ; jeton d'un autre seau 404 ; inconnu 404.
  const anonyme = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const zip = await anonyme.get(`${TELECHARGER}/${e.tok}/`, T)
  expect([zip.status(), zip.headers()['content-type']], 'jeton de réversibilité : ZIP servi').toEqual([200, 'application/zip'])
  expect((await zip.body()).subarray(0, 2).toString(), 'octets du ZIP posé').toBe('PK')
  expect((await anonyme.get(`${TELECHARGER}/${e.autre}/`, T)).status(), 'jeton du seau erp-uploads : 404').toBe(404)
  expect((await anonyme.get(`${TELECHARGER}/inconnu-apub1-${m}/`, T)).status(), 'jeton inconnu : 404').toBe(404)
  await anonyme.dispose()
  // Écran : Commercial responsable — URL refusée (/403), menu sans l'entrée ; Directeur (témoin) : l'entrée existe.
  const entree = 'a[href="/parametres/export-reversibilite"]'
  const pd = await navigateur(context, suivi, testInfo, comptes.di.nom)
  await pd.goto('/parametres')
  await expect.poll(() => pd.locator(entree).count(), { timeout: 60_000, message: 'Directeur : entrée « Export de réversibilité » au menu' }).toBeGreaterThan(0)
  const pr = await navigateur(context, suivi, testInfo, comptes.cr.nom)
  await pr.goto('/parametres/export-reversibilite')
  await expect(pr, 'Commercial responsable : URL refusée').toHaveURL(/\/403$/, { timeout: 60_000 })
  await pr.goto('/parametres')
  await expect(pr.getByRole('heading').first(), 'Paramètres ouverts').toBeVisible({ timeout: 60_000 })
  await pr.waitForLoadState('networkidle')
  expect(await pr.locator(entree).count(), 'Commercial responsable : entrée absente du menu').toBe(0)
  for (const s of Object.values(comptes)) await s.ctx.dispose()
  await page.close()
})

etape('PF5.2-APUB3', ['APUB3'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const e = await exportPret(m)
  const di = await session(testInfo, `apub3di_${m}`, await roleLivre('Directeur'))
  const cr = await session(testInfo, `apub3cr_${m}`, await roleLivre('Commercial responsable'))
  // Refus : le Commercial responsable ne coupe rien (403, lien toujours servi).
  const refus = await cr.ctx.post(`${API}/core/export-reversibilite/${e.run}/couper-lien/`, { ...T, data: {} })
  expect(refus.status(), 'Commercial responsable : couper-lien 403').toBe(403)
  const p = await navigateur(context, suivi, testInfo, di.nom)
  const appels = []
  p.on('request', (q) => { if (/\/couper-lien\/$/.test(q.url())) appels.push(q.url()) })
  await p.goto('/parametres/export-reversibilite')
  const lignes = p.locator('ul.divide-y > li')
  await expect(p.locator(`a[href*="${e.tok}"]`), 'ligne prête avec « Télécharger »').toBeVisible({ timeout: 60_000 })
  const idx = await lignes.evaluateAll((els, tok) => els.findIndex((x) => x.querySelector(`a[href*="${tok}"]`)), e.tok)
  const ligne = lignes.nth(idx)
  const dlg = p.getByRole('alertdialog').or(p.getByRole('dialog'))
  // « Annuler » : aucun appel, la ligne reste prête.
  await ligne.getByRole('button', { name: 'Couper le lien' }).click()
  await expect(dlg, 'confirmation maison').toContainText('Couper le lien de cet export ?')
  await dlg.getByRole('button', { name: 'Annuler' }).click()
  await expect(dlg).toBeHidden()
  expect(appels, 'Annuler : aucun appel').toEqual([])
  await expect(ligne.getByText('Télécharger')).toBeVisible()
  // Confirmer : un seul appel avec l'id du run, ligne « Expiré » sans « Télécharger ».
  await ligne.getByRole('button', { name: 'Couper le lien' }).click()
  const [rep] = await Promise.all([
    p.waitForResponse((x) => x.url().includes(`/export-reversibilite/${e.run}/couper-lien/`) && x.request().method() === 'POST'),
    dlg.getByRole('button', { name: 'Couper le lien' }).click(),
  ])
  expect(rep.status(), 'couper-lien 200').toBe(200)
  expect(appels.length, 'un seul appel').toBe(1)
  await expect(ligne, 'ligne « Expiré »').toContainText('Expiré', { timeout: 30_000 })
  await expect(ligne.getByText('Télécharger')).toHaveCount(0)
  await expect(p.locator(`a[href*="${e.tok}"]`)).toHaveCount(0)
  // Persistance : rechargé, la ligne reste « Expiré » ; base : lien inactif, run expiré.
  await p.reload()
  await expect(lignes.nth(idx), 'rechargé : toujours « Expiré »').toContainText('Expiré', { timeout: 60_000 })
  await expect(p.locator(`a[href*="${e.tok}"]`)).toHaveCount(0)
  expect(await py(`from core.export_registry import ExportReversibiliteRun
from core.signed_download import SignedDownload
sortie([ExportReversibiliteRun.objects.get(pk=${e.run}).statut, SignedDownload.objects.get(token=${JSON.stringify(e.tok)}).actif])`), 'base relue').toEqual(['expire', false])
  // L'ancien lien, ouvert par un visiteur sans session : 404.
  const anonyme = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  expect((await anonyme.get(`${TELECHARGER}/${e.tok}/`, T)).status(), 'ancien lien coupé : 404').toBe(404)
  await anonyme.dispose()
  for (const s of [di, cr]) await s.ctx.dispose()
  await page.close()
})

// ── APUB5 : signalement public par QR plafonné à 3 / 24 h par équipement ───────────────────────────
etape('PF5.3-APUB5', ['APUB5'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const eq = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
cl = Client.objects.create(company_id=${SOC}, nom='QR APUB5 ${m}', prenom='Acceptation')
inst = Installation.objects.create(company_id=${SOC}, reference='CHT-APUB5-${m}', client=cl)
pr = Produit.objects.create(company_id=${SOC}, nom='Onduleur APUB5 ${m}', sku='OND-APUB5-${m}', prix_achat=0, prix_vente=100)
e = Equipement.objects.create(company_id=${SOC}, produit=pr, installation=inst)
sortie({'id': e.pk, 'token': e.ensure_public_token(), 'client': cl.pk, 'inst': inst.pk, 'produit': pr.pk})`)
  const etat = () => py(`from apps.sav.models import Ticket
from apps.records.models import Attachment
sortie([Ticket.objects.filter(equipement_id=${eq.id}).count(), Attachment.objects.filter(company_id=${SOC}).count()])`)
  const p = await visiteur(context, suivi, testInfo)
  const refs = []
  let pieces = null
  for (let i = 0; i < 4; i += 1) {
    await p.goto(`/e/${eq.token}`)
    await p.locator('#es-description').fill(`panne p${i} ${m}`)
    if (i === 3) {
      pieces = (await etat())[1]
      await p.locator('#es-photo').setInputFiles({ name: 'p.png', mimeType: 'image/png', buffer: PNG_1PX })
    }
    const [r] = await Promise.all([
      p.waitForResponse((x) => x.url().includes(`/public/sav/equipement/${eq.token}/signaler/`) && x.request().method() === 'POST'),
      p.getByRole('button', { name: 'Envoyer le signalement' }).click(),
    ])
    const corps = await r.json()
    expect(r.status(), `envoi ${i + 1} : ${JSON.stringify(corps).slice(0, 200)}`).toBe(i < 3 ? 201 : 200)
    refs.push(corps.reference)
    if (i < 3) await expect(p.locator('p[role=status]'), `envoi ${i + 1} : référence affichée`).toContainText(`référence ${corps.reference}`)
  }
  expect(refs[3], '4e envoi : référence du 3e').toBe(refs[2])
  await expect(p.locator('p[role=status]'), 'écran du 4e : même référence').toContainText(`Signalement déjà enregistré : ${refs[2]}`)
  const [tickets, pj] = await etat()
  expect(tickets, 'relu : 3 tickets pour l\'équipement').toBe(3)
  expect(pj, 'aucune photo stockée au 4e').toBe(pieces)
  // Cas refusé : jeton inconnu → message « lien invalide ».
  suivi.attendre(/\/public\/sav\/equipement\/inconnu/, 404)
  const p2 = await visiteur(context, suivi, testInfo)
  await p2.goto(`/e/inconnu-apub5-${m}`)
  await p2.locator('#es-description').fill('panne')
  await p2.getByRole('button', { name: 'Envoyer le signalement' }).click()
  await expect(p2.locator('p[role=alert]'), 'jeton inconnu : lien invalide').toContainText('invalide', { timeout: 30_000 })
  await page.close()
})

// ── APUB4 : révocation d'une revue d'accès sous la garde de rang ───────────────────────────────────
etape('PF5.4-APUB4', ['APUB4'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  // (a) Société ISOLÉE (seuls ses comptes comptent pour « dernier propriétaire ») : fondateur protégé,
  // second Directeur, Commercial, rôles du registre ; tout par la vraie route sous le second Directeur.
  const co = await py(`from authentication.models import Company
from authentication.role_tiers import CODE_RANG_CIBLE, MESSAGES_REFUS_GESTION
c = Company.objects.create(nom='APUB4 ${m}', slug='apub4-${m}')
sortie({'id': c.pk, 'rang': MESSAGES_REFUS_GESTION[CODE_RANG_CIBLE]})`)
  const rDir = await roleLivre('Directeur', co.id)
  const rCom = await roleLivre('Commercial', co.id)
  const fondateur = await session(testInfo, `apub4f_${m}`, rDir, co.id)
  await py(`U.objects.filter(pk=${fondateur.id}).update(is_protected=True)
sortie(1)`)
  const d2 = await session(testInfo, `apub4d2_${m}`, rDir, co.id)
  const com = await session(testInfo, `apub4c_${m}`, rCom, co.id)
  const camp = await lireJson(await d2.ctx.post(`${API}/accessreview/campaigns/`, { ...T, data: { nom: `Revue APUB4 ${m}`, perimetre: 'all', statut: 'ouverte' } }), 'campagne')
  const items = (await lireJson(await d2.ctx.get(`${API}/accessreview/campaigns/${camp.id}/`, T), 'campagne relue')).items
  const item = (uid) => items.find((x) => x.user === uid)
  const attester = (uid) => d2.ctx.post(`${API}/accessreview/campaigns/${camp.id}/attester/`, { ...T, data: { item: item(uid).id, decision: 'revoque' } })
  const etat = () => py(`from apps.accessreview.models import AccessReviewItem
sortie({str(u.pk): [u.role.nom if u.role else None, AccessReviewItem.objects.get(campagne_id=${camp.id}, user=u).decision] for u in U.objects.filter(pk__in=[${fondateur.id}, ${d2.id}, ${com.id}])})`)
  const r1 = await attester(fondateur.id)
  expect([r1.status(), (await r1.json()).detail], 'fondateur protégé : 403 rang_cible').toEqual([403, co.rang])
  await py(`U.objects.filter(pk=${fondateur.id}).update(is_active=False)
sortie(1)`)
  const r2 = await attester(d2.id)
  const c2 = await r2.json()
  expect(r2.status(), `dernier propriétaire : ${JSON.stringify(c2).slice(0, 200)}`).toBe(403)
  expect(c2.detail, 'texte « dernier propriétaire »').toContain('dernier propriétaire')
  const apres = await etat()
  expect([apres[fondateur.id], apres[d2.id]], 'relu : items en attente, rôles inchangés').toEqual([['Directeur', 'en_attente'], ['Directeur', 'en_attente']])
  const r3 = await attester(com.id)
  const c3 = await r3.json()
  expect([r3.status(), c3.user_nom], 'Commercial : 200, user_nom').toEqual([200, com.nom])
  expect((await etat())[com.id], 'Commercial relu : rôle « Utilisateur », item révoqué').toEqual(['Utilisateur', 'revoque'])
  for (const s of [fondateur, d2, com]) await s.ctx.dispose()
  // (b) Écran /admin/gouvernance-acces de la société démo, sous un Directeur : la confirmation NOMME le compte et
  // le rôle ; Annuler n'écrit rien ; le protégé est refusé (message du serveur) ; rechargé, l'état tient.
  const dir = await session(testInfo, `apub4dir_${m}`, await roleLivre('Directeur'))
  const prot = await session(testInfo, `apub4prot_${m}`, await roleLivre('Directeur'))
  await py(`U.objects.filter(pk=${prot.id}).update(is_protected=True)
sortie(1)`)
  const vend = await session(testInfo, `apub4vend_${m}`, await roleLivre('Commercial'))
  const p = await navigateur(context, suivi, testInfo, dir.nom)
  const ATTESTER = /\/accessreview\/campaigns\/\d+\/attester\/$/
  suivi.attendre(ATTESTER, 403)
  const attests = []
  p.on('request', (q) => { if (ATTESTER.test(q.url())) attests.push(q.url()) })
  await p.goto('/admin/gouvernance-acces')
  const nomCamp = `Revue écran APUB4 ${m}`
  await p.getByLabel('Nom de la campagne').fill(nomCamp)
  const [cree] = await Promise.all([
    p.waitForResponse((x) => /\/accessreview\/campaigns\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'POST'),
    p.getByRole('button', { name: 'Lancer une campagne' }).click(),
  ])
  expect(cree.status(), 'campagne lancée').toBe(201)
  const ouvrir = async () => {
    await p.getByRole('button', { name: new RegExp(nomCamp) }).click()
    const rang = (s) => p.locator('div.py-1', { has: p.locator('span', { hasText: `${s.nom} (Compte #${s.id})` }) })
    return { v: rang(vend), pr: rang(prot) }
  }
  let rangs = await ouvrir()
  await expect(rangs.v, 'item du Commercial listé').toBeVisible({ timeout: 30_000 })
  const dlg = p.getByRole('alertdialog').or(p.getByRole('dialog'))
  await rangs.v.getByRole('button', { name: 'Révoquer' }).click()
  await expect(dlg, 'confirmation nommant compte et rôle').toContainText(`${vend.nom} (Compte #${vend.id}) perd le rôle « Commercial »`)
  await dlg.getByRole('button', { name: 'Annuler' }).click()
  await expect(dlg).toBeHidden()
  expect(attests, 'Annuler : aucun appel').toEqual([])
  await rangs.v.getByRole('button', { name: 'Révoquer' }).click()
  const [ok] = await Promise.all([
    p.waitForResponse((x) => ATTESTER.test(x.url()) && x.request().method() === 'POST'),
    dlg.getByRole('button', { name: 'Révoquer l’accès' }).click(),
  ])
  expect(ok.status(), 'révocation du Commercial : 200').toBe(200)
  await expect(rangs.v, 'item du Commercial révoqué').toContainText('revoque', { timeout: 30_000 })
  await rangs.pr.getByRole('button', { name: 'Révoquer' }).click()
  await expect(dlg).toContainText(`${prot.nom} (Compte #${prot.id}) perd le rôle « Directeur »`)
  const [ko] = await Promise.all([
    p.waitForResponse((x) => ATTESTER.test(x.url()) && x.request().method() === 'POST'),
    dlg.getByRole('button', { name: 'Révoquer l’accès' }).click(),
  ])
  expect(ko.status(), 'compte protégé : 403').toBe(403)
  await expect(p.getByText(co.rang).first(), 'message du serveur affiché').toBeVisible({ timeout: 30_000 })
  // Persistance : rechargé, le Commercial reste révoqué, le protégé en attente ; base relue.
  await p.reload()
  rangs = await ouvrir()
  await expect(rangs.v).toContainText('revoque', { timeout: 30_000 })
  await expect(rangs.pr).toContainText('en_attente')
  expect(await py(`sortie([U.objects.get(pk=${vend.id}).role.nom, U.objects.get(pk=${prot.id}).role.nom])`), 'rôles relus').toEqual(['Utilisateur', 'Directeur'])
  await py(`U.objects.filter(pk=${prot.id}).update(is_protected=False)
sortie(1)`)
  for (const s of [dir, prot, vend]) await s.ctx.dispose()
  await page.close()
})

// ── APUB13 / APUB14 : tiers, tableaux et requêtes sauvegardées ─────────────────────────────────────
/** Jeu lisible par Viewer ET Utilisateur (même prédicat que `run_query`) + son premier champ. */
const jeuLisible = (ids) => py(`from core import data_explorer
from core.data_explorer import exiger_lecture_dataset
lecteurs = [U.objects.get(pk=i) for i in ${JSON.stringify(ids)}]
def lisible(n):
    try:
        for u in lecteurs:
            exiger_lecture_dataset(n, u)
        return True
    except Exception:
        return False
d = next(x for x in data_explorer.list_datasets() if lisible(x['name']))
sortie({'name': d['name'], 'champ': d['fields'][0]})`)

etape('PF5.5-APUB13', ['APUB13'], async ({ testInfo }) => {
  const m = marque()
  const di = await session(testInfo, `apub13di_${m}`, await roleLivre('Directeur'))
  const vi = await session(testInfo, `apub13vi_${m}`, await roleLivre('Viewer'))
  const ut = await session(testInfo, `apub13ut_${m}`, await roleLivre('Utilisateur'))
  const jeu = await jeuLisible([vi.id, ut.id])
  const tiers = await lireJson(await di.ctx.post(`${API}/tiers/tiers/`, { ...T, data: { nom: `Partenaire APUB13 ${m}`, is_partenaire: true } }), 'tiers')
  const tab = await lireJson(await di.ctx.post(`${API}/core/dashboards/`, { ...T, data: { titre: `Tableau APUB13 ${m}`, partage: true } }), 'tableau')
  const req = await lireJson(await di.ctx.post(`${API}/core/saved-queries/`, { ...T, data: { titre: `Requête APUB13 ${m}`, dataset: jeu.name, spec: { select: [jeu.champ] }, partage: true } }), 'requête')
  const pirate = `Pirate APUB13 ${m}`
  for (const s of [vi, ut]) {
    const codes = [
      (await s.ctx.post(`${API}/tiers/tiers/`, { ...T, data: { nom: pirate } })).status(),
      (await s.ctx.patch(`${API}/tiers/tiers/${tiers.id}/`, { ...T, data: { nom: pirate } })).status(),
      (await s.ctx.delete(`${API}/tiers/tiers/${tiers.id}/`, T)).status(),
      (await s.ctx.post(`${API}/core/dashboards/`, { ...T, data: { titre: pirate } })).status(),
      (await s.ctx.patch(`${API}/core/dashboards/${tab.id}/`, { ...T, data: { titre: pirate } })).status(),
      (await s.ctx.delete(`${API}/core/dashboards/${tab.id}/`, T)).status(),
      (await s.ctx.post(`${API}/core/saved-queries/`, { ...T, data: { titre: pirate, dataset: jeu.name } })).status(),
      (await s.ctx.patch(`${API}/core/saved-queries/${req.id}/`, { ...T, data: { titre: pirate } })).status(),
      (await s.ctx.delete(`${API}/core/saved-queries/${req.id}/`, T)).status(),
    ]
    expect(codes, `${s.nom} : 9 écritures refusées`).toEqual(Array(9).fill(403))
    const run = await s.ctx.post(`${API}/core/saved-queries/${req.id}/run/`, { ...T, data: {} })
    expect(run.status(), `${s.nom} : run/ ${(await run.text()).slice(0, 200)}`).toBe(200)
  }
  // Persistance : les trois objets relus inchangés, aucun « Pirate » en base.
  expect([
    (await lireJson(await di.ctx.get(`${API}/tiers/tiers/${tiers.id}/`, T), 'tiers relu')).nom,
    (await lireJson(await di.ctx.get(`${API}/core/dashboards/${tab.id}/`, T), 'tableau relu')).titre,
    (await lireJson(await di.ctx.get(`${API}/core/saved-queries/${req.id}/`, T), 'requête relue')).titre,
  ], 'relus inchangés').toEqual([`Partenaire APUB13 ${m}`, `Tableau APUB13 ${m}`, `Requête APUB13 ${m}`])
  expect(await py(`from apps.tiers.models import Tiers
from core.models import Dashboard, SavedQuery
p = ${JSON.stringify(pirate)}
sortie([Tiers.objects.filter(nom=p).count(), Dashboard.objects.filter(titre=p).count(), SavedQuery.objects.filter(titre=p).count()])`), 'aucun objet « Pirate »').toEqual([0, 0, 0])
  // Le Commercial (rôle qui écrit) crée un de chaque : 201.
  const co = await session(testInfo, `apub13co_${m}`, await roleLivre('Commercial'))
  expect([
    (await co.ctx.post(`${API}/tiers/tiers/`, { ...T, data: { nom: `Tiers Commercial APUB13 ${m}`, is_partenaire: true } })).status(),
    (await co.ctx.post(`${API}/core/dashboards/`, { ...T, data: { titre: `Tableau Commercial APUB13 ${m}` } })).status(),
    (await co.ctx.post(`${API}/core/saved-queries/`, { ...T, data: { titre: `Requête Commercial APUB13 ${m}`, dataset: jeu.name } })).status(),
  ], 'Commercial : 201 ×3').toEqual([201, 201, 201])
  for (const s of [di, vi, ut, co]) await s.ctx.dispose()
})

etape('PF5.6-APUB14', ['APUB14'], async ({ testInfo }) => {
  const m = marque()
  const a = await session(testInfo, `apub14a_${m}`, await roleLivre('Directeur'))
  const b = await session(testInfo, `apub14b_${m}`, await roleLivre('Commercial'))
  const c = await session(testInfo, `apub14c_${m}`, await roleLivre('Directeur'))
  const jeu = await jeuLisible([a.id])
  const tab = await lireJson(await a.ctx.post(`${API}/core/dashboards/`, { ...T, data: { titre: `De A APUB14 ${m}`, partage: true } }), 'tableau de A')
  const req = await lireJson(await a.ctx.post(`${API}/core/saved-queries/`, { ...T, data: { titre: `Requête de A APUB14 ${m}`, dataset: jeu.name, spec: { select: [jeu.champ] }, partage: true } }), 'requête de A')
  const soc = await py(`from core.models import Dashboard
sortie(Dashboard.objects.create(company_id=${SOC}, owner=None, titre='Société APUB14 ${m}', partage=True).pk)`)
  const D = `${API}/core/dashboards`
  const Q = `${API}/core/saved-queries`
  const refus = async (r, quoi) => {
    const corps = await r.text()
    expect(r.status(), `${quoi} : ${corps.slice(0, 200)}`).toBe(403)
    return corps
  }
  expect(await refus(await b.ctx.patch(`${D}/${tab.id}/`, { ...T, data: { partage: false } }), 'B dé-partage le tableau de A'), 'message du serveur').toContain('vos propres tableaux')
  await refus(await b.ctx.delete(`${D}/${tab.id}/`, T), 'B supprime le tableau de A')
  await refus(await b.ctx.patch(`${Q}/${req.id}/`, { ...T, data: { partage: false } }), 'B dé-partage la requête de A')
  await refus(await b.ctx.delete(`${Q}/${req.id}/`, T), 'B supprime la requête de A')
  await refus(await c.ctx.patch(`${D}/${tab.id}/`, { ...T, data: { titre: 'Pris' } }), 'C (Directeur) modifie le tableau de A')
  await refus(await b.ctx.patch(`${D}/${soc}/`, { ...T, data: { titre: 'S2' } }), 'B modifie le tableau société')
  expect((await c.ctx.patch(`${D}/${soc}/`, { ...T, data: { titre: `Société APUB14 ${m} v2` } })).status(), 'C (palier administrateur) : tableau société 200').toBe(200)
  // Persistance : les objets de A relus partagés et présents ; A garde ses gestes.
  expect(await py(`from core.models import Dashboard, SavedQuery
sortie([list(Dashboard.objects.filter(pk=${tab.id}).values_list('partage', 'titre')), list(SavedQuery.objects.filter(pk=${req.id}).values_list('partage', 'titre'))])`), 'relus').toEqual([[[true, `De A APUB14 ${m}`]], [[true, `Requête de A APUB14 ${m}`]]])
  expect((await a.ctx.patch(`${D}/${tab.id}/`, { ...T, data: { titre: `De A APUB14 ${m} v2` } })).status(), 'A modifie son tableau').toBe(200)
  expect((await a.ctx.delete(`${Q}/${req.id}/`, T)).status(), 'A supprime sa requête').toBe(204)
  expect((await a.ctx.delete(`${D}/${tab.id}/`, T)).status(), 'A supprime son tableau').toBe(204)
  await py(`from core.models import Dashboard
Dashboard.objects.filter(pk=${soc}).delete()
sortie(1)`)
  for (const s of [a, b, c]) await s.ctx.dispose()
})

// ── APUB33 : page « Payer » d'un lien fermé, ouverte par un visiteur sans compte ──────────────────
etape('PF5.7-APUB33', ['APUB33'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const nomClient = `Atlas Agro APUB33 ${m}`
  const liens = await py(`from decimal import Decimal
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, PaymentLink
from apps.ventes.domain.encaissements import create_payment_link
cl = Client.objects.create(company_id=${SOC}, nom=${JSON.stringify(nomClient)}, prenom='', email='apub33-${m}@example.invalid')
pr = Produit.objects.create(company_id=${SOC}, nom='Onduleur APUB33 ${m}', sku='APUB33-${m}', prix_vente=Decimal('1000'), quantite_stock=10)
def lien(suffixe):
    f = Facture.objects.create(company_id=${SOC}, reference='FAC-APUB33-${m}-' + suffixe, client=cl, statut='emise', taux_tva=Decimal('20.00'))
    LigneFacture.objects.create(facture=f, produit=pr, designation='Onduleur', quantite=Decimal('1'), prix_unitaire=Decimal('1000'), remise=Decimal('0'), taux_tva=Decimal('20.00'))
    return create_payment_link(facture=f)
ouvert, annule, expire = lien('O'), lien('A'), lien('E')
PaymentLink.objects.filter(pk=annule.pk).update(statut='annule')
PaymentLink.objects.filter(pk=expire.pk).update(expires_at=timezone.now() - datetime.timedelta(days=1))
sortie({'ouvert': ouvert.token, 'annule': annule.token, 'expire': expire.token})`)
  const contrat = JSON.parse(readFileSync(join(RACINE, 'backend/django_core/apps/facturation/contract_samples/paiement_public.json'), 'utf8'))
  const anonyme = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const pageApi = async (tok) => lireJson(await anonyme.get(`${API}/public/pay/${tok}/`, T), `page ${tok}`)
  const ouvert = await pageApi(liens.ouvert)
  expect([ouvert.client_name, ouvert.montant_initial !== '0.00'], 'lien en attente : nom et montant gardés').toEqual([nomClient, true])
  for (const [tok, cle, attendu] of [[liens.annule, 'statut', 'annule'], [liens.expire, 'expire', true]]) {
    const x = await pageApi(tok)
    expect(x[cle], `${cle}`).toBe(attendu)
    expect(Object.keys(x).sort(), 'clés du contrat toutes présentes').toEqual(Object.keys(contrat.exemple_ferme).sort())
    expect([x.client_name, x.montant_initial, x.rib], `lien fermé (${cle}) : ni nom, ni montant, ni RIB`).toEqual(['', '0.00', null])
  }
  await anonyme.dispose()
  // Écran /payer/<jeton> du visiteur sans compte.
  const p = await visiteur(context, suivi, testInfo)
  await p.goto(`/payer/${liens.ouvert}`)
  await expect(p.getByText(nomClient).first(), 'lien ouvert : nom du client (témoin)').toBeVisible({ timeout: 60_000 })
  await p.goto(`/payer/${liens.expire}`)
  await expect(p.getByText('Lien expiré'), 'lien expiré').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText(nomClient)).toHaveCount(0)
  await p.goto(`/payer/${liens.annule}`)
  await expect(p.getByText('Facture annulée'), 'lien annulé : « Facture annulée »').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText(nomClient), 'sans nom de client').toHaveCount(0)
  await expect(p.getByTestId('rib')).toHaveCount(0)
  await page.close()
})

// ── APUB46 / APUB71 : portail fournisseur (lien et compte) ─────────────────────────────────────────
/** Fournisseur actif de la société démo + son compte portail (rôle « Portail fournisseur » du registre, mot de
 *  passe connu, déjà changé) + un BCF « envoyé » acheté par `acheteur`. */
const fournisseurPortail = (m, tag, acheteurId) => py(`from decimal import Decimal
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_PORTAIL_ROLES
from apps.stock.models import Fournisseur, Produit, BonCommandeFournisseur
from apps.stock.models_portail_fournisseur import CompteFournisseurPortail
perms = dict(CANONICAL_PORTAIL_ROLES)['Portail fournisseur']
role, _ = Role.objects.get_or_create(company_id=${SOC}, nom='Portail fournisseur', defaults=dict(permissions=list(perms), est_systeme=True))
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ${tag} ${m}', email='${tag.toLowerCase()}-${m}@example.invalid')
u = compte('${tag.toLowerCase()}f_${m}', role=role.pk, societe=${SOC})
u.portee = U.PORTEE_PORTAIL_FOURNISSEUR; u.portail_fournisseur_id = f.pk; u.save()
CompteFournisseurPortail.objects.create(company_id=${SOC}, fournisseur=f, utilisateur=u)
pr = Produit.objects.create(company_id=${SOC}, nom='Onduleur ${tag} ${m}', sku='OND-${tag}-${m}', prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))
bc = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference='BCF-${tag}-${m}', fournisseur=f, statut=BonCommandeFournisseur.Statut.ENVOYE, created_by=U.objects.get(pk=${acheteurId}))
bc.lignes.create(produit=pr, quantite=2, prix_achat_unitaire=Decimal('1200'))
sortie({'f': f.pk, 'u': u.username, 'bc': bc.pk, 'ref': bc.reference})`)

etape('PF5.8-APUB46', ['APUB46'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const acheteur = await session(testInfo, `apub46ach_${m}`, await roleLivre('Directeur'))
  const fp = await fournisseurPortail(m, 'APUB46', acheteur.id)
  const token = await py(`from apps.stock.models import Fournisseur
from apps.stock.services import generer_token_portail_fournisseur
f = Fournisseur.objects.get(pk=${fp.f})
sortie(generer_token_portail_fournisseur(f.company, f, U.objects.get(pk=${acheteur.id})).token)`)
  const compteurs = () => py(`from django.contrib.contenttypes.models import ContentType
from apps.notifications.models import Notification
from apps.records.models import Comment
from apps.stock.models import BonCommandeFournisseur
ct = ContentType.objects.get_for_model(BonCommandeFournisseur)
bc = BonCommandeFournisseur.objects.get(pk=${fp.bc})
sortie({'notif': Notification.objects.filter(recipient_id=${acheteur.id}, title='Confirmation fournisseur').count(), 'chatter': Comment.objects.filter(content_type=ct, object_id=${fp.bc}).count(), 'date': str(bc.date_confirmee_fournisseur), 'num': bc.numero_confirmation_fournisseur})`)
  const avant = await compteurs()
  // Porte à JETON : le fournisseur, sans compte ni session, ouvre son lien et clique deux fois « Confirmer ».
  const p = await visiteur(context, suivi, testInfo)
  await p.goto(`/fournisseur/lien/${token}`)
  const ligne = p.locator('li').filter({ has: p.locator('strong', { hasText: fp.ref }) })
  await expect(ligne, 'BCF listé au portail').toBeVisible({ timeout: 60_000 })
  const confirmer = async () => {
    const [r] = await Promise.all([
      p.waitForResponse((x) => x.url().includes(`/portail-fournisseur/${token}/bcf/${fp.bc}/confirmer/`) && x.request().method() === 'POST'),
      ligne.getByRole('button', { name: 'Confirmer la commande' }).click(),
    ])
    expect(r.status(), `confirmation : ${(await r.text()).slice(0, 200)}`).toBe(200)
    await p.waitForLoadState('networkidle')
  }
  await ligne.getByLabel('Date de livraison confirmée').fill('2026-12-01')
  await ligne.getByLabel('N° de confirmation').fill('C-1')
  await confirmer()
  const un = await compteurs()
  expect([un.notif - avant.notif, un.chatter - avant.chatter, un.date, un.num], '1re confirmation : 1 notification, 1 commentaire').toEqual([1, 1, '2026-12-01', 'C-1'])
  await expect(ligne.getByLabel('Date de livraison confirmée'), 'formulaire toujours rempli').toHaveValue('2026-12-01')
  await confirmer()
  expect(await compteurs(), 'même confirmation rejouée : rien de plus').toEqual(un)
  // Porte à COMPTE, même (date, numéro) : 200 sans écriture ni notification.
  const fo = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(fo, { username: fp.u, password: MDP_ESSAI })
  const rc = await fo.post(`${API}/portail/mes-bons-commande/${fp.bc}/confirmer/`, { ...T, data: { date_confirmee: '2026-12-01', numero_confirmation: 'C-1' } })
  expect(rc.status(), `porte à compte : ${(await rc.text()).slice(0, 200)}`).toBe(200)
  expect(await compteurs(), 'porte à compte identique : rien de plus').toEqual(un)
  await fo.dispose()
  // Date différente : enregistrée et notifiée.
  await ligne.getByLabel('Date de livraison confirmée').fill('2026-12-05')
  await confirmer()
  const deux = await compteurs()
  expect([deux.notif - avant.notif, deux.chatter - avant.chatter, deux.date, deux.num], 'nouvelle date : 2 notifications, 2 commentaires').toEqual([2, 2, '2026-12-05', 'C-1'])
  // Persistance : rechargé, l'écran affiche la date confirmée relue.
  await p.reload()
  await expect(p.locator('li').filter({ has: p.locator('strong', { hasText: fp.ref }) }), 'rechargé : date confirmée').toContainText('Confirmée pour le', { timeout: 60_000 })
  await acheteur.ctx.dispose()
  await page.close()
})

etape('PF5.9-APUB71', ['APUB71'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const fp = await fournisseurPortail(m, 'APUB71', await py(`sortie(U.objects.get(username='demo_admin').pk)`))
  const fo = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(fo, { username: fp.u, password: MDP_ESSAI })
  const gestes = async () => [
    await fo.get(`${API}/portail/fournisseur/tableau-de-bord/`, T),
    await fo.get(`${API}/portail/mes-bons-commande/`, T),
    await fo.post(`${API}/portail/mes-bons-commande/${fp.bc}/confirmer/`, { ...T, data: { date_confirmee: '2027-01-15' } }),
  ]
  const poser = (champs) => py(`from apps.stock.models import Fournisseur
Fournisseur.objects.filter(pk=${fp.f}).update(${champs})
sortie(1)`)
  const bcf = () => py(`from apps.stock.models import BonCommandeFournisseur
b = BonCommandeFournisseur.objects.get(pk=${fp.bc})
sortie([b.date_confirmee_fournisseur, b.numero_confirmation_fournisseur])`)
  // Témoin : accès ouvert — lecture 200 et le BCF à l'écran.
  expect((await fo.get(`${API}/portail/mes-bons-commande/`, T)).status(), 'compte ouvert : liste 200').toBe(200)
  const p = await navigateur(context, suivi, testInfo, fp.u)
  await p.goto('/portail/fournisseur/commandes')
  await expect(p.getByText(fp.ref).first(), 'compte ouvert : BCF à l\'écran').toBeVisible({ timeout: 60_000 })
  // Bloqué « total », archivé, candidature rejetée (sans clic « Révoquer l'accès ») : 403 révocation ×3, rien d'écrit.
  for (const [etat, champs] of [
    ['bloqué total', "statut='bloque_total', is_archived=False, statut_validation='valide'"],
    ['archivé', "statut='actif', is_archived=True, statut_validation='valide'"],
    ['rejeté', "statut='actif', is_archived=False, statut_validation='rejete'"],
  ]) {
    await poser(champs)
    for (const r of await gestes()) {
      const corps = await r.text()
      expect(r.status(), `${etat} : ${r.url()} → ${corps.slice(0, 200)}`).toBe(403)
      expect(corps, `${etat} : message de révocation`).toContain('Votre accès au portail a été révoqué')
    }
    expect(await bcf(), `${etat} : BCF relu sans confirmation`).toEqual([null, ''])
  }
  // Écran du fournisseur coupé : plus le BCF, plus de « Confirmer ».
  await poser("statut='bloque_total', is_archived=False, statut_validation='valide'")
  suivi.attendre(/\/api\/django\/portail\//, 403)
  await p.reload()
  await p.waitForLoadState('networkidle')
  await expect(p.getByText(fp.ref), 'coupé : BCF plus affiché').toHaveCount(0)
  await expect(p.getByRole('button', { name: /Confirmer/ })).toHaveCount(0)
  // « Bloqué commandes » : lecture inchangée (200).
  await poser("statut='bloque_commandes', is_archived=False, statut_validation='valide'")
  const tb = await fo.get(`${API}/portail/fournisseur/tableau-de-bord/`, T)
  const li = await fo.get(`${API}/portail/mes-bons-commande/`, T)
  expect([tb.status(), li.status()], 'bloqué commandes : lectures 200').toEqual([200, 200])
  await poser("statut='bloque_total'")
  await fo.dispose()
  await page.close()
})

// ── APUB54 : objets personnalisés par la grille des rôles ──────────────────────────────────────────
etape('PF5.10-APUB54', ['APUB54'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  await py(`from apps.customfields.models import CustomObjectDef, CustomFieldDef, CustomRecord
o, _ = CustomObjectDef.objects.get_or_create(company_id=${SOC}, code='registre_cles', defaults=dict(libelle='Registre des clés'))
o.actif = True; o.save()
CustomFieldDef.objects.get_or_create(company_id=${SOC}, module='custom:registre_cles', code='numero_cle', defaults=dict(libelle='Numéro', type='text'))
CustomRecord.objects.create(company_id=${SOC}, objet=o, data={'numero_cle': 'A1-${m}'})
sortie(o.pk)`)
  const URL_REC = `${API}/custom-fields/custom-objects/registre_cles/records/`
  const di = await session(testInfo, `apub54di_${m}`, await roleLivre('Directeur'))
  const co = await session(testInfo, `apub54co_${m}`, await roleLivre('Commercial'))
  expect((await di.ctx.get(URL_REC, T)).status(), 'Directeur : liste 200').toBe(200)
  const cree = await di.ctx.post(URL_REC, { ...T, data: { data: { numero_cle: `D1-${m}` } } })
  expect(cree.status(), `Directeur : création ${(await cree.text()).slice(0, 200)}`).toBe(201)
  const perso = await py(`from apps.roles.models import Role
sortie(Role.objects.create(company_id=${SOC}, nom='APUB54 perso ${m}', permissions=[]).pk)`)
  const patch = await di.ctx.patch(`${API}/roles/${perso}/`, { ...T, data: { permissions: ['custom_object.registre_cles.voir'] } })
  expect(patch.status(), `Directeur octroie le code : ${(await patch.text()).slice(0, 200)}`).toBe(200)
  expect(await py(`from apps.roles.models import Role
sortie(Role.objects.get(pk=${perso}).permissions)`), 'rôle relu : code enregistré').toEqual(['custom_object.registre_cles.voir'])
  const porteur = await session(testInfo, `apub54po_${m}`, perso)
  expect((await porteur.ctx.get(URL_REC, T)).status(), 'porteur du code : 200').toBe(200)
  expect((await co.ctx.get(URL_REC, T)).status(), 'Commercial sans le code : 403').toBe(403)
  // Écran /objets/registre_cles en Directeur : liste et création, persistée au rechargement.
  const p = await navigateur(context, suivi, testInfo, di.nom)
  await p.goto('/objets/registre_cles')
  await expect(p.getByText(`D1-${m}`).first(), 'liste : enregistrement créé par l\'API').toBeVisible({ timeout: 60_000 })
  await p.locator('#champ-numero_cle').fill(`UI-${m}`)
  const [r] = await Promise.all([
    p.waitForResponse((x) => x.url().includes('/custom-objects/registre_cles/records/') && x.request().method() === 'POST'),
    p.getByRole('button', { name: "Ajouter l'enregistrement" }).click(),
  ])
  expect(r.status(), 'création à l\'écran : 201').toBe(201)
  await expect(p.getByText(`UI-${m}`).first(), 'ligne ajoutée').toBeVisible({ timeout: 30_000 })
  suivi.verifie(5)
  await p.reload()
  await expect(p.getByText(`UI-${m}`).first(), 'rechargé : ligne présente').toBeVisible({ timeout: 60_000 })
  for (const s of [di, co, porteur]) await s.ctx.dispose()
  await page.close()
})

// ── APUB55 : catalogue de l'explorateur borné aux jeux lisibles ────────────────────────────────────
etape('PF5.11-APUB55', ['APUB55'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const te = await session(testInfo, `apub55te_${m}`, await roleLivre('Commercial terrain'))
  const di = await session(testInfo, `apub55di_${m}`, await roleLivre('Directeur'))
  const verite = await py(`from core import data_explorer
from core.data_explorer import exiger_lecture_dataset
u = U.objects.get(pk=${te.id})
def refuse(n):
    try:
        exiger_lecture_dataset(n, u)
        return False
    except Exception:
        return True
tous = sorted(data_explorer._DATASETS)
sortie({'tous': tous, 'refuses': [n for n in tous if refuse(n)], 'palier': U.tier_for_role(u.role)})`)
  expect(verite.refuses.length, 'des jeux sont refusés au Commercial terrain').toBeGreaterThan(0)
  const noms = async (s) => {
    const a = (await lireJson(await s.ctx.get(`${API}/core/data-explorer/datasets/`, T), 'catalogue')).datasets.map((d) => d.name).sort()
    const b = (await lireJson(await s.ctx.get(`${API}/core/saved-queries/datasets/`, T), 'catalogue requêtes')).map((d) => d.name).sort()
    expect(b, `${s.nom} : même catalogue aux deux routes`).toEqual(a)
    return a
  }
  const vusTerrain = await noms(te)
  expect(vusTerrain.filter((n) => verite.refuses.includes(n)), 'aucun jeu refusé proposé').toEqual([])
  for (const n of vusTerrain) expect((await te.ctx.get(`${API}/core/data-explorer/datasets/${n}/`, T)).status(), `détail ${n} lisible`).toBe(200)
  const refuse = verite.refuses[0]
  expect((await te.ctx.get(`${API}/core/data-explorer/datasets/${refuse}/`, T)).status(), `détail refusé ${refuse} : 403`).toBe(403)
  expect(await noms(di), 'Directeur : tous les jeux').toEqual(verite.tous)
  // Écran : l'Explorateur de données est réservé aux paliers responsable/administrateur ; le Commercial terrain
  // (palier relu) est renvoyé vers /403 — aucun jeu ne lui est proposé.
  const p = await navigateur(context, suivi, testInfo, te.nom)
  await p.goto('/donnees/explorateur')
  if (['responsable', 'admin'].includes(verite.palier)) {
    await expect(p.getByTestId('expl-nb-datasets')).toContainText(`${vusTerrain.length} enregistré`, { timeout: 60_000 })
  } else {
    await expect(p, `palier « ${verite.palier} » : écran refusé`).toHaveURL(/\/403$/, { timeout: 60_000 })
  }
  for (const s of [te, di]) await s.ctx.dispose()
  await page.close()
})

// ── APUB57 : masquage « Premiers pas » réservé à `parametres_modifier` ────────────────────────────
etape('PF5.12-APUB57', ['APUB57'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const cr = await session(testInfo, `apub57cr_${m}`, await roleLivre('Commercial responsable'))
  const di = await session(testInfo, `apub57di_${m}`, await roleLivre('Directeur'))
  const B = `${API}/onboarding/items-masques`
  const liste = async (s) => lireJson(await s.ctx.get(`${B}/`, T), 'items masqués')
  const item = (await liste(cr)).find((x) => x.key === 'import_clients')
  expect(item, 'item « import_clients » au catalogue').toBeTruthy()
  const initial = item.masque
  for (const geste of ['masquer', 'demasquer']) {
    expect((await cr.ctx.post(`${B}/${item.id}/${geste}/`, { ...T, data: {} })).status(), `Commercial responsable : ${geste} 403`).toBe(403)
  }
  expect((await liste(cr)).find((x) => x.id === item.id).masque, 'relu : statut inchangé après les refus').toBe(initial)
  // Écran en Commercial responsable : bandeau lecture seule, case désactivée.
  const libelle = `Afficher « ${item.libelle} » dans les Premiers pas`
  const pc = await navigateur(context, suivi, testInfo, cr.nom)
  await pc.goto('/parametres?onglet=demo_onboarding')
  await expect(pc.getByTestId('parametres-lecture-seule'), 'bandeau lecture seule').toBeVisible({ timeout: 60_000 })
  await expect(pc.getByLabel(libelle), 'case désactivée').toBeDisabled({ timeout: 30_000 })
  // Écran en Directeur : masquage effectif, persistant au rechargement, puis rétabli.
  const pd = await navigateur(context, suivi, testInfo, di.nom)
  await pd.goto('/parametres?onglet=demo_onboarding')
  const caseD = pd.getByLabel(libelle)
  await expect(caseD, 'Directeur : case active').toBeEnabled({ timeout: 60_000 })
  await expect(pd.getByTestId('parametres-lecture-seule')).toHaveCount(0)
  const action = initial ? 'demasquer' : 'masquer'
  const [r] = await Promise.all([
    pd.waitForResponse((x) => x.url().includes(`/onboarding/items-masques/${item.id}/${action}/`)),
    caseD.click(),
  ])
  expect(r.status(), `Directeur : ${action} 200`).toBe(200)
  await pd.reload()
  await expect(pd.getByLabel(libelle), 'rechargé : nouvel état').toBeChecked({ checked: initial, timeout: 60_000 })
  expect((await liste(di)).find((x) => x.id === item.id).masque, 'relu : basculé').toBe(!initial)
  const retour = await di.ctx.post(`${B}/${item.id}/${initial ? 'masquer' : 'demasquer'}/`, { ...T, data: {} })
  expect(retour.status(), 'Directeur : rétabli 200').toBe(200)
  for (const s of [cr, di]) await s.ctx.dispose()
  await page.close()
})
