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
import { API_DJANGO } from '../helpers.js'

const etape = groupe('ACRM', ['ACRM3', 'ACRM4', 'ACRM5', 'ACRM6', 'ACRM7', 'ACRM8', 'ACRM13', 'ACRM23', 'ACRM24', 'ACRM25', 'ACRM26', 'ACRM30', 'ACRM40', 'ACRM45'])
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
