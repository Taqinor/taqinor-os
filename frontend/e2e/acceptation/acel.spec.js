// Preuves en direct du groupe ACEL (audit PF11 « tâches planifiées », dossier
// docs/audits/2026-11-11-parcours-PF11.md), jouées sur un runner GitHub (METHODE §C.4 point 7).
// Le runner n'a NI worker Celery NI beat : chaque tâche planifiée est prouvée en appelant la VRAIE fonction de
// tâche (ou le vrai balayage) dans le shell Django de la pile, à une heure simulée quand la clause en dépend, puis
// en relisant la base et, quand la clause nomme un écran, en l'AFFIRMANT à l'écran. Chaque étape vérifie aussi que
// la tâche est INSCRITE (planning `beat_schedule`, file de `CELERY_TASK_ROUTES`, tâche enregistrée).
// Notifications : le report N1 (hors fenêtre de travail) est livré par le VRAI balayage `livrer_notifications_differees`
// à l'heure d'ouverture, jamais contourné. Aucun envoi réel (e-mail au backend console, aucun fournisseur).
// Écartées (pas de worker/beat réel, pas de conteneurs) : ACEL3, ACEL4, ACEL8 — voir le rapport.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import {
  lireJson, telephoneMobileUnique, assurerSessionPage, uiLoginJusquAuxApps, connexionApi, PNG_1PX, contextePortailClient,
} from '../helpers.js'

const etape = groupe('ACEL', ['ACEL11', 'ACEL14', 'ACEL32', 'ACEL39', 'ACEL45', 'ACEL48', 'ACEL61', 'ACEL62', 'ACEL65',
  'ACEL70', 'ACEL73', 'ACEL76', 'ACEL77', 'ACEL78', 'ACEL79'])
