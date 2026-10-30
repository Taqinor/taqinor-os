// ACRM60 — acceptation en direct du groupe ACRM (audit CRM) : rejeu, sur la pile locale, des
// parcours de portée, de données lead/client, de cadence et de signaux dont les reproductions
// d'origine sont citées dans la tâche, avec des comptes à rôle réel (Commercial, Commercial terrain,
// Admin RH, Technicien, Viewer, rôle personnalisé sans `client_pii_voir`, Directeur) et la société 43
// en témoin. Comptes `acc60_*` créés par `manage.py shell` (E2E_DJANGO_EXEC) avec un mot de passe
// d'essai local, désactivés en fin de spec ; données `ACC60 …` d'essai. Aucune donnée de production.
//
// Chaque refus est suivi d'une RELECTURE EN BASE (clause persistance). Les étapes non jouables sur
// cette pile (site public, canaux externes) ne sont pas simulées : elles ne figurent pas dans `couvre`.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawn } from 'node:child_process'
import { groupe } from './_oracles.js'
import { API_DJANGO, textePdf, telephoneMobileUnique, lireJson, listeDe } from '../helpers.js'

const etape = groupe('ACRM', ['ACRM3', 'ACRM4', 'ACRM5', 'ACRM6', 'ACRM7', 'ACRM8', 'ACRM13', 'ACRM23', 'ACRM24', 'ACRM25', 'ACRM26', 'ACRM30', 'ACRM40', 'ACRM45', 'ACRM12', 'ACRM15', 'ACRM17', 'ACRM20', 'ACRM22', 'ACRM32', 'ACRM35', 'ACRM37', 'ACRM38', 'ACRM46', 'ACRM55', 'ACRM21', 'ACRM42', 'ACRM11', 'ACRM41', 'ACRM14', 'ACRM19', 'ACRM59', 'ACRM10', 'ACRM27', 'ACRM34'])
test.describe.configure({ timeout: 600_000 })

const PW = 'Acc60-essai-local-2026!'
const T = { timeout: 120_000 }
const TEL = '+212661909901'

/** Un `manage.py shell` persistant (démarrage ~1 min) : code en base64 par ligne, réponse `@@R<json>`. */
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
from apps.roles.models import Role
from apps.crm.models import Lead, Client
U = get_user_model()
def sortie(o): print('@@' + json.dumps(o, default=str))
`
const base = (testInfo) => testInfo.project.use.baseURL
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
const sansId = (j) => { const c = JSON.parse(JSON.stringify(j)); if (c?.error) delete c.error.request_id; return JSON.stringify(c) }

const COMPTES = {
  acc60_dir: { role: 1 },
  acc60_com: { role: 4 },
  acc60_com2: { role: 4 }, // le « collègue » : ses leads sont hors portée de acc60_com
  acc60_cresp: { role: 3 },
  acc60_terrain: { role: 70 },
  acc60_rh: { role: 71 },
  acc60_tech: { role: 6 },
  acc60_viewer: { role: 7 },
  acc60_nopii: { role: 'NOPII' },
  acc60_b: { role: 91, societe: 43 },
}
let monde = null
async function monter() {
  if (monde) return monde
  monde = await py(`${PRELUDE}
base = Role.objects.get(pk=4)
nopii, _ = Role.objects.get_or_create(company_id=1, nom='acc60 sans client_pii_voir', defaults=dict(permissions=[]))
nopii.permissions = [p for p in base.permissions if p != 'client_pii_voir']; nopii.save()
C = json.loads('${JSON.stringify(COMPTES)}')
ids = {}
for nom, c in C.items():
    soc = c.get('societe', 1)
    role_id = nopii.id if c['role'] == 'NOPII' else c['role']
    u, _ = U.objects.get_or_create(username=nom, defaults=dict(company_id=soc, role_id=role_id))
    u.company_id = soc; u.role_id = role_id; u.is_active = True; u.email = nom + '@acc60.test'
    u.must_change_password = False; u.failed_login_count = 0; u.locked_until = None; u.set_password('${PW}'); u.save()
    ids[nom] = u.id
def lead(nom, owner, **kw):
    l, _ = Lead.objects.get_or_create(company_id=1, nom=nom, defaults=dict(owner_id=ids[owner], telephone=kw.pop('telephone', '')))
    l.owner_id = ids[owner]; l.save(); return l
l_mien = lead('ACC60 Mien', 'acc60_com')
l_coll = lead('ACC60 Collegue', 'acc60_com2')
l_nopii = lead('ACC60 Masque', 'acc60_nopii', telephone='${TEL}')
Lead.objects.filter(pk=l_nopii.pk).update(telephone='${TEL}')
cli_h, _ = Client.objects.get_or_create(company_id=1, nom='ACC60 ClientHors')
Lead.objects.filter(pk=l_coll.pk).update(client=cli_h)
cli_t, _ = Client.objects.get_or_create(company_id=1, nom='ACC60 ClientTemoin', defaults=dict(telephone='${TEL}'))
Lead.objects.filter(pk=l_nopii.pk).update(client=cli_t)
sortie(dict(ids=ids, mien=l_mien.id, coll=l_coll.id, nopii=l_nopii.id, cli_h=cli_h.id, cli_t=cli_t.id))`)
  return monde
}
test.afterAll(async () => {
  try {
    await py(`${PRELUDE}
U.objects.filter(username__startswith='acc60_').update(is_active=False)
Role.objects.filter(company_id=1, nom='acc60 sans client_pii_voir').exists(); sortie('ok')`)
  } catch { /* nettoyage au mieux */ }
  serveur?.proc.stdin.end()
})

// ── P5.1 — portée des clients, PII, équipes (ACRM3, ACRM4, ACRM5, ACRM26) ──────────────────
etape('P5.1', ['ACRM3', 'ACRM4', 'ACRM5'], async ({ testInfo }) => {
  const m = await monter()
  const refus = []
  for (const compte of ['acc60_terrain', 'acc60_rh']) {
    const c = await api(testInfo, compte)
    for (const chemin of ['/crm/clients/', `/crm/clients/${m.cli_t}/`, '/crm/clients/search/?q=ACC60', `/crm/clients/${m.cli_t}/documents/`, '/crm/clients/dormants/', '/crm/clients/mon-portefeuille/']) {
      const r = await c.get(`${API_DJANGO}${chemin}`, T)
      refus.push(`${compte} GET ${chemin} → ${r.status()}`)
      expect(r.status(), `${compte} GET ${chemin}`).toBe(403)
    }
  }
  // Technicien : garde l'accès (sav_voir + client_pii_voir) et ne voit aucun lead.
  const tech = await api(testInfo, 'acc60_tech')
  expect((await tech.get(`${API_DJANGO}/crm/clients/`, T)).status(), 'Technicien : liste clients').toBe(200)
  const st = await tech.get(`${API_DJANGO}/crm/clients/search/?q=ACC60`, T)
  expect(st.status()).toBe(200)
  expect(await st.text(), 'aucun résultat lead pour le Technicien').not.toContain('ACC60 Masque')
  // Viewer : relancer-dormance refusé.
  const viewer = await api(testInfo, 'acc60_viewer')
  const rd = await viewer.post(`${API_DJANGO}/crm/clients/${m.cli_t}/relancer-dormance/`, T)
  expect(rd.status(), 'Viewer relancer-dormance').toBe(403)

  // ACRM4 / ACRM5 : le rôle sans client_pii_voir ne reçoit le numéro témoin nulle part.
  const nopii = await api(testInfo, 'acc60_nopii')
  const fiche = await nopii.get(`${API_DJANGO}/crm/leads/${m.nopii}/`, T)
  expect(fiche.status()).toBe(200)
  const corps = await fiche.json()
  expect(corps.pii_masked, 'pii_masked').toBe(true)
  expect(corps.telephone ?? null).toBeNull()
  expect(corps.phone_normalise ?? null, 'phone_normalise masqué (ACRM5)').toBeNull()
  expect(JSON.stringify(corps)).not.toContain('661909901')
  for (const chemin of ['/crm/leads/', '/crm/leads/doublons/', `/crm/leads/${m.nopii}/historique/`, '/crm/clients/search/?q=ACC60']) {
    const r = await nopii.get(`${API_DJANGO}${chemin}`, T)
    const txt = await r.text()
    refus.push(`nopii GET ${chemin} → ${r.status()}`)
    expect(r.status(), `nopii GET ${chemin}`).toBeLessThan(500)
    expect(txt, `numéro témoin absent de ${chemin}`).not.toContain('661909901')
  }
  // Commercial complet : voit phone_normalise comme aujourd'hui.
  await py(`${PRELUDE}
Lead.objects.filter(pk=${m.mien}).update(telephone='${TEL}'); sortie('ok')`)
  const com = await api(testInfo, 'acc60_com')
  const complet = await (await com.get(`${API_DJANGO}/crm/leads/${m.mien}/`, T)).json()
  expect(complet.pii_masked).toBeFalsy()
  expect(String(complet.phone_normalise || '')).toContain('661909901')
  test.info().annotations.push({ type: 'refus', description: refus.join(' ; ') })
})

etape('P5.1b', ['ACRM26'], async ({ testInfo }) => {
  const m = await monter()
  const eq = await py(`${PRELUDE}
from apps.crm.models import EquipeCommerciale
e, _ = EquipeCommerciale.objects.get_or_create(company_id=1, nom='ACC60 Equipe collegue', defaults=dict(responsable_id=${m.ids.acc60_com2}))
e.responsable_id = ${m.ids.acc60_com2}; e.save(); sortie(e.id)`)
  const com = await api(testInfo, 'acc60_com')
  const r = await com.patch(`${API_DJANGO}/crm/equipes/${eq}/`, { ...T, data: { responsable: m.ids.acc60_com } })
  expect(r.status(), 'Commercial ne se nomme pas responsable').toBe(403)
  expect((await com.post(`${API_DJANGO}/crm/equipes/`, { ...T, data: { nom: 'ACC60 Mienne' } })).status()).toBe(403)
  expect((await com.delete(`${API_DJANGO}/crm/equipes/${eq}/`, T)).status()).toBe(403)
  const rel = await py(`${PRELUDE}
from apps.crm.models import EquipeCommerciale
sortie(EquipeCommerciale.objects.get(pk=${eq}).responsable_id)`)
  expect(rel, 'responsable inchangé en base').toBe(m.ids.acc60_com2)
  expect((await com.get(`${API_DJANGO}/crm/equipes/`, T)).status(), 'lecture ouverte').toBe(200)
  const rollup = await com.get(`${API_DJANGO}/crm/forecast/rollup/`, T)
  expect(rollup.status()).toBe(200)
  expect((await rollup.json()).equipes.map((e) => e.equipe_id)).not.toContain(eq)
  const dir = await api(testInfo, 'acc60_dir')
  const ok = await dir.patch(`${API_DJANGO}/crm/equipes/${eq}/`, { ...T, data: { nom: 'ACC60 Equipe collegue' } })
  expect(ok.status(), 'un admin modifie l\'équipe').toBe(200)
})

etape('P5.1c', ['ACRM24'], async ({ testInfo }) => {
  const m = await monter()
  const id = await py(`${PRELUDE}
import uuid
from apps.crm.models import VisiteExterne, AppareilEquipe
a = str(uuid.uuid4())
VisiteExterne.objects.create(company_id=1, lead_id=${m.coll}, appareil_id=a)
sortie(a)`)
  const viewer = await api(testInfo, 'acc60_viewer')
  const r = await viewer.post(`${API_DJANGO}/crm/appareils-equipe/ce-navigateur/`, { ...T, data: { appareil_id: id } })
  expect(r.status(), await r.text()).toBe(200)
  const corps = await r.json()
  expect(corps.appareil_id, 'uuid neuf rendu').not.toBe(id)
  const rel = await py(`${PRELUDE}
from apps.crm.models import AppareilEquipe
sortie(dict(prospect=AppareilEquipe.objects.filter(company_id=1, appareil_id='${id}').count(), neuf=AppareilEquipe.objects.filter(company_id=1, appareil_id='${corps.appareil_id}').count()))`)
  expect(rel, 'l\'appareil du prospect n\'est pas inscrit ; l\'uuid neuf l\'est').toEqual({ prospect: 0, neuf: 1 })
})

// ── P5.2 — objets secondaires et enfants bornés à la portée (ACRM7, ACRM8, ACRM25) ─────────
etape('P5.2', ['ACRM7', 'ACRM8'], async ({ testInfo }) => {
  const m = await monter()
  const com = await api(testInfo, 'acc60_com')
  // ACRM7 : lier un client d'une autre équipe → refus sous le champ, comme un id absent.
  expect((await com.get(`${API_DJANGO}/crm/clients/${m.cli_h}/`, T)).status(), 'client hors portée : 404').toBe(404)
  const hors = await com.post(`${API_DJANGO}/crm/leads/${m.mien}/convertir-client/`, { ...T, data: { mode: 'lier', client_id: m.cli_h } })
  const absent = await com.post(`${API_DJANGO}/crm/leads/${m.mien}/convertir-client/`, { ...T, data: { mode: 'lier', client_id: 99999999 } })
  expect(hors.status()).toBe(404)
  expect(absent.status()).toBe(404)
  const jh = await hors.json()
  expect(jh.client_id).toEqual(['Client introuvable.'])
  expect(sansId(jh), 'hors portée = absent').toBe(sansId(await absent.json()))
  expect(await py(`${PRELUDE}
sortie(Lead.objects.get(pk=${m.mien}).client_id)`), 'lead non lié').toBeNull()
  // ACRM8 : RDV sur un lead d'une autre équipe → 400 « Lead introuvable. », rien d'écrit ; sur le sien → 201.
  const quand = new Date(Date.now() + 3 * 864e5).toISOString()
  const compter = async () => py(`${PRELUDE}
