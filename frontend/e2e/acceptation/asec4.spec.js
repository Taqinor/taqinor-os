// Rejeu en direct des tâches ASEC66-84 (vérifie ASEC VER4, lot 7) : chaque étape rejoue la sonde du constat quand
// elle existe (`scripts/sonde.py`, transaction annulée) ET joue le geste par l'API réelle sous de vrais comptes
// connectés : refus du rôle privé du code, passage inchangé des rôles légitimes. Société = celle de demo_admin
// (jamais un id en dur) ; rôles système relus par leur nom.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage } from '../helpers.js'

const etape = groupe('ASEC', ['ASEC66'])
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
  const ligne = (r.stdout || '').split('\n').filter((l) => l.startsWith('{')).pop()
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
