// ACVI (suite) — preuves en direct des tâches construites après `acvi.spec.js` : portée, opposition, reprises, gabarits.
// Gestes par l'API réelle ; le shell Django (`_django.js`) ne pose que ce qu'aucun geste ne pose (doublon, touche d'un
// type précis, STOP de la touche) et relit ce que l'API ne sert pas.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, connexionApi, assurerSessionPage, isoDansJours, uniq, PNG_1PX } from '../helpers.js'

const etape = groupe('ACVI', [
  'ACVI2', 'ACVI3', 'ACVI6', 'ACVI8', 'ACVI10', 'ACVI11', 'ACVI13', 'ACVI24', 'ACVI31', 'ACVI36', 'ACVI37', 'ACVI38', 'ACVI40', 'ACVI43',
  'ACVI51', 'ACVI52', 'ACVI53', 'ACVI54', 'ACVI63', 'ACVI76', 'ACVI88', 'ACVI89', 'ACVI97', 'ACVI98',
])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const courriel = () => `${uniq('acvib').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.invalid`
const sessions = new Map()
async function compteSession(testInfo, nom, role, prenom = null) {
  const dej = sessions.get(nom)
  if (dej && Date.now() - dej.quand < 20 * 60_000) return dej
  const id = await py(`u = compte(${JSON.stringify(nom)}, role=${role})
u.first_name = ${JSON.stringify(prenom ?? '')}; u.save(update_fields=['first_name']); sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  const s = { ctx, id, quand: Date.now() }
  sessions.set(nom, s)
  return s
}
const ROLE = { COMMERCIAL_RESP: 3, COMMERCIAL: 4, TERRAIN: 70, ADMIN_RH: 71 }
const nouveauLead = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: courriel(), ...extra },
}), 'lead')
const relu = async (request, id) => lireJson(await request.get(`${API}/crm/leads/${id}/`, T), 'lead relu')
const touches = async (request, lid) => listeDe(await lireJson(await request.get(`${API}/crm/relance-etapes/?lead=${lid}`, T), 'touches'))
const aFaire = (ts, cadence) => ts.filter((t) => t.statut === 'a_faire' && (!cadence || t.cadence === cadence))
const historique = async (request, lid) => listeDe(await lireJson(await request.get(`${API}/crm/leads/${lid}/historique/`, T), 'historique'))
const texteHist = (h) => h.map((a) => a.body || a.message || a.description || '').join(' | ')
const opposer = (leadId) => py(`from apps.crm.models_cadence import RelanceEtape
from apps.crm.cadence_reponses import repondre_ne_plus_contacter
from apps.crm.models import Lead
l = Lead.objects.get(pk=${leadId})
t = RelanceEtape.objects.filter(lead=l, statut='a_faire').order_by('ordre').first()
repondre_ne_plus_contacter(t, U.objects.get(username='demo_admin'))
l.refresh_from_db(); sortie(l.ne_plus_contacter)`)
const dateIso = (j) => isoDansJours(j)

// ── Portée ──────────────────────────────────────────────────────────────────────────────────
etape('PA1.05.visite_hors_portee', ['ACVI2'], async ({ testInfo }) => {
  const m = marque()
  const u = await compteSession(testInfo, 'acvib_terrain', ROLE.TERRAIN)
  const c1 = await compteSession(testInfo, 'acvib_c1', ROLE.COMMERCIAL)
  const c2 = await compteSession(testInfo, 'acvib_c2', ROLE.COMMERCIAL)
  const l1 = await nouveauLead(c1.ctx, `ACVI2 ${m}`)
  const comptes = `from apps.crm.models import LeadActivity
from apps.visites.models import VisiteTerrain
sortie([VisiteTerrain.objects.filter(lead_id=${l1.id}).count(), LeadActivity.objects.filter(lead_id=${l1.id}).count()])`
  const avant = await py(comptes)
  for (const [qui, s] of [['terrain', u], ['C2 soi', c2]]) {
    const r = await s.ctx.post(`${API}/visites/visites/`, { ...T, data: { lead: l1.id } })
    expect(r.status(), qui).toBe(400)
    expect((await r.json()).lead, `${qui} : champ lead nommé`).toEqual(['Lead introuvable.'])
  }
  expect(await py(comptes), '0 visite, 0 activité ajoutée').toEqual(avant)
  // Témoin : le terrain sur SON lead.
  const sien = await py(`from apps.crm.models import Lead
sortie(Lead.objects.create(company_id=1, nom='ACVI2 sien ${m}', telephone=${JSON.stringify(telephoneMobileUnique())}, ville='Rabat', owner_id=${u.id}).id)`)
  const ok = await u.ctx.post(`${API}/visites/visites/`, { ...T, data: { lead: sien } })
  expect(ok.status(), 'terrain sur son lead').toBe(201)
})

etape('PA1.03.lectures_crm_droit', ['ACVI3'], async ({ page, testInfo }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI3 ${m}`)
  const u = await compteSession(testInfo, 'acvib_terrain', ROLE.TERRAIN)
  const r = await compteSession(testInfo, 'acvib_rh', ROLE.ADMIN_RH)
  for (const [qui, s] of [['terrain', u], ['Admin RH', r]]) {
    for (const route of [`relance-etapes/?lead=${l.id}`, 'relance-etapes/?scope=all', 'appointments/', 'points-contact/']) {
      const x = await s.ctx.get(`${API}/crm/${route}`, T)
      expect(x.status(), `${qui} ${route}`).toBe(403)
      expect(await x.text(), `${qui} ${route} : droit nommé`).toContain('droit_manquant')
    }
  }
  expect((await page.request.get(`${API}/crm/relance-etapes/?lead=${l.id}`, T)).status(), 'témoin admin').toBe(200)
})