from apps.crm.models import Appointment, LeadActivity
sortie([Appointment.objects.filter(lead_id=${m.coll}).count(), LeadActivity.objects.filter(lead_id=${m.coll}).count()])`)
  const avant = await compter()
  const rh = await com.post(`${API_DJANGO}/crm/appointments/`, { ...T, data: { lead: m.coll, scheduled_at: quand } })
  const ra = await com.post(`${API_DJANGO}/crm/appointments/`, { ...T, data: { lead: 99999999, scheduled_at: quand } })
  expect(rh.status()).toBe(400)
  expect(ra.status()).toBe(400)
  expect((await rh.json()).lead).toEqual(['Lead introuvable.'])
  expect(sansId(await rh.json())).toBe(sansId(await ra.json()))
  expect(await compter(), 'aucun RDV ni chatter sur le lead du collègue').toEqual(avant)
  const mien = await com.post(`${API_DJANGO}/crm/appointments/`, { ...T, data: { lead: m.mien, scheduled_at: quand } })
  expect(mien.status(), await mien.text()).toBe(201)
  await com.delete(`${API_DJANGO}/crm/appointments/${(await mien.json()).id}/`, T)
})

etape('P5.2b', ['ACRM25'], async ({ testInfo }) => {
  await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const lister = async () => {
    const r = await dir.get(`${API_DJANGO}/crm/motifs-perte/`, T)
    expect(r.status()).toBe(200)
    const j = await r.json()
    return (Array.isArray(j) ? j : j.results || [])
  }
  const avant = await lister()
  const prix = avant.find((x) => x.nom === 'Prix')
  if (!prix) throw new Error('NON JOUABLE : la société démo n\'a pas le motif standard « Prix » (déjà renommé par un autre rejeu)')
  try {
    const r = await dir.patch(`${API_DJANGO}/crm/motifs-perte/${prix.id}/`, { ...T, data: { nom: 'Prix trop élevé' } })
    expect(r.status(), await r.text()).toBe(200)
    for (const lecture of [1, 2]) { // « recharger Paramètres » : deux lectures successives
      const noms = (await lister()).map((x) => x.nom)
      expect(noms.filter((n) => /^Prix/.test(n)), `lecture ${lecture} : un seul libellé « Prix… »`).toEqual(['Prix trop élevé'])
    }
  } finally {
    await dir.patch(`${API_DJANGO}/crm/motifs-perte/${prix.id}/`, { ...T, data: { nom: 'Prix' } })
  }
})

// ── P5.4 / ACRM30 — placement et recherche bornés à la portée (ACRM6, ACRM30) ──────────────
etape('P5.4', ['ACRM6'], async ({ testInfo }) => {
  const m = await monter()
  await py(`${PRELUDE}
from apps.crm.models import RelanceEtape
for pk in (${m.mien}, ${m.coll}):
    Lead.objects.filter(pk=pk).update(stage='contacted', relance_date=None, date_creation=timezone.now() - datetime.timedelta(days=60))
RelanceEtape.objects.filter(lead_id__in=[${m.mien}, ${m.coll}]).delete(); sortie('ok')`)
  const com = await api(testInfo, 'acc60_com')
  expect((await com.get(`${API_DJANGO}/crm/leads/${m.coll}/`, T)).status(), 'le lead du collègue répond 404').toBe(404)
  const ap = await com.post(`${API_DJANGO}/crm/leads/placement-cadences/`, { ...T, data: { apply: false } })
  expect(ap.status(), await ap.text()).toBe(200)
  const txt = await ap.text()
  expect(txt, 'le lead du collègue est absent de l aperçu').not.toContain('ACC60 Collegue')
  const avantCom = JSON.parse(txt).total_candidats
  const dir = await api(testInfo, 'acc60_dir')
  const apAdmin = await dir.post(`${API_DJANGO}/crm/leads/placement-cadences/`, { ...T, data: { apply: false } })
  expect(apAdmin.status()).toBe(200)
  const totalAdmin = (await apAdmin.json()).total_candidats
  expect(totalAdmin, 'un admin (portée toute la société) voit plus de candidats que le Commercial').toBeGreaterThan(avantCom)
  // Contre-épreuve différentielle : le lead du collègue passe dans la portée du Commercial → +1 candidat.
  await py(`${PRELUDE}
Lead.objects.filter(pk=${m.coll}).update(owner_id=${m.ids.acc60_com}); sortie('ok')`)
  try {
    const apres = await com.post(`${API_DJANGO}/crm/leads/placement-cadences/`, { ...T, data: { apply: false } })
    expect((await apres.json()).total_candidats, 'dans sa portée, le lead du collègue devient candidat (+1)').toBe(avantCom + 1)
  } finally {
    await py(`${PRELUDE}
Lead.objects.filter(pk=${m.coll}).update(owner_id=${m.ids.acc60_com2}); sortie('ok')`)
  }
  const etapes = await py(`${PRELUDE}
from apps.crm.models import RelanceEtape
sortie(RelanceEtape.objects.filter(lead_id=${m.coll}).count())`)
  expect(etapes, 'aucune touche créée par un aperçu').toBe(0)
})

etape('P4.3', ['ACRM30'], async ({ testInfo }) => {
  const m = await monter()
  await py(`${PRELUDE}
Lead.objects.filter(pk=${m.coll}).update(nom='ACC60 PROBE Collegue'); Lead.objects.filter(pk=${m.mien}).update(nom='ACC60 PROBE Mien', owner_id=${m.ids.acc60_cresp}); sortie('ok')`)
  try {
    const cresp = await api(testInfo, 'acc60_cresp')
    const r = await cresp.get(`${API_DJANGO}/visites/leads-recherche/?q=ACC60 PROBE`, T)
    expect(r.status(), await r.text()).toBe(200)
    const txt = await r.text()
    expect(txt, 'le lead du collègue hors sous-arbre n\'est pas trouvé').not.toContain('PROBE Collegue')
    expect(txt, 'son propre lead est trouvé').toContain('PROBE Mien')
    const dir = await api(testInfo, 'acc60_dir')
    const ra = await dir.get(`${API_DJANGO}/visites/leads-recherche/?q=ACC60 PROBE`, T)
    expect(await ra.text(), 'un admin trouve tout').toContain('PROBE Collegue')
  } finally {
    await py(`${PRELUDE}
Lead.objects.filter(pk=${m.coll}).update(nom='ACC60 Collegue'); Lead.objects.filter(pk=${m.mien}).update(nom='ACC60 Mien', owner_id=${m.ids.acc60_com}); sortie('ok')`)
  }
})

// ── P1.3 — fusion de doublons (ACRM13, ACRM40) ─────────────────────────────────────────────
etape('P1.3', ['ACRM13', 'ACRM40'], async ({ testInfo }) => {
  const m = await monter()
  const ids = await py(`${PRELUDE}
k1, _ = Client.objects.get_or_create(company_id=1, nom='ACC60 K1')
k2, _ = Client.objects.get_or_create(company_id=1, nom='ACC60 K2')
s = Lead.objects.create(company_id=1, nom='ACC60 Survivant', owner_id=${m.ids.acc60_dir}, telephone='+212661606001', inclinaison_deg=0, nb_etages=0, client=k1)
a = Lead.objects.create(company_id=1, nom='ACC60 Absorbe', owner_id=${m.ids.acc60_dir}, telephone='+212661606001', inclinaison_deg=30, nb_etages=2, client=k2)
sortie(dict(s=s.id, a=a.id, k1=k1.id, k2=k2.id))`)
  const dir = await api(testInfo, 'acc60_dir')
  const r = await dir.post(`${API_DJANGO}/crm/leads/${ids.s}/merge/`, { ...T, data: { others: [ids.a] } })
  expect(r.status(), await r.text()).toBe(200)
  const corps = await r.json()
  expect(Number(corps.inclinaison_deg), 'toit plat 0° conservé').toBe(0)
  expect(Number(corps.nb_etages)).toBe(0)
  expect(corps.clients_distincts, 'deux fiches client signalées').toHaveLength(2)
  const rel = await py(`${PRELUDE}
from apps.crm.models import LeadActivity
l = Lead.objects.get(pk=${ids.s})
sortie(dict(inc=str(l.inclinaison_deg), et=l.nb_etages, client=l.client_id,
            note=[a.body for a in LeadActivity.objects.filter(lead=l, body__icontains='Deux fiches client')]))`)
  expect(Number(rel.inc)).toBe(0)
  expect(rel.client, 'le survivant garde K1').toBe(ids.k1)
  expect(rel.note.length, 'note « Deux fiches client » au chatter').toBeGreaterThanOrEqual(1)
})

// ── P2.5 — rappel FDA (ACRM45) et P3 — trace des rendez-vous (ACRM23) ──────────────────────
etape('P2.5', ['ACRM45'], async ({ testInfo }) => {
  const m = await monter()
  await py(`${PRELUDE}
from apps.crm.models import RelanceEtape
RelanceEtape.objects.filter(lead_id=${m.mien}, cle='rappel_fda').delete()
Lead.objects.filter(pk=${m.mien}).update(dossier_subvention='', dossier_subvention_le=None); sortie('ok')`)
  const com = await api(testInfo, 'acc60_com')
  const ouvertes = async () => py(`${PRELUDE}
from apps.crm.models import RelanceEtape
e = RelanceEtape.objects.filter(lead_id=${m.mien}, cle='rappel_fda', statut='a_faire')
sortie(dict(n=e.count(), echeance=[str(x.due_date) for x in e], libelle=[x.libelle for x in e], relance=str(Lead.objects.get(pk=${m.mien}).relance_date)))`)
  const patch = async (corps) => {
    const r = await com.patch(`${API_DJANGO}/crm/leads/${m.mien}/`, { ...T, data: corps })
    expect(r.status(), await r.text()).toBe(200)
  }
  const demain = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)
  await patch({ dossier_subvention: 'accorde', dossier_subvention_le: demain(10) })
  const un = await ouvertes()
  expect(un.n, 'un rappel ouvert après le 1er enregistrement').toBe(1)
  await patch({ dossier_subvention_le: demain(12) })
  const deux = await ouvertes()
  expect(deux.n, 'toujours UN seul rappel après correction de la date').toBe(1)
  expect(deux.libelle[0], 'libellé daté de la nouvelle approbation').not.toBe(un.libelle[0])
  expect(deux.relance, 'relance_date du lead = échéance du rappel (file recalée)').toBe(deux.echeance[0])
  // « Ma file » : le lead y figure (relances du jour/semaine).
  const file = await com.get(`${API_DJANGO}/crm/relance-etapes/?scope=week`, T)
  expect(file.status()).toBeLessThan(500)
  await patch({ dossier_subvention: 'refuse' })
  expect((await ouvertes()).n, 'rappel annulé quand le statut quitte « accordé »').toBe(0)
})

etape('P3.4', ['ACRM23'], async ({ testInfo }) => {
  const m = await monter()
  const com = await api(testInfo, 'acc60_com')
  const quand = new Date(Date.now() + 3 * 864e5).toISOString()
  const cree = await com.post(`${API_DJANGO}/crm/appointments/`, { ...T, data: { lead: m.mien, scheduled_at: quand } })
  expect(cree.status(), await cree.text()).toBe(201)
  const id = (await cree.json()).id
  await py(`${PRELUDE}
from apps.crm.models import Appointment
Appointment.objects.filter(pk=${id}).update(reminder_sent=True); sortie('ok')`)
  const notes = async () => py(`${PRELUDE}
from apps.crm.models import LeadActivity, Appointment
sortie(dict(notes=list(LeadActivity.objects.filter(lead_id=${m.mien}, body__startswith='RDV #${id}').values_list('body', flat=True)),
            rappel=Appointment.objects.filter(pk=${id}).values_list('reminder_sent', flat=True).first()))`)
  const dep = await com.patch(`${API_DJANGO}/crm/appointments/${id}/`, { ...T, data: { scheduled_at: new Date(Date.now() + 6 * 864e5).toISOString(), statut: 'planifie' } })
  expect(dep.status(), await dep.text()).toBe(200)
  const a = await notes()
  expect(a.notes.some((n) => /déplacé du/.test(n)), JSON.stringify(a.notes)).toBe(true)
  expect(a.rappel, 'rappel réarmé après le déplacement').toBe(false)
  const ann = await com.patch(`${API_DJANGO}/crm/appointments/${id}/`, { ...T, data: { statut: 'annule' } })
  expect(ann.status()).toBe(200)
  const b = await notes()
  expect(b.notes.some((n) => /Planifié → Annulé/.test(n) && /acc60_com/.test(n)), JSON.stringify(b.notes)).toBe(true)
  const sup = await com.delete(`${API_DJANGO}/crm/appointments/${id}/`, T)
  expect([200, 204]).toContain(sup.status())
  const c = await notes()
  expect(c.notes.some((n) => /supprimé/.test(n)), JSON.stringify(c.notes)).toBe(true)
})

// ════════════════════════════════════════════════════════════════════════════════════════════════
// ACRM60 — GROUPE A (identité, cadence, opposition, placement) — blocs à coller À LA FIN de
// `frontend/e2e/acceptation/acrm.spec.js`.
//
// À FAIRE AUSSI DANS LE SPEC (deux retouches d'en-tête, rien d'autre) :
//   1. remplacer `import { API_DJANGO } from '../helpers.js'` par
//      `import { API_DJANGO, textePdf, telephoneMobileUnique, lireJson, listeDe } from '../helpers.js'`
//   2. ajouter à la liste `couvre` de `groupe('ACRM', [...])` :
//      'ACRM12', 'ACRM15', 'ACRM17', 'ACRM20', 'ACRM22', 'ACRM32', 'ACRM35', 'ACRM37', 'ACRM38', 'ACRM46', 'ACRM55'
//
// Réutilise du spec : etape, py, PRELUDE, api, monter, T, API_DJANGO, expect.
// Comptes : acc60_dir (Directeur, responsable des leads d'essai) ; `page.request` = demo_admin (config).
// Toute donnée créée porte « ACC60 » + une marque unique ; nettoyage en finally (leads, devis archivés,
// règle d'automatisation, modèle de message, barreau de cadence rétabli).
// ════════════════════════════════════════════════════════════════════════════════════════════════

const marqueG = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const platG = (t) => String(t).replace(/[\s\u00a0\u202f]/g, '').toLowerCase()
const jourIsoG = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)

/** Crée des leads d'essai par le shell (chaque définition : { champs, stage (CLÉ de STAGES.py), age_jours, maj }).
 *  Les touches/lignes d'étape posées automatiquement à la création sont retirées : le test pose son propre état. */
async function creerLeadsG(m, defs) {
  return py(`${PRELUDE}