fermerDjangoApresTout()
const API = '/api/django'
const DJANGO = process.env.E2E_API_TARGET || 'http://127.0.0.1:8000'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 600_000 })
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
test.beforeEach(async ({ page }) => { await page.addInitScript(INIT); await assurerSessionPage(page) })
const contextesUi = []
const apres = []
test.afterEach(async () => {
  for (const c of contextesUi.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

// ── Outils ──────────────────────────────────────────────────────────────────────────────────────────────────────
/** Inscription au calendrier : entrées du `beat_schedule`, file routée, tâche enregistrée. */
const planning = (nom) => py(`from erp_agentique.celery import app
from django.conf import settings
app.loader.import_default_modules()
entrees = [(k, v) for k, v in app.conf.beat_schedule.items() if v.get('task') == ${J(nom)}]
route = (getattr(settings, 'CELERY_TASK_ROUTES', None) or {}).get(${J(nom)}, {})
sortie(dict(enregistree=${J(nom)} in app.tasks, file=route.get('queue'),
  entrees=[dict(cle=k, schedule=str(v['schedule']), options=v.get('options') or {}) for k, v in entrees]))`)
async function inscrite(nom, motif) {
  const p = await planning(nom)
  console.log(`[ACEL] calendrier ${nom} : ${J(p)}`)
  expect(p.enregistree, `${nom} : tâche enregistrée`).toBe(true)
  expect(p.file, `${nom} : routée sur la file « scheduled »`).toBe('scheduled')
  expect(p.entrees.length, `${nom} : une entrée au planning`).toBe(1)
  if (motif) expect(p.entrees[0].schedule, `${nom} : horaire`).toMatch(motif)
  return p
}
/** Livre (vrai balayage N1, à l'heure d'ouverture) les notifications différées `ids`. */
const LIVRER = `
def livrer(ids):
    from apps.notifications.models import Notification
    from apps.notifications.services import livrer_notifications_differees
    dues = list(Notification.objects.filter(pk__in=ids, programmee_pour__isnull=False).values_list('programmee_pour', flat=True))
    return livrer_notifications_differees(now=max(dues)) if dues else 0
`
/** Résumé des problèmes (jeton de service de la pile) : occurrences par tâche en échec. */
async function echecsConsignes() {
  const ctx = await pwRequest.newContext({ baseURL: DJANGO, extraHTTPHeaders: { Authorization: `Bearer ${process.env.PROBLEMES_RESUME_TOKEN || ''}` } })
  try {
    const r = await lireJson(await ctx.get(`${API}/reporting/problemes/resume/?jours=1`, T), 'résumé des problèmes')
    const occ = {}
    for (const g of r.taches_en_echec || []) occ[g.tache] = (occ[g.tache] || 0) + g.occurrences
    return occ
  } finally {
    await ctx.dispose()
  }
}
/** Sonde HÔTE (`docs/audits/sondes/ACEL/<c>.py`) ; {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'ACEL', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin],
    { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
function sondeRejouee(constat) {
  const s = sondeHote(constat)
  expect(s.ok, `sonde ${constat} exécutée : ${s.err || ''}`).toBe(true)
  console.log(`[ACEL] sonde ${constat} : ${J(s.res).slice(0, 600)}`)
  expect(s.res.observe?.inconclusif, `sonde ${constat} concluante`).toBeUndefined()
  expect(s.res.repro, `sonde ${constat} : repro faux`).toBe(false)
}
/** `manage.py <args>` dans la pile (même préfixe que le shell). */
function manage(args) {
  const [cmd, ...pre] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const r = spawnSync(cmd, [...pre, 'python', 'manage.py', ...args],
    { encoding: 'utf8', timeout: 300_000, maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  return { code: r.status, out: `${r.stdout || ''}`, err: `${r.stderr || ''}`.slice(-1500) }
}
const compteRole = (nom, nomRole) => py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}).pk, societe=${SOC})
sortie(u.id)`)
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), ...(u.viewport ? { viewport: u.viewport } : {}),
  })
  contextesUi.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}
async function cloche(p, titre) {
  await p.getByRole('button', { name: /^Notifications \(/ }).first().click()
  await expect(p.getByText(titre).first(), `cloche : « ${titre} »`).toBeVisible({ timeout: 30_000 })
  await p.keyboard.press('Escape')
}
/** GED : armoire puis chemin de dossiers dans l'arbre. */
async function ouvrirDossierGed(p, cabinet, chemin) {
  await p.goto('/ged')
  const choix = p.getByRole('combobox', { name: 'Choisir le cabinet' })
  await expect(choix, 'sélecteur d\'armoire').toBeVisible({ timeout: 90_000 })
  await choix.click()
  await p.getByRole('option', { name: cabinet, exact: true }).click()
  const arbre = p.getByRole('tree', { name: 'Dossiers' })
  for (const seg of chemin) {
    await arbre.getByRole('button', { name: seg, exact: true }).first().click({ timeout: 30_000 })
  }
}
const ligneGed = (p, nom) => p.locator('tr').filter({ has: p.getByLabel(`Sélectionner ${nom}`, { exact: true }) })

// ═══ PF11.4 — ACEL11 : export de réversibilité, travail de fond et bac à sable tués → balayage 15 min ═══
etape('PF11.4-ACEL11', ['ACEL11'], async ({ page }) => {
  await inscrite('core.balayer_travaux_orphelins', /^<crontab: \*\/15 \* \* \* \*/)
  const m = marque()
  const f = await py(`from datetime import timedelta
from core.export_registry import ExportReversibiliteRun
from core.models import BackgroundJob
from apps.adminops.models import SandboxEnvironment, AdminOpsSettings
a = U.objects.get(username='demo_admin'); co = a.company
n = timezone.now()
actifs = SandboxEnvironment.objects.filter(company=co, statut__in=['en_creation', 'pret']).count()
run = ExportReversibiliteRun.objects.create(company=co, demande_par=a, statut='en_cours')
ExportReversibiliteRun.objects.filter(pk=run.pk).update(updated_at=n - timedelta(minutes=45), created_at=n - timedelta(minutes=45))
vieux = BackgroundJob.objects.create(company=co, user=a, kind='acel11_${m}', statut='running')
recent = BackgroundJob.objects.create(company=co, user=a, kind='acel11_${m}', statut='running')
BackgroundJob.objects.filter(pk=vieux.pk).update(updated_at=n - timedelta(minutes=45))
BackgroundJob.objects.filter(pk=recent.pk).update(updated_at=n - timedelta(minutes=5))
sb = SandboxEnvironment.objects.create(company=co, statut='en_creation', date_expiration=n + timedelta(days=14), cree_par=a)
SandboxEnvironment.objects.filter(pk=sb.pk).update(date_creation=n - timedelta(minutes=45))
sortie(dict(run=run.pk, vieux=vieux.pk, recent=recent.pk, sb=sb.pk, actifs=actifs, autorise=AdminOpsSettings.get_or_default(co).sandbox_autorise,
  runs=ExportReversibiliteRun.objects.filter(company=co).count()))`)
  apres.push(() => py(`from core.export_registry import ExportReversibiliteRun
from core.models import BackgroundJob
from apps.adminops.models import SandboxEnvironment
co = ${SOC}
ExportReversibiliteRun.objects.filter(pk=${f.run}).delete()
BackgroundJob.objects.filter(kind='acel11_${m}').delete()
SandboxEnvironment.objects.filter(company_id=co, date_creation__gte=timezone.now() - datetime.timedelta(hours=2)).delete()
SandboxEnvironment.objects.filter(pk=${f.sb}).delete()
sortie(1)`))
  expect([f.actifs, f.autorise], 'précondition : aucun bac à sable actif, création autorisée').toEqual([0, true])
  const badges = (statut) => page.getByRole('heading', { name: 'Exports précédents' })
    .locator('xpath=following-sibling::ul[1]').getByText(statut, { exact: true })
  // Écran AVANT le balayage : l'export tué est « En cours ».
  await page.goto('/parametres/export-reversibilite')
  await expect(badges('En cours').first(), 'avant : export « En cours »').toBeVisible({ timeout: 60_000 })
  const r = await py(`${LIVRER}
from core.export_registry import ExportReversibiliteRun
from core.models import BackgroundJob
from core.tasks import balayer_travaux_orphelins_task
from apps.notifications.models import Notification
a = U.objects.get(username='demo_admin')
avant = set(Notification.objects.filter(recipient=a).values_list('pk', flat=True))
res = balayer_travaux_orphelins_task()
ids = list(Notification.objects.filter(recipient=a, event_type='travail_de_fond_echoue').exclude(pk__in=avant).values_list('pk', flat=True))
livrees = livrer(ids)
v = BackgroundJob.objects.get(pk=${f.vieux})
sortie(dict(res=res, run=ExportReversibiliteRun.objects.get(pk=${f.run}).statut, vieux=[v.statut, v.message_erreur],
  recent=BackgroundJob.objects.get(pk=${f.recent}).statut, notes=len(ids), livrees=livrees,
  echecs=ExportReversibiliteRun.objects.filter(company=a.company, statut='echec').count(),
  en_cours=ExportReversibiliteRun.objects.filter(company=a.company, statut='en_cours').count()))`)
  console.log(`[ACEL11] ${J(r)}`)
  expect(r.run, 'export de 45 min → échec').toBe('echec')
  expect(r.vieux[0], 'travail de fond de 45 min → failed').toBe('failed')
  expect(r.vieux[1], 'message « interrompu »').toMatch(/interrompu/i)
  expect(r.recent, 'travail de fond de 5 min : toujours running').toBe('running')
  expect(r.notes, 'demandeur prévenu (export + travail de fond)').toBeGreaterThanOrEqual(2)
  // Écran : l'historique montre « Échec » (autant de badges que d'exports en échec en base) ; la cloche du demandeur.
  await page.reload()
  await expect(badges('Échec').first(), 'après : export « Échec »').toBeVisible({ timeout: 60_000 })
  await expect(badges('Échec'), 'badges « Échec » = exports en échec en base').toHaveCount(r.echecs)
  await expect(badges('En cours'), 'badges « En cours » = exports en cours en base').toHaveCount(r.en_cours)
  await cloche(page, 'Un travail de fond a été interrompu')
  // Bac à sable : la création réussit malgré celui resté « en création » 45 min (passé en échec).
  await page.goto('/admin/sandbox')
  await expect(page.getByText('Environnements sandbox').first()).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: 'Créer un environnement de test' }).click()
  await expect(page.locator('[data-sonner-toast]').filter({ hasText: 'Création lancée' }).first(), 'création acceptée').toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Création interrompue (plus de 30 min).').first(), 'ancien : échec nommé').toBeVisible({ timeout: 30_000 })
  await page.reload()
  await expect(page.getByText('Création interrompue (plus de 30 min).').first(), 'après rechargement').toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('En création', { exact: true }).first(), 'nouveau bac à sable « En création »').toBeVisible()
  const sb = await py(`from apps.adminops.models import SandboxEnvironment
sortie(dict(ancien=SandboxEnvironment.objects.get(pk=${f.sb}).statut,
  nouveaux=SandboxEnvironment.objects.filter(company_id=${SOC}, statut='en_creation').exclude(pk=${f.sb}).count()))`)
  expect(sb, 'en base : ancien en échec, un nouveau en création').toEqual({ ancien: 'echec', nouveaux: 1 })
  // Idempotence : un second balayage ne change rien.
  const re = await py(`from core.tasks import balayer_travaux_orphelins_task
from core.models import BackgroundJob
balayer_travaux_orphelins_task()
sortie(BackgroundJob.objects.get(pk=${f.recent}).statut)`)
  expect(re, 'second passage : le travail récent reste running').toBe('running')
})

// ═══ PF11.3 — ACEL14 : compteurs Celery écrits par un processus, lus par /metrics (gunicorn) ═══
etape('PF11.3-ACEL14', ['ACEL14'], async ({ testInfo }) => {
  const m = marque()
  const nom = `acel14_super_${m}`
  await py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom='Administrateur').pk, societe=${SOC})
u.is_superuser = True; u.save(update_fields=['is_superuser'])
sortie(u.pk)`)
  apres.push(() => py(`U.objects.filter(username=${J(nom)}).update(is_active=False, is_superuser=False); sortie(1)`))
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  try {
    await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
    const lire = async () => {
      const r = await ctx.get(`${API}/core/metrics/`, T)
      expect(r.status(), '/metrics (superutilisateur) : 200').toBe(200)
      const t = await r.text()
      const n = (re) => Number((t.match(re) || [])[1] || 0)
      return {
        succes: n(/^taqinor_celery_tasks_total\{status="success"\} (\d+)/m),
        echecs: n(/^taqinor_celery_tasks_total\{status="failure"\} (\d+)/m),
        fileSucces: n(/^taqinor_celery_queue_tasks_total\{queue="default",status="success"\} (\d+)/m),
        fileEchecs: n(/^taqinor_celery_queue_tasks_total\{queue="default",status="failure"\} (\d+)/m),
      }
    }
    const avant = await lire()
    // Un AUTRE processus (le shell Django) exécute une tâche qui lève et deux qui réussissent, par les vrais signaux Celery.
    const x = await py(`from erp_agentique.celery import app
from core import metrics
@app.task(name='acceptation.acel14_leve_${m}')
def leve():
    raise RuntimeError('ACEL14 : tâche d essai qui lève')
@app.task(name='acceptation.acel14_reussit_${m}')
def reussit():
    return 1
etats = [leve.apply().state, reussit.apply().state, reussit.apply().state]
sortie(dict(etats=etats, cache=metrics.task_counters()))`)
    console.log(`[ACEL14] avant=${J(avant)} shell=${J(x)}`)
    expect(x.etats).toEqual(['FAILURE', 'SUCCESS', 'SUCCESS'])
    const apresLu = await lire()
    console.log(`[ACEL14] après=${J(apresLu)}`)
    expect(apresLu.echecs - avant.echecs, '/metrics : +1 échec').toBe(1)
    expect(apresLu.succes - avant.succes, '/metrics : +2 succès').toBe(2)
    expect(apresLu.fileEchecs - avant.fileEchecs, '/metrics par file : +1 échec').toBe(1)
    expect(apresLu.fileSucces - avant.fileSucces, '/metrics par file : +2 succès').toBe(2)
    // Persistance : relu une seconde fois (autre requête gunicorn) ⇒ identique.
    expect(await lire(), 'relu : identique').toEqual(apresLu)
  } finally {
    await ctx.dispose()
  }
})

