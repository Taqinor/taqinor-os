// Preuves en direct du groupe AERR, lot 5 (parcours PF12 « erreurs, pertes de saisie et gestes dangereux à
// l'écran », dossier docs/audits/2026-11-11-parcours-PF12.md) : AERR134, AERR153 (paramètres), AERR135 (lead),
// AERR151, AERR152 (SAV), AERR154 (analyse) — et, comme leurs clauses « Preuve en direct » le demandent, le rejeu
// des étapes que ces corrections débloquent : PF12.1-AERR25 et PF12.1-AERR25-annulation (aerr.spec.js, AERR25 avec
// AERR151), PF12.5-AERR125 (aerr4.spec.js, AERR125 avec AERR153), les deux étapes AERR130 (aerr4.spec.js, AERR130
// avec AERR154). Chaque étape joue l'ÉCRAN nommé sous un compte d'essai d'un rôle LIVRÉ du registre (société démo,
// session posée par la vraie route /token/), provoque l'échec quand la clause le demande (route Playwright déclarée
// AVANT par `suivi.attendre`), AFFIRME à l'écran ce que la clause nomme, relit la base ou l'API, puis recharge et
// réaffirme. Données propres créées par le shell Django ou l'API, retirées en fin d'étape.
import { test, expect } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { RACINE, cheminCapture } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, lireJson, listeDe, telephoneMobileUnique } from '../helpers.js'