from apps.crm import stages
from apps.crm.models import RelanceEtape, LeadActivity
defs = json.loads(${JSON.stringify(JSON.stringify(defs))})
ids = []
for d in defs:
    champs = dict(d.get('champs', {}))
    if d.get('stage'):
        champs['stage'] = getattr(stages, d['stage'])
    l = Lead.objects.create(company_id=1, owner_id=${m.ids.acc60_dir}, **champs)
    maj = dict(d.get('maj', {}))
    if d.get('age_jours'):
        maj['date_creation'] = timezone.now() - datetime.timedelta(days=d['age_jours'])
    if maj:
        Lead.objects.filter(pk=l.pk).update(**maj)
    RelanceEtape.objects.filter(lead_id=l.pk).delete()
    LeadActivity.objects.filter(lead_id=l.pk, field='stage').delete()
    ids.append(l.pk)
sortie(ids)`)
}

/** Nettoyage : suppression, sinon archivage si une référence (devis…) retient le lead. */
async function retirerLeadsG(ids) {
  if (!ids.length) return
  await py(`${PRELUDE}
for pk in ${JSON.stringify(ids)}:
    try:
        Lead.objects.filter(pk=pk).delete()
    except Exception:
        Lead.objects.filter(pk=pk).update(is_archived=True)
sortie('ok')`)
}

const touchesG = (leadId) => py(`${PRELUDE}
from apps.crm.models import RelanceEtape
sortie([dict(id=e.id, cadence=e.cadence, ordre=e.ordre, canal=e.canal, statut=e.statut, due_date=str(e.due_date))
        for e in RelanceEtape.objects.filter(lead_id=${leadId}).order_by('cadence', 'ordre', 'id')])`)

const etatLeadG = (leadId) => py(`${PRELUDE}
from apps.crm import stages
l = Lead.objects.get(pk=${leadId})
sortie(dict(stage=l.stage, contacte=(l.stage == stages.CONTACTED), tags=str(l.tags or ''),
            relance=str(l.relance_date) if l.relance_date else None))`)

// ── P1.2 — deux leads de la même personne (casse/espaces) → UN client (ACRM38) ─────────────
// Geste réel : « créer le devis » depuis chaque lead (POST /ventes/devis/ par demo_admin). Le shell ne sert qu'à poser
// les deux leads avec un e-mail BRUT différent par la casse et l'espace final (le formulaire les nettoierait).
// CLAUSE CLIENT : le PDF /proposal de chaque devis porte le nom du client rattaché.
etape('P1.2', ['ACRM38'], async ({ page }) => {
  const m = await monter()
  const marque = marqueG()
  const nom = `ACC60Dup${marque}`
  const emailNet = `acc60dup${marque}@x.ma`
  const admin = page.request
  const [l1, l2] = await creerLeadsG(m, [
    { stage: 'NEW', champs: { nom, telephone: telephoneMobileUnique(), ville: 'Casablanca', type_installation: 'residentiel', facture_hiver: 800 },
      maj: { email: `ACC60Dup${marque}@X.ma ` } },
    { stage: 'NEW', champs: { nom, telephone: telephoneMobileUnique(), ville: 'Casablanca', type_installation: 'residentiel', facture_hiver: 800 },
      maj: { email: emailNet } },
  ])
  const devisIds = []
  try {
    // Panier « rond » LIGNES_B (onduleur + panneaux + pose) : le moteur /proposal refuse (409, CONTENU) un devis
    // sans composition solaire — une ligne quelconque ne rend pas de proposition.
    const lignesPanier = []
    for (const [i, l] of LIGNES_B.entries()) {
      const p = await lireJson(await admin.post(`${API_DJANGO}/stock/produits/`, { ...T, data: { nom: `ACC60 ${l.d} ${marque}-${i}`, prix_vente: l.pu, ...(l.marque ? { marque: l.marque } : {}) } }), `produit ${l.d}`)
      lignesPanier.push({ produit: p.id, designation: l.d, quantite: l.q, prix_unitaire: l.pu, remise: '0.00', taux_tva: l.tva, type_ligne: 'produit', ordre: i })
    }
    for (const lead of [l1, l2]) {
      const d = await lireJson(await admin.post(`${API_DJANGO}/ventes/devis/`, { ...T, data: { lead, taux_tva: '20.00', mode_installation: 'residentiel' } }), `devis du lead ${lead}`)
      devisIds.push(d.id)
      const lignes = await admin.post(`${API_DJANGO}/ventes/devis/${d.id}/replace-lines/`, { ...T, data: { lignes: lignesPanier } })
      expect(lignes.status(), await lignes.text()).toBe(200)
    }
    // Relecture en base : un seul client, e-mail normalisé, les deux leads et les deux devis y sont rattachés.
    const rel = await py(`${PRELUDE}
from apps.ventes.models import Devis
devis = list(Devis.objects.filter(pk__in=${JSON.stringify(devisIds)}).values_list('id', 'client_id'))
clients = list(Client.objects.filter(company_id=1, email__iexact=${JSON.stringify(emailNet)}).values_list('id', 'email', 'nom'))
leads = list(Lead.objects.filter(pk__in=${JSON.stringify([l1, l2])}).values_list('id', 'client_id'))
sortie(dict(devis=devis, clients=clients, leads=leads))`)
    const clientsDevis = new Set(rel.devis.map((x) => x[1]))
    expect(clientsDevis.size, `un seul client pour les deux devis : ${JSON.stringify(rel)}`).toBe(1)
    expect([...clientsDevis][0], 'client rattaché non nul').not.toBeNull()
    expect(rel.clients, 'un seul client à cet e-mail (casse/espaces ignorés)').toHaveLength(1)
    expect(rel.clients[0][1], 'e-mail du client normalisé (minuscules, sans espace)').toBe(emailNet)
    expect(new Set(rel.leads.map((x) => x[1])).size, 'les deux leads pointent le même client').toBe(1)
    // L'API de lecture du devis dit la même chose que la base.
    for (const id of devisIds) {
      const lu = await lireJson(await admin.get(`${API_DJANGO}/ventes/devis/${id}/`, T), `devis ${id} relu`)
      expect(Number(lu.client?.id ?? lu.client), `devis ${id} : client de l'API = client en base`).toBe([...clientsDevis][0])
    }
    // CLAUSE CLIENT : le PDF /proposal de chaque devis (le seul PDF client) porte le nom du client rattaché.
    for (const id of devisIds) {
      const pdf = await admin.get(`${API_DJANGO}/ventes/devis/${id}/proposal/`, T)
      expect(pdf.status(), `PDF /proposal du devis ${id} : ${pdf.status() === 200 ? '' : (await pdf.text()).slice(0, 300)}`).toBe(200)
      expect(pdf.headers()['content-type'] || '').toContain('application/pdf')
      expect(platG(await textePdf(await pdf.body())), `le PDF du devis ${id} nomme le client`).toContain(platG(nom))
    }
  } finally {
    for (const id of devisIds) await admin.post(`${API_DJANGO}/ventes/devis/${id}/archiver/`, T).catch(() => undefined)
    await retirerLeadsG([l1, l2])
  }
})

// ── P1.2b — WhatsApp entrant d'un numéro connu seulement en `whatsapp` → aucun lead brouillon (ACRM32) ──
// Aucune route d'entrée jouable sans signature fournisseur (les webhooks WhatsApp BSP/Cloud exigent leurs clés,
// absentes du .env local ; le seul appelant de production du service, `compta.capturer_message_whatsapp`, est
// coquillé) : le rejeu appelle donc le SERVICE réel `resolve_or_create_lead_from_whatsapp` par le shell.
etape('P1.2b', ['ACRM32'], async () => {
  const m = await monter()
  const marque = marqueG()
  const chiffres = String(Date.now()).slice(-8)
  const [lead] = await creerLeadsG(m, [
    { stage: 'CONTACTED', champs: { nom: `ACC60 WhatsApp seul ${marque}`, telephone: '', whatsapp: `06${chiffres}` } },
  ])
  try {
    const sortieShell = await py(`${PRELUDE}
from apps.crm import leads_doublons, leads_intake
from authentication.models import Company
co = Company.objects.get(pk=1)
tel = '+2126${chiffres}'
avant = Lead.objects.filter(company_id=1).count()
trouves = [x.pk for x in leads_doublons.find_duplicates_by_contact(co, phone=tel)]
res = leads_intake.resolve_or_create_lead_from_whatsapp(co, tel, nom='ACC60 Client WhatsApp')
apres = Lead.objects.filter(company_id=1).count()
cle = Lead.objects.get(pk=${lead}).whatsapp_normalise
sortie(dict(avant=avant, apres=apres, trouves=trouves, resolu=res.pk, cle=cle))`)
    expect(sortieShell.trouves, 'find_duplicates_by_contact retrouve le lead par son WhatsApp').toEqual([lead])
    expect(sortieShell.resolu, 'le message entrant est rattaché au lead existant').toBe(lead)
    expect(sortieShell.apres, 'aucun lead brouillon créé').toBe(sortieShell.avant)
    expect(sortieShell.cle, 'clé normalisée du WhatsApp persistée (sans le 0 initial)').toBe(`6${chiffres}`)
    // Relecture indépendante en base : toujours un seul lead à ce numéro.
    const n = await py(`${PRELUDE}
sortie(Lead.objects.filter(company_id=1, whatsapp_normalise='6${chiffres}').count())`)
    expect(n).toBe(1)
  } finally {
    await retirerLeadsG([lead])
  }
})

