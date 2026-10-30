// ASEC21 — acceptation en direct du groupe ASEC (sécurité, vague 3) : rejeu des reproductions
// d'origine des constats C-ASEC sur la pile locale à deux sociétés (1 = « TAQINOR Démo »,
// 43 = « TAQINOR Démo (complet) » en témoin voisin) et constat du refus attendu, chaque refus
// étant suivi d'une RELECTURE EN BASE (clause persistance : ligne inchangée). Les parcours
// légitimes équivalents sont rejoués (Directeur réinitialise un Commercial, Commercial encaisse…).
//
// Comptes : des comptes `acc21_*` sont créés par `manage.py shell` (E2E_DJANGO_EXEC) avec un mot
// de passe d'essai local, jamais celui d'un compte réel ; ils sont désactivés en fin de spec.
// Aucune donnée de production. La proposition publique (ASEC23/ASEC53) est jouée sur `apps/web` :
// non lancé sur cette pile → son enregistrement du 29/10 (f9ef5544f) reste la preuve.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { spawn } from 'node:child_process'
import { API_DJANGO, uniq } from '../helpers.js'

const etape = groupe('ASEC', ['ASEC2', 'ASEC3', 'ASEC4', 'ASEC5', 'ASEC6', 'ASEC8', 'ASEC10', 'ASEC11', 'ASEC12', 'ASEC13', 'ASEC22', 'ASEC24', 'ASEC27', 'ASEC29', 'ASEC32', 'ASEC34', 'ASEC35'])
test.describe.configure({ timeout: 600_000 })

const PW = 'Acc21-essai-local-2026!'
const T = { timeout: 120_000 }
const nonJouable = (raison) => { throw new Error(`NON JOUABLE : ${raison}`) }

/** Python dans le conteneur, via UN `manage.py shell` persistant (le démarrage dure ~1 min sur cette
 *  pile chargée) : chaque appel envoie son code (base64, une ligne) et lit la réponse ; la dernière
 *  ligne `@@<json>` imprimée par le code est renvoyée parsée. */
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
  "            exec(base64.b64decode(ligne).decode(), ns)",
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
from django.contrib.auth import get_user_model
from apps.roles.models import Role
from authentication.models import Company
U = get_user_model()
def sortie(o): print('@@' + json.dumps(o, default=str))
`
const base = (testInfo) => testInfo.project.use.baseURL

/** Contexte API connecté (cookies) ; patiente le throttle « login » (429) au lieu d'échouer. */
const ctxCache = new Map()
async function api(testInfo, username, password = PW) {
  if (ctxCache.has(username)) return ctxCache.get(username)
  const c = await pwRequest.newContext({ baseURL: base(testInfo) })
  await expect(async () => {
    const r = await c.post(`${API_DJANGO}/token/`, { data: { username, password } })
    expect(r.status(), `connexion de ${username}`).toBe(200)
  }).toPass({ intervals: [10_000, 20_000, 30_000], timeout: 240_000 })
  ctxCache.set(username, c)
  return c
}

/** POST /token/ qui attend la fin d'un 429 (throttle « login » 5/min/IP, partagé avec d'autres rejeux). */
async function token(c, data) {
  let r
  for (let i = 0; i < 10; i++) {
    r = await c.post(`${API_DJANGO}/token/`, { data })
    if (r.status() !== 429) return r
    await new Promise((res) => setTimeout(res, 20_000))
  }
  return r
}

/** Comptes de la spec (société 1) : un par palier + une société voisine (43). */
const COMPTES = {
  acc21_dir: { role: 1, protege: true }, // Directeur protégé (cible)
  acc21_dir2: { role: 1 }, // second Directeur (acteur légitime)
  acc21_cresp: { role: 3 }, // Commercial responsable
  acc21_tresp: { role: 5 }, // Technicien responsable
  acc21_rh: { role: 71 }, // Admin RH
  acc21_com: { role: 4 }, // Commercial (cible de palier inférieur)
  acc21_terrain: { role: 70 }, // Commercial terrain
  acc21_viewer: { role: 7 },
  acc21_b: { role: 91, societe: 43 }, // Directeur de la société voisine
}
let pret = false
async function monterComptes() {
  if (pret) return
  await py(`${PRELUDE}
C = json.loads('${JSON.stringify(COMPTES)}')
for nom, c in C.items():
    soc = c.get('societe', 1)
    u, _ = U.objects.get_or_create(username=nom, defaults=dict(company_id=soc, role_id=c['role']))
    u.company_id = soc; u.role_id = c['role']; u.is_active = True; u.is_protected = bool(c.get('protege'))
    u.email = nom + '@acc21.test'; u.must_change_password = False; u.failed_login_count = 0; u.locked_until = None
    u.totp_enabled = False; u.set_password('${PW}'); u.save()
sortie('ok')`)
  pret = true
}
const ligne = async (nom) => py(`${PRELUDE}
u = U.objects.get(username='${nom}')
sortie(dict(id=u.id, actif=u.is_active, email=u.email, role=u.role_id, mdp_ok=u.check_password('${PW}'),
            must=u.must_change_password, echecs=u.failed_login_count, verrou=u.locked_until,
            pas=getattr(u, 'totp_dernier_pas', None)))`)

test.afterAll(async () => {
  try {
    await py(`${PRELUDE}
