// Preuves en direct AMSG97 et AMSG99 (audit PF8 « messages et contacts », clôture du 14/11) :
// - AMSG97 : la commande de réparation `opposer_fiches_soeurs` (D-AMSG-2, réparation après liste montrée)
//   jouée par le VRAI `manage.py` (sous-processus, comme le lancera Reda) sur une paire laissée par la
//   migration 0154 : dry-run d'abord (liste sans numéro, rien écrit), puis `--appliquer` (en excluant par
//   `--sauf` toute autre fiche listée de la base jetable) ; relu en base ; seconde application ⇒ 0 fiche.
//   Aucun écran (0 écran dans la tâche) : la fiche B est montrée pour la capture seulement.
// - AMSG99 : pile au backend console (aucune clé d'envoi : l'e-mail ne part pas), réglage SAV allumé ; un
//   Directeur passe le ticket à « Planifié » PAR L'ÉCRAN du ticket, puis le technicien responsable se
//   connecte : « Mes activités » (/activites) liste « Envoyer ce WhatsApp ».
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps, connexionApi, telephoneMobileUnique, lireJson } from '../helpers.js'

const etape = groupe('AMSG', ['AMSG97', 'AMSG99'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 420_000 })
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
test.beforeEach(async ({ page }) => { await page.addInitScript(INIT); await assurerSessionPage(page) })
const ouverts = []
const apres = []
test.afterEach(async () => {
  for (const c of ouverts.splice(0)) await (c.dispose ? c.dispose() : c.close()).catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const note = (testInfo, type, description) => {
  testInfo.annotations.push({ type, description })
  console.log(`[AMSG] ${type} : ${description}`)
}

/** `manage.py <commande> …` dans le conteneur/répertoire Django (même voie que le shell d'acceptation). */
function manage(...args) {
  const [cmd, ...pre] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const r = spawnSync(cmd, [...pre, 'python', 'manage.py', ...args], { encoding: 'utf8', maxBuffer: 20_000_000 })
  if (r.status !== 0) throw new Error(`manage.py ${args.join(' ')} → ${r.status} : ${(r.stderr || '').slice(-800)}`)
  return r.stdout
}
/** Sonde HÔTE du dossier (`docs/audits/sondes/AMSG/<c>.py`) ; {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AMSG', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
/** Compte d'essai du rôle LIVRÉ `nomRole` (palier légacy dérivé) ; renvoie son id. */
const compteRole = (nom, nomRole) => py(`from apps.roles.models import Role
from authentication.role_tiers import tier_for_role_fields
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.role_legacy = tier_for_role_fields(r.nom, r.est_systeme, r.permissions); u.save(update_fields=['role_legacy'])
sortie(u.id)`)
/** Navigateur À FROID du compte `nom` (connexion par l'écran), surveillé par les oracles. */
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), viewport: { width: 1920, height: 1080 },
  })
  ouverts.push(ctx)
  if (!page.isClosed()) await page.close()
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}