etape('PA1.06.pieces_hors_portee', ['ACVI6'], async ({ testInfo }) => {
  const m = marque()
  const c1 = await compteSession(testInfo, 'acvib_c1', ROLE.COMMERCIAL)
  const c2 = await compteSession(testInfo, 'acvib_c2', ROLE.COMMERCIAL)
  const r = await compteSession(testInfo, 'acvib_rh', ROLE.ADMIN_RH)
  const l1 = await nouveauLead(c1.ctx, `ACVI6 ${m}`)
  const p = await lireJson(await c1.ctx.post(`${API}/records/attachments/`, {
    ...T, multipart: { model: 'crm.lead', id: String(l1.id), file: { name: 'p.png', mimeType: 'image/png', buffer: PNG_1PX } },
  }), 'pièce de C1')
  const proprio = listeDe(await lireJson(await c1.ctx.get(`${API}/records/attachments/?model=crm.lead&id=${l1.id}`, T), 'liste C1'))
  expect(proprio.map((x) => x.id), 'témoin : C1 voit sa pièce').toContain(p.id)
  const cible = listeDe(await lireJson(await c2.ctx.get(`${API}/records/attachments/?model=crm.lead&id=${l1.id}`, T), 'liste C2'))
  expect(cible, 'C2 : liste vide sur la cible').toEqual([])
  const sans = listeDe(await lireJson(await c2.ctx.get(`${API}/records/attachments/`, T), 'liste C2 sans filtre'))
  expect(sans.map((x) => x.id), 'C2 sans filtre : P absente').not.toContain(p.id)
  expect((await c2.ctx.get(`${API}/records/attachments/${p.id}/download/`, T)).status(), 'C2 download').toBe(404)
  const com = await r.ctx.post(`${API}/records/comments/`, { ...T, data: { model: 'crm.lead', id: l1.id, body: 'intrus' } })
  expect(com.status(), 'Admin RH commentaire').toBe(404)
  expect(await com.text(), 'cible nommée').toContain('Cible introuvable')
})

etape('PA1.07.valideur_borne', ['ACVI8'], async ({ page, testInfo }) => {
  const m = marque()
  const cr = await compteSession(testInfo, 'acvib_cr', ROLE.COMMERCIAL_RESP)
  const c3 = await compteSession(testInfo, 'acvib_c3', ROLE.COMMERCIAL)
  const l3 = await nouveauLead(c3.ctx, `ACVI8 ${m}`)
  const v3 = await lireJson(await c3.ctx.post(`${API}/visites/visites/`, { ...T, data: { lead: l3.id } }), 'V3')
  expect((await cr.ctx.get(`${API}/crm/leads/${l3.id}/`, T)).status(), 'témoin : CR ne voit pas le lead').toBe(404)
  expect((await cr.ctx.get(`${API}/visites/visites/${v3.id}/`, T)).status(), 'CR visite').toBe(404)
  const liste = listeDe(await lireJson(await cr.ctx.get(`${API}/visites/visites/`, T), 'liste CR'))
  expect(liste.map((x) => x.id), 'V3 absente de la liste').not.toContain(v3.id)
  expect((await page.request.get(`${API}/visites/visites/${v3.id}/`, T)).status(), 'portée all : 200').toBe(200)
})