// ═══ PF11.4 — ACEL32 : job d'import de l'API publique bloqué « en cours » → échec relançable à son curseur ═══
etape('PF11.4-ACEL32', ['ACEL32'], async ({ page }) => {
  await inscrite('publicapi.expirer_jobs_bloques', /^<crontab: \*\/10 \* \* \* \*/)
  const m = marque()
  const cle = await lireJson(await page.request.post(`${API}/publicapi/keys/`, { ...T, data: { label: `ACEL32 ${m}`, scopes: ['leads:write'] } }), 'clé API')
  const pub = await pwRequest.newContext({ baseURL: DJANGO, extraHTTPHeaders: { Authorization: `Api-Key ${cle.key}` } })
  const jobs = []
  try {
    const lignes = (k) => Array.from({ length: 5 }, (_, i) => J({ nom: `ACEL32 ${k}${i} ${m}`, email: `acel32-${k}${i}-${m}@example.invalid` })).join('\n')
    for (const k of ['a', 'b']) {
      const imp = await pub.post('/api/public/v1/imports/', { ...T, multipart: { file: { name: 'leads.jsonl', mimeType: 'application/x-ndjson', buffer: Buffer.from(`${lignes(k)}\n`) }, entite: 'leads', mode: 'upsert', dedup_key: 'email' } })
      expect(imp.status(), `import ${k} : ${(await imp.text()).slice(0, 200)}`).toBe(202)
      jobs.push((await imp.json()).id)
    }
    // Worker tué au milieu (pas de worker sur la pile) : le 1er a traité 2 lignes il y a 11 min, le 2nd progresse encore (1 min).
    await py(`from datetime import timedelta
from apps.publicapi.models import BulkJob
n = timezone.now()
BulkJob.objects.filter(pk=${jobs[0]}).update(statut='en_cours', cursor=2, traites=2, total=5, updated_at=n - timedelta(minutes=11))
BulkJob.objects.filter(pk=${jobs[1]}).update(statut='en_cours', cursor=1, traites=1, total=5, updated_at=n - timedelta(minutes=1))
sortie(1)`)
    const tache = () => py(`from apps.publicapi.tasks import expirer_jobs_bloques
sortie(expirer_jobs_bloques())`)
    expect(await tache(), 'balayage : 1 job expiré').toBeGreaterThanOrEqual(1)
    const g1 = await pub.get(`/api/public/v1/jobs/${jobs[0]}/`, T)
    const j1 = await g1.json()
    expect([g1.status(), j1.statut], 'suivi du job tué : echec').toEqual([200, 'echec'])
    expect(j1.message_erreur, 'message : relancer, reprise à la ligne 3').toBe('Traitement interrompu (arrêt du serveur) — relancez le job, il reprend à la ligne 3')
    expect(j1.termine_le, 'termine_le posé').toBeTruthy()
    const g2 = await pub.get(`/api/public/v1/jobs/${jobs[1]}/`, T)
    expect([g2.status(), (await g2.json()).statut, g2.headers()['retry-after']], 'job actif : en_cours inchangé').toEqual([200, 'en_cours', '3'])
    // Idempotence : rejouer la tâche ne change rien.
    await tache()
    const rel = await pub.post(`/api/public/v1/jobs/${jobs[0]}/relancer/`, T)
    const jr = await rel.json()
    expect([rel.status(), jr.statut, jr.cursor], 'relance : 200, en_file, curseur 2 conservé').toEqual([200, 'en_file', 2])
    const base = await py(`from apps.publicapi.models import BulkJob
sortie([list(BulkJob.objects.filter(pk=p).values_list('statut', 'cursor')[0]) for p in (${jobs[0]}, ${jobs[1]})])`)
    expect(base, 'relu en base').toEqual([['en_file', 2], ['en_cours', 1]])
  } finally {
    await pub.dispose()
    apres.push(async () => {
      await py(`from apps.publicapi.models import BulkJob
BulkJob.objects.filter(pk__in=${J(jobs)}).delete(); sortie(1)`)
      await page.request.delete(`${API}/publicapi/keys/${cle.id}/`, T).catch(() => null)
    })
  }
})

// ═══ PF11.3 — ACEL39 : comptage tournant et vagues balayés société par société, échec consigné ═══
etape('PF11.3-ACEL39', ['ACEL39'], async () => {
  sondeRejouee('C-ACEL-004')
  await inscrite('stock.generer_comptages_tournants', /^<crontab: 15 5 \* \* \*/)
  await inscrite('stock.liberer_vagues_planifiees', /^<crontab: \*\/15 \* \* \* \*/)
  const avant = await echecsConsignes()
  const m = marque()
  const r = await py(`from decimal import Decimal as D
from django.db import transaction
from authentication.models import Company
from apps.stock import selectors_wms, services_wms
from apps.stock.models import InventaireSession, Produit, VaguePicking
from apps.stock.services import assurer_plans_comptage_tournant, configurer_liberation_vague, creer_vague_depuis_besoins
from apps.stock.tasks import generer_comptages_tournants_task, liberer_vagues_planifiees_task
res = {}
with transaction.atomic():
    A = Company.objects.create(nom='ACEL39 A ${m}', slug='acel39-a-${m}')
    B = Company.objects.create(nom='ACEL39 B ${m}', slug='acel39-b-${m}')
    vagues = {}
    for co, k in ((A, 'A'), (B, 'B')):
        u = U.objects.create_user(username='acel39_' + k + '_${m}', password='x', role_legacy='admin', company=co)
        assurer_plans_comptage_tournant(co)
        p = Produit.objects.create(company=co, nom='Vis ' + k, sku='ACEL39-' + k + '-${m}', prix_achat=D('5'), prix_vente=D('9'), quantite_stock=100)
        v = creer_vague_depuis_besoins(company=co, user=u, besoins=[{'produit_id': p.id, 'quantite': 1}])
        configurer_liberation_vague(vague=v, mode='auto_seuil', seuil_lignes=1)
        vagues[k] = v.pk
    reel_classes, reel_lancer = selectors_wms.classes_abc_produits, services_wms.lancer_vague
    def classes(company, **kw):
        if company.id == A.id:
            raise RuntimeError('ACEL39 : classes ABC en panne chez A')
        return reel_classes(company, **kw)
    def lancer(vague):
        if vague.company_id == A.id:
            raise RuntimeError('ACEL39 : lancement en panne chez A')
        return reel_lancer(vague)
    with mock.patch.object(selectors_wms, 'classes_abc_produits', side_effect=classes):
        res['comptage'] = generer_comptages_tournants_task()
        res['rejeu'] = generer_comptages_tournants_task()
    with mock.patch.object(services_wms, 'lancer_vague', side_effect=lancer):
        res['vagues'] = liberer_vagues_planifiees_task()
    res['sessions'] = [InventaireSession.objects.filter(company=A).count(), InventaireSession.objects.filter(company=B).count()]
    res['statuts'] = [VaguePicking.objects.get(pk=vagues['A']).statut, VaguePicking.objects.get(pk=vagues['B']).statut]
    transaction.set_rollback(True)
res['rien_laisse'] = not Company.objects.filter(slug__in=['acel39-a-${m}', 'acel39-b-${m}']).exists()
sortie(res)`)
  console.log(`[ACEL39] ${J(r)}`)
  expect(r.sessions, 'comptage : A 0 session, B 1 session').toEqual([0, 1])
  expect(r.comptage, 'comptage : la tâche rend le total (≥ 1, B compris)').toBeGreaterThanOrEqual(1)
  expect(r.statuts, 'vagues : A brouillon, B lancée').toEqual(['brouillon', 'lancee'])
  expect(r.vagues, 'vagues : la tâche rend le total (≥ 1)').toBeGreaterThanOrEqual(1)
  expect(r.rien_laisse, 'transaction annulée').toBe(true)
  const ap = await echecsConsignes()
  console.log(`[ACEL39] résumé avant=${J(avant)} après=${J(ap)}`)
  expect((ap['stock.generer_comptages_tournants'] || 0) - (avant['stock.generer_comptages_tournants'] || 0), 'résumé des problèmes : comptage consigné (A, deux passages)').toBeGreaterThanOrEqual(1)
  expect((ap['stock.liberer_vagues_planifiees'] || 0) - (avant['stock.liberer_vagues_planifiees'] || 0), 'résumé des problèmes : vagues consignées').toBe(1)
})

