// Preuves en direct du groupe ACEL (tâches planifiées), lot 2 — vague d'acceptation 6 sur runner GitHub
// (METHODE §C.4 point 7) : ACEL4, ACEL8, ACEL13, ACEL31, ACEL36, ACEL42, ACEL46.
// Le runner n'a NI worker Celery NI beat : chaque clause est prouvée en lisant le planning réel (`beat_schedule`), en
// appelant la VRAIE fonction de tâche dans le shell Django (heure simulée quand la clause en dépend), puis en relisant la
// base et, quand la clause nomme un écran, en l'AFFIRMANT à l'écran (compte demo_admin = administrateur).
// Écartée (conteneur Docker et PID 1 requis) : ACEL3. ACEL4 et ACEL8 : seules les moitiés lisibles sans worker sont jouées
// (planning et montages) — la moitié « worker arrêté 20 min, messages révoqués » et « exec dans le conteneur » ne l'est pas.
import { test, expect, request as pwRequest } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, connexionApi } from '../helpers.js'

const etape = groupe('ACEL', ['ACEL4', 'ACEL8', 'ACEL13', 'ACEL31', 'ACEL36', 'ACEL42', 'ACEL46'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 600_000 })
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
test.beforeEach(async ({ page }) => { await page.addInitScript(INIT); await assurerSessionPage(page) })
const apres = []
const ouverts = []
test.afterEach(async () => {
  for (const c of ouverts.splice(0)) await c.dispose().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const chemin = (u) => new URL(u).pathname
const lire = (rel) => readFileSync(join(RACINE, rel), 'utf8')

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACEL4 — passages fréquents du planning Celery : `expires` = au plus la période ; commentaires dérivés corrigés
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF11-ACEL4-planning', ['ACEL4'], async ({ page, testInfo }) => {
  const r = await py(`from celery.schedules import crontab
from erp_agentique.celery import app
app.loader.import_default_modules()
def periode(minute):
    m = str(minute)
    if m == '*': return 60
    if m.startswith('*/'): return int(m[2:]) * 60
    if ',' in m:
        v = sorted(int(x) for x in m.split(','))
        return min((v[(i + 1) % len(v)] - v[i]) % 60 or 60 for i in range(len(v))) * 60
    return 3600
frequentes, manques, mauvais = [], [], []
total = 0
for cle, e in app.conf.beat_schedule.items():
    total += 1
    s = e.get('schedule')
    if not isinstance(s, crontab): continue
    if (str(s._orig_hour), str(s._orig_day_of_week), str(s._orig_day_of_month)) != ('*', '*', '*'): continue
    p = periode(s._orig_minute)
    frequentes.append(cle)
    exp = (e.get('options') or {}).get('expires')
    if exp is None: manques.append(cle)
    elif not (0 < float(exp) <= p): mauvais.append([cle, exp, p])
sortie(dict(total=total, frequentes=len(frequentes), manques=manques, mauvais=mauvais))`)
  console.log(`[ACEL4] planning : ${J(r)}`)
  expect(r.frequentes, `entrées sans hour/day_of_week/day_of_month (${r.frequentes} sur ${r.total})`).toBeGreaterThan(0)
  expect(r.manques, 'chaque passage fréquent porte options.expires').toEqual([])
  expect(r.mauvais, '0 < expires ≤ période pour chaque passage fréquent').toEqual([])
  // Commentaires dérivés : les deux affirmations fausses nommées par la clause ont disparu.
  const celery = lire('backend/django_core/erp_agentique/celery.py')
  expect(celery, 'AACQ97 : plus « déclenchable à la main » pour adsengine.emit_capi_signatures').not.toMatch(/emit_capi_signatures[^\n]*déclenchable à la main|déclenchable à la main[^\n]*emit_capi_signatures/)
  const base = lire('backend/django_core/erp_agentique/settings/base.py')
  expect(base, 'CELERY_TASK_ROUTES : plus « beat 30 min » pour crm.sync_odoo_leads').not.toMatch(/sync_odoo_leads[^\n]*beat 30 min/)
  testInfo.annotations.push({ type: 'périmètre', description: 'worker arrêté 20 min / messages révoqués (journal « expired ») non jouable : pas de worker sur le runner' })
  await page.goto('/')
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACEL8 — recalcul hebdomadaire de la couverture i18n : montages du worker et instantané écrit
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF11-ACEL8-i18n', ['ACEL8'], async ({ page }) => {
  const compose = lire('docker-compose.yml')
  const debut = compose.indexOf('\n  celery_worker:')
  const fin = compose.indexOf('\n  celery_worker_interactive:')
  expect(debut, 'service celery_worker présent').toBeGreaterThan(0)
  const bloc = compose.slice(debut, fin > debut ? fin : undefined)
  expect(bloc, 'montage :ro de l\'extracteur i18n sur /opt/scripts').toMatch(/-\s*\.\/scripts\/extract_i18n_strings\.py:\/opt\/scripts\/extract_i18n_strings\.py:ro/)
  expect(bloc, 'montage :ro de frontend/src sur /opt/frontend/src').toMatch(/-\s*\.\/frontend\/src:\/opt\/frontend\/src:ro/)
  const r = await py(`from core.tasks_i18n import recalculer_couverture_i18n_task
from core.models import I18nCoverageSnapshot
from core.dates import aujourd_hui_local
n = recalculer_couverture_i18n_task()
semaine = I18nCoverageSnapshot.lundi_de(aujourd_hui_local())
s = I18nCoverageSnapshot.objects.filter(company_id=${SOC}, semaine=semaine).first()
sortie(dict(n=n, existe=s is not None, composants=(s.composants_total if s else 0), migres=(s.composants_migres if s else 0), pct=(str(s.couverture_pct) if s else None)))`)
  console.log(`[ACEL8] instantané : ${J(r)}`)
  expect(r.n, 'la tâche écrit au moins un instantané').toBeGreaterThan(0)
  expect(r.existe, 'un I18nCoverageSnapshot de la semaine existe').toBe(true)
  expect(r.composants, 'à composants > 0').toBeGreaterThan(0)
  await page.goto('/')
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACEL13 — Sécurité & identité : seuil des comptes dormants lu et enregistré
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF11-ACEL13-ecran', ['ACEL13'], async ({ page, testInfo }) => {
  const avant = await py(`from apps.parametres.models_company import CompanyProfile
p = CompanyProfile.objects.get(company_id=${SOC})
ancien = p.dormant_days
p.dormant_days = 45; p.save(update_fields=['dormant_days'])
sortie(ancien)`)
  apres.push(() => py(`from apps.parametres.models_company import CompanyProfile
CompanyProfile.objects.filter(company_id=${SOC}).update(dormant_days=${Number(avant) || 0})
sortie(True)`))
  const patchs = []
  page.on('request', (q) => { if (q.method() === 'PATCH' && /\/parametres\/update\/$/.test(chemin(q.url()))) patchs.push(q.postDataJSON()) })
  const ouvrirOnglet = async () => {
    await page.goto('/admin/securite-identite')
    await page.getByRole('tab', { name: /Bannière/ }).click({ timeout: 60_000 })
    const champ = page.locator('#dormant')
    await expect(champ, 'champ « Désactivation des comptes dormants (jours) »').toBeVisible({ timeout: 30_000 })
    return champ
  }
  let champ = await ouvrirOnglet()
  await expect(page.getByText('Désactivation des comptes dormants (jours)'), 'libellé').toBeVisible()
  await expect(page.getByText(/0 = jamais/).first(), 'légende « 0 = jamais »').toBeVisible()
  await expect(champ, 'lit 45').toHaveValue('45')
  await champ.fill('60')
  const [r] = await Promise.all([
    page.waitForResponse((q) => q.request().method() === 'PATCH' && /\/parametres\/update\/$/.test(chemin(q.url())), T),
    page.getByRole('button', { name: 'Enregistrer', exact: true }).click(),
  ])
  expect(r.status(), `enregistrement : ${(await r.text()).slice(0, 200)}`).toBe(200)
  expect(patchs.length, 'un PATCH').toBe(1)
  expect(Object.keys(patchs[0]).sort(), 'le corps porte dormant_days avec login_banner_text et lockout_max_attempts')
    .toEqual(['dormant_days', 'lockout_max_attempts', 'login_banner_text'])
  expect(patchs[0].dormant_days, 'dormant_days: 60').toBe(60)
  expect(await py(`from apps.parametres.models_company import CompanyProfile
sortie(CompanyProfile.objects.get(company_id=${SOC}).dormant_days)`), 'base : 60').toBe(60)
  const lu = await lireJson(await page.request.get(`${API}/parametres/`, T), 'profil')
  expect(lu.dormant_days, 'GET /parametres/ relit 60').toBe(60)
  // Persistance : rechargé, l'écran relit 60.
  champ = await ouvrirOnglet()
  await expect(champ, 'rechargé : 60').toHaveValue('60')
  // Un champ vide envoie 0.
  await champ.fill('')
  const [r0] = await Promise.all([
    page.waitForResponse((q) => q.request().method() === 'PATCH' && /\/parametres\/update\/$/.test(chemin(q.url())), T),
    page.getByRole('button', { name: 'Enregistrer', exact: true }).click(),
  ])
  expect(r0.status()).toBe(200)
  expect(patchs[1].dormant_days, 'champ vide : dormant_days = 0').toBe(0)
  testInfo.annotations.push({ type: 'corps PATCH', description: J(patchs) })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACEL31 — rapports programmés d'heure en heure : UNE ligne d'historique par rapport et par jour
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF11-ACEL31-heures', ['ACEL31'], async ({ page, testInfo }) => {
  const m = marque()
  const nomA = `ACEL31 A8h ${m}`
  const nomB = `ACEL31 B ${m}`
  apres.push(() => py(`from apps.reporting.models import SavedReport
SavedReport.objects.filter(name__in=[${J(nomA)}, ${J(nomB)}]).delete()
sortie(True)`))
  const r = await py(`import zoneinfo
from apps.reporting.models import SavedReport, EnvoiRapport
from apps.reporting import scheduled_reports as sr
TZ = zoneinfo.ZoneInfo('Africa/Casablanca')
a = SavedReport.objects.create(company_id=${SOC}, name=${J(nomA)}, target_kind='sales', schedule='daily', recipients='boss@example.com', heure_envoi=8)
b = SavedReport.objects.create(company_id=${SOC}, name=${J(nomB)}, target_kind='sales', schedule='daily', recipients='boss@example.com')
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
passer(lundi, (6, 7, 8, 9, 10))
res = dict(lundi=lundi.isoformat(), mardi=mardi.isoformat(), lundi_a=heures(a, lundi), lundi_b=heures(b, lundi))
passer(mardi, (6, 7, 9))
res.update(mardi_a=heures(a, mardi), mardi_b=heures(b, mardi))
res['total'] = EnvoiRapport.objects.filter(saved_report__in=(a, b)).count()
passer(mardi, (9,))
res['total_apres_rejeu'] = EnvoiRapport.objects.filter(saved_report__in=(a, b)).count()
res['statuts'] = sorted(set(EnvoiRapport.objects.filter(saved_report__in=(a, b)).values_list('statut', flat=True)))
sortie(res)`)
  console.log(`[ACEL31] historique : ${J(r)}`)
  expect([r.lundi_a, r.lundi_b], 'lundi : UNE ligne pour B (passage de 6 h) et UNE pour A (passage de 8 h)').toEqual([[8], [6]])
  expect([r.mardi_a, r.mardi_b], 'mardi (passage de 8 h manquant) : B à 6 h, A à 9 h').toEqual([[9], [6]])
  expect(r.total, 'quatre lignes en tout (une par rapport et par jour)').toBe(4)
  expect(r.total_apres_rejeu, 'rejouer une passe du jour : aucune ligne de plus').toBe(4)
  // Écran « Envois programmés » : le rapport réglé à 8 h montre sa ligne « non configuré » (aucune clé d'envoi sur le runner).
  await page.goto('/reporting/envois-programmes')
  await expect(page.getByRole('heading', { name: /Envois programmés/ }).first(), 'écran « Envois programmés »').toBeVisible({ timeout: 60_000 })
  const reglage = page.getByRole('row').filter({ hasText: nomA }).filter({ hasText: /à 8 h/ })
  await expect(reglage.first(), 'le rapport A est réglé « à 8 h »').toBeVisible({ timeout: 60_000 })
  const histoA = page.getByRole('row').filter({ hasText: nomA }).filter({ hasText: /non configur/i })
  await expect(histoA, 'historique : les 2 lignes « non configuré » de A (lundi et mardi)').toHaveCount(2, { timeout: 60_000 })
  const histoB = page.getByRole('row').filter({ hasText: nomB }).filter({ hasText: /non configur/i })
  await expect(histoB, 'historique : les 2 lignes « non configuré » de B').toHaveCount(2)
  testInfo.annotations.push({ type: 'historique', description: J(r) })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACEL36 — page d'état publique : « inconnu » quand la dernière vérification a plus de 15 minutes
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF11-ACEL36-statut', ['ACEL36'], async ({ page, testInfo }) => {
  const m = marque()
  const etat = await py(`from apps.statuspage.models import ComponentStatus
sortie([[c.pk, c.statut] for c in ComponentStatus.objects.filter(company__isnull=True)])`)
  apres.push(() => py(`from apps.statuspage.models import ComponentStatus
from apps.statuspage.views import PUBLIC_STATUS_CACHE_KEY
from django.core.cache import cache
ComponentStatus.objects.filter(nom__contains='ACEL36 ${m}').delete()
for pk, statut in ${J(etat)}:
    ComponentStatus.objects.filter(pk=pk).update(statut=statut, derniere_verification=timezone.now())
cache.delete(PUBLIC_STATUS_CACHE_KEY)
sortie(True)`))
  // Given : deux composants système `operational` (tous les autres aussi, pour un statut global lisible) vérifiés il y a 20 min.
  const poser = (minutes) => py(`from apps.statuspage.models import ComponentStatus
from apps.statuspage.views import PUBLIC_STATUS_CACHE_KEY
from django.core.cache import cache
for n in ('A', 'B'):
    ComponentStatus.objects.get_or_create(company=None, nom='ACEL36 ${m} ' + n, defaults=dict(statut='operational'))
ComponentStatus.objects.filter(company__isnull=True).update(statut='operational', derniere_verification=timezone.now() - datetime.timedelta(minutes=${minutes}))
cache.delete(PUBLIC_STATUS_CACHE_KEY)
sortie(ComponentStatus.objects.filter(company__isnull=True).count())`)
  expect(await poser(20), 'Given : composants système posés').toBeGreaterThanOrEqual(2)
  const anonyme = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  ouverts.push(anonyme)
  const perime = await anonyme.get(`${API}/statuspage/public/`, T)
  expect(perime.status(), `GET public (périmé) : ${(await perime.text()).slice(0, 200)}`).toBe(200)
  const jp = await perime.json()
  expect([jp.overall_status, jp.donnees_perimees], 'vérification vieille de 20 min : « inconnu » et donnees_perimees').toEqual(['inconnu', true])
  const noms = jp.composants.map((c) => c.nom)
  expect(noms, 'les composants restent listés').toEqual(expect.arrayContaining([`ACEL36 ${m} A`, `ACEL36 ${m} B`]))
  expect(jp.composants.every((c) => !!c.derniere_verification), 'chacun avec sa derniere_verification').toBe(true)
  // Même requête après `derniere_verification` = maintenant (cache vidé) : opérationnel.
  await poser(0)
  const frais = await anonyme.get(`${API}/statuspage/public/`, T)
  const jf = await frais.json()
  expect([frais.status(), jf.overall_status, jf.donnees_perimees], 'vérification fraîche : « operational », données non périmées').toEqual([200, 'operational', false])
  await page.goto('/')
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACEL42 — Paramètres → Achats : interrupteur « Relance proposée des BCF en retard » puis passe de nuit
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF11-ACEL42-ecran', ['ACEL42'], async ({ page, testInfo }) => {
  const m = marque()
  const x = await py(`from decimal import Decimal as D
import datetime
from apps.stock.models import Fournisseur, Produit, AchatsParametres
from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
p = AchatsParametres.for_company(U.objects.get(username='demo_admin').company)
p.relance_bcf_actif = False; p.save(update_fields=['relance_bcf_actif'])
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ACEL42 ${m}', telephone='0600000000')
pr = Produit.objects.create(company_id=${SOC}, nom='Onduleur ACEL42 ${m}', sku='ACEL42-${m}', prix_vente=D('2000'), prix_achat=D('1000'))
b = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference='BCF-ACEL42-${m}', fournisseur=f, statut='envoye', date_livraison_prevue=datetime.date.today() - datetime.timedelta(days=5))
LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=pr, quantite=10, prix_achat_unitaire=D('1000'), quantite_recue=0)
sortie(dict(id=p.pk, ref=b.reference, b=b.pk, f=f.pk, p=pr.pk))`)
  apres.push(() => py(`from apps.stock.models import Fournisseur, Produit, AchatsParametres
from apps.achats.models import BonCommandeFournisseur
from apps.notifications.models import Notification
AchatsParametres.objects.filter(pk=${x.id}).update(relance_bcf_actif=False)
Notification.objects.filter(body__contains=${J(x.ref)}).delete()
BonCommandeFournisseur.objects.filter(pk=${x.b}).delete(); Produit.objects.filter(pk=${x.p}).delete(); Fournisseur.objects.filter(pk=${x.f}).delete()
sortie(True)`))
  // Given : le BCF est en retard mais l'interrupteur est éteint ⇒ la passe de nuit ne propose rien.
  const eteint = await py(`from apps.stock.tasks import relancer_bcf_en_retard_task
from apps.notifications.models import Notification
relancer_bcf_en_retard_task()
sortie(Notification.objects.filter(event_type='bcf_relance_proposee', body__contains=${J(x.ref)}).count())`)
  expect(eteint, 'Given : interrupteur éteint, aucune relance proposée').toBe(0)
  const patchs = []
  page.on('request', (q) => { if (q.method() === 'PATCH' && /\/stock\/achats-parametres\/\d+\/$/.test(chemin(q.url()))) patchs.push(q.postDataJSON()) })
  const ouvrir = async () => {
    await page.goto('/parametres/achats')
    const sw = page.getByRole('switch', { name: 'Proposer la relance des BCF en retard' })
    await expect(sw, 'interrupteur « Proposer la relance des BCF en retard »').toBeVisible({ timeout: 60_000 })
    return sw
  }
  let sw = await ouvrir()
  await expect(sw, 'éteint au départ').not.toBeChecked()
  await sw.click()
  await expect(sw, 'allumé').toBeChecked()
  const [r] = await Promise.all([
    page.waitForResponse((q) => q.request().method() === 'PATCH' && /\/stock\/achats-parametres\/\d+\/$/.test(chemin(q.url())), T),
    page.getByRole('button', { name: 'Enregistrer', exact: true }).click(),
  ])
  expect(r.status(), `PATCH stock/achats-parametres : ${(await r.text()).slice(0, 200)}`).toBe(200)
  expect(patchs[0].relance_bcf_actif, 'le corps envoie relance_bcf_actif: true').toBe(true)
  const relu = await lireJson(await page.request.get(`${API}/stock/achats-parametres/`, T), 'achats-parametres')
  expect(relu.relance_bcf_actif, 'le GET suivant rend relance_bcf_actif: true').toBe(true)
  // Persistance : rechargé, la case est cochée ; base à vrai.
  sw = await ouvrir()
  await expect(sw, 'rechargé : case cochée').toBeChecked()
  // La passe suivante de `stock.relancer_bcf_en_retard` propose la relance du BCF en retard.
  const passe = await py(`from apps.stock.tasks import relancer_bcf_en_retard_task
from apps.stock.models import AchatsParametres
from apps.notifications.models import Notification
res = relancer_bcf_en_retard_task()
n = Notification.objects.filter(event_type='bcf_relance_proposee', body__contains=${J(x.ref)})
sortie(dict(societe=res.get(${SOC}, 0), notifs=n.count(), vrai=AchatsParametres.objects.get(pk=${x.id}).relance_bcf_actif))`)
  expect(passe.vrai, 'AchatsParametres relu : vrai').toBe(true)
  expect(passe.societe, 'la tâche rend ≥ 1 relance proposée pour la société').toBeGreaterThanOrEqual(1)
  expect(passe.notifs, 'une notification bcf_relance_proposee existe pour ce BCF').toBe(1)
  testInfo.annotations.push({ type: 'passe de nuit', description: J(passe) })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACEL46 — récurrences d'intervention d'un chantier : créables à l'écran, jour d'échéance gardé (31/01, 28/02, 31/03)
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF11-ACEL46-ecran', ['ACEL46'], async ({ page, testInfo }) => {
  const m = marque()
  const x = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
cl = Client.objects.create(company_id=${SOC}, nom='ACEL46 ${m}', prenom='Essai', email='acel46-${m}@example.invalid')
a = Installation.objects.create(company_id=${SOC}, reference='CHT-ACEL46A-${m}', client=cl)
b = Installation.objects.create(company_id=${SOC}, reference='CHT-ACEL46B-${m}', client=cl)
sortie(dict(cl=cl.pk, a=a.pk, ref=a.reference, b=b.pk))`)
  apres.push(() => py(`from apps.crm.models import Client
from apps.installations.models import Installation, Intervention, RecurrenceIntervention
for q in (Intervention.objects.filter(installation_id__in=[${x.a}, ${x.b}]), RecurrenceIntervention.objects.filter(installation_id__in=[${x.a}, ${x.b}]),
          Installation.objects.filter(pk__in=[${x.a}, ${x.b}]), Client.objects.filter(pk=${x.cl})):
    try: q.delete()
    except Exception as exc: print('nettoyage', exc)
sortie(True)`))
  // La tâche de 05:35 est inscrite au planning.
  const plan = await py(`from erp_agentique.celery import app
app.loader.import_default_modules()
sortie([[k, str(v['schedule'])] for k, v in app.conf.beat_schedule.items() if v.get('task') == 'installations.generer_interventions_recurrentes'])`)
  console.log(`[ACEL46] planning : ${J(plan)}`)
  expect(plan.length, 'la tâche installations.generer_interventions_recurrentes est au planning').toBeGreaterThanOrEqual(1)
  const rxPost = /\/api\/django\/installations\/recurrences-intervention\/$/
  // Fiche chantier → onglet Interventions → section « Interventions récurrentes ».
  const section = async () => {
    await page.goto(`/chantiers?id=${x.a}`)
    const fiche = page.getByRole('dialog').filter({ hasText: x.ref }).first()
    await expect(fiche, 'fiche du chantier ouverte').toBeVisible({ timeout: 60_000 })
    await page.getByRole('tab', { name: /Interventions/ }).first().click()
    await expect(page.getByText('Interventions récurrentes').first(), 'section « Interventions récurrentes »').toBeVisible({ timeout: 30_000 })
    return fiche
  }
  await section()
  await expect(page.getByText('Aucune intervention récurrente sur ce chantier.'), 'Given : aucune récurrence').toBeVisible({ timeout: 30_000 })
  await page.locator('#rec-type').selectOption('nettoyage')
  await page.locator('#rec-regle').selectOption('mensuelle')
  await page.locator('#rec-date').fill('2026-01-31')
  const [r] = await Promise.all([
    page.waitForResponse((q) => q.request().method() === 'POST' && rxPost.test(chemin(q.url())), T),
    page.locator('div.items-end').filter({ has: page.locator('#rec-date') }).getByRole('button', { name: 'Ajouter', exact: true }).click(),
  ])
  expect(r.status(), `création : ${(await r.text()).slice(0, 300)}`).toBe(201)
  const rec = await r.json()
  expect([rec.regle, rec.intervalle, rec.prochaine_echeance, rec.type_intervention, rec.jour_ancrage], 'récurrence mensuelle × 1, 31/01, jour d\'ancrage 31')
    .toEqual(['mensuelle', 1, '2026-01-31', 'nettoyage', 31])
  await expect(page.getByText(/Nettoyage — Mensuelle/), 'la section liste la récurrence').toBeVisible({ timeout: 30_000 })
  // La tâche génère trois interventions : 31/01, 28/02, 31/03.
  const gen = await py(`from apps.installations.models import Installation, Intervention, RecurrenceIntervention
from apps.installations.services import generer_interventions_recurrentes
inst = Installation.objects.get(pk=${x.a})
crees = generer_interventions_recurrentes(inst.company, aujourd_hui=datetime.date(2026, 3, 31))
r = RecurrenceIntervention.objects.get(pk=${rec.id})
sortie(dict(dates=sorted(i.date_prevue.isoformat() for i in Intervention.objects.filter(installation=inst)), prochaine=r.prochaine_echeance.isoformat(), nb=r.nb_generees))`)
  expect(gen.dates, '3 Intervention du chantier datées 31/01, 28/02, 31/03').toEqual(['2026-01-31', '2026-02-28', '2026-03-31'])
  expect(gen.prochaine, 'prochaine échéance 30/04').toBe('2026-04-30')
  // Persistance : fiche rechargée, la section montre la même récurrence et la prochaine échéance 30/04.
  await section()
  await expect(page.getByText(/Nettoyage — Mensuelle/), 'rechargée : récurrence listée').toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/prochaine échéance\s*30.04.2026/), 'rechargée : prochaine échéance 30/04/2026').toBeVisible()
  // Un autre chantier de la société n'y voit rien.
  const autre = await lireJson(await page.request.get(`${API}/installations/recurrences-intervention/?installation=${x.b}`, T), 'récurrences de l\'autre chantier')
  const lignes = Array.isArray(autre) ? autre : autre.results
  expect(lignes.length, 'autre chantier : aucune récurrence').toBe(0)
  // Une autre société reçoit 404 sur la récurrence.
  const autreSoc = await py(`from authentication.models import Company
co = Company.objects.create(nom='ACEL46 autre ${m}', slug='acel46-autre-${m}')
u = U.objects.create_user(username='acel46x_${m}', password=${J(MDP_ESSAI)}, company=co, role_legacy='admin', email='acel46x-${m}@accept.test')
u.must_change_password = False; u.save()
sortie(dict(co=co.pk, nom=u.username))`)
  apres.push(() => py(`from authentication.models import Company
U.objects.filter(username=${J(autreSoc.nom)}).delete()
try: Company.objects.filter(pk=${autreSoc.co}).delete()
except Exception as exc: print('nettoyage', exc)
sortie(True)`))
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  ouverts.push(ctx)
  await connexionApi(ctx, { username: autreSoc.nom, password: MDP_ESSAI })
  const refus = await ctx.get(`${API}/installations/recurrences-intervention/${rec.id}/`, T)
  expect(refus.status(), `autre société : ${(await refus.text()).slice(0, 200)}`).toBe(404)
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACEL4 (preuve en direct) — vrais beat + worker Celery, lancés par le workflow AVANT les specs (Redis du job) :
// beat seul ~190 s (3 minutes de passages publiés sans worker), puis arrêt du beat, puis worker ~40 s.
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF11-ACEL4-reel', ['ACEL4'], async ({ page, testInfo }) => {
  const lireTmp = (f) => { try { return readFileSync(f, 'utf8') } catch { return '' } }
  const beat = lireTmp('/tmp/acel4-beat.log')
  const worker = lireTmp('/tmp/acel4-worker.log')
  expect(beat.length, 'journal du beat présent (le workflow a lancé un vrai beat)').toBeGreaterThan(0)
  expect(worker.length, 'journal du worker présent (le workflow a lancé un vrai worker)').toBeGreaterThan(0)
  const NOM = 'publicapi\\.retry_webhook_deliveries'
  const publies = (beat.match(/Sending due task publicapi-retry-webhook-deliveries/g) || []).length
  const recus = (worker.match(new RegExp(`Task ${NOM}\\[[0-9a-f-]+\\] received`, 'g')) || []).length
  const reussis = (worker.match(new RegExp(`Task ${NOM}\\[[0-9a-f-]+\\] succeeded`, 'g')) || []).length
  const expires = worker.split('\n').filter((l) => /expire/i.test(l) && l.includes('publicapi.retry_webhook_deliveries'))
  console.log(`[ACEL4] publiés ${publies}, reçus ${recus}, réussis ${reussis}, expirés ${expires.length}`)
  testInfo.annotations.push({ type: 'comptes', description: `publiés ${publies}, reçus ${recus}, réussis ${reussis}, expirés ${expires.length} ; ${expires[0] || ''}` })
  expect(publies, 'le beat a publié ≥ 2 passages pendant que le worker était arrêté').toBeGreaterThanOrEqual(2)
  expect(reussis, 'au retour du worker : exécutée AU PLUS UNE FOIS').toBeLessThanOrEqual(1)
  expect(expires.length, 'les autres messages sont révoqués : journal « expired »').toBeGreaterThanOrEqual(1)
  expect(reussis + expires.length, 'chaque passage publié est soit exécuté une fois, soit expiré').toBeGreaterThanOrEqual(publies)
  await page.goto('/')
})