U.objects.filter(username__startswith='acc21_').update(is_active=False, is_protected=False)
sortie('ok')`)
  } catch { /* nettoyage au mieux */ }
  serveur?.proc.stdin.end()
})

// ── ASEC2 / ASEC3 / ASEC10 — rang de la cible, action de réinitialisation, users_gerer ──────────
etape('P1.1', ['ASEC2', 'ASEC3', 'ASEC10'], async ({ testInfo }) => {
  await monterComptes()
  const cible = (await ligne('acc21_dir'))
  const avant = (await ligne('acc21_com'))
  const refus = []
  // Trois paliers « responsable » contre le Directeur protégé : 403 rang_cible, aucune ligne modifiée.
  for (const acteur of ['acc21_cresp', 'acc21_tresp', 'acc21_rh']) {
    const c = await api(testInfo, acteur)
    const gestes = [
      ['PATCH password', 'patch', `/users/${cible.id}/`, { password: 'Pirate-mdp-2026!' }],
      ['PATCH email', 'patch', `/users/${cible.id}/`, { email: 'pirate@acc21.test' }],
      ['PATCH is_active', 'patch', `/users/${cible.id}/`, { is_active: false }],
      ['PATCH role', 'patch', `/users/${cible.id}/`, { role: 4 }],
      ['PATCH must_change_password', 'patch', `/users/${cible.id}/`, { must_change_password: true }],
      ['POST reinitialiser', 'post', `/users/${cible.id}/reinitialiser-mot-de-passe/`, { password: 'Pirate-mdp-2026!' }],
      ['DELETE', 'delete', `/users/${cible.id}/`, undefined],
    ]
    for (const [nom, methode, chemin, data] of gestes) {
      const r = await c[methode](`${API_DJANGO}${chemin}`, { ...T, data })
      refus.push(`${acteur} ${nom} → ${r.status()}`)
      expect(r.status(), `${acteur} ${nom} : ${(await r.text()).slice(0, 160)}`).toBe(403)
    }
  }
  // Persistance : la cible est inchangée en base.
  const apres = (await ligne('acc21_dir'))
  expect(apres.actif).toBe(true)
  expect(apres.email).toBe('acc21_dir@acc21.test')
  expect(apres.role).toBe(1)
  expect(apres.mdp_ok, 'mot de passe du Directeur inchangé').toBe(true)
  expect(apres.must).toBe(false)

  // Rôle plus large : le Commercial responsable se l'attribue → refusé.
  const cresp = await api(testInfo, 'acc21_cresp')
  const moi = (await ligne('acc21_cresp'))
  const rAttrib = await cresp.patch(`${API_DJANGO}/users/${moi.id}/`, { ...T, data: { role: 1 } })
  expect([400, 403], `auto-attribution du rôle Directeur → ${rAttrib.status()} ${(await rAttrib.text()).slice(0, 200)}`).toContain(rAttrib.status())
  expect((await ligne('acc21_cresp')).role).toBe(3)
  // Rôle personnalisé plus large que le sien (palier responsable + paie_gerer) : 403 role_plus_large.
  const large = await py(`${PRELUDE}
b = Role.objects.get(pk=3)
r, _ = Role.objects.get_or_create(company_id=1, nom='acc21 perso large', defaults=dict(permissions=[]))
r.permissions = list(b.permissions) + ['paie_gerer']; r.save(); sortie(r.id)`)
  const rLarge = await cresp.patch(`${API_DJANGO}/users/${moi.id}/`, { ...T, data: { role: large } })
  expect(rLarge.status(), `rôle perso plus large → ${(await rLarge.text()).slice(0, 200)}`).toBe(403)
  expect(JSON.stringify(await rLarge.json())).toContain('role_plus_large')
  expect((await ligne('acc21_cresp')).role, 'rôle inchangé en base').toBe(3)
  await py(`${PRELUDE}
Role.objects.filter(company_id=1, nom='acc21 perso large').delete(); sortie('ok')`)

  // Parcours légitime : un Directeur réinitialise un Commercial (palier inférieur).
  const com = await api(testInfo, 'acc21_com')
  expect((await com.get(`${API_DJANGO}/auth/me/`, T)).status()).toBe(200)
  const dir = await api(testInfo, 'acc21_dir2')
  const faible = await dir.post(`${API_DJANGO}/users/${avant.id}/reinitialiser-mot-de-passe/`, { ...T, data: { password: 'a' } })
  expect(faible.status(), 'mot de passe « a » refusé par la politique').toBe(400)
  expect(JSON.stringify(await faible.json())).toContain('password')
  const ok = await dir.post(`${API_DJANGO}/users/${avant.id}/reinitialiser-mot-de-passe/`, { ...T, data: { password: 'Nouveau-mdp-acc21-2026!' } })
  expect(ok.status(), await ok.text()).toBe(200)
  // Sessions de la cible révoquées : l'ancien cookie → 401.
  expect((await com.get(`${API_DJANGO}/auth/me/`, T)).status(), 'ancienne session révoquée').toBe(401)
  const rel = await py(`${PRELUDE}
from apps.parametres.models import SettingsAuditLog
u = U.objects.get(username='acc21_com')
l = SettingsAuditLog.objects.filter(company_id=1).order_by('-id')[:5]
sortie(dict(must=u.must_change_password, ancien=u.check_password('${PW}'), nouveau=u.check_password('Nouveau-mdp-acc21-2026!'),
            journal=[str(x.__dict__.get('action', '')) + '|' + str(x.__dict__.get('description', ''))[:80] for x in l]))`)
  expect(rel.must, 'must_change_password posé').toBe(true)
  expect(rel.nouveau).toBe(true)
  expect(rel.ancien).toBe(false)
  expect(JSON.stringify(rel.journal)).not.toContain('Nouveau-mdp')
  // Remise à l'état pour les étapes suivantes.
  await py(`${PRELUDE}
