// Preuves en direct du groupe ASUP, second lot (audit PF10, dossier docs/audits/2026-11-11-parcours-PF10.md) :
// ASUP42, ASUP44, ASUP49, ASUP47, ASUP52 — celles qui demandent de monter des devis, des visites, un besoin de
// chantier ou l'écran groupé du stock. Même patron que `asup.spec.js` (gestes par la VRAIE route ou le vrai beat
// dans le shell Django, données propres créées puis retirées, relecture en base), et cette fois le volet « à
// l'écran » de chaque clause qui en a un est AFFIRMÉ (planning du terrain, liste des leads, matériel du chantier,
// suggestion « Marque » de la barre groupée). Sonde hôte du constat rejouée : `repro` attendu faux.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import {
  connexionApi, assurerSessionPage, telephoneMobileUnique, lireJson, listeDe, setLeadsView, STAGE_LABELS,
} from '../helpers.js'

const etape = groupe('ASUP', ['ASUP42', 'ASUP44', 'ASUP49', 'ASUP47', 'ASUP52'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

/** Rejoue une sonde HÔTE du dossier (`docs/audits/sondes/ASUP/<c>.py`) ; renvoie {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'ASUP', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
function sondeRejouee(constat) {
  const s = sondeHote(constat)
  expect(s.ok, `sonde ${constat} exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde ${constat} : ${JSON.stringify(s.res.observe)}`).toBe(false)
}

/** Compte d'essai du rôle LIVRÉ `nomRole` dans la société démo, connecté par /token/ (contexte API) ; {ctx, id}. */
async function session(testInfo, nom, nomRole) {
  const id = await creerCompte(nom, nomRole)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { ctx, id }
}
const creerCompte = (nom, nomRole) => py(`from apps.roles.models import Role
u = compte(${JSON.stringify(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nomRole)}).pk, societe=${SOC})
sortie(u.id)`)

/** Un NAVIGATEUR connecté sous un compte d'essai (cookies posés par /token/ dans le contexte), page surveillée. */
async function navigateurSous(page, suivi, testInfo, nom) {
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
  })
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  return { ctx, page: suivi.surveiller(await ctx.newPage()) }
}

