// AMSG — preuves en direct, lot 9 (vague d'acceptation 8 sur runner GitHub, 17/11/2026) : l'écran « Mes activités »
// (/activites) du technicien responsable, corrigé par la vague 7 — AMSG102 (lien wa.me de la note), AMSG103 (bouton
// « Enregistrement » vers /chantiers et /interventions), AMSG104 (« — » et non « null null » en colonne Type) — et le
// rejeu SANS écart d'AMSG96/AMSG56 (la tâche « Envoyer ce WhatsApp » de l'expédition et du rappel J-1 est maintenant
// envoyable depuis l'écran). Aucun envoi réel (backend e-mail = console, aucune clé d'envoi). Les tâches sont créées par
// les VRAIES routes/tâches (POST `expedier`, balayage `rappel_rdv_j1` rejoué dans le shell : le beat ne tourne pas sur
// le runner) ; l'écran est celui du technicien (session relayée par cookies). Données propres retirées en fin d'étape.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, connexionApi } from '../helpers.js'

const etape = groupe('AMSG', ['AMSG102', 'AMSG103', 'AMSG104', 'AMSG96', 'AMSG56'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const WA = /https:\/\/wa\.me\/[^\s<>"')]+/
const sessions = []
test.afterAll(async () => { for (const c of sessions) await c.dispose().catch(() => undefined) })

// Fabrique Python : société démo, technicien responsable T (rôle Directeur : /chantiers et /interventions accessibles).
const FABRIQUE = `
import random
import datetime as dt
from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.installations.models import Installation, Livraison, Intervention
from apps.records.models import Activity, ActivityType
ADMIN = U.objects.get(username='demo_admin')
CO = ADMIN.company_id
def technicien(nom):
    return compte(nom, role=Role.objects.get(company_id=CO, nom='Directeur').pk, societe=CO)
def ct(modele):
    return ContentType.objects.get_for_model(modele)
def tel():
    return '+2126' + ''.join(str(random.randint(0, 9)) for _ in range(8))
`
const pyAvec = (code) => py(`${FABRIQUE}\n${code}`)
const nettoyer = (ids) => py(`${FABRIQUE}
from apps.sav.models import Ticket
ids = json.loads(${J(J(ids))})
def sans_erreur(f):
    try:
        f()
    except Exception as exc:
        print('nettoyage', exc)
for mod, cle in ((Livraison, 'livs'), (Intervention, 'intervs'), (Installation, 'installs'), (Lead, 'leads'), (Client, 'clients'), (Ticket, 'tickets')):
    pks = ids.get(cle, [])
    if pks:
        sans_erreur(lambda: Activity.objects.filter(content_type=ct(mod), object_id__in=pks).delete())
sans_erreur(lambda: Ticket.objects.filter(pk__in=ids.get('tickets', [])).delete())
sans_erreur(lambda: Intervention.objects.filter(pk__in=ids.get('intervs', [])).delete())
sans_erreur(lambda: Livraison.objects.filter(pk__in=ids.get('livs', [])).delete())
sans_erreur(lambda: Installation.objects.filter(pk__in=ids.get('installs', [])).delete())
sans_erreur(lambda: Lead.all_objects.filter(pk__in=ids.get('leads', [])).delete())
sans_erreur(lambda: Client.objects.filter(pk__in=ids.get('clients', [])).delete())
sortie(1)`).catch(() => undefined)

/** Session API du technicien + écran : ses cookies posés sur la page d'essai. */
async function enTechnicien(context, testInfo, nom) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  sessions.push(ctx)
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  await context.addCookies((await ctx.storageState()).cookies)
  return ctx
}
const mesTaches = async (ctx) => Object.values(await lireJson(await ctx.get(`${API}/records/activities/mine/`, T), 'mes activités')).flat()
const ligne = (page, texte) => page.getByRole('row').filter({ hasText: texte })

/** Chantier du technicien T + livraison expédiée par la VRAIE route + rappel J-1 sur une intervention du lendemain. */
async function livraisonEtRappel(page, m, nomT) {
  const d = await pyAvec(`t = technicien(${J(nomT)})
c = Client.objects.create(company_id=CO, nom='AMSG9 ' + ${J(m)}, prenom='Essai', email=${J(m.toLowerCase())} + '@example.invalid', telephone=tel())
i = Installation.objects.create(company_id=CO, client=c, reference='CH-AMSG9-' + ${J(m)})
Installation.objects.filter(pk=i.pk).update(technicien_responsable=t, created_by=ADMIN)
liv = Livraison.objects.create(company_id=CO, installation=i, reference='LIV-AMSG9-' + ${J(m)})
sortie(dict(t=t.id, client=c.id, inst=i.id, liv=liv.id))`)
  const ids = { clients: [d.client], installs: [d.inst], livs: [d.liv], intervs: [], leads: [], tickets: [] }
  const rep = await lireJson(await page.request.post(`${API}/installations/livraisons/${d.liv}/expedier/`, { ...T, data: {} }), 'expédier')
  expect(rep.statut, 'livraison en transit').toBe('en_transit')
  if ('email_sent' in rep) expect(rep.email_sent, 'sans clé d’envoi : email_sent faux').toBe(false)
  const sw = await pyAvec(`from apps.installations.tasks import rappel_rdv_j1, casablanca_today
a = Installation.objects.get(pk=${d.inst})
iv = Intervention.objects.create(company_id=a.company_id, installation=a, type_intervention='pose', created_by=ADMIN,
    date_prevue=casablanca_today() + dt.timedelta(days=1), rdv_confirme=False)
res = rappel_rdv_j1()
sortie(dict(interv=iv.id, emails=res['emails_envoyes']))`)
  ids.intervs.push(sw.interv)
  expect(sw.emails, 'sans clé d’envoi : emails_envoyes 0').toBe(0)
  return { ...d, ...sw, ids }
}

// ═══ PF8.5 — AMSG102 + AMSG96/AMSG56 sans écart : « Ouvrir WhatsApp » depuis /activites, sans ouvrir la fiche ═══
etape('PF8.5-AMSG102', ['AMSG102', 'AMSG96', 'AMSG56'], async ({ page, context, testInfo }) => {
  const m = marque().toUpperCase()
  const nomT = `amsg9_t_${m.toLowerCase()}`
  const d = await livraisonEtRappel(page, m, nomT)
  try {
    const autre = await pyAvec(`t = technicien(${J(nomT)})
i2 = Installation.objects.get(pk=${d.inst})
l2 = Livraison.objects.create(company_id=CO, installation=i2, reference='LIV-AMSG9-SANS-' + ${J(m)})
Activity.objects.create(company_id=CO, content_type=ct(Livraison), object_id=l2.pk, summary='Rappeler le transporteur', note='Appeler le chauffeur avant 9 h, sans message.',
    due_date=dt.date.today(), assigned_to=t, created_by=ADMIN)
at, _ = ActivityType.objects.get_or_create(company_id=CO, nom='Appel', defaults=dict(icone='📞'))
lead = Lead.objects.create(company_id=CO, nom='AMSG9 lead ' + ${J(m)}, telephone=tel(), email='lead-' + ${J(m.toLowerCase())} + '@example.invalid')
Activity.objects.create(company_id=CO, content_type=ct(Lead), object_id=lead.pk, activity_type=at, summary='Appeler le prospect',
    due_date=dt.date.today(), assigned_to=t, created_by=ADMIN)
sortie(dict(liv_sans=l2.pk, liv_sans_ref=l2.reference, lead=lead.pk, lead_nom=lead.nom))`)
    d.ids.livs.push(autre.liv_sans)
    d.ids.leads.push(autre.lead)
    const ctxT = await enTechnicien(context, testInfo, nomT)
    const taches = await mesTaches(ctxT)
    const wa = taches.filter((x) => x.summary === 'Envoyer ce WhatsApp')
    expect(wa.length, `AMSG96 : le technicien responsable a ses deux tâches « Envoyer ce WhatsApp » (livraison + rappel J-1) : ${wa.length}`).toBe(2)
    expect(wa.map((x) => x.assigned_to), 'AMSG96 : assignées à T').toEqual([d.t, d.t])
    const tLiv = wa.find((x) => x.target_model === 'installations.livraison')
    const tInt = wa.find((x) => x.target_model === 'installations.intervention')
    expect([!!tLiv, !!tInt], 'une tâche sur la livraison, une sur l’intervention').toEqual([true, true])
    expect(tLiv.target_phone, 'précondition de la clause : target_phone nul').toBeNull()
    const lienLiv = tLiv.note.match(WA)?.[0]
    const lienInt = tInt.note.match(WA)?.[0]
    expect([!!lienLiv, !!lienInt], 'le brouillon (lien wa.me) vit dans la note des deux tâches').toEqual([true, true])
    const verifier = async () => {
      await page.goto('/activites')
      const l1 = ligne(page, tLiv.target_label).filter({ hasText: 'Envoyer ce WhatsApp' }).first()
      await expect(l1, 'la ligne de la tâche de livraison est affichée avec son résumé').toBeVisible({ timeout: 60_000 })
      const a1 = l1.locator('a[title="Ouvrir WhatsApp"]')
      await expect(a1, 'livraison : un seul lien « Ouvrir WhatsApp »').toHaveCount(1)
      await expect(a1, 'livraison : href = lien wa.me de la note').toHaveAttribute('href', lienLiv)
      await expect(a1, 'lien externe').toHaveAttribute('target', '_blank')
      const l2 = ligne(page, tInt.target_label).filter({ hasText: 'Envoyer ce WhatsApp' }).first()
      await expect(l2, 'la ligne de la tâche du rappel J-1 est affichée').toBeVisible({ timeout: 60_000 })
      await expect(l2.locator('a[title="Ouvrir WhatsApp"]'), 'rappel J-1 : href = lien wa.me de la note').toHaveAttribute('href', lienInt)
    }
    await verifier()
    await page.reload()
    await verifier() // persistance : rechargement
    expect(new URL(page.url()).pathname, 'la fiche n’a pas été ouverte').toBe('/activites')
    // Une note sans lien wa.me n'ajoute rien ; une tâche à target_phone garde ses icônes.
    const sans = ligne(page, autre.liv_sans_ref).first()
    await expect(sans, 'tâche sans lien dans la note : ligne affichée').toBeVisible({ timeout: 60_000 })
    await expect(sans.locator('a[title="Ouvrir WhatsApp"], a[title="Appeler"]'), 'note sans wa.me : aucune icône ajoutée').toHaveCount(0)
    const pl = ligne(page, autre.lead_nom).first()
    await expect(pl, 'tâche à target_phone : ligne affichée').toBeVisible({ timeout: 60_000 })
    await expect(pl.locator('a[title="Appeler"]'), 'target_phone : icône Appeler gardée').toHaveCount(1)
    await expect(pl.locator('a[title="Appeler"]')).toHaveAttribute('href', /^tel:/)
    await expect(pl.locator('a[title="Ouvrir WhatsApp"]'), 'target_phone : icône WhatsApp gardée').toHaveCount(1)
    await expect(pl.locator('a[title="Ouvrir WhatsApp"]')).toHaveAttribute('href', /^https:\/\/wa\.me\//)
  } finally {
    await nettoyer(d.ids)
  }
})

// ═══ PF8.5 — AMSG103 : le bouton « Enregistrement » mène au chantier / à l'intervention ═══
etape('PF8.5-AMSG103', ['AMSG103'], async ({ page, context, testInfo }) => {
  const m = marque().toUpperCase()
  const nomT = `amsg9_t3_${m.toLowerCase()}`
  const d = await livraisonEtRappel(page, m, nomT)
  try {
    const x = await pyAvec(`t = technicien(${J(nomT)})
from apps.sav.models import Ticket
lead = Lead.objects.create(company_id=CO, nom='AMSG9 L ' + ${J(m)}, telephone=tel())
tk = Ticket.objects.create(company_id=CO, reference='SAV-AMSG9-' + ${J(m)}, client_id=${d.client})
cibles = dict(lead=(Lead, lead.pk), client=(Client, ${d.client}), installation=(Installation, ${d.inst}), ticket=(Ticket, tk.pk))
for cle, (mod, pk) in cibles.items():
    Activity.objects.create(company_id=CO, content_type=ct(mod), object_id=pk, summary='AMSG9 cible ' + cle + ' ' + ${J(m)},
        due_date=dt.date.today(), assigned_to=t, created_by=ADMIN)
sortie(dict(lead=lead.pk, ticket=tk.pk))`)
    d.ids.leads.push(x.lead)
    d.ids.tickets.push(x.ticket)
    const ctxT = await enTechnicien(context, testInfo, nomT)
    const taches = await mesTaches(ctxT)
    const wa = taches.filter((t) => t.summary === 'Envoyer ce WhatsApp')
    const tLiv = wa.find((t) => t.target_model === 'installations.livraison')
    const tInt = wa.find((t) => t.target_model === 'installations.intervention')
    expect([!!tLiv, !!tInt], 'tâche de livraison et tâche d’intervention du technicien').toEqual([true, true])
    const cible = (cle) => taches.find((t) => t.summary === `AMSG9 cible ${cle} ${m}`)
    // [tâche, chemin attendu après le clic, quoi]
    const attendus = [
      [tLiv, '/chantiers', 'livraison'],
      [tInt, '/interventions', 'intervention'],
      [cible('lead'), `/crm/leads?lead=${x.lead}`, 'lead (inchangé)'],
      [cible('client'), '/crm', 'client (inchangé)'],
      [cible('installation'), '/chantiers', 'chantier (inchangé)'],
      [cible('ticket'), '/sav', 'ticket SAV (inchangé)'],
    ]
    for (const [tache, chemin, quoi] of attendus) {
      expect(tache, `${quoi} : tâche servie à T`).toBeTruthy()
      await page.goto('/activites')
      const l = ligne(page, tache.target_label).filter({ hasText: tache.summary }).first()
      await expect(l, `${quoi} : ligne affichée`).toBeVisible({ timeout: 60_000 })
      await l.getByRole('button', { name: tache.target_label }).click()
      const attendu = new URL(chemin, 'http://x')
      await expect.poll(() => {
        const u = new URL(page.url())
        return `${u.pathname}${u.search}`
      }, { message: `${quoi} : le bouton « Enregistrement » mène à ${chemin}`, timeout: 30_000 }).toBe(`${attendu.pathname}${attendu.search}`)
    }
  } finally {
    await nettoyer(d.ids)
  }
})

// ═══ PF8.5 — AMSG104 : colonne Type « — » pour une tâche sans type ; jamais « null » ni « undefined » ═══
etape('PF8.5-AMSG104', ['AMSG104'], async ({ page, context, testInfo }) => {
  const m = marque().toUpperCase()
  const nomT = `amsg9_t4_${m.toLowerCase()}`
  const d = await livraisonEtRappel(page, m, nomT)
  try {
    const x = await pyAvec(`t = technicien(${J(nomT)})
at, _ = ActivityType.objects.get_or_create(company_id=CO, nom='Appel', defaults=dict(icone='📞'))
lead = Lead.objects.create(company_id=CO, nom='AMSG9 T ' + ${J(m)}, telephone=tel())
Activity.objects.create(company_id=CO, content_type=ct(Lead), object_id=lead.pk, activity_type=at, summary='Appeler AMSG9 ' + ${J(m)},
    due_date=dt.date.today(), assigned_to=t, created_by=ADMIN)
sortie(dict(lead=lead.pk, icone=at.icone, nom=at.nom))`)
    d.ids.leads.push(x.lead)
    const ctxT = await enTechnicien(context, testInfo, nomT)
    const taches = await mesTaches(ctxT)
    const sansType = taches.find((t) => t.summary === 'Envoyer ce WhatsApp' && t.target_model === 'installations.livraison')
    expect(sansType, 'tâche « Envoyer ce WhatsApp » de la livraison servie à T').toBeTruthy()
    expect([sansType.activity_type_icone, sansType.activity_type_nom], 'précondition : servie sans type (icône et nom null)').toEqual([null, null])
    const verifier = async () => {
      await page.goto('/activites')
      const l1 = ligne(page, sansType.target_label).filter({ hasText: 'Envoyer ce WhatsApp' }).first()
      await expect(l1, 'ligne de la tâche sans type').toBeVisible({ timeout: 60_000 })
      await expect(l1.getByRole('cell').first(), 'colonne Type : « — » pour une tâche sans type').toHaveText('—')
      const l2 = ligne(page, `Appeler AMSG9 ${m}`).first()
      await expect(l2, 'ligne de la tâche « Appel » typée').toBeVisible({ timeout: 60_000 })
      await expect(l2.getByRole('cell').first(), 'colonne Type : icône et nom du type').toHaveText(`${x.icone} ${x.nom}`)
      const corps = await page.locator('body').innerText()
      expect(corps, 'jamais « null » à l’écran').not.toMatch(/\bnull\b/)
      expect(corps, 'jamais « undefined » à l’écran').not.toMatch(/\bundefined\b/)
    }
    await verifier()
    await page.reload()
    await verifier() // persistance : rechargement
  } finally {
    await nettoyer(d.ids)
  }
})
