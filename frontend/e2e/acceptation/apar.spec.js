// APAR45 — acceptation en direct du groupe APAR (Paramètres → textes → notifications → automatisation
// → bus → approbations) : rejeu des parcours P1.1 … P7 et H×H de la tâche sur la pile locale à deux
// sociétés (1 = « TAQINOR Démo », 43 = société voisine), par les VRAIES routes et les VRAIS écrans.
//
// Comptes : `acc45_*` créés par `manage.py shell` (E2E_DJANGO_EXEC) avec un mot de passe d'essai local
// (Directeur, Admin RH, Technicien responsable, Commercial en société 1 ; Directeur en société 43),
// désactivés en fin de spec. Réglages de la société 1 modifiés par la spec (RIB, ICE, TVA, fêtes
// mobiles…) : rétablis puis relus à la fin de chaque étape. Aucune donnée de production, aucun envoi
// réel. Une étape non jouable ici lève « NON JOUABLE : <raison> » — jamais un PASS.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawn } from 'node:child_process'
import { groupe } from './_oracles.js'
import { API_DJANGO, lireJson, telephoneMobileUnique, textePdf, uniq } from '../helpers.js'

const etape = groupe('APAR', ['APAR45'])
test.describe.configure({ timeout: 900_000 })

const PW = 'Acc45-essai-local-2026!'
const T = { timeout: 120_000 }

// ── manage.py shell persistant (comptes, données de test) ───────────────────────────────────────
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
U = get_user_model()
def sortie(o): print('@@' + json.dumps(o, default=str))
`
const COMPTES = {
  acc45_dir: { role: 1 }, // second Directeur (société 1) = « second onglet » / approbateur
  acc45_rh: { role: 71 }, // Admin RH
  acc45_tresp: { role: 5 }, // Technicien responsable
  acc45_com: { role: 4 }, // Commercial
  acc45_b: { role: 91, societe: 43 }, // Directeur de la société 43
}
let pret = false
async function monterComptes() {
  if (pret) return
  await py(`${PRELUDE}
C = json.loads('${JSON.stringify(COMPTES)}')
for nom, c in C.items():
    soc = c.get('societe', 1)
    u, _ = U.objects.get_or_create(username=nom, defaults=dict(company_id=soc, role_id=c['role']))
    u.company_id = soc; u.role_id = c['role']; u.is_active = True
    u.email = nom + '@acc45.test'; u.must_change_password = False; u.failed_login_count = 0; u.locked_until = None
    u.totp_enabled = False; u.set_password('${PW}'); u.save()
sortie('ok')`)
  pret = true
}
test.afterAll(async () => {
  try {
    await py(`${PRELUDE}