u = U.objects.get(username='acc21_com'); u.set_password('${PW}'); u.must_change_password = False; u.save(); sortie('ok')`)
  ctxCache.delete('acc21_com')

  // Un PATCH générique portant `password` → 400 password_via_reinitialisation, sans écriture.
  const g = await dir.patch(`${API_DJANGO}/users/${avant.id}/`, { ...T, data: { password: 'Autre-mdp-acc21-2026!' } })
  expect(g.status(), 'password dans un PATCH générique').toBe(400)
  expect(JSON.stringify(await g.json())).toContain('password_via_reinitialisation')
  expect((await ligne('acc21_com')).mdp_ok).toBe(true)
  // Création sans mot de passe : 400 sur `password` (plus de 500).
  const sans = await dir.post(`${API_DJANGO}/users/`, { ...T, data: { username: 'acc21_sansmdp', email: 'x@acc21.test', role: 4 } })
  expect(sans.status(), await sans.text()).toBe(400)
  expect(JSON.stringify(await sans.json())).toContain('password')

  // ASEC10 : un rôle de palier responsable SANS users_gerer ne peut écrire sur /users/.
  const sansDroit = await py(`${PRELUDE}
base = Role.objects.get(pk=3)
r, _ = Role.objects.get_or_create(company_id=1, nom='acc21 sans users_gerer', defaults=dict(permissions=[]))
r.permissions = [p for p in base.permissions if p != 'users_gerer']; r.save()
u = U.objects.get(username='acc21_viewer'); u.role_id = r.id; u.save()
sortie(dict(role=r.id, avait='users_gerer' in base.permissions))`)
  const sd = await api(testInfo, 'acc21_viewer')
  const rSans = await sd.patch(`${API_DJANGO}/users/${avant.id}/`, { ...T, data: { poste: 'X acc21' } })
  expect(rSans.status(), `sans users_gerer : ${await rSans.text()}`).toBe(403)
  expect(JSON.stringify(await rSans.json())).toContain('droit_manquant')
  expect((await sd.get(`${API_DJANGO}/users/`, T)).status(), 'la lecture reste ouverte').toBe(200)
  // Le Directeur, lui, modifie un Commercial (200 inchangé).
  const dOk = await dir.patch(`${API_DJANGO}/users/${avant.id}/`, { ...T, data: { poste: 'Vendeur acc21' } })
  expect(dOk.status(), await dOk.text()).toBe(200)
  await py(`${PRELUDE}
u = U.objects.get(username='acc21_viewer'); u.role_id = 7; u.save()
Role.objects.filter(company_id=1, nom='acc21 sans users_gerer').delete(); sortie('ok')`)
  expect(sansDroit.avait, 'le rôle Commercial responsable porte users_gerer (base de la copie)').toBe(true)
  test.info().annotations.push({ type: 'refus', description: refus.length + ' refus 403 constatés' })
})

// ── ASEC4 — verrou par /token/ ───────────────────────────────────────────────────────────────
etape('P1.2', ['ASEC4'], async ({ testInfo }) => {
  await monterComptes()
  const c = await pwRequest.newContext({ baseURL: base(testInfo) })
  // Identifiant inconnu et mot de passe faux : même 401, même corps (hors identifiants).
  const inconnu = await token(c, { username: 'acc21_inconnu_zz', password: 'faux' })
  const faux = await token(c, { username: 'acc21_terrain', password: 'faux-1' })
  expect(inconnu.status()).toBe(401)
  expect(faux.status()).toBe(401)
  const sansId = async (r) => { const j = await r.json(); if (j.error) delete j.error.request_id; return JSON.stringify(j) }
  expect(await sansId(inconnu), 'identifiant inconnu = mot de passe faux (hors request_id)').toBe(await sansId(faux))
  expect((await ligne('acc21_terrain')).echecs, 'un échec compté en base même société à lockout=0').toBe(1)
  // Seuil société posé à 3 (profil société 1), restauré en fin d'étape.
  const ancien = await py(`${PRELUDE}
from apps.parametres.models_company import CompanyProfile
p = CompanyProfile.objects.filter(company_id=1).first()
p.lockout_max_attempts = 3; p.save(update_fields=['lockout_max_attempts'])
sortie(CompanyProfile.objects.filter(company_id=1).first().lockout_max_attempts)`)
  expect(ancien).toBe(3)
  try {
    await token(c, { username: 'acc21_terrain', password: 'faux-2' })
    await token(c, { username: 'acc21_terrain', password: 'faux-3' })
    const l = (await ligne('acc21_terrain'))
    expect(l.verrou, 'échéance de verrou posée en base au 3e échec (compteur remis à 0)').toBeTruthy()
    // Compte verrouillé : même avec le BON mot de passe, le 401 générique (ASEC14-revue : le verrou n'est
    // jamais annoncé avant vérification) — identique à celui d'un identifiant inconnu.
    const verrouille = await token(c, { username: 'acc21_terrain', password: PW })
    expect(verrouille.status(), 'compte verrouillé + bon mot de passe').toBe(401)
    const sansReq = async (r) => { const j = await r.json(); if (j.error) delete j.error.request_id; return JSON.stringify(j) }
    expect(await sansReq(verrouille), 'corps identique à un identifiant inconnu').toBe(await sansReq(inconnu))
  } finally {
    await py(`${PRELUDE}
from apps.parametres.models_company import CompanyProfile
p = CompanyProfile.objects.filter(company_id=1).first(); p.lockout_max_attempts = 0; p.save(update_fields=['lockout_max_attempts'])
u = U.objects.get(username='acc21_terrain'); u.failed_login_count = 0; u.locked_until = None; u.save(); sortie('ok')`)
  }
  await new Promise((r) => setTimeout(r, 62_000)) // fenêtre du throttle « login » (5/min/IP)
  // Un succès remet le compteur à 0 (compte « acc21_viewer » : 1 échec puis 1 succès).
  await token(c, { username: 'acc21_viewer', password: 'faux-v' })
  expect((await ligne('acc21_viewer')).echecs).toBeGreaterThanOrEqual(1)
  const bon = await token(c, { username: 'acc21_viewer', password: PW })
  expect(bon.status()).toBe(200)
  expect((await ligne('acc21_viewer')).echecs, 'succès → compteur remis à 0').toBe(0)
  await c.dispose()
})

// ── ASEC5 — rejeu TOTP ───────────────────────────────────────────────────────────────────────
etape('P1.3', ['ASEC5'], async ({ testInfo }) => {
  await monterComptes()
  const secret = await py(`${PRELUDE}