// ═══ AMSG97 — `opposer_fiches_soeurs` : dry-run liste B sans rien écrire, `--appliquer` la coche (chatter) ═══
etape('PF8.2-AMSG97-commande', ['AMSG97'], async ({ page, testInfo }) => {
  const m = marque()
  const brut = telephoneMobileUnique().slice(4) // 6XXXXXXXX
  const tel0 = `0${brut}`                       // « 0600000000 »
  const telIntl = `+212 ${brut[0]} ${brut.slice(1, 3)} ${brut.slice(3, 5)} ${brut.slice(5, 7)} ${brut.slice(7, 9)}` // « +212 6 00 00 00 00 »
  // Given : A et B contactables au même numéro écrit autrement ; A passée opposée par `update()` et son empreinte
  // écrite par `bulk_create` (état laissé par la migration 0154 : aucune sœur cochée) ; C même numéro dans une
  // AUTRE société ; D contactable sans contact commun.
  const x = await py(`from apps.crm.models import Lead, EmpreinteOpposition
from apps.crm.leads_doublons import empreintes_contact
from authentication.models import Company
co = Company.objects.get(pk=${SOC})
a = Lead.objects.create(company=co, nom='A97 ${m}', telephone='${tel0}')
b = Lead.objects.create(company=co, nom='B97 ${m}', telephone='${telIntl}')
autre = Company.objects.create(nom='AMSG97 Autre ${m}', slug='amsg97-autre-${m}')
c = Lead.objects.create(company=autre, nom='C97 ${m}', telephone='${tel0}')
d = Lead.objects.create(company=co, nom='D97 ${m}', telephone='${telephoneMobileUnique()}')
Lead.objects.filter(pk=a.pk).update(ne_plus_contacter=True)
emp = list(empreintes_contact(telephone='${tel0}'))
EmpreinteOpposition.objects.bulk_create([EmpreinteOpposition(company=co, nature=n, empreinte=e) for n, e in emp], ignore_conflicts=True)
b.refresh_from_db()
sortie(dict(a=a.pk, b=b.pk, c=c.pk, d=d.pk, autre=autre.pk, slug=co.slug, b_oppose=b.ne_plus_contacter, empreintes=[e for _, e in emp]))`)
  apres.push(() => py(`from apps.crm.models import Lead, EmpreinteOpposition
from authentication.models import Company
for pk in ${J([x.a, x.b, x.c, x.d])}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)
EmpreinteOpposition.objects.filter(company_id=${SOC}, empreinte__in=${J(x.empreintes)}).delete()
try: Company.objects.filter(pk=${x.autre}).delete()
except Exception as exc: print('nettoyage société', exc)
sortie(True)`))
  expect(x.b_oppose, 'Given : B contactable (aucune sœur cochée par la migration 0154)').toBe(false)
  const etat = () => py(`from apps.crm.models import Lead, LeadActivity
from apps.crm.selectors import peut_contacter
r = {}
for k, pk in ${J({ b: x.b, c: x.c, d: x.d })}.items():
    le = Lead.all_objects.get(pk=pk)
    r[k] = [le.ne_plus_contacter, bool(peut_contacter(le))]
r['chatter_b'] = [[a.old_value, a.new_value] for a in LeadActivity.objects.filter(lead_id=${x.b}, kind=LeadActivity.Kind.MODIFICATION, field='ne_plus_contacter')]
sortie(r)`)
  const avant = await etat()
  expect([avant.b, avant.c, avant.d], 'Given : B, C, D contactables').toEqual([[false, true], [false, true], [false, true]])
  // When (1) : `manage.py opposer_fiches_soeurs` (dry-run, toutes sociétés).
  const apercu = manage('opposer_fiches_soeurs')
  console.log(`[AMSG97] dry-run :\n${apercu}`)
  const listees = [...apercu.matchAll(/lead #(\d+) · société (\S+) · contact commun : (\S+)/g)].map((y) => ({ pk: Number(y[1]), slug: y[2], nature: y[3] }))
  const ligneB = listees.find((y) => y.pk === x.b)
  expect(ligneB, 'dry-run : une ligne pour B').toEqual({ pk: x.b, slug: x.slug, nature: 'téléphone' })
  expect(listees.map((y) => y.pk), 'dry-run : ni C (autre société) ni D (aucun contact commun)').not.toEqual(expect.arrayContaining([x.c]))
  expect(listees.map((y) => y.pk)).not.toEqual(expect.arrayContaining([x.d]))
  expect(apercu, 'jamais le numéro').not.toContain(brut.slice(1))
  expect(apercu).toContain(`${listees.length} fiche(s) — dry-run, rien écrit`)
  expect(await etat(), 'dry-run : rien écrit (B inchangée)').toEqual(avant)
  // When (2) : `--appliquer` — les AUTRES fiches que la base jetable listerait sont exclues par `--sauf`
  // (geste du fondateur après la liste montrée).
  const sauf = listees.filter((y) => y.pk !== x.b).map((y) => y.pk)
  note(testInfo, 'dry-run', `${listees.length} fiche(s) listée(s) ; exclues par --sauf : ${J(sauf)}`)
  const opts = ['opposer_fiches_soeurs', '--appliquer', ...(sauf.length ? ['--sauf', sauf.join(',')] : [])]
  const applique = manage(...opts)
  console.log(`[AMSG97] appliqué : ${applique}`)
  expect(applique).toContain('1 fiche(s) cochée(s)')
  // Then + persistance : B cochée avec sa ligne de chatter ancien → nouveau, plus contactable ; C et D inchangées.
  const e = await etat()
  expect(e.b, 'B relue : ne_plus_contacter, peut_contacter faux').toEqual([true, false])
  expect(e.chatter_b.length, `une ligne de chatter sur B (${J(e.chatter_b)})`).toBe(1)
  expect([e.c, e.d], 'C (autre société) et D inchangées').toEqual([[false, true], [false, true]])
  // Seconde application : 0 fiche.
  expect(manage(...opts), 'seconde application : rien').toContain('0 fiche(s) cochée(s)')
  expect(manage('opposer_fiches_soeurs'), 'dry-run rejoué : B n\'est plus listée').not.toContain(`lead #${x.b} `)
  // Sonde du constat : elle modélise la chaîne STOP (faux ORM, sans la commande) — relevée, jamais comptée.
  const s = sondeHote('C-AMSG-VER3-100')
  console.log(`[AMSG97] sonde C-AMSG-VER3-100 (hors commande, non comptée) : ${s.ok ? J(s.res).slice(0, 300) : s.err}`)
  await page.goto(`/crm/leads/${x.b}`)
  await expect(page.locator('body')).toContainText(`B97 ${m}`, { timeout: 60_000 })
})

// ═══ AMSG99 — tâche « Envoyer ce WhatsApp » assignée au technicien du ticket, visible dans ses « Mes activités » ═══
etape('PF8.5-AMSG99-ecran', ['AMSG99'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const techNom = `amsg99te_${m}`
  const dirNom = `amsg99di_${m}`
  const creNom = `amsg99cr_${m}`
  const techId = await compteRole(techNom, 'Technicien')
  const dirId = await compteRole(dirNom, 'Directeur')
  const creId = await compteRole(creNom, 'Technicien responsable')
  const x = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import SavSlaSettings, Ticket
co = U.objects.get(username='demo_admin').company
sla = SavSlaSettings.get(co)
avant = sla.notifications_client_sav
sla.notifications_client_sav = True
sla.save(update_fields=['notifications_client_sav'])
from apps.ventes.email_service import is_email_configured
c = Client.objects.create(company=co, nom='Client AMSG99 ${m}', prenom='Essai', telephone='${telephoneMobileUnique()}', email='amsg99-${m}@example.invalid')
inst = Installation.objects.create(company=co, client=c, reference='CHT-AMSG99-${m}')
t1 = Ticket.objects.create(company=co, reference='SAV-AMSG99-${m}-1', client=c, installation=inst, type=Ticket.Type.CORRECTIF,
    statut=Ticket.Statut.NOUVEAU, description='Panne AMSG99 ${m}', created_by=U.objects.get(username='demo_admin'),
    technicien_responsable=U.objects.get(pk=${techId}))
t2 = Ticket.objects.create(company=co, reference='SAV-AMSG99-${m}-2', client=c, installation=inst, type=Ticket.Type.CORRECTIF,
    statut=Ticket.Statut.NOUVEAU, description='Panne AMSG99 ${m} bis', created_by=U.objects.get(pk=${creId}))
sortie(dict(avant=avant, client=c.pk, inst=inst.pk, t1=t1.pk, t2=t2.pk, ref1=t1.reference, ref2=t2.reference, email=is_email_configured()))`)
  apres.push(() => py(`from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.records.models import Activity
from apps.sav.models import SavSlaSettings, Ticket
co = U.objects.get(username='demo_admin').company
sla = SavSlaSettings.get(co); sla.notifications_client_sav = ${x.avant ? 'True' : 'False'}; sla.save(update_fields=['notifications_client_sav'])
for fn in (lambda: Activity.objects.filter(content_type=ContentType.objects.get_for_model(Ticket), object_id__in=[${x.t1}, ${x.t2}]).delete(),
           lambda: Ticket.objects.filter(pk__in=[${x.t1}, ${x.t2}]).delete(), lambda: Installation.objects.filter(pk=${x.inst}).delete(),
           lambda: Client.objects.filter(pk=${x.client}).delete()):
    try: fn()
    except Exception as exc: print('nettoyage', exc)
sortie(True)`))
  expect(x.email, 'pile au backend console : aucune clé d\'envoi configurée').toBe(false)
  const taches = (t) => py(`from django.contrib.contenttypes.models import ContentType
from apps.records.models import Activity
from apps.sav.models import Ticket
sortie([[a.assigned_to_id, a.created_by_id, a.note] for a in Activity.objects.filter(content_type=ContentType.objects.get_for_model(Ticket), object_id=${t}, summary='Envoyer ce WhatsApp')])`)
  // When : un Directeur passe T1 à « Planifié » par l'écran du ticket.
  const pd = await ecran(page, suivi, testInfo, dirNom)
  await pd.goto(`/sav?id=${x.t1}`)
  await expect(pd.getByText('Pièces consommées').first(), 'fiche ticket ouverte').toBeVisible({ timeout: 60_000 })
  // Fiche du ticket : panneau latéral (« Ticket SAV — <réf.> ») ; le sélecteur « Statut » suit son libellé.
  await expect(pd.getByText(`Ticket SAV — ${x.ref1}`)).toBeVisible({ timeout: 30_000 })
  await pd.locator('xpath=//label[normalize-space()="Statut"]/following::button[@role="combobox"][1]').click()
  await pd.getByRole('option', { name: 'Planifié', exact: true }).click()
  const [rep] = await Promise.all([
    pd.waitForResponse((r) => r.request().method() === 'POST' && new RegExp(`/sav/tickets/${x.t1}/planifier/$`).test(new URL(r.url()).pathname), T),
    pd.getByRole('button', { name: 'Mettre à jour' }).first().click(),
  ])
  expect(rep.status(), `planifier : ${(await rep.text()).slice(0, 200)}`).toBe(200)
  await expect(pd.locator('[data-sonner-toast]').filter({ hasText: 'Ticket mis à jour' }).first()).toBeVisible({ timeout: 30_000 })
  // Then : la tâche est assignée au technicien responsable X, créée par le Directeur, avec le brouillon wa.me.
  const t1 = await taches(x.t1)
  expect(t1.length, `une tâche « Envoyer ce WhatsApp » sur T1 (${J(t1).slice(0, 300)})`).toBe(1)
  expect([t1[0][0], t1[0][1]], 'assigned_to = technicien X, created_by = Directeur').toEqual([techId, dirId])
  expect(t1[0][2], 'la tâche porte le lien wa.me').toContain('wa.me/')
  // Connexion du technicien : « Mes activités » liste la tâche (lue par records/activities/mine/).
  const pt = await ecran(pd, suivi, testInfo, techNom)
  const lue = pt.waitForResponse((r) => r.request().method() === 'GET' && /\/records\/activities\/mine\//.test(r.url()), T)
  await pt.goto('/activites')
  const mine = await (await lue).json()
  const servies = Object.values(mine).flat().filter((a) => a && a.summary === 'Envoyer ce WhatsApp')
  expect(servies.length, 'servie au technicien : une tâche « Envoyer ce WhatsApp »').toBe(1)
  note(testInfo, 'tâche servie', `cible « ${servies[0].target_label} », note avec wa.me : ${String(servies[0].note || '').includes('wa.me/')}`)
  // « Mes activités » (tableaux par échéance : la tâche du jour est sous « Aujourd'hui ») ; la même tâche figure
  // aussi dans « Ma file » (file de travail, chargée à part) — affirmée séparément.
  const mesActivites = () => pt.getByRole('table', { name: "Aujourd'hui" }).getByRole('row').filter({ hasText: 'Envoyer ce WhatsApp' })
  const ligne = mesActivites()
  await expect(ligne, '« Mes activités » du technicien : la tâche est listée').toHaveCount(1, { timeout: 60_000 })
  await pt.reload()
  await expect(mesActivites(), 'rechargé : toujours listée dans « Mes activités »').toHaveCount(1, { timeout: 60_000 })
  await expect(pt.getByRole('row').filter({ hasText: 'Envoyer ce WhatsApp' }), 'rechargé : listée aussi dans « Ma file »').toHaveCount(2, { timeout: 60_000 })
  // T2 (sans technicien) transitée SANS utilisateur (user=None, chemin des tâches planifiées) ⇒ tâche au créateur C ;
  // GET records/activities/mine/ de C la liste.
  await py(`from apps.sav.models import Ticket
from apps.sav.services import appliquer_transition_ticket
appliquer_transition_ticket(Ticket.objects.get(pk=${x.t2}), Ticket.Statut.PLANIFIE, None)
sortie(1)`)
  const t2 = await taches(x.t2)
  expect(t2.map((y) => [y[0], y[1]]), 'T2 : assignée au créateur C, created_by vide').toEqual([[creId, null]])
  const apiC = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  ouverts.push(apiC)
  await connexionApi(apiC, { username: creNom, password: MDP_ESSAI })
  const mineC = await lireJson(await apiC.get(`${API}/records/activities/mine/`, T), 'mine C')
  expect(Object.values(mineC).flat().filter((a) => a && a.summary === 'Envoyer ce WhatsApp').length, 'Mes activités de C : la tâche de T2').toBe(1)
})