etape('PA1.08.attribution_portee', ['ACVI10'], async ({ page, testInfo }) => {
  const m = marque()
  const c = await compteSession(testInfo, 'acvib_c10', ROLE.COMMERCIAL)
  const d = await compteSession(testInfo, 'acvib_d10', ROLE.COMMERCIAL)
  await nouveauLead(c.ctx, `ACVI10 C ${m}`)
  await nouveauLead(d.ctx, `ACVI10 D ${m}`)
  await nouveauLead(d.ctx, `ACVI10 D2 ${m}`)
  const rep = await lireJson(await c.ctx.get(`${API}/crm/rapports/attribution/`, T), 'rapport C')
  expect((rep.par_commercial || []).length, `C seul dans par_commercial (${JSON.stringify(rep.par_commercial).slice(0, 200)})`).toBeLessThanOrEqual(1)
  expect(JSON.stringify(rep.par_commercial), 'collègue absent').not.toContain('acvib_d10')
  const nC = await py(`from apps.crm.models import Lead
sortie(Lead.objects.filter(company_id=1, owner_id=${c.id}).count())`)
  const totalSource = (rep.par_source || []).reduce((a, x) => a + Number(x.nb_leads ?? 0), 0)
  expect(totalSource, 'par_source ne compte que ses leads').toBeLessThanOrEqual(nC)
  expect(totalSource, 'par_source non vide').toBeGreaterThan(0)
  const adm = await lireJson(await page.request.get(`${API}/crm/rapports/attribution/`, T), 'rapport admin')
  expect((adm.par_commercial || []).length, 'témoin portée all : plusieurs commerciaux').toBeGreaterThan(1)
})

// ── Arrivées ────────────────────────────────────────────────────────────────────────────────
etape('PA1.01.meta_corbeille', ['ACVI11'], async ({ page }) => {
  const leadgen = `acvib${marque()}`
  const tel = telephoneMobileUnique()
  const fd = `fd = [{'name':'full_name','values':['Meta Corbeille']},{'name':'phone_number','values':[${JSON.stringify(tel)}]}]`
  const id = await py(`from apps.crm.leads_meta import create_lead_from_meta_lead_ads as c
${fd}
l = c(company=U.objects.get(username='demo_admin').company, leadgen_id=${JSON.stringify(leadgen)}, field_data=fd)
sortie(l.id)`)
  const del = await page.request.delete(`${API}/crm/leads/${id}/`, T)
  expect(del.status(), 'suppression').toBeLessThan(300)
  const r = await py(`from apps.crm.leads_meta import create_lead_from_meta_lead_ads as c
from apps.crm.models import Lead
from apps.crm.models_cadence import RelanceEtape
from apps.notifications.models import Notification
av = RelanceEtape.objects.filter(lead_id=${id}).count(); n0 = Notification.objects.count()
${fd}
l = c(company=U.objects.get(username='demo_admin').company, leadgen_id=${JSON.stringify(leadgen)}, field_data=fd)
sortie(dict(rendu=l.id, n=Lead.all_objects.filter(external_id=${JSON.stringify(leadgen)}).count(), touches=RelanceEtape.objects.filter(lead_id=${id}).count()-av, notifs=Notification.objects.count()-n0, supprime=Lead.all_objects.get(pk=${id}).is_deleted))`)
  expect(r, 'une seule fiche, rendue telle quelle, 0 touche, 0 notification').toEqual({ rendu: id, n: 1, touches: 0, notifs: 0, supprime: true })
  const restaure = await py(`from apps.crm.models import Lead
l = Lead.all_objects.get(pk=${id}); l.restore(); sortie(Lead.objects.filter(pk=${id}).exists())`)
  expect(restaure, 'restaurable sans heurter uniq_lead_external_ref').toBe(true)
})

const leadProprietaire = (rep) => rep.proprietaire?.id ?? rep.proprietaire_lead_id ?? rep.lead_proprietaire?.id ?? rep.proprietaire_id ?? rep.lead_proprietaire_id

