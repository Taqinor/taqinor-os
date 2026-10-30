// ALEA26 — acceptation en direct du groupe ALEA (audit lead) : rejeu, sur la pile locale, du parcours
// lead → fiche → relance → visite → feu vert (étapes P1.2, P1.3, P1.5, P2.2, P2.3, P3.1, P3.4, P3.5, P3.7,
// P5.3 du plan). Comptes `alea26_*` (Commercial terrain, Technicien responsable) créés par
// `manage.py shell` (E2E_DJANGO_EXEC) avec un mot de passe d'essai local, désactivés en fin de spec ;
// données `ALEA26 …` d'essai supprimées ensuite. Aucune donnée de production.
//
// Chaque geste est relu par GET / en base (clause persistance). L'horloge de la pile n'est pas pilotable :
// « touche due vendredi consultée un dimanche » (P2.3) est rejouée par un JOUR FÉRIÉ société posé sur
// aujourd'hui (même chemin de code, `jours_ouvres_entre`), retiré ensuite.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawn } from 'node:child_process'
import { groupe } from './_oracles.js'
import { API_DJANGO, PNG_1PX, boutonNouveauLead, gotoLeads, isoDansJours, lireJson, listeDe } from '../helpers.js'

const etape = groupe('ALEA', ['ALEA26', 'ALEA5', 'ALEA6', 'ALEA7', 'ALEA8', 'ALEA9', 'ALEA10', 'ALEA12', 'ALEA16', 'ALEA17', 'ALEA18', 'ALEA19', 'ALEA29', 'ALEA32'])
test.describe.configure({ timeout: 600_000 })

const PW = 'Alea26-essai-local-2026!'
const T = { timeout: 120_000 }
const NOM = 'ALEA26'

/** Un `manage.py shell` persistant : code en base64 par ligne, réponse `@@R<json>`. */
const SERVEUR = [
  'import sys, json, base64, io, contextlib, traceback',
  'ns = {}',
  "print('@@PRET', flush=True)",
  'for ligne in sys.stdin:',
  '    ligne = ligne.strip()',
  '    if not ligne: continue',
  '    buf = io.StringIO()',
  '    try:',
  '        with contextlib.redirect_stdout(buf):',
  '            exec(base64.b64decode(ligne).decode(), ns)',
  "        sortie = {'ok': True, 'out': buf.getvalue()}",
  '    except BaseException:',
  "        sortie = {'ok': False, 'out': buf.getvalue(), 'err': traceback.format_exc()[-1800:]}",
  "    print('@@R' + json.dumps(sortie), flush=True)",
].join('\n')
let serveur = null
const attentes = []
let tampon = ''
function demarrerServeur() {
  if (serveur) return serveur.pret
  const [cmd, ...args] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const proc = spawn(cmd, [...args, 'python', 'manage.py', 'shell', '-c', SERVEUR], { stdio: ['pipe', 'pipe', 'ignore'] })
  let pretOk
  const pret = new Promise((r) => { pretOk = r })
  proc.stdout.on('data', (d) => {
    tampon += d.toString()
    let i
    while ((i = tampon.indexOf('\n')) >= 0) {
      const l = tampon.slice(0, i).trim()
      tampon = tampon.slice(i + 1)
      if (l === '@@PRET') pretOk()
      else if (l.startsWith('@@R')) attentes.shift()?.(JSON.parse(l.slice(3)))
    }
  })
  serveur = { proc, pret }
  return pret
}
async function py(code) {
  await demarrerServeur()
  const rep = await new Promise((resolve) => {
    attentes.push(resolve)
    serveur.proc.stdin.write(`${Buffer.from(`import json\n${code}`).toString('base64')}\n`)
  })
  if (!rep.ok) throw new Error(`shell serveur : ${rep.err}`)
  const l = rep.out.split('\n').filter((x) => x.startsWith('@@')).pop()
  return l ? JSON.parse(l.slice(2)) : null
}
const PRELUDE = `
import datetime
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.visites.models import VisiteTerrain
U = get_user_model()
def sortie(o): print('@@' + json.dumps(o, default=str))
`
const base = (testInfo) => testInfo.project.use.baseURL
const ctxCache = new Map()
async function api(testInfo, username) {
  if (ctxCache.has(username)) return ctxCache.get(username)
  const c = await pwRequest.newContext({ baseURL: base(testInfo) })
  await expect(async () => {
    const r = await c.post(`${API_DJANGO}/token/`, { data: { username, password: PW } })
    expect(r.status(), `connexion de ${username}`).toBe(200)
  }).toPass({ intervals: [10_000, 20_000, 30_000], timeout: 240_000 })
  ctxCache.set(username, c)
  return c
}