const G = 'AERR'
const etape = groupe(G, ['AERR134', 'AERR135', 'AERR25', 'AERR151', 'AERR152', 'AERR125', 'AERR153', 'AERR130', 'AERR154'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const DEMANDE = 'Modifications non enregistrées — quitter cette page ?'
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

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société démo ; {nom, id, tier}. Désactivé en fin d'étape. */
async function compteRole(prefixe, nomRole) {
  const nom = `${prefixe}_${marque()}`
  const r = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
assert r.est_systeme, 'rôle non système'
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.first_name = 'Essai'; u.last_name = ${J(nomRole)}; u.save(update_fields=['first_name', 'last_name'])
sortie({'id': u.id, 'tier': u.menu_tier, 'perms': sorted(r.permissions or [])})`)
  comptes.push(nom)
  return { nom, ...r }
}

/** Écran du compte `nom` : contexte neuf (accueil et visites guidées vus, SW bloqué), session par la vraie route
 *  /token/, observé par les oracles. La page demo_admin de l'étape est refermée : la capture montre CET écran.
 *  Seule la demande de saisie non enregistrée (`confirmLeaveIfDirty`) est un dialogue natif attendu. */
async function ecran(page, suivi, testInfo, nom, viewport = { width: 1600, height: 1000 }) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', viewport,
  })
  contextes.push(ctx)
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of listeDe(await visites.json())) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  const p = suivi.surveiller(await ctx.newPage())
  const dem = { vues: 0, prochaine: null }
  p.removeAllListeners('dialog')
  p.on('dialog', async (d) => {
    if (d.type() === 'confirm' && d.message() === DEMANDE && dem.prochaine) {
      const reponse = dem.prochaine
      dem.prochaine = null
      dem.vues += 1
      await (reponse === 'quitter' ? d.accept() : d.dismiss()).catch(() => undefined)
      return
    }
    suivi.incidents.push({ oracle: '4', texte: `dialogue natif inattendu ${d.type()} : ${d.message()}` })
    await d.dismiss().catch(() => undefined)
  })
  return { p, dem }
}

/** Panne INJECTÉE (déclarée au suivi AVANT) sur les requêtes `methode` d'URL `re` ; les autres passent. */
async function panne(p, suivi, re, { statut = 503, methode = 'GET', corps = { detail: 'Service indisponible (panne simulée, rejeu AERR).' }, retenue = null } = {}) {
  suivi.attendre(re, statut)
  const hits = { n: 0 }
  const h = async (route) => {
    if (route.request().method() !== methode) return route.fallback()
    hits.n += 1
    if (retenue) await retenue
    return route.fulfill({ status: statut, contentType: 'application/json', body: J(corps) })
  }
  await p.route(re, h)
  return { hits, vues: hits, lever: () => p.unroute(re, h) }
}

/** Requêtes `methode` d'URL `re` parties de la page. */
function compter(p, methode, re) {
  const vues = []
  p.on('request', (r) => { if (r.method() === methode && re.test(r.url())) vues.push(r.url()) })
  return vues
}

/** Capture PENDANT que l'écran affirmé est visible (en plus de la capture de fin d'étape). */
async function cliche(p, id, moment) {
  const chemin = join(RACINE, cheminCapture(G, `${id}-${moment}`))
  mkdirSync(dirname(chemin), { recursive: true })
  await p.screenshot({ path: chemin, type: 'jpeg', quality: 60 })
}

const auRepos = (p) => p.waitForLoadState('networkidle').catch(() => undefined)

/** Toutes les lignes d'une liste DRF (paginée ou non). */
async function lignes(ctx, url) {
  const out = []
  let suivant = url
  while (suivant) {
    const d = await lireJson(await ctx.get(suivant, T), url)
    if (Array.isArray(d)) return out.concat(d)
    out.push(...(d.results || []))
    suivant = d.next ? (() => { const u = new URL(d.next); return `${u.pathname}${u.search}` })() : null
  }
  return out
}

// ══════════════════════════════ PARAMÈTRES — AERR134 ══════════════════════════════

// ═══ PF12.2 — AERR134 : corps de modèle brandé et traduction tapés survivent à un aller-retour d'onglet ═══
etape('PF12.2-AERR134', ['AERR134'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ad = await compteRole('aerr134ad', 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, ad.nom)
  const nomModele = `Modèle AERR134 ${m}`
  const corpsServeur = `Bonjour, corps enregistré ${m}`
  const modele = await lireJson(await p.request.post(`${API}/core/branded-templates/`, {
    ...T, data: { kind: 'email', code: `aerr134_${m}`, nom: nomModele, sujet: `Offre ${m}`, corps: corpsServeur },
  }), 'modèle brandé')
  apres.push(() => py(`from core.models import BrandedTemplate
BrandedTemplate.objects.filter(pk=${modele.id}).delete()`))
  const nav = p.getByRole('navigation', { name: 'Sections des paramètres' })
  const onglet = (label) => nav.getByRole('button', { name: label, exact: true })
  const lectures = compter(p, 'GET', /\/api\/django\/core\/branded-templates\/(\?|$)/)
  await p.goto('/parametres?onglet=modeles_brandes')
  await p.getByRole('button', { name: nomModele, exact: true }).click({ timeout: 60_000 })
  const corps = p.getByPlaceholder('Corps', { exact: true })
  await expect(corps, 'éditeur ouvert sur le corps enregistré').toHaveValue(corpsServeur, { timeout: 30_000 })
  const tape = `Bonjour {client} — offre ${m}`
  await corps.fill(tape)
  await auRepos(p)
  const lecturesAvant = lectures.length
  // Aller-retour par l'onglet Traductions, sans enregistrer.
  await onglet('Traductions').click()
  await expect(onglet('Traductions'), 'onglet Traductions actif').toHaveAttribute('aria-current', 'page')
  await expect(p.getByLabel('Rechercher une traduction'), 'Traductions affichées').toBeVisible({ timeout: 30_000 })
  await expect(corps, 'Modèles brandés masqué pendant Traductions').toBeHidden()
  await onglet('Modèles brandés').click()
  await expect(onglet('Modèles brandés')).toHaveAttribute('aria-current', 'page')
  await expect(corps, 'retour sur Modèles brandés : le corps tapé est toujours là').toHaveValue(tape, { timeout: 15_000 })
  await auRepos(p)
  expect(lectures.length, 'aucune nouvelle lecture serveur des modèles au retour').toBe(lecturesAvant)
  await cliche(p, 'PF12.2-AERR134', 'corps-garde')
  expect(await py(`from core.models import BrandedTemplate
sortie(BrandedTemplate.objects.get(pk=${modele.id}).corps)`), 'base : rien écrit (corps serveur inchangé)').toBe(corpsServeur)
  // Traductions : une valeur tapée survit à un aller-retour par Référentiels.
  await onglet('Traductions').click()
  const cellule = p.getByLabel(/^Traduction English de /).first()
  await expect(cellule).toBeVisible({ timeout: 30_000 })
  const label = await cellule.getAttribute('aria-label')
  const champ = p.getByLabel(label, { exact: true })
  const traduction = `Libellé AERR134 ${m}`
  await champ.fill(traduction)
  await onglet('Référentiels').click()
  await expect(onglet('Référentiels')).toHaveAttribute('aria-current', 'page')
  await expect(champ, 'Traductions masqué pendant Référentiels').toBeHidden({ timeout: 15_000 })
  await auRepos(p)
  await onglet('Traductions').click()
  await expect(champ, 'retour sur Traductions : la traduction tapée est toujours là').toHaveValue(traduction, { timeout: 15_000 })
  await expect(p.getByRole('button', { name: /Enregistrer \(1\)/ }), 'le brouillon compte 1 modification non enregistrée').toBeVisible()
  await cliche(p, 'PF12.2-AERR134', 'traduction-gardee')
  const cle = label.replace(/^Traduction English de /, '')
  const surcharges = await lireJson(await p.request.get(`${API}/parametres/traductions/effective/`, T), 'surcharges')
  expect(surcharges?.overrides?.en?.[cle], 'base : aucune surcharge écrite').not.toBe(traduction)
})

// ══════════════════════════════ LEADS — AERR135 ══════════════════════════════

// ═══ PF12.2 — AERR135 : réassignation refusée (400) depuis le kanban ⇒ ni « Responsable modifié. » ni « Annuler » ═══
etape('PF12.2-AERR135', ['AERR135'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const di = await compteRole('aerr135di', 'Directeur')
  const sami = await compteRole('aerr135sa', 'Commercial')
  const nadia = await compteRole('aerr135na', 'Commercial')
  const nom = `Lead Démo AERR135 ${m}`
  const lead = await py(`from apps.crm.models import Lead
sortie(Lead.objects.create(company_id=${SOC}, nom=${J(nom)}, telephone='${telephoneMobileUnique()}', email='aerr135-${m}@example.invalid', owner_id=${sami.id}).pk)`)
  apres.push(() => py(`from apps.crm.models import Lead
Lead.all_objects.filter(pk=${lead}).delete()`))
  const { p } = await ecran(page, suivi, testInfo, di.nom)
  const PATCH = new RegExp(`/api/django/crm/leads/${lead}/$`)
  const refus = await panne(p, suivi, PATCH, { statut: 400, methode: 'PATCH', corps: { owner: ['Utilisateur inactif.'] } })
  const ouvrir = async () => {
    await p.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(nom)}`)
    const carte = p.locator(`[data-lead-id="${lead}"]`)
    await expect(carte, 'carte du lead sur le kanban').toBeVisible({ timeout: 60_000 })
    return carte
  }
  const carte = await ouvrir()
  const declencheur = carte.locator(`button[title="Responsable : ${sami.nom}"]`)
  await expect(declencheur, 'Given : responsable Sami').toBeVisible({ timeout: 30_000 })
  await declencheur.click()
  const menu = p.locator('.ap-menu')
  await expect(menu).toBeVisible({ timeout: 15_000 })
  const [req] = await Promise.all([
    p.waitForRequest((q) => q.method() === 'PATCH' && PATCH.test(q.url()), T),
    menu.getByRole('button', { name: nadia.nom }).click(),
  ])
  expect(req.postDataJSON(), 'PATCH envoyé : owner = Nadia').toMatchObject({ owner: nadia.id })
  await expect(toast(p, 'Utilisateur inactif').first(), 'un toast d\'erreur nomme le refus').toBeVisible({ timeout: 30_000 })
  await p.waitForTimeout(2_500)
  await expect(toast(p, 'Responsable modifié.'), 'aucun « Responsable modifié. »').toHaveCount(0)
  await expect(p.locator('[data-sonner-toast]').getByRole('button', { name: 'Annuler' }), 'aucun « Annuler »').toHaveCount(0)
  await expect(carte.locator(`button[title="Responsable : ${sami.nom}"]`), 'la carte garde Sami').toBeVisible()
  await expect(carte.locator(`button[title="Responsable : ${nadia.nom}"]`)).toHaveCount(0)
  expect(refus.hits.n, 'un seul PATCH (aucun « revert »)').toBe(1)
  await cliche(p, 'PF12.2-AERR135', 'refus')
  // Persistance : base puis écran rechargé.
  expect(await py(`from apps.crm.models import Lead
sortie(Lead.all_objects.get(pk=${lead}).owner_id)`), 'base : responsable Sami').toBe(sami.id)
  await refus.lever()
  const carte2 = await ouvrir()
  await expect(carte2.locator(`button[title="Responsable : ${sami.nom}"]`), 'après rechargement : Sami').toBeVisible({ timeout: 30_000 })
  await auRepos(p)
})