// ── P2.1 — cadence : barreau désactivé, double clic, « Fait » WhatsApp (ACRM12, ACRM35, ACRM55, ACRM22) ──
// Gestes réels par l'API (acc60_dir) : « Relancer la cadence » = POST relance/initialiser ; « Fait » = POST
// relance-etapes/<id>/fait/ ; réglage du barreau = PATCH Paramètres → cadence-relance. Le shell ne sert qu'aux
// relectures (+ la tentative de doublon direct en base pour ACRM55). Les pannes injectées d'ACRM12(b)/ACRM22 sont
// couvertes par leurs tests unitaires et ne sont PAS rejouées ici (non jouables honnêtement en direct).
etape('P2.1', ['ACRM12', 'ACRM35', 'ACRM55', 'ACRM22'], async ({ testInfo }) => {
  const m = await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const marque = marqueG()
  const initialiser = (id) => dir.post(`${API_DJANGO}/crm/leads/${id}/relance/initialiser/`, { ...T, data: { cadence: 'contact' } })
  const [leadA, leadB, leadC] = await creerLeadsG(m, [
    { stage: 'CONTACTED', champs: { nom: `ACC60 Barreau ${marque}`, telephone: telephoneMobileUnique() } },
    { stage: 'CONTACTED', champs: { nom: `ACC60 DoubleClic ${marque}`, telephone: telephoneMobileUnique() } },
    { stage: 'CONTACTED', champs: { nom: `ACC60 Fait WhatsApp ${marque}`, telephone: telephoneMobileUnique() } },
  ])
  let barreau = null
  try {
    // (a) ACRM12 — le barreau de la touche ouverte est désactivé, puis « Fait » : le lead reste Contacté, une suite existe.
    const rA = await initialiser(leadA)
    expect(rA.status(), await rA.text()).toBe(200)
    const ouvertesA = (await touchesG(leadA)).filter((t) => t.statut === 'a_faire' && t.cadence === 'contact')
    expect(ouvertesA.length, 'au moins une touche contact ouverte après le lancement').toBeGreaterThanOrEqual(1)
    const premiere = ouvertesA.sort((x, y) => x.ordre - y.ordre)[0]
    const barreaux = listeDe(await lireJson(await dir.get(`${API_DJANGO}/parametres/cadence-relance/?cadence=contact`, T), 'barreaux contact'))
    barreau = barreaux.find((b) => b.ordre === premiere.ordre)
    expect(barreau, `barreau de la touche ${premiere.ordre} dans Paramètres`).toBeTruthy()
    expect(barreau.actif, 'le barreau est actif avant le test').toBe(true)
    const avantA = await etatLeadG(leadA)
    const off = await dir.patch(`${API_DJANGO}/parametres/cadence-relance/${barreau.id}/`, { ...T, data: { actif: false } })
    expect(off.status(), await off.text()).toBe(200)
    const faitA = await dir.post(`${API_DJANGO}/crm/relance-etapes/${premiere.id}/fait/`, {
      ...T, data: premiere.canal === 'appel' ? { outcome: 'pas_de_reponse' } : {},
    })
    expect(faitA.status(), await faitA.text()).toBe(200)
    const apresA = await etatLeadG(leadA)
    expect(apresA.stage, 'étape du lead inchangée (pas de Froid)').toBe(avantA.stage)
    expect(apresA.contacte, 'toujours Contacté').toBe(true)
    expect(apresA.tags, 'aucune étiquette « Injoignable … appels »').not.toContain('Injoignable')
    const touchesApresA = await touchesG(leadA)
    const suite = touchesApresA.filter((t) => t.statut === 'a_faire' && t.cadence === 'contact' && t.ordre > premiere.ordre)
    expect(suite.length, `une touche suivante ouverte (barreau actif suivant) : ${JSON.stringify(touchesApresA)}`).toBeGreaterThanOrEqual(1)
    expect(touchesApresA.find((t) => t.id === premiere.id).statut, 'la touche cliquée est « faite »').toBe('fait')
    // Rétablissement immédiat du réglage, puis relecture.
    const on = await dir.patch(`${API_DJANGO}/parametres/cadence-relance/${barreau.id}/`, { ...T, data: { actif: true } })
    expect(on.status()).toBe(200)
    barreau = null
    expect(await py(`${PRELUDE}
from apps.parametres.models_relance import CadenceRelanceEtape
sortie(CadenceRelanceEtape.objects.filter(company_id=1, cadence='contact', actif=False).count())`), 'aucun barreau contact resté désactivé').toBe(0)

    // (b) ACRM35 + ACRM55 — double clic « Relancer la cadence » : deux requêtes SIMULTANÉES, une seule série.
    const [r1, r2] = await Promise.all([initialiser(leadB), initialiser(leadB)])
    expect(r1.status() < 500 && r2.status() < 500, `statuts ${r1.status()} / ${r2.status()}`).toBe(true)
    const groupes = await py(`${PRELUDE}
from django.db.models import Count
from apps.crm.models import RelanceEtape
rows = RelanceEtape.objects.filter(lead_id=${leadB}, statut='a_faire').values('cadence', 'ordre').annotate(n=Count('id'))
sortie([dict(cadence=r['cadence'], ordre=r['ordre'], n=r['n']) for r in rows])`)
    expect(groupes.find((g) => g.cadence === 'contact' && g.ordre === 1)?.n, `une seule touche (contact, 1) ouverte : ${JSON.stringify(groupes)}`).toBe(1)
    expect(groupes.every((g) => g.n === 1), `aucun doublon ouvert par (cadence, ordre) : ${JSON.stringify(groupes)}`).toBe(true)
    // ACRM55 : la base elle-même refuse une seconde touche À FAIRE identique (contrainte partielle).
    const direct = await py(`${PRELUDE}
from django.db import IntegrityError, transaction
from apps.crm.models import RelanceEtape
ex = RelanceEtape.objects.filter(lead_id=${leadB}, cadence='contact', ordre=1, statut='a_faire').first()
resultat = 'refuse'
try:
    with transaction.atomic():
        RelanceEtape.objects.create(company_id=1, lead_id=${leadB}, cadence='contact', ordre=1, canal=ex.canal,
                                    libelle='ACC60 doublon', due_at=ex.due_at, due_date=ex.due_date, statut='a_faire',
                                    cle=ex.cle, devis_id=ex.devis_id)
    resultat = 'ACCEPTE'
except IntegrityError:
    resultat = 'refuse'
n = RelanceEtape.objects.filter(lead_id=${leadB}, cadence='contact', ordre=1, statut='a_faire').count()
sortie(dict(resultat=resultat, ouvertes=n))`)
    expect(direct, 'contrainte d\'unicité des touches ouvertes (ACRM55)').toEqual({ resultat: 'refuse', ouvertes: 1 })

    // (c) ACRM22 — « Fait » sur une touche WhatsApp : touche suivante posée, UNE ligne de chatter.
    const rC = await initialiser(leadC)
    expect(rC.status(), await rC.text()).toBe(200)
    const ouvertesC = (await touchesG(leadC)).filter((t) => t.statut === 'a_faire' && t.cadence === 'contact').sort((x, y) => x.ordre - y.ordre)
    const wa = ouvertesC.find((t) => t.canal === 'whatsapp')
    if (!wa) throw new Error('NON JOUABLE : aucune touche WhatsApp ouverte en tête de la cadence « contact » de la société démo')
    const chatter = () => py(`${PRELUDE}
from apps.crm.models import LeadActivity
sortie(dict(total=LeadActivity.objects.filter(lead_id=${leadC}).count(),
            faites=LeadActivity.objects.filter(lead_id=${leadC}, body__contains='marquée faite').count()))`)
    const avantC = await chatter()
    const faitC = await dir.post(`${API_DJANGO}/crm/relance-etapes/${wa.id}/fait/`, { ...T, data: {} })
    expect(faitC.status(), await faitC.text()).toBe(200)
    const apresC = await touchesG(leadC)
    expect(apresC.find((t) => t.id === wa.id).statut, 'la touche WhatsApp est « faite »').toBe('fait')
    expect(apresC.some((t) => t.statut === 'a_faire' && t.cadence === 'contact' && t.ordre > wa.ordre), `touche suivante posée : ${JSON.stringify(apresC)}`).toBe(true)
    const apresChatter = await chatter()
    expect(apresChatter.faites - avantC.faites, `exactement une ligne « marquée faite » (total ${avantC.total} → ${apresChatter.total})`).toBe(1)
  } finally {
    if (barreau) await dir.patch(`${API_DJANGO}/parametres/cadence-relance/${barreau.id}/`, { ...T, data: { actif: true } }).catch(() => undefined)
    await retirerLeadsG([leadA, leadB, leadC])
  }
})

// ── P2.2 — opposition : file WhatsApp en masse (ACRM15), règle e-mail (ACRM17), vieux lead (ACRM37) ─────
// (a) Gestes réels : POST /crm/message-templates/ (demo_admin) puis POST /crm/leads/bulk/ {prepare_whatsapp} (acc60_dir).
// (b) Règle créée par POST /automation/rules/ (demo_admin) ; le passage d'étape est joué par le shell sous backend e-mail
//     `locmem` avec l'horloge posée un jour ouvré à 10 h (Casablanca) — la garde d'opposition précède la fenêtre d'envoi,
//     l'horloge ne sert qu'au lead TÉMOIN non opposé (preuve que la règle fonctionne). Relecture par GET /automation/runs/.
// (c) Démarrage de la cadence d'un lead à relance_date 2020-01-01 (POST relance/initialiser) puis lecture de la file.
etape('P2.2', ['ACRM15', 'ACRM17', 'ACRM37'], async ({ page, testInfo }) => {
  const m = await monter()
  const admin = page.request
  const dir = await api(testInfo, 'acc60_dir')
  const marque = marqueG()
  const aCreer = [
    // a, b, c : file WhatsApp
    { stage: 'CONTACTED', champs: { nom: `ACC60 Oppose ${marque}`, prenom: 'Aa', telephone: telephoneMobileUnique(), ne_plus_contacter: true } },
    { stage: 'CONTACTED', champs: { nom: `ACC60 Perdu ${marque}`, prenom: 'Bb', telephone: telephoneMobileUnique(), perdu: true, is_archived: true } },
    { stage: 'CONTACTED', champs: { nom: `ACC60 Normal ${marque}`, prenom: 'Cc', telephone: telephoneMobileUnique() } },
    // règle e-mail : un opposé, un témoin
    { stage: 'CONTACTED', champs: { nom: `ACC60 RegleOppose ${marque}`, telephone: telephoneMobileUnique(), email: `acc60opp${marque}@example.com`, ne_plus_contacter: true } },
    { stage: 'CONTACTED', champs: { nom: `ACC60 RegleTemoin ${marque}`, telephone: telephoneMobileUnique(), email: `acc60tem${marque}@example.com` } },
    // vieux lead à rappel passé
    { stage: 'CONTACTED', champs: { nom: `ACC60 VieuxLead ${marque}`, telephone: telephoneMobileUnique() }, age_jours: 90, maj: { relance_date: '2020-01-01' } },
  ]
  const [lA, lB, lC, lOpp, lTem, lVieux] = await creerLeadsG(m, aCreer)
  let modele = null
  let regle = null
  try {
    // ── (a) ACRM15 ─────────────────────────────────────────────────────────────────────────
    const crM = await admin.post(`${API_DJANGO}/crm/message-templates/`, {
      ...T, data: { nom: `ACC60 RDV ${marque}`, langue: 'fr', corps: 'Bonjour {prenom}. Réservez votre visite : {lien_rdv}' },
    })
    expect(crM.status(), await crM.text()).toBe(201)
    modele = (await crM.json()).id
    const bulk = await dir.post(`${API_DJANGO}/crm/leads/bulk/`, { ...T, data: { action: 'prepare_whatsapp', ids: [lA, lB, lC], template_id: modele } })
    expect(bulk.status(), await bulk.text()).toBe(200)
    const corps = await bulk.json()
    expect(corps.queue.map((q) => q.lead_id), 'la file ne contient que le lead normal').toEqual([lC])
    const motifs = Object.fromEntries(corps.skipped.map((s) => [s.id, s.reason]))
    expect(motifs[lA], 'le lead opposé est nommé dans skipped').toBe('ne plus contacter')
    expect(motifs[lB], 'le lead perdu/archivé est nommé dans skipped').toBe('perdu/archivé')
    const texte = decodeURIComponent(corps.queue[0].wa_url.split('text=').pop())
    expect(texte).toContain('Bonjour Cc')
    expect(texte.trimEnd().endsWith(':'), `aucune phrase à blanc : « ${texte} »`).toBe(false)
    if (texte.includes('Réservez votre visite')) expect(texte).toMatch(/Réservez votre visite : \S+/)
    // CLAUSE PERSISTANCE : aucun lien de réservation créé pour les exclus.
    expect(await py(`${PRELUDE}
from apps.crm.models import BookingLink
sortie(BookingLink.objects.filter(lead_id__in=[${lA}, ${lB}]).count())`), 'aucun BookingLink pour le lead opposé ni le perdu').toBe(0)

    // ── (b) ACRM17 ─────────────────────────────────────────────────────────────────────────
    const FU = await py(`${PRELUDE}
from apps.crm import stages
sortie(stages.FOLLOW_UP)`)
    const crR = await admin.post(`${API_DJANGO}/automation/rules/`, {
      ...T, data: { nom: `ACC60 règle e-mail ${marque}`, enabled: true, trigger_type: 'lead_stage_change', trigger_config: { stage: FU },
                    action_type: 'send_email', action_config: { body: 'Bonjour ACC60' } },
    })
    expect(crR.status(), await crR.text()).toBe(201)
    regle = (await crR.json()).id
    const jeu = await py(`${PRELUDE}
from unittest import mock
from django.core import mail
from django.test import override_settings
from apps.automation.models import AutomationRun
from apps.notifications.selectors import fenetre_notifications
from apps.crm import horaires, stages
from authentication.models import Company
co = Company.objects.get(pk=1)
jour = timezone.localtime(timezone.now(), horaires.CASABLANCA).date()
faux = None
for i in range(1, 21):
    d = jour + datetime.timedelta(days=i)
    cand = datetime.datetime(d.year, d.month, d.day, 10, 0, tzinfo=horaires.CASABLANCA)
    if d.weekday() < 5 and fenetre_notifications(co, cand).ouverte:
        faux = cand
        break
if faux is None:
    raise Exception('aucun jour ouvré à fenêtre ouverte trouvé')
with mock.patch('django.utils.timezone.now', return_value=faux), \\
        override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
    mail.outbox = []
    opp = Lead.objects.get(pk=${lOpp}); opp.stage = stages.FOLLOW_UP; opp.save()
    apres_opp = [x.to for x in mail.outbox]
    tem = Lead.objects.get(pk=${lTem}); tem.stage = stages.FOLLOW_UP; tem.save()
    apres_tem = [x.to for x in mail.outbox]
runs = {r['target_id']: [r['status'], r['message']] for r in AutomationRun.objects.filter(rule_id=${regle}).values('target_id', 'status', 'message')}
sortie(dict(apres_opp=apres_opp, apres_tem=apres_tem, runs=runs, fenetre=str(faux)))`)
    expect(jeu.apres_opp, 'aucun e-mail envoyé au lead opposé').toEqual([])
    expect(jeu.runs[lOpp]?.[0], `exécution « ignorée » pour l'opposé : ${JSON.stringify(jeu.runs)}`).toBe('skipped')
    expect(jeu.runs[lOpp]?.[1], 'motif français de refus').toContain('Contact refusé')
    expect(jeu.apres_tem, `le lead témoin non opposé reçoit l'e-mail (${jeu.fenetre}) : ${JSON.stringify(jeu.runs[lTem])}`).toEqual([[`acc60tem${marque}@example.com`]])
    expect(jeu.runs[lTem]?.[0], 'exécution du témoin réussie').toBe('success')
    // Historique de la règle servi par l'API (ce que l'écran lit).
    const histo = listeDe(await lireJson(await admin.get(`${API_DJANGO}/automation/runs/?rule=${regle}`, T), 'exécutions de la règle'))
    const parCible = Object.fromEntries(histo.map((r) => [r.target_id, r.status]))
    expect(parCible[lOpp], 'GET /automation/runs/ : opposé = skipped').toBe('skipped')
    expect(parCible[lTem], 'GET /automation/runs/ : témoin = success').toBe('success')
    // Retrait immédiat de la règle (ne plus déclencher sur d'autres leads), puis relecture.
    expect((await admin.delete(`${API_DJANGO}/automation/rules/${regle}/`, T)).status()).toBeLessThan(300)
    regle = null

    // ── (c) ACRM37 ─────────────────────────────────────────────────────────────────────────
    const enRetard = async () => {
      const r = await dir.get(`${API_DJANGO}/crm/leads/relances/?scope=overdue`, T)
      expect(r.status(), await r.text()).toBe(200)
      return (await r.json()).results.map((x) => x.id)
    }
    expect(await enRetard(), 'témoin : avant démarrage, le vieux lead est « en retard »').toContain(lVieux)
    const ini = await dir.post(`${API_DJANGO}/crm/leads/${lVieux}/relance/initialiser/`, { ...T, data: { cadence: 'contact' } })
    expect(ini.status(), await ini.text()).toBe(200)
    const touches = await touchesG(lVieux)
    const premiereOuverte = touches.filter((t) => t.statut === 'a_faire').sort((x, y) => (x.due_date < y.due_date ? -1 : x.due_date > y.due_date ? 1 : x.ordre - y.ordre))[0]
    expect(premiereOuverte, 'une première touche ouverte').toBeTruthy()
    const etat = await etatLeadG(lVieux)
    expect(etat.relance, 'relance_date = échéance de la première touche (file recalée)').toBe(premiereOuverte.due_date)
    expect(await enRetard(), 'le lead n\'est plus « en retard »').not.toContain(lVieux)
    // « Ma file » : la frise du lead montre la même première touche.
    const frise = listeDe(await lireJson(await dir.get(`${API_DJANGO}/crm/relance-etapes/?lead=${lVieux}`, T), 'frise du lead'))
    expect(frise.some((e) => e.statut === 'a_faire' && String(e.due_date) === premiereOuverte.due_date), 'la frise porte la touche à cette date').toBe(true)
  } finally {
    if (regle) await admin.delete(`${API_DJANGO}/automation/rules/${regle}/`, T).catch(() => undefined)
    if (modele) {
      const sup = await admin.delete(`${API_DJANGO}/crm/message-templates/${modele}/`, T).catch(() => null)
      if (!sup || sup.status() >= 300) await admin.patch(`${API_DJANGO}/crm/message-templates/${modele}/`, { ...T, data: { archived: true } }).catch(() => undefined)
    }
    await retirerLeadsG([lA, lB, lC, lOpp, lTem, lVieux])
  }
})