etape('PA1.01.proprietaire_doublon_vivant', ['ACVI13'], async ({ page }) => {
  const m = marque()
  const telA = telephoneMobileUnique()
  const a = await nouveauLead(page.request, `ACVI13 A ${m}`, { telephone: telA })
  await lireJson(await page.request.post(`${API}/crm/leads/${a.id}/archiver/`, { ...T, data: {} }), 'archiver A')
  const loc = await nouveauLead(page.request, `ACVI13 T ${m}`)
  const rep = await lireJson(await page.request.post(`${API}/crm/leads/${loc.id}/locataire/`, { ...T, data: { locataire: true, proprietaire: { nom: `P ${m}`, telephone: telA } } }), 'locataire')
  const pid = leadProprietaire(rep)
  expect(pid, `fiche propriétaire rendue (${JSON.stringify(rep).slice(0, 300)})`).toBeTruthy()
  expect(pid, 'fiche neuve ≠ A').not.toBe(a.id)
  // Cadence v4 (« une touche traitée matérialise la suivante ») : le « 2 touches » du plan précède v4 ; témoin = un lead né de la fiche.
  const temoin13 = await nouveauLead(page.request, `ACVI13 temoin ${m}`)
  expect(aFaire(await touches(page.request, pid), 'contact').length, 'cadence contact posée, comme un lead né de la fiche').toBe(aFaire(await touches(page.request, temoin13.id), 'contact').length)
  expect(aFaire(await touches(page.request, pid), 'contact').length, 'au moins une touche').toBeGreaterThanOrEqual(1)
  expect((await relu(page.request, a.id)).is_archived, 'A inchangé').toBe(true)
  // Froid parqué : rouvert, pas de fiche neuve.
  const telF = telephoneMobileUnique()
  const f = await nouveauLead(page.request, `ACVI13 F ${m}`, { telephone: telF })
  const app = aFaire(await touches(page.request, f.id))[0]
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${app.id}/fait/`, { ...T, data: { outcome: 'non_joint', note: 'rejeu ACVI13' } }), 'appel')
  await lireJson(await page.request.patch(`${API}/crm/leads/${f.id}/`, { ...T, data: { stage: 'COLD', parc_raison: 'budget' } }), 'froid')
  const loc2 = await nouveauLead(page.request, `ACVI13 T2 ${m}`)
  const rep2 = await lireJson(await page.request.post(`${API}/crm/leads/${loc2.id}/locataire/`, { ...T, data: { locataire: true, proprietaire: { nom: `P2 ${m}`, telephone: telF } } }), 'locataire 2')
  expect(leadProprietaire(rep2), 'Froid rouvert, pas de fiche neuve').toBe(f.id)
  expect((await relu(page.request, f.id)).stage, 'plus au Froid').not.toBe('COLD')
})

etape('PA1.03.ticket_cadence', ['ACVI88'], async ({ page }) => {
  const m = marque()
  const ids = await py(`from apps.crm.models import Client
from apps.sav.models import Ticket
a = U.objects.get(username='demo_admin')
def t(cl): return Ticket.objects.create(company_id=1, client=cl, reference='SAV-ACVI88-'+str(cl.id), created_by=a).id
c1 = Client.objects.create(company_id=1, nom='ACVI88 ${m}', prenom='A', telephone=${JSON.stringify(telephoneMobileUnique())}, email='a${m}@example.invalid')
c2 = Client.objects.create(company_id=1, nom='ACVI88 sansnum ${m}', prenom='B', email='b${m}@example.invalid')
sortie([t(c1), t(c2)])`)
  const r1 = await lireJson(await page.request.post(`${API}/sav/tickets/${ids[0]}/creer-lead/`, { ...T, data: {} }), 'lead du ticket')
  const lid = r1.lead?.id ?? r1.lead_id ?? r1.id
  expect((await relu(page.request, lid)).stage, 'lead NEW').toBe('NEW')
  // Cadence v4 : même nombre qu'un lead né de la fiche (voir ACVI13).
  const temoin88 = await nouveauLead(page.request, `ACVI88 temoin ${m}`)
  expect(aFaire(await touches(page.request, lid), 'contact').length, 'cadence contact, comme un lead né de la fiche').toBe(aFaire(await touches(page.request, temoin88.id), 'contact').length)
  expect(aFaire(await touches(page.request, lid), 'contact').length, 'au moins une touche').toBeGreaterThanOrEqual(1)
  const r2 = await lireJson(await page.request.post(`${API}/sav/tickets/${ids[1]}/creer-lead/`, { ...T, data: {} }), 'lead sans numéro')
  const lid2 = r2.lead?.id ?? r2.lead_id ?? r2.id
  expect(aFaire(await touches(page.request, lid2), 'contact').length, '0 touche sans numéro').toBe(0)
  expect(texteHist(await historique(page.request, lid2)), 'refus nommé au chatter').toContain('Cadence de relance non initialisée')
})

// ── Opposition ──────────────────────────────────────────────────────────────────────────────
etape('PA1.04.empreinte_opposition', ['ACVI43'], async ({ page }) => {
  const m = marque()
  const tel = telephoneMobileUnique()
  const a = await nouveauLead(page.request, `ACVI43 A ${m}`, { telephone: tel })
  expect(await opposer(a.id), 'A opposée').toBe(true)
  const b = await nouveauLead(page.request, `ACVI43 B ${m}`, { telephone: tel, email: courriel() })
  expect((await relu(page.request, b.id)).ne_plus_contacter, 'B naît opposée').toBe(true)
  expect((await touches(page.request, b.id)).filter((t) => t.template_cle === 'identite' && t.statut === 'a_faire'), '0 touche identite').toEqual([])
  await lireJson(await page.request.patch(`${API}/crm/leads/${a.id}/`, { ...T, data: { ne_plus_contacter: false } }), 'levée sur A')
  await lireJson(await page.request.patch(`${API}/crm/leads/${b.id}/`, { ...T, data: { ne_plus_contacter: false } }), 'levée sur B')
  const c = await nouveauLead(page.request, `ACVI43 C ${m}`, { telephone: tel, email: courriel() })
  expect((await relu(page.request, c.id)).ne_plus_contacter, 'C naît contactable').toBe(false)
})

etape('PA1.04.levee_reprend', ['ACVI52'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI52 ${m}`)
  await opposer(l.id)
  expect(aFaire(await touches(page.request, l.id)), 'plus rien à faire au STOP').toEqual([])
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { ne_plus_contacter: false } }), 'levée')
  expect(aFaire(await touches(page.request, l.id)).length, '≥ 1 touche à faire').toBeGreaterThanOrEqual(1)
  expect(texteHist(await historique(page.request, l.id)), 'note reprise').toContain('Dossier rouvert (opposition levée) — cadence de reprise posée.')
  const reg = await py(`from core.models import ConsentRecord
from apps.crm.models import Lead
l = Lead.objects.get(pk=${l.id})
c = ConsentRecord.objects.filter(company_id=1, subject_identifier__in=[x for x in (l.email, l.telephone) if x]).order_by('-pk').first()
sortie(c.granted if c else None)`)
  expect(reg, 'registre granted=True').toBe(true)
})