// ══════════════════════════════ SAV — AERR25 + AERR151, AERR152 ══════════════════════════════

const ticketsDe = (m, specs) => py(`from apps.crm.models import Client
from apps.sav.models import Ticket
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
ids = []
for s in ${J(specs)}:
    t = Ticket.objects.create(company_id=${SOC}, client=cl, reference=s['ref'], priorite=s['priorite'],
        description=s['description'], instructions=s.get('instructions', ''))
    ids.append(t.pk)
sortie(dict(client=cl.pk, tickets=ids))`)
const champsTicket = (pks) => py(`from apps.sav.models import Ticket
sortie([[t.priorite, t.description, t.instructions] for t in (Ticket.objects.get(pk=pk) for pk in ${J(pks)})])`)
const retirerTickets = (ids) => py(`from apps.crm.models import Client
from apps.sav.models import Ticket
for pk in ${J(ids.tickets)}:
    try: Ticket.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`)

/** Liste /sav filtrée sur le client d'essai ; renvoie les localisateurs utiles. */
async function listeTickets(p, m) {
  await p.goto('/sav')
  await p.getByPlaceholder('Rechercher (référence, client, chantier, description)…').fill(`AERR Client ${m}`, { timeout: 60_000 })
  const ligne = (ref) => p.getByRole('row').filter({ hasText: ref })
  const fiche = p.locator('aside[aria-label^="Détail du ticket"]')
  const champ = {
    description: fiche.locator('label:text-is("Description") + div textarea'),
    priorite: fiche.locator('label:text-is("Priorité") + button'),
    technicien: fiche.locator('label:text-is("Technicien responsable") + button'),
    instructions: fiche.locator('#ticket-instructions'),
  }
  const sortirDuChamp = () => fiche.getByText('Suivi, équipement, interventions, pièces et historique du ticket.').click()
  return { ligne, fiche, champ, sortirDuChamp }
}