let monde = null
async function monter() {
  if (monde) return monde
  monde = await py(`${PRELUDE}
ids = {}
for nom, role in (('alea26_terrain', 70), ('alea26_techresp', 5)):
    u, _ = U.objects.get_or_create(username=nom, defaults=dict(company_id=1, role_id=role))
    u.company_id = 1; u.role_id = role; u.is_active = True; u.email = nom + '@alea26.test'
    u.must_change_password = False; u.failed_login_count = 0; u.locked_until = None; u.set_password('${PW}'); u.save()
    ids[nom] = u.id
sortie(dict(ids=ids))`)
  return monde
}
let seq = 0
const tel = () => { seq += 1; return `+2126${String(Date.now() + seq).slice(-8)}` }
async function nouveauLead(proprietaireId, suffixe = '', extra = '') {
  return py(`${PRELUDE}
l = Lead.objects.create(company_id=1, nom='${NOM} ${suffixe}', prenom='Essai', ville='Casablanca', telephone='${tel()}', owner_id=${proprietaireId}${extra})
sortie(l.id)`)
}
test.afterAll(async () => {
  try {
    await py(`${PRELUDE}
from django.apps import apps as dj
from apps.calepinage.models import Calepinage
from apps.calepinage.services.parametres import enregistrer_parametres
from authentication.models import Company
ls = Lead.objects.filter(company_id=1, nom__startswith='${NOM}')
for c in Calepinage.objects.filter(lead_id__in=ls.values('id')): c.delete()
VisiteTerrain.objects.filter(lead_id__in=ls.values('id')).delete()
try: ls.delete()
except Exception as e: print('lead delete', e)
dj.get_model('entites', 'Entite').objects.filter(nom__startswith='${NOM}').delete()
dj.get_model('notifications', 'Holiday').objects.filter(nom__startswith='${NOM}').delete()
enregistrer_parametres(Company.objects.get(pk=1), {'presets': {}})
U.objects.filter(username__startswith='alea26_').update(is_active=False)
sortie('ok')`)
  } catch { /* nettoyage au mieux */ }
  serveur?.proc.stdin.end()
})

/** Ouvre la fiche du lead et déplie la section Contact (repliée par défaut quand elle est complète). */
async function ouvrirFicheContact(page, id) {
  await page.goto(`/crm/leads/${id}`)
  await expect(page.locator('.modal-title, h1, h2').filter({ hasText: /Lead —/ }).first()).toBeVisible({ timeout: 60_000 })
  const lat = page.locator('#lf-gps-lat')
  if (!(await lat.isVisible().catch(() => false))) {
    await page.locator('section.lw-section').filter({ has: page.locator('.lw-section-title', { hasText: /^Contact$/ }) }).locator('.lw-section-head').click()
  }
  await expect(lat).toBeVisible({ timeout: 30_000 })
}

// ── P1.2 — créer un lead depuis Leads ; `entite` d'une autre société refusée comme un id absent (ALEA16) ──
etape('P1.2', ['ALEA16'], async ({ page, suivi }) => {
  await gotoLeads(page)
  // Création par la vraie fenêtre « Nouveau lead » (attente de l'enregistrement portée à 60 s).
  const nom = `${NOM} UI ${Date.now()}`
  await boutonNouveauLead(page).click()
  const fenetre = page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })
  await expect(fenetre.getByRole('heading', { name: 'Nouveau lead' })).toBeVisible()
  await fenetre.locator('#lf-nom').fill(nom)
  await fenetre.locator('#lf-ville').fill('Casablanca')
  await fenetre.getByRole('button', { name: 'Créer le lead' }).click()
  await expect(fenetre).toHaveCount(0, { timeout: 60_000 })
  suivi.verifie(5)
  await expect(page.getByText(nom).first()).toBeVisible({ timeout: 30_000 })
  const trouves = listeDe(await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/?search=${encodeURIComponent(nom)}`), 'recherche lead'))
  const lead = trouves.find((l) => l.nom === nom)
  expect(lead, 'lead créé relu par GET').toBeTruthy()
  // Entité d'une autre société (43) : refus identique à un id absent.
  const e = await py(`${PRELUDE}
from django.apps import apps as dj
E = dj.get_model('entites', 'Entite')
x = E.objects.create(company_id=43, nom='${NOM} entite etrangere', code='ALEA26X')
sortie(x.id)`)
  suivi.attendre(/\/crm\/leads\/\d+\/$/, 404)
  suivi.attendre(/\/crm\/leads\/\d+\/$/, 400)
  const etrangere = await page.request.patch(`${API_DJANGO}/crm/leads/${lead.id}/`, { data: { entite: e } })
  const absente = await page.request.patch(`${API_DJANGO}/crm/leads/${lead.id}/`, { data: { entite: 99999999 } })
  expect(etrangere.status(), 'entité étrangère').toBe(absente.status())
  expect([400, 404]).toContain(etrangere.status())
  const corpsE = await etrangere.json()
  const corpsA = await absente.json()
  const norm = (c) => JSON.stringify(c.entite).split(String(e)).join('N').split('99999999').join('N').replace(/\s/g, ' ')
  expect(norm(corpsE), 'même message d entité qu un id absent').toBe(norm(corpsA))
  expect(corpsE.error?.code, 'même code d erreur qu un id absent').toBe(corpsA.error?.code)
  const relu = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${lead.id}/`), 'lead relu')
  expect(relu.entite ?? null, 'entité inchangée en base').toBeNull()
})