// ═══ PF11.3 — ACEL45 : purge GPS et récurrences d'intervention, échecs consignés, sociétés suivantes servies ═══
etape('PF11.3-ACEL45', ['ACEL45'], async () => {
  sondeRejouee('C-ACEL-004')
  await inscrite('installations.purger_positions_gps', /^<crontab: 35 3 \* \* \*/)
  await inscrite('installations.generer_interventions_recurrentes', /^<crontab: 35 5 \* \* \*/)
  const avant = await echecsConsignes()
  const m = marque()
  const r = await py(`from django.db import transaction, DatabaseError
from authentication.models import Company
from apps.crm.models import Client
from apps.installations import gps_tracking_service, services
from apps.installations.models import Installation, Intervention, RecurrenceIntervention
from apps.installations.tasks import generer_interventions_recurrentes_task, purger_positions_gps_task
res = {}
with transaction.atomic():
    insts = {}
    for k in ('A', 'B'):
        co = Company.objects.create(nom='ACEL45 ' + k + ' ${m}', slug='acel45-' + k.lower() + '-${m}')
        cl = Client.objects.create(company=co, nom='Client', prenom='ACEL45', email='acel45-' + k.lower() + '-${m}@example.invalid')
        inst = Installation.objects.create(company=co, reference='CHT-ACEL45-' + k + '-${m}', client=cl)
        RecurrenceIntervention.objects.create(company=co, installation=inst, type_intervention='controle', regle='mensuelle', prochaine_echeance=datetime.date.today())
        insts[k] = (co, inst)
    A = insts['A'][0]
    with mock.patch.object(gps_tracking_service, 'purge_positions_expirees', side_effect=DatabaseError('ACEL45 : purge GPS en panne')):
        res['purge'] = purger_positions_gps_task()
    reel = services.generer_interventions_recurrentes
    def generer(company, *a, **k):
        if company.id == A.id:
            raise RuntimeError('ACEL45 : génération en panne chez A')
        return reel(company, *a, **k)
    with mock.patch.object(services, 'generer_interventions_recurrentes', side_effect=generer):
        res['generees'] = generer_interventions_recurrentes_task()
    res['interventions'] = [Intervention.objects.filter(installation=insts['A'][1]).count(), Intervention.objects.filter(installation=insts['B'][1]).count()]
    transaction.set_rollback(True)
res['rien_laisse'] = not Company.objects.filter(slug__startswith='acel45-').filter(slug__endswith='-${m}').exists()
sortie(res)`)
  console.log(`[ACEL45] ${J(r)}`)
  expect(r.purge, 'purge en panne : la tâche rend 0').toBe(0)
  expect(r.interventions, 'A sans intervention, B son intervention').toEqual([0, 1])
  expect(r.generees, 'la tâche rend le total (≥ 1, B compris)').toBeGreaterThanOrEqual(1)
  expect(r.rien_laisse, 'transaction annulée').toBe(true)
  const ap = await echecsConsignes()
  console.log(`[ACEL45] résumé avant=${J(avant)} après=${J(ap)}`)
  expect((ap['installations.purger_positions_gps'] || 0) - (avant['installations.purger_positions_gps'] || 0), 'résumé : purge GPS consignée').toBe(1)
  expect((ap['installations.generer_interventions_recurrentes'] || 0) - (avant['installations.generer_interventions_recurrentes'] || 0), 'résumé : génération consignée une fois (A)').toBe(1)
})

// ═══ PF11.3 — ACEL48 : balayage SLA du SAV avec le cache des verrous en panne (Redis injoignable) ═══
etape('PF11.3-ACEL48', ['ACEL48'], async () => {
  await inscrite('sav.scan_sla_pre_alerts_and_escalations_quotidien', /^<crontab: \*\/15 \* \* \* \*/)
  const m = marque()
  const r = await py(`from django.db import transaction
from django.core.cache import cache as vrai_cache
from django_redis.cache import RedisCache
from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import Notification
from apps.sav import tasks as sav_tasks
from apps.sav.models import EscaladeSlaNiveau, SavSlaSettings, Ticket
res = {}
# Cache des verrous EN PANNE : vrai client django-redis vers un port fermé, IGNORE_EXCEPTIONS comme la pile.
mort = RedisCache('redis://127.0.0.1:1/1', {'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient', 'IGNORE_EXCEPTIONS': True, 'SOCKET_CONNECT_TIMEOUT': 1, 'SOCKET_TIMEOUT': 1}})
res['add_mort'] = repr(mort.add('acel48-sonde-${m}', 1, 5))
with transaction.atomic():
    co = Company.objects.create(nom='ACEL48 ${m}', slug='acel48-${m}')
    resp = U.objects.create_user(username='acel48_resp_${m}', password='x', role_legacy='normal', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='ACEL48')
    t = Ticket.objects.create(company=co, reference='SAV-ACEL48-${m}', client=cl, statut=Ticket.Statut.EN_COURS, sla_due_at=datetime.date.today())
    palier = EscaladeSlaNiveau.objects.create(company=co, libelle='J+0 responsable', ordre=1, seuil_jours_apres_echeance=0, notifier_utilisateur=resp)
    s = SavSlaSettings.get(co); s.sla_breach_enabled = True; s.save(update_fields=['sla_breach_enabled'])
    notifs = lambda: Notification.objects.filter(recipient=resp).count()
    # Verrou TENU (vrai cache sain) : le balayage saute.
    vrai_cache.add('sav-sla-scan:pre-alerts', 1, 600)
    try:
        res['tenu'] = sav_tasks.scan_sla_pre_alerts_and_escalations_quotidien()
    finally:
        vrai_cache.delete('sav-sla-scan:pre-alerts')
    res['notifs_tenu'] = notifs()
    with mock.patch.object(sav_tasks, 'cache', mort):
        res['panne'] = sav_tasks.scan_sla_pre_alerts_and_escalations_quotidien()
        res['notifs_panne'] = notifs()
        t.refresh_from_db()
        res['paliers'] = list(t.sla_escalade_paliers_notifies or [])
        res['palier'] = palier.pk
        res['second'] = sav_tasks.scan_sla_pre_alerts_and_escalations_quotidien()
    res['notifs_fin'] = notifs()
    transaction.set_rollback(True)
res['rien_laisse'] = not Company.objects.filter(slug='acel48-${m}').exists()
sortie(res)`)
  console.log(`[ACEL48] ${J(r)}`)
  expect(r.add_mort, 'cache en panne : cache.add rend None (panne avalée)').toBe('None')
  expect(r.tenu, 'verrou tenu : skipped').toEqual({ skipped: true })
  expect(r.notifs_tenu, 'verrou tenu : 0 notification').toBe(0)
  expect(r.panne.skipped, 'cache en panne : le balayage tourne').toBeUndefined()
  expect(r.panne.escalations, 'cache en panne : escalade émise').toBeGreaterThanOrEqual(1)
  expect(r.notifs_panne, 'une notification pour le responsable').toBe(1)
  expect(r.paliers, 'palier noté sur le ticket').toContain(r.palier)
  expect(r.notifs_fin, '2e passage : pas de 2e notification').toBe(1)
  expect(r.rien_laisse, 'transaction annulée').toBe(true)
})

// ═══ PF11.2 — ACEL61 : une pièce jointe importée puis purgée n'est jamais réimportée ═══
etape('PF11.2-ACEL61', ['ACEL61'], async () => {
  sondeRejouee('C-ACEL-002')
  await inscrite('ged.migrer_pieces_jointes', /^<crontab: 25 3 \* \* 1/)
  const m = marque()
  const r = await py(`from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from authentication.models import Company
from apps.crm.models import Lead
from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder, PieceJointeImportee
from apps.ged.management.commands.migrate_attachments_to_ged import import_attachments
from apps.ged.tasks import migrer_pieces_jointes_task
from apps.records.models import Attachment
res = {}
k1, k2 = 'attachments/acel61-${m}-P.pdf', 'attachments/acel61-${m}-L.pdf'
with transaction.atomic():
    co = Company.objects.create(nom='ACEL61 ${m}', slug='acel61-${m}')
    admin = U.objects.create_user(username='acel61_${m}', password='x', company=co, role_legacy='admin')
    cab = Cabinet.objects.create(company=co, nom='Cab'); folder = Folder.objects.create(company=co, cabinet=cab, nom='R')
    att = Attachment.objects.create(company=co, object_id=folder.pk, content_type=ContentType.objects.get_for_model(Folder), uploaded_by=admin, file_key=k1, filename='P.pdf', size=1, mime='application/pdf')
    res['premier'] = import_attachments(company=co)
    doc = DocumentVersion.objects.get(file_key=k1).document
    services.mettre_en_corbeille(doc, admin)
    services.purger_definitivement(doc)
    lead = Lead.objects.create(company=co, nom='Corbeille ACEL61')
    Attachment.objects.create(company=co, object_id=lead.pk, content_type=ContentType.objects.get_for_model(Lead), uploaded_by=admin, file_key=k2, filename='L.pdf', size=1, mime='application/pdf')
    lead.soft_delete(admin)
    res['tache'] = migrer_pieces_jointes_task()
    res['import2'] = import_attachments(company=co)
    res['import3'] = import_attachments(company=co)
    res['documents'] = Document.objects.filter(company=co, versions__file_key__in=[k1, k2]).count()
    res['versions'] = DocumentVersion.objects.filter(file_key__in=[k1, k2]).count()
    res['original'] = Attachment.objects.filter(pk=att.pk, file_key=k1).exists()
    res['marqueurs'] = PieceJointeImportee.objects.filter(company=co).count()
    transaction.set_rollback(True)
res['rien_laisse'] = not Company.objects.filter(slug='acel61-${m}').exists()
sortie(res)`)
  console.log(`[ACEL61] ${J(r)}`)
  expect(r.premier.documents, '1er import : 1 document').toBe(1)
  expect(r.tache.documents, 'tâche hebdomadaire réelle : rien recréé pour la société d\'essai').toBeGreaterThanOrEqual(0)
  for (const k of ['import2', 'import3']) {
    expect([r[k].documents, r[k].skipped], `${k} : 0 document, 2 sautées`).toEqual([0, 2])
  }
  expect([r.documents, r.versions], 'aucun Document ni DocumentVersion pour ces pièces').toEqual([0, 0])
  expect(r.original, 'pièce jointe d\'origine intacte').toBe(true)
  expect(r.marqueurs, 'marqueur « déjà importé » relu en base').toBeGreaterThanOrEqual(1)
  expect(r.rien_laisse, 'transaction annulée').toBe(true)
})