// ═══ PF12.1 — AERR25 (S1) : la fiche suit le ticket sélectionné (clic, J/K), « Mettre à jour » n'écrit que B ═══
// Rejeu de l'étape PF12.1-AERR25 d'aerr.spec.js (sortie d'`etapeRouge`, clause « Preuve en direct » d'AERR151).
etape('PF12.1-AERR25', ['AERR25'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const A = `SAV-A25-${m}`
  const B = `SAV-B25-${m}`
  const ids = await ticketsDe(m, [
    { ref: A, priorite: 'urgente', description: `Onduleur HS ${m}`, instructions: `Couper le disjoncteur ${m}` },
    { ref: B, priorite: 'normale', description: `Panneau fissuré ${m}`, instructions: `Accès par le portail ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const [idA, idB] = ids.tickets
  const re = await compteRole('aerr25re', 'Responsable')
  const { p, dem } = await ecran(page, suivi, testInfo, re.nom)
  const patchs = compter(p, 'PATCH', /\/api\/django\/sav\/tickets\/\d+\/$/)
  const { ligne, fiche, champ, sortirDuChamp } = await listeTickets(p, m)
  await expect(ligne(A), 'ticket A listé').toBeVisible({ timeout: 60_000 })
  await expect(ligne(B), 'ticket B listé').toBeVisible()
  const montre = async (ref, desc, prio, instr, quand) => {
    await expect(fiche, `${quand} : fiche de ${ref}`).toHaveAttribute('aria-label', `Détail du ticket ${ref}`)
    await expect(fiche, `${quand} : en-tête ${ref}`).toContainText(`Ticket SAV — ${ref}`)
    await expect(champ.description, `${quand} : description de ${ref}`).toHaveValue(desc)
    await expect(champ.priorite, `${quand} : priorité de ${ref}`).toContainText(prio)
    await expect(champ.instructions, `${quand} : instructions de ${ref}`).toHaveValue(instr)
  }
  await ligne(A).getByText(A).click()
  await montre(A, `Onduleur HS ${m}`, 'Urgente', `Couper le disjoncteur ${m}`, 'fiche A ouverte')
  await ligne(B).getByText(B).click()
  await montre(B, `Panneau fissuré ${m}`, 'Normale', `Accès par le portail ${m}`, 'clic sur B')
  await cliche(p, 'PF12.1-AERR25', 1)
  const [req] = await Promise.all([
    p.waitForRequest((r) => r.method() === 'PATCH' && /\/api\/django\/sav\/tickets\/\d+\/$/.test(r.url()), T),
    fiche.getByRole('button', { name: 'Mettre à jour' }).click(),
  ])
  expect(new URL(req.url()).pathname, 'le PATCH vise B').toBe(`${API}/sav/tickets/${idB}/`)
  const corps = req.postDataJSON()
  expect([corps.priorite, corps.description, corps.instructions], 'corps du PATCH = champs de B')
    .toEqual(['normale', `Panneau fissuré ${m}`, `Accès par le portail ${m}`])
  await expect(toast(p, 'Ticket mis à jour').first(), 'toast de succès').toBeVisible({ timeout: 30_000 })
  expect(await champsTicket([idA, idB]), 'base : A et B gardent chacun leurs champs').toEqual([
    ['urgente', `Onduleur HS ${m}`, `Couper le disjoncteur ${m}`],
    ['normale', `Panneau fissuré ${m}`, `Accès par le portail ${m}`],
  ])
  const ordre = await p.getByRole('row').filter({ hasText: `25-${m}` }).allInnerTexts()
  expect(ordre.length, 'les 2 lignes du jeu').toBe(2)
  const bApresA = ordre.findIndex((t) => t.includes(B)) > ordre.findIndex((t) => t.includes(A))
  await sortirDuChamp()
  await p.keyboard.press(bApresA ? 'k' : 'j')
  await montre(A, `Onduleur HS ${m}`, 'Urgente', `Couper le disjoncteur ${m}`, 'touche vers A')
  await sortirDuChamp()
  await p.keyboard.press(bApresA ? 'j' : 'k')
  await montre(B, `Panneau fissuré ${m}`, 'Normale', `Accès par le portail ${m}`, 'touche vers B')
  const retouche = `Panneau fissuré ${m} — retouche non enregistrée`
  await champ.description.fill(retouche)
  dem.prochaine = 'rester'
  await ligne(A).getByText(A).click()
  await expect.poll(() => dem.vues, { message: 'clic sur A : la demande est posée' }).toBe(1)
  await expect(fiche, 'rester (clic) : toujours B').toHaveAttribute('aria-label', `Détail du ticket ${B}`)
  await expect(champ.description, 'rester (clic) : saisie gardée').toHaveValue(retouche)
  await sortirDuChamp()
  dem.prochaine = 'rester'
  await p.keyboard.press(bApresA ? 'k' : 'j')
  await expect.poll(() => dem.vues, { message: 'touche vers A : la demande est posée' }).toBe(2)
  await expect(fiche, 'rester (clavier) : toujours B').toHaveAttribute('aria-label', `Détail du ticket ${B}`)
  await expect(champ.description, 'rester (clavier) : saisie gardée').toHaveValue(retouche)
  await cliche(p, 'PF12.1-AERR25', 2)
  dem.prochaine = 'quitter'
  await ligne(A).getByText(A).click()
  await expect.poll(() => dem.vues).toBe(3)
  await montre(A, `Onduleur HS ${m}`, 'Urgente', `Couper le disjoncteur ${m}`, 'quitter vers A')
  expect(patchs.length, 'un seul PATCH en tout (celui de B)').toBe(1)
  expect(await champsTicket([idA, idB]), 'base relue : champs d\'origine').toEqual([
    ['urgente', `Onduleur HS ${m}`, `Couper le disjoncteur ${m}`],
    ['normale', `Panneau fissuré ${m}`, `Accès par le portail ${m}`],
  ])
  await p.reload()
  const l2 = await listeTickets(p, m)
  await l2.ligne(B).getByText(B).click({ timeout: 60_000 })
  await expect(l2.fiche).toHaveAttribute('aria-label', `Détail du ticket ${B}`)
  await expect(l2.champ.description, 'après rechargement : description d\'origine de B').toHaveValue(`Panneau fissuré ${m}`)
  await expect(l2.champ.priorite).toContainText('Normale')
  await auRepos(p)
})

// ═══ PF12.1 — AERR25 (Then, 3ᵉ clause) + AERR151 : la boîte « Annuler ce ticket ? » de la fiche B nomme B ═══
etape('PF12.1-AERR25-annulation', ['AERR25', 'AERR151'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const A = `SAV-A25-${m}`
  const B = `SAV-B25-${m}`
  const ids = await ticketsDe(m, [
    { ref: A, priorite: 'urgente', description: `Onduleur HS ${m}` },
    { ref: B, priorite: 'normale', description: `Panneau fissuré ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const re = await compteRole('aerr151re', 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, re.nom)
  const { ligne, fiche, sortirDuChamp } = await listeTickets(p, m)
  const boite = p.getByRole('alertdialog')
  const verifierBoite = async (quand) => {
    await fiche.getByRole('button', { name: 'Annuler le ticket' }).click()
    await expect(boite, `${quand} : titre inchangé`).toContainText('Annuler ce ticket ?')
    await expect(boite, `${quand} : la boîte nomme B`).toContainText(`Le ticket ${B} sera marqué annulé`, { timeout: 5_000 })
    await expect(boite, `${quand} : jamais A`).not.toContainText(A)
  }
  // Clic : fiche A puis B.
  await ligne(A).getByText(A).click({ timeout: 60_000 })
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${A}`)
  await ligne(B).getByText(B).click()
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${B}`)
  await verifierBoite('clic A → B')
  await cliche(p, 'PF12.1-AERR25-annulation', 'clic')
  await p.keyboard.press('Escape')
  await expect(boite, 'Échap : boîte refermée').toHaveCount(0, { timeout: 15_000 })
  await expect(fiche, 'Échap : la fiche B reste ouverte').toHaveAttribute('aria-label', `Détail du ticket ${B}`)
  // Clavier : J/K vers A puis retour sur B.
  const ordre = await p.getByRole('row').filter({ hasText: `25-${m}` }).allInnerTexts()
  const bApresA = ordre.findIndex((t) => t.includes(B)) > ordre.findIndex((t) => t.includes(A))
  await sortirDuChamp()
  await p.keyboard.press(bApresA ? 'k' : 'j')
  await expect(fiche, 'touche vers A').toHaveAttribute('aria-label', `Détail du ticket ${A}`)
  await sortirDuChamp()
  await p.keyboard.press(bApresA ? 'j' : 'k')
  await expect(fiche, 'touche vers B').toHaveAttribute('aria-label', `Détail du ticket ${B}`)
  await verifierBoite('J/K A → B')
  await cliche(p, 'PF12.1-AERR25-annulation', 'clavier')
  await p.keyboard.press('Escape')
  await expect(boite).toHaveCount(0, { timeout: 15_000 })
  expect(await py(`from apps.sav.models import Ticket
sortie([t.annule for t in Ticket.objects.filter(pk__in=${J(ids.tickets)})])`), 'base : aucun ticket annulé').toEqual([false, false])
})

// ═══ PF12.1 — AERR152 : « Mettre à jour » / « Corriger » de la fiche équipement seulement sous equipement_gerer ═══
etape('PF12.1-AERR152', ['AERR152'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const re = await compteRole('aerr152re', 'Responsable')
  const tr = await compteRole('aerr152tr', 'Technicien responsable')
  expect([re.perms.includes('equipement_gerer'), re.perms.includes('equipement_voir')], 'Responsable : voir sans gérer').toEqual([false, true])
  expect(tr.perms.includes('equipement_gerer'), 'Technicien responsable : gère les équipements').toBe(true)
  const serie = `SN-4471-${m}`
  const ids = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
i = Installation.objects.create(company_id=${SOC}, reference=${J(`AERR152-${m}`)}, client=cl)
pr = Produit.objects.create(company_id=${SOC}, nom=${J(`Onduleur AERR152 ${m}`)}, prix_vente=100)
e = Equipement.objects.create(company_id=${SOC}, produit=pr, installation=i, numero_serie=${J(serie)}, created_by_id=${tr.id})
sortie(dict(client=cl.pk, inst=i.pk, produit=pr.pk, eq=e.pk))`)
  apres.push(() => py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
Equipement.objects.filter(pk=${ids.eq}).delete()
Installation.objects.filter(pk=${ids.inst}).delete()
Produit.objects.filter(pk=${ids.produit}).delete()
Client.objects.filter(pk=${ids.client}).delete()`))
  const ouvrirFiche = async (p) => {
    await p.goto('/equipements')
    await p.getByPlaceholder('Rechercher (série, produit, chantier, client)…').fill(`AERR152 ${m}`, { timeout: 60_000 })
    const ligne = p.getByRole('row').filter({ hasText: serie })
    await expect(ligne, 'équipement listé').toBeVisible({ timeout: 60_000 })
    await ligne.getByText(serie).click()
    const fiche = p.getByRole('dialog').filter({ hasText: 'Équipement —' })
    await expect(fiche, 'fiche ouverte').toBeVisible({ timeout: 30_000 })
    return fiche
  }
  // 1) Responsable (sans equipement_gerer) : ni « Mettre à jour » ni « Corriger » ; « Fermer » reste ; aucun 403.
  const ecritures = []
  const navigateur = page.context().browser()
  const { p: pR } = await ecran(page, suivi, testInfo, re.nom)
  pR.on('request', (q) => { if (['PATCH', 'PUT', 'POST'].includes(q.method()) && /\/sav\/equipements\//.test(q.url())) ecritures.push(q.url()) })
  const ficheR = await ouvrirFiche(pR)
  await expect(ficheR.locator('button:text-is("Fermer")'), '« Fermer » reste').toBeVisible()
  await expect(ficheR.getByRole('button', { name: 'Mettre à jour' }), 'sans equipement_gerer : pas de « Mettre à jour »').toHaveCount(0)
  await expect(ficheR.getByRole('button', { name: 'Corriger' }), 'sans equipement_gerer : pas de « Corriger »').toHaveCount(0)
  await auRepos(pR)
  await cliche(pR, 'PF12.1-AERR152', 'responsable')
  expect(ecritures, 'aucune écriture tentée').toEqual([])
  await pR.reload()
  const ficheR2 = await ouvrirFiche(pR)
  await expect(ficheR2.getByRole('button', { name: 'Mettre à jour' }), 'après rechargement : toujours absent').toHaveCount(0)
  await expect(ficheR2.getByRole('button', { name: 'Corriger' })).toHaveCount(0)
  await auRepos(pR)
  await pR.close()
  // 2) Technicien responsable (equipement_gerer) : les deux boutons ; « Mettre à jour » ⇒ 200.
  const ctx = await navigateur.newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', viewport: { width: 1600, height: 1000 },
  })
  contextes.push(ctx)
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: tr.nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) for (const v of listeDe(await visites.json())) if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
  const pT = suivi.surveiller(await ctx.newPage())
  const ficheT = await ouvrirFiche(pT)
  await expect(ficheT.getByRole('button', { name: 'Corriger' }), 'avec equipement_gerer : « Corriger »').toBeVisible()
  const maj = ficheT.getByRole('button', { name: 'Mettre à jour' })
  await expect(maj, 'avec equipement_gerer : « Mettre à jour »').toBeVisible()
  await ficheT.locator('label:text-is("Note") + textarea').fill(`Note AERR152 ${m}`)
  const [rep] = await Promise.all([
    pT.waitForResponse((x) => ['PATCH', 'PUT'].includes(x.request().method()) && new URL(x.url()).pathname === `${API}/sav/equipements/${ids.eq}/`, T),
    maj.click(),
  ])
  expect(rep.status(), `« Mettre à jour » : ${(await rep.text()).slice(0, 200)}`).toBe(200)
  await expect(toast(pT, 'Équipement mis à jour').first()).toBeVisible({ timeout: 30_000 })
  await cliche(pT, 'PF12.1-AERR152', 'technicien-responsable')
  expect(await py(`from apps.sav.models import Equipement
sortie(Equipement.objects.get(pk=${ids.eq}).note)`), 'base : note enregistrée').toBe(`Note AERR152 ${m}`)
  await auRepos(pT)
})

