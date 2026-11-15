// Preuves en direct ÉCRAN du groupe AERR, lot 8 (contre-visite de clôture du 14/11, 2ᵉ passe : constats
// C-AERR-VER2-200 à 224, dossier docs/audits/2026-11-14-erreurs-ecran-verifie.md) : AERR158, AERR169 (Paramètres),
// AERR173 (GED › Rétention), AERR159, AERR160, AERR170 (SAV / recette de pompage), AERR172 (Interventions),
// AERR162, AERR164 (devis), AERR161 (factures), AERR167 (leads, écriture annulable), AERR156, AERR163, AERR165,
// AERR166 (CRM). Chaque étape joue le geste À L'ÉCRAN que nomme la clause « Preuve en direct » de sa tâche, sous un
// compte d'essai d'un rôle SYSTÈME du registre (société démo, session posée par la vraie route /token/, patron
// aerr5.spec.js), provoque l'échec quand la clause le demande (route Playwright déclarée AVANT par `suivi.attendre`),
// affirme à l'écran, relit la base (shell Django) ou l'API, recharge et réaffirme. Données propres créées par le shell
// Django ou l'API et retirées en fin d'étape (base jetable du runner). Aucun envoi réel (pas de worker Celery).
import { test, expect } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { RACINE, cheminCapture } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, lireJson, listeDe, telephoneMobileUnique } from '../helpers.js'