// ═══ PF11.3 — ACEL62 : archive légale altérée OU introuvable → cloche de l'administrateur + résumé des problèmes ═══
etape('PF11.3-ACEL62', ['ACEL62'], async ({ page }) => {
  sondeRejouee('C-ACEL-003')
  await inscrite('ged.verifier_integrite_archives', /^<crontab: 15 3 \* \* \*/)
  const avantEchecs = await echecsConsignes()
  const m = marque()
  const src = Date.now()
  const f = await py(`from django.conf import settings
from apps.ged import services
from apps.records.storage import get_minio_client
a = U.objects.get(username='demo_admin'); co = a.company
res = {'slug': co.slug}
docs = []
for i, nom in enumerate(('ACEL62 contrat altere ${m}.pdf', 'ACEL62 bail introuvable ${m}.pdf')):
    d, _ = services.deposit_document(company=co, nom=nom, source_type='acceptation_acel62', source_id=${src} + i,
        contenu_bytes=('%PDF-1.4 ACEL62 original ' + nom).encode(), mime='application/pdf', cabinet_nom='ACEL62 ${m}', folder_nom='Archives', created_by=a)
    services.archiver_legalement(d, user=a, motif='ACEL62 ${m}')
    docs.append(d.versions.order_by('-version').first().file_key)
c = get_minio_client()
c.put_object(Bucket=settings.MINIO_BUCKET_UPLOADS, Key=docs[0], Body=b'contenu MODIFIE ACEL62')
c.delete_object(Bucket=settings.MINIO_BUCKET_UPLOADS, Key=docs[1])
res['cles'] = docs
sortie(res)`)
  const compter = () => py(`from apps.notifications.models import Notification
sortie(dict(admin=Notification.objects.filter(recipient__username='demo_admin', event_type='security_alert', title__contains='${m}').count(),
  tous=Notification.objects.filter(event_type='security_alert', title__contains='${m}').count()))`)
  // 1er contrôle nocturne : la VRAIE commande (même service que la tâche ged.verifier_integrite_archives).
  const c1 = manage(['verifier_archives', '--company', f.slug])
  console.log(`[ACEL62] 1er passage rc=${c1.code} ${c1.out.slice(-600)} ${c1.err}`)
  expect(c1.code, 'verifier_archives : rc 0').toBe(0)
  const livre = await py(`${LIVRER}
from apps.notifications.models import Notification
sortie(livrer(list(Notification.objects.filter(event_type='security_alert', title__contains='${m}').values_list('pk', flat=True))))`)
  const n1 = await compter()
  console.log(`[ACEL62] notifications ${J(n1)} (livrées à l'ouverture : ${livre})`)
  expect(n1.admin, 'demo_admin : 2 notifications (altérée + introuvable)').toBe(2)
  const e1 = await echecsConsignes()
  expect((e1['ged.verifier_integrite_archives'] || 0) - (avantEchecs['ged.verifier_integrite_archives'] || 0), 'résumé des problèmes : une ligne').toBe(1)
  // Cloche de l'administrateur : les deux archives nommées.
  await page.goto('/ged')
  await cloche(page, `Archive légale introuvable : « ACEL62 bail introuvable ${m}.pdf »`)
  await cloche(page, `Archive légale altérée : « ACEL62 contrat altere ${m}.pdf »`)
  // 2e passage au résultat inchangé : aucune notification ni ligne de plus.
  const c2 = manage(['verifier_archives', '--company', f.slug])
  expect(c2.code, '2e passage : rc 0').toBe(0)
  expect(await compter(), '2e passage : rien de plus').toEqual(n1)
  const e2 = await echecsConsignes()
  expect(e2['ged.verifier_integrite_archives'] || 0, '2e passage : pas de 2e ligne').toBe(e1['ged.verifier_integrite_archives'] || 0)
  await page.reload()
  await cloche(page, `Archive légale introuvable : « ACEL62 bail introuvable ${m}.pdf »`)
})

// ═══ PF11.3 — ACEL65 : dépôt GED d'un document du portail repris après échec, échec définitif consigné ═══
etape('PF11.3-ACEL65', ['ACEL65'], async ({ page, testInfo }) => {
  const m = marque()
  const cl = await py(`from apps.crm.models import Client
c = Client.objects.create(company_id=${SOC}, nom='ACEL65 Client ${m}', email='acel65-${m}@example.invalid', telephone='${telephoneMobileUnique()}')
sortie(c.pk)`)
  const portail = await contextePortailClient({ request: pwRequest }, page.request, testInfo.project.use.baseURL, cl, `P0rtail!${m}`)
  const pdf = (t) => ({ name: `acel65-${t}.pdf`, mimeType: 'application/pdf', buffer: Buffer.from(`%PDF-1.4\n% ACEL65 ${t} ${m}\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n`) })
  const deposer = async (t) => {
    const r = await portail.post(`${API}/portail/mes-documents/`, { ...T, multipart: { type_document: 'facture_onee', libelle: `ACEL65 ${t} ${m}`, fichier: pdf(t) } })
    expect(r.status(), `dépôt portail ${t} : ${(await r.text()).slice(0, 200)}`).toBe(201)
    return (await r.json()).id
  }
  try {
    const ok = await deposer('repris')
    const ko = await deposer('perdu')
    // Le récepteur ne dépose plus dans la requête : la tâche est confiée au courtier (aucun worker ⇒ « GED arrêtée »).
    const etat = await py(`import json as _j, redis
from django.conf import settings
from apps.portail.models import DocumentClientPortail as D
r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
msgs = []
for q in (b'default', b'scheduled', b'interactive', b'bulk'):
    for brut in r.lrange(q, 0, -1):
        try:
            h = _j.loads(brut).get('headers') or {}
        except Exception:
            continue
        if h.get('task') == 'portail.deposer_document_ged':
            msgs.append(h.get('argsrepr'))
sortie(dict(docs=[list(D.objects.filter(pk=p).values_list('fichier_key', 'document_ged_id')[0]) for p in (${ok}, ${ko})], msgs=msgs))`)
    console.log(`[ACEL65] ${J(etat)}`)
    for (const [cle, ged] of etat.docs) {
      expect(cle, 'fichier en stockage objet (clé)').toBeTruthy()
      expect(ged, 'pas encore en GED (aucun worker)').toBeNull()
    }
    expect(etat.msgs, 'tâche portail.deposer_document_ged en file pour chaque dépôt').toEqual(expect.arrayContaining([`(${ok},)`, `(${ko},)`]))
    const avant = await echecsConsignes()
    // La VRAIE tâche, comme le worker l'exécute : la GED lève au 1er appel puis répond.
    const r = await py(`from apps.ged import services as g
from apps.ged.models import Document
from apps.portail.models import DocumentClientPortail as D
from apps.portail.tasks import deposer_document_ged
reel = g.deposit_document
appels = []
def panne_puis_reel(*a, **k):
    appels.append(1)
    if len(appels) == 1:
        raise ConnectionError('ACEL65 : GED arrêtée')
    return reel(*a, **k)
with mock.patch.object(g, 'deposit_document', side_effect=panne_puis_reel):
    e1 = deposer_document_ged.apply(args=[${ok}]).state
n1 = len(appels)
ged = D.objects.get(pk=${ok}).document_ged_id
e2 = deposer_document_ged.apply(args=[${ok}]).state
toujours = []
def toujours_panne(*a, **k):
    toujours.append(1)
    raise ConnectionError('ACEL65 : GED arrêtée pour de bon')
with mock.patch.object(g, 'deposit_document', side_effect=toujours_panne):
    e3 = deposer_document_ged.apply(args=[${ko}]).state
d = Document.objects.filter(pk=ged).first()
sortie(dict(e1=e1, n1=n1, ged=ged, e2=e2, ged_apres=D.objects.get(pk=${ok}).document_ged_id,
  docs=Document.objects.filter(company_id=${SOC}, nom='ACEL65 repris ${m}').count(), e3=e3, essais=len(toujours),
  ko=D.objects.get(pk=${ko}).document_ged_id, nom=d.nom if d else None, cabinet=d.folder.cabinet.nom if d else None, dossier=d.folder.nom if d else None))`)
    console.log(`[ACEL65] ${J(r)}`)
    expect([r.e1, r.n1], 'repris : SUCCESS après une relance').toEqual(['SUCCESS', 2])
    expect(r.ged, 'document_ged posé').toBeTruthy()
    expect([r.e2, r.ged_apres, r.docs], 'relance après succès : rien de plus, un seul document').toEqual(['SUCCESS', r.ged, 1])
    expect([r.e3, r.essais, r.ko], 'échec définitif : FAILURE après 1 + 3 relances, document_ged vide').toEqual(['FAILURE', 4, null])
    const ap = await echecsConsignes()
    expect((ap['portail.deposer_document_ged'] || 0) - (avant['portail.deposer_document_ged'] || 0), 'échec définitif consigné au résumé des problèmes').toBe(1)
    // Écran GED (administrateur) : « Portail client / Documents clients » montre le document repris.
    expect([r.cabinet, r.dossier], 'rangé dans Portail client / Documents clients').toEqual(['Portail client', 'Documents clients'])
    await ouvrirDossierGed(page, 'Portail client', ['Documents clients'])
    await expect(ligneGed(page, r.nom), 'document repris visible').toBeVisible({ timeout: 60_000 })
    await expect(ligneGed(page, r.nom)).toContainText('1 (v1)')
    await expect(page.getByLabel(`Sélectionner ACEL65 perdu ${m}`, { exact: true }), 'document en échec définitif : absent').toHaveCount(0)
    await page.reload()
    await ouvrirDossierGed(page, 'Portail client', ['Documents clients'])
    await expect(ligneGed(page, r.nom), 'après rechargement').toBeVisible({ timeout: 60_000 })
  } finally {
    await portail.dispose()
  }
})

