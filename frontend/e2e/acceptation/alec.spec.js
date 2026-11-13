// Rejeu en direct du groupe ALEC (parcours PF6 « lecture sensible », docs/audits/2026-11-11-parcours-PF6.md) :
// chaque étape joue la LECTURE de sa tâche par l'API réelle sous de vrais comptes connectés (`/token/`), aux rôles
// SYSTÈME de la société de demo_admin relus par leur nom et comparés au registre (`CANONICAL_SYSTEM_ROLES`, aligné
// par `init_roles`) — jamais un rôle fabriqué. Le rôle privé lit la clé absente / reçoit 403 ou 404 ; le Directeur
// (et le créateur quand la tâche le dit) la lit. Données posées par l'ORM (shell Django persistant) ou l'API, propres
// à l'étape (marque unique), nettoyées à la fin. La sonde du constat est rejouée quand elle existe (hôte, sans base).
// ALEC15/16 (agent SQL FastAPI) : l'outil sécurisé RÉEL (`_make_secure_query_tool`) dans le venv FastAPI
// (`E2E_IA_PYTHON`), permissions lues par le vrai `resolve_caller_permissions` (→ `/auth/me/` du Django du rejeu),
// requêtes exécutées sur la base du rejeu ; aucune clé de LLM n'est en jeu (la garde est en amont du modèle).
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, lireJson, telephoneMobileUnique, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC1', 'ALEC2', 'ALEC8', 'ALEC9', 'ALEC10', 'ALEC15', 'ALEC16', 'ALEC18', 'ALEC19',
  'ALEC21', 'ALEC27', 'ALEC36', 'ALEC37', 'ALEC39'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

/** Rejoue une sonde ALEC (script hôte, sans base) ; {ok, repro, observe | erreur}. */
function sonde(n) {
  const r = spawnSync('python', [`docs/audits/sondes/ALEC/C-ALEC-${n}.py`], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000 })
  try {
    const d = JSON.parse(r.stdout)
    return { ok: true, repro: d.repro, observe: d.observe }
  } catch {
    return { ok: false, erreur: ((r.stderr || r.stdout || '').trim().split('\n').pop() || `code ${r.status}`).slice(0, 300) }
  }
}
/** Sonde rejouée : si elle s'exécute, `repro` doit être faux ; si elle plante (bouchon d'audit qui ignore la
 *  nouvelle garde), l'échec d'exécution est consigné (annotation) — le rejeu API ci-dessous fait la preuve. */
function sondeApres(testInfo, n) {
  const s = sonde(n)
  testInfo.annotations.push({ type: `sonde C-ALEC-${n}`, description: s.ok ? `repro=${s.repro}` : `ne s'exécute plus : ${s.erreur}` })
  console.log(`[ALEC] sonde C-ALEC-${n} : ${s.ok ? `repro=${s.repro}` : `ERREUR ${s.erreur}`}`)
  if (s.ok) expect(s.repro, `sonde C-ALEC-${n} après correctif`).toBe(false)
  return s
}

/** Rôle SYSTÈME relu par son nom ; ses codes en base = ceux du registre livré. */
async function roleReel(nom) {
  const r = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
r = Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nom)})
reg = set(dict(CANONICAL_SYSTEM_ROLES)[${JSON.stringify(nom)}])
sortie(dict(pk=r.pk, manque=sorted(reg - set(r.permissions)), plus=sorted(set(r.permissions) - reg)))`)
  expect([r.manque, r.plus], `rôle « ${nom} » en base = registre livré`).toEqual([[], []])
  return r.pk
}

const sessions = []
/** Compte d'essai au rôle livré `nomRole`, connecté par `/token/` ; {ctx, id, username}. */
async function session(testInfo, prefixe, nomRole) {
  const username = `${prefixe}_${marque()}`
  const id = await py(`u = compte(${JSON.stringify(username)}, role=${await roleReel(nomRole)}, societe=${SOC})
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username, password: MDP_ESSAI })
  const s = { ctx, id, username, role: nomRole }
  sessions.push(s)
  return s
}
async function fermerSessions() {
  const noms = sessions.splice(0).map((s) => { s.ctx.dispose().catch(() => undefined); return s.username })
  if (noms.length) await py(`U.objects.filter(username__in=${JSON.stringify(noms)}).update(is_active=False)
sortie(1)`).catch(() => null)
}
test.afterEach(fermerSessions)

/** Toutes les lignes d'une liste DRF (paginée ou non) ; `next` ramené au chemin relatif (même origine, cookies). */
async function lignes(ctx, url) {
  const out = []
  let suivant = url
  while (suivant) {
    const r = await ctx.get(suivant, T)
    expect(r.status(), `${url} → ${(await r.text()).slice(0, 200)}`).toBe(200)
    const d = await r.json()
    if (Array.isArray(d)) return out.concat(d)
    out.push(...(d.results || []))
    suivant = d.next ? (() => { const u = new URL(d.next); return `${u.pathname}${u.search}` })() : null
  }
  return out
}
const statut = async (ctx, url) => (await ctx.get(url, T)).status()

/** Page sous un compte d'essai (connexion par l'écran), observée par les oracles. */
async function pageSous(context, suivi, testInfo, s) {
  const ctx = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', storageState: { cookies: [], origins: [] } })
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await uiLoginJusquAuxApps(p, { username: s.username, password: MDP_ESSAI })
  return { p, ctx }
}

// ── PF6.4 — signature GED (C-ALEC-001) ─────────────────────────────────────────────────────────────────────────
const docGed = (m, extra = '') => `from apps.ged.models import Cabinet, Folder, Document
cab = Cabinet.objects.create(company_id=${SOC}, nom='ALEC ${m}')
fol = Folder.objects.create(company_id=${SOC}, cabinet=cab, nom='Dossier ALEC ${m}')
doc = Document.objects.create(company_id=${SOC}, folder=fol, nom='Contrat ALEC ${m}')
${extra}`
const nettoyerGed = (m) => py(`from apps.ged.models import Cabinet
for c in Cabinet.objects.filter(company_id=${SOC}, nom='ALEC ${m}'):
    try: c.delete()
    except Exception: pass
sortie(1)`).catch(() => null)