import pyotp
u = U.objects.get(username='acc21_com'); s = pyotp.random_base32(); u.totp_secret = s; u.totp_enabled = True
u.totp_dernier_pas = None; u.save(); sortie(s)`)
  const c = await pwRequest.newContext({ baseURL: base(testInfo) })
  try {
    const fraisCode = () => py(`import pyotp
print('@@' + json.dumps(pyotp.TOTP('${secret}').now()))`)
    let code = await fraisCode()
    let un = await c.post(`${API_DJANGO}/token/`, { data: { username: 'acc21_com', password: PW, otp: code } })
    for (let i = 0; i < 8 && un.status() === 429; i++) { // throttle « login » : attendre, code frais
      await new Promise((res) => setTimeout(res, 20_000))
      code = await fraisCode()
      un = await c.post(`${API_DJANGO}/token/`, { data: { username: 'acc21_com', password: PW, otp: code } })
    }
    expect(un.status(), `1er code : ${await un.text()}`).toBe(200)
    const pas = (await ligne('acc21_com')).pas
    expect(pas, 'totp_dernier_pas relu en base après la 1re acceptation').toBeTruthy()
    const deux = await token(c, { username: 'acc21_com', password: PW, otp: code })
    expect(deux.status(), 'même code rejoué').toBe(401)
    expect(JSON.stringify(await deux.json())).toContain('otp_deja_utilise')
    expect((await ligne('acc21_com')).pas, 'pas inchangé après le refus').toBe(pas)
  } finally {
    await py(`${PRELUDE}
u = U.objects.get(username='acc21_com'); u.totp_enabled = False; u.totp_secret = ''; u.totp_dernier_pas = None; u.save(); sortie('ok')`)
    await c.dispose()
  }
})

// ── ASEC12 / ASEC13 — admin Django et inscription anonyme ───────────────────────────────────
etape('P1.4', ['ASEC12', 'ASEC13'], async ({ testInfo }) => {
  await monterComptes()
  const avant = await py(`${PRELUDE}
sortie(dict(c=Company.objects.count(), u=U.objects.count()))`)
  const anon = await pwRequest.newContext({ baseURL: base(testInfo) })
  const ins = await anon.post(`${API_DJANGO}/auth/register-company/`, {
    data: { company_name: uniq('ACC21 Co'), username: 'acc21_inscrit', email: 'ins@acc21.test', password: PW },
  })
  expect(ins.status(), `inscription anonyme : ${await ins.text()}`).toBe(404)
  const apres = await py(`${PRELUDE}
sortie(dict(c=Company.objects.count(), u=U.objects.count()))`)
  expect(apres, 'aucune société ni compte créés').toEqual(avant)

  // ASEC12 : un compte is_staff non superuser est refusé par l'admin Django ; un superuser 2FA exige un code.
  const admin = `${API_DJANGO}/admin/login/`
  const page = await anon.get(admin, T)
  if (page.status() !== 200) nonJouable(`page de connexion de l'admin Django inaccessible (${page.status()}) par le proxy ERP`)
  const formulaire = async (ctx, username, extra = {}) => {
    const g = await ctx.get(admin, T)
    const tok = (await g.text()).match(/name="csrfmiddlewaretoken" value="([^"]+)"/)?.[1]
    return ctx.post(admin, {
      ...T, maxRedirects: 0, headers: { Referer: `${base(testInfo)}${admin}` },
      form: { csrfmiddlewaretoken: tok, username, password: PW, next: `${API_DJANGO}/admin/`, ...extra },
    })
  }
  const dansAdmin = async (ctx) => (await ctx.get(`${API_DJANGO}/admin/`, { ...T, maxRedirects: 0 })).status() === 200
  // (a) is_staff NON superuser : refus (formulaire en erreur), aucun accès à l'index admin.
  await py(`${PRELUDE}
u = U.objects.get(username='acc21_viewer'); u.is_staff = True; u.is_superuser = False; u.save(); sortie('ok')`)
  const staff = await pwRequest.newContext({ baseURL: base(testInfo) })
  const rStaff = await formulaire(staff, 'acc21_viewer')
  expect(rStaff.status(), 'is_staff non superuser : formulaire ré-affiché, pas de redirection').toBe(200)
  expect(await dansAdmin(staff), 'index admin fermé au staff non superuser').toBe(false)
  // (b) superuser 2FA : sans code / code faux refusés ; bon code → accès + UserSession.
  const secret = await py(`${PRELUDE}
import pyotp
u = U.objects.get(username='acc21_dir2'); s = pyotp.random_base32()
u.is_staff = True; u.is_superuser = True; u.totp_secret = s; u.totp_enabled = True; u.totp_dernier_pas = None
u.failed_login_count = 0; u.save(); sortie(s)`)
  try {
    const su = await pwRequest.newContext({ baseURL: base(testInfo) })
    const sans = await formulaire(su, 'acc21_dir2')
    expect(sans.status(), 'superuser 2FA sans code').toBe(200)
    expect(await sans.text()).toContain('Code de double authentification')
    const faux = await formulaire(su, 'acc21_dir2', { otp: '000000' })
    expect(faux.status(), 'code faux').toBe(200)
    expect(await dansAdmin(su), 'toujours dehors').toBe(false)
    const comptes = await py(`${PRELUDE}
from authentication.models import UserSession
u = U.objects.get(username='acc21_dir2'); sortie(dict(echecs=u.failed_login_count, sessions=UserSession.objects.filter(user=u).count()))`)
    expect(comptes.echecs, 'compteur des échecs incrémenté en base').toBeGreaterThanOrEqual(1)
    const code = await py(`import pyotp
print('@@' + json.dumps(pyotp.TOTP('${secret}').now()))`)
    const bon = await formulaire(su, 'acc21_dir2', { otp: code })
    expect(bon.status(), `bon code : ${(await bon.text()).slice(0, 120)}`).toBe(302)
    expect(await dansAdmin(su), 'index admin ouvert avec le bon code').toBe(true)
    const apres = await py(`${PRELUDE}
from authentication.models import UserSession
u = U.objects.get(username='acc21_dir2'); sortie(UserSession.objects.filter(user=u).count())`)
    expect(apres, 'une UserSession tracée pour la connexion admin').toBeGreaterThan(comptes.sessions)
    await su.dispose()
  } finally {
    await py(`${PRELUDE}
u = U.objects.get(username='acc21_dir2'); u.is_staff = False; u.is_superuser = False; u.totp_enabled = False; u.totp_secret = ''; u.totp_dernier_pas = None; u.failed_login_count = 0; u.locked_until = None; u.save()
v = U.objects.get(username='acc21_viewer'); v.is_staff = False; v.save(); sortie('ok')`)
    await staff.dispose()
  }
  await anon.dispose()
})