// ═══ PF11.2 — ACEL70 : deux rendus de la même facture à une minute → une seule version GED ═══
etape('PF11.2-ACEL70', ['ACEL70'], async ({ page }) => {
  const m = marque()
  const r = await py(`from decimal import Decimal as D
from datetime import datetime as _dt, timezone as dtz
from freezegun import freeze_time
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ged.models import Document, DocumentVersion, RoutageDocumentaire
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.tasks import task_generate_facture_pdf
a = U.objects.get(username='demo_admin'); co = a.company
res = {'routage': RoutageDocumentaire.objects.filter(company=co, source='ventes_facture').count()}
cl = Client.objects.create(company=co, nom='ACEL70 ${m}', email='acel70-${m}@example.invalid', telephone='${telephoneMobileUnique()}', adresse='Casablanca')
p = Produit.objects.create(company=co, nom='Onduleur ACEL70 ${m}', sku='ACEL70-${m}', prix_vente=D('100.00'), prix_achat=D('60.00'), quantite_stock=10)
f = Facture.objects.create(company=co, reference='FAC-ACEL70-${m}', client=cl, statut='emise', taux_tva=D('20.00'), remise_globale=D('0'), created_by=a)
LigneFacture.objects.create(facture=f, produit=p, designation='Onduleur ACEL70', quantite=D('2'), prix_unitaire=D('100.00'), remise=D('0'))
avant = set(Document.objects.filter(company=co).values_list('pk', flat=True))
with freeze_time(_dt.now(dtz.utc).replace(second=0, microsecond=0)) as t:
    res['r1'] = task_generate_facture_pdf.apply(args=[f.id, a.pk]).state
    t.tick(60)
    res['r2'] = task_generate_facture_pdf.apply(args=[f.id, a.pk]).state
docs = Document.objects.filter(company=co).exclude(pk__in=avant)
res['docs'] = docs.count()
d = docs.first()
res['versions'] = DocumentVersion.objects.filter(document=d).count() if d else 0
if d:
    chemin, x = [], d.folder
    while x is not None:
        chemin.insert(0, x.nom); x = x.parent
    res.update(doc=d.pk, nom=d.nom, cabinet=d.folder.cabinet.nom, chemin=chemin)
res['facture'] = f.pk
sortie(res)`)
  console.log(`[ACEL70] ${J(r)}`)
  expect(r.routage, 'routage ventes_facture semé (ADOC75)').toBeGreaterThanOrEqual(1)
  expect([r.r1, r.r2], 'deux rendus réussis').toEqual(['SUCCESS', 'SUCCESS'])
  expect([r.docs, r.versions], 'deux rendus à une minute : 1 document, 1 version').toEqual([1, 1])
  // Écran GED : « Ventes / Factures / <année> » — une seule version.
  await ouvrirDossierGed(page, r.cabinet, r.chemin)
  await expect(ligneGed(page, r.nom), 'facture rangée en GED').toBeVisible({ timeout: 60_000 })
  await expect(ligneGed(page, r.nom), 'une seule version').toContainText('1 (v1)')
  // Données changées (une ligne de plus) : une 2e version.
  const r3 = await py(`from decimal import Decimal as D
from apps.ged.models import DocumentVersion
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.tasks import task_generate_facture_pdf
from apps.ventes.utils.pdf import empreinte_donnees_facture_pdf
f = Facture.objects.get(pk=${r.facture})
LigneFacture.objects.create(facture=f, produit=Produit.objects.get(sku='ACEL70-${m}'), designation='Ajout ACEL70', quantite=D('1'), prix_unitaire=D('50.00'), remise=D('0'))
e = task_generate_facture_pdf.apply(args=[f.id]).state
f.refresh_from_db()
sortie(dict(e=e, versions=DocumentVersion.objects.filter(document_id=${r.doc}).count(), meta=f.pdf_render_meta == {'empreinte': empreinte_donnees_facture_pdf(f)}))`)
  console.log(`[ACEL70] 3e rendu ${J(r3)}`)
  expect(r3, 'ligne ajoutée : 2 versions, empreinte relue = dernier rendu').toEqual({ e: 'SUCCESS', versions: 2, meta: true })
  await page.reload()
  await ouvrirDossierGed(page, r.cabinet, r.chemin)
  await expect(ligneGed(page, r.nom), 'après rechargement : 2 versions').toContainText('2 (v2)', { timeout: 60_000 })
})

// ═══ PF11.4 — ACEL73 : `manage.py emit_capi_signatures` déclenche la tâche, sans réseau sans configuration ═══
etape('PF11.4-ACEL73', ['ACEL73'], async () => {
  const p = await planning('adsengine.emit_capi_signatures')
  console.log(`[ACEL73] calendrier ${J(p)}`)
  expect(p.enregistree, 'tâche enregistrée').toBe(true)
  expect(p.entrees, 'toujours ABSENTE du planning (synchro Odoo manuelle)').toEqual([])
  const c = manage(['emit_capi_signatures'])
  console.log(`[ACEL73] rc=${c.code} ${c.out.trim()} ${c.err}`)
  expect(c.code, 'commande : rc 0').toBe(0)
  expect(c.out, 'sortie : CRM Dataset non configuré').toContain('CRM Dataset non configuré')
  const r = await py(`import io
from django.core.management import call_command
from apps.adsengine import capi_odoo
co = ${SOC}
def sortie_cmd():
    b = io.StringIO(); call_command('emit_capi_signatures', stdout=b); return b.getvalue().strip()
res = {'configure_pile': capi_odoo.is_configured()}
with mock.patch.object(capi_odoo, 'emit_lead_received') as recus, mock.patch.object(capi_odoo, 'emit_signed_deals') as signes:
    res['sans'] = sortie_cmd()
    res['appels_sans'] = [recus.call_count, signes.call_count]
with mock.patch.object(capi_odoo, 'is_configured', return_value=True), \\
        mock.patch.object(capi_odoo, 'emit_lead_received', side_effect=lambda c: {'emitted': 1 if c.pk == co else 0}), \\
        mock.patch.object(capi_odoo, 'emit_signed_deals', side_effect=lambda c: {'emitted': 2 if c.pk == co else 0}):
    res['avec'] = sortie_cmd()
sortie(res)`)
  console.log(`[ACEL73] ${J(r)}`)
  expect(r.configure_pile, 'pile sans CRM Dataset').toBe(false)
  expect(r.sans, 'sans configuration').toContain('CRM Dataset non configuré')
  expect(r.appels_sans, 'aucun appel aux émetteurs').toEqual([0, 0])
  expect(r.avec, 'configurée : résumé imprimé').toBe('1 reçu(s), 2 signé(s)')
})