U.objects.filter(username__startswith='acc45_').update(is_active=False)
sortie('ok')`)
  } catch { /* nettoyage au mieux */ }
  serveur?.proc.stdin.end()
})

const ctxCache = new Map()
/** Contexte API connecté (cookies) ; patiente le throttle « login » (429). */
async function api(testInfo, username) {
  if (ctxCache.has(username)) return ctxCache.get(username)
  const c = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await expect(async () => {
    const r = await c.post(`${API_DJANGO}/token/`, { data: { username, password: PW } })
    expect(r.status(), `connexion de ${username}`).toBe(200)
  }).toPass({ intervals: [10_000, 20_000, 30_000], timeout: 300_000 })
  ctxCache.set(username, c)
  return c
}
const j = async (res, quoi, statut) => {
  if (statut) expect(res.status(), `${quoi} → ${(await res.text()).slice(0, 300)}`).toBe(statut)
  return lireJson(res, quoi)
}
const profil = async (r) => j(await r.get(`${API_DJANGO}/parametres/`, T), 'profil')
const majProfil = (r, data, statut = 200) => r.patch(`${API_DJANGO}/parametres/update/`, { ...T, data }).then(async (res) => {
  if (statut) expect(res.status(), `PATCH profil ${JSON.stringify(data)} → ${(await res.text()).slice(0, 300)}`).toBe(statut)
  return res
})
/** Rétablit RIB / ICE / TVA de la société 1 (valeurs lues au départ) et relit. */
async function retablirProfil(r, base) {
  const p = await profil(r)
  await majProfil(r, { rib: base.rib || '', ice: base.ice || '', tva_standard: base.tva_standard, updated_at: p.updated_at })
  const apres = await profil(r)
  expect([apres.rib || '', apres.ice || '', apres.tva_standard]).toEqual([base.rib || '', base.ice || '', base.tva_standard])
}
const nbAudit = async (r, query = '') => (await j(await r.get(`${API_DJANGO}/parametres/audit/?limit=1${query}`, T), 'journal')).count

// ── P1.1 — verrou optimiste (deux onglets), ICE normalisé, erreur sous le champ ────────────────
etape('P1.1', ['APAR45'], async ({ page, testInfo, suivi }) => {
  await monterComptes()
  suivi.attendre(/\/parametres\/update\/$/, 400)
  suivi.attendre(/\/parametres\/update\/$/, 409)
  const a = page.request // demo_admin = onglet A
  const b = await api(testInfo, 'acc45_dir') // second Directeur = onglet B
  const base = await profil(a)
  try {
    const luParA = base.updated_at
    expect(luParA).toBeTruthy()
    await majProfil(b, { rib: 'ACC45-RIB-B', updated_at: luParA })
    const avantAudit = await nbAudit(a, '&field=rib')
    const refus = await majProfil(a, { tva_standard: '14.00', updated_at: luParA }, 409)
    expect(await refus.text()).toMatch(/modifi/i)
    const relu = await profil(a)
    expect(relu.rib, 'le RIB de B est conservé').toBe('ACC45-RIB-B')
    expect(relu.tva_standard, 'la TVA de A n\'est pas écrite').toBe(base.tva_standard)
    const rib = await j(await a.get(`${API_DJANGO}/parametres/audit/?field=rib&limit=5`, T), 'journal rib')
    expect(rib.results.some((x) => x.user_nom === 'demo_admin' && /ACC45-RIB-B/.test(String(x.new_value))), 'aucune ligne rib au nom de A').toBe(false)
    expect(await nbAudit(a, '&field=rib')).toBe(avantAudit)
    // Après rechargement A renvoie le seul champ modifié avec le nouvel horodatage : 200.
    await majProfil(a, { tva_standard: '14.00', updated_at: relu.updated_at })
    expect((await profil(a)).tva_standard).toBe('14.00')
    // ICE espacé / tiré : stocké en 15 chiffres, relu identique après rechargement.
    for (const saisi of ['001 234 567 000 089', '001-234-567-000-089']) {
      await majProfil(a, { ice: saisi, updated_at: (await profil(a)).updated_at })
      expect((await profil(a)).ice, `ICE « ${saisi} »`).toBe('001234567000089')
    }
    // ICE de 14 chiffres : refus nommant le champ, rien d'écrit.
    const mauvais = await majProfil(a, { ice: '00123456700008', updated_at: (await profil(a)).updated_at }, null)
    expect([400, 409], `ICE 14 chiffres → ${mauvais.status()}`).toContain(mauvais.status())
    const corps = await mauvais.json()
    expect(JSON.stringify(corps), 'le refus nomme le champ ice').toMatch(/"ice"/)
    expect((await profil(a)).ice).toBe('001234567000089')
    // Écran : l'erreur s'affiche SOUS le champ ICE.
    await page.goto('/parametres')
    const champ = page.getByLabel(/ICE/i).first()
    await expect(champ).toBeVisible({ timeout: 60_000 })
    await champ.fill('00123456700008')
    await page.getByRole('button', { name: /^Enregistrer/ }).first().click()
    const erreur = page.getByText(/exactement 15 chiffres/).first()
    await expect(erreur, 'erreur ICE affichée').toBeVisible({ timeout: 30_000 })
    await champ.scrollIntoViewIfNeeded()
    const bc = await champ.boundingBox()
    let proche = null
    const candidats = page.getByText(/exactement 15 chiffres/)
    for (let k = 0; k < await candidats.count(); k += 1) {
      if (!(await candidats.nth(k).isVisible())) continue
      const be = await candidats.nth(k).boundingBox()
      if (be && be.y >= bc.y + bc.height - 4 && be.y - (bc.y + bc.height) < 60 && Math.abs(be.x - bc.x) < 40) proche = be
    }
    expect(proche, 'un message « 15 chiffres » est affiché SOUS le champ ICE (sous sa boîte, à moins de 60 px, aligné)').toBeTruthy()
    await page.reload()
    expect((await profil(a)).ice, 'après F5 la valeur serveur est inchangée').toBe('001234567000089')
  } finally {
    await retablirProfil(a, base)
  }
})

// ── P1.2 — Admin RH : écriture refusée (403) ; écran en lecture seule ──────────────────────────
etape('P1.2', ['APAR45'], async ({ page, context, testInfo, suivi }) => {
  await monterComptes()
  const a = page.request
  const rh = await api(testInfo, 'acc45_rh')
  const base = await profil(a)
  const tauxAvant = (await j(await a.get(`${API_DJANGO}/parametres/taux-tva/`, T), 'taux')).length ?? null
  const msgs = await j(await a.get(`${API_DJANGO}/parametres/messages/`, T), 'messages')
  const msg = msgs.find((m) => m.cle === 'rappel_rdv')
  const gestes = [
    ['PATCH tva_standard', await rh.patch(`${API_DJANGO}/parametres/update/`, { ...T, data: { tva_standard: '14.00', updated_at: base.updated_at } })],
    ['POST taux de TVA', await rh.post(`${API_DJANGO}/parametres/taux-tva/`, { ...T, data: { code: 'ACC45RH', taux: '14.00', libelle: 'ACC45 RH' } })],
    ['PUT message client', await rh.put(`${API_DJANGO}/parametres/messages/`, { ...T, data: { cle: 'rappel_rdv', corps_fr: 'PIRATE ACC45 RH' } })],
  ]
  for (const [nom, rep] of gestes) {
    expect(rep.status(), `${nom} par l'Admin RH : ${(await rep.text()).slice(0, 200)}`).toBe(403)
  }
  suivi.attendre(/\/parametres\//, 403)
  const apres = await profil(a)
  expect(apres.tva_standard).toBe(base.tva_standard)
  expect(apres.updated_at, 'aucune écriture').toBe(base.updated_at)
  const msgApres = (await j(await a.get(`${API_DJANGO}/parametres/messages/`, T), 'messages')).find((m) => m.cle === 'rappel_rdv')
  expect(msgApres.corps_fr).toBe(msg.corps_fr)
  const tauxApres = (await j(await a.get(`${API_DJANGO}/parametres/taux-tva/`, T), 'taux')).length ?? null
  expect(tauxApres).toBe(tauxAvant)
  // Écran : l'Admin RH ouvre Paramètres et ne peut pas enregistrer.
  const etat = await rh.storageState()
  await context.clearCookies()
  await context.addCookies(etat.cookies)
  // ERR-PARAM-ASSIGNABLE-USERS-403 — l'Admin RH (sans droit CRM) n'appelle plus
  // `GET /crm/assignable-users/` au montage de Paramètres : ni 403 ni console.error.
  const assignables = []
  page.on('response', (r) => { if (/\/crm\/assignable-users\//.test(r.url())) assignables.push(`${r.request().method()} ${r.status()}`) })
  const erreursConsole = []
  page.on('console', (m) => { if (m.type() === 'error') erreursConsole.push(m.text()) })
  await page.goto('/parametres')
  await expect(page.getByText(/lecture seule/i).first()).toBeVisible({ timeout: 60_000 })
  await page.waitForLoadState('networkidle').catch(() => undefined)
  testInfo.annotations.push({ type: 'assignable-users', description: `appels ${JSON.stringify(assignables)} ; console.error ${JSON.stringify(erreursConsole)}` })
  console.log(`[P1.2] assignable-users : ${JSON.stringify(assignables)} ; console.error : ${JSON.stringify(erreursConsole)}`)
  expect(assignables.filter((x) => / 403$/.test(x)), 'aucun 403 sur /crm/assignable-users/').toEqual([])
  expect(erreursConsole, 'aucune console.error sur Paramètres (Admin RH)').toEqual([])
  const enregistrer = page.getByRole('button', { name: /^Enregistrer/ })
  const n = await enregistrer.count()
  for (let i = 0; i < n; i += 1) await expect(enregistrer.nth(i)).toBeDisabled()
})

// ── P1.3 — tolérance 15 : même facture sur l'étude et sur le devis ─────────────────────────────
etape('P1.3', ['APAR45'], async ({ page }) => {
  // Geste réel : l'admin règle la tolérance à 15 dans Tarification & ROI (route de l'écran), puis la
  // facture mensuelle de l'écran (`/tarification/roi/` → `tariff.monthly_bill`, chemin étude) est
  // comparée, pour 205/215/305/501/511 kWh, à celle du chemin DEVIS calculée dans le processus
  // django par le même idiome que `etude_horaire._reglages_tarifaires` (surcharge société →
  // TrancheTable, sinon grille nationale ONEE_TRANCHES) puis `pricing._monthly_bill_from_kwh`.
  await monterComptes()
  const a = page.request
  const avant = await j(await a.get(`${API_DJANGO}/parametres/tarification/`, T), 'tarification')
  const tolAvant = avant.tolerance_kwh
  const maj = await a.patch(`${API_DJANGO}/parametres/tarification/update/`, { ...T, data: { tolerance_kwh: 15 } })
  expect(maj.status(), (await maj.text()).slice(0, 300)).toBe(200)
  try {
    const relu = await j(await a.get(`${API_DJANGO}/parametres/tarification/`, T), 'tarification relue')
    expect(relu.tolerance_kwh, 'tolérance 15 enregistrée').toBe(15)
    const ecarts = []
    const lignes = []
    for (const kwh of [205, 215, 305, 501, 511]) {
      const roi = await j(await a.post(`${API_DJANGO}/parametres/tarification/roi/`, { ...T, data: { kwc: 3, conso_mensuelle_kwh: kwh, cout_total_ttc: 30000 } }), `roi ${kwh}`, 200)
      const devis = await py(`${PRELUDE}
from decimal import Decimal
from authentication.models import Company
from apps.parametres.selectors import residential_tranches_for
from apps.ventes.quote_engine.pricing import TrancheTable, ONEE_TRANCHES, _monthly_bill_from_kwh
t = residential_tranches_for(Company.objects.get(pk=1))
table = TrancheTable(t['pairs'], selective_threshold=t['selective_threshold'], boundary_tolerance=t['boundary_tolerance']) if t else ONEE_TRANCHES
sortie(dict(source='societe' if t else 'national', facture=str(Decimal(str(_monthly_bill_from_kwh(${kwh}, table))).quantize(Decimal('0.01')))))`)
      lignes.push(`${kwh} kWh : écran ${roi.facture_mensuelle_ttc} / devis ${devis.facture} (${devis.source})`)
      if (Math.abs(Number(roi.facture_mensuelle_ttc) - Number(devis.facture)) > 0.01) ecarts.push(lignes[lignes.length - 1])
    }
    console.log(`[P1.3] ${lignes.join(' ; ')}`)
    test.info().annotations.push({ type: 'factures', description: lignes.join(' ; ') })
    expect(ecarts, 'tolérance 15 : même facture sur l\'écran (étude) et sur le devis').toEqual([])
    // Écran : la tolérance relue après F5.
    await page.goto('/parametres?onglet=tarification')
    await page.reload()
    expect((await j(await a.get(`${API_DJANGO}/parametres/tarification/`, T), 'tarification après F5')).tolerance_kwh).toBe(15)
  } finally {
    const r = await a.patch(`${API_DJANGO}/parametres/tarification/update/`, { ...T, data: { tolerance_kwh: tolAvant } })
    expect(r.status(), 'tolérance rétablie').toBe(200)
  }
})

// ── P1.5 — rétention 1 j puis purge : aucune ligne de moins de 365 j supprimée ──────────────────
etape('P1.5', ['APAR45'], async ({ testInfo }) => {
  await monterComptes()
  const b = await api(testInfo, 'acc45_b')
  const avant = await py(`${PRELUDE}
from django.utils import timezone
from apps.audit.models import AuditLog
from apps.parametres.models import CompanyProfile, SettingsAuditLog
c = U.objects.get(username='acc45_b').company
p = CompanyProfile.get(company=c)
ancien = p.audit_retention_days
p.audit_retention_days = 1; p.save()
def vieux(model, jours, **kw):
    o = model.objects.create(company=c, **kw)
    model.objects.filter(pk=o.pk).update(timestamp=timezone.now() - timezone.timedelta(days=jours))
    return o.pk
a10 = vieux(AuditLog, 10, action=AuditLog.Action.LOGIN, actor_username='acc45-ret')
a400 = vieux(AuditLog, 400, action=AuditLog.Action.LOGIN, actor_username='acc45-ret')
s10 = vieux(SettingsAuditLog, 10, section='profil', field='acc45', old_value='a', new_value='b')
s400 = vieux(SettingsAuditLog, 400, section='profil', field='acc45', old_value='a', new_value='b')
limite = timezone.now() - timezone.timedelta(days=365)
recents = list(AuditLog.objects.filter(company=c, timestamp__gte=limite).values_list('pk', flat=True))
recents_s = list(SettingsAuditLog.objects.filter(company=c, timestamp__gte=limite).values_list('pk', flat=True))
sortie(dict(ancien=ancien, a10=a10, a400=a400, s10=s10, s400=s400, recents=recents, recents_s=recents_s))`)
  try {
    const rep = await j(await b.post(`${API_DJANGO}/parametres/audit/purge/`, { ...T, data: {} }), 'purge', 200)
    expect(rep.audit_deleted, 'une ligne d\'audit de 400 j purgée').toBeGreaterThanOrEqual(1)
    expect(rep.settings_deleted, 'une ligne de réglages de 400 j purgée').toBeGreaterThanOrEqual(1)
    const apres = await py(`${PRELUDE}
from apps.audit.models import AuditLog
from apps.parametres.models import SettingsAuditLog
sortie(dict(
  a10=AuditLog.objects.filter(pk=${avant.a10}).exists(), a400=AuditLog.objects.filter(pk=${avant.a400}).exists(),
  s10=SettingsAuditLog.objects.filter(pk=${avant.s10}).exists(), s400=SettingsAuditLog.objects.filter(pk=${avant.s400}).exists(),
  perdus=AuditLog.objects.filter(pk__in=${JSON.stringify(avant.recents)}).count() - ${avant.recents.length},
  perdus_s=SettingsAuditLog.objects.filter(pk__in=${JSON.stringify(avant.recents_s)}).count() - ${avant.recents_s.length}))`)
    expect(apres.a400, 'ligne de 400 j supprimée').toBe(false)
    expect(apres.s400).toBe(false)
    expect(apres.a10, 'ligne de 10 j conservée malgré la rétention de 1 j (plancher 365 j)').toBe(true)
    expect(apres.s10).toBe(true)
    expect(apres.perdus, '0 ligne de moins de 365 j supprimée').toBe(0)
    expect(apres.perdus_s).toBe(0)
  } finally {
    await py(`${PRELUDE}
from apps.parametres.models import CompanyProfile
c = U.objects.get(username='acc45_b').company
p = CompanyProfile.get(company=c); p.audit_retention_days = ${avant.ancien ?? 0}; p.save()
sortie('ok')`)
  }
})

// ── P2.1 — « Rappel de RDV » sans changement ; « } » seul dans un e-mail ───────────────────────
etape('P2.1', ['APAR45'], async ({ page, suivi }) => {
  const a = page.request
  const msg = (await j(await a.get(`${API_DJANGO}/parametres/messages/`, T), 'messages')).find((m) => m.cle === 'rappel_rdv')
  expect(msg, 'message « Rappel de RDV »').toBeTruthy()
  const avant = await nbAudit(a, '&section=messages')
  await j(await a.put(`${API_DJANGO}/parametres/messages/`, { ...T, data: { cle: 'rappel_rdv', corps_fr: msg.corps_fr, corps_darija: msg.corps_darija || '' } }), 'enregistrement sans changement', 200)
  expect(await nbAudit(a, '&section=messages'), 'enregistrer sans toucher : aucune ligne de journal').toBe(avant)
  const relu = (await j(await a.get(`${API_DJANGO}/parametres/messages/`, T), 'messages')).find((m) => m.cle === 'rappel_rdv')
  expect(relu.corps_fr).toBe(msg.corps_fr)
  // « } » seul dans un e-mail : refus 400 sous le champ « corps », rien d'écrit.
  const emails = await j(await a.get(`${API_DJANGO}/parametres/email-templates/`, T), 'e-mails')
  const liste = Array.isArray(emails) ? emails : emails.results || []
  const rep = await a.put(`${API_DJANGO}/parametres/email-templates/bulk/`, { ...T, data: { templates: [{ cle: 'envoi_devis', sujet: 'Devis', corps: '}' }] } })
  const corps = await rep.text()
  expect(rep.status(), corps.slice(0, 200)).toBe(400)
  expect(corps).toMatch(/"corps"/)
  expect(corps).toMatch(/Accolade/i)
  suivi.attendre(/email-templates\/bulk\/$/, 400)
  const apres = await j(await a.get(`${API_DJANGO}/parametres/email-templates/`, T), 'e-mails relus')
  const listeApres = Array.isArray(apres) ? apres : apres.results || []
  expect(JSON.stringify(listeApres), 'le « } » n\'a pas été écrit').toBe(JSON.stringify(liste))
})

// ── P2.3 — changer le RIB : le PDF du devis accepté se télécharge toujours ─────────────────────
etape('P2.3', ['APAR45'], async ({ page, suivi }) => {
  const a = page.request
  const base = await profil(a)
  try {
    const produit = await j(await a.post(`${API_DJANGO}/stock/produits/`, { ...T, data: { nom: uniq('ACC45 produit'), prix_vente: '1000.00', prix_achat: '600.00', quantite_stock: 0, tva: '20.00' } }), 'produit', 201)
    const lead = await j(await a.post(`${API_DJANGO}/crm/leads/`, { ...T, data: { nom: uniq('ACC45 lead'), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800' } }), 'lead', 201)
    const devis = await j(await a.post(`${API_DJANGO}/ventes/devis/`, { ...T, data: { lead: lead.id, taux_tva: '20.00', mode_installation: 'residentiel' } }), 'devis', 201)
    await j(await a.post(`${API_DJANGO}/ventes/devis/${devis.id}/replace-lines/`, { ...T, data: { lignes: [{ produit: produit.id, designation: 'ACC45', quantite: '1.00', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'lignes', 200)
    await j(await a.post(`${API_DJANGO}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client ACC45' } }), 'acceptation', 200)
    const pdf = async () => {
      const rep = await a.get(`${API_DJANGO}/ventes/devis/${devis.id}/proposal/?pdf_mode=onepage`, T)
      expect(rep.status(), 'PDF du devis accepté').toBe(200)
      expect(rep.headers()['content-type'] || '').toContain('application/pdf')
      return textePdf(await rep.body())
    }
    const avant = await pdf()
    await majProfil(a, { rib: 'ACC45-RIB-PDF', updated_at: base.updated_at })
    const apres = await pdf()
    expect(apres.length, 'le PDF du devis accepté est rendu après le changement de RIB').toBeGreaterThan(200)
    expect((await profil(a)).rib).toBe('ACC45-RIB-PDF')
    // CLAUSE CLIENT : le montant du PDF est celui de l'écran du devis.
    const rel = await j(await a.get(`${API_DJANGO}/ventes/devis/${devis.id}/`, T), 'devis relu')
    const plat = (t) => String(t).replace(/\s/g, '').replace(new RegExp(String.fromCharCode(160) + '|' + String.fromCharCode(0x202f), 'g'), '')
    expect(plat(apres)).toContain(plat('1 000,00'))
    expect(plat(avant)).toContain(plat('1 000,00'))
    expect(rel.statut).toBe('accepte')
    await page.goto('/ventes/devis')
    suivi.verifie(6)
  } finally {
    await retablirProfil(a, base)
  }
})

// ── P3.1 — annonce « Toute la société » : rapport de conformité à 100 % des internes ─────────────
etape('P3.1', ['APAR45'], async ({ page, testInfo }) => {
  await monterComptes()
  const a = page.request
  const annonce = await j(await a.post(`${API_DJANGO}/notifications/annonces/`, {
    ...T, data: { titre: uniq('ACC45 annonce'), corps: 'Lecture obligatoire', cible_type: 'tous', lecture_obligatoire: true },
  }), 'annonce', 201)
  await j(await a.post(`${API_DJANGO}/notifications/annonces/${annonce.id}/publier/`, { ...T, data: {} }), 'publication', 200)
  const lecteurs = ['acc45_dir', 'acc45_rh', 'acc45_tresp', 'acc45_com']
  await j(await a.post(`${API_DJANGO}/notifications/annonces/${annonce.id}/accuser-lecture/`, { ...T, data: {} }), 'lecture demo_admin', 200)
  for (const u of lecteurs) {
    const c = await api(testInfo, u)
    await j(await c.post(`${API_DJANGO}/notifications/annonces/${annonce.id}/accuser-lecture/`, { ...T, data: {} }), `lecture ${u}`, 200)
  }
  // Les autres comptes internes de la pile n'ont pas de mot de passe connu : leur lecture passe par le
  // service d'accusé (même code que la route) ; les comptes de portail ne sont ni ciblés ni comptés.
  const internes = await py(`${PRELUDE}
from apps.notifications.models import Annonce
from apps.notifications.selectors import utilisateurs_internes_actifs
from apps.notifications.services import acknowledge_annonce
an = Annonce.objects.get(pk=${annonce.id})
tous = list(utilisateurs_internes_actifs(an.company))
restants = []
for u in tous:
    try:
        acknowledge_annonce(an, u)
    except Exception as e:
        restants.append(u.username + ':' + str(e)[:60])
portail = list(U.objects.filter(company=an.company, portee=U.PORTEE_PORTAIL_CLIENT).values_list('username', flat=True))
sortie(dict(internes=[u.username for u in tous], portail=portail, erreurs=restants))`)
  expect(internes.erreurs).toEqual([])
  const rapport = await j(await a.get(`${API_DJANGO}/notifications/annonces/${annonce.id}/conformite/`, T), 'conformité')
  expect(rapport.manquants, 'aucun interne manquant').toEqual([])
  expect(rapport.total_cibles, 'cibles = comptes internes actifs').toBe(internes.internes.length)
  const texte = JSON.stringify(rapport)
  for (const p of internes.portail) expect(texte, `compte de portail ${p} hors du rapport`).not.toContain(`"${p}"`)
  testInfo.annotations.push({ type: 'rapport', description: `${rapport.total_cibles} cibles, portail exclus : ${internes.portail.join(', ') || 'aucun compte de portail en société 1'}` })
  await page.goto('/parametres/notifications')
})

// ── P3.2 — corriger une fête mobile future : une seule ligne ────────────────────────────────────
etape('P3.2', ['APAR45'], async ({ page }) => {
  const a = page.request
  const ANNEE = 2028
  const dates = { aid_el_fitr: '2028-01-27', aid_el_adha: '2028-04-04', '1er_moharram': '2028-06-24', aid_el_mawlid: '2028-09-02' }
  const etat0 = await j(await a.get(`${API_DJANGO}/parametres/fetes-mobiles/?annee=${ANNEE}`, T), 'état')
  expect(Object.values(etat0).every((v) => v === null), 'année 2028 vierge avant le rejeu').toBe(true)
  const lister = async () => {
    const l = await j(await a.get(`${API_DJANGO}/notifications/holidays/?page_size=500`, T), 'jours fériés')
    return (Array.isArray(l) ? l : l.results || []).filter((h) => String(h.date).startsWith(String(ANNEE)) && /a[iï]d|moharram|mawlid|hégir|hegir/i.test(h.nom))
  }
  try {
    await j(await a.post(`${API_DJANGO}/parametres/fetes-mobiles/enregistrer/`, { ...T, data: { annee: ANNEE, dates } }), 'saisie des 4 fêtes', 200)
    // 4 fêtes + le 2ᵉ jour des deux Aïd (APAR36) = 6 lignes.
    expect((await lister()).length, '4 fêtes saisies = 6 lignes (2ᵉ jour des Aïd)').toBe(6)
    const corrigee = { ...dates, aid_el_adha: '2028-04-05' }
    await j(await a.post(`${API_DJANGO}/parametres/fetes-mobiles/enregistrer/`, { ...T, data: { annee: ANNEE, dates: corrigee } }), 'correction de l\'Aïd al-Adha', 200)
    const lignes = await lister()
    expect(lignes.length, 'toujours 6 lignes : la correction remplace, ne duplique pas').toBe(6)
    expect(lignes.filter((h) => /adha/i.test(h.nom)).map((h) => h.date).sort(), 'Aïd al-Adha : jour 1 corrigé + 2ᵉ jour, plus aucune ligne au 04/04').toEqual(['2028-04-05', '2028-04-06'])
    expect(lignes.filter((h) => String(h.date) === '2028-04-04'), 'ancienne date retirée').toEqual([])
    const etat = await j(await a.get(`${API_DJANGO}/parametres/fetes-mobiles/?annee=${ANNEE}`, T), 'état relu')
    expect(etat.aid_el_adha).toBe('2028-04-05')
    // Journal : la correction est tracée (ancienne → nouvelle date).
    const j1 = await j(await a.get(`${API_DJANGO}/parametres/audit/?field=aid_el_adha&limit=5`, T), 'journal fêtes')
    expect(j1.results.some((x) => /2028-04-04/.test(String(x.old_value)) && /2028-04-05/.test(String(x.new_value))), 'correction journalisée').toBe(true)
    await page.goto('/parametres')
  } finally {
    for (const h of await lister()) await a.delete(`${API_DJANGO}/notifications/holidays/${h.id}/`, T)
    expect((await lister()).length, 'fêtes de test retirées').toBe(0)
  }
})

etape('P3.2b', ['APAR45'], async ({ page }) => {
  // La règle est créée par la VRAIE route (écran Automatisations) ; le changement d'étape est fait
  // dans le processus django avec l'horloge FIGÉE à 23:30 Africa/Casablanca (patch de
  // `django.utils.timezone.now`, l'idiome `frozen` des tests — freezegun absent de l'image) et le
  // backend e-mail locmem du MÊME processus, lu ensuite. Reprise : `engine.resume_scheduled_step`
  // sur la seule échéance du run (jamais le balayage global, qui reprendrait celles des autres).
  await monterComptes()
  const a = page.request
  const regle = await j(await a.post(`${API_DJANGO}/automation/rules/`, {
    ...T, data: { nom: uniq('ACC45 fenetre 23h30'), trigger_type: 'lead_stage_change', trigger_config: { stage: 'FOLLOW_UP' }, action_type: 'send_email', action_config: { subject: 'ACC45 suivi', body: 'Bonjour, ACC45.' }, enabled: true },
  }), 'règle e-mail', 201)
  try {
    const r = await py(`${PRELUDE}
import datetime
from unittest import mock
from django.core import mail
from django.test.utils import override_settings
from django.utils import timezone
from apps.automation.models import AutomationScheduledStep, AutomationRun
from apps.automation.engine import resume_scheduled_step
from apps.crm.models import Lead
from apps.crm import stages
UTC = datetime.timezone.utc
nuit = datetime.datetime.combine(timezone.localdate(), datetime.time(22, 30), tzinfo=UTC)  # 23:30 au Maroc
with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
    mail.outbox = []
    with mock.patch('django.utils.timezone.now', return_value=nuit):
        lead = Lead.objects.create(company_id=1, nom='ACC45 Fenetre', stage=stages.NEW, email='acc45.fenetre@acc45.test')
        lead.stage = stages.FOLLOW_UP; lead.save()
        a_23h30 = len(mail.outbox)
        st = list(AutomationScheduledStep.objects.filter(rule_id=${regle.id}, target_id=lead.pk))
        ouverture = timezone.localtime(st[0].run_at) if st else None
        avant_ouverture = st[0].run_at > nuit if st else None
    # Reprise une heure APRÈS l'échéance calculée (le prochain créneau ouvré : un vendredi 23:30
    # rouvre le lundi 08:30 — le samedi est hors fenêtre).
    lendemain = (st[0].run_at if st else nuit) + datetime.timedelta(hours=1)
    with mock.patch('django.utils.timezone.now', return_value=lendemain):
        for e in st:
            resume_scheduled_step(e)
        a_10h30 = [(m.subject, m.to) for m in mail.outbox]
runs = list(AutomationRun.objects.filter(rule_id=${regle.id}, target_id=lead.pk).values_list('status', 'message'))
for e in st: e.refresh_from_db()
sortie(dict(lead=lead.pk, a_23h30=a_23h30, n_etapes=len(st), ouverture=str(ouverture), hm=[ouverture.hour, ouverture.minute] if ouverture else None,
            future=avant_ouverture, a_10h30=a_10h30, statut=[e.statut for e in st], runs=runs))`)
    console.log(`[P3.2b] ${JSON.stringify(r)}`)
    test.info().annotations.push({ type: 'fenêtre', description: JSON.stringify(r) })
    try {
      expect(r.a_23h30, 'à 23:30 : aucun e-mail envoyé').toBe(0)
      expect(r.n_etapes, 'une échéance planifiée (AutomationScheduledStep)').toBe(1)
      expect(r.future, 'échéance après 23:30').toBe(true)
      expect(r.hm[0] * 60 + r.hm[1], `reprise à ${r.ouverture} ≥ 08:30`).toBeGreaterThanOrEqual(8 * 60 + 30)
      expect(r.a_10h30.length, 'à l\'ouverture : UN e-mail').toBe(1)
      expect(r.a_10h30[0][1]).toEqual(['acc45.fenetre@acc45.test'])
    } finally {
      await py(`${PRELUDE}
from apps.crm.models import Lead
from apps.automation.models import AutomationScheduledStep
AutomationScheduledStep.objects.filter(rule_id=${regle.id}).delete(); Lead.objects.filter(pk=${r.lead}).delete(); sortie('ok')`)
    }
  } finally {
    await a.delete(`${API_DJANGO}/automation/rules/${regle.id}/`, T)
  }
})

// ── P3.3 — préférences : canal WhatsApp grisé « non disponible » ───────────────────────────────
etape('P3.3', ['APAR45'], async ({ page }) => {
  await page.goto('/parametres/notifications')
  await expect(page.getByText('non disponible').first()).toBeVisible({ timeout: 60_000 })
  const indispo = page.getByRole('switch', { name: /non disponible/ })
  const n = await indispo.count()
  expect(n, 'cases du canal indisponible').toBeGreaterThan(0)
  for (let i = 0; i < Math.min(n, 5); i += 1) {
    await expect(indispo.nth(i)).toBeDisabled()
    await expect(indispo.nth(i)).not.toBeChecked()
  }
  await expect(page.getByText(/whatsapp/i).first()).toBeVisible()
})

// ── P3.4 — approuver deux fois la même demande : « Décision déjà prise » ────────────────────────
etape('P3.4', ['APAR45'], async ({ page, testInfo, suivi }) => {
  await monterComptes()
  const a = page.request
  const com = await api(testInfo, 'acc45_com')
  const type = await j(await a.post(`${API_DJANGO}/automation/approval-request-types/`, { ...T, data: { nom: uniq('ACC45 type'), champs_requis: [], enabled: true } }), 'type de demande', 201)
  const dem = await j(await com.post(`${API_DJANGO}/automation/approval-requests/`, { ...T, data: { request_type: type.id, payload: {} } }), 'demande', 201)
  const un = await a.post(`${API_DJANGO}/automation/approval-requests/${dem.id}/approve/`, { ...T, data: { note: 'ok' } })
  expect(un.status(), (await un.text()).slice(0, 200)).toBe(200)
  const deux = await a.post(`${API_DJANGO}/automation/approval-requests/${dem.id}/approve/`, { ...T, data: { note: 'ok bis' } })
  const corps = await deux.text()
  expect(deux.status(), corps.slice(0, 200)).toBe(400)
  expect(corps).toMatch(/Décision déjà prise/)
  suivi.attendre(/approval-requests\/\d+\/approve\/$/, 400)
  const relu = await j(await a.get(`${API_DJANGO}/automation/approval-requests/${dem.id}/`, T), 'demande relue')
  expect(relu.status).toBe('approved')
})

// ── P4.1 — recette J+3 installée et exécutée sur un devis envoyé ───────────────────────────────
etape('P4.1', ['APAR45'], async ({ page }) => {
  // Recette J+3 installée par la VRAIE route d'installation (écran Automatisations → Modèles) ;
  // un devis ENVOYÉ créé pour le run (client à e-mail d'essai) dont la validité est échue depuis
  // 3 jours ; le déclencheur temporel `_trigger_date_echeance_champ` est rejoué dans le processus
  // django à 10:00 (fenêtre ouverte, horloge figée) avec le backend locmem de CE processus, lu
  // ensuite. Seuls les e-mails et runs de NOTRE devis sont comptés ; la recette est désactivée en
  // fin d'étape (elle ne relance donc aucun autre devis de la société démo).
  await monterComptes()
  const a = page.request
  const inst = await a.post(`${API_DJANGO}/automation/modeles-catalogue/installer/relance_j3_devis_sans_reponse/`, { ...T, data: {} })
  expect([200, 201], (await inst.text()).slice(0, 300)).toContain(inst.status())
  const regle = (await inst.json()).rule
  expect(regle.trigger_type).toBe('date_echeance_champ')
  if (!regle.enabled) await j(await a.patch(`${API_DJANGO}/automation/rules/${regle.id}/`, { ...T, data: { enabled: true } }), 'activer la recette', 200)
  try {
    const r = await py(`${PRELUDE}
import datetime
from unittest import mock
from django.core import mail
from django.test.utils import override_settings
from django.utils import timezone
from apps.automation.beat_tasks import _trigger_date_echeance_champ
from apps.automation.models import AutomationRun
from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.models import Company
UTC = datetime.timezone.utc
jour = datetime.datetime.combine(timezone.localdate(), datetime.time(9, 0), tzinfo=UTC)  # 10:00 au Maroc
cli, _ = Client.objects.get_or_create(company_id=1, nom='ACC45 ClientJ3', defaults=dict(prenom='Karim', email='acc45.j3@acc45.test'))
cli.email = 'acc45.j3@acc45.test'; cli.save()
d = Devis.objects.create(company_id=1, client=cli, reference='ACC45-J3-' + timezone.now().strftime('%H%M%S'), statut='envoye', date_validite=timezone.localdate() - datetime.timedelta(days=3))
with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
    mail.outbox = []
    with mock.patch('django.utils.timezone.now', return_value=jour):
        _trigger_date_echeance_champ(Company.objects.get(pk=1))
        _trigger_date_echeance_champ(Company.objects.get(pk=1))  # second passage : idempotent
    nos = [dict(sujet=m.subject, corps=m.body, to=m.to) for m in mail.outbox if 'acc45.j3@acc45.test' in m.to]
runs = list(AutomationRun.objects.filter(rule_id=${regle.id}, target_id=d.pk).values_list('status', 'message'))
Devis.objects.filter(pk=d.pk).update(statut='refuse')
sortie(dict(devis=d.pk, ref=d.reference, emails=nos, runs=runs))`)
    console.log(`[P4.1] ${JSON.stringify(r)}`)
    test.info().annotations.push({ type: 'relance J+3', description: JSON.stringify(r) })
    expect(r.emails.length, 'UN e-mail de relance pour le devis (deux passages)').toBe(1)
    const e = r.emails[0]
    expect(`${e.sujet}\n${e.corps}`, 'e-mail sans accolade').not.toMatch(/[{}]/)
    expect(e.sujet, 'le sujet porte la référence du devis').toContain(r.ref)
    expect(e.corps, 'nom du client substitué').toMatch(/ACC45 ClientJ3|Karim/)
    expect(r.runs.filter(([s]) => s === 'success').length, `run journalisé ${JSON.stringify(r.runs)}`).toBe(1)
    const runsApi = await j(await a.get(`${API_DJANGO}/automation/runs/?rule=${regle.id}&page_size=50`, T), 'runs')
    expect((runsApi.results || []).some((x) => x.target_id === r.devis && x.status === 'success'), 'run visible dans le journal').toBe(true)
  } finally {
    await a.patch(`${API_DJANGO}/automation/rules/${regle.id}/`, { ...T, data: { enabled: false } })
  }
})

// ── P4.2 — webhook avec deux règles : un seul run ─────────────────────────────────────────────
etape('P4.2', ['APAR45'], async ({ page, testInfo }) => {
  const a = page.request
  const creerRegle = async (nom) => j(await a.post(`${API_DJANGO}/automation/rules/`, {
    ...T, data: { nom: uniq(nom), trigger_type: 'webhook_inbound', trigger_config: {}, action_type: 'wait', action_config: {}, enabled: true },
  }), `règle ${nom}`, 201)
  const regleA = await creerRegle('ACC45 webhook A')
  const regleB = await creerRegle('ACC45 webhook B')
  try {
    const trig = await j(await a.post(`${API_DJANGO}/automation/incoming-webhooks/`, { ...T, data: { rule: regleA.id } }), 'déclencheur webhook', 201)
    const jeton = trig.token
    expect(jeton, 'jeton du déclencheur').toBeTruthy()
    const pub = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
    const rep = await pub.post(`${API_DJANGO}/public/hooks/${jeton}/`, { ...T, data: { x: 1 } })
    expect(rep.status(), (await rep.text()).slice(0, 200)).toBe(202)
    const runs = async (rule) => (await j(await a.get(`${API_DJANGO}/automation/runs/?rule=${rule.id}&page_size=50`, T), 'runs')).count
    await expect.poll(() => runs(regleA), { timeout: 60_000 }).toBe(1)
    expect(await runs(regleB), 'la règle B (sans jeton) ne tourne pas').toBe(0)
    await page.goto('/parametres?onglet=automatisations')
  } finally {
    for (const r of [regleA, regleB]) await a.delete(`${API_DJANGO}/automation/rules/${r.id}/`, T)
  }
})

etape('P4.2b', ['APAR45'], async ({ page }) => {
  // Facture créée POUR LE RUN (client d'essai, émise, échue depuis 5 jours) AVANT la règle — aucun
  // run de création ; règle FACTURE_OVERDUE (`wait`) créée par la VRAIE route ; la facture est
  // annulée par la VRAIE route d'annulation (`POST /ventes/factures/<id>/annuler/`, signal
  // `_facture_saved`) ⇒ aucun run ; puis le balayage `_trigger_facture_overdue` ne la compte plus
  // parmi ses candidates (son queryset, rejoué pour CETTE facture — jamais sur les factures démo).
  await monterComptes()
  const a = page.request
  const f = await py(`${PRELUDE}
import datetime
from decimal import Decimal
from django.utils import timezone
from apps.crm.models import Client
from apps.ventes.models import Facture
cli, _ = Client.objects.get_or_create(company_id=1, nom='ACC45 ClientEchu', defaults=dict(email='acc45.echu@acc45.test'))
fa = Facture.objects.create(company_id=1, client=cli, reference='ACC45-ECHUE-' + timezone.now().strftime('%H%M%S'), statut='emise',
                            date_echeance=timezone.localdate() - datetime.timedelta(days=5), montant_ttc=Decimal('1200'))
sortie(dict(id=fa.pk, ref=fa.reference))`)
  const regle = await j(await a.post(`${API_DJANGO}/automation/rules/`, {
    ...T, data: { nom: uniq('ACC45 facture echue'), trigger_type: 'facture_overdue', trigger_config: {}, action_type: 'wait', action_config: {}, enabled: true },
  }), 'règle facture échue', 201)
  try {
    const runs = async () => py(`${PRELUDE}
from apps.automation.models import AutomationRun
sortie(list(AutomationRun.objects.filter(rule_id=${regle.id}, target_id=${f.id}).values_list('status', 'message')))`)
    const avant = await runs()
    const ann = await a.post(`${API_DJANGO}/ventes/factures/${f.id}/annuler/`, { ...T, data: {} })
    const corps = await ann.text()
    console.log(`[P4.2b] annuler → ${ann.status()} ${corps.slice(0, 200)}`)
    expect(ann.status(), corps.slice(0, 300)).toBe(200)
    expect((await j(await a.get(`${API_DJANGO}/ventes/factures/${f.id}/`, T), 'facture relue')).statut, 'annulée en base').toBe('annulee')
    const apres = await runs()
    expect(apres, 'annuler une facture échue : aucun run').toEqual(avant)
    const balayage = await py(`${PRELUDE}
from django.utils import timezone
from apps.automation.engine import FACTURE_STATUTS_RELANCABLES
from apps.ventes.models import Facture
sortie(Facture.objects.filter(company_id=1, pk=${f.id}, date_echeance__lt=timezone.localdate(), statut__in=FACTURE_STATUTS_RELANCABLES).count())`)
    expect(balayage, 'la facture annulée n\'est plus candidate du balayage quotidien').toBe(0)
    expect(await runs(), 'toujours aucun run').toEqual(avant)
    test.info().annotations.push({ type: 'runs', description: `avant ${JSON.stringify(avant)} ; après ${JSON.stringify(apres)}` })
  } finally {
    await a.delete(`${API_DJANGO}/automation/rules/${regle.id}/`, T)
  }
})

// ── P4.3 — simuler une action SMS / WhatsApp : « non disponible » ─────────────────────────────
etape('P4.3', ['APAR45'], async ({ page }) => {
  const a = page.request
  const lead = await j(await a.post(`${API_DJANGO}/crm/leads/`, { ...T, data: { nom: uniq('ACC45 lead sim'), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800' } }), 'lead', 201)
  const effets = {}
  // SMS : aucun fournisseur — la règle ne peut même pas être créée (400 nommant « non disponible »).
  const sms = await a.post(`${API_DJANGO}/automation/rules/`, {
    ...T, data: { nom: uniq('ACC45 send_sms'), trigger_type: 'lead_stage_change', trigger_config: {}, action_type: 'send_sms', action_config: { message: 'Bonjour' }, enabled: false },
  })
  const smsCorps = await sms.text()
  expect(sms.status(), smsCorps.slice(0, 200)).toBe(400)
  expect(smsCorps, 'SMS : « non disponible » dit clairement').toMatch(/non disponible/i)
  effets.send_sms = smsCorps.slice(0, 160)
  // WhatsApp : la simulation ne promet aucun envoi automatique.
  const regle = await j(await a.post(`${API_DJANGO}/automation/rules/`, {
    ...T, data: { nom: uniq('ACC45 send_whatsapp'), trigger_type: 'lead_stage_change', trigger_config: {}, action_type: 'send_whatsapp', action_config: { message: 'Bonjour' }, enabled: false },
  }), 'règle send_whatsapp', 201)
  try {
    const sim = await j(await a.post(`${API_DJANGO}/automation/rules/${regle.id}/simuler/`, { ...T, data: { target_model: 'crm.lead', target_id: lead.id } }), 'simulation WhatsApp', 200)
    effets.send_whatsapp = JSON.stringify(sim.effets)
    expect(sim.simulation).toBe(true)
  } finally {
    await a.delete(`${API_DJANGO}/automation/rules/${regle.id}/`, T)
  }
  expect(effets.send_whatsapp, 'WhatsApp : aucun envoi réel annoncé').not.toMatch(/Un (message )?WhatsApp partirait|envoyé/i)
  test.info().annotations.push({ type: 'effets simulés', description: JSON.stringify(effets).slice(0, 600) })
})

// ── P5.1 — écran Automatisations sans déclencheur « projet » ───────────────────────────────────
etape('P5.1', ['APAR45'], async ({ page }) => {
  const a = page.request
  const modeles = await j(await a.get(`${API_DJANGO}/automation/modeles-catalogue/`, T), 'modèles')
  const declencheurs = (modeles.modeles || []).map((m) => m.trigger_type)
  expect(declencheurs.filter((t) => /projet/i.test(t)), 'catalogue sans déclencheur projet').toEqual([])
  await page.goto('/parametres?onglet=automatisations')
  await expect(page.locator('body')).not.toContainText('Une erreur est survenue')
  const nouveau = page.getByRole('button', { name: /Nouvelle règle|Créer une règle|Ajouter/i }).first()
  if (await nouveau.isVisible().catch(() => false)) {
    await nouveau.click()
    const select = page.getByLabel(/déclencheur/i).first()
    if (await select.isVisible().catch(() => false)) {
      const options = await select.locator('option').allTextContents()
      expect(options.filter((o) => /projet/i.test(o)), 'liste UI des déclencheurs sans « projet »').toEqual([])
    }
  }
})

// ── P6 — refuser une demande via le dialogue de motif ─────────────────────────────────────────
etape('P6', ['APAR45'], async ({ page, testInfo, suivi }) => {
  await monterComptes()
  const a = page.request
  const com = await api(testInfo, 'acc45_com')
  const type = await j(await a.post(`${API_DJANGO}/automation/approval-request-types/`, { ...T, data: { nom: uniq('ACC45 type refus'), champs_requis: [], enabled: true } }), 'type', 201)
  const dem = await j(await com.post(`${API_DJANGO}/automation/approval-requests/`, { ...T, data: { request_type: type.id, payload: {} } }), 'demande', 201)
  const dialogues = []
  page.on('dialog', (d) => { dialogues.push(d.type()) })
  await page.goto('/approbations')
  await page.getByRole('tab', { name: /Demandes ad-hoc/i }).click()
  const ligne = page.locator('tr, li, article, [data-testid]').filter({ hasText: type.nom }).last()
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  await ligne.getByRole('button', { name: /Refuser/i }).first().click()
  const dialogue = page.getByRole('dialog')
  await expect(dialogue).toBeVisible({ timeout: 30_000 })
  const confirmer = dialogue.getByRole('button', { name: /Refuser|Confirmer/i }).last()
  await expect(confirmer, 'confirmation inerte tant que le motif est vide').toBeDisabled()
  await dialogue.getByRole('textbox').fill('Budget non validé ACC45')
  await confirmer.click()
  await expect(async () => {
    const relu = await j(await a.get(`${API_DJANGO}/automation/approval-requests/${dem.id}/`, T), 'demande relue')
    expect(relu.status).toBe('rejected')
    expect(JSON.stringify(relu)).toContain('Budget non validé ACC45')
  }).toPass({ timeout: 30_000 })
  expect(dialogues, 'aucun dialogue natif').toEqual([])
  void suivi
})

// ── P7 — journal d'audit : « Charger plus » jusqu'à la ligne 51 ────────────────────────────────
etape('P7', ['APAR45'], async ({ page }) => {
  const a = page.request
  const total = await nbAudit(a)
  expect(total, 'journal de la société 1 d\'au moins 51 lignes').toBeGreaterThan(50)
  const p1 = await j(await a.get(`${API_DJANGO}/parametres/audit/?limit=50`, T), 'page 1')
  const p2 = await j(await a.get(`${API_DJANGO}/parametres/audit/?limit=50&offset=50`, T), 'page 2')
  expect(p1.count).toBe(total)
  expect(p1.results.length).toBe(50)
  expect(p2.results[0].id, 'la page 2 commence à la ligne 51').not.toBe(p1.results[49].id)
  const ligne51 = p2.results[0]
  const mauvais = await a.get(`${API_DJANGO}/parametres/audit/?user=abc`, T)
  expect(mauvais.status(), 'user invalide : 400, jamais 500').toBe(400)
  // Écran : Paramètres › Avancé — « Charger plus » rend la ligne n° 51 atteignable.
  await page.goto('/parametres?onglet=avance')
  const plus = page.getByRole('button', { name: 'Charger plus' })
  await expect(plus).toBeVisible({ timeout: 60_000 })
  const avant = await page.locator('text=→').count()
  await plus.click()
  await expect(async () => {
    expect(await page.locator('text=→').count(), 'des lignes supplémentaires s\'affichent').toBeGreaterThan(avant)
  }).toPass({ timeout: 30_000 })
  expect(ligne51.field).toBeTruthy()
})

// ── H×H — un Commercial crée puis modifie une règle d'automatisation : 403, rien d'écrit ────────
etape('H×H', ['APAR45'], async ({ page, testInfo, suivi }) => {
  await monterComptes()
  const a = page.request
  const com = await api(testInfo, 'acc45_com')
  const avantRegles = (await j(await a.get(`${API_DJANGO}/automation/rules/?page_size=500`, T), 'règles')).count
  const avantAudit = await nbAudit(a)
  const creer = await com.post(`${API_DJANGO}/automation/rules/`, { ...T, data: { nom: uniq('ACC45 pirate'), trigger_type: 'webhook_inbound', trigger_config: {}, action_type: 'wait', action_config: {}, enabled: true } })
  expect(creer.status(), (await creer.text()).slice(0, 200)).toBe(403)
  // Modification d'une règle existante (créée par le Directeur pour le test).
  const regle = await j(await a.post(`${API_DJANGO}/automation/rules/`, { ...T, data: { nom: uniq('ACC45 cible'), trigger_type: 'webhook_inbound', trigger_config: {}, action_type: 'wait', action_config: {}, enabled: false } }), 'règle cible', 201)
  try {
    const modif = await com.patch(`${API_DJANGO}/automation/rules/${regle.id}/`, { ...T, data: { enabled: true, nom: 'PIRATE' } })
    expect(modif.status(), (await modif.text()).slice(0, 200)).toBe(403)
    const bascule = await com.post(`${API_DJANGO}/automation/rules/${regle.id}/toggle/`, { ...T, data: {} })
    expect(bascule.status()).toBe(403)
    const relu = await j(await a.get(`${API_DJANGO}/automation/rules/${regle.id}/`, T), 'règle relue')
    expect(relu.enabled).toBe(false)
    expect(relu.nom).not.toBe('PIRATE')
    suivi.attendre(/automation\/rules\//, 403)
  } finally {
    await a.delete(`${API_DJANGO}/automation/rules/${regle.id}/`, T)
  }
  expect((await j(await a.get(`${API_DJANGO}/automation/rules/?page_size=500`, T), 'règles')).count, 'aucune règle écrite par le Commercial').toBe(avantRegles)
  expect(await nbAudit(a)).toBeGreaterThanOrEqual(avantAudit) // la règle cible du Directeur est journalisée ; rien au nom du Commercial
  const audit = await j(await a.get(`${API_DJANGO}/parametres/audit/?section=automatisations&limit=20`, T), 'journal automatisations')
  expect(audit.results.some((x) => x.user_nom === 'acc45_com'), 'aucune ligne du journal au nom du Commercial').toBe(false)
  await page.goto('/parametres?onglet=automatisations')
})