// ─────────────────────────────────────────────────────────────────────────────
// ASUP42 — relances (paliers QJ4 + moteur d'engagement) : rien pour un lead archivé ou perdu. Preuve « API
// seulement — 0 écran » : le vrai beat dans une transaction ANNULÉE (il porte sur toutes les sociétés).
etape('PF10.2-ASUP42', ['ASUP42'], async ({ page }) => {
  sondeRejouee('C-ASUP-016')
  const m = marque()
  const [t0, t1, t2, t3] = [telephoneMobileUnique(), telephoneMobileUnique(), telephoneMobileUnique(), telephoneMobileUnique()]
  const res = await py(`from datetime import datetime, time, timedelta
from decimal import Decimal
from django.db import transaction
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.crm.selectors import devis_a_cadence_active
from apps.notifications.models import Notification
from apps.ventes.models import Devis, DevisNudgeLog, ShareLink
from apps.ventes.domain.recouvrement import send_devis_followup_nudges
from apps.ventes.scheduled import engagement_followup_engine
own = U.objects.get(username='demo_admin'); CO = own.company_id
r = {}
with transaction.atomic():
    envoi = datetime.combine(timezone.localdate() - timedelta(days=3), time(12, 0), tzinfo=timezone.get_current_timezone())
    cl = Client.objects.create(company_id=CO, nom='ASUP42 ${m}', prenom='Client', email='asup42_${m}@asup.invalid', telephone='${t0}')
    mk = lambda nom, tel, **k: Lead.objects.create(company_id=CO, nom=nom + ' ${m}', stage=stages.QUOTE_SENT, owner=own, telephone=tel, **k)
    la, lp, lt = mk('ASUP42 archive', '${t1}', is_archived=True), mk('ASUP42 perdu', '${t2}', perdu=True), mk('ASUP42 temoin', '${t3}')
    dv = lambda n, l: Devis.objects.create(company_id=CO, reference='DEV-ASUP42-${m}-' + n, client=cl, lead=l, statut=Devis.Statut.ENVOYE,
                                           taux_tva=Decimal('20'), date_envoi=envoi, created_by=own)
    ds = [dv('A', la), dv('P', lp), dv('T', lt)]
    notifs = lambda: [Notification.objects.filter(link='/ventes/devis?devis=%d' % d.pk).count() for d in ds]
    r['cadence'] = [devis_a_cadence_active(d.pk) for d in ds]
    send_devis_followup_nudges()                       # palier j+2 (envoi il y a 3 jours)
    r['logs'] = [DevisNudgeLog.objects.filter(devis=d).count() for d in ds]
    r['canal'] = list(DevisNudgeLog.objects.filter(devis=ds[2]).values_list('canal', flat=True))
    r['notifs_paliers'] = notifs()
    r['wa_ecartes'] = Notification.objects.filter(body__contains='wa.me', link__in=['/ventes/devis?devis=%d' % d.pk for d in ds[:2]]).count()
    for d in ds: ShareLink.for_devis(d)               # lien jamais ouvert, envoi > 24 h
    engagement_followup_engine()
    r['notifs_moteur'] = notifs()
    r['declencheurs'] = [bool(ShareLink.objects.filter(devis=d).first().engagement_triggers_fired) for d in ds]
    # Persistance : relire DevisNudgeLog, puis lead restauré (archivage / perte levés) ⇒ le palier part au passage suivant.
    r['relu'] = [DevisNudgeLog.objects.filter(devis=d).exists() for d in ds[:2]]
    Lead.objects.filter(pk=la.pk).update(is_archived=False)
    Lead.objects.filter(pk=lp.pk).update(perdu=False)
    send_devis_followup_nudges()
    r['apres_restauration'] = [DevisNudgeLog.objects.filter(devis=d).count() for d in ds[:2]]
    transaction.set_rollback(True)
r['rien_laisse'] = not Devis.objects.filter(reference__startswith='DEV-ASUP42-${m}').exists()
sortie(r)`)
  expect(res.cadence, 'aucune cadence ouverte sur les trois devis').toEqual([false, false, false])
  expect(res.logs, 'palier j+2 : aucun DevisNudgeLog pour D1 (archivé) et D2 (perdu), D3 (témoin) relancé').toEqual([0, 0, 1])
  expect(res.notifs_paliers.slice(0, 2), 'palier : aucune notification pour D1 et D2').toEqual([0, 0])
  expect(res.wa_ecartes, 'aucun brouillon wa.me pour D1 et D2').toBe(0)
  expect(res.declencheurs, 'moteur d\'engagement : D1 et D2 sautés, D3 signalé « non ouverte 24 h »').toEqual([false, false, true])
  expect(res.notifs_moteur.slice(0, 2), 'moteur : aucune notification pour D1 et D2').toEqual([0, 0])
  expect(res.notifs_moteur[2], `moteur : D3 reçoit sa notification (palier ${res.notifs_paliers[2]} → ${res.notifs_moteur[2]}, canal ${res.canal})`).toBeGreaterThan(res.notifs_paliers[2])
  expect(res.relu, 'persistance : relu, toujours aucune ligne pour D1 et D2').toEqual([false, false])
  expect(res.apres_restauration, 'lead restauré ⇒ le palier part au passage suivant').toEqual([1, 1])
  expect(res.rien_laisse, 'transaction annulée').toBe(true)
  // 0 écran (relances produites par le beat) : page ouverte pour les oracles seulement.
  await page.goto('/ventes/devis')
  await expect(page.locator('body')).toBeVisible()
})