etape('PA1.05.whatsapp_visite_oppose', ['ACVI89'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI89 ${m}`)
  await opposer(l.id)
  const ap = await py(`from apps.crm.models import Appointment
sortie(Appointment.objects.create(company_id=1, lead_id=${l.id}, scheduled_at=timezone.now()+datetime.timedelta(days=2), statut='planifie').id)`)
  const n0 = (await historique(page.request, l.id)).length
  const a = await page.request.get(`${API}/crm/leads/${l.id}/message-visite/?cle=visite_proposition`, T)
  expect(a.status(), 'message-visite').toBe(409)
  const ta = await a.text()
  expect(ta, 'motif nommé (refus_rendu_whatsapp)').toContain('ne plus contacter')
  expect(ta, 'sans lien').not.toContain('wa.me')
  const b = await page.request.post(`${API}/crm/appointments/${ap}/confirmer-whatsapp/`, { ...T, data: {} })
  expect(b.status(), 'confirmer-whatsapp').toBe(409)
  expect(await b.text(), 'motif nommé (refus_rendu_whatsapp)').toContain('ne plus contacter')
  expect((await historique(page.request, l.id)).length, '0 activité').toBe(n0)
})

etape('PA1.08.whatsapp_devis_oppose', ['ACVI98'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI98 ${m}`)
  await opposer(l.id)
  const dv = await py(`from apps.ventes.models import Devis
from apps.crm.services import resolve_client_for_lead
from apps.crm.models import Lead
l = Lead.objects.get(pk=${l.id}); r = resolve_client_for_lead(l)
d = Devis.objects.create(company_id=1, lead=l, client=r[0] if isinstance(r, tuple) else r, reference='ACVI98-${m}', statut='envoye')
sortie(d.id)`)
  const n0 = (await historique(page.request, l.id)).length
  for (const route of ['whatsapp-devis-apercu', 'whatsapp-devis']) {
    const r = await page.request.post(`${API}/crm/leads/${l.id}/${route}/`, { ...T, data: { devis_ids: [dv] } })
    expect(r.status(), route).toBe(409)
    const t = await r.text()
    expect(t, `${route} : motif (MOTIF_CONTACT_REFUSE)`).toContain('ne plus être contactée')
    expect(t, `${route} : sans lien`).not.toContain('wa.me')
  }
  expect((await historique(page.request, l.id)).length, '0 activité').toBe(n0)
  expect(await py(`from apps.ventes.models import Devis
sortie(Devis.objects.get(pk=${dv}).statut)`), 'devis inchangé').toBe('envoye')
})