// ══════════════════════════════ APPROBATIONS — AERR125 + AERR153 ══════════════════════════════

const CREER = /\/api\/django\/automation\/approval-delegations\/$/
const delegationsDe = (ids) => py(`from apps.automation.models import ApprovalDelegation
n = timezone.now()
sortie([dict(id=d.pk, delegant=d.delegant_id, suppleant=d.suppleant_id, active=d.date_debut <= n <= d.date_fin) for d in ApprovalDelegation.objects.filter(delegant_id__in=${J(ids)}).order_by('pk')])`)
const retirerDelegations = (ids) => py(`from apps.automation.models import ApprovalDelegation
ApprovalDelegation.objects.filter(delegant_id__in=${J(ids)}).delete()`)

/** Onglet Délégations de /approbations + choix du suppléant et d'une période d'un jour (aujourd'hui). */
function ecranDelegations(p, sup) {
  const periode = p.locator('#delegation-periode')
  return {
    periode,
    ligneActive: p.locator('li').filter({ hasText: sup.nom }).filter({ hasText: 'Active' }),
    ouvrir: async () => {
      await p.goto('/approbations')
      await p.getByRole('tab', { name: 'Délégations' }).click({ timeout: 60_000 })
      await expect(periode).toBeVisible({ timeout: 30_000 })
    },
    choisir: async () => {
      await p.locator('#delegation-suppleant').click()
      await p.getByRole('option', { name: sup.nom, exact: true }).click()
      await periode.click()
      const jour = p.locator('[role="gridcell"][aria-current="date"]')
      await jour.click()
      await jour.click()
      await expect(periode, 'période d\'un seul jour choisie').toContainText('→')
    },
  }
}

