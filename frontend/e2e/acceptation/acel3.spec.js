// Preuves en direct du groupe ACEL (tâches planifiées), lot 3 — vague d'acceptation 8 sur runner GitHub (METHODE §C.4 point 7) :
// ACEL31 (D-ACEL-1 = heure_respectee) APRÈS la moitié « planning » (ACEL1 : `reporting-email-saved-reports` passe à chaque
// heure pile de 6 h à 23 h). Le runner n'a NI worker Celery NI beat : (1) le planning RÉEL est lu dans `beat_schedule` ;
// (2) la sonde C-ACEL-001 est REJOUÉE sur ce planning ⇒ repro faux ; (3) la VRAIE tâche `email_saved_reports` est appelée à
// CHAQUE heure de passage lue dans le planning (heure simulée), puis l'historique est relu en base ; (4) l'écran « Envois
// programmés » est AFFIRMÉ (ligne réglée à 8 h, lignes d'historique « non configuré », aide « Vide : 6 h … »).
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage } from '../helpers.js'

const etape = groupe('ACEL', ['ACEL31'])
fermerDjangoApresTout()
const J = JSON.stringify
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const apres = []
test.afterEach(async () => {
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const HEURES = Array.from({ length: 18 }, (_, i) => i + 6) // 6 … 23

/** Sonde HÔTE (`docs/audits/sondes/ACEL/<c>.py`) : {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'ACEL', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin],
    { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}

etape('PF11-ACEL31-planning-sonde', ['ACEL31'], async ({ page }) => {
  // (1) Planning RÉEL (celery.beat_schedule chargé par l'application) : UNE entrée pour la tâche, minute 0, heures 6 à 23.
  const beat = await py(`from celery.schedules import crontab
from erp_agentique.celery import app
app.loader.import_default_modules()
res = {}
for cle, e in app.conf.beat_schedule.items():
    if e.get('task') != 'reporting.email_saved_reports': continue
    s = e['schedule']
    res[cle] = dict(heures=sorted(s.hour), minutes=sorted(s.minute), jours=sorted(s.day_of_week), expires=e.get('options', {}).get('expires'))
sortie(res)`)
  console.log(`[ACEL31] planning : ${J(beat)}`)
  expect(Object.keys(beat), 'UNE seule entrée du planning lance reporting.email_saved_reports').toHaveLength(1)
  const e = Object.values(beat)[0]
  expect(e.heures, 'passage à CHAQUE heure de 6 h à 23 h').toEqual(HEURES)
  expect(e.minutes, 'à l\'heure pile').toEqual([0])
  expect(e.jours, 'tous les jours').toEqual([0, 1, 2, 3, 4, 5, 6])
  // (2) Sonde C-ACEL-001 rejouée sur ce planning : elle doit CONCLURE (jamais « inconclusif ») et ne plus reproduire.
  const s = sondeHote('C-ACEL-001')
  console.log(`[ACEL31] sonde C-ACEL-001 : ${s.ok ? J(s.res).slice(0, 900) : s.err}`)
  expect(s.ok, `la sonde C-ACEL-001 s'exécute (${s.err || ''})`).toBe(true)
  expect(s.res.observe?.inconclusif, 'la sonde conclut (aucun bouchon périmé)').toBeUndefined()
  expect(s.res.repro, 'sonde C-ACEL-001 rejouée : repro FAUX').toBe(false)
  const o = s.res.observe
  expect(Object.values(o.entrees_beat_de_la_tache), 'la sonde lit les 18 passages du planning').toEqual([HEURES])
  expect(o.heures_reglees_jamais_dues, 'aucune heure réglée (7, 8, 9 h) n\'est « jamais due »').toEqual([])
  expect(o.plus_d_un_envoi_par_jour, 'jamais plus d\'un envoi par jour').toEqual([])
  expect(o.passages_ou_le_rapport_est_du['8'][0], 'réglé à 8 h : dû dès le passage de 8 h').toBe(8)
  expect(Object.values(o.conforme_a_l_ecran_3h_et_vide_a_6h), 'écran : « vide = 6 h ; de 0 à 5 h, part à 6 h »').toEqual([true, true])
  // Trace lisible : la sortie de la sonde et le planning sont affichés dans la page capturée (plus de page blanche).
  const echapper = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;')
  await page.setContent(`<html><body style="font:13px monospace;padding:16px"><h3>ACEL31 — sonde C-ACEL-001 rejouée : repro = ${J(s.res.repro)}</h3>`
    + `<p>planning réel (beat_schedule) : ${echapper(J(beat))}</p>`
    + `<pre style="white-space:pre-wrap">${echapper(J({ repro: s.res.repro, observe: o }, null, 1)).slice(0, 5000)}</pre></body></html>`)
  await expect(page.getByRole('heading', { name: /repro = false/ }), 'la capture montre la sortie de la sonde').toBeVisible()
})

etape('PF11-ACEL31-historique-ecran', ['ACEL31'], async ({ page, testInfo, suivi }) => {
  const m = marque()
  const noms = { a: `ACEL31 A8h ${m}`, b: `ACEL31 B vide ${m}`, c: `ACEL31 C23h ${m}`, d: `ACEL31 D3h ${m}` }
  apres.push(() => py(`from apps.reporting.models import SavedReport
SavedReport.objects.filter(name__in=${J(Object.values(noms))}).delete()
sortie(True)`))
  // (3) La VRAIE tâche, à CHAQUE heure de passage LUE dans le planning, un lundi puis un mardi (passage de 8 h manquant).
  const r = await py(`import zoneinfo
from celery.schedules import crontab
from erp_agentique.celery import app
from apps.reporting.models import SavedReport, EnvoiRapport
from apps.reporting import scheduled_reports as sr
TZ = zoneinfo.ZoneInfo('Africa/Casablanca')
app.loader.import_default_modules()
passages = sorted(next(e['schedule'] for e in app.conf.beat_schedule.values() if e.get('task') == 'reporting.email_saved_reports').hour)
mk = lambda nom, h: SavedReport.objects.create(company_id=${SOC}, name=nom, target_kind='sales', schedule='daily', recipients='boss@example.com', heure_envoi=h)
a = mk(${J(noms.a)}, 8); b = mk(${J(noms.b)}, None); c = mk(${J(noms.c)}, 23); d = mk(${J(noms.d)}, 3)
lundi = timezone.localdate() - datetime.timedelta(days=2)
while lundi.weekday() != 0: lundi -= datetime.timedelta(days=1)
mardi = lundi + datetime.timedelta(days=1)
def passer(jour, heures):
    for h in heures:
        quand = datetime.datetime(jour.year, jour.month, jour.day, h, 0, tzinfo=TZ)
        with mock.patch('django.utils.timezone.now', return_value=quand), mock.patch.object(sr, '_casablanca_now', return_value=quand):
            sr.email_saved_reports()
def heures(rapport, jour):
    return sorted(e.envoye_le.astimezone(TZ).hour for e in EnvoiRapport.objects.filter(saved_report=rapport) if e.envoye_le.astimezone(TZ).date() == jour)
tous = (a, b, c, d)
passer(lundi, passages)
res = dict(passages=passages, lundi={k: heures(x, lundi) for k, x in zip('abcd', tous)})
passer(mardi, [h for h in passages if h != 8])
res['mardi'] = {k: heures(x, mardi) for k, x in zip('abcd', tous)}
res['a_lundi_utc'] = sorted(e.envoye_le.astimezone(datetime.timezone.utc).hour for e in EnvoiRapport.objects.filter(saved_report=a) if e.envoye_le.astimezone(TZ).date() == lundi)
res['total'] = EnvoiRapport.objects.filter(saved_report__in=tous).count()
passer(mardi, passages)
res['total_apres_rejeu'] = EnvoiRapport.objects.filter(saved_report__in=tous).count()
res['statuts'] = sorted(set(EnvoiRapport.objects.filter(saved_report__in=tous).values_list('statut', flat=True)))
sortie(res)`)
  console.log(`[ACEL31] historique : ${J(r)}`)
  expect(r.passages, 'passages lus dans le planning').toEqual(HEURES)
  expect(r.lundi, 'lundi : UNE ligne par rapport — A à 8 h, B (vide) à 6 h, C à 23 h, D (3 h) à 6 h').toEqual({ a: [8], b: [6], c: [23], d: [6] })
  expect(r.mardi, 'mardi, passage de 8 h manquant : A part au passage suivant (9 h), les autres comme lundi').toEqual({ a: [9], b: [6], c: [23], d: [6] })
  expect(r.total, 'huit lignes en tout (une par rapport et par jour)').toBe(8)
  expect(r.total_apres_rejeu, 'rejouer toutes les passes du mardi : aucune ligne de plus').toBe(8)
  // (4) Écran « Envois programmés » : la ligne réglée à 8 h, l'historique « non configuré » (aucune clé d'envoi sur le runner).
  await page.goto('/reporting/envois-programmes')
  await expect(page.getByRole('heading', { name: /Envois programmés/ }).first(), 'écran « Envois programmés »').toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('row').filter({ hasText: noms.a }).filter({ hasText: /à 8 h/ }).first(), 'le rapport A est réglé « à 8 h »').toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('row').filter({ hasText: noms.a }).filter({ hasText: /non configur/i }), 'historique : les 2 lignes « non configuré » de A (lundi et mardi)').toHaveCount(2, { timeout: 60_000 })
  for (const k of ['b', 'c', 'd']) {
    await expect(page.getByRole('row').filter({ hasText: noms[k] }).filter({ hasText: /non configur/i }), `historique : 2 lignes « non configuré » du rapport ${k.toUpperCase()}`).toHaveCount(2)
  }
  // L'aide du champ « Heure d'envoi » dit la règle livrée : vide = 6 h ; de 0 à 5 h, part à 6 h.
  await page.getByRole('button', { name: `Modifier ${noms.b}` }).click()
  await expect(page.getByText('Vide : 6 h ; de 0 à 5 h, part à 6 h.'), "aide du champ « Heure d'envoi »").toBeVisible({ timeout: 30_000 })
  // Table « Historique des envois », lue en heure de Casablanca : la ligne « non configuré » de A à 08:00 (lundi), puis 09:00 (mardi).
  const u = testInfo.project.use
  // Fuseau d'affichage = celui qui rend « heure de Casablanca » pour CE serveur (l'ICU de Chromium et le tzdata du serveur
  // peuvent différer sur le Maroc) : décalage = 8 h locales − heure UTC de la ligne de A du lundi.
  const decalage = 8 - r.a_lundi_utc[0]
  expect([0, 1], `décalage Casablanca/UTC du serveur (UTC de la ligne de A : ${J(r.a_lundi_utc)})`).toContain(decalage)
  const fuseau = decalage === 0 ? 'UTC' : 'Etc/GMT-1'
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: await page.context().storageState(), serviceWorkers: 'block',
    timezoneId: fuseau, ...(u.locale ? { locale: u.locale } : {}), ...(u.viewport ? { viewport: u.viewport } : {}),
  })
  apres.push(() => ctx.close())
  await page.close()
  const p2 = suivi.surveiller(await ctx.newPage())
  await p2.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await p2.goto('/reporting/envois-programmes')
  const histo = p2.getByRole('table', { name: 'Historique des envois' })
  await expect(histo, 'table « Historique des envois »').toBeVisible({ timeout: 60_000 })
  await expect(histo.getByRole('row').filter({ hasText: noms.a }), 'historique : 2 lignes de A').toHaveCount(2, { timeout: 60_000 })
  console.log(`[ACEL31] lignes de A à l'écran (fuseau ${fuseau}) : ${J(await histo.getByRole('row').filter({ hasText: noms.a }).allInnerTexts())}`)
  const ligneA8 = histo.getByRole('row').filter({ hasText: noms.a }).filter({ hasText: /(?<!\d)08:00(?!\d)/ })
  await expect(ligneA8, 'historique : la ligne de A à 08:00').toHaveCount(1, { timeout: 60_000 })
  await expect(ligneA8, "cette ligne est « non configuré » (aucune clé d'envoi sur le runner)").toContainText(/non configur/i)
  const ligneA9 = histo.getByRole('row').filter({ hasText: noms.a }).filter({ hasText: /(?<!\d)09:00(?!\d)/ })
  await expect(ligneA9, 'historique : mardi, passage de 8 h manquant, la ligne de A à 09:00').toHaveCount(1)
  await expect(histo.getByRole('row').filter({ hasText: noms.b }).filter({ hasText: /(?<!\d)06:00(?!\d)/ }), 'B (vide) à 06:00 : 2 lignes').toHaveCount(2)
  await ligneA8.scrollIntoViewIfNeeded()
  testInfo.annotations.push({ type: 'historique', description: J(r) })
})