// ═══ PF11.5 — ACEL76 : annonce programmée publiée au balayage de 30 min, jour chômé compris ═══
etape('PF11.5-ACEL76', ['ACEL76'], async ({ page, suivi, testInfo }) => {
  await inscrite('notifications.reveiller_snoozes', /^<crontab: \*\/30 \* \* \* \*/)
  const m = marque()
  const titre = `ACEL76 annonce programmée ${m}`
  const nom = `acel76c_${m}`
  await compteRole(nom, 'Commercial')
  apres.push(() => py(`U.objects.filter(username=${J(nom)}).update(is_active=False); sortie(1)`))
  // Programmée à « maintenant + 2 min » par l'administrateur.
  const quand = new Date(Date.now() + 2 * 60_000).toISOString()
  const a = await lireJson(await page.request.post(`${API}/notifications/annonces/`, { ...T, data: { titre, corps: 'Annonce programmée ACEL76', cible_type: 'tous', date_publication: quand } }), 'annonce programmée')
  apres.push(() => page.request.delete(`${API}/notifications/annonces/${a.id}/`, T))
  expect(a.publiee, 'non publiée à la création').toBe(false)
  const p = await ecran(page, suivi, testInfo, nom)
  await p.goto('/annonces')
  await expect(p.getByRole('heading', { name: 'Annonces' }).first()).toBeVisible({ timeout: 60_000 })
  await expect(p.getByText(titre), 'avant l\'heure : invisible').toHaveCount(0)
  // Le passage */30 suivant (horloge à +3 min), un jour chômé : publiée.
  const r = await py(`from apps.notifications import sweeps
from apps.notifications.models import Annonce, Notification
plus3 = timezone.now() + datetime.timedelta(minutes=3)
with mock.patch('django.utils.timezone.now', return_value=plus3), mock.patch.object(sweeps, 'is_jour_ouvre', return_value=False):
    sweeps.reveiller_snoozes()
    an = Annonce.objects.get(pk=${a.id})
    notes = Notification.objects.filter(event_type='annonce_published', title=${J(titre)}).count()
    sweeps.sweep_daily()
    notes_daily = Notification.objects.filter(event_type='annonce_published', title=${J(titre)}).count()
    sweeps.reveiller_snoozes()
sortie(dict(publiee=an.publiee, notes=notes, notes_daily=notes_daily,
  notes_fin=Notification.objects.filter(event_type='annonce_published', title=${J(titre)}).count(),
  destinataire=Notification.objects.filter(event_type='annonce_published', title=${J(titre)}, recipient__username=${J(nom)}).count()))`)
  console.log(`[ACEL76] ${J(r)}`)
  expect(r.publiee, 'publiée par le balayage */30, jour chômé').toBe(true)
  expect(r.notes, 'destinataires notifiés').toBeGreaterThanOrEqual(1)
  expect(r.destinataire, 'le commercial est destinataire').toBe(1)
  expect(r.notes_daily, 'sweep_daily le même jour : rien de plus').toBe(r.notes)
  expect(r.notes_fin, 'second passage : rien de plus').toBe(r.notes)
  await p.reload()
  await expect(p.getByText(titre).first(), 'annonce visible au destinataire').toBeVisible({ timeout: 60_000 })
  await p.reload()
  await expect(p.getByText(titre).first(), 'après rechargement').toBeVisible({ timeout: 60_000 })
})