// ═══ PF12.5 — AERR125 + AERR153 : délégation d'un seul jour ⇒ fin 23:59:59.999 locale, « Active » ; 201 sans `delegant` ═══
// Rejeu de l'étape PF12.5-AERR125 d'aerr4.spec.js (sortie d'`etapeDefaut`, clause « Preuve en direct » d'AERR153).
etape('PF12.5-AERR125', ['AERR125', 'AERR153'], async ({ page, suivi, testInfo }) => {
  const ad = await compteRole('aerr125ad', 'Administrateur')
  const sup = await compteRole('aerr125su', 'Commercial')
  apres.push(() => retirerDelegations([ad.id]))
  const { p } = await ecran(page, suivi, testInfo, ad.nom)
  const d = ecranDelegations(p, sup)
  const attendu = await p.evaluate(() => {
    const a = new Date(); a.setHours(0, 0, 0, 0)
    const f = new Date(); f.setHours(23, 59, 59, 999)
    return [a.toISOString(), f.toISOString()]
  })
  await d.ouvrir()
  // 1) Refus 400 {date_fin} servi (injecté) ⇒ message SOUS le sélecteur de période, saisie gardée, rien créé.
  const motif = 'La date de fin est refusée (rejeu AERR125).'
  const refus = await panne(p, suivi, CREER, { statut: 400, methode: 'POST', corps: { date_fin: [motif] } })
  await d.choisir()
  const [reqRefus] = await Promise.all([
    p.waitForRequest((q) => q.method() === 'POST' && CREER.test(q.url())),
    p.getByRole('button', { name: 'Déléguer' }).click(),
  ])
  const corpsRefus = reqRefus.postDataJSON()
  expect([corpsRefus.date_debut, corpsRefus.date_fin], 'un seul jour : début 00:00 et fin 23:59:59.999 locales').toEqual(attendu)
  await expect(p.locator('#delegation-periode-error'), 'le refus est rendu sous la période').toContainText(motif, { timeout: 30_000 })
  await expect(d.periode, 'saisie de la période conservée').toContainText('→')
  expect(refus.hits.n).toBe(1)
  await cliche(p, 'PF12.5-AERR125', 'refus-date-fin')
  await refus.lever()
  // 2) Création RÉELLE (serveur) avec la même saisie, corps sans `delegant` ⇒ 201, délégant = l'appelant, « Active ».
  const [req] = await Promise.all([
    p.waitForRequest((q) => q.method() === 'POST' && CREER.test(q.url())),
    p.getByRole('button', { name: 'Déléguer' }).click(),
  ])
  const corps = req.postDataJSON()
  expect([corps.date_debut, corps.date_fin], 'création réelle : mêmes bornes').toEqual(attendu)
  expect('delegant' in corps, 'le corps envoyé ne porte pas `delegant`').toBe(false)
  const rep = await req.response()
  const texteRep = await rep.text()
  expect(rep.status(), `création réelle : ${texteRep.slice(0, 300)} (corps envoyé ${J(corps)})`).toBe(201)
  expect(JSON.parse(texteRep).delegant, 'réponse : délégant = l\'appelant').toBe(ad.id)
  await expect(toast(p, 'Délégation créée.').first()).toBeVisible({ timeout: 30_000 })
  await expect(d.ligneActive, 'la délégation est listée « Active » (en cours)').toBeVisible({ timeout: 30_000 })
  await cliche(p, 'PF12.5-AERR125', 'delegation-active')
  const base = await py(`from apps.automation.models import ApprovalDelegation
n = timezone.now()
sortie([dict(debut=d.date_debut.timestamp() * 1000, fin=d.date_fin.timestamp() * 1000, active=d.date_debut <= n <= d.date_fin) for d in ApprovalDelegation.objects.filter(delegant_id=${ad.id})])`)
  expect(base.length, 'en base : une délégation').toBe(1)
  expect([Math.round(base[0].debut), Math.round(base[0].fin)], 'en base : bornes envoyées').toEqual([Date.parse(attendu[0]), Date.parse(attendu[1])])
  expect(base[0].active, 'en base : en cours maintenant').toBe(true)
  const relue = listeDe(await lireJson(await p.request.get(`${API}/automation/approval-delegations/`, T), 'délégations'))
  expect(relue.filter((x) => x.delegant === ad.id).length, 'GET relu : la délégation, délégant = l\'appelant').toBe(1)
  await p.reload()
  await p.getByRole('tab', { name: 'Délégations' }).click({ timeout: 60_000 })
  await expect(d.ligneActive, 'après rechargement : « Active »').toBeVisible({ timeout: 30_000 })
})

// ═══ PF12.5 — AERR153 : un RESPONSABLE (palier responsable) délègue à l'écran ⇒ 201, délégant = lui ; un `delegant`
// envoyé par un responsable est gardé (route réelle, sa session) ═══
etape('PF12.5-AERR153-responsable', ['AERR153'], async ({ page, suivi, testInfo }) => {
  const re = await compteRole('aerr153re', 'Responsable')
  const sup = await compteRole('aerr153su', 'Commercial')
  const tiers = await compteRole('aerr153ti', 'Commercial')
  expect(re.tier, 'palier responsable').toBe('responsable')
  apres.push(() => retirerDelegations([re.id, tiers.id]))
  const { p } = await ecran(page, suivi, testInfo, re.nom)
  const d = ecranDelegations(p, sup)
  await d.ouvrir()
  await d.choisir()
  const [req] = await Promise.all([
    p.waitForRequest((q) => q.method() === 'POST' && CREER.test(q.url())),
    p.getByRole('button', { name: 'Déléguer' }).click(),
  ])
  expect('delegant' in req.postDataJSON(), 'le corps envoyé ne porte pas `delegant`').toBe(false)
  const rep = await req.response()
  expect(rep.status(), `« Déléguer » : ${(await rep.text()).slice(0, 300)}`).toBe(201)
  await expect(toast(p, 'Délégation créée.').first(), 'toast « Délégation créée. »').toBeVisible({ timeout: 30_000 })
  await expect(d.ligneActive, 'ligne « en cours » (Active) listée').toBeVisible({ timeout: 30_000 })
  await cliche(p, 'PF12.5-AERR153-responsable', 'delegation-active')
  expect((await delegationsDe([re.id])).map((x) => [x.delegant, x.suppleant, x.active]), 'base : délégant = le responsable')
    .toEqual([[re.id, sup.id, true]])
  // Un responsable qui envoie `delegant` le garde (même route, sa session).
  const now = new Date()
  const fin = new Date(now.getTime() + 3600_000)
  const pour = await p.request.post(`${API}/automation/approval-delegations/`, {
    ...T, data: { delegant: tiers.id, suppleant: sup.id, date_debut: now.toISOString(), date_fin: fin.toISOString() },
  })
  expect(pour.status(), `responsable + delegant tiers : ${(await pour.text()).slice(0, 200)}`).toBe(201)
  expect((await pour.json()).delegant, 'délégant envoyé gardé').toBe(tiers.id)
  await p.reload()
  await p.getByRole('tab', { name: 'Délégations' }).click({ timeout: 60_000 })
  await expect(d.ligneActive.first(), 'après rechargement : « Active »').toBeVisible({ timeout: 30_000 })
})