// ── P2.3 — aperçu du placement : rappel manuel compté, touches annulées proposées (ACRM20, ACRM46) ──────
// Aperçu seul (`apply:false`) : jamais d'application (elle déplacerait des dizaines de leads de la démo). Comptes
// comparés en DIFFÉRENTIEL (avant/après la création des deux leads) car la démo porte d'autres candidats. La liste
// `apercu` est tronquée à 20 lignes : la décision par lead est relue par la fonction pure `_decider_placements`.
etape('P2.3', ['ACRM20', 'ACRM46'], async ({ testInfo }) => {
  const m = await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const marque = marqueG()
  const apercu = async () => {
    const r = await dir.post(`${API_DJANGO}/crm/leads/placement-cadences/`, { ...T, data: { apply: false } })
    expect(r.status(), await r.text()).toBe(200)
    return r.json()
  }
  const avant = await apercu()
  expect(avant.apply, 'un aperçu n\'applique rien').toBe(false)
  const [lRappel, lAnnule] = await creerLeadsG(m, [
    { stage: 'CONTACTED', age_jours: 60, champs: { nom: `ACC60 RappelManuel ${marque}`, telephone: telephoneMobileUnique() } },
    { stage: 'QUOTE_SENT', age_jours: 60, champs: { nom: `ACC60 TouchesAnnulees ${marque}`, telephone: telephoneMobileUnique() } },
  ])
  try {
    // Rappel posé comme la commerciale le fait : PATCH du lead (ligne MODIFICATION), dans 20 jours.
    const rappel = jourIsoG(20)
    const patch = await dir.patch(`${API_DJANGO}/crm/leads/${lRappel}/`, { ...T, data: { relance_date: rappel } })
    expect(patch.status(), await patch.text()).toBe(200)
    // Lead aux touches toutes closes : une seule touche, « annulée par le moteur ».
    await py(`${PRELUDE}
from apps.crm.models import RelanceEtape
quand = timezone.now() - datetime.timedelta(days=50)
RelanceEtape.objects.create(company_id=1, lead_id=${lAnnule}, cadence='contact', ordre=1, canal=RelanceEtape.Canal.APPEL,
                            libelle='ACC60 Appel 1', due_at=quand, due_date=quand.date(), statut=RelanceEtape.Statut.ANNULEE)
sortie('ok')`)
    const etatAvant = { rappel: await etatLeadG(lRappel), annule: await etatLeadG(lAnnule), touches: (await touchesG(lRappel)).length + (await touchesG(lAnnule)).length }
    const apres = await apercu()
    expect(apres.total_candidats - avant.total_candidats, 'les deux leads sont candidats').toBe(2)
    expect(apres.ignores.rappel_manuel_a_venir - avant.ignores.rappel_manuel_a_venir, 'ACRM20 : compté « rappel manuel à venir »').toBe(1)
    expect(apres.ignores.deja_en_cadence - avant.ignores.deja_en_cadence, 'ACRM46 : des touches toutes closes ne comptent pas « déjà en cadence »').toBe(0)
    expect(apres.a_placer - avant.a_placer, 'ACRM46 : seul le lead aux touches annulées est proposé').toBe(1)
    // Décision par lead (fonction pure, aucune écriture) : le rappel est écarté, l'annulé est proposé (Devis sans suite).
    const decisions = await py(`${PRELUDE}
from apps.crm.cadence_placement import _decider_placements
from authentication.models import Company
dec, ign, tot = _decider_placements(Company.objects.get(pk=1), timezone.now())
codes = {d['lead'].pk: d['code'] for d in dec}
sortie(dict(rappel=codes.get(${lRappel}), annule=codes.get(${lAnnule})))`)
    expect(decisions.rappel ?? null, 'le lead à rappel manuel n\'est pas proposé').toBeNull()
    expect(decisions.annule, 'le lead aux touches annulées est proposé comme dormant « devis sans suite »').toBe('dormant_devis')
    // CLAUSE PERSISTANCE : l'aperçu n'a rien écrit (étape, tags, relance_date, touches) et le rappel est intact.
    const etatApres = { rappel: await etatLeadG(lRappel), annule: await etatLeadG(lAnnule), touches: (await touchesG(lRappel)).length + (await touchesG(lAnnule)).length }
    expect(etatApres, 'aucune écriture par l\'aperçu').toEqual(etatAvant)
    expect(etatApres.rappel.relance, 'relance_date du rappel manuel conservée').toBe(rappel)
  } finally {
    await retirerLeadsG([lRappel, lAnnule])
  }
})

// ───────────────────────────────────────────────────────────────────────────────────────────
// ACRM60 — GROUPE B (à coller À LA FIN de frontend/e2e/acceptation/acrm.spec.js).
// Réutilise du fichier : etape, py, PRELUDE, api, base, monter, T, API_DJANGO, expect, pwRequest.
// À FAIRE À LA MAIN : ajouter à la liste `couvre` de `groupe('ACRM', [...])` les ids
// 'ACRM21','ACRM42','ACRM11','ACRM41','ACRM14','ACRM19','ACRM59','ACRM10','ACRM27','ACRM34'.
// Toutes les données créées sont nommées « ACC60 … <étiquette Date.now()> » et nettoyées en finally.
// ───────────────────────────────────────────────────────────────────────────────────────────
const TAGB = String(Date.now())
/** Téléphone mobile marocain unique par run (n = 0..9) : +2126 + 8 chiffres. */
const telB = (n) => `+2126${String(Number(TAGB.slice(-7)) * 10 + n).padStart(8, '0')}`
const UA_NAVIGATEUR = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

/** Lit une réponse API : statut attendu sinon erreur parlante (jamais un faux vert). */
async function lireB(r, quoi, attendu = [200, 201]) {
  const txt = await r.text()
  if (!attendu.includes(r.status())) throw new Error(`${quoi} : HTTP ${r.status()} — ${txt.slice(0, 500)}`)
  return txt ? JSON.parse(txt) : null
}
const listeB = (j) => (Array.isArray(j) ? j : (j?.results || []))

// Panier « rond » de atot.spec.js (parcours d'acceptation connu) : TTC = 32 000,00 (15 000 + 11 000 + 6 000).
const LIGNES_B = [
  { d: 'Onduleur hybride Deye 5kW Monophasé', q: '1', pu: '12500.00', tva: '20.00', marque: 'Deye' },
  { d: 'Panneau Canadian Solar 710W', q: '8', pu: '1250.00', tva: '10.00', marque: 'Canadian Solar' },
  { d: 'Installation', q: '1', pu: '5000.00', tva: '20.00' },
]
/** Devis par l'API en Directeur : produits (POST stock/produits/) + POST ventes/devis/atomic/ sur le LEAD ;
 *  puis, au choix, envoi (share-link {envoi:true}) et acceptation (POST accepter/). */