// ─────────────────────────────────────────────────────────────────────────────
// ASUP44 — supprimer (unitaire puis en masse) un lead à visite planifiée annule la visite ; à l'écran : la visite
// disparaît de « Ma journée » du terrain assigné ; restaurer le lead ne la replante pas.
etape('PF10.3-ASUP44', ['ASUP44'], async ({ page, suivi, testInfo }) => {
  sondeRejouee('C-ASUP-018')
  const m = marque()
  const terrain = `asup44te_${m}`
  const terrainId = await creerCompte(terrain, 'Commercial terrain')
  const di = await session(testInfo, `asup44di_${m}`, 'Directeur')
  const noms = [`ASUP44 unitaire ${m}`, `ASUP44 masse ${m}`, `ASUP44 sans visite ${m}`]
  const tels = noms.map(() => telephoneMobileUnique())
  const ids = await py(`from apps.crm import stages
from apps.crm.models import Lead
from apps.visites import services as visites_services
from core.dates import aujourd_hui_local
own = U.objects.get(username='demo_admin'); te = U.objects.get(pk=${terrainId})
mk = lambda nom, tel: Lead.objects.create(company_id=own.company_id, nom=nom, stage=stages.CONTACTED, owner=own, telephone=tel)
leads = [mk(n, t) for n, t in zip(${JSON.stringify(noms)}, ${JSON.stringify(tels)})]
visites, erreurs = [], []
for l in leads[:2]:
    v, e = visites_services.planifier_visite(l, own, aujourd_hui_local(), commercial=te)
    visites.append(v.pk if v else None); erreurs.append(e)
prevue = [str(Lead.objects.get(pk=l.pk).visite_prevue_le) for l in leads[:2]]
sortie(dict(leads=[l.pk for l in leads], visites=visites, erreurs=erreurs, prevue=prevue, jour=str(aujourd_hui_local())))`)
  const etat = () => py(`from apps.crm.models import Lead
from apps.visites.models import VisiteTerrain
from apps.notifications.models import Notification
L = [Lead.all_objects.get(pk=pk) for pk in ${JSON.stringify(ids.leads)}]
V = [VisiteTerrain.objects.get(pk=pk) for pk in ${JSON.stringify(ids.visites)}]
sortie(dict(
  visites=[[v.statut, v.date_prevue, 'annulé — le lead est supprimé.' in (v.notes or '')] for v in V],
  annulee=VisiteTerrain.Statut.ANNULEE,
  prevue=[l.visite_prevue_le for l in L], supprime=[l.is_deleted for l in L],
  notes=[l.activites.filter(body__startswith='Rendez-vous de visite', user__isnull=True).count() for l in L],
  texte=[x.body for x in L[0].activites.filter(body__startswith='Rendez-vous de visite', user__isnull=True)],
  prevenu=Notification.objects.filter(recipient_id=${terrainId}, title='Visite technique annulée').count()))`)
  let terrainNav = null
  try {
    expect(ids.erreurs, 'visites planifiées sans erreur').toEqual([{}, {}])
    expect(ids.prevue, 'visite_prevue_le posé à aujourd\'hui').toEqual([ids.jour, ids.jour])
    // À l'écran AVANT : le terrain voit ses deux visites du jour dans « Ma journée ».
    terrainNav = await navigateurSous(page, suivi, testInfo, terrain)
    const tp = terrainNav.page
    await tp.goto('/visites')
    await expect(tp.getByRole('heading', { name: 'Ma journée' })).toBeVisible({ timeout: 60_000 })
    for (const n of noms.slice(0, 2)) await expect(tp.getByText(n, { exact: true }), `avant : « ${n} » dans Ma journée`).toBeVisible({ timeout: 60_000 })
    // Geste 1 : le Directeur supprime le premier lead (vraie route du bouton Supprimer de la liste).
    const d1 = await di.ctx.delete(`${API}/crm/leads/${ids.leads[0]}/`, T)
    expect(d1.status(), `suppression unitaire : ${(await d1.text()).slice(0, 200)}`).toBeLessThan(300)
    // Geste 2 : action en masse « delete » sur le second lead (visite) et le troisième (sans visite).
    const d2 = await di.ctx.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'delete', ids: [ids.leads[1], ids.leads[2]] } })
    expect(d2.status(), `suppression en masse : ${(await d2.text()).slice(0, 200)}`).toBe(200)
    const apres = await etat()
    expect(apres.supprime, 'les trois leads sont en corbeille').toEqual([true, true, true])
    for (const v of apres.visites) expect(v, 'visite annulée par le module Visites (statut, date vidée, note « le lead est supprimé »)').toEqual([apres.annulee, null, true])
    expect(apres.prevue, 'visite_prevue_le vidé (le 3e n\'en avait pas)').toEqual([null, null, null])
    expect(apres.notes, 'UNE note système « Rendez-vous de visite … annulé » par lead à visite ; aucune sans visite').toEqual([1, 1, 0])
    expect(apres.texte[0], 'texte de la note').toContain('annulé (le technicien est prévenu) : le lead est supprimé.')
    expect(apres.prevenu, 'le terrain est prévenu deux fois').toBe(2)
    // À l'écran APRÈS (persistance : page rechargée) : les visites ont disparu du planning du terrain.
    await tp.reload()
    await expect(tp.getByRole('heading', { name: 'Ma journée' })).toBeVisible({ timeout: 60_000 })
    await expect(tp.getByText('Aucune visite aujourd’hui'), 'Ma journée vide').toBeVisible({ timeout: 60_000 })
    for (const n of noms) await expect(tp.getByText(n, { exact: true }), `après : « ${n} » absent`).toHaveCount(0)
    // Restaurer le premier lead (corbeille commune) : la visite reste annulée.
    const entree = await py(`from django.contrib.contenttypes.models import ContentType
from apps.trash.models import ElementSupprime
from apps.crm.models import Lead
e = ElementSupprime.objects.filter(content_type=ContentType.objects.get_for_model(Lead), object_id=${ids.leads[0]}).order_by('-pk').first()
sortie(e.pk if e else None)`)
    expect(entree, 'entrée de corbeille du lead supprimé').toBeTruthy()
    const rr = await page.request.post(`${API}/trash/corbeille/${entree}/restaurer/`, T)
    expect(rr.status(), `restaurer : ${(await rr.text()).slice(0, 200)}`).toBe(200)
    const fin = await etat()
    expect(fin.supprime[0], 'lead restauré').toBe(false)
    expect(fin.visites[0], 'restauré ⇒ la visite reste annulée').toEqual([fin.annulee, null, true])
    expect(fin.prevue[0], 'restauré ⇒ aucune date de visite replantée').toBeNull()
    await tp.reload()
    await expect(tp.getByRole('heading', { name: 'Ma journée' })).toBeVisible({ timeout: 60_000 })
    await expect(tp.getByText(noms[0], { exact: true }), 'après restauration : toujours absent du planning').toHaveCount(0)
    // Capture de l'étape : le planning du terrain, vide (la page du terrain est la première capturée si on
    // ferme celle de l'admin, restée vierge).
    // L'écart déclaré plus bas ne couvre QUE le 403 de la coquille sur /stock/produits/?page_size=1 : tout autre
    // incident d'oracle fait tomber le corps de l'étape.
    const autres = suivi.incidents.filter((i) => !(/\/api\/django\/stock\/produits\/\?page_size=1\b/.test(i.texte) && /403/.test(i.texte)))
    expect(autres, 'aucun incident d\'oracle hors du 403 connu de la coquille').toEqual([])
    await page.close()
  } finally {
    await di.ctx.dispose()
    // Le contexte du terrain reste ouvert jusqu'à la fin du worker : sa page porte la capture de l'étape.
    void terrainNav
    await py(`from apps.crm.models import Lead
from apps.visites.models import VisiteTerrain
VisiteTerrain.objects.filter(lead_id__in=${JSON.stringify(ids.leads)}).delete()
for pk in ${JSON.stringify(ids.leads)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
  }
}, {
  // Run runner 43507923128 (13/11) : corps de l'étape VERT (toutes les assertions d'ASUP44 passées), seuls les
  // oracles 2/3 tombent — à CHAQUE chargement de page du compte « Commercial terrain », la coquille
  // (components/layout/Sidebar.jsx → features/onboarding/onboardingHelpers.js::lireComptesOnboarding) lit
  // `GET /stock/produits/?page_size=1` sans droit stock ⇒ 403 + console.error. Défaut antérieur et hors
  // d'ASUP44 (jumeau non traité d'ERR-SHELL-USERS-403-COMMERCIAL, qui n'a borné que /users/) ; il échoue à la
  // base de la même façon. Assertions du corps intactes.
  ecart: {
    base: 'FAIL',
    raison: 'coquille du compte Commercial terrain : GET /stock/produits/?page_size=1 → 403 à chaque page '
      + '(onboardingHelpers.js::lireComptesOnboarding, appelé par Sidebar.jsx ; jumeau d\'ERR-SHELL-USERS-403-COMMERCIAL), '
      + 'défaut antérieur hors ASUP44, à classer chez le propriétaire du shell frontend',
  },
})

// ─────────────────────────────────────────────────────────────────────────────
// ASUP49 — le client signe par son lien public le devis d'un lead ARCHIVÉ : le lead est désarchivé (une entrée
// de chatter) et réapparaît « Signé » dans la liste des leads ; lead non archivé : aucune entrée ; second
// `devis_accepted` sans changement de statut : rien.
const colonne = (page, cle) => page.getByRole('region', { name: new RegExp(`^Étape ${STAGE_LABELS[cle]} — \\d+ leads?$`) })
async function chercherLead(page, nom) {
  await page.goto('/crm/leads')
  await setLeadsView(page, 'kanban')
  await page.getByPlaceholder('Rechercher nom, téléphone, email…').fill(nom)
}
async function devisEnvoye(r, nom, m) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, {
    ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `asup49${m}${nom.length}@example.invalid`, type_installation: 'residentiel', facture_hiver: '1500' },
  }), 'lead')
  // Nom de produit propre à CE lead (deux devis par étape : un nom partagé rend 409 « produit actif de ce nom »).
  const prod = async (n, pv) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `${n} ${nom}`, prix_vente: pv, prix_achat: '111.11' } }), 'produit')
  const pan = await prod('Panneau mono 550W ASUP49', '1000.00')
  const ond = await prod('Onduleur réseau 10kW ASUP49', '10000.00')
  const ligne = (p, q, ordre) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: p.prix_vente, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre })
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligne(pan, 12, 0), ligne(ond, 1, 1)] },
  }), 'devis')
  const lien = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  return { lead, d, lien, produits: [pan.id, ond.id] }
}
async function signerParLeLien(testInfo, jeton, nom) {
  const client = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] } })
  try {
    const pub = await lireJson(await client.get(`${API}/public/proposal/${jeton}/data/`, T), 'charge publique')
    const s = await client.post(`${API}/public/proposal/${jeton}/accept/`, {
      ...T, data: { nom, consent_esign: true, accepte_conditions: true, empreinte_contenu: pub.empreinte_contenu },
    })
    return { status: s.status(), texte: (await s.text()).slice(0, 300) }
  } finally { await client.dispose() }
}

etape('PF10.3-ASUP49', ['ASUP49'], async ({ page, testInfo }) => {
  sondeRejouee('C-ASUP-023')
  const r = page.request
  const m = marque()
  const crees = []
  try {
    const a = await devisEnvoye(r, `ASUP49 archive ${m}`, m); crees.push(a)
    const t = await devisEnvoye(r, `ASUP49 temoin ${m}`, m); crees.push(t)
    // Le commercial archive le lead dont le devis est envoyé (route « Archiver » de la fiche).
    const ar = await r.post(`${API}/crm/leads/${a.lead.id}/archiver/`, { ...T, data: {} })
    expect(ar.status(), `archiver : ${(await ar.text()).slice(0, 200)}`).toBe(200)
    expect((await lireJson(await r.get(`${API}/crm/leads/${a.lead.id}/`, T), 'lead relu')).is_archived, 'lead archivé').toBe(true)
    // À l'écran AVANT : le lead archivé est caché de la liste par défaut.
    await chercherLead(page, a.lead.nom)
    await expect(page.getByRole('region', { name: /^Étape / }).first()).toBeVisible({ timeout: 60_000 })
    await expect(page.locator('article.kb-card', { hasText: a.lead.nom }), 'avant : lead archivé absent de la liste').toHaveCount(0)
    // Le client signe par le lien public (événement devis_accepted), pour les deux devis.
    const sa = await signerParLeLien(testInfo, a.lien.token, 'Client ASUP49')
    expect(sa.status, `signature (lead archivé) : ${sa.texte}`).toBe(200)
    const st = await signerParLeLien(testInfo, t.lien.token, 'Client ASUP49 temoin')
    expect(st.status, `signature (témoin) : ${st.texte}`).toBe(200)
    const lu = await py(`from apps.crm import stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.portee_selectors import est_lead_signe
from apps.ventes.models import Devis
def vue(pk, ref):
    l = Lead.all_objects.get(pk=pk)
    return dict(archive=l.is_archived, par=l.archived_by_id, le=l.archived_at, signe=l.stage == stages.SIGNED, est_signe=est_lead_signe(l),
                entrees=LeadActivity.objects.filter(lead_id=pk, body='désarchivé : devis signé %s' % ref).count(),
                toutes=LeadActivity.objects.filter(lead_id=pk, body__startswith='désarchivé').count(),
                statut=Devis.objects.get(reference=ref).statut)
sortie(dict(a=vue(${a.lead.id}, ${JSON.stringify(a.d.reference)}), t=vue(${t.lead.id}, ${JSON.stringify(t.d.reference)})))`)
    expect(lu.a.statut, 'devis accepté').toBe('accepte')
    expect([lu.a.archive, lu.a.par, lu.a.le], 'lead : is_archived faux, archived_by et archived_at vides').toEqual([false, null, null])
    expect([lu.a.signe, lu.a.est_signe], 'lead : étape Signé et est_lead_signe vrai').toEqual([true, true])
    expect(lu.a.entrees, 'UNE entrée « désarchivé : devis signé <référence> »').toBe(1)
    expect([lu.t.archive, lu.t.signe, lu.t.toutes], 'lead non archivé : signé, aucune entrée « désarchivé »').toEqual([false, true, 0])
    // Second devis_accepted sans changement de statut (rejoué sur le récepteur, transaction ANNULÉE) : rien.
    const second = await py(`from django.db import transaction
from apps.crm.models import Lead, LeadActivity
from apps.crm.receivers import _avancer_stage_on_devis_accepted
from apps.ventes.models import Devis
r = {}
with transaction.atomic():
    Lead.all_objects.filter(pk=${a.lead.id}).update(is_archived=True)
    d = Devis.objects.select_related('lead').get(pk=${a.d.id})
    _avancer_stage_on_devis_accepted(None, d, None, d.statut)
    r = dict(archive=Lead.all_objects.get(pk=${a.lead.id}).is_archived, entrees=LeadActivity.objects.filter(lead_id=${a.lead.id}, body__startswith='désarchivé').count())
    transaction.set_rollback(True)
sortie(r)`)
    expect(second, 'second devis_accepted sans transition : ni désarchivage ni entrée').toEqual({ archive: true, entrees: 1 })
    // À l'écran APRÈS (persistance : page rechargée) : le lead réapparaît dans la colonne « Signé ».
    await chercherLead(page, a.lead.nom)
    await expect(colonne(page, 'SIGNED').getByText(a.lead.nom), 'après : lead visible dans « Signé »').toBeVisible({ timeout: 60_000 })
  } finally {
    const leads = crees.map((x) => x.lead.id)
    const devis = crees.map((x) => x.d.id)
    const produits = crees.flatMap((x) => x.produits)
    await py(`from apps.crm.models import Lead
from apps.ventes.models import Devis
from apps.stock.models import Produit
for d in Devis.objects.filter(pk__in=${JSON.stringify(devis)}):
    try: d.delete()
    except Exception as exc:
        Devis.objects.filter(pk=d.pk).update(is_active=False); print('devis archivé', d.pk, exc)
for pk in ${JSON.stringify(leads)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)
for pk in ${JSON.stringify(produits)}:
    try: Produit.objects.filter(pk=pk).delete()
    except Exception as exc: print('produit', pk, exc)`).catch(() => null)
  }
})

// ─────────────────────────────────────────────────────────────────────────────
// ASUP47 — chantier en pénurie, F1 archivé (1 200) moins cher que F2 actif (1 350) : F2 est proposé (écran
// « Matériel & BC »), « Commander les manques » crée le brouillon chez F2 ; un BCF explicite chez F1 rend 409
// nommé, rien écrit.
etape('PF10.2-ASUP47', ['ASUP47'], async ({ page, suivi }) => {
  sondeRejouee('C-ASUP-021')
  const m = marque()
  const ids = await py(`from decimal import Decimal
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit, Fournisseur, PrixFournisseur
from apps.stock.services import cheapest_prix_fournisseur
from apps.ventes.models import Devis, LigneDevis
CO = ${SOC}
p = Produit.objects.create(company_id=CO, nom='Onduleur ASUP47 ${m}', sku='ASUP47-${m}', prix_achat=Decimal('1000'), prix_vente=Decimal('2000'), quantite_stock=0)
f1 = Fournisseur.objects.create(company_id=CO, nom='Solaire Nord ASUP47 ${m}', is_archived=True)
f2 = Fournisseur.objects.create(company_id=CO, nom='Atlas Appro ASUP47 ${m}')
PrixFournisseur.objects.create(company_id=CO, produit=p, fournisseur=f1, prix_achat=Decimal('1200'))
PrixFournisseur.objects.create(company_id=CO, produit=p, fournisseur=f2, prix_achat=Decimal('1350'))
cl = Client.objects.create(company_id=CO, nom='ASUP47 ${m}', prenom='Client', email='asup47_${m}@asup.invalid', telephone='${telephoneMobileUnique()}')
d = Devis.objects.create(company_id=CO, reference='DEV-ASUP47-${m}', client=cl, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
LigneDevis.objects.create(devis=d, produit=p, designation=p.nom, quantite=Decimal('3'), prix_unitaire=p.prix_vente)
inst = Installation.objects.create(company_id=CO, reference='CH-ASUP47-${m}', client=cl, devis=d)
best = cheapest_prix_fournisseur(p)
sortie(dict(produit=p.pk, nom=p.nom, f1=f1.pk, f2=f2.pk, f1nom=f1.nom, f2nom=f2.nom, client=cl.pk, devis=d.pk, inst=inst.pk,
            moins_cher=[best.fournisseur_id, str(best.prix_achat)] if best else None))`)
  const bcfs = () => py(`from apps.stock.models import BonCommandeFournisseur
sortie({str(f): list(BonCommandeFournisseur.objects.filter(fournisseur_id=f).values_list('statut', flat=True)) for f in (${ids.f1}, ${ids.f2})})`)
  try {
    expect(ids.moins_cher, 'cheapest_prix_fournisseur : F2 (1 350), jamais F1 archivé').toEqual([ids.f2, '1350.00'])
    // À l'écran : chantier, onglet « Matériel & BC » — le fournisseur proposé de la ligne en manque est F2.
    await page.goto(`/chantiers?id=${ids.inst}`)
    await page.getByRole('tab', { name: /Matériel/ }).click({ timeout: 60_000 })
    const ligne = page.locator('tr', { hasText: ids.nom }).first()
    await expect(ligne, 'ligne du besoin matériel').toBeVisible({ timeout: 60_000 })
    await expect(ligne, 'fournisseur proposé : F2 (actif)').toContainText(ids.f2nom)
    await expect(page.getByText(ids.f1nom), 'F1 (archivé) jamais proposé').toHaveCount(0)
    // « Commander les manques » (vraie route commander-besoin, par le bouton de l'écran).
    const rep = page.waitForResponse((x) => /\/commander-besoin\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'POST', T)
    await page.getByRole('button', { name: /Commander les manques/ }).click()
    const cb = await rep
    expect(cb.status(), `commander-besoin : ${(await cb.text()).slice(0, 300)}`).toBe(201)
    const corps = await cb.json()
    expect(corps.bons_commande.map((b) => b.fournisseur), 'brouillon créé chez F2').toEqual([ids.f2])
    await expect(page.getByRole('status').filter({ hasText: 'bon de commande créé' }), 'écran : brouillon créé chez F2').toContainText(ids.f2nom, { timeout: 60_000 })
    // BCF explicite chez F1 (porte de création des BCF) : 409 nommé, rien écrit.
    suivi.attendre(/\/stock\/bons-commande-fournisseur\/$/, 409)
    const explicite = await page.request.post(`${API}/stock/bons-commande-fournisseur/`, {
      ...T, data: { fournisseur: ids.f1, lignes: [{ produit: ids.produit, quantite: 5, prix_achat_unitaire: '1200' }] },
    })
    const ce = await explicite.text()
    expect(explicite.status(), `BCF chez F1 : ${ce.slice(0, 300)}`).toBe(409)
    expect(ce, 'motif nommé').toContain('archivé : désarchivez-le pour lui commander')
    // Persistance : relire les BCF ⇒ aucun chez F1, un brouillon chez F2 ; écran rechargé : le BCF du chantier est chez F2.
    const lus = await bcfs()
    expect(lus[String(ids.f1)], 'aucun BCF chez F1').toEqual([])
    expect(lus[String(ids.f2)].length, 'un BCF chez F2').toBe(1)
    // Run 43509139251 : un reload lancé PENDANT le rafraîchissement de la fiche (statut avancé par la commande,
    // `refreshInstallation` → resynchro du formulaire) a croisé le garde « modifications non enregistrées »
    // (beforeunload). On attend que la fiche ait fini de se recharger (réseau au repos) avant de recharger ;
    // si le dialogue revient malgré tout, l'oracle 4 le compte (aucun champ n'a été saisi).
    await page.waitForLoadState('networkidle', T)
    await page.reload()
    await page.getByRole('tab', { name: /Matériel/ }).click({ timeout: 60_000 })
    const blocBcf = page.locator('tr', { hasText: corps.bons_commande[0].reference })
    await expect(blocBcf.first(), 'BCF du chantier listé chez F2').toContainText(ids.f2nom, { timeout: 60_000 })
    await expect(page.getByText(ids.f1nom), 'F1 absent après rechargement').toHaveCount(0)
  } finally {
    await py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit, Fournisseur, PrixFournisseur, BonCommandeFournisseur
from apps.ventes.models import Devis, LigneDevis
def tenter(f):
    try: f()
    except Exception as exc: print('nettoyage', exc)
for b in BonCommandeFournisseur.objects.filter(fournisseur_id__in=(${ids.f1}, ${ids.f2})):
    tenter(lambda: b.lignes.all().delete()); tenter(b.delete)
tenter(lambda: Installation.objects.filter(pk=${ids.inst}).delete())
tenter(lambda: LigneDevis.objects.filter(devis_id=${ids.devis}).delete())
tenter(lambda: Devis.objects.filter(pk=${ids.devis}).delete())
tenter(lambda: Client.objects.filter(pk=${ids.client}).delete())
tenter(lambda: PrixFournisseur.objects.filter(produit_id=${ids.produit}).delete())
tenter(lambda: Fournisseur.objects.filter(pk__in=(${ids.f1}, ${ids.f2})).delete())
tenter(lambda: Produit.objects.filter(pk=${ids.produit}).delete())`).catch(() => null)
  }
})