// ── Cadence ─────────────────────────────────────────────────────────────────────────────────
etape('PA1.05.visite_arrete_contact', ['ACVI37'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI37 ${m}`)
  expect(aFaire(await touches(page.request, l.id), 'contact').length, 'cadence contact démarrée').toBeGreaterThan(0)
  await lireJson(await page.request.post(`${API}/visites/visites/`, { ...T, data: { lead: l.id, date_prevue: dateIso(3) } }), 'visite planifiée')
  const ts = await touches(page.request, l.id)
  expect(aFaire(ts, 'contact'), '0 touche contact à faire').toEqual([])
  expect(aFaire(ts).length, 'confirmation et débrief posés').toBeGreaterThanOrEqual(1)
  expect(aFaire(await touches(page.request, l.id), 'contact'), 'persistance').toEqual([])
})

etape('PA1.08.froid_arrete_filet', ['ACVI38'], async ({ page }) => {
  const m = marque()
  // Un appel réel tracé (aucun parcage à 0 touche), puis le filet seul ouvert : le Given de la tâche.
  const l = await nouveauLead(page.request, `ACVI38 ${m}`)
  const t0 = aFaire(await touches(page.request, l.id))[0]
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t0.id}/fait/`, { ...T, data: { outcome: 'non_joint', note: 'rejeu ACVI38' } }), 'appel')
  const pose = await py(`from apps.crm.models import Lead
from apps.crm.models_cadence import RelanceEtape
from apps.crm.cadence_filet import assurer_prochaine_etape_apres_succes
from apps.crm import stages
a = U.objects.get(username='demo_admin')
RelanceEtape.objects.filter(lead_id=${l.id}, statut='a_faire').update(statut='annulee')
Lead.objects.filter(pk=${l.id}).update(stage=stages.CONTACTED, first_contacted_at=timezone.now())
f = assurer_prochaine_etape_apres_succes(Lead.objects.get(pk=${l.id}), a)
sortie(dict(cadence=f.cadence if f else None))`)
  expect(pose.cadence, 'filet generique posé').toBe('generique')
  expect(aFaire(await touches(page.request, l.id), 'generique').length, 'filet à faire avant').toBeGreaterThan(0)
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { stage: 'COLD', parc_raison: 'budget' } }), 'Froid')
  expect(aFaire(await touches(page.request, l.id)).filter((t) => t.cadence !== 'reveil'), 'seul le réveil peut rester').toEqual([])
})

etape('PA1.04.annuler_touche_archive', ['ACVI40'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI40 ${m}`)
  const t = aFaire(await touches(page.request, l.id))[0]
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t.id}/fait/`, { ...T, data: { outcome: 'non_joint', note: 'rejeu ACVI40' } }), 'fait')
  await lireJson(await page.request.post(`${API}/crm/leads/${l.id}/archiver/`, { ...T, data: {} }), 'archiver')
  const r = await page.request.post(`${API}/crm/relance-etapes/${t.id}/annuler/`, { ...T, data: {} })
  expect(r.status(), 'refus').toBe(409)
  const c = await r.json()
  expect(JSON.stringify(c.lead ?? c), 'nomme lead').toContain('archivé')
  expect((await touches(page.request, l.id)).find((x) => x.id === t.id).statut, 'reste fait').toBe('fait')
})

etape('PA1.08.rdv_annule_portes', ['ACVI24'], async ({ page }) => {
  const m = marque()
  const porte = async (nom, geste) => {
    const l = await nouveauLead(page.request, `ACVI24 ${nom} ${m}`)
    const v = await lireJson(await page.request.post(`${API}/visites/visites/`, { ...T, data: { lead: l.id, date_prevue: dateIso(5) } }), `visite ${nom}`)
    expect((await relu(page.request, l.id)).visite_prevue_le, `${nom} : date posée`).toBeTruthy()
    await geste(l)
    const etat = await py(`from apps.crm.models import Lead
from apps.visites.models import VisiteTerrain
sortie([Lead.all_objects.get(pk=${l.id}).visite_prevue_le, VisiteTerrain.objects.get(pk=${v.id}).statut])`)
    expect(etat[0], `${nom} : date vidée`).toBeNull()
    expect(etat[1], `${nom} : visite annulée`).toBe('annulee')
    expect(texteHist(await historique(page.request, l.id)), `${nom} : note système`).toContain('Rendez-vous de visite')
  }
  await porte('lot-perdu', async (l) => lireJson(await page.request.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'set_perdu', ids: [l.id], motif: 'Prix' } }), 'lot perdu'))
  await porte('lot-archive', async (l) => lireJson(await page.request.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'archive', ids: [l.id] } }), 'lot archive'))
  await porte('archiver', async (l) => lireJson(await page.request.post(`${API}/crm/leads/${l.id}/archiver/`, { ...T, data: {} }), 'archiver'))
})

etape('PA1.02.patch_owner_effets', ['ACVI31', 'ACVI51'], async ({ page, testInfo }) => {
  const m = marque()
  const u2 = await compteSession(testInfo, 'acvib_u2', ROLE.COMMERCIAL, 'Sara')
  const l = await nouveauLead(page.request, `ACVI31 ${m}`)
  await py(`from apps.crm.models import Lead
from apps.crm import stages
Lead.objects.filter(pk=${l.id}).update(stage=stages.CONTACTED, first_contacted_at=timezone.now())
sortie(1)`)
  const n0 = await py(`from apps.notifications.models import Notification
sortie(Notification.objects.filter(recipient_id=${u2.id}).count())`)
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { owner: u2.id } }), 'PATCH owner')
  const pass = aFaire(await touches(page.request, l.id)).filter((x) => (x.libelle || '').toLowerCase().includes('passation') || x.template_cle === 'passation')
  expect(pass.length, '1 touche passation à faire').toBe(1)
  const n1 = await py(`from apps.notifications.models import Notification
sortie(Notification.objects.filter(recipient_id=${u2.id}).count())`)
  expect(n1, 'u2 notifié').toBeGreaterThan(n0)
  // ACVI51 : le gabarit par défaut n'est plus vide (message rendu de la touche, puis les deux clés).
  const msg = await lireJson(await page.request.get(`${API}/crm/relance-etapes/${pass[0].id}/message/`, T), 'message passation')
  expect((msg.message || '').trim(), 'message de passation non vide').not.toBe('')
  expect(msg.message, 'aucun placeholder littéral').not.toContain('{')
  const corps = await py(`from apps.parametres.models_messages import MessageTemplate as M
from authentication.models import Company
co = Company.objects.get(pk=1)
sortie({k: M.get_corps(co, k) for k in ('passation', 'appel_apres_reponse')})`)
  for (const [k, v] of Object.entries(corps)) {
    expect((v || '').trim(), `${k} non vide`).not.toBe('')
    expect(v, `${k} : expéditeur par placeholder`).toMatch(/\{conseiller\}|\{marque\}/)
    expect(v, `${k} : sans ancien_conseiller`).not.toContain('{ancien_conseiller}')
  }
})