etape('PF6.4.ALEC1', ['ALEC1'], async ({ testInfo }) => {
  sondeApres(testInfo, '001')
  const m = marque()
  const c1 = await session(testInfo, 'alec1c1', 'Commercial')
  const lecteurs = {
    c2: await session(testInfo, 'alec1c2', 'Commercial'), viewer: await session(testInfo, 'alec1v', 'Viewer'),
    c1, directeur: await session(testInfo, 'alec1d', 'Directeur'),
  }
  try {
    const ids = await py(docGed(m, `from apps.ged import services
c1 = U.objects.get(pk=${c1.id})
mono = services.demander_signature(doc, signataire_nom='M', signataire_email='m-${m}@example.invalid', company=doc.company, created_by=c1, notifier=False)
multi = services.creer_demande_multi_signataires(doc, destinataires=[{'nom': 'A', 'email': 'a-${m}@example.invalid'}, {'nom': 'B', 'email': 'b-${m}@example.invalid'}], company=doc.company, created_by=c1)
sortie(dict(mono=mono.pk, multi=multi.pk))`))
    for (const [qui, s] of Object.entries(lecteurs)) {
      const voit = qui === 'c1' || qui === 'directeur'
      const liste = Object.fromEntries((await lignes(s.ctx, `${API}/ged/demandes-signature/`)).map((d) => [d.id, d]))
      expect(liste[ids.mono], `${qui} : demande mono listée`).toBeTruthy()
      expect(liste[ids.multi], `${qui} : demande à destinataires listée`).toBeTruthy()
      const detail = await lireJson(await s.ctx.get(`${API}/ged/demandes-signature/${ids.mono}/`, T), `${qui} détail mono`)
      for (const [quoi, ligne] of [['liste mono', liste[ids.mono]], ['détail mono', detail]]) {
        expect('token' in ligne, `${qui} ${quoi} : token`).toBe(voit)
        expect('lien_signature' in ligne, `${qui} ${quoi} : lien_signature`).toBe(voit)
      }
      expect('token' in liste[ids.multi], `${qui} : token d'une demande à destinataires (jamais servi)`).toBe(false)
      const dests = [...(await lignes(s.ctx, `${API}/ged/signataires-demande/`)).filter((d) => d.demande === ids.multi),
        ...(liste[ids.multi].signataires || [])]
      expect(dests.length, `${qui} : 2 destinataires (liste) + 2 (imbriqués)`).toBe(4)
      for (const d of dests) {
        expect('lien_signature' in d, `${qui} destinataire ${d.id} : lien_signature`).toBe(voit)
        expect('token' in d, `${qui} destinataire ${d.id} : token`).toBe(false)
      }
    }
  } finally { await nettoyerGed(m) }
})

etape('PF6.4.ALEC2', ['ALEC2'], async ({ testInfo }) => {
  sondeApres(testInfo, '001')
  const m = marque()
  const anonyme = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  try {
    const d = await py(docGed(m, `from apps.ged import services
admin = U.objects.get(username='demo_admin')
mono = services.demander_signature(doc, signataire_nom='M', signataire_email='m-${m}@example.invalid', company=doc.company, created_by=admin, notifier=False)
multi = services.creer_demande_multi_signataires(doc, destinataires=[{'nom': 'Alice', 'email': 'al-${m}@example.invalid'}, {'nom': 'Bob', 'email': 'bo-${m}@example.invalid'}], company=doc.company, created_by=admin)
sortie(dict(mono=mono.token, multi=multi.token, multi_id=multi.pk, n=multi.signataires.count()))`))
    expect(d.n, 'demande à 2 destinataires').toBe(2)
    const url = `${API}/ged/signature/${d.multi}/`
    expect(await statut(anonyme, url), 'GET jeton global d\'une demande à destinataires').toBe(404)
    const post = await anonyme.post(url, { ...T, data: { action: 'signer', consentement: true, signature_texte: 'Client' } })
    expect(post.status(), `POST signer : ${(await post.text()).slice(0, 200)}`).toBe(404)
    const relue = await py(`from apps.ged.models import DemandeSignatureDocument as DemandeSignature
x = DemandeSignature.objects.get(pk=${d.multi_id})
sortie(dict(statut=x.statut, version=x.version_signee_id))`)
    expect(relue, 'persistance : demande relue en attente, aucune version figée').toEqual({ statut: 'en_attente', version: null })
    expect(await statut(anonyme, `${API}/ged/signature/${d.mono}/`), 'demande mono : route publique inchangée').toBe(200)
  } finally { await anonyme.dispose(); await nettoyerGed(m) }
})