// ─────────────────────────────────────────────────────────────────────────────
// ASUP52 — la suggestion « Marque » de la barre d'actions groupées du stock n'offre aucune marque archivée ;
// la saisie libre d'une marque archivée reste possible.
etape('PF10.2-ASUP52', ['ASUP52'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const active = `Huawei ASUP52 ${m}`
  const ancienne = `Ancienne ASUP52 ${m}`
  const crees = { marques: [], produits: [] }
  try {
    for (const nom of [active, ancienne]) crees.marques.push((await lireJson(await r.post(`${API}/stock/marques/`, { ...T, data: { nom } }), `marque ${nom}`)).id)
    await lireJson(await r.patch(`${API}/stock/marques/${crees.marques[1]}/`, { ...T, data: { archived: true } }), 'marque archivée')
    const servies = listeDe(await lireJson(await r.get(`${API}/stock/marques/?page_size=500`, T), 'marques'))
    expect(servies.find((x) => x.id === crees.marques[1])?.archived, 'l\'API sert bien la marque archivée (archived: true)').toBe(true)
    for (const n of [1, 2, 3]) {
      crees.produits.push((await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Produit ASUP52 ${m} n${n}`, prix_vente: '100.00' } }), `produit ${n}`)).id)
    }
    // À l'écran : liste du stock, 2 produits cochés, panneau « Marque » de la barre groupée.
    await page.goto('/stock')
    await page.getByPlaceholder('Chercher partout…').fill(`Produit ASUP52 ${m}`)
    for (const n of [1, 2]) await page.getByRole('checkbox', { name: `Sélectionner Produit ASUP52 ${m} n${n}` }).click({ timeout: 60_000 })
    const barre = page.getByRole('region', { name: 'Actions produits en masse' })
    await expect(barre, 'barre groupée : 2 produits sélectionnés').toContainText('2 produits sélectionnés')
    await barre.getByRole('radiogroup', { name: "Panneau d'action en masse" }).getByRole('radio', { name: 'Marque' }).click()
    const champ = barre.getByPlaceholder('Marque')
    await expect(champ).toBeVisible()
    expect(await champ.getAttribute('list'), 'le champ « Marque » porte la liste de suggestions').toBe('bpb-marques')
    const options = await page.locator('#bpb-marques option').evaluateAll((os) => os.map((o) => o.value))
    expect(options, 'suggestion : la marque active est proposée').toContain(active)
    expect(options, 'suggestion : la marque archivée n\'est jamais proposée').not.toContain(ancienne)
    // Saisie libre de la marque archivée : toujours possible (action set_brand).
    await champ.fill(ancienne)
    const rep = page.waitForResponse((x) => /\/stock\/produits\/bulk/.test(x.url()) && x.request().method() === 'POST', T)
    await barre.getByRole('button', { name: 'Appliquer' }).click()
    expect((await rep).status(), 'set_brand accepté').toBeLessThan(300)
    const lus = await py(`from apps.stock.models import Produit
sortie([Produit.objects.get(pk=pk).marque for pk in ${JSON.stringify(crees.produits)}])`)
    expect(lus.slice(0, 2), 'saisie libre appliquée aux 2 produits cochés').toEqual([ancienne, ancienne])
    expect(lus[2] === ancienne, 'le 3e (non coché) inchangé').toBe(false)
  } finally {
    await py(`from apps.stock.models import Produit, Marque
for pk in ${JSON.stringify(crees.produits)}:
    try: Produit.objects.filter(pk=pk).delete()
    except Exception as exc: print('produit', pk, exc)
Marque.objects.filter(pk__in=${JSON.stringify(crees.marques)}).delete()`).catch(() => null)
  }
})