// ═══ PF11.4 — ACEL77 : assemblage des photos de toit tué → « échec — relancez » après 10 min ═══
etape('PF11.4-ACEL77', ['ACEL77'], async ({ page }) => {
  const m = marque()
  const lead = await lireJson(await page.request.post(`${API}/crm/leads/`, { ...T, data: { nom: `ACEL77 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `acel77-${m}@example.invalid` } }), 'lead')
  apres.push(() => page.request.delete(`${API}/crm/leads/${lead.id}/`, T))
  const v = await lireJson(await page.request.post(`${API}/visites/visites/`, { ...T, data: { lead: lead.id } }), 'visite')
  for (const i of [1, 2]) {
    await lireJson(await page.request.post(`${API}/visites/visites/${v.id}/photos/`, { ...T, multipart: { slot_code: 'toiture_vue_generale', fichier: { name: `toit-${i}.png`, mimeType: 'image/png', buffer: PNG_1PX } } }), `photo ${i}`)
  }
  // Écran de calage : « Assembler les photos » (aucun worker : la tâche reste en file, comme tuée).
  await page.goto(`/visites/${v.id}/calage`)
  await page.getByRole('button', { name: 'Assembler les photos' }).click({ timeout: 60_000 })
  await expect(page.getByText('Assemblage des photos en cours…'), 'en cours').toBeVisible({ timeout: 30_000 })
  const recul = (min) => py(`from apps.visites.models import VisiteTerrain
V = VisiteTerrain.objects.filter(pk=${v.id})
V.update(assemblage_demande_le=timezone.now() - datetime.timedelta(minutes=${min}))
sortie(list(V.values_list('assemblage_etat', flat=True)))`)
  expect(await recul(9), 'demandé il y a 9 min').toEqual(['en_cours'])
  await page.reload()
  await expect(page.getByText('Assemblage des photos en cours…'), 'à 9 min : toujours en cours').toBeVisible({ timeout: 60_000 })
  expect(await recul(11), 'demandé il y a 11 min').toEqual(['en_cours'])
  await page.reload()
  await expect(page.getByText('Assemblage échoué'), 'à 11 min : échec').toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(/relancez/i).first(), 'message « relancez »').toBeVisible()
  const base = await py(`from apps.visites.models import VisiteTerrain
x = VisiteTerrain.objects.get(pk=${v.id})
sortie(dict(etat=x.assemblage_etat, erreur=x.assemblage_erreur, t=x.assemblage_demande_le))`)
  expect(base.etat, 'relu en base : echec').toBe('echec')
  expect(base.erreur).toMatch(/relancez/i)
  await page.reload()
  await expect(page.getByText('Assemblage échoué'), 'après rechargement : échec').toBeVisible({ timeout: 60_000 })
  // Relancer : de nouveau « en cours », nouvel horodatage.
  const t0 = await py(`sortie(timezone.now())`)
  await page.getByRole('button', { name: 'Assembler les photos' }).click()
  await expect(page.getByText('Assemblage des photos en cours…'), 'relancé : en cours').toBeVisible({ timeout: 30_000 })
  const relance = await py(`from apps.visites.models import VisiteTerrain
x = VisiteTerrain.objects.get(pk=${v.id})
sortie(dict(etat=x.assemblage_etat, neuf=x.assemblage_demande_le >= datetime.datetime.fromisoformat(${J(t0)})))`)
  expect(relance, 'relancé : en_cours, horodatage neuf').toEqual({ etat: 'en_cours', neuf: true })
})

// ═══ PF11.5 — ACEL78 : interrupteur « Relevé de compte mensuel automatique » sur la fiche client ═══
etape('PF11.5-ACEL78', ['ACEL78'], async ({ page }) => {
  const p = await planning('ventes.releve_mensuel_reminders')
  console.log(`[ACEL78] calendrier ${J(p)}`)
  expect([p.enregistree, p.file, p.entrees.length], 'tâche du relevé inscrite (file scheduled)').toEqual([true, 'scheduled', 1])
  const m = marque()
  const nom = `ACEL78 Entreprise ${m}`
  const id = await py(`from apps.crm.models import Client
c = Client.objects.create(company_id=${SOC}, nom=${J(nom)}, type_client='entreprise', email='acel78-${m}@example.invalid', telephone='${telephoneMobileUnique()}')
sortie(c.pk)`)
  apres.push(() => page.request.delete(`${API}/crm/clients/${id}/`, T))
  const releve = () => py(`from apps.crm.models import Client
sortie(Client.objects.get(pk=${id}).releve_mensuel_auto)`)
  expect(await releve(), 'éteint au départ').toBe(false)
  const ouvrir = async () => {
    await page.goto('/crm')
    await page.getByPlaceholder('Rechercher nom, email, tél, ICE, IF, RC, CIN…').fill(nom)
    const ligne = page.getByRole('row').filter({ hasText: nom }).first()
    await expect(ligne).toBeVisible({ timeout: 60_000 })
    await ligne.hover()
    await ligne.getByRole('button', { name: 'Éditer' }).click()
    await expect(page.getByText('Éditer le client').first()).toBeVisible({ timeout: 30_000 })
    return page.getByLabel('Relevé de compte mensuel automatique')
  }
  const enregistrer = async () => {
    const [req] = await Promise.all([
      page.waitForRequest((q) => ['PATCH', 'PUT'].includes(q.method()) && new RegExp(`/crm/clients/${id}/?$`).test(new URL(q.url()).pathname), { timeout: 30_000 }),
      page.getByRole('button', { name: 'Mettre à jour' }).click(),
    ])
    await expect(page.getByText('Éditer le client'), 'fiche refermée').toHaveCount(0, { timeout: 30_000 })
    return req.postDataJSON()
  }
  let caseRel = await ouvrir()
  await expect(caseRel, 'case visible, décochée').not.toBeChecked()
  await caseRel.check()
  const corps1 = await enregistrer()
  expect(corps1.releve_mensuel_auto, 'enregistrement : releve_mensuel_auto: true').toBe(true)
  expect(await releve(), 'relu en base : allumé').toBe(true)
  caseRel = await ouvrir()
  await expect(caseRel, 'fiche rouverte : case cochée').toBeChecked()
  // Enregistrer sans toucher la case : la clé n'est pas envoyée.
  const corps2 = await enregistrer()
  expect('releve_mensuel_auto' in corps2, 'case non touchée : clé absente').toBe(false)
  // Éteindre depuis l'ERP.
  caseRel = await ouvrir()
  await caseRel.uncheck()
  const corps3 = await enregistrer()
  expect(corps3.releve_mensuel_auto, 'éteint : false envoyé').toBe(false)
  expect(await releve(), 'relu en base : éteint').toBe(false)
  caseRel = await ouvrir()
  await expect(caseRel, 'fiche rouverte : décochée').not.toBeChecked()
})

// ═══ PF11.4 — ACEL79 : lead sorti (corbeille, archivé, perdu, ne plus contacter) retiré de la file d'attribution ═══
etape('PF11.4-ACEL79', ['ACEL79'], async ({ page, suivi, testInfo }) => {
  await inscrite('crm.attribuer_leads_echus', /^<crontab: \* \* \* \* \*/)
  const m = marque()
  const nomChef = `acel79chef_${m}`
  const chef = await compteRole(nomChef, 'Commercial responsable')
  const membre = await compteRole(`acel79a_${m}`, 'Commercial')
  const f = await py(`from apps.crm.models import EquipeCommerciale, Lead
from apps.crm.dispatch import marquer_en_attente
from apps.crm.models_clients import AttributionEnAttente
import random
co = ${SOC}
eq = EquipeCommerciale.objects.create(company_id=co, nom='ACEL79 ${m}', recoit_leads=True, responsable_id=${chef}, confirmation_responsable=True)
eq.membres.set([${membre}])
leads = {}
for k in ('temoin', 'corbeille', 'archive', 'perdu', 'npc'):
    l = Lead.objects.create(company_id=co, nom='ACEL79 ' + k + ' ${m}', ville='Casablanca', telephone='+2126' + str(random.randint(10000000, 99999999)), owner=marquer_en_attente(eq))
    leads[k] = l.pk
sortie(dict(eq=eq.pk, leads=leads, attentes=AttributionEnAttente.objects.filter(lead_id__in=list(leads.values())).count()))`)
  apres.push(async () => {
    for (const lid of Object.values(f.leads)) await page.request.delete(`${API}/crm/leads/${lid}/`, T).catch(() => null)
    await py(`from apps.crm.models import EquipeCommerciale
EquipeCommerciale.objects.filter(pk=${f.eq}).delete()
U.objects.filter(pk__in=[${chef}, ${membre}]).update(is_active=False)
sortie(1)`)
  })
  expect(f.attentes, 'précondition : 5 leads en attente du responsable').toBe(5)
  // Mis à la corbeille par le vrai geste (suppression), les trois autres sortis.
  const del = await page.request.delete(`${API}/crm/leads/${f.leads.corbeille}/`, T)
  expect(del.status(), 'lead mis à la corbeille').toBeLessThan(300)
  await py(`from apps.crm.models import Lead
M = Lead.all_objects
M.filter(pk=${f.leads.archive}).update(is_archived=True)
M.filter(pk=${f.leads.perdu}).update(perdu=True)
M.filter(pk=${f.leads.npc}).update(ne_plus_contacter=True)
sortie(1)`)
  const nomLead = (k) => `ACEL79 ${k} ${m}`
  const p = await ecran(page, suivi, testInfo, nomChef)
  await p.goto('/crm/attribution')
  await expect(p.getByRole('heading', { name: `Attribution des leads — ACEL79 ${m}` }), 'écran du responsable').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('1 en attente', { exact: true }), 'file : seul le témoin').toBeVisible()
  await expect(p.getByText(nomLead('temoin')).first(), 'témoin dans la file').toBeVisible()
  for (const k of ['corbeille', 'archive', 'perdu', 'npc']) await expect(p.getByText(nomLead(k)), `${k} : absent de la file`).toHaveCount(0)
  // Échéance dépassée : la VRAIE tâche planifiée (chaque minute), deux passages.
  const r = await py(`import logging
from apps.crm.models import Lead
from apps.crm.models_clients import AttributionEnAttente
from apps.crm.tasks import attribuer_leads_echus_task
from apps.notifications.models import Notification
ids = ${J(Object.values(f.leads))}
sortis = ${J(['corbeille', 'archive', 'perdu', 'npc'].map((k) => f.leads[k]))}
AttributionEnAttente.objects.filter(lead_id__in=ids).update(echeance=timezone.now() - datetime.timedelta(minutes=1))
class Capte(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING); self.lignes = []
    def emit(self, rec):
        self.lignes.append(rec.getMessage())
h = Capte(); lg = logging.getLogger('apps.crm.dispatch'); lg.addHandler(h)
try:
    p1 = attribuer_leads_echus_task()
    h.lignes.clear()
    p2 = attribuer_leads_echus_task()
finally:
    lg.removeHandler(h)
M = Lead.all_objects
sortie(dict(p1=p1, p2=p2, avert2=[x for x in h.lignes if 'attente' in x], restantes=AttributionEnAttente.objects.filter(lead_id__in=sortis).count(),
  owners=sorted(set(M.filter(pk__in=sortis).values_list('owner_id', flat=True))), temoin=M.get(pk=${f.leads.temoin}).owner_id,
  notes=[' '.join([n.title, n.body or '', n.link or '']) for n in Notification.objects.filter(recipient_id__in=[${membre}, ${chef}])]))`)
  console.log(`[ACEL79] ${J(r)}`)
  expect(r.restantes, 'aucune attente restante pour les 4 sortis').toBe(0)
  expect(r.owners, 'owner inchangé (le responsable)').toEqual([chef])
  expect(r.temoin, 'témoin attribué au membre').toBe(membre)
  for (const k of ['corbeille', 'archive', 'perdu', 'npc']) {
    const mentions = r.notes.filter((t) => t.includes(nomLead(k)) || new RegExp(`/crm/leads/${f.leads[k]}(?!\\d)`).test(t))
    expect(mentions, `${k} : aucune notification (membre ni responsable)`).toEqual([])
  }
  expect(r.avert2, '2e passage : aucun avertissement').toEqual([])
  await p.reload()
  await expect(p.getByText('Aucun lead en attente'), 'file vide après le passage').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('0 en attente', { exact: true })).toBeVisible()
  for (const k of ['corbeille', 'archive', 'perdu', 'npc']) await expect(p.getByText(nomLead(k)), `${k} : toujours absent`).toHaveCount(0)
})