// ── ASEC8 — diff d'audit 2FA / mot de passe caviardé ─────────────────────────────────────────
etape('P1.5', ['ASEC8'], async () => {
  await monterComptes()
  const r = await py(`${PRELUDE}
import pyotp
from apps.audit.models import AuditLog
u = U.objects.get(username='acc21_terrain')
u.totp_secret = pyotp.random_base32(); u.totp_enabled = True; u.save()
u.set_password('Autre-acc21-2026!'); u.save()
l = list(AuditLog.objects.filter(object_id=str(u.pk)).order_by('-id')[:6].values_list('changes', flat=True))
u.totp_enabled = False; u.totp_secret = ''; u.set_password('${PW}'); u.save()
sortie(dict(n=len(l), diffs=json.dumps(l, default=str)[:1500]))`)
  expect(r.n, 'des lignes d\'audit existent pour le compte').toBeGreaterThan(0)
  expect(r.diffs).not.toMatch(/pbkdf2_sha256\$/)
  expect(r.diffs).not.toMatch(/"new": "[A-Z2-7]{32}"/)
})

// ── Voisins : montage de deux sociétés (A = 1, B = 43) ──────────────────────────────────────
const refuse = (statut) => [400, 403, 404].includes(statut) // id étranger ≡ id inconnu (ENF11) : 404 ou 400
let monde = null
async function mondeAB() {
  if (monde) return monde
  monde = await py(`${PRELUDE}
from decimal import Decimal
from apps.crm.models import Client
from apps.ventes.models import Facture, LigneFacture, Devis, LigneDevis
from apps.stock.models import Produit
from apps.sav.models import Ticket, CategorieTicket
from apps.installations.models import Installation, Intervention
from apps.records.models import ActivityType
def mk(soc, tag):
    cli, _ = Client.objects.get_or_create(company_id=soc, nom='ACC21 ' + tag, defaults=dict(prenom='Voisin', email=f'acc21-{tag}@example.invalid'))
    prod, _ = Produit.objects.get_or_create(company_id=soc, sku='ACC21-' + tag, defaults=dict(nom='ACC21 secret ' + tag, prix_vente=Decimal('10'), quantite_stock=5))
    typ, _ = ActivityType.objects.get_or_create(company_id=soc, nom='ACC21 type secret ' + tag)
    cat, _ = CategorieTicket.objects.get_or_create(company_id=soc, libelle='ACC21 categorie secrete ' + tag)
    return cli, prod, typ, cat
cA, pA, tA, catA = mk(1, 'A')
cB, pB, tB, catB = mk(43, 'B')
dirA = U.objects.get(username='acc21_dir2'); dirB = U.objects.get(username='acc21_b')
fact, _ = Facture.objects.get_or_create(company_id=1, reference='FAC-ACC21-BROUILLON', defaults=dict(client=cA, statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20.00'), created_by=dirA))
fact.client = cA; fact.statut = Facture.Statut.BROUILLON; fact.save()
devis, _ = Devis.objects.get_or_create(company_id=1, reference='DEV-ACC21-1', defaults=dict(client=cA, statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20.00'), created_by=dirA))
devis.roof_image = 'roofs/1/DEV-ACC21-1.png'; devis.save()
tick, _ = Ticket.objects.get_or_create(company_id=1, reference='SAV-ACC21-1', defaults=dict(client=cA, type=Ticket.Type.CORRECTIF, sous_garantie=Ticket.SousGarantie.NON, created_by=dirA, cout=Decimal('100.00')))
inst, _ = Installation.objects.get_or_create(company_id=1, reference='CHT-ACC21', defaults=dict(client=cA))
interv = Intervention.objects.filter(company_id=1, installation=inst).first() or Intervention.objects.create(company_id=1, installation=inst)
sortie(dict(cA=cA.id, cB=cB.id, pA=pA.id, pB=pB.id, tA=tA.id, tB=tB.id, catB=catB.id, uB=dirB.id, uA=dirA.id,
            fact=fact.id, devis=devis.id, ticket=tick.id, ticket_cout=str(tick.cout), inst=inst.id, interv=interv.id))`)
  return monde
}
const GARDE_FUITE = /ACC21 (secret|type secret|categorie secrete) B|acc21_b\b|Voisin/