// ═══ PF12.5 — AERR153 : un EMPLOYÉ (palier limité) — POST sans `delegant` par la route réelle, sa session ⇒ 201,
// délégant = lui ; un `delegant` tiers envoyé est ramené à lui-même ═══
etape('PF12.5-AERR153-employe-api', ['AERR153'], async ({ page, testInfo }) => {
  const em = await compteRole('aerr153em', 'Commercial')
  const sup = await compteRole('aerr153es', 'Commercial')
  const tiers = await compteRole('aerr153et', 'Commercial')
  expect(em.tier, 'palier limité').not.toMatch(/^(admin|responsable)$/)
  apres.push(() => retirerDelegations([em.id, tiers.id]))
  const ctx = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] } })
  contextes.push(ctx)
  await connexionApi(ctx.request, { username: em.nom, password: MDP_ESSAI })
  const a = new Date(); a.setHours(0, 0, 0, 0)
  const f = new Date(); f.setHours(23, 59, 59, 999)
  const sans = await ctx.request.post(`${API}/automation/approval-delegations/`, {
    ...T, data: { suppleant: sup.id, date_debut: a.toISOString(), date_fin: f.toISOString() },
  })
  expect(sans.status(), `employé sans delegant : ${(await sans.text()).slice(0, 200)}`).toBe(201)
  expect((await sans.json()).delegant, 'délégant = l\'employé').toBe(em.id)
  const autre = await ctx.request.post(`${API}/automation/approval-delegations/`, {
    ...T, data: { delegant: tiers.id, suppleant: sup.id, date_debut: a.toISOString(), date_fin: f.toISOString() },
  })
  expect(autre.status(), `employé + delegant tiers : ${(await autre.text()).slice(0, 200)}`).toBe(201)
  expect((await autre.json()).delegant, 'delegant tiers ramené à l\'employé').toBe(em.id)
  const relue = listeDe(await lireJson(await ctx.request.get(`${API}/automation/approval-delegations/`, T), 'délégations'))
  expect(relue.filter((x) => x.delegant === em.id).length, 'GET relu : deux délégations, délégant = l\'employé').toBe(2)
  expect((await delegationsDe([tiers.id])).length, 'base : aucune délégation au nom du tiers').toBe(0)
})