// ── P1.5 — coller un GPS à 7 décimales dans la fiche (ALEA17, ALEA18, ALEA29) ─────────────────────────────
etape('P1.5', ['ALEA17', 'ALEA18', 'ALEA29'], async ({ page }) => {
  const id = await nouveauLead((await py(`${PRELUDE}\nsortie(U.objects.get(username='demo_admin').id)`)), 'GPS')
  const patchs = []
  page.on('request', (r) => {
    if (r.method() === 'PATCH' && new RegExp(`/crm/leads/${id}/$`).test(r.url())) patchs.push(r.postData())
  })
  const statuts = []
  page.on('response', (r) => {
    if (r.request().method() === 'PATCH' && new RegExp(`/crm/leads/${id}/$`).test(r.url())) statuts.push(r.status())
  })
  await ouvrirFicheContact(page, id)
  const lat = page.locator('#lf-gps-lat')
  await lat.fill('33.5731104')
  await page.locator('#lf-gps-lng').fill('-7.5898434')
  await expect(page.getByText('✓ Enregistré').first()).toBeVisible({ timeout: 30_000 })
  await page.waitForTimeout(6000)
  expect(patchs.length, `un seul PATCH (vu : ${patchs.join(' | ')})`).toBe(1)
  expect(statuts, 'PATCH 200').toEqual([200])
  await expect(page.locator('#lf-gps-lat')).toHaveValue(/^33\.57311/)
  expect(await page.locator('.field-error, [role="alert"]').filter({ hasText: /format|décimal|chiffres/i }).count(), 'aucune erreur résiduelle').toBe(0)
  const lu = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${id}/`), 'lead relu')
  expect(Number(lu.gps_lat)).toBeCloseTo(33.57311, 6)
  expect(Number(lu.gps_lng)).toBeCloseTo(-7.589843, 6)
  expect(String(lu.gps_lat), 'arrondi à 6 décimales').toMatch(/^33\.57311\d?$/)
  // F5 : valeurs identiques ; enregistrer sans toucher → aucune requête d'écriture.
  patchs.length = 0
  await ouvrirFicheContact(page, id)
  await expect(page.locator('#lf-gps-lat')).toHaveValue(/^33\.57311/)
  await expect(page.locator('#lf-gps-lng')).toHaveValue(/^-7\.58984/)
  await page.waitForTimeout(4000)
  expect(patchs.length, 'aucune écriture sans modification').toBe(0)
  // ALEA29 : un PATCH {} n'avance ni date_modification ni updated_by.
  const avant = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${id}/`), 'avant PATCH {}')
  expect((await page.request.patch(`${API_DJANGO}/crm/leads/${id}/`, { data: {} })).status()).toBe(200)
  const apres = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${id}/`), 'après PATCH {}')
  expect(apres.date_modification, 'date_modification inchangée par PATCH {}').toBe(avant.date_modification)
  // Facture « 450,555 » : arrondie (ALEA17), pas de 400.
  const f = await page.request.patch(`${API_DJANGO}/crm/leads/${id}/`, { data: { facture_hiver: '450,555' } })
  expect(f.status(), await f.text()).toBe(200)
  expect(Number((await f.json()).facture_hiver)).toBeCloseTo(450.56, 2)
})

// ── P1.3 — deux modifications de la note : deux lignes au chatter (ALEA19) ─────────────────────────────────
etape('P1.3', ['ALEA19'], async ({ page }) => {
  const id = await nouveauLead(1, 'Chatter')
  for (const note of ['AAA', 'BBB']) {
    expect((await page.request.patch(`${API_DJANGO}/crm/leads/${id}/`, { data: { note } })).status()).toBe(200)
  }
  const lire = async () => listeDe(await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${id}/historique/`), 'historique'))
    .filter((a) => a.field === 'note')
  let lignes = await lire()
  expect(lignes.length, 'deux lignes de chatter pour la note').toBe(2)
  expect(lignes.some((a) => a.old_value === 'AAA' && a.new_value === 'BBB'), 'AAA → BBB lisible').toBeTruthy()
  // Un PATCH identique n'ajoute rien ; la fiche rouverte montre l'ancien texte.
  expect((await page.request.patch(`${API_DJANGO}/crm/leads/${id}/`, { data: { note: 'BBB' } })).status()).toBe(200)
  lignes = await lire()
  expect(lignes.length, 'second PATCH identique : aucune entrée').toBe(2)
  await page.goto(`/crm/leads/${id}`)
  await expect(page.getByText(/AAA\s*→\s*BBB/).first(), 'chatter de la fiche rouverte : ancien → nouveau').toBeVisible({ timeout: 60_000 })
})