// ── PF6.3 — documents GED et PDF de chantier (C-ALEC-016, C-ALEC-017) ───────────────────────────────────────────
etape('PF6.3.ALEC18', ['ALEC18'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, '016')
  const m = marque()
  const c1 = await session(testInfo, 'alec18c1', 'Commercial')
  const c2 = await session(testInfo, 'alec18c2', 'Commercial')
  const terrain = await session(testInfo, 'alec18t', 'Commercial terrain')
  const rh = await session(testInfo, 'alec18rh', 'Admin RH')
  const dir = await session(testInfo, 'alec18d', 'Directeur')
  let ui = null
  try {
    const ids = await py(`from apps.ged.models import Cabinet, Folder, Document
cab = Cabinet.objects.create(company_id=${SOC}, nom='ALEC ${m}')
fol = Folder.objects.create(company_id=${SOC}, cabinet=cab, nom='Dossier ALEC ${m}')
interne = Document.objects.create(company_id=${SOC}, folder=fol, nom='ALEC18-${m}-interne')
fac = Document.objects.create(company_id=${SOC}, folder=fol, nom='ALEC18-${m}-FAC.pdf', created_by_id=${c1.id}, custom_data={'routage_reference': 'FAC-${m}'})
up = Document.objects.create(company_id=${SOC}, folder=fol, nom='ALEC18-${m}-CIN.pdf', custom_data={'source_type': 'portail.piece', 'source_id': 1})
sortie(dict(interne=interne.pk, fac=fac.pk, up=up.pk))`)
    const vus = async (s) => new Set((await lignes(s.ctx, `${API}/ged/documents/?search=ALEC18-${m}`)).map((d) => d.id))
    for (const chemin of ['documents/', `documents/${ids.interne}/`, 'versions/']) {
      expect(await statut(terrain.ctx, `${API}/ged/${chemin}`), `Commercial terrain : ${chemin}`).toBe(403)
    }
    expect([...await vus(rh)], 'Admin RH : document interne seul').toEqual([ids.interne])
    expect([...await vus(c2)], 'C2 : ni la facture de C1 ni l\'upload portail').toEqual([ids.interne])
    expect([...await vus(c1)].sort(), 'C1 : document interne + sa facture').toEqual([ids.interne, ids.fac].sort())
    expect([...await vus(dir)].sort(), 'Directeur : tout').toEqual([ids.interne, ids.fac, ids.up].sort())
    for (const id of [ids.fac, ids.up]) expect(await statut(c2.ctx, `${API}/ged/documents/${id}/`), `C2 détail ${id}`).toBe(404)
    // Écran GED en C2 : le dossier montre le document interne, jamais la facture de C1.
    ui = await pageSous(context, suivi, testInfo, c2)
    const p = ui.p
    await p.goto('/ged')
    const choix = p.getByRole('combobox', { name: 'Choisir le cabinet' })
    if (await choix.count()) {
      await choix.click()
      await p.getByRole('option', { name: `ALEC ${m}`, exact: true }).click()
    }
    await p.getByRole('treeitem').getByRole('button', { name: `Dossier ALEC ${m}` }).click()
    await expect(p.getByLabel(`Sélectionner ALEC18-${m}-interne`)).toBeVisible({ timeout: 30_000 })
    await expect(p.getByLabel(`Sélectionner ALEC18-${m}-FAC.pdf`)).toHaveCount(0)
    await expect(p.getByLabel(`Sélectionner ALEC18-${m}-CIN.pdf`)).toHaveCount(0)
    await p.reload()
    await expect(p.getByText(`ALEC18-${m}-FAC.pdf`)).toHaveCount(0)
  } finally {
    if (ui) await ui.ctx.close().catch(() => undefined)
    await nettoyerGed(m)
  }
})