etape('PA1.08.restaurer_pose_touche', ['ACVI36'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI36 ${m}`)
  await lireJson(await page.request.post(`${API}/crm/leads/${l.id}/archiver/`, { ...T, data: {} }), 'archiver')
  expect(aFaire(await touches(page.request, l.id)), 'touches annulées à l\'archivage').toEqual([])
  await lireJson(await page.request.post(`${API}/crm/leads/${l.id}/restaurer/`, { ...T, data: {} }), 'restaurer')
  expect((await relu(page.request, l.id)).is_archived, 'plus archivé').toBe(false)
  expect(aFaire(await touches(page.request, l.id)).length, '≥ 1 touche à faire').toBeGreaterThanOrEqual(1)
})

etape('PA1.08.conflit_detail', ['ACVI76'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI76 ${m}`)
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { perdu: true, motif_perte: 'Prix' } }), 'perdu')
  const r = await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { stage: 'CONTACTED' } })
  expect(r.status(), 'refus').toBe(409)
  const c = await r.json()
  expect(c.detail, 'detail = premier message').toBe('Lead perdu — étape non modifiable.')
  expect(c.stage, 'stage inchangé (additif)').toEqual(['Lead perdu — étape non modifiable.'])
  expect(c.error?.code, 'code').toBe('state_conflict')
  expect(c.error?.message, 'message égal').toBe(c.detail)
})