// ── P2.2 — poser une relance et la reporter : la date du lead est celle de la touche ───────────────────────
etape('P2.2', ['ALEA26'], async ({ page }) => {
  const id = await nouveauLead(1, 'Relance')
  await py(`${PRELUDE}
l = Lead.objects.get(pk=${id}); d = timezone.localdate()
RelanceEtape.objects.create(company_id=1, lead=l, cadence='contact', ordre=2, canal=RelanceEtape.Canal.APPEL, libelle='Appel ALEA26',
  due_at=timezone.now() + datetime.timedelta(hours=2), due_date=d, cadence_depart=timezone.now())
Lead.objects.filter(pk=l.pk).update(relance_date=d); sortie('ok')`)
  // Premier jour OUVRÉ (lundi-vendredi) à J+9 ou après : la touche est recalée sur la fenêtre société.
  const d = new Date(); d.setDate(d.getDate() + 9)
  while ([0, 6].includes(d.getDay())) d.setDate(d.getDate() + 1)
  const j9 = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const r = await page.request.patch(`${API_DJANGO}/crm/leads/${id}/`, { data: { relance_date: j9 } })
  expect(r.status(), await r.text()).toBe(200)
  const lu = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${id}/`), 'lead relu')
  const touches = listeDe(await lireJson(await page.request.get(`${API_DJANGO}/crm/relance-etapes/?lead=${id}`), 'touches')).filter((t) => t.libelle === 'Appel ALEA26')
  expect(touches.length).toBe(1)
  expect(String(lu.relance_date).slice(0, 10), 'date du lead').toBe(j9)
  expect(String(touches[0].due_date).slice(0, 10), 'date de la touche = date du lead').toBe(j9)
  // Observation (non bloquante) : report vers un DIMANCHE — la touche est recalée par la fenêtre société.
  const dim = new Date(); dim.setDate(dim.getDate() + 14)
  while (dim.getDay() !== 0) dim.setDate(dim.getDate() + 1)
  const jd = `${dim.getFullYear()}-${String(dim.getMonth() + 1).padStart(2, '0')}-${String(dim.getDate()).padStart(2, '0')}`
  await page.request.patch(`${API_DJANGO}/crm/leads/${id}/`, { data: { relance_date: jd } })
  const lu2 = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${id}/`), 'lead relu (dimanche)')
  const t2 = listeDe(await lireJson(await page.request.get(`${API_DJANGO}/crm/relance-etapes/?lead=${id}`), 'touches')).find((t) => t.libelle === 'Appel ALEA26')
  test.info().annotations.push({ type: 'observation dimanche', description: `lead=${String(lu2.relance_date).slice(0, 10)} touche=${String(t2.due_date).slice(0, 10)} (cible ${jd})` })
  console.log(`[ALEA P2.2] report vers un dimanche : lead=${String(lu2.relance_date).slice(0, 10)} touche=${String(t2.due_date).slice(0, 10)} cible=${jd}`)
})