const ROUTES_PDF = ['pv-reception', 'bon-livraison', 'dossier-remise', 'attestation']
etape('PF6.3.ALEC19', ['ALEC19'], async ({ testInfo }) => {
  sondeApres(testInfo, '017')
  const m = marque()
  const tech = await session(testInfo, 'alec19t', 'Technicien')
  const c1 = await session(testInfo, 'alec19c1', 'Commercial')
  const terrain = await session(testInfo, 'alec19ct', 'Commercial terrain')
  const rh = await session(testInfo, 'alec19rh', 'Admin RH')
  const dir = await session(testInfo, 'alec19d', 'Directeur')
  const ch = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
cl = Client.objects.create(company_id=${SOC}, nom='Idrissi${m}', prenom='Nadia', telephone='${telephoneMobileUnique()}', adresse='3 rue Secret, Rabat')
i = Installation.objects.create(company_id=${SOC}, reference='CH-ALEC19-${m}', client=cl, created_by_id=${c1.id}, technicien_responsable_id=${tech.id}, statut=Installation.Statut.INSTALLE)
sortie(dict(id=i.pk, client=cl.pk))`)
  try {
    for (const s of [terrain, rh]) {
      for (const route of ROUTES_PDF) {
        const r = await s.ctx.get(`${API}/documents/chantiers/${ch.id}/${route}/`, T)
        expect(r.status(), `${s.role} : ${route}`).toBe(403)
        expect((await r.body()).includes(Buffer.from(`Idrissi${m}`)), `${s.role} : ${route} sans le client`).toBe(false)
      }
    }
    for (const [s, routes] of [[tech, ROUTES_PDF], [c1, ROUTES_PDF.slice(0, 3)], [dir, ROUTES_PDF]]) {
      for (const route of routes) {
        const r = await s.ctx.get(`${API}/documents/chantiers/${ch.id}/${route}/`, T)
        expect(r.status(), `${s.role} : ${route} ${r.status() >= 400 ? (await r.text()).slice(0, 200) : ''}`).toBe(200)
        expect(r.headers()['content-type'], `${s.role} : ${route} PDF`).toContain('application/pdf')
      }
    }
  } finally {
    await py(`from apps.installations.models import Installation
from apps.crm.models import Client
Installation.objects.filter(pk=${ch.id}).delete(); Client.objects.filter(pk=${ch.client}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── PF6.4 — jetons publics (C-ALEC-033) et photo du toit (C-ALEC-035) ─────────────────────────────────────────
etape('PF6.4.ALEC36', ['ALEC36'], async ({ testInfo }) => {
  const m = marque()
  const dir = await session(testInfo, 'alec36d', 'Directeur')
  const com = await session(testInfo, 'alec36c', 'Commercial')
  try {
    const fol = await py(docGed(m, 'sortie(fol.pk)'))
    const cree = await lireJson(await dir.ctx.post(`${API}/ged/depots-publics/`, { ...T, data: { folder: fol } }), 'création du lien de dépôt')
    expect(cree.token, 'réponse de création (créateur) : token').toBeTruthy()
    for (const [s, voit] of [[com, false], [dir, true]]) {
      const ligne = (await lignes(s.ctx, `${API}/ged/depots-publics/`)).find((x) => x.id === cree.id)
      expect(ligne, `${s.role} : lien listé`).toBeTruthy()
      const detail = await lireJson(await s.ctx.get(`${API}/ged/depots-publics/${cree.id}/`, T), `${s.role} détail`)
      expect(['token' in ligne, 'token' in detail], `${s.role} : token (liste, détail)`).toEqual([voit, voit])
    }
  } finally { await nettoyerGed(m) }
})

etape('PF6.4.ALEC37', ['ALEC37'], async ({ testInfo }) => {
  const m = marque()
  const com = await session(testInfo, 'alec37c', 'Commercial')
  const dir = await session(testInfo, 'alec37d', 'Directeur')
  const x = await py(`from decimal import Decimal
from apps.crm.models import Client, Lead
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis
from apps.ventes.models import Devis
com = U.objects.get(pk=${com.id})
cl = Client.objects.create(company_id=${SOC}, nom='Site', prenom='ALEC37', email='alec37-${m}@example.invalid')
lead = Lead.objects.create(company_id=${SOC}, nom='Site ALEC37 ${m}', type_installation='residentiel', owner=com)
dv = Devis.objects.create(company_id=${SOC}, reference='DEV-ALEC37-${m}', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel', created_by=com)
inst, _ = create_installation_from_devis(dv, com, com.company)
it = Intervention.objects.create(company_id=${SOC}, installation=inst, type_intervention='pose', created_by=com, technicien=com, statut=Intervention.Statut.VALIDEE, signataire_nom='Client Test')
type(inst).objects.filter(pk=inst.pk).update(created_by=com)
sortie(dict(inst=inst.pk, it=it.pk, client=it.ensure_lien_client_token(), rapport=it.ensure_lien_rapport_token(), devis=dv.pk))`)
  for (const s of [com, dir]) {
    const r = await s.ctx.get(`${API}/installations/interventions/${x.it}/`, T)
    if (s === com) {
      // Le Commercial lit les chantiers par l'octroi `ventes_voir` sur le CHANTIER, pas la fiche intervention.
      expect(r.status(), 'Commercial : fiche intervention').toBe(403)
    } else {
      expect(r.status(), 'Directeur : fiche intervention').toBe(200)
      const d = await r.json()
      expect(['lien_client_token' in d, 'lien_rapport_token' in d], 'Directeur : fiche intervention sans jetons').toEqual([false, false])
    }
    const ch = await lireJson(await s.ctx.get(`${API}/installations/chantiers/${x.inst}/`, T), `${s.role} : fiche chantier`)
    const imb = (ch.interventions || []).filter((i) => i.id === x.it)
    expect(imb.length, `${s.role} : intervention imbriquée`).toBe(1)
    expect(['lien_client_token' in imb[0], 'lien_rapport_token' in imb[0]], `${s.role} : chantier sans jetons`).toEqual([false, false])
  }
  const lien = await lireJson(await dir.ctx.get(`${API}/installations/interventions/${x.it}/lien-rapport/`, T), 'Directeur lien-rapport')
  expect(lien.token, 'action lien-rapport : seule source du jeton').toBe(x.rapport)
  const relu = await py(`from apps.installations.models import Intervention
i = Intervention.objects.get(pk=${x.it})
sortie([i.lien_client_token, i.lien_rapport_token])`)
  expect(relu, 'persistance : jetons inchangés').toEqual([x.client, x.rapport])
})

etape('PF6.4.ALEC39', ['ALEC39'], async ({ testInfo }) => {
  const a = await session(testInfo, 'alec39a', 'Commercial')
  const b = await session(testInfo, 'alec39b', 'Commercial')
  const dir = await session(testInfo, 'alec39d', 'Directeur')
  const x = await py(`from apps.crm.models import Lead
from apps.visites.models import VisiteTerrain
b = U.objects.get(pk=${b.id})
lead = Lead.objects.create(company_id=${SOC}, nom='Toit de B ALEC39', owner=b, telephone='${telephoneMobileUnique()}')
v = VisiteTerrain.objects.create(company_id=${SOC}, lead=lead, commercial=b, statut=VisiteTerrain.Statut.VALIDEE, photo_toit_key='toit-assemble-alec39.png', texture_calage={'coins': [[33.57, -7.58], [33.57, -7.57], [33.56, -7.57], [33.56, -7.58]]})
sortie(dict(lead=lead.pk, visite=v.pk))`)
  try {
    const refus = await a.ctx.get(`${API}/crm/leads/${x.lead}/photo-toit/`, T)
    expect(refus.status(), 'Commercial A : photo-toit du lead de B').toBe(404)
    expect((await refus.json()).detail, 'même réponse qu\'un lead d\'une autre société').toBe('Lead introuvable.')
    expect(await statut(a.ctx, `${API}/crm/leads/${x.lead}/`), 'Commercial A : fiche du lead de B').toBe(404)
    const ok = await lireJson(await dir.ctx.get(`${API}/crm/leads/${x.lead}/photo-toit/`, T), 'Directeur photo-toit')
    expect(Object.keys(ok).sort(), 'Directeur : forme du contrat').toEqual(['texture_calage', 'url', 'visite_id'])
    expect(ok.visite_id, 'Directeur : dernière visite validée').toBe(x.visite)
    expect(ok.url, 'Directeur : url de l\'image').toContain(`/visites/visites/${x.visite}/photo-toit/`)
    expect(ok.texture_calage?.coins?.length, 'Directeur : calage').toBe(4)
    expect(await statut(b.ctx, `${API}/crm/leads/${x.lead}/photo-toit/`), 'Commercial B (propriétaire)').toBe(200)
  } finally {
    await py(`from apps.crm.models import Lead
from apps.visites.models import VisiteTerrain
VisiteTerrain.objects.filter(pk=${x.visite}).delete(); Lead.objects.filter(pk=${x.lead}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── PF6.1 — montants d'achat côté chantiers (C-ALEC-006, -007, -008) ────────────────────────────────────────────
const bcf = (m, montant) => `from apps.stock.models import Fournisseur, Produit, BonCommandeFournisseur, LigneBonCommandeFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom='Four ALEC ${m}')
pr = Produit.objects.create(company_id=${SOC}, nom='Prod ALEC ${m}', prix_vente=1, prix_achat=0)
bcf = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference='BCF-ALEC-${m}', fournisseur=f)
LigneBonCommandeFournisseur.objects.create(bon_commande=bcf, produit=pr, quantite=1, prix_achat_unitaire=${montant})
`

etape('PF6.1.ALEC8', ['ALEC8'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, '006')
  const m = marque()
  const tech = await session(testInfo, 'alec8t', 'Technicien')
  const dir = await session(testInfo, 'alec8d', 'Directeur')
  const x = await py(`${bcf(m, 10000)}
from apps.installations.models import ApprobationBCF
appr = ApprobationBCF.objects.create(company_id=${SOC}, bcf=bcf, palier='admin', montant_approuve=10000, approuve_par_id=${dir.id})
sortie(dict(bcf=bcf.pk, appr=appr.pk))`)
  let ui = null
  try {
    const liste = await lignes(tech.ctx, `${API}/installations/approbations-bcf/?bcf=${x.bcf}`)
    const ligne = liste.find((l) => l.id === x.appr)
    expect(ligne, 'Technicien : approbation listée').toBeTruthy()
    const detail = await lireJson(await tech.ctx.get(`${API}/installations/approbations-bcf/${x.appr}/`, T), 'Technicien détail')
    for (const [quoi, l] of [['liste', ligne], ['détail', detail]]) {
      expect('montant_approuve' in l, `Technicien ${quoi} : montant_approuve`).toBe(false)
      expect([l.palier, l.approuve_par, 'date_approbation' in l], `Technicien ${quoi} : palier, approbateur, date`).toEqual(['admin', dir.id, true])
    }
    const d = await lireJson(await dir.ctx.get(`${API}/installations/approbations-bcf/${x.appr}/`, T), 'Directeur détail')
    expect(parseFloat(d.montant_approuve), 'Directeur : 10 000').toBe(10000)
    // Écran Approvisionnement (route au palier responsable/admin) : le Technicien (palier « normal ») n'y entre pas
    // (page « Accès refusé ») ; le Technicien responsable (rôle livré du constat, sans `prix_achat_voir`) y entre et
    // lit « — » dans la colonne « Montant approuvé ».
    ui = await pageSous(context, suivi, testInfo, tech)
    await ui.p.goto('/chantiers/approvisionnement')
    await expect(ui.p.getByText('Accès refusé (403)')).toBeVisible({ timeout: 30_000 })
    await ui.ctx.close().catch(() => undefined)
    const tr = await session(testInfo, 'alec8tr', 'Technicien responsable')
    const ltr = await lireJson(await tr.ctx.get(`${API}/installations/approbations-bcf/${x.appr}/`, T), 'Technicien responsable détail')
    expect('montant_approuve' in ltr, 'Technicien responsable : montant_approuve').toBe(false)
    ui = await pageSous(context, suivi, testInfo, tr)
    const p = ui.p
    await p.goto('/chantiers/approvisionnement')
    await p.getByRole('tab', { name: 'Approbations BCF' }).click()
    const rangee = p.locator('tr').filter({ has: p.locator('td', { hasText: new RegExp(`^${x.bcf}$`) }) })
    await expect(rangee).toHaveCount(1, { timeout: 30_000 })
    await expect(rangee.locator('td').nth(2)).toHaveText('—')
  } finally {
    if (ui) await ui.ctx.close().catch(() => undefined)
    await py(`from apps.installations.models import ApprobationBCF
ApprobationBCF.objects.filter(pk=${x.appr}).delete()
sortie(1)`).catch(() => null)
  }
})

etape('PF6.1.ALEC9', ['ALEC9'], async ({ testInfo }) => {
  sondeApres(testInfo, '007')
  const m = marque()
  const x = await py(`${bcf(m, 20000)}
from apps.installations.models_program import Projet, BudgetProjet, BudgetEngagement
pj = Projet.objects.create(company_id=${SOC}, reference='PR-ALEC9-${m}', nom='Programme ALEC9 ${m}')
bu = BudgetProjet.objects.create(company_id=${SOC}, projet=pj, budget_materiel=50000)
BudgetEngagement.objects.create(company_id=${SOC}, budget=bu, source='bon_commande', categorie='materiel', bon_commande=bcf)
sortie(dict(projet=pj.pk, budget=bu.pk))`)
  const controle = `${API}/installations/controle-budgetaire/?montant=0&projet=${x.projet}`
  const synthese = `${API}/installations/programme-budgets/${x.budget}/synthese/`
  try {
    for (const nom of ['Commercial', 'Technicien']) {
      const s = await session(testInfo, `alec9${nom.slice(0, 3).toLowerCase()}`, nom)
      for (const url of [controle, synthese]) {
        const r = await s.ctx.get(url, T)
        const corps = await r.json().catch(() => ({}))
        expect(r.status(), `${nom} : ${url}`).toBe(403)
        // Corps `{detail}` (+ l'enveloppe `error` que pose `core.exceptions.taqinor_exception_handler` sur toute
        // erreur) : aucun montant du budget d'achat.
        expect(typeof corps.detail, `${nom} : detail`).toBe('string')
        expect(Object.keys(corps).filter((k) => !['detail', 'error'].includes(k)), `${nom} : aucune autre clé`).toEqual([])
        expect(JSON.stringify(corps), `${nom} : aucun montant`).not.toMatch(/30 ?000|50 ?000|20 ?000/)
      }
    }
    const dir = await session(testInfo, 'alec9d', 'Directeur')
    const c = await lireJson(await dir.ctx.get(controle, T), 'Directeur contrôle')
    expect(c.reste_categorie, 'Directeur : reste matériel 50 000 − 20 000 engagés').toBe(30000)
    expect(await statut(dir.ctx, synthese), 'Directeur : synthèse').toBe(200)
  } finally {
    await py(`from apps.installations.models_program import Projet
Projet.objects.filter(pk=${x.projet}).delete()
sortie(1)`).catch(() => null)
  }
})

etape('PF6.1.ALEC10', ['ALEC10'], async ({ testInfo }) => {
  sondeApres(testInfo, '008')
  const m = marque()
  const x = await py(`from decimal import Decimal
from apps.installations.models import Kit, KitComposant, OrdreAssemblage, OrdreSousTraitance
from apps.stock.models import Fournisseur, Produit
from apps.crm.models import Client
admin = U.objects.get(username='demo_admin')
comp = Produit.objects.create(company_id=${SOC}, nom='Coffret ALEC10 ${m}', prix_vente=200, prix_achat=0, quantite_stock=0)
c1 = Produit.objects.create(company_id=${SOC}, nom='Onduleur ALEC10 ${m}', prix_vente=200, prix_achat=100, quantite_stock=50)
kit = Kit.objects.create(company_id=${SOC}, nom='Coffret ALEC10 ${m}', produit_compose=comp)
KitComposant.objects.create(kit=kit, produit=c1, quantite=2)
st = Fournisseur.objects.create(company_id=${SOC}, nom='Atelier ALEC10 ${m}', type=Fournisseur.Type.SERVICE)
ost = OrdreSousTraitance.objects.create(company_id=${SOC}, reference='OST-ALEC10-${m}', sous_traitant=st, prestation='Assemblage façon', montant=Decimal('500'), montant_realise=Decimal('450'), created_by=admin)
o = OrdreAssemblage.objects.create(company_id=${SOC}, reference='ASM-ALEC10-${m}', kit=kit, quantite=1, sous_traitant=st, ordre_sous_traitance=ost, created_by=admin)
cl = Client.objects.create(company_id=${SOC}, nom='Site', prenom='ALEC10', email='alec10-${m}@example.invalid')
sortie(dict(ordre=o.pk, composite=comp.pk, client=cl.pk))`)
  const devisKit = (suffixe) => py(`from decimal import Decimal
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
d = Devis.objects.create(company_id=${SOC}, reference='DEV-ALEC10-${m}-${suffixe}', client_id=${x.client}, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
LigneDevis.objects.create(devis=d, produit=Produit.objects.get(pk=${x.composite}), designation='Coffret', quantite=Decimal('1'), prix_unitaire=Decimal('300'))
sortie(d.pk)`)
  const cout = `${API}/installations/ordres-assemblage/${x.ordre}/cout-soustraitance/`
  const depuis = `${API}/installations/ordres-assemblage/depuis-devis/`
  const tech = await session(testInfo, 'alec10t', 'Technicien')
  const r1 = await tech.ctx.get(cout, T)
  expect(r1.status(), 'Technicien : coût de sous-traitance').toBe(403)
  expect('cout_composite' in (await r1.json().catch(() => ({}))), 'Technicien : sans cout_composite').toBe(false)
  const dvT = await devisKit('t')
  const r2 = await tech.ctx.post(depuis, { ...T, data: { devis: dvT } })
  expect(r2.status(), `Technicien depuis-devis : ${(await r2.text()).slice(0, 200)}`).toBe(201)
  const ordresT = await r2.json()
  expect(ordresT.length, 'Technicien : ordres créés').toBeGreaterThan(0)
  for (const o of ordresT) expect('cout_prevu' in o, `Technicien : ordre ${o.id} sans cout_prevu`).toBe(false)
  const dir = await session(testInfo, 'alec10d', 'Directeur')
  const c = await lireJson(await dir.ctx.get(cout, T), 'Directeur coût')
  expect(c.cout_composite, 'Directeur : 2 × 100 + façon 450').toBeCloseTo(650)
  const dvD = await devisKit('d')
  const r3 = await dir.ctx.post(depuis, { ...T, data: { devis: dvD } })
  expect(r3.status(), `Directeur depuis-devis : ${(await r3.text()).slice(0, 200)}`).toBe(201)
  expect('cout_prevu' in (await r3.json())[0], 'Directeur : cout_prevu servi').toBe(true)
  const relus = await py(`from apps.installations.models import OrdreAssemblage
sortie([OrdreAssemblage.objects.filter(company_id=${SOC}, devis_id=${dvT}).count(), OrdreAssemblage.objects.filter(company_id=${SOC}, devis_id=${dvD}).count()])`)
  expect(relus.every((n) => n > 0), `persistance : ordres relus ${JSON.stringify(relus)}`).toBe(true)
})

// ── PF6.2 / PF6.4 — agent SQL FastAPI (C-ALEC-013, C-ALEC-014) ─────────────────────────────────────────────────
const IA = `
import json, os, sys
sys.path.insert(0, os.getcwd())
os.environ['DJANGO_INTERNAL_URL'] = 'http://127.0.0.1:8000'
os.environ['DJANGO_INTERNAL_HOST'] = 'localhost'
from app.services.action_tools import ActionContext, resolve_caller_permissions
from app.services import sql_agent_service as s
from langchain_community.utilities import SQLDatabase
a = json.loads(sys.argv[1])
ctx = resolve_caller_permissions(ActionContext(a['company_id'], '', None, a['token']))
perms = list(ctx.permissions)
# Même dérivation que SQLAgentService (allow_price L17, allow_pii ALEC15, permissions ALEC16).
allow_price = 'prix_achat_voir' in perms
allow_pii = 'client_pii_voir' in perms
permissions = perms or None
db = SQLDatabase.from_uri(a['db'], include_tables=['sav_ticket', 'crm_client'], sample_rows_in_table_info=0)
outil = s._make_secure_query_tool(db, a['company_id'], allow_price, allow_pii, permissions)
refus = (s._UNSAFE_QUERY_REPLY, s._FORBIDDEN_TOOL_REPLY)
res = dict(n_permissions=len(perms), allow_price=allow_price, allow_pii=allow_pii, cas={})
for sql in a['sql']:
    c = {}
    try:
        c['securise'] = s._validate_and_secure(sql, a['company_id'], allow_price=allow_price, allow_pii=allow_pii, permissions=permissions)
    except s.SQLSecurityError as e:
        c['refus'] = str(e)
    out = outil._run(sql)
    c['outil_refuse'] = out in refus
    c['outil'] = str(out)[:300]
    res['cas'][sql] = c
print('@@' + json.dumps(res, default=str))
`
async function agentSql(s, companyId, sqls) {
  const py3 = process.env.E2E_IA_PYTHON
  expect(py3, 'E2E_IA_PYTHON (venv des dépendances FastAPI) posé par le workflow').toBeTruthy()
  const jeton = (await s.ctx.storageState()).cookies.find((c) => c.name === 'access_token')?.value
  expect(jeton, `${s.role} : jeton d'accès`).toBeTruthy()
  const arg = JSON.stringify({ token: jeton, company_id: companyId, sql: sqls, db: process.env.E2E_IA_DB || 'postgresql://erp_user:ci_password@localhost:5432/erp_db' })
  const r = spawnSync(py3, ['-c', IA, arg], { cwd: join(RACINE, 'backend/fastapi_ia'), encoding: 'utf8', maxBuffer: 50_000_000 })
  const l = (r.stdout || '').split('\n').filter((x) => x.startsWith('@@')).pop()
  expect(l, `outil SQL (${s.role}) : ${(r.stderr || '').slice(-800)}`).toBeTruthy()
  const res = JSON.parse(l.slice(2))
  console.log(`[ALEC] agent SQL ${s.role} : ${JSON.stringify(res).slice(0, 1500)}`)
  return res
}
const societe = () => py(`sortie(${SOC})`)

etape('PF6.2.ALEC15', ['ALEC15'], async ({ testInfo }) => {
  sondeApres(testInfo, '013')
  const cid = await societe()
  const Q = ['SELECT cout FROM sav_ticket', 'SELECT donnees_structurees FROM ia_ocr_document',
    'SELECT email, telephone FROM crm_client', 'SELECT * FROM sav_ticket', 'SELECT count(*) FROM crm_client']
  const PRIX = /prix d'achat \/ marge/
  const PII = /client_pii_voir/
  // Commercial terrain : ni `prix_achat_voir` ni `client_pii_voir` (ni code crm/sav : refus de module ALEC16 ensuite).
  const terrain = await session(testInfo, 'alec15t', 'Commercial terrain')
  const t = await agentSql(terrain, cid, Q)
  expect([t.allow_price, t.allow_pii, t.n_permissions > 0], 'Commercial terrain : droits lus par /auth/me/').toEqual([false, false, true])
  for (const [q, motif] of [[Q[0], PRIX], [Q[1], PRIX], [Q[2], PII], [Q[3], PRIX]]) {
    expect(t.cas[q].refus, `Commercial terrain : ${q}`).toMatch(motif)
    expect(t.cas[q].outil_refuse, `Commercial terrain : ${q} refusée sans exécution`).toBe(true)
  }
  // Utilisateur (rôle livré : crm_voir + client_pii_voir, sans prix_achat_voir ni portée) : coût et OCR refusés,
  // coordonnées et count(*) acceptés.
  const user = await session(testInfo, 'alec15u', 'Utilisateur')
  const u = await agentSql(user, cid, Q)
  expect([u.allow_price, u.allow_pii], 'Utilisateur : droits').toEqual([false, true])
  for (const q of [Q[0], Q[1], Q[3]]) {
    expect(u.cas[q].refus, `Utilisateur : ${q}`).toMatch(PRIX)
    expect(u.cas[q].outil_refuse, `Utilisateur : ${q} sans exécution`).toBe(true)
  }
  for (const q of [Q[2], Q[4]]) {
    expect(u.cas[q].refus, `Utilisateur : ${q} accepté`).toBeUndefined()
    expect(u.cas[q].securise, `Utilisateur : ${q} filtré par société`).toContain(`company_id = ${cid}`)
    expect(u.cas[q].outil_refuse || /"contenu": "Error/.test(u.cas[q].outil), `Utilisateur : ${q} exécuté`).toBe(false)
  }
  // Directeur : les 4 acceptées, réécrites sur la société (exécutées par l'outil sur la base du rejeu).
  const dir = await session(testInfo, 'alec15d', 'Directeur')
  const d = await agentSql(dir, cid, Q)
  expect([d.allow_price, d.allow_pii], 'Directeur : droits').toEqual([true, true])
  for (const q of Q) {
    expect(d.cas[q].refus, `Directeur : ${q} accepté`).toBeUndefined()
    expect(d.cas[q].securise, `Directeur : ${q} filtré par société`).toContain(`company_id = ${cid}`)
    expect(d.cas[q].outil_refuse, `Directeur : ${q} passe la garde de l'outil`).toBe(false)
  }
  for (const q of [Q[0], Q[2], Q[3], Q[4]]) expect(/"contenu": "Error/.test(d.cas[q].outil), `Directeur : ${q} exécuté : ${d.cas[q].outil}`).toBe(false)
})

etape('PF6.4.ALEC16', ['ALEC16'], async ({ testInfo }) => {
  sondeApres(testInfo, '014')
  const cid = await societe()
  const FAC = 'SELECT reference FROM ventes_facture'
  const DEV = 'SELECT reference FROM ventes_devis'
  const CH = 'SELECT reference FROM installations_installation'
  const tech = await session(testInfo, 'alec16t', 'Technicien')
  const t = await agentSql(tech, cid, [FAC, CH])
  expect(t.cas[FAC].refus, 'Technicien : ventes_facture refusée (module)').toMatch(/droit du module manquant/)
  expect(t.cas[CH].refus, 'Technicien : installations_installation refusée (portée équipe)').toMatch(/Portee restreinte/)
  expect([t.cas[FAC].outil_refuse, t.cas[CH].outil_refuse], 'Technicien : sans exécution').toEqual([true, true])
  const com = await session(testInfo, 'alec16c', 'Commercial')
  const c = await agentSql(com, cid, [DEV])
  expect(c.cas[DEV].refus, 'Commercial (soi) : ventes_devis refusée (portée)').toMatch(/Portee restreinte/)
  expect(c.cas[DEV].outil_refuse, 'Commercial : sans exécution').toBe(true)
  const dir = await session(testInfo, 'alec16d', 'Directeur')
  const d = await agentSql(dir, cid, [FAC, DEV])
  for (const q of [FAC, DEV]) {
    expect(d.cas[q].refus, `Directeur : ${q} accepté`).toBeUndefined()
    expect(d.cas[q].securise, `Directeur : ${q} réécrit sur la société`).toContain(`company_id = ${cid}`)
    expect(d.cas[q].outil_refuse, `Directeur : ${q} passe l'outil`).toBe(false)
  }
})

// ── PF6.4 — journal hors ligne (C-ALEC-019) et fiche technicien (C-ALEC-023) ────────────────────────────────────
etape('PF6.4.ALEC21', ['ALEC21'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, '019')
  const m = marque()
  const a = await session(testInfo, 'alec21a', 'Commercial')
  const b = await session(testInfo, 'alec21b', 'Commercial')
  const dir = await session(testInfo, 'alec21d', 'Directeur')
  const x = await py(`from apps.offlinesync.models import OfflineOperation as O
oa = O.objects.create(company_id=${SOC}, module='visites', op_type='visite.mesures', client_op_id='alec21-a-${m}', user_id=${a.id}, statut=O.Statut.CONFLIT)
ob = O.objects.create(company_id=${SOC}, module='visites', op_type='visite.mesures', client_op_id='alec21-b-${m}', user_id=${b.id}, statut=O.Statut.CONFLIT)
sortie(dict(a=oa.pk, b=ob.pk, statut=ob.statut, resolution=ob.resolution))`)
  const J = `${API}/offlinesync/operations/`
  let ui = null
  try {
    const idsA = (await lignes(a.ctx, J)).map((o) => o.id)
    expect(idsA, 'Commercial A : ses opérations seulement').toEqual([x.a])
    expect(await statut(a.ctx, `${J}${x.b}/`), 'Commercial A : détail de B').toBe(404)
    const res = await a.ctx.post(`${J}${x.b}/resoudre/`, { ...T, data: { choix: 'serveur' } })
    expect(res.status(), `Commercial A : résoudre l'opération de B ${(await res.text()).slice(0, 200)}`).toBe(404)
    const relue = await py(`from apps.offlinesync.models import OfflineOperation as O
o = O.objects.get(pk=${x.b})
sortie(dict(statut=o.statut, resolution=o.resolution))`)
    expect(relue, 'persistance : opération de B inchangée').toEqual({ statut: x.statut, resolution: x.resolution })
    const idsD = (await lignes(dir.ctx, J)).map((o) => o.id)
    expect([idsD.includes(x.a), idsD.includes(x.b)], 'Directeur : les deux opérations').toEqual([true, true])
    expect(await statut(dir.ctx, `${J}${x.b}/`), 'Directeur : détail de B').toBe(200)
    // Écran des conflits en Commercial A : son conflit, jamais celui de B.
    ui = await pageSous(context, suivi, testInfo, a)
    await ui.p.goto('/synchro/conflits')
    await expect(ui.p.locator(`input[name="conflit-${x.a}"]`).first()).toBeVisible({ timeout: 30_000 })
    await expect(ui.p.locator(`input[name="conflit-${x.b}"]`)).toHaveCount(0)
  } finally {
    if (ui) await ui.ctx.close().catch(() => undefined)
    await py(`from apps.offlinesync.models import OfflineOperation as O
O.objects.filter(pk__in=[${x.a}, ${x.b}]).delete()
sortie(1)`).catch(() => null)
  }
})

etape('PF6.4.ALEC27', ['ALEC27'], async ({ testInfo }) => {
  sondeApres(testInfo, '023')
  const m = marque()
  const t1 = await session(testInfo, 'alec27t1', 'Technicien')
  const t2 = await session(testInfo, 'alec27t2', 'Technicien')
  const r = await session(testInfo, 'alec27r', 'Technicien responsable')
  const dir = await session(testInfo, 'alec27d', 'Directeur')
  const x = await py(`from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
cl = Client.objects.create(company_id=${SOC}, nom='Client ALEC27 ${m}')
i = Installation.objects.create(company_id=${SOC}, reference='CH-ALEC27-${m}', client=cl)
it = Intervention.objects.create(company_id=${SOC}, installation=i, type_intervention=Intervention.Type.DEPANNAGE, technicien_id=${t2.id}, statut=Intervention.Statut.TERMINEE)
sortie(dict(inst=i.pk, client=cl.pk))`)
  const url = `${API}/reporting/insights/technicien-scorecard/?technicien=${t2.id}`
  try {
    expect(await statut(t1.ctx, url), 'Technicien T1 : fiche du collègue T2').toBe(403)
    const refus = await r.ctx.get(url, T)
    expect(refus.status(), 'Technicien responsable sans subordonné : T2 hors sous-arbre').toBe(404)
    expect((await refus.json()).detail).toBe('Technicien introuvable.')
    expect(await statut(dir.ctx, url), 'Directeur').toBe(200)
  } finally {
    await py(`from apps.installations.models import Installation
from apps.crm.models import Client
Installation.objects.filter(pk=${x.inst}).delete(); Client.objects.filter(pk=${x.client}).delete()
sortie(1)`).catch(() => null)
  }
})