const G = 'AERR'
const etape = groupe(G, ['AERR158', 'AERR169', 'AERR173', 'AERR159', 'AERR160', 'AERR170', 'AERR172',
  'AERR162', 'AERR164', 'AERR161', 'AERR167', 'AERR156', 'AERR163', 'AERR165', 'AERR166'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const DEMANDE = 'Quitter sans enregistrer ?' // AERR155 — boîte maison de `confirmLeaveIfDirty`
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const contextes = []
const apres = []
const comptes = []
test.afterEach(async () => {
  for (const c of contextes.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
  const noms = comptes.splice(0)
  if (noms.length) await py(`U.objects.filter(username__in=${J(noms)}).update(is_active=False)`).catch(() => undefined)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte })
const auRepos = (p) => p.waitForLoadState('networkidle').catch(() => undefined)

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société démo ; {nom, id}. Désactivé en fin d'étape. */
async function compteRole(prefixe, nomRole, { prenom = 'Essai', famille = nomRole } = {}) {
  const nom = `${prefixe}_${marque()}`
  const id = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
assert r.est_systeme, 'rôle non système'
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.first_name = ${J(prenom)}; u.last_name = ${J(famille)}; u.save(update_fields=['first_name', 'last_name'])
sortie(u.id)`)
  comptes.push(nom)
  return { nom, id }
}

/** Écran du compte `nom` : contexte neuf (accueil et visites guidées vus, SW bloqué), session par la vraie route
 *  /token/, observé par les oracles ; la page demo_admin de l'étape est refermée (la capture montre CET écran).
 *  `dem.repondre()` répond dans la boîte maison « Quitter sans enregistrer ? » ; tout dialogue natif = oracle 4. */
async function ecran(page, suivi, testInfo, nom, viewport = { width: 1600, height: 1000 }) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', viewport,
  })
  contextes.push(ctx)
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
    } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of listeDe(await visites.json())) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  const p = suivi.surveiller(await ctx.newPage())
  const boite = p.getByRole('alertdialog').filter({ hasText: DEMANDE })
  const dem = { vues: 0, prochaine: null, boite }
  dem.repondre = async () => {
    if (dem.prochaine && await boite.isVisible()) {
      await boite.getByRole('button', { name: dem.prochaine === 'quitter' ? 'Quitter' : 'Rester', exact: true }).click()
      await expect(boite, 'boîte maison refermée').toHaveCount(0)
      dem.prochaine = null
      dem.vues += 1
    }
    return dem.vues
  }
  p.removeAllListeners('dialog')
  p.on('dialog', async (d) => {
    suivi.incidents.push({ oracle: '4', texte: `dialogue natif inattendu ${d.type()} : ${d.message()}` })
    await d.dismiss().catch(() => undefined)
  })
  return { p, dem, ctx }
}

/** Panne INJECTÉE (déclarée au suivi AVANT) sur les requêtes `methode` d'URL `re` ; les autres passent. */
async function panne(p, suivi, re, { statut = 500, methode = 'GET', corps = { detail: 'Panne simulée (acceptation AERR).' } } = {}) {
  suivi.attendre(re, statut)
  const hits = { n: 0 }
  const h = async (route) => {
    if (route.request().method() !== methode) return route.fallback()
    hits.n += 1
    if (statut === 'reseau') return route.abort('failed')
    return route.fulfill({ status: statut, contentType: 'application/json', body: J(corps) })
  }
  await p.route(re, h)
  return { hits, lever: () => p.unroute(re, h) }
}

/** Requêtes `methode` d'URL `re` parties de la page. */
function compter(p, methode, re) {
  const vues = []
  p.on('request', (r) => { if (r.method() === methode && re.test(r.url())) vues.push(r.postData() || '') })
  return vues
}

/** Route tenue : chaque requête qui passe attend `lacher()`, puis `issue(route)`. */
function porte() {
  let lacher
  let signaler
  const ouverte = new Promise((r) => { lacher = r })
  const arrivee = new Promise((r) => { signaler = r })
  return {
    arrivee, lacher: () => lacher(),
    gestion: (issue) => async (route) => { signaler(); await ouverte; await issue(route) },
  }
}

/** Capture PENDANT que l'écran affirmé est visible (en plus de la capture de fin d'étape). */
async function cliche(p, id, moment) {
  const chemin = join(RACINE, cheminCapture(G, `${id}-${moment}`))
  mkdirSync(dirname(chemin), { recursive: true })
  await p.screenshot({ path: chemin, type: 'jpeg', quality: 60 })
}

// ══════════════════════════════ PARAMÈTRES — AERR158, AERR169 ══════════════════════════════

// ═══ PF12.2 — AERR158 : E-mail, Supervision et Clients gardent leur saisie après un aller-retour d'onglet ═══
etape('PF12.2-AERR158', ['AERR158'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ad = await compteRole('aerr158ad', 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, ad.nom)
  const nav = p.getByRole('navigation', { name: 'Sections des paramètres' })
  const onglet = (label) => nav.getByRole('button', { name: label, exact: true })
  const aller = async (label) => {
    await onglet(label).click()
    await expect(onglet(label), `onglet ${label} actif`).toHaveAttribute('aria-current', 'page')
  }
  const ecritures = compter(p, 'PUT', /\/api\/django\/parametres\//)
  const patchs = compter(p, 'PATCH', /\/api\/django\/(parametres|monitoring)\//)
  const posts = compter(p, 'POST', /\/api\/django\/(parametres\/email-templates|monitoring|customfields|core\/custom-fields)/)
  await p.goto('/parametres?onglet=email')
  await expect(onglet('Email')).toHaveAttribute('aria-current', 'page', { timeout: 60_000 })
  const corps = p.locator('#pe-email-corps-envoi_devis')
  await expect(corps, 'modèle « envoi_devis » affiché').toBeVisible({ timeout: 60_000 })
  const corpsServi = await corps.inputValue()
  const tape = `Bonjour {client}, voici votre devis — AERR158 ${m}`
  await corps.fill(tape)
  // Aller-retour par « Leads ».
  await aller('Leads')
  await expect(corps, 'E-mail masqué pendant Leads').toBeHidden()
  await aller('Email')
  await expect(corps, 'retour sur Email : le corps tapé est toujours là').toHaveValue(tape, { timeout: 15_000 })
  await cliche(p, 'PF12.2-AERR158', 'email')
  // Supervision : seuil modifié, aller-retour par Leads.
  await aller('Supervision')
  const seuil = p.locator('#underperf-threshold')
  await expect(seuil, 'seuil de sous-performance affiché').toBeVisible({ timeout: 60_000 })
  await expect(seuil, 'seuil modifiable (Administrateur)').toBeEditable()
  const seuilServi = await seuil.inputValue()
  const seuilTape = seuilServi === '37' ? '38' : '37'
  await seuil.fill(seuilTape)
  await aller('Leads')
  await expect(seuil).toBeHidden()
  await aller('Supervision')
  await expect(seuil, 'retour sur Supervision : seuil tapé gardé').toHaveValue(seuilTape, { timeout: 15_000 })
  // Clients : brouillon de champ personnalisé, aller-retour par Leads.
  await aller('Clients')
  const libelle = p.getByPlaceholder('Libellé du champ')
  await expect(libelle, 'brouillon de champ client').toBeVisible({ timeout: 60_000 })
  const champTape = `Champ AERR158 ${m}`
  await libelle.fill(champTape)
  await aller('Leads')
  await expect(libelle).toBeHidden()
  await aller('Clients')
  await expect(libelle, 'retour sur Clients : brouillon gardé').toHaveValue(champTape, { timeout: 15_000 })
  // Et l'e-mail tient toujours après ces trois allers-retours.
  await aller('Email')
  await expect(corps, 'Email, après Supervision et Clients : corps gardé').toHaveValue(tape)
  await auRepos(p)
  expect([ecritures.length, patchs.length, posts.length], 'rien n\'est écrit tant qu\'on n\'enregistre pas').toEqual([0, 0, 0])
  // Persistance : rien d'écrit en base ; recharger ⇒ valeurs servies.
  const servis = await lireJson(await p.request.get(`${API}/parametres/email-templates/effective/`, T), 'modèles')
  const envoi = listeDe(servis).find((t) => t.cle === 'envoi_devis')
  expect(envoi?.corps, 'base : corps servi inchangé').not.toBe(tape)
  await p.reload()
  await expect(corps, 'rechargé : corps servi').toHaveValue(corpsServi, { timeout: 60_000 })
  await aller('Supervision')
  await expect(seuil, 'rechargé : seuil servi').toHaveValue(seuilServi, { timeout: 60_000 })
  await aller('Email')
  await corps.fill(tape)
  await aller('Leads')
  await aller('Email')
  await expect(corps, 'rechargé, réaffirmé : corps tapé gardé').toHaveValue(tape)
})

// ═══ PF12.1 — AERR169 : lecture des règles de routage en 500 ⇒ UN toast (global) ; en 404 ⇒ UN toast (local) ═══
etape('PF12.1-AERR169', ['AERR169'], async ({ page, suivi, testInfo }) => {
  const ad = await compteRole('aerr169ad', 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, ad.nom)
  const REGLES = /\/api\/django\/notifications\/routing-rules\/(\?|$)/
  const toasts = p.locator('[data-sonner-toast]')
  const ouvrir = async () => {
    const lu = p.waitForResponse((x) => REGLES.test(x.url()) && x.request().method() === 'GET', T)
    await p.goto('/parametres?onglet=notifications')
    return lu
  }
  // 1) 500 : le toast global seul.
  const c500 = await panne(p, suivi, REGLES, { statut: 500, corps: { detail: 'Panne simulée AERR169 (règles).' } })
  expect((await ouvrir()).status(), 'lecture des règles rejetée 500').toBe(500)
  await expect(toasts.first(), 'un message est affiché').toBeVisible({ timeout: 30_000 })
  await p.waitForTimeout(2_500)
  await auRepos(p)
  const textes500 = await toasts.allInnerTexts()
  console.log(`[AERR169] toasts sur 500 : ${J(textes500)} ; lectures des règles : ${c500.hits.n}`)
  expect(c500.hits.n, 'au moins une lecture des règles').toBeGreaterThan(0)
  if (c500.hits.n > 1) testInfo.annotations.push({ type: 'lecture doublée', description: `${c500.hits.n} GET routing-rules au montage` })
  expect(textes500.length, `500 : un toast par lecture rejetée (${J(textes500)}, ${c500.hits.n} lecture(s))`).toBe(c500.hits.n)
  expect(textes500.every((t) => t.includes('Panne simulée AERR169')), '500 : seul le message du serveur (global)').toBe(true)
  await expect(toast(p, 'Chargement des règles impossible.'), '500 : pas de toast local en plus').toHaveCount(0)
  await cliche(p, 'PF12.1-AERR169', '500')
  await c500.lever()
  // 2) 404 : le global se tait, le toast local parle — un seul.
  const c404 = await panne(p, suivi, REGLES, { statut: 404, corps: { detail: 'Pas trouvé.' } })
  expect((await ouvrir()).status(), 'lecture des règles rejetée 404').toBe(404)
  await expect(toasts.first(), '404 : un message est affiché').toBeVisible({ timeout: 30_000 })
  await p.waitForTimeout(2_500)
  await auRepos(p)
  const textes404 = await toasts.allInnerTexts()
  console.log(`[AERR169] toasts sur 404 : ${J(textes404)} ; lectures des règles : ${c404.hits.n}`)
  expect(textes404.length, `404 : un toast par lecture rejetée (${J(textes404)}, ${c404.hits.n} lecture(s))`).toBe(c404.hits.n)
  await c404.lever()
  // Persistance (lecture) : panne levée, rechargé ⇒ aucun toast d'erreur.
  await ouvrir()
  await p.waitForTimeout(2_000)
  await auRepos(p)
  await expect(toasts.filter({ hasText: /impossible|Panne|Pas trouvé/ }), 'rechargé sans panne : aucun message d\'échec').toHaveCount(0)
  // Fin d'étape sur l'écran en panne (capture) : 500 réinjecté.
  const fin = await panne(p, suivi, REGLES, { statut: 500, corps: { detail: 'Panne simulée AERR169 (règles).' } })
  await ouvrir()
  await expect(toasts.first()).toBeVisible({ timeout: 30_000 })
  await p.waitForTimeout(2_500)
  expect(await toasts.count(), 'réaffirmé : un toast par lecture rejetée').toBe(fin.hits.n)
  await fin.lever()
})

// ══════════════════════════════ GED — AERR173 ══════════════════════════════

// ═══ PF12.4 — AERR173 : « Lever le hold » ⇒ « Lever le gel « motif » ? » ; Annuler ⇒ aucun appel, gel actif ═══
etape('PF12.4-AERR173', ['AERR173'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ad = await compteRole('aerr173ad', 'Administrateur')
  const motif = `Litige client AERR173 ${m}`
  const ids = await py(`from apps.ged.models import Cabinet, Folder, Document, LegalHold
cab = Cabinet.objects.create(company_id=${SOC}, nom='AERR173 ${m}')
fol = Folder.objects.create(company_id=${SOC}, cabinet=cab, nom='Dossier AERR173 ${m}')
doc = Document.objects.create(company_id=${SOC}, folder=fol, nom='Contrat AERR173 ${m}.pdf')
h = LegalHold.objects.create(company_id=${SOC}, document=doc, motif=${J(motif)}, place_par_id=${ad.id})
sortie(dict(cab=cab.pk, doc=doc.pk, hold=h.pk))`)
  apres.push(() => py(`from apps.ged.models import Cabinet, LegalHold
LegalHold.objects.filter(pk=${ids.hold}).update(actif=False)
try: Cabinet.objects.filter(pk=${ids.cab}).delete()
except Exception as exc: print('nettoyage', exc)`))
  const actif = () => py(`from apps.ged.models import LegalHold
sortie(LegalHold.objects.get(pk=${ids.hold}).actif)`)
  const { p } = await ecran(page, suivi, testInfo, ad.nom)
  const levees = compter(p, 'POST', new RegExp(`/api/django/ged/legal-holds/${ids.hold}/lever/$`))
  const boite = p.getByRole('alertdialog')
  const ligne = p.getByRole('row').filter({ hasText: motif })
  const ouvrir = async () => {
    await p.goto('/ged/retention')
    await p.getByRole('tab', { name: 'Legal holds' }).click({ timeout: 60_000 })
    await expect(ligne, 'gel listé').toBeVisible({ timeout: 60_000 })
    await expect(ligne, 'gel actif').toContainText('Actif')
  }
  const demander = async () => {
    await ligne.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
    await p.getByRole('menuitem', { name: 'Lever le hold' }).click()
    await expect(boite, 'confirmation nommée').toContainText(`Lever le gel « ${motif} » ?`, { timeout: 15_000 })
    await expect(boite, 'effet nommé').toContainText('Le document redevient supprimable.')
  }
  await ouvrir()
  await demander()
  await cliche(p, 'PF12.4-AERR173', 'boite')
  await boite.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(boite).toHaveCount(0)
  await p.waitForTimeout(1_000)
  expect(levees.length, 'Annuler : aucun appel de levée').toBe(0)
  expect(await actif(), 'base : gel toujours actif').toBe(true)
  await expect(ligne, 'écran : toujours « Actif »').toContainText('Actif')
  // Persistance : recharger ⇒ toujours actif ; la question revient ; fin sur la boîte nommée.
  await p.reload()
  await ouvrir()
  await demander()
  expect(levees.length, 'aucune levée').toBe(0)
})

// ══════════════════════════════ SAV — AERR159, AERR160 (ticket), AERR170 ══════════════════════════════

const ticketsDe = (m, specs, tech = null) => py(`from apps.crm.models import Client
from apps.sav.models import Ticket
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
ids = []
for s in ${J(specs)}:
    t = Ticket.objects.create(company_id=${SOC}, client=cl, reference=s['ref'], priorite=s['priorite'],
        description=s['description'], technicien_responsable_id=${tech ?? 'None'})
    ids.append(t.pk)
sortie(dict(client=cl.pk, tickets=ids))`)
const champsTicket = (pks) => py(`from apps.sav.models import Ticket
sortie([[t.priorite, t.description, t.annule] for t in (Ticket.objects.get(pk=pk) for pk in ${J(pks)})])`)
const notesTicket = (pk) => py(`from apps.sav.models import Ticket
t = Ticket.objects.get(pk=${pk})
try:
    from apps.sav.models import TicketActivity
    n = TicketActivity.objects.filter(ticket=t, kind='note').count()
except Exception:
    n = None
sortie(n)`)
const retirerTickets = (ids) => py(`from apps.crm.models import Client
from apps.sav.models import Ticket
for pk in ${J(ids.tickets)}:
    try: Ticket.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`)
async function listeTickets(p, m) {
  await p.goto('/sav')
  const recherche = p.getByPlaceholder('Rechercher (référence, client, chantier, description)…')
  await recherche.fill(`AERR Client ${m}`, { timeout: 60_000 })
  const ligne = (ref) => p.getByRole('row').filter({ hasText: ref })
  const fiche = p.locator('aside[aria-label^="Détail du ticket"]')
  const champ = {
    description: fiche.locator('label:text-is("Description") + div textarea'),
    priorite: fiche.locator('label:text-is("Priorité") + button'),
    note: fiche.getByPlaceholder('Écrire une note…'),
  }
  return { ligne, fiche, champ, recherche }
}

// ═══ PF12.2 — AERR159 : note tapée sur SAV-1 puis clic sur SAV-2 ⇒ demande ; « Rester » garde la note ═══
etape('PF12.2-AERR159', ['AERR159'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const S1 = `SAV-1159-${m}`
  const S2 = `SAV-2159-${m}`
  const ids = await ticketsDe(m, [
    { ref: S1, priorite: 'normale', description: `Onduleur ${m}` },
    { ref: S2, priorite: 'normale', description: `Câble ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const re = await compteRole('aerr159re', 'Responsable')
  const { p, dem } = await ecran(page, suivi, testInfo, re.nom)
  const notes = compter(p, 'POST', /\/api\/django\/sav\/tickets\/\d+\/(noter|notes?|note)\/$/)
  const { ligne, fiche, champ } = await listeTickets(p, m)
  await expect(ligne(S1), 'SAV-1 listé').toBeVisible({ timeout: 60_000 })
  await expect(ligne(S2), 'SAV-2 listé').toBeVisible()
  // Sans saisie : bascule directe, aucune demande.
  await ligne(S1).getByText(S1).click()
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await ligne(S2).getByText(S2).click()
  await expect(fiche, 'sans saisie : bascule directe sur SAV-2').toHaveAttribute('aria-label', `Détail du ticket ${S2}`)
  await expect(dem.boite, 'sans saisie : aucune demande').toHaveCount(0)
  // Note tapée sur SAV-1, clic sur SAV-2 : la demande d'abord.
  await ligne(S1).getByText(S1).click()
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  const texte = `Pièce remplacée sur site ${m}`
  await champ.note.fill(texte)
  dem.prochaine = 'rester'
  await ligne(S2).getByText(S2).click()
  await expect(dem.boite, 'clic sur SAV-2 : « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await cliche(p, 'PF12.2-AERR159', 'demande')
  await expect.poll(() => dem.repondre(), { message: 'clic : la demande est posée' }).toBe(1)
  await expect(fiche, 'rester : fiche SAV-1').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(champ.note, 'rester : note intacte').toHaveValue(texte)
  // Raccourci J/K : même demande.
  const ordre = await p.getByRole('row').filter({ hasText: `159-${m}` }).allInnerTexts()
  const s2Apres = ordre.findIndex((t) => t.includes(S2)) > ordre.findIndex((t) => t.includes(S1))
  await fiche.getByText('Suivi, équipement, interventions, pièces et historique du ticket.').click()
  dem.prochaine = 'rester'
  await p.keyboard.press(s2Apres ? 'j' : 'k')
  await expect.poll(() => dem.repondre(), { message: 'touche J/K : la demande est posée' }).toBe(2)
  await expect(fiche, 'rester (clavier) : fiche SAV-1').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(champ.note, 'rester (clavier) : note intacte').toHaveValue(texte)
  // « Quitter » : SAV-2 s'ouvre, la note n'est écrite nulle part.
  dem.prochaine = 'quitter'
  await ligne(S2).getByText(S2).click()
  await expect.poll(() => dem.repondre()).toBe(3)
  await expect(fiche, 'quitter : fiche SAV-2').toHaveAttribute('aria-label', `Détail du ticket ${S2}`)
  expect(notes.length, 'aucune note envoyée').toBe(0)
  const n1 = await notesTicket(ids.tickets[0])
  if (n1 !== null) expect(n1, 'base : aucune note sur SAV-1').toBe(0)
  // Rechargé : réaffirmé (note tapée ⇒ demande au changement), fin sur la demande.
  await p.reload()
  const l2 = await listeTickets(p, m)
  await l2.ligne(S1).getByText(S1).click({ timeout: 60_000 })
  await expect(l2.fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(l2.champ.note, 'rechargé : champ note vide').toHaveValue('')
  await l2.champ.note.fill(texte)
  await l2.ligne(S2).getByText(S2).click()
  await expect(dem.boite, 'rechargé : la demande revient').toBeVisible({ timeout: 15_000 })
})

// ═══ PF12.2 — AERR160 (ticket) : priorité modifiée puis « Fermer » ⇒ demande ; « Rester » garde la priorité ═══
etape('PF12.2-AERR160-ticket', ['AERR160'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const S1 = `SAV-1160-${m}`
  const te = await compteRole('aerr160te', 'Technicien')
  const ids = await ticketsDe(m, [{ ref: S1, priorite: 'normale', description: `Onduleur ${m}` }], te.id)
  apres.push(() => retirerTickets(ids))
  const { p, dem } = await ecran(page, suivi, testInfo, te.nom)
  const patchs = compter(p, 'PATCH', /\/api\/django\/sav\/tickets\/\d+\/$/)
  const { ligne, fiche, champ } = await listeTickets(p, m)
  const fermer = () => fiche.getByRole('button', { name: 'Fermer', exact: true }).click()
  await ligne(S1).getByText(S1).click({ timeout: 60_000 })
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  // Sans saisie : « Fermer » ferme directement.
  await fermer()
  await expect(fiche, 'sans saisie : fiche fermée').toHaveCount(0)
  await expect(dem.boite, 'sans saisie : aucune demande').toHaveCount(0)
  // Priorité modifiée puis « Fermer » : la demande ; « Rester » garde la priorité.
  await ligne(S1).getByText(S1).click()
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await champ.priorite.click()
  await p.getByRole('option', { name: 'Urgente', exact: true }).click()
  await expect(champ.priorite, 'priorité choisie : Urgente').toContainText('Urgente')
  dem.prochaine = 'rester'
  await fermer()
  await expect(dem.boite, '« Fermer » : « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await cliche(p, 'PF12.2-AERR160-ticket', 'demande')
  await expect.poll(() => dem.repondre(), { message: '« Fermer » : la demande est posée' }).toBe(1)
  await expect(fiche, 'rester : fiche ouverte').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(champ.priorite, 'rester : priorité gardée').toContainText('Urgente')
  // « Quitter » : la fiche se ferme, rien n'est écrit.
  dem.prochaine = 'quitter'
  await fermer()
  await expect.poll(() => dem.repondre()).toBe(2)
  await expect(fiche, 'quitter : fiche fermée').toHaveCount(0)
  expect(patchs.length, 'aucun PATCH').toBe(0)
  expect(await champsTicket(ids.tickets), 'base : priorité inchangée').toEqual([['normale', `Onduleur ${m}`, false]])
  await p.reload()
  const l2 = await listeTickets(p, m)
  await l2.ligne(S1).getByText(S1).click({ timeout: 60_000 })
  await expect(l2.champ.priorite, 'rechargé : priorité servie').toContainText('Normale')
  await l2.champ.priorite.click()
  await p.getByRole('option', { name: 'Urgente', exact: true }).click()
  await l2.fiche.getByRole('button', { name: 'Fermer', exact: true }).click()
  await expect(dem.boite, 'rechargé : la demande revient').toBeVisible({ timeout: 15_000 })
})

// ═══ PF12.4 — AERR170 : Entrée sur un bouton focalisé n'ouvre aucun ticket ; J sous « Annuler ce ticket ? » ═══
// L'écran /sav n'a pas de bouton « Nouveau ticket » (la création passe par la palette) : la clause est jouée sur le
// premier bouton atteint au clavier, la puce de statut « Nouveau » (Entrée ⇒ ce bouton agit : le filtre s'applique).
etape('PF12.4-AERR170', ['AERR170'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const S1 = `SAV-1170-${m}`
  const S2 = `SAV-2170-${m}`
  const ids = await ticketsDe(m, [
    { ref: S1, priorite: 'normale', description: `Onduleur ${m}` },
    { ref: S2, priorite: 'normale', description: `Câble ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const re = await compteRole('aerr170re', 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, re.nom)
  const jouer = async (passe) => {
    const { ligne, fiche, recherche } = await listeTickets(p, m)
    await expect(ligne(S1), `${passe}SAV-1 listé`).toBeVisible({ timeout: 60_000 })
    await expect(ligne(S2)).toBeVisible()
    const puce = p.locator('button').filter({ hasText: /^\s*Nouveau\s*\d+\s*$/ }).first()
    await expect(puce, `${passe}puce de statut « Nouveau »`).toBeVisible()
    await expect(puce).not.toHaveClass(/border-primary/)
    // Tab (arrière) depuis la recherche jusqu'à la puce.
    await recherche.focus()
    const h = await puce.elementHandle()
    let atteint = false
    for (let i = 0; i < 25 && !atteint; i += 1) {
      await p.keyboard.press('Shift+Tab')
      atteint = await p.evaluate((el) => document.activeElement === el, h)
    }
    expect(atteint, `${passe}la puce est atteinte au clavier`).toBe(true)
    await p.keyboard.press('Enter')
    await expect(puce, `${passe}Entrée : le bouton focalisé agit (filtre « Nouveau »)`).toHaveClass(/border-primary/, { timeout: 15_000 })
    await p.waitForTimeout(800)
    await expect(fiche, `${passe}Entrée : aucun ticket ouvert`).toHaveCount(0)
    if (!passe) await cliche(p, 'PF12.4-AERR170', 'entree')
    // J sous « Annuler ce ticket ? » : même ticket.
    await ligne(S1).getByText(S1).click()
    await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
    await fiche.getByRole('button', { name: 'Annuler le ticket' }).click()
    const boite = p.getByRole('alertdialog')
    await expect(boite, `${passe}« Annuler ce ticket ? »`).toContainText('Annuler ce ticket ?')
    await p.keyboard.press('j')
    await p.keyboard.press('J')
    await p.waitForTimeout(500)
    await expect(fiche, `${passe}J sous la boîte : même ticket`).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
    await expect(boite, `${passe}la boîte reste ouverte`).toBeVisible()
    return boite
  }
  const boite = await jouer('')
  await p.keyboard.press('Escape')
  await expect(boite).toHaveCount(0)
  expect(await champsTicket(ids.tickets), 'base : aucun ticket annulé').toEqual([
    ['normale', `Onduleur ${m}`, false], ['normale', `Câble ${m}`, false],
  ])
  await p.reload()
  await jouer('rechargé : ')
})

// ══════════════════════════════ CHANTIERS — AERR160 (recette), AERR172 ══════════════════════════════

const chantierDe = (m, prefixe, { agricole = false, tech = null, interventions = [] } = {}) => py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.models_intervention import Intervention
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
i = Installation.objects.create(company_id=${SOC}, reference=${J(`${prefixe}-${m}`)}, client=cl${agricole ? ", type_installation='agricole'" : ''}${tech ? `, technicien_responsable_id=${tech}` : ''})
ivs = []
for s in ${J(interventions)}:
    iv = Intervention.objects.create(company_id=${SOC}, installation=i, type_intervention='depannage', statut=s['statut'])
    ivs.append(iv.pk)
sortie(dict(client=cl.pk, inst=i.pk, ivs=ivs))`)
const retirerChantier = (ids) => py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.models_intervention import Intervention
for pk in ${J(ids.ivs || [])}:
    try: Intervention.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage intervention', pk, exc)
try: Installation.objects.filter(pk=${ids.inst}).delete()
except Exception as exc: print('nettoyage chantier', exc)
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`)

// ═══ PF12.2 — AERR160 (recette) : débit saisi puis « Fermer » ⇒ demande ; « Rester » garde le débit ═══
etape('PF12.2-AERR160-recette', ['AERR160'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const te = await compteRole('aerr160rp', 'Technicien')
  const ids = await chantierDe(m, 'AERR160', { agricole: true, tech: te.id })
  apres.push(() => retirerChantier(ids))
  const r = page.request
  const ouverte = await r.post(`${API}/installations/chantiers/${ids.inst}/recette-pompage/`, { ...T, data: {} })
  expect(ouverte.status(), `fiche de recette ouverte : ${(await ouverte.text()).slice(0, 200)}`).toBeLessThan(300)
  const { p, dem } = await ecran(page, suivi, testInfo, te.nom)
  const ecritures = compter(p, 'PATCH', /\/recette-pompage\//)
  const recette = p.getByRole('dialog', { name: 'Recette de pompage (IEC 62253)' })
  const debit = recette.locator('#recette-pompage-debit_mesure_m3h')
  // Le bouton « Fermer » du PIED (la croix d'en-tête porte aussi le nom « Fermer », par aria-label).
  const fermer = () => recette.locator('button:not([aria-label])').filter({ hasText: /^\s*Fermer\s*$/ }).click()
  const ouvrir = async () => {
    await p.goto(`/chantiers?id=${ids.inst}`)
    await p.getByRole('tab', { name: /Jalons/ }).click({ timeout: 60_000 })
    await expect(p.getByTestId('ch6-recette')).toBeVisible({ timeout: 30_000 })
    await p.getByRole('button', { name: /fiche de recette/ }).first().click()
    await expect(recette).toBeVisible({ timeout: 30_000 })
    await expect(debit).toBeVisible()
  }
  await ouvrir()
  await fermer()
  await expect(recette, 'sans saisie : « Fermer » ferme directement').toBeHidden()
  await expect(dem.boite, 'sans saisie : aucune demande').toHaveCount(0)
  await ouvrir()
  await debit.fill('12')
  dem.prochaine = 'rester'
  await fermer()
  await expect(dem.boite, '« Fermer » : « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await cliche(p, 'PF12.2-AERR160-recette', 'demande')
  await expect.poll(() => dem.repondre(), { message: '« Fermer » : la demande est posée' }).toBe(1)
  await expect(recette, 'rester : fiche ouverte').toBeVisible()
  await expect(debit, 'rester : débit 12 gardé').toHaveValue('12')
  dem.prochaine = 'quitter'
  await fermer()
  await expect.poll(() => dem.repondre()).toBe(2)
  await expect(recette, 'quitter : fiche fermée').toBeHidden()
  expect(ecritures.length, 'aucune écriture de recette').toBe(0)
  const lue = await (await r.get(`${API}/installations/chantiers/${ids.inst}/recette-pompage/`, T)).json()
  expect(lue.record?.debit_mesure_m3h ?? null, 'base : aucune mesure enregistrée').toBeNull()
  await p.reload()
  await ouvrir()
  await expect(debit, 'rechargé : mesure non enregistrée').toHaveValue('')
  await debit.fill('12')
  await fermer()
  await expect(dem.boite, 'rechargé : la demande revient').toBeVisible({ timeout: 15_000 })
})

// ═══ PF12.4 — AERR172 : fiche intervention, « Terminée » / « Validée » ⇒ boîte nommée ; Annuler n'envoie rien ═══
etape('PF12.4-AERR172', ['AERR172'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await chantierDe(m, 'AERR172', { interventions: [{ statut: 'sur_site' }] })
  apres.push(() => retirerChantier(ids))
  const [iv] = ids.ivs
  const r = page.request
  const lire = async () => lireJson(await r.get(`${API}/installations/interventions/${iv}/`, T), 'intervention relue')
  const iv0 = await lire()
  const nomI = iv0.reference ?? iv0.installation_reference ?? `#${iv}`
  expect(iv0.statut, 'Given : « Sur site »').toBe('sur_site')
  const re = await compteRole('aerr172re', 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, re.nom, { width: 1920, height: 1080 })
  const patchs = compter(p, 'PATCH', new RegExp(`/api/django/installations/interventions/${iv}/$`))
  const boite = p.getByRole('alertdialog')
  const fiche = p.getByRole('dialog').filter({ hasText: `AERR172-${m}` })
  const statut = fiche.getByRole('combobox', { name: 'Statut', exact: true })
  const ouvrir = async () => {
    await p.goto(`/interventions?installation=${ids.inst}`)
    const carte = p.locator('.kb-drag-wrap').first()
    await expect(carte, 'intervention affichée').toBeVisible({ timeout: 60_000 })
    await carte.click()
    await expect(statut, 'fiche ouverte, sélecteur de statut').toBeVisible({ timeout: 30_000 })
    await expect(statut).toContainText('Sur site')
  }
  const choisir = async (label) => {
    await statut.click()
    await p.getByRole('option', { name: label, exact: true }).click()
    await expect(boite, `« ${label} » : boîte nommée`).toContainText(`Passer ${nomI} à « ${label} » ?`, { timeout: 15_000 })
    await expect(boite, 'effet nommé').toContainText('le ticket SAV lié sera résolu')
  }
  await ouvrir()
  for (const label of ['Terminée', 'Validée']) {
    await choisir(label)
    if (label === 'Terminée') await cliche(p, 'PF12.4-AERR172', 'terminee')
    await boite.getByRole('button', { name: 'Annuler', exact: true }).click()
    await expect(boite).toHaveCount(0)
    await p.waitForTimeout(800)
    expect(patchs.length, `${label} + Annuler : aucun PATCH`).toBe(0)
    await expect(statut, `${label} + Annuler : toujours « Sur site »`).toContainText('Sur site')
  }
  expect((await lire()).statut, 'base : toujours « sur_site »').toBe('sur_site')
  await p.reload()
  await ouvrir()
  await choisir('Terminée')
  expect(patchs.length, 'rechargé : aucun PATCH avant réponse').toBe(0)
})

// ══════════════════════════════ VENTES — AERR162, AERR164, AERR161 ══════════════════════════════

const LEAD_CI = {
  type_installation: 'commercial', categorie_commerciale: 'bureau', tension_raccordement: 'bt', raccordement: 'triphase',
  type_toiture: 'bac_acier', conso_mensuelle_kwh: '10000', contrat_electricite: 'bt_patente',
}
/** Lead + produit + devis (porté par `cree`) ; `envoye` ⇒ lien client émis (vraie route share-link). */
async function devisDe(cree, admin, m, { ci = false, envoye = false, ht = '10000.00' } = {}) {
  const l = await lireJson(await cree.post(`${API}/crm/leads/`, { ...T, data: {
    nom: `AERR ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `aerr-${m}@example.invalid`, ...(ci ? LEAD_CI : {}),
  } }), 'lead')
  const pr = await lireJson(await admin.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation AERR ${m}`, prix_vente: ht, prix_achat: '1.00' } }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, { ...T, data: {
    taux_tva: '20.00', remise_globale: '0', lead: l.id, ...(ci ? { mode_installation: 'commercial' } : {}),
    lignes: [{ produit: pr.id, designation: pr.nom, quantite: '1', prix_unitaire: ht, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
  } }), 'devis')
  if (envoye) await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const relu = await lireJson(await cree.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  return { id: d.id, reference: relu.reference, statut: relu.statut, leadId: l.id }
}

// ═══ PF12.2 — AERR162 : acceptation refusée 409 date future, 500, coupure ⇒ modale rouverte, saisie gardée ═══
etape('PF12.2-AERR162', ['AERR162'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const co = await compteRole('aerr162co', 'Commercial')
  const { p } = await ecran(page, suivi, testInfo, co.nom)
  const d = await devisDe(p.request, admin, `${m}ci`, { ci: true, envoye: true })
  expect(d.statut, 'Given : devis C&I envoyé').toBe('envoye')
  const ACCEPTER = new RegExp(`/api/django/ventes/devis/${d.id}/accepter/$`)
  const ligne = p.locator(`#devis-row-${d.id}`)
  const acc = p.getByRole('dialog').filter({ hasText: `Accepter le devis — ${d.reference}` })
  const ICE = '001525487000088'
  const MSG_DATE = 'La date ne peut pas être future.'
  const remplir = async () => {
    await ligne.getByRole('button', { name: 'Accepter', exact: true }).click()
    await expect(acc).toBeVisible()
    await expect(acc.getByTestId('identite-entreprise'), 'bloc entreprise d\'un C&I').toBeVisible()
    await acc.locator('#accept-nom').fill('M. Alami')
    await acc.locator('#accept-raison-sociale').fill(`Boulangerie AERR ${m}`)
    await acc.locator('#accept-qualite').fill('Gérant')
    await acc.locator('#accept-ice').fill(ICE)
    return acc.locator('#accept-date').inputValue()
  }
  const garde = async (date, quand) => {
    await expect(acc, `${quand} : modale du MÊME devis rouverte`).toBeVisible({ timeout: 30_000 })
    await expect(acc.locator('#accept-nom'), `${quand} : nom gardé`).toHaveValue('M. Alami')
    await expect(acc.locator('#accept-date'), `${quand} : date gardée`).toHaveValue(date)
    await expect(acc.locator('#accept-raison-sociale'), `${quand} : raison sociale gardée`).toHaveValue(`Boulangerie AERR ${m}`)
    await expect(acc.locator('#accept-qualite'), `${quand} : qualité gardée`).toHaveValue('Gérant')
    await expect(acc.locator('#accept-ice'), `${quand} : ICE gardé`).toHaveValue(ICE)
  }
  const confirmer = async () => {
    const rep = p.waitForRequest((x) => x.method() === 'POST' && ACCEPTER.test(x.url()), T)
    await acc.getByRole('button', { name: "Confirmer l'acceptation" }).click()
    return rep
  }
  let issue = 'conflit'
  const repondre = (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    if (issue === 'conflit') return route.fulfill({ status: 409, contentType: 'application/json', body: J({ date_acceptation: [MSG_DATE] }) })
    if (issue === 'panne') return route.fulfill({ status: 500, contentType: 'application/json', body: J({ detail: 'Panne simulée AERR162.' }) })
    return route.abort('failed')
  }
  suivi.attendre(ACCEPTER, 409)
  suivi.attendre(ACCEPTER, 500)
  suivi.attendre(ACCEPTER, 'reseau')
  await p.route(ACCEPTER, repondre)
  await p.goto('/ventes/devis')
  await expect(ligne).toBeVisible({ timeout: 90_000 })
  const date = await remplir()
  // 409 date future : modale rouverte, message sous la date.
  await confirmer()
  await garde(date, '409')
  await expect(acc.locator('#accept-date').locator('xpath=..'), '409 : message sous la date').toContainText(MSG_DATE, { timeout: 15_000 })
  await cliche(p, 'PF12.2-AERR162', '409')
  // 500 : modale rouverte, saisie gardée, un message.
  issue = 'panne'
  await confirmer()
  await garde(date, '500')
  await expect(p.locator('[data-sonner-toast]').first(), '500 : un message').toBeVisible({ timeout: 30_000 })
  // Coupure : modale rouverte, saisie gardée, un message.
  issue = 'coupure'
  await confirmer()
  await garde(date, 'coupure')
  await expect(p.locator('[data-sonner-toast]').first(), 'coupure : un message').toBeVisible({ timeout: 30_000 })
  // Persistance : rien d'accepté ; recharger et réaffirmer le 409.
  expect((await lireJson(await p.request.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')).statut, 'persistance : toujours envoyé').toBe('envoye')
  await acc.getByRole('button', { name: 'Annuler' }).click()
  await p.reload()
  await expect(ligne).toBeVisible({ timeout: 90_000 })
  issue = 'conflit'
  const date2 = await remplir()
  await confirmer()
  await garde(date2, 'rechargé, 409')
  await expect(acc.locator('#accept-date').locator('xpath=..'), 'rechargé : message sous la date').toContainText(MSG_DATE, { timeout: 15_000 })
  expect((await lireJson(await p.request.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')).statut).toBe('envoye')
})

// ═══ PF12.4 — AERR164 : générateur › Lots, deux Entrée pendant l'envoi ⇒ un seul creerLotDevis, un seul lot ═══
etape('PF12.4-AERR164', ['AERR164'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const co = await compteRole('aerr164co', 'Commercial')
  const { p } = await ecran(page, suivi, testInfo, co.nom)
  const d = await devisDe(p.request, admin, `${m}ci`, { ci: true })
  expect(d.statut, 'Given : un devis brouillon modifiable').toBe('brouillon')
  const LOTS = new RegExp(`/api/django/ventes/devis/${d.id}/lots/$`)
  const posts = compter(p, 'POST', LOTS)
  const carte = p.getByTestId('lots-multi-sites')
  const ouvrirGenerateur = async () => {
    await p.goto(`/ventes/devis/nouveau?edit=${d.id}`)
    await expect(p.locator('#gen-form')).toBeVisible({ timeout: 90_000 })
    await expect(p.getByTestId('ci-profil'), 'générateur C&I').toBeVisible({ timeout: 90_000 })
    await auRepos(p)
    const bascule = carte.getByRole('button', { name: 'Afficher' })
    if (await bascule.isVisible()) await bascule.click()
    await expect(carte.getByTestId('lot-formulaire')).toBeVisible({ timeout: 30_000 })
  }
  const deuxEntrees = async (nom) => {
    const g = porte()
    await p.route(LOTS, g.gestion((route) => route.continue()))
    await carte.locator('#lot-nom').fill(nom)
    await carte.locator('#lot-nom').press('Enter')
    await g.arrivee // le 1er POST est parti et TENU
    await carte.locator('#lot-nom').press('Enter')
    await carte.locator('#lot-nom').press('Enter')
    await p.waitForTimeout(800)
    const pendant = posts.length
    const rep = p.waitForResponse((x) => x.request().method() === 'POST' && LOTS.test(x.url()), T)
    g.lacher()
    expect((await rep).status(), 'le lot est créé').toBeLessThan(300)
    await p.unroute(LOTS)
    await p.waitForTimeout(2_000)
    await auRepos(p)
    return pendant
  }
  await ouvrirGenerateur()
  const pendant = await deuxEntrees(`Lot A ${m}`)
  expect(pendant, 'pendant l\'envoi : un seul creerLotDevis malgré trois Entrée').toBe(1)
  expect(posts.length, 'après la réponse : toujours un seul envoi').toBe(1)
  await expect(carte, 'lot listé').toContainText(`Lot A ${m}`, { timeout: 30_000 })
  await cliche(p, 'PF12.4-AERR164', 'un-lot')
  const nomsServis = async () => (await lireJson(await p.request.get(`${API}/ventes/devis/${d.id}/lots/`, T), 'lots')).lots.map((l) => l.nom_lot)
  expect((await nomsServis()).filter((n) => n === `Lot A ${m}`), 'base : un seul « Lot A »').toHaveLength(1)
  // Rechargé : un seul « Lot A » ; réaffirmé avec « Lot B ».
  await p.reload()
  await ouvrirGenerateur()
  await expect(carte).toContainText(`Lot A ${m}`, { timeout: 30_000 })
  await p.waitForTimeout(2_000)
  const pendant2 = await deuxEntrees(`Lot B ${m}`)
  expect(pendant2, 'rechargé : un seul envoi pendant l\'envoi').toBe(2)
  expect(posts.length, 'rechargé : deux créations en tout').toBe(2)
  const noms = await nomsServis()
  expect([noms.filter((n) => n === `Lot A ${m}`).length, noms.filter((n) => n === `Lot B ${m}`).length], 'base : un lot de chaque').toEqual([1, 1])
})

/** Vente acceptée puis facturée « complete » et émise (demo_admin). */
async function factureDe(admin, m) {
  const d = await devisDe(admin, admin, m, { envoye: true })
  await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AERR' } }), 'accepter')
  const rep = await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'complete', emettre: true, remplacer_brouillons: true } }), 'facturer')
  return { id: rep.facture.id, reference: rep.facture.reference, statut: rep.facture.statut }
}
const valeurMad = (texte) => Number(String(texte).replace(/\D/g, '')) / 100
const tuile = (p, libelle) => p.getByText(libelle, { exact: true }).first().locator('xpath=../..').locator('.num')

// ═══ PF12.3 — AERR161 : note de débit créée ⇒ « Total dû » relu sans recharger ; relecture rejetée ⇒ « pas à jour » ═══
etape('PF12.3-AERR161', ['AERR161'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const f = await factureDe(admin, `${m}f`)
  expect(f.statut, 'Given : facture émise').toBe('emise')
  const ad = await compteRole('aerr161ad', 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, ad.nom)
  const KPIS = /\/api\/django\/ventes\/factures\/kpis\/$/
  const kpis = async () => lireJson(await p.request.get(`${API}/ventes/factures/kpis/`, T), 'kpis')
  const lireDu = async () => valeurMad(await tuile(p, 'Total dû').innerText())
  const AVIS = 'Indicateurs pas à jour — la relecture a échoué.'
  const lectures = compter(p, 'GET', KPIS)
  await p.goto('/ventes/factures')
  const ligne = p.locator(`#facture-row-${f.id}`)
  await expect(ligne).toBeVisible({ timeout: 90_000 })
  const du0 = Number((await kpis()).total_du)
  await expect.poll(lireDu, { timeout: 30_000, message: 'tuile au montage = serveur' }).toBe(du0)
  await ligne.locator('button', { hasText: 'Actions' }).click()
  await p.getByRole('menuitem', { name: 'Note de débit' }).click()
  const boite = p.getByRole('dialog').filter({ hasText: `Notes de débit — ${f.reference}` })
  await expect(boite).toBeVisible({ timeout: 30_000 })
  const creer = async (montant, motif) => {
    await boite.locator('#nd-motif').fill(motif)
    await boite.locator('#nd-montant').fill(montant)
    await boite.locator('#nd-tva').fill('20')
    const rep = p.waitForResponse((x) => x.request().method() === 'POST' && /\/creer-note-debit\/$/.test(new URL(x.url()).pathname), T)
    await boite.getByRole('button', { name: 'Créer la note de débit' }).click()
    expect((await rep).status(), 'note de débit créée').toBeLessThan(300)
  }
  // 1) Note de 200 HT : les tuiles sont relues, « Total dû » change sans recharger.
  const n0 = lectures.length
  await creer('200', `AERR161 révision ${m}`)
  await expect.poll(() => lectures.length, { timeout: 30_000, message: 'getFacturesKpis rappelé' }).toBeGreaterThan(n0)
  const du1 = Number((await kpis()).total_du)
  expect(du1, 'serveur : total dû + 240 (200 HT + TVA)').toBeCloseTo(du0 + 240, 2)
  await expect.poll(lireDu, { timeout: 30_000, message: 'SANS recharger : « Total dû » = nouvelle valeur servie' }).toBe(du1)
  await expect(p.getByText(AVIS)).toHaveCount(0)
  await cliche(p, 'PF12.3-AERR161', 'releu')
  // 2) Relecture des tuiles rejetée : anciennes valeurs + « Indicateurs pas à jour ».
  suivi.attendre(KPIS, 'reseau')
  await p.route(KPIS, (route) => route.abort('failed'))
  await creer('100', `AERR161 frais ${m}`)
  await expect(p.getByText(AVIS), '« Indicateurs pas à jour »').toBeVisible({ timeout: 30_000 })
  expect(await lireDu(), 'relecture rejetée : l\'ancienne valeur reste').toBe(du1)
  const du2 = Number((await kpis()).total_du)
  expect(du2, 'serveur : 2ᵉ note comptée').toBeCloseTo(du1 + 120, 2)
  await p.unroute(KPIS)
  // Persistance : recharger ⇒ le serveur fait foi.
  await boite.getByRole('button', { name: 'Fermer' }).click()
  await expect(boite).toBeHidden({ timeout: 30_000 })
  if (await p.getByRole('menu').isVisible()) await p.keyboard.press('Escape')
  await p.reload()
  await expect(ligne).toBeVisible({ timeout: 90_000 })
  await expect.poll(lireDu, { timeout: 30_000, message: 'rechargé : « Total dû » = serveur' }).toBe(du2)
  await expect(p.getByText(AVIS)).toHaveCount(0)
})

// ══════════════════════════════ CRM — AERR167, AERR156, AERR163, AERR165, AERR166 ══════════════════════════════

const creerLeads = (owner, liste) => py(`from apps.crm.models import Lead
out = []
for d in json.loads(${J(J(liste))}):
    out.append(Lead.objects.create(company_id=${SOC}, owner_id=${owner}, **d).pk)
sortie(out)`)
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
const fermerVisite = async (p) => {
  const b = p.getByRole('button', { name: 'Fermer la visite guidée' })
  await b.waitFor({ state: 'visible', timeout: 8_000 }).then(() => b.click()).catch(() => undefined)
}

// ═══ PF12.1 — AERR167 : archiver depuis la liste un lead supprimé dans un autre onglet (404) ⇒ un message ═══
etape('PF12.1-AERR167', ['AERR167'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const di = await compteRole('aerr167di', 'Directeur')
  const [a, b] = await creerLeads(di.id, [
    { nom: `Benali ${m}`, prenom: 'Ahmed', telephone: telephoneMobileUnique(), stage: 'NEW' },
    { nom: `Tazi ${m}`, prenom: 'Salma', telephone: telephoneMobileUnique(), stage: 'NEW' },
  ])
  apres.push(() => supprimerLeads([a, b]))
  const etat = (pk) => py(`from apps.crm.models import Lead
l = Lead.all_objects.get(pk=${pk}); sortie([l.is_archived, bool(getattr(l, 'is_deleted', False))])`)
  const { p, ctx } = await ecran(page, suivi, testInfo, di.nom)
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  const ligne = (n) => p.locator('tr.lv-row').filter({ hasText: n })
  await expect(ligne(`Benali ${m}`), 'lead A listé').toBeVisible({ timeout: 60_000 })
  await expect(ligne(`Tazi ${m}`), 'lead B listé').toBeVisible()
  await fermerVisite(p)
  const boite = p.getByRole('alertdialog')
  const presser = async (bouton) => { await bouton.focus(); await p.keyboard.press('Enter') }
  const archiver = async (n) => {
    await presser(ligne(n).getByRole('button', { name: 'Archiver', exact: true }))
    await expect(boite).toContainText('Archiver « ', { timeout: 15_000 })
    const rep = p.waitForResponse((x) => x.request().method() === 'POST' && /\/crm\/leads\/\d+\/archiver\/$/.test(new URL(x.url()).pathname), T)
    await boite.getByRole('button', { name: 'Archiver', exact: true }).click()
    return (await rep).status()
  }
  // A supprimé dans un AUTRE onglet (même session).
  const onglet = suivi.surveiller(await ctx.newPage())
  const sup = await onglet.request.delete(`${API}/crm/leads/${a}/`, T)
  expect(sup.status(), `lead A supprimé ailleurs : ${(await sup.text()).slice(0, 200)}`).toBeLessThan(300)
  await onglet.close()
  expect(await etat(a), 'base : A à la corbeille').toEqual([false, true])
  const ARCH_A = new RegExp(`/api/django/crm/leads/${a}/archiver/$`)
  suivi.attendre(ARCH_A, 404)
  const echec = "L'archivage a échoué — réessayez."
  expect(await archiver(`Benali ${m}`), 'archiver A : 404 servi').toBe(404)
  await expect(toast(p, echec).first(), '404 : le message local est affiché').toBeVisible({ timeout: 30_000 })
  await expect(toast(p, 'Lead archivé.'), 'aucun « Lead archivé. »').toHaveCount(0)
  await expect(p.locator('[data-sonner-toast]').getByRole('button', { name: 'Annuler' }), 'aucun « Annuler »').toHaveCount(0)
  await cliche(p, 'PF12.1-AERR167', '404')
  expect(await etat(a), 'base : A ni archivé ni restauré').toEqual([false, true])
  // B : refus 400 servi (toast global) ⇒ toujours UN seul toast, pas de toast local en plus.
  const ARCH_B = new RegExp(`/api/django/crm/leads/${b}/archiver/$`)
  const refus = await panne(p, suivi, ARCH_B, { statut: 400, methode: 'POST', corps: { detail: 'Refus simulé AERR167.' } })
  await p.waitForTimeout(6_500) // laisse partir les toasts précédents
  expect(await archiver(`Tazi ${m}`), 'archiver B : 400 servi').toBe(400)
  await expect(toast(p, 'Refus simulé AERR167.').first(), '400 : le toast global nomme le refus').toBeVisible({ timeout: 30_000 })
  await p.waitForTimeout(1_500)
  await expect(toast(p, echec), '400 : aucun toast local en plus').toHaveCount(0)
  expect(await p.locator('[data-sonner-toast]').count(), '400 : un seul toast').toBe(1)
  expect(await etat(b), 'base : B non archivé').toEqual([false, false])
  await refus.lever()
  // Persistance : recharger ⇒ B listé, A absent (corbeille).
  await p.reload()
  await expect(ligne(`Tazi ${m}`), 'rechargé : B listé').toBeVisible({ timeout: 60_000 })
  await expect(ligne(`Benali ${m}`), 'rechargé : A absent').toHaveCount(0)
})

// ═══ PF12.1 — AERR156 : relance en 500, fenêtre fermée puis rouverte ⇒ le nouvel appel est journalisé ═══
etape('PF12.1-AERR156', ['AERR156'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await compteRole('aerr156co', 'Commercial')
  const [lead] = await creerLeads(co.id, [{ nom: `AERR156 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const { p } = await ecran(page, suivi, testInfo, co.nom)
  await p.goto(`/crm/leads/${lead}`)
  const rail = p.getByTestId('lw-context-rail')
  await expect(rail).toBeVisible({ timeout: 60_000 })
  const journaux = compter(p, 'POST', new RegExp(`/api/django/crm/leads/${lead}/log-interaction/$`))
  const reports = compter(p, 'PATCH', new RegExp(`/api/django/crm/leads/${lead}/$`))
  const LEAD = new RegExp(`/api/django/crm/leads/${lead}/$`)
  suivi.attendre(LEAD, 500)
  let premier = true
  await p.route(LEAD, (route) => {
    if (route.request().method() === 'PATCH' && premier) {
      premier = false
      return route.fulfill({ status: 500, contentType: 'application/json', body: J({ detail: 'Panne simulée AERR156.' }) })
    }
    return route.fallback()
  })
  const pop = p.getByRole('dialog').filter({ hasText: 'Journaliser un appel' })
  const journaliser = async () => {
    await rail.getByRole('button', { name: 'Journaliser', exact: true }).click()
    await expect(pop).toBeVisible({ timeout: 30_000 })
    await pop.getByRole('group', { name: "Résultat de l'appel" }).getByRole('button', { name: 'Non joint' }).click()
    await pop.getByRole('button', { name: 'Demain', exact: true }).click()
    await pop.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  }
  await journaliser()
  await expect(toast(p, "Appel journalisé ; la relance n'a pas pu être planifiée — réessayez.").first(), '1ᵉʳ appel : journalisé, relance non planifiée').toBeVisible({ timeout: 30_000 })
  expect([journaux.length, reports.length], '1ᵉʳ essai : 1 journal, 1 report (refusé)').toEqual([1, 1])
  // Fenêtre fermée (« Annuler ») puis rouverte : nouvelle saisie ⇒ nouvel appel journalisé.
  await pop.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(pop).toBeHidden({ timeout: 15_000 })
  await journaliser()
  await expect(toast(p, 'Appel journalisé.').first(), '2ᵉ appel : « Appel journalisé. »').toBeVisible({ timeout: 30_000 })
  await expect(toast(p, 'Relance planifiée.'), 'jamais « Relance planifiée. » pour un nouvel appel').toHaveCount(0)
  expect([journaux.length, reports.length], '2ᵉ appel : logInteraction rappelé, report rejoué').toEqual([2, 2])
  await cliche(p, 'PF12.1-AERR156', 'deux-appels')
  const enBase = await py(`from apps.crm.models import LeadActivity
sortie(LeadActivity.objects.filter(lead_id=${lead}, kind='appel').count())`)
  expect(enBase, 'base : deux appels journalisés').toBe(2)
  // Persistance : historique relu ⇒ deux appels.
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await p.reload()
  await expect(rail).toBeVisible({ timeout: 60_000 })
  const histo = await p.request.get(`${API}/crm/leads/${lead}/historique/`, T)
  expect(histo.status()).toBe(200)
  expect((J(await histo.json()).match(/"kind":\s*"appel"/g) || []).length, 'historique relu : deux appels').toBe(2)
})

// ═══ PF12.1 — AERR163 : profil site, 120.555 en facture d'hiver ⇒ refus réel sous « Facture hiver », saisie gardée ═══
etape('PF12.1-AERR163', ['AERR163'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await compteRole('aerr163co', 'Commercial')
  const nomClient = `AERR163 ${m}`
  const cl = await py(`from decimal import Decimal
from apps.crm.models import Client, SiteProfile, Lead
c = Client.objects.create(company_id=${SOC}, nom=${J(nomClient)}, prenom='Essai')
SiteProfile.objects.create(company_id=${SOC}, client=c, facture_hiver=Decimal('900.00'), surface_toiture_m2=Decimal('80.00'))
Lead.objects.create(company_id=${SOC}, owner_id=${co.id}, client=c, nom=${J(nomClient)}, prenom='Lead', telephone=${J(telephoneMobileUnique())}, stage='NEW')
sortie(c.pk)`)
  apres.push(() => py(`from apps.crm.models import Client, Lead, SiteProfile
Lead.all_objects.filter(client_id=${cl}).delete()
SiteProfile.objects.filter(client_id=${cl}).delete(); Client.objects.filter(pk=${cl}).delete()`))
  const servi = () => py(`from apps.crm.models import SiteProfile
sortie([str(x.facture_hiver) for x in SiteProfile.objects.filter(client_id=${cl})])`)
  const { p } = await ecran(page, suivi, testInfo, co.nom)
  const choisir = async () => {
    await p.goto('/crm/profils-site')
    await p.locator('#sp-client').click({ timeout: 60_000 })
    await p.getByRole('searchbox').fill(nomClient)
    await p.getByRole('option', { name: new RegExp(nomClient) }).click()
    await expect(p.locator('#sp-hiver'), 'profil lu').toHaveValue(/^900(\.0+)?$/, { timeout: 30_000 })
  }
  const PATCH = /\/api\/django\/crm\/site-profiles\/\d+\/$/
  suivi.attendre(PATCH, 400)
  const jouer = async (quand) => {
    await p.locator('#sp-hiver').fill('120.555')
    const refus = p.waitForResponse((r) => PATCH.test(r.url()) && r.request().method() === 'PATCH', T)
    await p.getByRole('button', { name: 'Enregistrer le profil' }).click()
    const r = await refus
    expect(r.status(), `${quand} : le serveur refuse la facture d'hiver`).toBe(400)
    const msg = (await r.json()).facture_hiver?.[0]
    expect(msg, `${quand} : refus nommé sur facture_hiver`).toBeTruthy()
    const sous = p.locator('#sp-hiver').locator('xpath=following-sibling::p[@role="alert"][1]')
    await expect(sous, `${quand} : message sous « Facture hiver »`).toHaveText(msg, { timeout: 15_000 })
    await expect(p.locator('#sp-hiver'), `${quand} : saisie gardée`).toHaveValue('120.555')
    await expect(p.locator('#sp-surface').locator('xpath=following-sibling::p[@role="alert"]'), `${quand} : rien sous la surface`).toHaveCount(0)
    return msg
  }
  await choisir()
  await jouer('1ᵉʳ essai')
  await cliche(p, 'PF12.1-AERR163', 'sous-le-champ')
  expect(await servi(), 'base : facture d\'hiver inchangée').toEqual(['900.00'])
  await choisir()
  await jouer('rechargé')
  expect(await servi()).toEqual(['900.00'])
})

// ═══ PF12.3 — AERR165 : verdict de Sami affiché, choix de Nadia en panne ⇒ aucun verdict de Sami ═══
const creerEtapes = (lead, etapes) => py(`from apps.crm.models import RelanceEtape, Lead
l = Lead.objects.get(pk=${lead})
out = []
for i, d in enumerate(json.loads(${J(J(etapes))})):
    out.append(RelanceEtape.objects.create(company_id=l.company_id, lead=l, ordre=i + 1, due_at=timezone.now(),
        due_date=timezone.localdate(), **d).pk)
sortie(out)`)

etape('PF12.3-AERR165', ['AERR165'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const di = await compteRole('aerr165di', 'Directeur')
  const sami = await compteRole('aerr165sa', 'Commercial', { prenom: 'Sami', famille: `AERR165 ${m}` })
  const nadia = await compteRole('aerr165na', 'Commercial', { prenom: 'Nadia', famille: `AERR165 ${m}` })
  const [ls, ln] = [
    ...(await creerLeads(sami.id, [{ nom: `AERR165 S ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])),
    ...(await creerLeads(nadia.id, [{ nom: `AERR165 N ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])),
  ]
  apres.push(() => supprimerLeads([ls, ln]))
  await creerEtapes(ls, [{ cadence: 'contact', canal: 'appel', libelle: `Appel S ${m}` }])
  await creerEtapes(ln, [{ cadence: 'contact', canal: 'appel', libelle: `Appel N ${m}` }])
  const { p } = await ecran(page, suivi, testInfo, di.nom)
  const CONTROLE = /\/api\/django\/crm\/relance-etapes\/controle\//
  const panel = p.getByTestId('controle-suivi-panel')
  const verdict = panel.getByTestId('controle-verdict')
  const choisirCommercial = async (u, prenom) => {
    const sel = panel.getByRole('combobox', { name: 'Commercial' })
    await expect(sel, 'sélecteur de commercial').toBeVisible({ timeout: 30_000 })
    await sel.click()
    await p.getByRole('option', { name: new RegExp(`(${prenom} AERR165 ${m}|${u.nom})`) }).click()
  }
  const ouvrir = async () => {
    await p.goto('/crm/cockpit')
    await expect(verdict, 'verdict de l\'équipe lu').toBeVisible({ timeout: 60_000 })
    const bascule = panel.getByTestId('controle-bascule-detail')
    if ((await bascule.getAttribute('aria-expanded')) !== 'true') await bascule.click()
    await expect(panel.getByTestId('controle-detail-corps')).toBeVisible({ timeout: 30_000 })
  }
  const jouer = async (passe) => {
    await ouvrir()
    // Sami : verdict servi et affiché.
    const luSami = p.waitForResponse((x) => CONTROLE.test(x.url()) && new URL(x.url()).searchParams.get('owner') === String(sami.id), T)
    await choisirCommercial(sami, 'Sami')
    expect((await luSami).status(), `${passe}verdict de Sami servi`).toBe(200)
    await expect(panel.getByTestId('controle-commercial-actif'), `${passe}Sami choisi`).toContainText(new RegExp(`Sami AERR165 ${m}|${sami.nom}`))
    await expect(verdict, `${passe}verdict de Sami affiché`).toBeVisible({ timeout: 30_000 })
    // Nadia : lecture en panne ⇒ aucun chiffre de Sami, « Indisponible » + Réessayer.
    const coupe = await panne(p, suivi, CONTROLE)
    const luNadia = p.waitForResponse((x) => CONTROLE.test(x.url()) && new URL(x.url()).searchParams.get('owner') === String(nadia.id), T)
    await choisirCommercial(nadia, 'Nadia')
    expect((await luNadia).status(), `${passe}lecture de Nadia rejetée`).toBe(500)
    await expect(panel.getByTestId('controle-commercial-actif'), `${passe}Nadia choisie`).toContainText(new RegExp(`Nadia AERR165 ${m}|${nadia.nom}`))
    const indispo = panel.getByTestId('controle-panne')
    await expect(indispo, `${passe}avis « Indisponible » + Réessayer`).toBeVisible({ timeout: 30_000 })
    await expect(indispo.getByRole('button', { name: 'Réessayer' })).toBeVisible()
    await expect(verdict, `${passe}aucun verdict de Sami sous le filtre Nadia`).toHaveCount(0)
    await expect(panel.getByTestId('controle-comparaison'), `${passe}aucune comparaison de Sami`).toHaveCount(0)
    await expect(panel.getByTestId('controle-pas-a-jour'), `${passe}jamais « Pas à jour » sur un autre filtre`).toHaveCount(0)
    return { coupe, indispo }
  }
  const { coupe, indispo } = await jouer('')
  await cliche(p, 'PF12.3-AERR165', 'panne-nadia')
  // Réessayer, panne levée : le verdict de Nadia est lu.
  await coupe.lever()
  await indispo.getByRole('button', { name: 'Réessayer' }).click()
  await expect(verdict, 'Réessayer : verdict de Nadia').toBeVisible({ timeout: 30_000 })
  await expect(indispo).toHaveCount(0)
  // Rechargé : réaffirmé ; l'étape finit sur l'avis de panne.
  await p.reload()
  await jouer('rechargé : ')
})

// ═══ PF12.2 — AERR166 : fiche lead modifiée, réseau coupé, quitter, « Abandonner » ⇒ aucun PATCH, valeur d'origine ═══
etape('PF12.2-AERR166', ['AERR166'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await compteRole('aerr166co', 'Commercial')
  const [a] = await creerLeads(co.id, [{ nom: `AERR166 A ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW', ville: 'Rabat' }])
  apres.push(() => supprimerLeads([a]))
  const villeDe = () => py(`from apps.crm.models import Lead
sortie(Lead.objects.get(pk=${a}).ville)`)
  const { p } = await ecran(page, suivi, testInfo, co.nom)
  const LEAD = new RegExp(`/api/django/crm/leads/${a}/$`)
  const patchs = compter(p, 'PATCH', LEAD)
  const fiche = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: new RegExp(`AERR166 A ${m}`) }) })
  const ville = fiche.locator('#lf-ville')
  const ouvrir = async () => {
    await p.goto(`/crm/leads?lead=${a}`)
    await expect(fiche, 'fiche du lead ouverte').toBeVisible({ timeout: 60_000 })
    if (!(await ville.isVisible())) {
      await fiche.getByRole('navigation', { name: 'Sections du lead' }).getByRole('button', { name: 'Contact', exact: true }).click()
    }
    await expect(ville).toBeVisible({ timeout: 30_000 })
    await expect(ville, 'ville servie').toHaveValue('Rabat')
  }
  const abandonner = async (quand) => {
    const coupe = await panne(p, suivi, LEAD, { statut: 'reseau', methode: 'PATCH' })
    await ville.fill('Agadir')
    await fiche.locator('button.modal-close[aria-label="Fermer"]').click()
    const q = p.getByRole('alertdialog').filter({ hasText: 'Abandonner les modifications ?' })
    await expect(q, `${quand} : l'enregistrement a échoué, la question est posée`).toBeVisible({ timeout: 30_000 })
    if (!quand.startsWith('rechargé')) await cliche(p, 'PF12.2-AERR166', 'abandonner')
    await q.getByRole('button', { name: 'Abandonner', exact: true }).click()
    await expect(q).toHaveCount(0)
    await expect(fiche, `${quand} : fiche quittée`).toHaveCount(0, { timeout: 15_000 })
    const n = patchs.length
    await p.waitForTimeout(3_000)
    expect(patchs.length, `${quand} : aucun PATCH au démontage après « Abandonner »`).toBe(n)
    // Réseau rétabli : rien ne repart.
    await coupe.lever()
    await p.waitForTimeout(3_000)
    await auRepos(p)
    expect(patchs.length, `${quand} : réseau rétabli, aucun PATCH`).toBe(n)
    expect(await villeDe(), `${quand} : base, ville d'origine`).toBe('Rabat')
  }
  await ouvrir()
  await abandonner('1ᵉʳ passage')
  // Relire A : la valeur d'origine, aucun brouillon restauré.
  await ouvrir()
  await expect(p.getByText('Brouillon restauré'), 'miroir de session purgé : aucun brouillon restauré').toHaveCount(0)
  // Rechargé : réaffirmé.
  await p.reload()
  await ouvrir()
  await abandonner('rechargé')
  await ouvrir()
  await expect(p.getByText('Brouillon restauré')).toHaveCount(0)
})