// ── P2.3 — « en retard » : badge, drapeau lead, cockpit d'accord (ALEA32) ───────────────────────────────────
etape('P2.3', ['ALEA32'], async ({ page }) => {
  const m = await monter()
  const owner = m.ids.alea26_techresp
  const id = await nouveauLead(owner, 'Retard')
  const hier = isoDansJours(-1)
  await py(`${PRELUDE}
from django.apps import apps as dj
l = Lead.objects.get(pk=${id})
RelanceEtape.objects.create(company_id=1, lead=l, cadence='generique', ordre=1, canal=RelanceEtape.Canal.APPEL, libelle='Retard ALEA26',
  due_at=timezone.now() - datetime.timedelta(days=1), due_date=datetime.date.fromisoformat('${hier}'))
dj.get_model('notifications', 'Holiday').objects.filter(nom__startswith='${NOM}').delete()
sortie('ok')`)
  const lectures = async () => {
    const touche = listeDe(await lireJson(await page.request.get(`${API_DJANGO}/crm/relance-etapes/?lead=${id}`), 'touches')).find((t) => t.libelle === 'Retard ALEA26')
    const lead = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${id}/`), 'lead')
    const ctl = await lireJson(await page.request.get(`${API_DJANGO}/crm/relance-etapes/controle/?jours=14&owner=${owner}`), 'cockpit')
    return { badge: !!touche.overdue, drapeau: !!lead.touche_en_retard, cockpit: ctl.exceptions.en_retard.total }
  }
  // Jour ouvré écoulé depuis l'échéance : en retard partout.
  const ouvre = await lectures()
  // Aujourd'hui férié société (équivalent « consulté un dimanche ») : aucun jour compté, en retard nulle part.
  await py(`${PRELUDE}
from django.apps import apps as dj
dj.get_model('notifications', 'Holiday').objects.create(company_id=1, nom='${NOM} ferie', date=timezone.localdate()); sortie('ok')`)
  const ferie = await lectures()
  await py(`${PRELUDE}
from django.apps import apps as dj
dj.get_model('notifications', 'Holiday').objects.filter(nom__startswith='${NOM}').delete(); sortie('ok')`)
  test.info().annotations.push({ type: 'lectures', description: JSON.stringify({ ouvre, ferie }) })
  // Si hier est non ouvré (week-end), « ouvre » n'est pas en retard non plus : l'accord reste l'oracle.
  expect(ouvre.badge, 'badge et drapeau lead disent pareil (jour ouvré)').toBe(ouvre.drapeau)
  expect(ferie.badge, 'férié : badge pas en retard').toBe(false)
  expect(ferie.drapeau, 'férié : drapeau lead pas en retard').toBe(false)
  expect(ferie.cockpit, 'férié : cockpit ne compte pas la touche').toBe(0)
  expect(ouvre.cockpit > 0, 'jour ouvré écoulé : cockpit d accord avec le badge').toBe(ouvre.badge)
})

// ── gestes de visite partagés ───────────────────────────────────────────────────────────────────────────────
const MESURES = {
  toiture: { longueur_m: 12.5, largeur_m: 8, pente_deg: 15, toit_plat: false, orientation: 'sud', type_couverture: 'tuile', etat_couverture: 'bon' },
  tableau: { calibre_disjoncteur_a: 63, type_alimentation: 'mono', emplacements_libres: 4 },
  local_onduleur: { largeur_mur_cm: 200, hauteur_mur_cm: 250, profondeur_degagement_cm: 80, distance_tableau_m: 5, local_abrite: true, local_ventile: true },
}
const V = `${API_DJANGO}/visites/visites`
async function photo(ctx, id, slot, nom) {
  return lireJson(await ctx.post(`${V}/${id}/photos/`, { ...T, multipart: { slot_code: slot, fichier: { name: nom, mimeType: 'image/png', buffer: PNG_1PX } } }), `photo ${slot}`)
}
async function remplir(ctx, id) {
  for (const [categorie, valeurs] of Object.entries(MESURES)) {
    await lireJson(await ctx.patch(`${V}/${id}/mesures/`, { ...T, data: { categorie, valeurs } }), `mesures ${categorie}`)
  }
  const visite = await lireJson(await ctx.get(`${V}/${id}/`, T), 'visite')
  for (const bloc of visite.checklist) {
    for (const slot of bloc.slots.filter((s) => s.requis)) {
      for (let i = 0; i < (slot.min_photos || 1); i += 1) await photo(ctx, id, slot.code, `${slot.code}-${i}.png`)
    }
  }
  return lireJson(await ctx.get(`${V}/${id}/`, T), 'visite remplie')
}
async function visiteTerminee(ctx, leadId) {
  const cree = await lireJson(await ctx.post(`${V}/`, { ...T, data: { lead: leadId } }), 'créer la visite')
  const v = await remplir(ctx, cree.id)
  expect(v.completude.complet, `visite complète (${JSON.stringify(v.completude.manquants)})`).toBe(true)
  const t = await lireJson(await ctx.post(`${V}/${cree.id}/terminer/`, { ...T, data: {} }), 'terminer')
  expect(t.statut).toBe('terminee')
  return cree.id
}
const statutVisite = async (ctx, id) => (await lireJson(await ctx.get(`${V}/${id}/`, T), 'visite')).statut

// ── P3.1 — planifier la visite deux fois : une visite, une note (ALEA9, ALEA10) ─────────────────────────────
etape('P3.1', ['ALEA9', 'ALEA10'], async ({ testInfo, suivi }) => {
  const m = await monter()
  const terrain = await api(testInfo, 'alea26_terrain')
  const id = await nouveauLead(m.ids.alea26_terrain, 'Plan')
  // Rendez-vous en attente (brouillon daté à J+5), comme dans le test ALEA9.
  await py(`${PRELUDE}
VisiteTerrain.objects.create(company_id=1, lead_id=${id}, commercial_id=${m.ids.alea26_terrain}, statut='brouillon', date_prevue=timezone.localdate() + datetime.timedelta(days=5)); sortie('ok')`)
  suivi.attendre(/\/visites\/visites\//, 400)
  suivi.attendre(/\/visites\/visites\//, 409)
  const passe = await terrain.post(`${V}/`, { ...T, data: { lead: id, date_prevue: isoDansJours(-1) } })
  expect([400, 409], `date passée refusée (statut observé ${passe.status()})`).toContain(passe.status())
  expect(JSON.stringify(await passe.json())).toContain('date_prevue')
  const notesDe = () => py(`${PRELUDE}
sortie([a.body for a in LeadActivity.objects.filter(lead_id=${id}).order_by('id') if 'isite' in (a.body or '')])`)
  const attente = await py(`${PRELUDE}
sortie(VisiteTerrain.objects.get(lead_id=${id}).id)`)
  const un = await lireJson(await terrain.post(`${V}/`, { ...T, data: { lead: id, date_prevue: isoDansJours(1) } }), 'planifier')
  expect(un.id, 'le rendez-vous en attente est déplacé, pas dupliqué').toBe(attente)
  const notes1 = await notesDe()
  expect(notes1.length, `une seule note de chatter (${JSON.stringify(notes1)})`).toBe(1)
  expect(notes1[0]).toMatch(/^Visite technique planifiée le/)
  const deux = await lireJson(await terrain.post(`${V}/`, { ...T, data: { lead: id, date_prevue: isoDansJours(2) } }), 'replanifier')
  expect(deux.id, 'replanifier déplace encore le même rendez-vous').toBe(un.id)
  const etat = await py(`${PRELUDE}
nb = VisiteTerrain.objects.filter(lead_id=${id}).count()
v = VisiteTerrain.objects.get(lead_id=${id}); sortie(dict(nb=nb, date=v.date_prevue))`)
  expect(etat.nb, 'une seule visite en base').toBe(1)
  expect(String(etat.date).slice(0, 10)).toBe(isoDansJours(2))
  // PATCH date_prevue vers le passé sur le brouillon : refusé, date inchangée.
  const patch = await terrain.patch(`${V}/${un.id}/`, { ...T, data: { date_prevue: isoDansJours(-1) } })
  expect([400, 409], 'date passée en PATCH').toContain(patch.status())
  expect(JSON.stringify(await patch.json())).toContain('date_prevue')
  const relu = await lireJson(await terrain.get(`${V}/${un.id}/`, T), 'visite relue')
  expect(String(relu.date_prevue).slice(0, 10)).toBe(isoDansJours(2))
})

// ── P3.4 — valider un brouillon est refusé en nommant `statut` (ALEA6) ──────────────────────────────────────
etape('P3.4', ['ALEA6'], async ({ testInfo, suivi }) => {
  const m = await monter()
  const terrain = await api(testInfo, 'alea26_terrain')
  const bureau = await api(testInfo, 'alea26_techresp')
  const id = await nouveauLead(m.ids.alea26_terrain, 'Brouillon')
  const v = await lireJson(await terrain.post(`${V}/`, { ...T, data: { lead: id } }), 'brouillon')
  suivi.attendre(/\/visites\/visites\/\d+\/(valider|renvoyer)\//, 409)
  suivi.attendre(/\/visites\/visites\/\d+\/(valider|renvoyer)\//, 400)
  const r = await bureau.post(`${V}/${v.id}/valider/`, { ...T, data: {} })
  test.info().annotations.push({ type: 'statut HTTP', description: `valider brouillon → ${r.status()}` })
  expect([400, 409], 'refus de transition').toContain(r.status())
  expect(JSON.stringify(await r.json()), 'le refus nomme statut').toContain('statut')
  expect(await statutVisite(terrain, v.id), 'rien n\'a bougé').toBe('brouillon')
  const rv = await bureau.post(`${V}/${v.id}/renvoyer/`, { ...T, data: { photos: [], mesures: [], motif: 'x' } })
  expect([400, 409]).toContain(rv.status())
  expect(await statutVisite(terrain, v.id)).toBe('brouillon')
})

// ── P3.5 — terminer, qualification refusée après coup, renvoi, photo reprise sans suppression (ALEA7, ALEA12) ─
etape('P3.5', ['ALEA7', 'ALEA12'], async ({ testInfo, suivi }) => {
  const m = await monter()
  const terrain = await api(testInfo, 'alea26_terrain')
  const bureau = await api(testInfo, 'alea26_techresp')
  const id = await nouveauLead(m.ids.alea26_terrain, 'Terrain')
  const vid = await visiteTerminee(terrain, id)
  suivi.attendre(new RegExp(`/visites/visites/${vid}/`), 409)
  suivi.attendre(new RegExp(`/visites/visites/${vid}/`), 400)
  // ALEA7 : la qualification d'une visite terminée est refusée en nommant `statut` ; rien ne change.
  const q = await terrain.post(`${V}/${vid}/qualification/`, { ...T, data: { temperature: 'froid', devis: 'convient', decideur: 'seul', frein: 'aucun', declencheur: 'economies', rappel: 'demain_matin' } })
  expect([400, 409], 'qualification après terminée').toContain(q.status())
  expect(JSON.stringify(await q.json())).toContain('statut')
  const n = await terrain.patch(`${V}/${vid}/`, { ...T, data: { notes: 'x' } })
  expect([400, 409], 'notes après terminée').toContain(n.status())
  // Renvoi du bureau d'études sur une photo, puis reprise sans suppression.
  const avant = await lireJson(await terrain.get(`${V}/${vid}/`, T), 'visite')
  const slot = avant.checklist.flatMap((b) => b.slots).find((s) => s.code === 'toiture_vue_generale') || avant.checklist.flatMap((b) => b.slots).find((s) => s.requis && (s.photos || []).length)
  const media = slot.photos[0].id
  const rv = await lireJson(await bureau.post(`${V}/${vid}/renvoyer/`, { ...T, data: { photos: [media], mesures: [], motif: 'Reprendre la toiture.' } }), 'renvoyer')
  expect(rv.statut).toBe('a_refaire')
  const bloque = await terrain.post(`${V}/${vid}/terminer/`, { ...T, data: {} })
  expect(bloque.status(), 'terminer bloqué tant que la photo est à refaire').toBe(409)
  await photo(terrain, vid, slot.code, 'reprise.png')
  const apres = await lireJson(await terrain.get(`${V}/${vid}/`, T), 'visite reprise')
  const sl = apres.checklist.flatMap((b) => b.slots).find((s) => s.code === slot.code)
  expect(sl.etat, 'le slot quitte a_refaire').not.toBe('a_refaire')
  const fin = await lireJson(await terrain.post(`${V}/${vid}/terminer/`, { ...T, data: {} }), 'terminer à nouveau')
  expect(fin.statut).toBe('terminee')
  expect(await statutVisite(terrain, vid)).toBe('terminee')
})

// ── P3.7 — feu vert bureau d'études : retenir une variante (ALEA5, ALEA8) ───────────────────────────────────
etape('P3.7', ['ALEA5', 'ALEA8'], async ({ page, testInfo, suivi }) => {
  const m = await monter()
  const terrain = await api(testInfo, 'alea26_terrain')
  const bureau = await api(testInfo, 'alea26_techresp')
  const id = await nouveauLead(m.ids.alea26_terrain, 'FeuVert')
  const cal = await py(`${PRELUDE}
from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.parametres import enregistrer_parametres
from authentication.models import Company
enregistrer_parametres(Company.objects.get(pk=1), {'presets': {'feu_vert_bureau_etudes': True}})
c = Calepinage.objects.create(company_id=1, lead_id=${id})
v1 = CalepinageVariante.objects.create(company_id=1, calepinage=c, nom='V1')
v2 = CalepinageVariante.objects.create(company_id=1, calepinage=c, nom='V2')
v3 = CalepinageVariante.objects.create(company_id=1, calepinage=c, nom='V3')
sortie(dict(c=c.id, v=[v1.id, v2.id, v3.id]))`)
  const retenir = (vid) => page.request.post(`${API_DJANGO}/calepinage/calepinages/${cal.c}/variantes/${vid}/retenir/`, T)
  const retenue = (vid) => py(`${PRELUDE}
from apps.calepinage.models import CalepinageVariante
sortie(CalepinageVariante.objects.get(pk=${vid}).retenue)`)
  suivi.attendre(/\/calepinage\/calepinages\/\d+\/variantes\/\d+\/retenir\//, 400)
  suivi.attendre(/\/calepinage\/calepinages\/\d+\/variantes\/\d+\/retenir\//, 409)
  suivi.attendre(new RegExp('/visites/visites/\\d+/renvoyer/'), 403)
  const vid = await visiteTerminee(terrain, id)
  // Terminée mais pas validée : retenir refusée (feu_vert).
  const r1 = await retenir(cal.v[0])
  expect(r1.status(), 'retenir avant validation').toBe(400)
  expect(JSON.stringify(await r1.json())).toContain('feu_vert')
  expect(await retenue(cal.v[0]), 'rien n\'est retenu').toBe(false)
  // Valider en Technicien responsable : retenir accepté.
  await lireJson(await bureau.post(`${V}/${vid}/valider/`, { ...T, data: {} }), 'valider')
  const r2 = await retenir(cal.v[0])
  expect(r2.status(), await r2.text()).toBe(200)
  expect(await retenue(cal.v[0]), 'variante retenue après feu vert').toBe(true)
  // Renvoyer : le Commercial terrain 403, le Technicien responsable 200.
  const refus = await terrain.post(`${V}/${vid}/renvoyer/`, { ...T, data: { photos: [], mesures: [], motif: 'x' } })
  expect(refus.status(), 'Commercial terrain ne renvoie pas').toBe(403)
  expect(await statutVisite(bureau, vid), 'visite toujours validée après le 403').toBe('validee')
  const ok = await bureau.post(`${V}/${vid}/renvoyer/`, { ...T, data: { photos: [], mesures: [], motif: 'Reprendre.' } })
  expect(ok.status(), await ok.text()).toBe(200)
  expect(await statutVisite(bureau, vid)).toBe('a_refaire')
  // Retenir de nouveau (autre variante) : refusée, la porte s'est refermée.
  const r3 = await retenir(cal.v[1])
  expect(r3.status(), 'retenir après renvoi').toBe(400)
  expect(JSON.stringify(await r3.json())).toContain('feu_vert')
  expect(await retenue(cal.v[1])).toBe(false)
})

// ── P5.3 — le Commercial terrain n'écrit ni n'archive les leads (SROLE-1 / ASEC) ───────────────────────────
etape('P5.3', ['ALEA26'], async ({ testInfo, suivi }) => {
  const m = await monter()
  const terrain = await api(testInfo, 'alea26_terrain')
  const id = await nouveauLead(m.ids.alea26_terrain, 'Droits')
  suivi.attendre(/\/crm\/leads\//, 403)
  const patch = await terrain.patch(`${API_DJANGO}/crm/leads/${id}/`, { ...T, data: {} })
  const bulk = await terrain.post(`${API_DJANGO}/crm/leads/bulk/`, { ...T, data: { action: 'archive', ids: [id] } })
  const archive = await py(`${PRELUDE}\nsortie(Lead.objects.get(pk=${id}).is_archived)`)
  test.info().annotations.push({ type: 'observé', description: `PATCH {} → ${patch.status()} ; bulk archive → ${bulk.status()} ; archivé=${archive}` })
  expect(patch.status(), 'PATCH {} du Commercial terrain').toBe(403)
  expect(bulk.status(), 'bulk archive du Commercial terrain').toBe(403)
  expect(archive, 'le lead n\'est pas archivé').not.toBe(true)
})