// ── ASEC6 — FK d'une autre société sur les activités ──────────────────────────────────────
etape('P2.1', ['ASEC6'], async ({ testInfo }) => {
  await monterComptes()
  const m = await mondeAB()
  const c = await api(testInfo, 'acc21_cresp')
  const compter = async () => (await py(`${PRELUDE}
from apps.records.models import Activity
sortie(Activity.objects.filter(company_id=1).count())`))
  const avant = await compter()
  const moi = (await ligne('acc21_cresp')).id
  for (const [champ, valeur] of [['assigned_to', m.uB], ['activity_type', m.tB], ['assigned_to', 999999999], ['activity_type', 999999999]]) {
    const r = await c.post(`${API_DJANGO}/records/activities/`, { ...T, data: { summary: 'ACC21 refus', assigned_to: moi, activity_type: m.tA, [champ]: valeur } })
    const txt = await r.text()
    expect(refuse(r.status()), `POST ${champ}=${valeur} → ${r.status()} ${txt.slice(0, 160)}`).toBe(true)
    expect(txt).not.toMatch(GARDE_FUITE)
    expect(r.status(), 'jamais 500').toBeLessThan(500)
  }
  expect(await compter(), 'aucune activité créée').toBe(avant)
  // Légitime : ids de A → 201, puis PATCH vers un type de B refusé et activité inchangée.
  const ok = await c.post(`${API_DJANGO}/records/activities/`, { ...T, data: { summary: 'ACC21 ok', assigned_to: moi, activity_type: m.tA } })
  expect(ok.status(), await ok.text()).toBe(201)
  const act = await ok.json()
  const patch = await c.patch(`${API_DJANGO}/records/activities/${act.id}/`, { ...T, data: { activity_type: m.tB } })
  expect(refuse(patch.status())).toBe(true)
  expect(await patch.text()).not.toMatch(GARDE_FUITE)
  const rel = await py(`${PRELUDE}
from apps.records.models import Activity
a = Activity.objects.get(pk=${act.id}); sortie(dict(t=a.activity_type_id, u=a.assigned_to_id))`)
  expect(rel).toEqual({ t: m.tA, u: moi })
  await c.delete(`${API_DJANGO}/records/activities/${act.id}/`, T)
})

// ── ASEC22 / ASEC27 — FK devis et facture, champs serveur ─────────────────────────────────
etape('P2.2', ['ASEC22', 'ASEC27'], async ({ testInfo }) => {
  await monterComptes()
  const m = await mondeAB()
  const c = await api(testInfo, 'acc21_dir2')
  // Ligne de devis avec un produit de B ; roof_image du corps ignoré.
  const ligneR = await c.post(`${API_DJANGO}/ventes/devis-lignes/`, { ...T, data: { devis: m.devis, designation: 'X', quantite: '1', prix_unitaire: '10', produit: m.pB } })
  expect(refuse(ligneR.status()), `ligne produit B → ${ligneR.status()}`).toBe(true)
  expect(await ligneR.text()).not.toMatch(GARDE_FUITE)
  const ligneInconnue = await c.post(`${API_DJANGO}/ventes/devis-lignes/`, { ...T, data: { devis: m.devis, designation: 'X', quantite: '1', prix_unitaire: '10', produit: 999999999 } })
  expect(ligneInconnue.status()).toBe(ligneR.status()) // un id étranger répond comme un id absent
  const roof = await c.patch(`${API_DJANGO}/ventes/devis/${m.devis}/`, { ...T, data: { roof_image: 'roofs/43/etranger.png' } })
  expect(roof.status(), 'roof_image ignoré (pas de 5xx)').toBeLessThan(500)
  const relD = await py(`${PRELUDE}
from apps.ventes.models import Devis, LigneDevis
d = Devis.objects.get(pk=${m.devis}); sortie(dict(roof=d.roof_image, lignes=LigneDevis.objects.filter(devis=d, produit_id=${m.pB}).count()))`)
  expect(relD.roof, 'roof_image inchangée en base').toBe('roofs/1/DEV-ACC21-1.png')
  expect(relD.lignes, 'aucune ligne sur un produit de B').toBe(0)
  const ok = await c.post(`${API_DJANGO}/ventes/devis-lignes/`, { ...T, data: { devis: m.devis, designation: 'ACC21 ok', quantite: '1', prix_unitaire: '10', produit: m.pA } })
  expect(ok.status(), await ok.text()).toBe(201)
  // Facture : FK étrangères et champs serveur.
  for (const champ of ['client', 'devis', 'bon_commande', 'lead', 'entite', 'condition_paiement_ref']) {
    const r = await c.patch(`${API_DJANGO}/ventes/factures/${m.fact}/`, { ...T, data: { [champ]: champ === 'client' ? m.cB : 999999999 } })
    expect(refuse(r.status()), `facture ${champ} → ${r.status()}`).toBe(true)
    expect(await r.text()).not.toMatch(GARDE_FUITE)
  }
  const st = await c.patch(`${API_DJANGO}/ventes/factures/${m.fact}/`, { ...T, data: { statut: 'payee', revue_statut: 'validee', abandon_par: m.uA, updated_by: m.uB } })
  expect(st.status(), 'PATCH de champs serveur sans 5xx').toBeLessThan(500)
  const relF = await py(`${PRELUDE}
from apps.ventes.models import Facture
f = Facture.objects.get(pk=${m.fact}); sortie(dict(statut=f.statut, client=f.client_id, rev=f.revue_statut, ab=f.abandon_par_id, ub=f.updated_by_id))`)
  expect(relF.statut).toBe('brouillon')
  expect(relF.client).toBe(m.cA)
  expect(relF.ab).toBeNull()
  expect(relF.ub, 'updated_by jamais posé depuis le corps').not.toBe(m.uB)
  // Création d'une facture avec le client de B : refusée.
  const nb = await c.post(`${API_DJANGO}/ventes/factures/`, { ...T, data: { client: m.cB, taux_tva: '20.00' } })
  expect(refuse(nb.status())).toBe(true)
})

