// Acceptation en direct — groupe ACHT, troisième lot (run 99392c vague 10) : preuve due d'ACHT138 — les activités de
// l'agenda (`GET reporting/calendar/?types=activite`) bornées à la vue des activités : un Technicien ne voit que les
// siennes, un Commercial jamais l'à-faire PERSONNEL d'autrui, le Directeur tout. Comptes d'essai aux rôles SYSTÈME de
// la société de demo_admin, connectés par la vraie route ; activités posées au shell (marquées) ; écran « Agenda »
// (/calendrier) joué en Technicien puis en Directeur.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, connexionApi, uiLoginJusquAuxApps, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ACHT', ['ACHT138'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 120_000 }
const J = JSON.stringify
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()

const sessions = new Map()
async function session(testInfo, nom, roleNom) {
  if (sessions.has(nom)) return sessions.get(nom)
  const id = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from authentication.role_tiers import tier_for_role_fields
co = U.objects.get(username='demo_admin').company_id
r = Role.objects.filter(company_id=co, nom=${J(roleNom)}).order_by('id').first()
if r is None:
    r = Role.objects.create(company_id=co, nom=${J(roleNom)}, est_systeme=True, permissions=list(dict(CANONICAL_SYSTEM_ROLES)[${J(roleNom)}]))
u = compte(${J(nom)}, role=r.pk, societe=co)
u.role_legacy = tier_for_role_fields(r.nom, r.est_systeme, r.permissions); u.save(update_fields=['role_legacy'])
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  const s = { ctx, nom, id }
  sessions.set(nom, s)
  return s
}
test.afterAll(async () => { for (const s of sessions.values()) await s.ctx.dispose().catch(() => undefined) })

async function agendaEcran(page, testInfo, suivi, nom, { voit, voitPas }) {
  const ctxUi = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block' })
  try {
    const p = suivi.surveiller(await ctxUi.newPage())
    await p.addInitScript(() => {
      try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
      try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
    })
    await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
    for (let passe = 0; passe < 2; passe += 1) { // 2ᵉ passe = persistance : rechargement de l'agenda
      const charge = p.waitForResponse((q) => /\/reporting\/calendar\/?(\?|$)/.test(q.url()), T)
      if (passe === 0) await p.goto('/calendrier')
      else await p.reload()
      expect((await charge).status(), `agenda de ${nom} servi`).toBe(200)
      for (const s of voit) await expect(p.getByText(s, { exact: false }).first(), `${nom} voit « ${s} »`).toBeVisible({ timeout: 60_000 })
      for (const s of voitPas) await expect(p.getByText(s, { exact: false }), `${nom} ne voit pas « ${s} »`).toHaveCount(0)
    }
  } finally {
    await ctxUi.close().catch(() => undefined)
  }
}

etape('P.agenda_activites_bornees', ['ACHT138'], async ({ page, suivi, testInfo }) => {
  const d = await session(testInfo, 'acht138_directeur', 'Directeur')
  const c = await session(testInfo, 'acht138_commercial', 'Commercial')
  const t = await session(testInfo, 'acht138_technicien', 'Technicien')
  const m = marque()
  const resumes = { P: `ACHT138 perso D ${m}`, A: `ACHT138 activite C ${m}`, A_T: `ACHT138 activite T ${m}` }
  const ids = await py(`from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead
from apps.records.models import Activity
co = U.objects.get(username='demo_admin').company
D, C, T = (U.objects.get(pk=i) for i in (${d.id}, ${c.id}, ${t.id}))
lead = Lead.objects.create(company=co, nom='ACC ACHT138 ${m}', owner=C)
ct, jour = ContentType.objects.get_for_model(Lead), timezone.localdate()
P = Activity.objects.create(company=co, summary=${J(resumes.P)}, personnelle=True, created_by=D, assigned_to=D, due_date=jour)
A = Activity.objects.create(company=co, content_type=ct, object_id=lead.pk, summary=${J(resumes.A)}, created_by=C, assigned_to=C, due_date=jour)
AT = Activity.objects.create(company=co, content_type=ct, object_id=lead.pk, summary=${J(resumes.A_T)}, created_by=C, assigned_to=T, due_date=jour)
sortie(dict(P=P.id, A=A.id, A_T=AT.id, lead=lead.id))`)
  try {
    const vus = async (s) => {
      const corps = await lireJson(await s.ctx.get(`${API}/reporting/calendar/?types=activite`, T), `agenda de ${s.nom}`)
      const mes = new Set([ids.P, ids.A, ids.A_T])
      return new Set((corps.events || []).map((e) => e.obj_id ?? e.link_id).filter((x) => mes.has(x)))
    }
    expect([...(await vus(t))].sort(), 'Technicien : {A_T} seulement').toEqual([ids.A_T])
    const vc = await vus(c)
    expect(vc.has(ids.A), 'Commercial : son activité A').toBe(true)
    expect(vc.has(ids.P), 'Commercial : jamais l’à-faire personnel P du Directeur').toBe(false)
    expect([...(await vus(d))].sort((a, b) => a - b), 'Directeur : P, A, A_T').toEqual([ids.P, ids.A, ids.A_T].sort((a, b) => a - b))
    // Écran « Agenda » en Technicien : aucune activité d'autrui ; en Directeur : inchangé (les trois).
    await agendaEcran(page, testInfo, suivi, t.nom, { voit: [resumes.A_T], voitPas: [resumes.A, resumes.P] })
    await agendaEcran(page, testInfo, suivi, d.nom, { voit: [resumes.P, resumes.A, resumes.A_T], voitPas: [] })
  } finally {
    await py(`from apps.records.models import Activity
from apps.crm.models import Lead
Activity.objects.filter(pk__in=${J([ids.P, ids.A, ids.A_T])}).delete()
Lead.objects.filter(pk=${ids.lead}).delete()
sortie(1)`).catch(() => null)
  }
}, {
  ecart: {
    base: 'FAIL',
    raison: 'GET /api/django/crm/assignable-users/ → 403 (+ console.error et toast « permission ») au montage de /calendrier '
      + 'pour le Technicien : frontend/src/pages/CalendarPage.jsx l. 80-82 appelle crmApi.getAssignableUsers() sans garde de '
      + 'droit (vue IsResponsableOrAdmin) — jumeau, sur l’agenda, d’ERR-ACHT123-ASSIGNABLE-USERS-403-TECHNICIEN corrigé sur '
      + 'Chantiers ; défaut du shell frontend antérieur, hors ACHT138 (backend reporting/calendar.py, lecture des activités) '
      + '— rejeu runner 13/11 run 43509702846 : corps de l’étape vert, seuls les oracles 2/3 tombent.',
  },
})