async function devisB(apiDir, leadId, { envoyer = true, accepter = false } = {}) {
  const lignes = []
  for (const [i, l] of LIGNES_B.entries()) {
    const p = await lireB(await apiDir.post(`${API_DJANGO}/stock/produits/`, {
      ...T, data: { nom: `ACC60 ${l.d} ${Date.now()}-${i}`, prix_vente: l.pu, ...(l.marque ? { marque: l.marque } : {}) },
    }), `produit ${l.d}`)
    lignes.push({ produit: p.id, designation: l.d, quantite: l.q, prix_unitaire: l.pu, remise: '0.00', taux_tva: l.tva, type_ligne: 'produit', ordre: i })
  }
  const d = await lireB(await apiDir.post(`${API_DJANGO}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lignes, lead: leadId },
  }), 'devis')
  let token = null
  if (envoyer) token = (await lireB(await apiDir.post(`${API_DJANGO}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')).token
  if (envoyer && accepter) await lireB(await apiDir.post(`${API_DJANGO}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ACC60' } }), 'acceptation')
  const relu = await lireB(await apiDir.get(`${API_DJANGO}/ventes/devis/${d.id}/`, T), 'devis relu')
  return { id: d.id, reference: relu.reference, ttc: Number(relu.total_ttc), token }
}

// ── P5.1d — ACRM21 : consolidation « CA groupe » + export, selon la déclaration de chaque action ──
// Geste réel : un Commercial ouvre la fiche d'un client MÈRE rattaché à SON lead (le panneau appelle
// GET clients/<id>/consolidation/). Shell : création de la mère, d'une filiale (Client.parent) et des leads
// (le Commercial ET le Commercial responsable, pour que le client soit dans la portée de chacun).
etape('P5.1d', ['ACRM21'], async ({ testInfo }) => {
  const m = await monter()
  const tag = `${TAGB}-g`
  const o = await py(`${PRELUDE}
mere = Client.objects.create(company_id=1, nom='ACC60 Mere ${tag}')
fil = Client.objects.create(company_id=1, nom='ACC60 Filiale ${tag}', parent=mere)
l1 = Lead.objects.create(company_id=1, nom='ACC60 Groupe ${tag}', owner_id=${m.ids.acc60_com}, client=mere)
l2 = Lead.objects.create(company_id=1, nom='ACC60 GroupeResp ${tag}', owner_id=${m.ids.acc60_cresp}, client=mere)
sortie(dict(mere=mere.id, fil=fil.id, leads=[l1.id, l2.id]))`)
  try {
    const refus = []
    for (const compte of ['acc60_com', 'acc60_cresp', 'acc60_dir']) {
      const c = await api(testInfo, compte)
      const cons = await c.get(`${API_DJANGO}/crm/clients/${o.mere}/consolidation/`, T)
      refus.push(`${compte} consolidation → ${cons.status()}`)
      expect(cons.status(), `${compte} : consolidation (déclaration IsAnyRole + portée)`).toBe(200)
      const j = await cons.json()
      expect(j.filiales.map((f) => f.id), `${compte} : la filiale figure au « CA groupe »`).toContain(o.fil)
      for (const cle of ['ca_devis_total', 'ca_factures_total', 'nb_devis_total', 'nb_factures_total']) expect(j, `${compte} : clé ${cle}`).toHaveProperty(cle)
      const doc = await c.get(`${API_DJANGO}/crm/clients/${o.mere}/documents/`, T)
      expect(doc.status(), `${compte} : documents inchangé`).toBe(200)
      // data-export : palier IsResponsableOrAdmin + droit crm_export — attendu relu côté serveur, pas supposé.
      const droits = await py(`${PRELUDE}
u = U.objects.get(username='${compte}')
sortie(dict(resp=bool(u.is_responsable), admin=bool(u.is_admin_role), export='crm_export' in (u.role.permissions or [])))`)
      const exp = await c.get(`${API_DJANGO}/crm/clients/${o.mere}/data-export/`, T)
      refus.push(`${compte} data-export → ${exp.status()} (${JSON.stringify(droits)})`)
      const attendu200 = droits.resp && (droits.admin || droits.export)
      expect(exp.status(), `${compte} : data-export selon sa déclaration ${JSON.stringify(droits)}`).toBe(attendu200 ? 200 : 403)
      if (exp.status() === 200) expect(Object.keys(await exp.json())).toEqual(expect.arrayContaining(['identite', 'documents']))
    }
    test.info().annotations.push({ type: 'refus', description: refus.join(' ; ') })
  } finally {
    await py(`${PRELUDE}
Lead.objects.filter(pk__in=${JSON.stringify(o.leads)}).delete()
Client.objects.filter(pk=${o.fil}).delete(); Client.objects.filter(pk=${o.mere}).delete(); sortie('ok')`)
  }
})

// ── P2.5b — ACRM42 : RDV dans 30 min sur un lead SANS responsable → un manager reçoit le rappel ──
// Geste réel : POST crm/appointments/ (Directeur) à +30 min sur un lead sans owner. Shell : le beat
// `send_due_appointment_reminders` est GLOBAL (toute la base) → on n'appelle que la fonction par rendez-vous
// `dispatch_appointment_reminder(appt)` (celle que le beat boucle), puis on relit reminder_sent et les
// Notification des destinataires `lead_notification_recipients` (repli managers). Les lignes sont créées même
// hors fenêtre de messages (`programmee_pour` seulement posé) : on relit donc la ligne, pas la cloche.
// NON REJOUÉ ici : « société sans manager → reminder_sent faux » et la plage iftar (horloge figée) — couverts
// par tests_acrm_rappels_visite.py, pas jouables sans société vide / sans figer l'horloge de la pile.
etape('P2.5b', ['ACRM42'], async ({ testInfo }) => {
  await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const lid = await py(`${PRELUDE}
sortie(Lead.objects.create(company_id=1, nom='ACC60 SansResp ${TAGB}-r', owner=None).id)`)
  let rdv = null
  try {
    const r = await dir.post(`${API_DJANGO}/crm/appointments/`, { ...T, data: { lead: lid, scheduled_at: new Date(Date.now() + 30 * 60_000).toISOString() } })
    rdv = (await lireB(r, 'création du RDV à +30 min')).id
    const rel = await py(`${PRELUDE}
from apps.crm.models import Appointment
from apps.crm.visites_rdv import dispatch_appointment_reminder, APPOINTMENT_REMINDER_MINUTES
from apps.crm.services import lead_notification_recipients
from apps.notifications.models import Notification
a = Appointment.objects.select_related('lead', 'company').get(pk=${rdv})
dest = [u.id for u in lead_notification_recipients(a.lead)]
avant = a.reminder_sent
envoye = dispatch_appointment_reminder(a)
a.refresh_from_db()
motif = '(RDV #${rdv})'
def lignes():
    return list(Notification.objects.filter(event_type='appointment_reminder', body__contains=motif).values_list('recipient_id', 'programmee_pour'))
n1 = lignes()
rejoue = dispatch_appointment_reminder(a)
n2 = lignes()
sortie(dict(dest=dest, fenetre=APPOINTMENT_REMINDER_MINUTES, avant=avant, envoye=envoye, apres=a.reminder_sent, n1=n1, n2=n2, rejoue=rejoue))`)
    if (!rel.dest.length) throw new Error('NON JOUABLE : la société démo n\'a aucun manager (Commercial responsable / Directeur actif) — le repli managers ne peut pas être observé')
    expect(rel.fenetre, 'le RDV à +30 min est dans la fenêtre de rappel du beat').toBeGreaterThanOrEqual(30)
    expect(rel.avant, 'RDV neuf : rappel pas encore envoyé').toBe(false)
    expect(rel.envoye, 'dispatch_appointment_reminder renvoie True').toBe(true)
    expect(rel.apres, 'reminder_sent vrai en base').toBe(true)
    const destinataires = rel.n1.map((x) => x[0])
    for (const d of rel.dest) expect(destinataires, `le manager #${d} a une notification « Rappel visite »`).toContain(d)
    expect(rel.rejoue, 'idempotent').toBe(true)
    expect(rel.n2.length, 'second passage : aucune notification en plus').toBe(rel.n1.length)
    test.info().annotations.push({ type: 'rappel', description: `destinataires=${JSON.stringify(rel.dest)} notifications=${JSON.stringify(rel.n1)}` })
  } finally {
    await py(`${PRELUDE}
from apps.crm.models import Appointment
from apps.notifications.models import Notification
Notification.objects.filter(event_type='appointment_reminder', body__contains='(RDV #${rdv})').delete()
Appointment.objects.filter(lead_id=${lid}).delete(); Lead.objects.filter(pk=${lid}).delete(); sortie('ok')`)
  }
})

// ── P3.1 — ACRM11 : réviser un devis ENVOYÉ puis ouvrir l'ANCIEN lien → aucune touche (lien révoqué, ADEV97) ──
// Geste réel : devis envoyé (share-link), POST devis/<id>/reviser/ (V2), puis le client ouvre le lien V1 :
// la page de proposition poste le beacon public POST ventes/proposal/<jeton>/vu/ (204) — c'est lui qui compte la
// lecture humaine. Trois ouvertures « espacées de 16 min » : l'horloge n'est pas rejouable, on recule
// `last_viewed_at` du lien de 16 min en base entre deux ouvertures (fenêtre REOUVERTURE_FENETRE = 15 min).
// NON REJOUÉ : le moteur `engagement_followup_engine` (beat global) — couvert par test_acrm_signal_version_remplacee.py.
etape('P3.1', ['ACRM11'], async ({ testInfo }) => {
  const m = await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const lid = await py(`${PRELUDE}
sortie(Lead.objects.create(company_id=1, nom='ACC60 Version ${TAGB}-v', owner_id=${m.ids.acc60_com}).id)`)
  const publique = await pwRequest.newContext({ baseURL: base(testInfo), extraHTTPHeaders: { 'User-Agent': UA_NAVIGATEUR } })
  const devisIds = []
  try {
    const v1 = await devisB(dir, lid, { envoyer: true }); devisIds.push(v1.id)
    const rev = await lireB(await dir.post(`${API_DJANGO}/ventes/devis/${v1.id}/reviser/`, T), 'révision de V1')
    const v2id = rev.id; devisIds.push(v2id)
    const v1relu = await lireB(await dir.get(`${API_DJANGO}/ventes/devis/${v1.id}/`, T), 'V1 relue')
    expect(v1relu.is_active, 'V1 remplacée').toBe(false)
    expect(v1relu.statut, 'V1 reste envoyée (règle #4 : statut non touché)').toBe('envoye')
    const tok2 = (await lireB(await dir.post(`${API_DJANGO}/ventes/devis/${v2id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi de V2')).token
    const v2ref = (await lireB(await dir.get(`${API_DJANGO}/ventes/devis/${v2id}/`, T), 'V2 relue')).reference
    const snapshot = () => py(`${PRELUDE}
from apps.crm.models import RelanceEtape
sortie(list(RelanceEtape.objects.filter(lead_id=${lid}).order_by('pk').values_list('pk', 'due_date', 'libelle')))`)
    const avant = await snapshot()
    const ouvrir = async (token, quoi, attendu = 204) => {
      const r = await publique.post(`${API_DJANGO}/ventes/proposal/${token}/vu/`, T)
      expect(r.status(), `beacon « vu » ${quoi}`).toBe(attendu)
    }
    // ADEV97 (L3 lien public, 24/10/2026 — décision postérieure à ACRM11) : le lien d'une version REMPLACÉE
    // est révoqué à la révision ; l'ancien lien ne se lit plus (404 muet). Le résultat écrit d'ACRM11
    // (« aucune touche d'appel » sur l'ancienne version) est donc vérifié sur ce comportement en vigueur ;
    // la note de chatter est celle d'ADEV97 (« Lien public … révoqué automatiquement (remplacé …) »).
    for (let i = 0; i < 3; i++) {
      await ouvrir(v1.token, `V1 ouverture ${i + 1} (lien révoqué)`, 404)
      await py(`${PRELUDE}
import datetime
from apps.ventes.models import ShareLink
ShareLink.objects.filter(token='${v1.token}').update(last_viewed_at=timezone.now() - datetime.timedelta(minutes=16)); sortie('ok')`)
    }
    const rel = await py(`${PRELUDE}
from apps.crm.models import LeadActivity, RelanceEtape
from apps.ventes.models import ShareLink, DevisActivity
l = ShareLink.objects.get(token='${v1.token}')
sortie(dict(
  revoque=str(l.revoque_le), valide=l.is_valid, vues=l.view_count,
  note_revoc=list(DevisActivity.objects.filter(devis_id=${v1.id}, body__icontains='révoqué automatiquement').values_list('body', flat=True)),
  ouvert=list(LeadActivity.objects.filter(lead_id=${lid}, body__icontains='ouvert le devis').values_list('body', flat=True)),
  rouverte=RelanceEtape.objects.filter(lead_id=${lid}, libelle='Proposition rouverte — appeler').count()))`)
    test.info().annotations.push({ type: 'V1', description: JSON.stringify(rel) })
    expect(rel.valide, 'lien V1 fermé à la révision (ADEV97)').toBe(false)
    expect(rel.vues, 'aucune lecture comptée sur le lien V1').toBe(0)
    expect(rel.note_revoc.length, `UNE note de révocation sur V1 : ${JSON.stringify(rel.note_revoc)}`).toBe(1)
    expect(rel.note_revoc[0]).toMatch(/remplacé par une nouvelle version/)
    expect(rel.ouvert, 'aucune ligne « a ouvert / rouvert le devis » sur V1').toEqual([])
    expect(rel.rouverte, 'aucune touche « Proposition rouverte — appeler »').toBe(0)
    expect(await snapshot(), 'touches et échéances inchangées').toEqual(avant)
    // Contre-épreuve V2 (version en vigueur) : son lien répond (204). Sa LECTURE n'est pas comptée sur cette pile :
    // QJEQUIPE4 (`crm/visites.py::requete_marquee_equipe`) classe « équipe » toute requête de la même IP qu'un
    // utilisateur connecté de la société dans les 2 h — ici tout part de 127.0.0.1. Constat noté, pas un défaut.
    await ouvrir(tok2, 'V2 (lien vivant)')
    const v2 = await py(`${PRELUDE}
from apps.ventes.models import ShareLink
l = ShareLink.objects.get(token='${tok2}')
sortie(dict(valide=l.is_valid, vues=l.view_count))`)
    expect(v2.valide, 'le lien V2 reste vivant').toBe(true)
    test.info().annotations.push({ type: 'V2', description: `${v2ref} : lien vivant, vues=${v2.vues} (QJEQUIPE4 : même IP que l'équipe connectée)` })
  } finally {
    await publique.dispose()
    await py(`${PRELUDE}
from apps.ventes.models import Devis
Devis.objects.filter(pk__in=${JSON.stringify(devisIds)}).update(is_active=False)
Lead.objects.filter(pk=${lid}).update(is_archived=True); sortie('ok')`)
  }
})

// ── P3.2 — ACRM41 : réserver par le lien PUBLIC → cloche du responsable + note de chatter ──
// Geste réel : le prospect (non connecté) POST crm/public/booking/<jeton>/reserve/. Shell : création du
// BookingLink (c'est le placeholder {lien_rdv} d'un message qui le fabrique, hors de portée ici). Lead avec
// responsable (acc60_com) puis lead SANS responsable (repli managers). Relecture : Appointment, Notification,
// LeadActivity ; second POST sur le même jeton → 410 sans second RDV.
etape('P3.2', ['ACRM41'], async ({ testInfo }) => {
  const m = await monter()
  const o = await py(`${PRELUDE}
from apps.crm.models import BookingLink
a = Lead.objects.create(company_id=1, nom='ACC60 Reserve ${TAGB}-b', owner_id=${m.ids.acc60_com})
b = Lead.objects.create(company_id=1, nom='ACC60 ReserveSansResp ${TAGB}-b', owner=None)
la = BookingLink.objects.create(company_id=1, lead=a); lb = BookingLink.objects.create(company_id=1, lead=b)
sortie(dict(a=a.id, b=b.id, ta=la.token, tb=lb.token))`)
  const publique = await pwRequest.newContext({ baseURL: base(testInfo), extraHTTPHeaders: { 'User-Agent': UA_NAVIGATEUR } })
  try {
    for (const [cle, lead, token] of [['responsable', o.a, o.ta], ['sans responsable (managers)', o.b, o.tb]]) {
      const quand = new Date(Date.now() + 2 * 864e5).toISOString()
      const r = await publique.post(`${API_DJANGO}/crm/public/booking/${token}/reserve/`, { ...T, data: { scheduled_at: quand } })
      const corps = await lireB(r, `réservation publique (${cle})`, [201])
      const rel = await py(`${PRELUDE}
from apps.crm.models import Appointment, LeadActivity
from apps.crm.services import lead_notification_recipients
from apps.notifications.models import Notification
l = Lead.objects.get(pk=${lead})
dest = [u.id for u in lead_notification_recipients(l)]
sortie(dict(rdv=Appointment.objects.filter(lead_id=${lead}).count(), dest=dest,
  notifs=list(Notification.objects.filter(body__contains='(RDV #${corps.appointment_id})').values_list('recipient_id', 'event_type', 'programmee_pour')),
  notes=list(LeadActivity.objects.filter(lead_id=${lead}, body__startswith='Le client a réservé sa visite le').values_list('body', flat=True))))`)
      expect(rel.rdv, `${cle} : exactement 1 RDV`).toBe(1)
      expect(rel.dest.length, `${cle} : destinataires résolubles`).toBeGreaterThan(0)
      const recus = rel.notifs.map((x) => x[0])
      for (const d of rel.dest) expect(recus, `${cle} : notification pour #${d} (${JSON.stringify(rel.notifs)})`).toContain(d)
      if (cle === 'responsable') expect(recus, 'le responsable du lead est prévenu').toContain(m.ids.acc60_com)
      expect(rel.notes.length, `${cle} : une note lisible au chatter`).toBe(1)
      const encore = await publique.post(`${API_DJANGO}/crm/public/booking/${token}/reserve/`, { ...T, data: { scheduled_at: quand } })
      expect(encore.status(), `${cle} : le lien est consommé (410)`).toBe(410)
      expect((await py(`${PRELUDE}
from apps.crm.models import Appointment
sortie(Appointment.objects.filter(lead_id=${lead}).count())`)), `${cle} : toujours 1 RDV en base`).toBe(1)
    }
  } finally {
    await publique.dispose()
    await py(`${PRELUDE}
from apps.crm.models import Appointment
from apps.notifications.models import Notification
for pk in (${o.a}, ${o.b}):
    for a in Appointment.objects.filter(lead_id=pk):
        Notification.objects.filter(body__contains='(RDV #%d)' % a.id).delete()
    Appointment.objects.filter(lead_id=pk).delete()
Lead.objects.filter(pk__in=[${o.a}, ${o.b}]).delete(); sortie('ok')`)
  }
})

// ── P3.3 — ACRM14 : rejeu d'un payload Meta après correction manuelle → la correction est gardée ──
// Geste réel : 1re passe = le service du webhook/pull (`crm.services.create_lead_from_meta_lead_ads`, aucun appel
// réseau, payload de forme Graph API) ; la commerciale corrige par PATCH crm/leads/<id>/ (priorité « normale »,
// WhatsApp vidé) ; 2e passe identique = rejeu webhook / pull adsengine/tasks.py. Shell : les deux passes (le
// webhook Meta signé n'est pas atteignable sans secret). Relecture en base : valeurs humaines, aucune écriture.
etape('P3.3', ['ACRM14'], async ({ testInfo }) => {
  await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const tel = telB(3)
  const Q_INSTALL = 'où_souhaitez-vous_installer_votre_système_solaire_?'
  const Q_FACTURE = "quelle_est_votre_facture_moyenne_d'électricité_par_mois_?"
  const Q_QUAND = "quand_comptez-vous_commencer_l'installation_?"
  const FD = [
    { name: 'full_name', values: [`ACC60 Meta ${TAGB}`] },
    { name: 'phone_number', values: [tel] },
    { name: 'city', values: ['casablanca'] },
    { name: Q_INSTALL, values: ['sur_ma_villa'] },
    { name: Q_FACTURE, values: ['entre_1000_dh_à_2000_dh'] },
    { name: Q_QUAND, values: ['le_plus_tôt_possible_(ce_mois-ci)'] },
  ]
  const passe = `
from authentication.models import Company
from apps.crm.services import create_lead_from_meta_lead_ads
FD = json.loads(${JSON.stringify(JSON.stringify(FD))})
l = create_lead_from_meta_lead_ads(company=Company.objects.get(pk=1), leadgen_id='ACC60-META-${TAGB}', field_data=FD, form_id='FORM-ACC60')`
  let lid = null
  try {
    const un = await py(`${PRELUDE}${passe}
from apps.crm.models import LeadActivity
sortie(dict(id=l.id, priorite=l.priorite, whatsapp=l.whatsapp, tel=l.telephone,
  champs=list(LeadActivity.objects.filter(lead=l, kind='modification', user__isnull=True).values_list('field', flat=True))))`)
    lid = un.id
    expect(un.priorite, '1re passe : priorité haute').toBe('haute')
    expect(un.whatsapp, '1re passe : WhatsApp = téléphone').toBe(un.tel)
    expect(un.champs, '1re passe : une ligne de chatter par champ enrichi').toContain('whatsapp')
    const p = await dir.patch(`${API_DJANGO}/crm/leads/${lid}/`, { ...T, data: { priorite: 'normale', whatsapp: '' } })
    await lireB(p, 'correction manuelle (PATCH)')
    const lignesAvant = await py(`${PRELUDE}
from apps.crm.models import LeadActivity
sortie(LeadActivity.objects.filter(lead_id=${lid}).count())`)
    const deux = await py(`${PRELUDE}${passe}
from apps.crm.models import LeadActivity
l.refresh_from_db()
sortie(dict(meme=l.id == ${lid}, priorite=l.priorite, whatsapp=l.whatsapp, lignes=LeadActivity.objects.filter(lead_id=${lid}).count()))`)
    expect(deux.meme, 'le rejeu retombe sur le même lead (idempotence leadgen_id)').toBe(true)
    expect(deux.priorite, 'priorité « normale » conservée').toBe('normale')
    expect(deux.whatsapp || '', 'WhatsApp vidé conservé').toBe('')
    expect(deux.lignes, 'aucune écriture : même nombre de lignes de chatter').toBe(lignesAvant)
    const rel = await lireB(await dir.get(`${API_DJANGO}/crm/leads/${lid}/`, T), 'fiche relue')
    expect(rel.priorite).toBe('normale')
    expect(rel.whatsapp || '').toBe('')
  } finally {
    await py(`${PRELUDE}
Lead.objects.filter(external_system='meta_lead_ads', external_id='ACC60-META-${TAGB}').delete(); sortie('ok')`)
  }
})

// ── P1.4 — ACRM19 + ACRM59 : effacement d'un lead du site, puis opposition au registre ──
// (a) Geste réel : demande de droit « effacement » (POST core/dsr-requests/ → prendre-en-charge → traiter),
//     qui exécute les fournisseurs DSR dont `crm.dsr_provider.erase_crm`, puis l'admin des payloads
//     (GET crm/website-lead-payloads/<id>/ et ?all=1). Shell : fabrication du lead + payloads bruts + session de
//     chat (le webhook site exige son secret) et relecture de la session de chat (aucune route de lecture).
// (b) Geste réel : PATCH crm/leads/<id>/ {ne_plus_contacter:true} (même registre que la réponse de touche
//     « ne plus me contacter »), puis décoche. Shell : ligne `whatsapp granted=True` d'intake et lecture de
//     core.ConsentRecord (la dernière ligne par identifiant et finalité).
// NON REJOUÉ : la réponse de touche (RelanceEtape) elle-même — même fonction `tracer_opposition_registre`.
etape('P1.4', ['ACRM19', 'ACRM59'], async ({ testInfo }) => {
  const m = await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const NOM = `ACC60 Kenza ${TAGB}`
  const EMAIL = `acc60-site-${TAGB}@acc60.test`
  const TEL = telB(4)
  const IP = '196.12.34.56'
  const a = await py(`${PRELUDE}
from apps.crm.models import WebsiteLeadPayload, ChatSessionPublique
lead = Lead.objects.create(company_id=1, nom='${NOM}', email='${EMAIL}', telephone='${TEL}')
corps = {'nom': '${NOM}', 'email': '${EMAIL}', 'telephone': '${TEL}'}
e = WebsiteLeadPayload.objects.create(company_id=1, payload=corps, remote_addr='${IP}', processed=False, error='mapping impossible')
t = WebsiteLeadPayload.objects.create(company_id=1, payload=corps, remote_addr='${IP}', processed=True, lead=lead)
c = ChatSessionPublique.objects.create(company_id=1, lead=lead, transcript=[{'auteur': 'visiteur', 'texte': 'Je suis ${NOM}, ${TEL}', 'date': '2026-10-01T10:00:00'}])
sortie(dict(lead=lead.id, erreur=e.id, traite=t.id, chat=c.id))`)
  const b = await py(`${PRELUDE}
from apps.crm.leads_consentement import enregistrer_consentement_lead
l = Lead.objects.create(company_id=1, nom='ACC60 Opposant ${TAGB}', owner_id=${m.ids.acc60_com}, email='acc60-opp-${TAGB}@acc60.test', telephone='${telB(5)}')
enregistrer_consentement_lead(l, purpose='whatsapp', granted=True, source='formulaire site web', occurred_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc))
sortie(dict(id=l.id, email=l.email, tel=l.telephone))`)
  let dsrId = null
  try {
    // (a) effacement par la demande de droit
    const dsr = await lireB(await dir.post(`${API_DJANGO}/core/dsr-requests/`, { ...T, data: { subject_identifier: EMAIL, kind: 'effacement' } }), 'demande d\'effacement')
    dsrId = dsr.id
    await lireB(await dir.post(`${API_DJANGO}/core/dsr-requests/${dsrId}/prendre-en-charge/`, T), 'prise en charge')
    const traitee = await lireB(await dir.post(`${API_DJANGO}/core/dsr-requests/${dsrId}/traiter/`, T), 'traitement de l\'effacement')
    expect(traitee.statut, 'demande traitée').toBe('traitee')
    const pasDePii = (txt, quoi) => {
      for (const pii of [NOM, EMAIL, TEL, IP, TEL.slice(-9)]) expect(txt, `${quoi} : « ${pii} » absent`).not.toContain(pii)
    }
    for (const id of [a.erreur, a.traite]) {
      const r = await dir.get(`${API_DJANGO}/crm/website-lead-payloads/${id}/`, T)
      pasDePii(await r.text(), `payload #${id} (admin détail, HTTP ${r.status()})`)
      expect(r.status()).toBe(200)
    }
    const liste = await dir.get(`${API_DJANGO}/crm/website-lead-payloads/?all=1`, T)
    expect(liste.status()).toBe(200)
    pasDePii(await liste.text(), 'liste admin des payloads (?all=1)')
    const rel = await py(`${PRELUDE}
from apps.crm.models import WebsiteLeadPayload, ChatSessionPublique
sortie(dict(payloads=[[str(p.payload), p.remote_addr or ''] for p in WebsiteLeadPayload.objects.filter(pk__in=[${a.erreur}, ${a.traite}])],
            transcript=str(ChatSessionPublique.objects.get(pk=${a.chat}).transcript)))`)
    pasDePii(JSON.stringify(rel), 'relecture en base (payloads + transcript)')

    // (b) opposition au registre, sous e-mail ET téléphone
    const finalites = await py(`${PRELUDE}
from apps.crm.leads_consentement import FINALITES_CONTACT
sortie(list(FINALITES_CONTACT))`)
    expect(finalites, 'le registre porte la finalité whatsapp').toContain('whatsapp')
    const dernieres = () => py(`${PRELUDE}
from core.models import ConsentRecord
from apps.crm.leads_consentement import FINALITES_CONTACT
out = {}
for ident in ('${b.email}', '${b.tel}'):
    for fin in FINALITES_CONTACT:
        r = ConsentRecord.objects.filter(company_id=1, subject_identifier=ident, purpose=fin).order_by('-occurred_at', '-pk').first()
        out[ident + '|' + fin] = None if r is None else [r.granted, r.source]
sortie(out)`)
    const patch = async (v) => lireB(await dir.patch(`${API_DJANGO}/crm/leads/${b.id}/`, { ...T, data: { ne_plus_contacter: v } }), `PATCH ne_plus_contacter=${v}`)
    await patch(true)
    const opp = await dernieres()
    for (const [cle, v] of Object.entries(opp)) {
      expect(v, `registre : une ligne pour ${cle}`).not.toBeNull()
      expect(v[0], `registre : dernière ligne REFUSÉE pour ${cle}`).toBe(false)
    }
    expect(Object.keys(opp).length, 'e-mail ET téléphone × chaque finalité').toBe(2 * finalites.length)
    await patch(false)
    const levee = await dernieres()
    for (const [cle, v] of Object.entries(levee)) {
      expect(v[0], `décoche : dernière ligne ACCORDÉE pour ${cle}`).toBe(true)
      expect(v[1], `décoche : la source nomme l'utilisateur (${cle})`).toContain('opposition levée par acc60_dir')
    }
  } finally {
    await py(`${PRELUDE}
from apps.crm.models import WebsiteLeadPayload, ChatSessionPublique
from core.models import ConsentRecord, DataSubjectRequest
ChatSessionPublique.objects.filter(pk=${a.chat}).delete()
WebsiteLeadPayload.objects.filter(pk__in=[${a.erreur}, ${a.traite}]).delete()
Lead.objects.filter(pk__in=[${a.lead}, ${b.id}]).delete()
ConsentRecord.objects.filter(company_id=1, subject_identifier__in=['${b.email}', '${b.tel}']).delete()
DataSubjectRequest.objects.filter(pk=${dsrId ?? 0}, subject_identifier='${EMAIL}').delete(); sortie('ok')`)
  }
})

// ── P4.2 — ACRM10 + ACRM27 : réviser un devis ACCEPTÉ → V2 seule au CA signé, objectif = « Mes équipes » ──
// Geste réel (Directeur) : devis sur un lead du Commercial (canal meta_ads + campagne unique) envoyé puis accepté
// (V1) ; POST devis/<id>/reviser/ ; V2 envoyée puis acceptée ; lectures GET crm/equipes/statistiques/ (carte
// « Mes équipes »), GET crm/leads/roi-sources/ (panneau « ROI par source »), POST crm/objectifs/ (ca_signe, mois
// courant) puis GET crm/objectifs/attainment/. Shell : lead, équipe témoin à UN seul membre (le Commercial) pour
// isoler les chiffres de la démo, et nouveau prix des lignes de la V2 brouillon (×1,5 : l'écran d'édition n'est
// pas rejoué ici). Mesures DIFFÉRENTIELLES pour « Mes équipes » ; campagne unique pour le ROI.
etape('P4.2', ['ACRM10', 'ACRM27'], async ({ testInfo }) => {
  const m = await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const camp = `acc60-roi-${TAGB}`
  const o = await py(`${PRELUDE}
from apps.crm.models import EquipeCommerciale
l = Lead.objects.create(company_id=1, nom='ACC60 CA ${TAGB}', owner_id=${m.ids.acc60_com}, canal='meta_ads', utm_campaign='${camp}')
e = EquipeCommerciale.objects.create(company_id=1, nom='ACC60 EquipeCA ${TAGB}', responsable_id=${m.ids.acc60_dir})
e.membres.set([${m.ids.acc60_com}])
d = datetime.date.today()
sortie(dict(lead=l.id, equipe=e.id, annee=d.year, mois=d.month))`)
  const stats = async () => {
    const j = await lireB(await dir.get(`${API_DJANGO}/crm/equipes/statistiques/`, T), 'Mes équipes')
    return Number(j.equipes.find((x) => x.id === o.equipe).ca_signe_mois)
  }
  const roi = async () => {
    const g = listeB(await lireB(await dir.get(`${API_DJANGO}/crm/leads/roi-sources/`, T), 'ROI par source')).find((x) => x.utm_campaign === camp)
    return g ? Number(g.signed_value_ttc) : 0
  }
  const proche = (a, b, quoi) => expect(Math.abs(a - b), `${quoi} : ${a} vs ${b}`).toBeLessThan(0.01)
  const devisIds = []
  let objCree = null
  try {
    const base0 = await stats()
    const v1 = await devisB(dir, o.lead, { envoyer: true, accepter: true }); devisIds.push(v1.id)
    proche((await stats()) - base0, v1.ttc, 'V1 acceptée : « Mes équipes » (différentiel)')
    proche(await roi(), v1.ttc, 'V1 acceptée : ROI par source')
    const rev = await lireB(await dir.post(`${API_DJANGO}/ventes/devis/${v1.id}/reviser/`, T), 'révision du devis accepté')
    const v2id = rev.id; devisIds.push(v2id)
    await py(`${PRELUDE}
from decimal import Decimal
from django.db.models import F
from apps.ventes.models import LigneDevis
LigneDevis.objects.filter(devis_id=${v2id}).update(prix_unitaire=F('prix_unitaire') * Decimal('1.5')); sortie('ok')`)
    await lireB(await dir.post(`${API_DJANGO}/ventes/devis/${v2id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi de V2')
    await lireB(await dir.post(`${API_DJANGO}/ventes/devis/${v2id}/accepter/`, { ...T, data: { nom: 'Client ACC60' } }), 'acceptation de V2')
    const v2 = Number((await lireB(await dir.get(`${API_DJANGO}/ventes/devis/${v2id}/`, T), 'V2 relue')).total_ttc)
    expect(v2, 'V2 a bien un autre montant que V1').not.toBeCloseTo(v1.ttc, 1)
    const v1relu = await lireB(await dir.get(`${API_DJANGO}/ventes/devis/${v1.id}/`, T), 'V1 relue')
    expect(v1relu.is_active, 'V1 remplacée').toBe(false)
    expect(v1relu.statut, 'V1 reste « accepte » (règle #4)').toBe('accepte')
    const apresEquipe = await stats()
    proche(apresEquipe - base0, v2, 'après révision : « Mes équipes » compte la V2 SEULE (pas V1+V2)')
    proche(await roi(), v2, 'après révision : ROI par source = V2 seule')
    // ACRM27 : objectif ca_signe du mois posé par l'API (réutilise un objectif déjà présent plutôt que de collisionner).
    const exist = await py(`${PRELUDE}
from apps.crm.models import ObjectifCommercial
sortie(list(ObjectifCommercial.objects.filter(company_id=1, owner_id=${m.ids.acc60_com}, metric='ca_signe', period_type='month', period_year=${o.annee}, period_month=${o.mois}).values_list('id', flat=True)))`)
    let objId = exist[0]
    if (!objId) {
      const cree = await lireB(await dir.post(`${API_DJANGO}/crm/objectifs/`, { ...T, data: { owner: m.ids.acc60_com, metric: 'ca_signe', period_type: 'month', period_year: o.annee, period_month: o.mois, cible: '100000' } }), 'objectif ca_signe')
      objId = cree.id; objCree = objId
    }
    const att = listeB(await lireB(await dir.get(`${API_DJANGO}/crm/objectifs/attainment/?year=${o.annee}&metric=ca_signe&owner=${m.ids.acc60_com}`, T), 'atteinte des objectifs')).find((x) => x.id === objId)
    expect(att, 'objectif présent dans l\'atteinte').toBeTruthy()
    proche(Number(att.realise), apresEquipe, 'objectif ca_signe : réalisé = chiffre de « Mes équipes » (équipe à un seul membre)')
    test.info().annotations.push({ type: 'ca', description: `V1=${v1.ttc} V2=${v2} equipe_delta=${apresEquipe - base0} realise=${att.realise} taux=${att.taux}` })
  } finally {
    if (objCree) await dir.delete(`${API_DJANGO}/crm/objectifs/${objCree}/`, T)
    await py(`${PRELUDE}
from apps.ventes.models import Devis
from apps.crm.models import EquipeCommerciale
Devis.objects.filter(pk__in=${JSON.stringify(devisIds)}).update(is_active=False)
Lead.objects.filter(pk=${o.lead}).update(is_archived=True)
EquipeCommerciale.objects.filter(pk=${o.equipe}).delete(); sortie('ok')`)
  }
})

// ── P4.1 — ACRM34 : « Mes équipes » pipeline_pondere = forecast des MÊMES leads ──
// Champs comparés : (1) crm/equipes/statistiques/ → equipes[id].pipeline_pondere (équipe témoin à UN membre,
// leads OUVERTS) ; (2) reporting/pipeline/ → prevision_ponderee (forecast XSAL7 : Σ valeur_forecast × poids, toute la
// société) ; (3) oracle shell Σ `_lead_forecast_value × _lead_win_weight` sur les 3 leads créés. Mesure
// DIFFÉRENTIELLE avant/après l'ajout de A (montant estimé 50 000), B (20 000 + devis envoyé puis refusé), C (devis
// envoyé) : Δ(1) = Δ(2) = (3), tolérance 1 MAD (le poids dépend de l'âge du lead, en jours fractionnaires).
// Écart assumé : /crm/forecast/rollup/ n'est PAS comparé — il agrège des ForecastEntry (autre notion).
etape('P4.1', ['ACRM34'], async ({ testInfo }) => {
  const m = await monter()
  const dir = await api(testInfo, 'acc60_dir')
  const eq = await py(`${PRELUDE}
from apps.crm.models import EquipeCommerciale
e = EquipeCommerciale.objects.create(company_id=1, nom='ACC60 EquipePond ${TAGB}', responsable_id=${m.ids.acc60_dir})
e.membres.set([${m.ids.acc60_com}])
sortie(e.id)`)
  const equipe = async () => Number((await lireB(await dir.get(`${API_DJANGO}/crm/equipes/statistiques/`, T), 'Mes équipes')).equipes.find((x) => x.id === eq).pipeline_pondere)
  const forecast = async () => Number((await lireB(await dir.get(`${API_DJANGO}/reporting/pipeline/`, T), 'pipeline')).prevision_ponderee)
  const devisIds = []
  let leads = []
  try {
    const e0 = await equipe(); const f0 = await forecast()
    const o = await py(`${PRELUDE}
from apps.crm import stages
a = Lead.objects.create(company_id=1, nom='ACC60 PondA ${TAGB}', owner_id=${m.ids.acc60_com}, stage=stages.CONTACTED, montant_estime=50000)
b = Lead.objects.create(company_id=1, nom='ACC60 PondB ${TAGB}', owner_id=${m.ids.acc60_com}, stage=stages.CONTACTED, montant_estime=20000)
c = Lead.objects.create(company_id=1, nom='ACC60 PondC ${TAGB}', owner_id=${m.ids.acc60_com}, stage=stages.CONTACTED)
sortie([a.id, b.id, c.id])`)
    leads = o
    const dB = await devisB(dir, o[1], { envoyer: true }); devisIds.push(dB.id)
    await lireB(await dir.post(`${API_DJANGO}/ventes/devis/${dB.id}/refuser/`, { ...T, data: { motif: 'Concurrent' } }), 'refus du devis de B')
    const dC = await devisB(dir, o[2], { envoyer: true }); devisIds.push(dC.id)
    const e1 = await equipe(); const f1 = await forecast()
    const oracle = await py(`${PRELUDE}
from decimal import Decimal
from apps.reporting.pipeline import _lead_forecast_value, _lead_win_weight
ls = list(Lead.objects.filter(pk__in=${JSON.stringify(o)}).prefetch_related('devis'))
tot = sum((_lead_forecast_value(l) * _lead_win_weight(l) for l in ls), Decimal('0'))
sortie(dict(total=str(tot), valeurs={l.nom: str(_lead_forecast_value(l)) for l in ls}))`)
    const att = Number(oracle.total)
    expect(att, `oracle : le forecast de ces leads est non nul ${JSON.stringify(oracle.valeurs)}`).toBeGreaterThan(0)
    expect(Math.abs((e1 - e0) - att), `Δ Mes équipes (${e1 - e0}) = oracle Σ forecast×poids (${att})`).toBeLessThan(1)
    expect(Math.abs((f1 - f0) - att), `Δ forecast reporting (${f1 - f0}) = oracle (${att})`).toBeLessThan(1)
    expect(Math.abs((e1 - e0) - (f1 - f0)), `Δ Mes équipes = Δ forecast pour les mêmes leads`).toBeLessThan(1)
    test.info().annotations.push({ type: 'pondere', description: `equipe ${e0}→${e1} ; forecast ${f0}→${f1} ; oracle ${att} ${JSON.stringify(oracle.valeurs)}` })
  } finally {
    await py(`${PRELUDE}
from apps.ventes.models import Devis
from apps.crm.models import EquipeCommerciale
Devis.objects.filter(pk__in=${JSON.stringify(devisIds)}).update(is_active=False)
Lead.objects.filter(pk__in=${JSON.stringify(leads)}).update(is_archived=True)
EquipeCommerciale.objects.filter(pk=${eq}).delete(); sortie('ok')`)
  }
})

// ── P6 — ACRM3 : la société 43 en témoin — aucune fuite des objets société 1 ──
// Geste réel : le compte acc60_b (société 43) lit les listes déjà utilisées plus haut et tente le détail / une
// écriture sur des ids de la société 1. Shell : un lead témoin de la société 43 (preuve que le compte lit bien
// SES données, donc que le silence n'est pas un faux vert) et un RDV de la société 1.
etape('P6', ['ACRM3'], async ({ testInfo }) => {
  const m = await monter()
  const b = await api(testInfo, 'acc60_b')
  const dir = await api(testInfo, 'acc60_dir')
  const PROPRE = `ACC60 TemoinB ${TAGB}`
  const o = await py(`${PRELUDE}
from apps.crm.models import Appointment
t = Lead.objects.create(company_id=43, nom='${PROPRE}', owner_id=${m.ids.acc60_b})
a = Appointment.objects.create(company_id=1, lead_id=${m.mien}, scheduled_at=timezone.now() + datetime.timedelta(days=5))
sortie(dict(temoin=t.id, rdv=a.id))`)
  try {
    // Contrôle positif : côté société 1 les objets ACC60 existent bel et bien et sont trouvables.
    const vue1 = await (await dir.get(`${API_DJANGO}/crm/leads/?search=ACC60`, T)).text()
    expect(vue1, 'société 1 : « ACC60 Mien » est visible du Directeur (le témoin n\'est pas vide)').toContain('ACC60 Mien')
    const lectures = [
      ['GET', '/crm/leads/?search=ACC60'], ['GET', '/crm/leads/'], ['GET', '/crm/clients/?search=ACC60'], ['GET', '/crm/clients/'],
      ['GET', '/crm/equipes/statistiques/'], ['POST', '/crm/leads/placement-cadences/', { apply: false }], ['GET', '/crm/appointments/'],
    ]
    const traces = []
    for (const [verbe, chemin, data] of lectures) {
      const r = verbe === 'GET' ? await b.get(`${API_DJANGO}${chemin}`, T) : await b.post(`${API_DJANGO}${chemin}`, { ...T, data })
      const txt = await r.text()
      traces.push(`${verbe} ${chemin} → ${r.status()}`)
      expect(r.status(), `${verbe} ${chemin} ne plante pas`).toBeLessThan(500)
      expect(txt.split(PROPRE).join(''), `${verbe} ${chemin} : aucun objet ACC60 de la société 1`).not.toContain('ACC60')
      expect(txt, `${verbe} ${chemin} : ni le numéro témoin ni le nom du Directeur de la société 1`).not.toContain('661909901')
    }
    // Les listes de base répondent 200 (sinon le silence ne prouve rien) et le lead propre apparaît.
    for (const chemin of ['/crm/leads/', '/crm/clients/']) expect((await b.get(`${API_DJANGO}${chemin}`, T)).status(), `témoin actif : ${chemin}`).toBe(200)
    expect(await (await b.get(`${API_DJANGO}/crm/leads/?search=ACC60`, T)).text(), 'acc60_b lit SES propres données').toContain(PROPRE)
    // Détails société 1 → 404 (jamais 403), et une écriture ne passe pas : relecture du nom en base.
    for (const chemin of [`/crm/leads/${m.mien}/`, `/crm/clients/${m.cli_t}/`, `/crm/appointments/${o.rdv}/`]) {
      const r = await b.get(`${API_DJANGO}${chemin}`, T)
      traces.push(`GET ${chemin} → ${r.status()}`)
      expect(r.status(), `GET ${chemin} d'une autre société`).toBe(404)
    }
    const ecr = await b.patch(`${API_DJANGO}/crm/leads/${m.mien}/`, { ...T, data: { nom: 'ACC60 PIRATE' } })
    traces.push(`PATCH /crm/leads/${m.mien}/ → ${ecr.status()}`)
    expect(ecr.status(), 'PATCH d\'un lead de la société 1').toBe(404)
    expect(await py(`${PRELUDE}
sortie(Lead.objects.get(pk=${m.mien}).nom)`), 'nom du lead société 1 inchangé en base').toBe('ACC60 Mien')
    test.info().annotations.push({ type: 'refus', description: traces.join(' ; ') })
  } finally {
    await py(`${PRELUDE}
from apps.crm.models import Appointment
Appointment.objects.filter(pk=${o.rdv}).delete(); Lead.objects.filter(pk=${o.temoin}).delete(); sortie('ok')`)
  }
})