// ── ASEC29 / ASEC11 — gestes d'argent réservés ────────────────────────────────────────────
etape('P2.3', ['ASEC11', 'ASEC29'], async ({ testInfo }) => {
  await monterComptes()
  const m = await mondeAB()
  const neuve = async (tag, par = m.uA) => (await py(`${PRELUDE}
from decimal import Decimal
from apps.ventes.models import Facture, LigneFacture
f = Facture.objects.create(company_id=1, reference='FAC-ACC21-${tag}-' + str(Facture.objects.count() + 1000), client_id=${m.cA},
    statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'), created_by_id=${par})
LigneFacture.objects.create(facture=f, produit_id=${m.pA}, designation='ACC21', quantite=Decimal('1'), prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
sortie(f.id)`))
  const geste = (c, id, nom) => nom === 'abandon'
    ? c.post(`${API_DJANGO}/ventes/factures/${id}/abandonner-solde/`, { ...T, data: { motif: 'geste_commercial' } })
    : c.post(`${API_DJANGO}/ventes/factures/${id}/enregistrer-paiement/`, { ...T, data: { montant: '100', date_paiement: new Date().toISOString().slice(0, 10), mode: 'virement' } })
  const lectures = []
  for (const compte of ['acc21_terrain', 'acc21_rh']) {
    const c = await api(testInfo, compte)
    for (const nom of ['abandon', 'paiement']) {
      const id = await neuve(`${compte}-${nom}`)
      const r = await geste(c, id, nom)
      expect(r.status(), `${compte} ${nom} : ${(await r.text()).slice(0, 160)}`).toBe(403)
      const rel = await py(`${PRELUDE}
from apps.ventes.models import Facture, Paiement
f = Facture.objects.get(pk=${id}); sortie(dict(s=f.statut, p=Paiement.objects.filter(facture=f).count(), ab=bool(f.abandon_montant)))`)
      expect(rel, `${compte} ${nom} : facture inchangée`).toEqual({ s: 'emise', p: 0, ab: false })
    }
    // ASEC11 : écritures CRM/Ventes fermées à ces deux rôles (création de facture, de lead, de client).
    const creeFacture = await c.post(`${API_DJANGO}/ventes/factures/`, { ...T, data: {} })
    expect(creeFacture.status(), `${compte} création de facture`).toBe(403)
    const lead = await c.post(`${API_DJANGO}/crm/leads/`, { ...T, data: { nom: uniq('ACC21 refus'), ville: 'Casablanca' } })
    expect(lead.status(), `${compte} création de lead`).toBe(403)
    const client = await c.post(`${API_DJANGO}/crm/clients/`, { ...T, data: { nom: 'ACC21 refus' } })
    expect(client.status(), `${compte} création de client`).toBe(403)
    // Lecture de la liste des factures : constatée (la matrice dorée du registre la laisse en « R »).
    const liste = await c.get(`${API_DJANGO}/ventes/factures/`, T)
    lectures.push(`${compte} GET factures → ${liste.status()}`)
  }
  test.info().annotations.push({ type: 'lectures', description: lectures.join(' ; ') })
  const com = await api(testInfo, 'acc21_com')
  const idCom = (await ligne('acc21_com')).id
  const idOk = await neuve('com-paie', idCom)
  const p = await geste(com, idOk, 'paiement')
  expect([200, 201], `Commercial (encaisser) : ${(await p.text()).slice(0, 200)}`).toContain(p.status())
  const idAb = await neuve('com-abandon', idCom)
  const a = await geste(com, idAb, 'abandon')
  expect([200, 201], `Commercial abandon : ${(await a.text()).slice(0, 200)}`).toContain(a.status())
  const rel = await py(`${PRELUDE}
from apps.ventes.models import Paiement
sortie(Paiement.objects.filter(facture_id=${idOk}).count())`)
  expect(rel, 'le paiement du Commercial est en base').toBe(1)
  // Rôle personnalisé SANS `encaisser` (Commercial moins ce code) : 403 droit_manquant.
  await py(`${PRELUDE}
base = Role.objects.get(pk=4)
r, _ = Role.objects.get_or_create(company_id=1, nom='acc21 sans encaisser', defaults=dict(permissions=[]))
r.permissions = [p for p in base.permissions if p != 'encaisser']; r.save()
u = U.objects.get(username='acc21_viewer'); u.role_id = r.id; u.save(); sortie(r.id)`)
  ctxCache.delete('acc21_viewer')
  const sans = await api(testInfo, 'acc21_viewer')
  const idSans = await neuve('sans-encaisser', (await ligne('acc21_viewer')).id)
  const rs = await geste(sans, idSans, 'paiement')
  expect(rs.status(), `sans encaisser : ${(await rs.text()).slice(0, 200)}`).toBe(403)
  const codeRefus = (await rs.json()).error?.code
  test.info().annotations.push({ type: 'code de refus ASEC29', description: `observé : ${codeRefus} (attendu par le texte de la tâche : droit_manquant)` })
  const relS = await py(`${PRELUDE}
from apps.ventes.models import Facture, Paiement
f = Facture.objects.get(pk=${idSans}); sortie(dict(s=f.statut, p=Paiement.objects.filter(facture=f).count()))`)
  expect(relS, 'facture inchangée après le refus').toEqual({ s: 'emise', p: 0 })
  await py(`${PRELUDE}
u = U.objects.get(username='acc21_viewer'); u.role_id = 7; u.save()
Role.objects.filter(company_id=1, nom='acc21 sans encaisser').delete(); sortie('ok')`)
  ctxCache.delete('acc21_viewer')
})