etape('PA1.08.kwh_contredit', ['ACVI97'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI97 ${m}`, { type_installation: 'residentiel', facture_hiver: '300', facture_ete: '300' })
  const p = await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { conso_mensuelle_kwh: 5000 } }), 'PATCH 5000')
  expect(JSON.stringify(p.avertissements?.kwh_factures ?? null), 'avertissement nommé').toContain('Consommation mensuelle (kWh)')
  expect(Number((await relu(page.request, l.id)).conso_mensuelle_kwh), 'valeur tapée gardée').toBe(5000)
  // Fiche complétée par le PATCH de la fiche (les champs requis varient) : seule la contradiction peut encore refuser.
  const manque = await py(`from apps.crm.devis_auto import champs_manquants_detail
from apps.crm.models import Lead
sortie([x['champ'] for x in champs_manquants_detail(Lead.objects.get(pk=${l.id}))])`)
  const corps = { presence_journee: 'oui' }
  for (const c of manque) corps[c] = c.includes('surface') ? 100 : 'plat'
  await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: corps })
  const r = await page.request.post(`${API}/crm/leads/${l.id}/devis-auto/`, { ...T, data: {} })
  expect(r.status(), 'devis-auto refusé').toBe(409)
  expect(await r.text(), 'motif').toContain('kWh déclaré incohérent')
  // Le plan disait « témoin 450 kWh » : au barème, 450 kWh = 737 MAD, soit 2,46 × 300 MAD, au-delà du seuil fondateur de 2× ;
  // la règle reste vraie à 450 et le témoin sous le seuil est 300 kWh (441 MAD, 1,47 ×).
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { conso_mensuelle_kwh: 450 } }), 'PATCH 450')
  expect((await relu(page.request, l.id)).avertissements?.kwh_factures ?? null, '450 kWh : 2,46× reste contredit').not.toBeNull()
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { conso_mensuelle_kwh: 300 } }), 'PATCH 300')
  expect((await relu(page.request, l.id)).avertissements?.kwh_factures ?? null, 'témoin 300 kWh : plus d\'avertissement').toBeNull()
  const pret = await page.request.post(`${API}/crm/leads/${l.id}/devis-auto/`, { ...T, data: {} })
  expect(await pret.text(), 'témoin : devis-auto ne refuse plus sur le kWh').not.toContain('kWh déclaré incohérent')
})

// ── Messages ────────────────────────────────────────────────────────────────────────────────
etape('PA1.gabarits_en_masse', ['ACVI53'], async ({ page, testInfo }) => {
  const m = marque()
  const refus = await page.request.post(`${API}/crm/message-templates/`, { ...T, data: { nom: `ACVI53 mauvais ${m}`, corps: 'Bonjour {inconnu}' } })
  expect(refus.status(), 'placeholder inconnu refusé').toBe(400)
  expect(JSON.stringify(await refus.json()), 'champ corps nommé').toContain('corps')
  expect(await py(`from apps.crm.models import MessageTemplate
sortie(MessageTemplate.objects.filter(nom='ACVI53 mauvais ${m}').count())`), 'gabarit refusé absent').toBe(0)
  const tpl = await lireJson(await page.request.post(`${API}/crm/message-templates/`, { ...T, data: { nom: `ACVI53 ${m}`, corps: 'Bonjour {prenom}, ici {conseiller}.' } }), 'gabarit')
  const u = await compteSession(testInfo, 'acvib_u2', ROLE.COMMERCIAL, 'Sara')
  const l = await nouveauLead(u.ctx, `ACVI53 ${m}`, { prenom: 'Amal' })
  const rep = await lireJson(await page.request.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'prepare_whatsapp', ids: [l.id], template_id: tpl.id } }), 'lot whatsapp')
  const txt = decodeURIComponent(JSON.stringify(rep))
  expect(txt, 'ici Sara').toContain('ici Sara')
  expect(txt, 'aucun placeholder littéral').not.toMatch(/\{(prenom|conseiller)\}/)
})

etape('PA1.touche_sans_login', ['ACVI54'], async ({ page, testInfo }) => {
  const m = marque()
  const u = await compteSession(testInfo, 'acvib_sansprenom', ROLE.COMMERCIAL, '')
  const l = await nouveauLead(u.ctx, `ACVI54 ${m}`)
  const t = await py(`from apps.crm.models_cadence import RelanceEtape
sortie(RelanceEtape.objects.create(company_id=1, lead_id=${l.id}, cadence='contact', ordre=9, due_date=timezone.localdate(), due_at=timezone.now(), canal='whatsapp', template_cle='identite', libelle='Identité').id)`)
  const msg = await lireJson(await page.request.get(`${API}/crm/relance-etapes/${t}/message/`, T), 'message')
  expect(msg.message || '', 'jamais le login').not.toContain('acvib_sansprenom')
  expect(msg.message || '', 'phrase omise').not.toMatch(/je suis\s+de/i)
  expect(msg.placeholders_manquants || [], 'placeholder manquant nommé').toContain('conseiller')
})

etape('PA1.05.reservation_publique', ['ACVI63'], async ({ page, testInfo }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI63 ${m}`)
  // Un lien sert une fois : la 2e réservation passe par un 2e lien du même lead (replanifie, ne crée pas).
  const lien = () => py(`from apps.crm.models import BookingLink
sortie(BookingLink.objects.create(company_id=1, lead_id=${l.id}).token)`)
  const pub = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const reserver = async (j) => {
    const d = new Date(Date.now() + j * 86_400_000); d.setUTCHours(9, 0, 0, 0)
    const r = await pub.post(`${API}/crm/public/booking/${await lien()}/reserve/`, { ...T, data: { scheduled_at: d.toISOString() } })
    expect(r.status(), `réservation J+${j} : ${await r.text()}`).toBeLessThan(300)
    return d.toISOString().slice(0, 10)
  }
  const d1 = await reserver(4)
  const etat = () => py(`from apps.visites.models import VisiteTerrain
from apps.crm.models import Lead
v = list(VisiteTerrain.objects.filter(lead_id=${l.id}).exclude(statut='annulee').values_list('id','statut'))
sortie(dict(v=v, prevue=Lead.objects.get(pk=${l.id}).visite_prevue_le))`)
  const e1 = await etat()
  expect(e1.v.length, '1 visite').toBe(1)
  expect(e1.v[0][1], 'brouillon').toBe('brouillon')
  expect(String(e1.prevue).slice(0, 10), 'visite_prevue_le').toBe(d1)
  const ts = aFaire(await touches(page.request, l.id))
  expect(ts.filter((t) => t.cadence === 'contact'), 'cadence suspendue').toEqual([])
  expect(ts.length, 'touches veille/débrief posées').toBeGreaterThanOrEqual(1)
  const d2 = await reserver(6)
  const e2 = await etat()
  expect(e2.v.length, '2e réservation : la même visite').toBe(1)
  expect(e2.v[0][0], 'même id').toBe(e1.v[0][0])
  expect(String(e2.prevue).slice(0, 10), 'déplacée').toBe(d2)
  await pub.dispose()
})