// DIAGNOSTIC (hors enregistrement) : l'écran Délégations sous un employé — la liste des suppléants vient de GET
// /users/ (palier admin/responsable) ; consigné au rapport, jamais une étape.
test('diagnostic — /approbations › Délégations sous un employé', async ({ page }, testInfo) => {
  const em = await compteRole('aerr153dg', 'Commercial')
  const ctx = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block' })
  contextes.push(ctx)
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: em.nom, password: MDP_ESSAI })
  const p = await ctx.newPage()
  const reps = []
  p.on('response', (r) => { if (/\/api\/django\/(users|automation)\//.test(r.url())) reps.push(`${r.request().method()} ${new URL(r.url()).pathname} → ${r.status()}`) })
  await p.goto('/approbations')
  await p.waitForTimeout(4_000)
  const onglet = await p.getByRole('tab', { name: 'Délégations' }).count()
  if (onglet) await p.getByRole('tab', { name: 'Délégations' }).click().catch(() => undefined)
  await p.waitForTimeout(3_000)
  const toasts = await p.locator('[data-sonner-toast]').allInnerTexts()
  let options = -1
  if (await p.locator('#delegation-suppleant').count()) {
    await p.locator('#delegation-suppleant').click().catch(() => undefined)
    options = await p.getByRole('option').count()
  }
  console.log(`[DIAG-AERR153-employe] url=${p.url()} onglet=${onglet} options=${options} toasts=${J(toasts)} reponses=${J(reps)}`)
})

// ══════════════════════════════ ANALYSE — AERR130 + AERR154 ══════════════════════════════

// ═══ PF12.3 — AERR130 + AERR154 : /reporting/classeurs, « Supprimer » n'ouvre pas la fiche ; « Annuler » laisse sur
// la liste ; suppression puis relecture coupée ⇒ le classeur restant reste + avis ═══
etape('PF12.3-AERR130-classeurs', ['AERR130', 'AERR154'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ad = await compteRole('aerr154ad', 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, ad.nom)
  const cls = []
  for (const x of ['Suivi CA', 'Marge']) cls.push(await lireJson(await p.request.post(`${API}/reporting/classeurs/`, { ...T, data: { titre: `${x} AERR154 ${m}`, cellules: {}, liens: {} } }), `classeur ${x}`))
  apres.push(() => py(`from apps.reporting.models import Classeur
Classeur.objects.filter(titre__contains=${J(m)}).delete()`))
  const LISTE = /\/api\/django\/reporting\/classeurs\/(\?|$)/
  const ligne = (x) => p.getByRole('row').filter({ hasText: `${x} AERR154 ${m}` })
  const avis = p.getByRole('status').filter({ hasText: 'Liste pas à jour' })
  const boite = p.getByRole('alertdialog')
  await p.goto('/reporting/classeurs')
  await expect(ligne('Suivi CA')).toBeVisible({ timeout: 60_000 })
  await expect(ligne('Marge')).toBeVisible()
  // 1) « Supprimer » puis « Annuler » : la boîte s'ouvre, l'URL ne bouge pas, rien n'est supprimé.
  await ligne('Suivi CA').getByRole('button', { name: 'Supprimer' }).click()
  await expect(boite, 'boîte de confirmation nommée').toContainText(`Suivi CA AERR154 ${m}`, { timeout: 15_000 })
  await expect(p, '« Supprimer » : on reste sur la liste').toHaveURL(/\/reporting\/classeurs$/)
  await cliche(p, 'PF12.3-AERR130-classeurs', 'boite-ouverte')
  await boite.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(boite).toHaveCount(0, { timeout: 15_000 })
  await expect(p, '« Annuler » : toujours la liste').toHaveURL(/\/reporting\/classeurs$/)
  await expect(ligne('Suivi CA'), '« Annuler » ne supprime rien').toBeVisible()
  await expect(ligne('Marge')).toBeVisible()
  expect((await lignes(p.request, `${API}/reporting/classeurs/`)).filter((c) => cls.some((k) => k.id === c.id)).length, 'en base : les deux classeurs').toBe(2)
  // 2) « Supprimer » confirmé, relecture coupée : liste gardée + avis, jamais la fiche « Classeur introuvable. ».
  let coupure = await panne(p, suivi, LISTE)
  await ligne('Suivi CA').getByRole('button', { name: 'Supprimer' }).click()
  await expect(boite).toContainText(`Suivi CA AERR154 ${m}`, { timeout: 15_000 })
  await boite.getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect(toast(p, 'Classeur supprimé.').first()).toBeVisible({ timeout: 30_000 })
  await expect(p, 'on reste sur la liste des classeurs').toHaveURL(/\/reporting\/classeurs$/)
  await expect(p.getByText('Classeur introuvable.'), 'aucune fiche « Classeur introuvable. »').toHaveCount(0)
  await expect.poll(() => coupure.hits.n, { message: 'la relecture après suppression a échoué', timeout: 30_000 }).toBeGreaterThan(0)
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(ligne('Marge'), 'le classeur restant est toujours listé').toBeVisible()
  await expect(ligne('Suivi CA'), 'la ligne supprimée est retirée localement').toHaveCount(0)
  await expect(p.getByText('Aucun classeur', { exact: true }), 'jamais « Aucun classeur »').toHaveCount(0)
  await cliche(p, 'PF12.3-AERR130-classeurs', 'relecture-coupee')
  const restants = (await lignes(p.request, `${API}/reporting/classeurs/`)).map((c) => c.id)
  expect([restants.includes(cls[0].id), restants.includes(cls[1].id)], 'en base : « Suivi CA » supprimé, « Marge » présent').toEqual([false, true])
  await coupure.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis).toHaveCount(0, { timeout: 30_000 })
  await expect(ligne('Marge'), 'relecture : « Marge » seul').toBeVisible()
  await expect(ligne('Suivi CA')).toHaveCount(0)
  await expect(p.getByText('Classeur introuvable.')).toHaveCount(0)
  // Persistance : recharger sous coupure ⇒ avis + Réessayer, jamais « Aucun classeur ».
  coupure = await panne(p, suivi, LISTE)
  await p.reload()
  await expect(avis, 'premier chargement rejeté : avis').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('Aucun classeur', { exact: true })).toHaveCount(0)
})

// ═══ PF12.3 — AERR130 (même règle, « Aucune configuration ») : /reporting/dashboards, suppression puis relecture coupée ═══
// Rejeu de l'étape PF12.3-AERR130-configurations d'aerr4.spec.js (sortie d'`etapeDefaut`).
etape('PF12.3-AERR130-configurations', ['AERR130'], async ({ page, suivi, testInfo }) => {
  const ad = await compteRole('aerr130cf', 'Administrateur')
  const u1 = await compteRole('aerr130u1', 'Commercial')
  const u2 = await compteRole('aerr130u2', 'Commercial')
  const { p } = await ecran(page, suivi, testInfo, ad.nom)
  const cfg = []
  for (const u of [u1, u2]) cfg.push(await lireJson(await p.request.post(`${API}/reporting/dashboard-config/`, { ...T, data: { user: u.id, cards: ['kpis'] } }), `configuration ${u.nom}`))
  apres.push(() => py(`from apps.reporting.models import DashboardConfig
DashboardConfig.objects.filter(pk__in=${J(cfg.map((c) => c.id))}).delete()`))
  const LISTE = /\/api\/django\/reporting\/dashboard-config\/(\?|$)/
  const ligne = (u) => p.getByRole('row').filter({ hasText: u.nom })
  const avis = p.getByRole('status').filter({ hasText: 'Configurations pas à jour' })
  await p.goto('/reporting/dashboards')
  await expect(ligne(u1)).toBeVisible({ timeout: 60_000 })
  await expect(ligne(u2)).toBeVisible()
  let coupure = await panne(p, suivi, LISTE)
  await ligne(u1).getByRole('button', { name: 'Supprimer' }).click()
  const boite = p.getByRole('alertdialog')
  await expect(boite).toContainText(u1.nom, { timeout: 15_000 })
  await boite.getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect(toast(p, 'Configuration supprimée.').first()).toBeVisible({ timeout: 30_000 })
  await expect.poll(() => coupure.hits.n, { message: 'la relecture après suppression a échoué', timeout: 30_000 }).toBeGreaterThan(0)
  await expect(avis, 'avis « Configurations pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(ligne(u2), 'la configuration restante est toujours listée').toBeVisible()
  await expect(ligne(u1)).toHaveCount(0)
  await expect(p.getByText('Aucune configuration', { exact: true })).toHaveCount(0)
  await cliche(p, 'PF12.3-AERR130-configurations', 'relecture-coupee')
  const restants = (await lignes(p.request, `${API}/reporting/dashboard-config/`)).map((c) => c.id)
  expect([restants.includes(cfg[0].id), restants.includes(cfg[1].id)], 'en base : 1re supprimée, 2e présente').toEqual([false, true])
  await coupure.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis).toHaveCount(0, { timeout: 30_000 })
  coupure = await panne(p, suivi, LISTE)
  await p.reload()
  await expect(avis, 'premier chargement rejeté : avis').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('Aucune configuration', { exact: true })).toHaveCount(0)
})