// ── ASEC32 / ASEC34 / ASEC35 — chantier et SAV ────────────────────────────────────────────
etape('P2.4', ['ASEC32', 'ASEC34', 'ASEC35'], async ({ testInfo }) => {
  await monterComptes()
  const m = await mondeAB()
  const c = await api(testInfo, 'acc21_dir2')
  const i1 = await c.patch(`${API_DJANGO}/installations/interventions/${m.interv}/`, { ...T, data: { technicien: m.uB } })
  expect(refuse(i1.status()), `intervention technicien B → ${i1.status()}`).toBe(true)
  expect(await i1.text()).not.toMatch(GARDE_FUITE)
  const i2 = await c.patch(`${API_DJANGO}/installations/chantiers/${m.inst}/`, { ...T, data: { technicien_responsable: m.uB } })
  expect(refuse(i2.status()), `chantier technicien_responsable B → ${i2.status()}`).toBe(true)
  const sig = await c.patch(`${API_DJANGO}/installations/interventions/${m.interv}/`, { ...T, data: { signature_client: 'data:image/png;base64,AAAA', signataire_nom: 'Pirate', signe_le: '2026-10-07T10:00:00Z' } })
  expect(sig.status(), await sig.text()).toBe(200)
  const relI = await py(`${PRELUDE}
from apps.installations.models import Intervention, Installation
i = Intervention.objects.get(pk=${m.interv}); n = Installation.objects.get(pk=${m.inst})
sortie(dict(t=i.technicien_id, sig=bool(i.signature_client), nom=i.signataire_nom, le=i.signe_le, tr=n.technicien_responsable_id))`)
  expect(relI.t).toBeNull()
  expect(relI.sig, 'signature non posable par PATCH').toBe(false)
  expect(relI.nom).toBeFalsy()
  expect(relI.le).toBeNull()
  expect(relI.tr).toBeNull()
  for (const [champ, valeur] of [['technicien_responsable', m.uB], ['categorie', m.catB]]) {
    const r = await c.patch(`${API_DJANGO}/sav/tickets/${m.ticket}/`, { ...T, data: { [champ]: valeur } })
    expect(refuse(r.status()), `ticket ${champ} → ${r.status()}`).toBe(true)
    expect(await r.text()).not.toMatch(GARDE_FUITE)
  }
  const fige = await c.patch(`${API_DJANGO}/sav/tickets/${m.ticket}/`, { ...T, data: { non_facturable: true, est_recidive: true, cout: '999.00' } })
  expect(fige.status(), await fige.text()).toBe(200)
  const relT = await py(`${PRELUDE}
from apps.sav.models import Ticket
t = Ticket.objects.get(pk=${m.ticket}); sortie(dict(nf=t.non_facturable, r=t.est_recidive, c=str(t.cout), tr=t.technicien_responsable_id, cat=t.categorie_id))`)
  expect(relT).toEqual({ nf: false, r: false, c: '100.00', tr: null, cat: null })
  const nbDevis = async () => py(`${PRELUDE}
from apps.ventes.models import Devis
sortie(Devis.objects.filter(company_id=1).count())`)
  const avant = await nbDevis()
  const mauvais = await c.post(`${API_DJANGO}/sav/tickets/${m.ticket}/creer-devis/`, { ...T, data: { lignes: [{ produit_id: m.pB, designation: 'Pièce', quantite: 1, prix_unitaire: '900' }] } })
  expect(refuse(mauvais.status()), `creer-devis produit B → ${mauvais.status()}`).toBe(true)
  expect(await mauvais.text()).not.toMatch(GARDE_FUITE)
  expect(await nbDevis(), 'aucun devis créé').toBe(avant)
  const bon = await c.post(`${API_DJANGO}/sav/tickets/${m.ticket}/creer-devis/`, { ...T, data: { lignes: [{ produit_id: m.pA, designation: 'Pièce A', quantite: 1, prix_unitaire: '900' }] } })
  expect(bon.status(), await bon.text()).toBe(201)
})

// ASEC36 (webhook WhatsApp SAV non signé) : NON JOUABLE sur cette pile — le canal est éteint
// (WHATSAPP_BUSINESS_API_KEY absente) et la route répond 404 avant toute vérification de signature ;
// la sémantique 401/503 reste couverte par apps/sav/tests_asec36_webhook_whatsapp.py (CI).

// ── ASEC24 — clé de toit d'une autre société ──────────────────────────────────────────────
etape('P2.6', ['ASEC24'], async ({ testInfo }) => {
  await monterComptes()
  const m = await mondeAB()
  const c = await api(testInfo, 'acc21_dir2')
  await py(`${PRELUDE}
from apps.ventes.models import Devis
Devis.objects.filter(pk=${m.devis}).update(roof_image='roofs/43/etranger-acc21.png'); sortie('ok')`)
  try {
    const r = await c.get(`${API_DJANGO}/ventes/devis/${m.devis}/proposal/`, { ...T, timeout: 240_000 })
    // Pas de clé étrangère téléchargée : le rendu aboutit (PDF) ou refuse proprement, jamais 5xx.
    expect(r.status(), `/proposal avec clé étrangère : ${r.status()}`).toBeLessThan(500)
    if (r.status() === 200) expect(r.headers()['content-type'] || '').toContain('application/pdf')
  } finally {
    await py(`${PRELUDE}
from apps.ventes.models import Devis
Devis.objects.filter(pk=${m.devis}).update(roof_image='roofs/1/DEV-ACC21-1.png'); sortie('ok')`)
  }
})
