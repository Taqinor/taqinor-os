// Preuves en direct du groupe AERR (parcours PF12 « erreurs, pertes de saisie et gestes dangereux à l'écran »,
// dossier docs/audits/2026-11-11-parcours-PF12.md), lot 1 : SAV (AERR25-27, 32, 129), chantiers et interventions
// (AERR28, 29, 34, 36, 38, 77, 78), stock et réglages (AERR33, 35, 37, 124). Chaque étape joue le geste À L'ÉCRAN
// sous un compte d'un rôle LIVRÉ du registre (`permissions_registre.py`, relu par son nom dans la société démo),
// AFFIRME ce que la clause nomme (champs, demande, confirmation nommée, avis « pas à jour » + « Réessayer »,
// bouton désactivé, toast « Annuler »), relit la base ou l'API, puis recharge et réaffirme. Les échecs sont
// PROVOQUÉS (route Playwright déclarée d'abord par `suivi.attendre`), jamais supposés. Données propres créées
// par le shell Django et retirées après la capture.
//
// La « demande » des gardes de saisie (AERR25, 27, 37, 38) est, par conception de la tâche, la confirmation
// native de `confirmLeaveIfDirty` (`frontend/src/ui/useDirtyGuard.js`) : l'étape l'ATTEND (message exact,
// réponse choisie « rester » / « quitter ») ; tout AUTRE dialogue natif reste un incident de l'oracle 4.
import { test, expect } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { RACINE, cheminCapture } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi } from '../helpers.js'

// AERR25 : ROUGE sur le runner le 14/11/2026 (run 43539824114, sha 26f066d15) pour DÉFAUT PRODUIT — la fiche suit
// bien la sélection (clic, J/K, PATCH de B avec les champs de B, demande avant de quitter une saisie : étape
// PF12.1-AERR25 verte), mais la 3ᵉ clause du Then n'est pas tenue : la boîte « Annuler ce ticket ? » de la fiche B
// ne nomme pas B (`TicketsPage.jsx::TicketDetailCorps`, titre et description fixes). Étapes inchangées, rejouées
// seulement sous AERR_ROUGES=1 (hors de l'enregistrement) tant que la boîte n'est pas corrigée.
const ROUGES = process.env.AERR_ROUGES === '1'
const G = 'AERR'
const etape = groupe(G, [
  ...(ROUGES ? ['AERR25'] : []), 'AERR26', 'AERR27', 'AERR32', 'AERR129',
  'AERR28', 'AERR29', 'AERR34', 'AERR36', 'AERR38', 'AERR77', 'AERR78',
  'AERR33', 'AERR35', 'AERR37', 'AERR124',
])
const etapeRouge = ROUGES ? etape : () => undefined
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
test.afterEach(async () => {
  for (const c of contextes.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()

/** Compte d'essai du rôle LIVRÉ `nomRole` (rôle système de la société démo) ; renvoie son id. */
const compteRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
assert r.est_systeme, 'rôle non système'
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.first_name = 'Essai'; u.last_name = ${J(nomRole)}; u.save(update_fields=['first_name', 'last_name'])
sortie(u.id)`)

/** Compte terrain neuf : « Ma journée » ouvre d'abord la notice de géolocalisation (« J'ai lu et j'accepte »,
 *  run 43539824114). Accord du compte d'essai donné par sa vraie route avant l'écran (donnée de départ). */
async function accordGps(p) {
  const lu = await p.request.get(`${API}/installations/gps-consentements/mon-consentement/`, T)
  expect(lu.ok(), `consentement lu : HTTP ${lu.status()}`).toBe(true)
  if ((await lu.json())?.statut === 'actif') return
  const ok = await p.request.post(`${API}/installations/gps-consentements/mon-consentement/accepter/`, { ...T, data: {} })
  expect(ok.ok(), `consentement accepté : HTTP ${ok.status()} ${(await ok.text()).slice(0, 200)}`).toBe(true)
}

/** Écran du compte `nom` : contexte neuf (accueil et visites guidées vus, SW bloqué), session par la vraie route
 *  /token/, observé par les oracles. La page demo_admin de l'étape est refermée : la capture montre CET écran.
 *  Les dialogues natifs passent par `demandes` (seule la demande de saisie non enregistrée est attendue). */
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
    for (const v of await visites.json()) {
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

/** Échec PROVOQUÉ sur les requêtes `methode` de `regex` (déclaré à l'oracle d'abord) : 500 servi, ou coupure
 *  réseau (`'reseau'`) ; `retenue` (promesse) garde la requête EN COURS jusqu'à sa résolution. */
async function panne(p, suivi, regex, { statut = 500, retenue = null, methode = 'GET' } = {}) {
  suivi.attendre(regex, statut)
  const vues = []
  const h = async (route) => {
    if (route.request().method() !== methode) return route.fallback()
    vues.push(route.request().url())
    if (retenue) await retenue
    if (statut === 'reseau') return route.abort('failed')
    return route.fulfill({ status: statut, contentType: 'application/json', body: J({ detail: 'panne simulée (acceptation AERR)' }) })
  }
  await p.route(regex, h)
  return { vues, lever: () => p.unroute(regex, h) }
}

/** Requêtes `methode` vers `regex` émises par la page (preuve « aucun PATCH avant Confirmer »). */
function compter(p, methode, regex) {
  const vues = []
  p.on('request', (r) => { if (r.method() === methode && regex.test(r.url())) vues.push(r.url()) })
  return vues
}

/** Capture PENDANT que l'écran affirmé est visible (en plus de la capture de fin d'étape). */
async function capturer(p, id, n) {
  const chemin = join(RACINE, cheminCapture(G, `${id}-${n}`))
  mkdirSync(dirname(chemin), { recursive: true })
  await p.screenshot({ path: chemin, type: 'jpeg', quality: 60 })
}

/** Attend le repos réseau de l'écran (les oracles voient alors tout ce qu'il a demandé). */
const auRepos = (p) => p.waitForLoadState('networkidle').catch(() => undefined)

async function lire(r, url, quoi) {
  const rep = await r.get(`${API}${url}`, T)
  expect(rep.ok(), `${quoi} : HTTP ${rep.status()}`).toBe(true)
  return rep.json()
}

// ══════════════════════════════ SAV — /sav, /equipements, /production/* ══════════════════════════════

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
  // Clic sur un texte non interactif de la fiche : le focus quitte le champ (J/K redeviennent des raccourcis).
  const sortirDuChamp = () => fiche.getByText('Suivi, équipement, interventions, pièces et historique du ticket.').click()
  return { ligne, fiche, champ, sortirDuChamp }
}

// ═══ PF12.1 — AERR25 (S1) : la fiche suit le ticket sélectionné (clic, J/K), « Mettre à jour » n'écrit que B ═══
etapeRouge('PF12.1-AERR25', ['AERR25'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const A = `SAV-A25-${m}`
  const B = `SAV-B25-${m}`
  const ids = await ticketsDe(m, [
    { ref: A, priorite: 'urgente', description: `Onduleur HS ${m}`, instructions: `Couper le disjoncteur ${m}` },
    { ref: B, priorite: 'normale', description: `Panneau fissuré ${m}`, instructions: `Accès par le portail ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const [idA, idB] = ids.tickets
  const nom = `aerr25re_${m}`
  await compteRole(nom, 'Responsable')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
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
  // Vue scindée (≥ 1280 px) : fiche A ouverte, puis un clic sur la ligne B.
  await ligne(A).getByText(A).click()
  await montre(A, `Onduleur HS ${m}`, 'Urgente', `Couper le disjoncteur ${m}`, 'fiche A ouverte')
  await ligne(B).getByText(B).click()
  await montre(B, `Panneau fissuré ${m}`, 'Normale', `Accès par le portail ${m}`, 'clic sur B')
  await capturer(p, 'PF12.1-AERR25', 1)
  // « Mettre à jour » : UN PATCH, sur B, avec les champs de B.
  const [req] = await Promise.all([
    p.waitForRequest((r) => r.method() === 'PATCH' && /\/api\/django\/sav\/tickets\/\d+\/$/.test(r.url()), T),
    fiche.getByRole('button', { name: 'Mettre à jour' }).click(),
  ])
  expect(new URL(req.url()).pathname, 'le PATCH vise B').toBe(`${API}/sav/tickets/${idB}/`)
  const corps = req.postDataJSON()
  expect([corps.priorite, corps.description, corps.instructions], 'corps du PATCH = champs de B')
    .toEqual(['normale', `Panneau fissuré ${m}`, `Accès par le portail ${m}`])
  await expect(toast(p, 'Ticket mis à jour'), 'toast de succès').toBeVisible({ timeout: 30_000 })
  expect(await champsTicket([idA, idB]), 'base : A et B gardent chacun leurs champs').toEqual([
    ['urgente', `Onduleur HS ${m}`, `Couper le disjoncteur ${m}`],
    ['normale', `Panneau fissuré ${m}`, `Accès par le portail ${m}`],
  ])
  // J/K (focus hors champ) : la fiche suit la sélection clavier, dans l'ordre affiché.
  const ordre = await p.getByRole('row').filter({ hasText: `25-${m}` }).allInnerTexts()
  expect(ordre.length, 'les 2 lignes du jeu').toBe(2)
  const bApresA = ordre.findIndex((t) => t.includes(B)) > ordre.findIndex((t) => t.includes(A))
  await sortirDuChamp()
  await p.keyboard.press(bApresA ? 'k' : 'j')
  await montre(A, `Onduleur HS ${m}`, 'Urgente', `Couper le disjoncteur ${m}`, 'touche vers A')
  await sortirDuChamp()
  await p.keyboard.press(bApresA ? 'j' : 'k')
  await montre(B, `Panneau fissuré ${m}`, 'Normale', `Accès par le portail ${m}`, 'touche vers B')
  // Retouche NON enregistrée sur B : changer de sélection DEMANDE d'abord ; « rester » garde la saisie.
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
  await capturer(p, 'PF12.1-AERR25', 2)
  // « Quitter » : la fiche passe à A avec SES champs ; la retouche de B n'est écrite nulle part.
  dem.prochaine = 'quitter'
  await ligne(A).getByText(A).click()
  await expect.poll(() => dem.vues).toBe(3)
  await montre(A, `Onduleur HS ${m}`, 'Urgente', `Couper le disjoncteur ${m}`, 'quitter vers A')
  expect(patchs.length, 'un seul PATCH en tout (celui de B)').toBe(1)
  // Persistance : relire B en base puis à l'écran rechargé.
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

// ═══ PF12.1 — AERR25 (Then, 3ᵉ clause) : la boîte d'annulation de la fiche B nomme B ═══
etapeRouge('PF12.1-AERR25-annulation', ['AERR25'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const A = `SAV-A25-${m}`
  const B = `SAV-B25-${m}`
  const ids = await ticketsDe(m, [
    { ref: A, priorite: 'urgente', description: `Onduleur HS ${m}` },
    { ref: B, priorite: 'normale', description: `Panneau fissuré ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const nom = `aerr25an_${m}`
  await compteRole(nom, 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const { ligne, fiche } = await listeTickets(p, m)
  await ligne(A).getByText(A).click({ timeout: 60_000 })
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${A}`)
  await ligne(B).getByText(B).click()
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${B}`)
  await fiche.getByRole('button', { name: 'Annuler le ticket' }).click()
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'boîte d\'annulation ouverte').toContainText('Annuler ce ticket ?')
  await capturer(p, 'PF12.1-AERR25-annulation', 1)
  await expect(boite, 'la boîte d\'annulation nomme le ticket visé (B)').toContainText(B, { timeout: 5_000 })
})

// ═══ PF12.1 — AERR26 : modifier les instructions trace « Instructions : ancien → nouveau » à l'historique ═══
etape('PF12.1-AERR26', ['AERR26'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ref = `SAV-I26-${m}`
  const ancien = `Couper le disjoncteur avant intervention. ${m}`
  const nouveau = `Accès par le portail nord. ${m}`
  const ids = await ticketsDe(m, [{ ref, priorite: 'normale', description: `Onduleur ${m}`, instructions: ancien }])
  apres.push(() => retirerTickets(ids))
  const nom = `aerr26re_${m}`
  const uid = await compteRole(nom, 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const { ligne, fiche, champ } = await listeTickets(p, m)
  await ligne(ref).getByText(ref).click({ timeout: 60_000 })
  await expect(champ.instructions).toHaveValue(ancien)
  await champ.instructions.fill(nouveau)
  await fiche.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(toast(p, 'Ticket mis à jour')).toBeVisible({ timeout: 30_000 })
  const entree = fiche.locator('div.rounded-lg.bg-card').filter({ hasText: 'Instructions :' })
  await expect(entree, 'historique : une ligne « Instructions »').toHaveCount(1, { timeout: 30_000 })
  await expect(entree, 'ancien texte').toContainText(ancien)
  await expect(entree, 'nouveau texte').toContainText(nouveau)
  await entree.scrollIntoViewIfNeeded()
  await capturer(p, 'PF12.1-AERR26', 1)
  const journal = () => py(`from apps.sav.models import TicketActivity
sortie([[a.field_label, a.old_value, a.new_value, a.user_id] for a in TicketActivity.objects.filter(ticket_id=${ids.tickets[0]}, field='instructions')])`)
  expect(await journal(), 'base : une TicketActivity instructions ancien → nouveau, par le compte joué').toEqual([['Instructions', ancien, nouveau, uid]])
  // « Mettre à jour » sans changement : aucune ligne de plus.
  await fiche.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(toast(p, 'Ticket mis à jour')).toBeVisible({ timeout: 30_000 })
  await auRepos(p)
  expect((await journal()).length, 'PATCH sans changement : aucune ligne').toBe(1)
  // Persistance : écran rechargé, fiche rouverte, la ligne d'historique est là.
  await p.reload()
  const l2 = await listeTickets(p, m)
  await l2.ligne(ref).getByText(ref).click({ timeout: 60_000 })
  const e2 = l2.fiche.locator('div.rounded-lg.bg-card').filter({ hasText: 'Instructions :' })
  await expect(e2, 'après rechargement : la ligne est relue').toHaveCount(1, { timeout: 30_000 })
  await expect(e2).toContainText(nouveau)
  await expect(l2.champ.instructions).toHaveValue(nouveau)
  await e2.scrollIntoViewIfNeeded()
  await auRepos(p)
})

// ═══ PF12.1 — AERR27 : Échap / J / K se taisent sous une boîte ou dans une liste ouverte ; Échap demande ═══
etape('PF12.1-AERR27', ['AERR27'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const S1 = `SAV-127-${m}`
  const S2 = `SAV-227-${m}`
  const ids = await ticketsDe(m, [
    { ref: S1, priorite: 'normale', description: `Onduleur ${m}` },
    { ref: S2, priorite: 'normale', description: `Câble ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const nom = `aerr27re_${m}`
  await compteRole(nom, 'Responsable')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
  const { ligne, fiche, champ } = await listeTickets(p, m)
  await expect(ligne(S2)).toBeVisible({ timeout: 60_000 })
  await ligne(S1).getByText(S1).click()
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  const retouche = `Onduleur ${m} — retouche non enregistrée`
  await champ.description.fill(retouche)
  // 1) « Annuler ce ticket ? » ouverte, Échap : seule la boîte se ferme, aucune demande, fiche ouverte.
  await fiche.getByRole('button', { name: 'Annuler le ticket' }).click()
  const boite = p.getByRole('alertdialog')
  await expect(boite).toContainText('Annuler ce ticket ?')
  await p.keyboard.press('Escape')
  await expect(boite, 'Échap ferme la boîte').toBeHidden()
  await expect(fiche, 'la fiche reste ouverte').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(champ.description, 'saisie intacte').toHaveValue(retouche)
  expect(dem.vues, 'aucune demande : la fiche n\'a pas été visée').toBe(0)
  // 2) Liste Technicien ouverte, « k » puis « j » : la sélection ne change pas.
  await champ.technicien.click()
  const liste = p.getByRole('listbox')
  await expect(liste, 'liste Technicien ouverte').toBeVisible()
  await p.keyboard.press('k')
  await p.keyboard.press('j')
  await capturer(p, 'PF12.1-AERR27', 1)
  await expect(fiche, 'k / j dans la liste : même ticket').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await p.keyboard.press('Escape')
  await expect(liste, 'Échap ferme la liste').toBeHidden()
  await expect(fiche, 'Échap dans la liste : fiche ouverte').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(champ.description).toHaveValue(retouche)
  expect(dem.vues, 'aucune demande pendant la liste').toBe(0)
  // 3) Aucune boîte, focus sur un bouton, Échap : la demande d'abord ; « rester » garde fiche et saisie.
  await fiche.getByRole('button', { name: "Rapport d'intervention (PDF)" }).focus()
  dem.prochaine = 'rester'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.vues, { message: 'Échap sur la fiche modifiée : demande posée' }).toBe(1)
  await expect(fiche, 'rester : fiche ouverte').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(champ.description, 'rester : saisie gardée').toHaveValue(retouche)
  await capturer(p, 'PF12.1-AERR27', 2)
  // « quitter » : la fiche se ferme ; rien n'a été écrit.
  await fiche.getByRole('button', { name: "Rapport d'intervention (PDF)" }).focus()
  dem.prochaine = 'quitter'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.vues).toBe(2)
  await expect(fiche, 'quitter : fiche fermée').toHaveCount(0)
  expect(await champsTicket([ids.tickets[0]]), 'base : description non écrite').toEqual([['normale', `Onduleur ${m}`, '']])
  await p.reload()
  const l2 = await listeTickets(p, m)
  await l2.ligne(S1).getByText(S1).click({ timeout: 60_000 })
  await expect(l2.champ.description, 'après rechargement : description d\'origine').toHaveValue(`Onduleur ${m}`)
  await auRepos(p)
})

// ═══ PF12.1 — AERR32 : relecture en cours puis ratée après un enregistrement : lignes, tri et sélection gardés ═══
etape('PF12.1-AERR32-tickets', ['AERR32'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const S1 = `SAV-132-${m}`
  const S2 = `SAV-232-${m}`
  const ids = await ticketsDe(m, [
    { ref: S1, priorite: 'normale', description: `Onduleur ${m}` },
    { ref: S2, priorite: 'normale', description: `Câble ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const nom = `aerr32re_${m}`
  await compteRole(nom, 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const { ligne, fiche, champ } = await listeTickets(p, m)
  await expect(ligne(S1)).toBeVisible({ timeout: 60_000 })
  await expect(ligne(S2)).toBeVisible()
  const ordreAvant = await p.getByRole('row').filter({ hasText: `32-${m}` }).allInnerTexts()
  // Sélection groupée d'une ligne, puis fiche de l'autre.
  await ligne(S2).getByRole('checkbox').click()
  await expect(ligne(S2).getByRole('checkbox'), 'ligne S2 sélectionnée').toBeChecked()
  await ligne(S1).getByText(S1).click()
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await champ.description.fill(`Onduleur ${m} — corrigé`)
  let liberer
  const retenue = new Promise((r) => { liberer = r })
  const relecture = await panne(p, suivi, /\/api\/django\/sav\/tickets\/\?/, { retenue })
  await fiche.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(toast(p, 'Ticket mis à jour')).toBeVisible({ timeout: 30_000 })
  // Relecture EN COURS : lignes et sélection à l'écran, aucun squelette.
  await expect.poll(() => relecture.vues.length, { message: 'relecture lancée' }).toBeGreaterThan(0)
  await expect(ligne(S1), 'relecture en cours : S1 affichée').toBeVisible()
  await expect(ligne(S2), 'relecture en cours : S2 affichée').toBeVisible()
  await expect(ligne(S2).getByRole('checkbox'), 'relecture en cours : sélection gardée').toBeChecked()
  liberer()
  // Relecture REJETÉE : avis « Liste pas à jour » + Réessayer, lignes, tri et sélection gardés.
  const avis = p.getByRole('status').filter({ hasText: 'Liste pas à jour' })
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(ligne(S1)).toBeVisible()
  await expect(ligne(S2)).toBeVisible()
  await expect(ligne(S2).getByRole('checkbox'), 'sélection gardée').toBeChecked()
  expect(await p.getByRole('row').filter({ hasText: `32-${m}` }).count(), 'les 2 lignes').toBe(2)
  expect((await p.getByRole('row').filter({ hasText: `32-${m}` }).allInnerTexts()).map((t) => t.includes(S1)),
    'tri gardé').toEqual(ordreAvant.map((t) => t.includes(S1)))
  await expect(p.getByText('Chargement impossible'), 'jamais l\'erreur pleine').toHaveCount(0)
  await capturer(p, 'PF12.1-AERR32-tickets', 1)
  expect(await champsTicket([ids.tickets[0]]), 'base : enregistrement passé').toEqual([['normale', `Onduleur ${m} — corrigé`, '']])
  // « Réessayer » une fois le serveur revenu : l'avis part, les lignes restent.
  await relecture.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'relecture réussie : avis retiré').toHaveCount(0, { timeout: 30_000 })
  await expect(ligne(S1)).toBeVisible()
  await expect(ligne(S2)).toBeVisible()
  // Premier chargement rejeté (aucune ligne chargée) : l'erreur pleine avec Réessayer, pas l'état vide.
  const initiale = await panne(p, suivi, /\/api\/django\/sav\/tickets\/\?/)
  await p.reload()
  await expect(p.getByText('Chargement impossible'), 'premier chargement rejeté : erreur pleine').toBeVisible({ timeout: 60_000 })
  await expect(p.getByRole('button', { name: 'Réessayer' }).first()).toBeVisible()
  await expect(p.getByText('Aucun ticket ouvert'), 'jamais l\'état vide').toHaveCount(0)
  await initiale.lever()
  await p.getByRole('button', { name: 'Réessayer' }).first().click()
  await p.getByPlaceholder('Rechercher (référence, client, chantier, description)…').fill(`AERR Client ${m}`, { timeout: 60_000 })
  await expect(ligne(S1), 'après Réessayer : les lignes reviennent').toBeVisible({ timeout: 60_000 })
  await auRepos(p)
})

etape('PF12.1-AERR32-equipements', ['AERR32'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
i = Installation.objects.create(company_id=${SOC}, reference=${J(`AERR32-${m}`)}, client=cl)
pr = Produit.objects.create(company_id=${SOC}, nom=${J(`Onduleur AERR32 ${m}`)}, prix_vente=100)
eqs = [Equipement.objects.create(company_id=${SOC}, produit=pr, installation=i, numero_serie='SN32-%s-${m}' % n) for n in ('1', '2')]
sortie(dict(client=cl.pk, inst=i.pk, produit=pr.pk, eqs=[e.pk for e in eqs]))`)
  apres.push(() => py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
Equipement.objects.filter(pk__in=${J(ids.eqs)}).delete()
Installation.objects.filter(pk=${ids.inst}).delete()
Produit.objects.filter(pk=${ids.produit}).delete()
Client.objects.filter(pk=${ids.client}).delete()`))
  const nom = `aerr32eq_${m}`
  // Administrateur : le Responsable n'a pas `equipement_gerer` (« Mettre à jour » refusé, run 43539824114).
  await compteRole(nom, 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const ligne = (n) => p.getByRole('row').filter({ hasText: `SN32-${n}-${m}` })
  const ouvrir = async () => {
    await p.goto('/equipements')
    await p.getByPlaceholder('Rechercher (série, produit, chantier, client)…').fill(`AERR32 ${m}`, { timeout: 60_000 })
  }
  await ouvrir()
  await expect(ligne(1), 'équipement 1 listé').toBeVisible({ timeout: 60_000 })
  await expect(ligne(2), 'équipement 2 listé').toBeVisible()
  await ligne(1).getByText(`SN32-1-${m}`).click()
  const fiche = p.getByRole('dialog').filter({ hasText: 'Équipement —' })
  await expect(fiche).toBeVisible()
  await fiche.locator('label:text-is("Note") + textarea').fill(`Note AERR32 ${m}`)
  const relecture = await panne(p, suivi, /\/api\/django\/sav\/equipements\/\?/)
  await fiche.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(toast(p, 'Équipement mis à jour')).toBeVisible({ timeout: 30_000 })
  const avis = p.getByRole('status').filter({ hasText: 'Liste pas à jour' })
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(ligne(1), 'équipement 1 gardé').toBeVisible()
  await expect(ligne(2), 'équipement 2 gardé').toBeVisible()
  await expect(p.getByText('Chargement impossible')).toHaveCount(0)
  await capturer(p, 'PF12.1-AERR32-equipements', 1)
  expect(await py(`from apps.sav.models import Equipement
sortie(Equipement.objects.get(pk=${ids.eqs[0]}).note)`), 'base : note enregistrée').toBe(`Note AERR32 ${m}`)
  await relecture.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'avis retiré après Réessayer').toHaveCount(0, { timeout: 30_000 })
  await p.reload()
  await ouvrir()
  await expect(ligne(1), 'après rechargement').toBeVisible({ timeout: 60_000 })
  await auRepos(p)
})

// ═══ PF12.1 — AERR129 : garanties et nettoyages gardés sur relecture ratée ; jamais « Aucune … » sur échec ═══
etape('PF12.1-AERR129-garanties', ['AERR129'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await py(`from decimal import Decimal
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionWarranty
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
annee = timezone.localdate().year + 1
inst = [Installation.objects.create(company_id=${SOC}, reference='AERR129-${m}-%d' % n, client=cl, puissance_installee_kwc=Decimal('10')) for n in (1, 2)]
gs = [ProductionWarranty.objects.create(company_id=${SOC}, installation=i, start_year=annee, guaranteed_year1_kwh=Decimal('12000'), degradation_pct_per_year=Decimal('0.5')) for i in inst]
sortie(dict(client=cl.pk, inst=[i.pk for i in inst], gs=[g.pk for g in gs]))`)
  apres.push(() => py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionWarranty
ProductionWarranty.objects.filter(pk__in=${J(ids.gs)}).delete()
Installation.objects.filter(pk__in=${J(ids.inst)}).delete()
Client.objects.filter(pk=${ids.client}).delete()`))
  const nom = `aerr129te_${m}`
  await compteRole(nom, 'Technicien')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const table = p.locator('[aria-label="Garanties de production"]')
  const ligne = (n) => table.getByRole('row').filter({ hasText: `AERR129-${m}-${n}` })
  await p.goto('/production/garanties')
  await expect(ligne(1), 'garantie 1 affichée').toBeVisible({ timeout: 60_000 })
  await expect(ligne(2), 'garantie 2 affichée').toBeVisible()
  await ligne(1).getByRole('button', { name: 'Modifier' }).click()
  const dlg = p.getByRole('dialog').filter({ hasText: 'Modifier la garantie' })
  await expect(dlg).toBeVisible()
  await dlg.locator('#w-note').fill(`Note AERR129 ${m}`)
  const relecture = await panne(p, suivi, /\/api\/django\/monitoring\/warranties\/\?/)
  await dlg.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(toast(p, 'Garantie mise à jour.')).toBeVisible({ timeout: 30_000 })
  const avis = p.getByRole('status').filter({ hasText: 'Liste pas à jour' })
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(ligne(1), 'les 2 garanties restent').toBeVisible()
  await expect(ligne(2)).toBeVisible()
  await expect(p.getByText('Aucune garantie de production'), 'jamais l\'état vide').toHaveCount(0)
  await capturer(p, 'PF12.1-AERR129-garanties', 1)
  expect(await py(`from apps.monitoring.models import ProductionWarranty
sortie(ProductionWarranty.objects.get(pk=${ids.gs[0]}).note)`), 'base : la garantie est enregistrée').toBe(`Note AERR129 ${m}`)
  // Premier chargement rejeté : état d'erreur + Réessayer, jamais « Aucune garantie de production ».
  await p.reload()
  const echec = p.getByRole('status').filter({ hasText: 'Garanties non chargées' })
  await expect(echec, 'premier chargement rejeté : avis d\'erreur').toBeVisible({ timeout: 60_000 })
  await expect(echec.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(p.getByText('Aucune garantie de production')).toHaveCount(0)
  await capturer(p, 'PF12.1-AERR129-garanties', 2)
  await relecture.lever()
  await echec.getByRole('button', { name: 'Réessayer' }).click()
  await expect(ligne(1), 'Réessayer : les garanties reviennent').toBeVisible({ timeout: 60_000 })
  await expect(echec).toHaveCount(0)
  await auRepos(p)
})

etape('PF12.1-AERR129-nettoyages', ['AERR129'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await py(`import datetime
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import MonitoringConfig, CleaningEvent
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
i = Installation.objects.create(company_id=${SOC}, reference=${J(`AERR129N-${m}`)}, client=cl)
cfg = MonitoringConfig.objects.create(company_id=${SOC}, installation=i)
j = timezone.localdate()
cs = [CleaningEvent.objects.create(company_id=${SOC}, installation=i, date=j - datetime.timedelta(days=d), note='Nettoyage %d ${m}' % d) for d in (30, 60)]
sortie(dict(client=cl.pk, inst=i.pk, cfg=cfg.pk, cs=[c.pk for c in cs]))`)
  apres.push(() => py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import MonitoringConfig, CleaningEvent
CleaningEvent.objects.filter(installation_id=${ids.inst}).delete()
MonitoringConfig.objects.filter(pk=${ids.cfg}).delete()
Installation.objects.filter(pk=${ids.inst}).delete()
Client.objects.filter(pk=${ids.client}).delete()`))
  const nom = `aerr129nt_${m}`
  await compteRole(nom, 'Technicien')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const journal = p.locator('[aria-label="Journal des nettoyages"]')
  const ligne = (d) => journal.getByRole('row').filter({ hasText: `Nettoyage ${d} ${m}` })
  const choisir = async () => {
    await p.goto('/production/nettoyages')
    await p.getByRole('combobox', { name: 'Choisir un système supervisé' }).click({ timeout: 60_000 })
    await p.getByRole('option', { name: new RegExp(`AERR129N-${m}|Système #${ids.inst}$`) }).click()
  }
  await choisir()
  await expect(ligne(30), 'nettoyage 1 affiché').toBeVisible({ timeout: 60_000 })
  await expect(ligne(60), 'nettoyage 2 affiché').toBeVisible()
  await p.locator('#c-note').fill(`Nettoyage 0 ${m}`)
  const relecture = await panne(p, suivi, /\/api\/django\/monitoring\/cleanings\/\?/)
  await p.getByRole('button', { name: 'Ajouter' }).click()
  await expect(toast(p, 'Nettoyage enregistré.')).toBeVisible({ timeout: 30_000 })
  const avis = p.getByRole('status').filter({ hasText: 'Liste pas à jour' })
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(ligne(30), 'les 2 nettoyages restent').toBeVisible()
  await expect(ligne(60)).toBeVisible()
  await expect(p.getByText('Aucun nettoyage enregistré pour ce système.'), 'jamais « Aucun nettoyage »').toHaveCount(0)
  await capturer(p, 'PF12.1-AERR129-nettoyages', 1)
  expect(await py(`from apps.monitoring.models import CleaningEvent
sortie(CleaningEvent.objects.filter(installation_id=${ids.inst}).count())`), 'base : le nettoyage est enregistré').toBe(3)
  await relecture.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(ligne(0), 'Réessayer : la liste relue porte le nouveau nettoyage').toBeVisible({ timeout: 30_000 })
  await expect(avis).toHaveCount(0)
  await p.reload()
  await choisir()
  await expect(ligne(0), 'après rechargement').toBeVisible({ timeout: 60_000 })
  await auRepos(p)
})

// ══════════════════════════════ CHANTIERS / INTERVENTIONS ══════════════════════════════

/** Chantier d'essai (client propre) + interventions, par le shell. */
const chantierDe = (m, prefixe, { agricole = false, interventions = [] } = {}) => py(`import datetime
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.models_intervention import Intervention
from apps.sav.models import Ticket
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
i = Installation.objects.create(company_id=${SOC}, reference=${J(`${prefixe}-${m}`)}, client=cl${agricole ? ", type_installation='agricole'" : ''})
ivs, tks = [], []
for s in ${J(interventions)}:
    t = None
    if s.get('ticket'):
        t = Ticket.objects.create(company_id=${SOC}, client=cl, installation=i, reference=s['ticket'], description='Panne ${m}')
        tks.append(t.pk)
    tech = U.objects.get(pk=s['technicien']) if s.get('technicien') else None
    iv = Intervention.objects.create(company_id=${SOC}, installation=i, ticket=t, type_intervention='depannage',
        statut=s['statut'], technicien=tech, date_prevue=timezone.localdate() if s.get('aujourdhui') else None)
    ivs.append(iv.pk)
sortie(dict(client=cl.pk, inst=i.pk, ivs=ivs, tickets=tks))`)
const retirerChantier = (ids) => py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.models_intervention import Intervention
from apps.sav.models import Ticket
for pk in ${J(ids.ivs || [])}:
    try: Intervention.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage intervention', pk, exc)
Ticket.objects.filter(pk__in=${J(ids.tickets || [])}).delete()
try: Installation.objects.filter(pk=${ids.inst}).delete()
except Exception as exc: print('nettoyage chantier', exc)
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`)

// ═══ PF12.2 — AERR28 : Installé confirmé (nom, statut, effet) avant tout PATCH ; En cours : PATCH + « Annuler » ═══
etape('PF12.2-AERR28', ['AERR28'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const crees = []
  try {
    for (const cible of [['materiel_commande', 'planifie', 'en_cours'], ['materiel_commande', 'planifie']]) {
      const c = await (await r.post(`${API}/installations/chantiers/`, { ...T, data: {} })).json()
      crees.push(c.id)
      for (const statut of cible) {
        const pas = await r.patch(`${API}/installations/chantiers/${c.id}/`, { ...T, data: { statut } })
        expect(pas.ok(), `préparation : « ${statut} » (${(await pas.text()).slice(0, 200)})`).toBe(true)
      }
    }
  } finally {
    apres.push(async () => { for (const id of crees) await r.delete(`${API}/installations/chantiers/${id}/`, T).catch(() => null) })
  }
  const [idA, idB] = crees
  const refA = (await lire(r, `/installations/chantiers/${idA}/`, 'chantier A')).reference
  const refB = (await lire(r, `/installations/chantiers/${idB}/`, 'chantier B')).reference
  const m = marque()
  const nom = `aerr28re_${m}`
  await compteRole(nom, 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, nom, { width: 1920, height: 1080 })
  const patchsA = compter(p, 'PATCH', new RegExp(`/api/django/installations/chantiers/${idA}/$`))
  const patchsB = compter(p, 'PATCH', new RegExp(`/api/django/installations/chantiers/${idB}/$`))
  const statutServi = async (id) => (await lire(r, `/installations/chantiers/${id}/`, 'chantier relu')).statut
  await p.goto('/chantiers')
  await p.getByLabel('Changer de vue').getByText('Kanban', { exact: true }).click({ timeout: 60_000 })
  const selA = p.locator(`#kc-statut-${idA}`)
  const selB = p.locator(`#kc-statut-${idB}`)
  await expect(selA, 'carte A en kanban, « En cours »').toHaveValue('en_cours', { timeout: 60_000 })
  // Sélecteur de la carte A → « Installé » : confirmation nommée, AUCUN PATCH avant « Confirmer ».
  await selA.selectOption('installe')
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'confirmation nommée').toContainText(`Passer ${refA} à « Installé » ?`)
  await expect(boite).toContainText(`${refA} passera à « Installé »`)
  await expect(boite, 'effet nommé').toContainText('le matériel réservé sortira du stock')
  await capturer(p, 'PF12.2-AERR28', 1)
  expect(patchsA.length, 'aucun PATCH tant que la boîte est ouverte').toBe(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toBeHidden()
  await expect(selA, 'Annuler : la carte reste « En cours »').toHaveValue('en_cours')
  expect(patchsA.length, 'Annuler : aucun PATCH').toBe(0)
  expect(await statutServi(idA), 'Annuler : statut servi inchangé').toBe('en_cours')
  await selA.selectOption('installe')
  await expect(boite).toContainText(`Passer ${refA} à « Installé » ?`)
  await boite.getByRole('button', { name: 'Confirmer' }).click()
  await expect.poll(() => patchsA.length, { message: 'Confirmer : un PATCH' }).toBe(1)
  await expect.poll(() => statutServi(idA), { message: 'statut servi « installe »' }).toBe('installe')
  await expect(selA, 'carte A « Installé »').toHaveValue('installe', { timeout: 30_000 })
  // Planifié → En cours : PATCH immédiat, sans boîte, puis toast « Annuler » qui repasse « Planifié ».
  await selB.selectOption('en_cours')
  await expect.poll(() => patchsB.length, { message: 'pas sans effet durable : PATCH immédiat' }).toBe(1)
  await expect(p.getByRole('alertdialog'), 'aucune boîte pour ce pas').toHaveCount(0)
  const t = toast(p, `${refB} passé à « En cours »`)
  await expect(t, 'toast avec Annuler').toBeVisible({ timeout: 30_000 })
  await capturer(p, 'PF12.2-AERR28', 2)
  await expect.poll(() => statutServi(idB)).toBe('en_cours')
  await t.getByRole('button', { name: 'Annuler' }).click()
  await expect.poll(() => statutServi(idB), { message: 'Annuler : statut servi « planifie »' }).toBe('planifie')
  // Persistance : écran rechargé (vue kanban gardée).
  await p.reload()
  await expect(selA, 'après rechargement : A « Installé »').toHaveValue('installe', { timeout: 60_000 })
  await expect(selB, 'après rechargement : B « Planifié »').toHaveValue('planifie')
  await auRepos(p)
})

/** Glisse la carte (dnd-kit, capteur pointeur : distance 6 px) sur la colonne `vers`. */
async function glisser(p, carte, colonne) {
  await carte.scrollIntoViewIfNeeded()
  const a = await carte.boundingBox()
  await p.mouse.move(a.x + a.width / 2, a.y + 20)
  await p.mouse.down()
  await p.mouse.move(a.x + a.width / 2 + 12, a.y + 26, { steps: 4 })
  await colonne.scrollIntoViewIfNeeded()
  const b = await colonne.boundingBox()
  await p.mouse.move(b.x + b.width / 2, b.y + 80, { steps: 20 })
  await p.mouse.up()
}
const colonne = (p, titre) => p.locator('section.kb-col').filter({ has: p.locator('.kb-col-title', { hasText: new RegExp(`^${titre}$`) }) })

// ═══ PF12.2 — AERR29 : dépôt sur « Validée » confirmé (nom, statut, ticket SAV résolu) ; Prête → En route + Annuler ═══
etape('PF12.2-AERR29', ['AERR29'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await chantierDe(m, 'AERR29', { interventions: [
    { statut: 'sur_site', ticket: `SAV-29-${m}` }, { statut: 'prete' },
  ] })
  apres.push(() => retirerChantier(ids))
  const [i1, i2] = ids.ivs
  const r = page.request
  const servi = async (id) => (await lire(r, `/installations/interventions/${id}/`, 'intervention relue')).statut
  const iv1 = await lire(r, `/installations/interventions/${i1}/`, 'intervention 1')
  const nomI = iv1.reference ?? iv1.installation_reference ?? `#${i1}`
  const nom = `aerr29re_${m}`
  await compteRole(nom, 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, nom, { width: 1920, height: 1080 })
  const patch1 = compter(p, 'PATCH', new RegExp(`/api/django/installations/interventions/${i1}/$`))
  const patch2 = compter(p, 'PATCH', new RegExp(`/api/django/installations/interventions/${i2}/$`))
  await p.goto(`/interventions?installation=${ids.inst}`)
  const carteSurSite = colonne(p, 'Sur site').locator('.kb-drag-wrap')
  const cartePrete = colonne(p, 'Prête').locator('.kb-drag-wrap')
  await expect(carteSurSite, 'kanban : intervention « Sur site »').toHaveCount(1, { timeout: 60_000 })
  await expect(cartePrete).toHaveCount(1)
  await glisser(p, carteSurSite, colonne(p, 'Validée'))
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'confirmation nommée').toContainText(`Passer ${nomI} à « Validée » ?`, { timeout: 30_000 })
  await expect(boite, 'effet nommé').toContainText('le ticket SAV lié sera résolu')
  await capturer(p, 'PF12.2-AERR29', 1)
  expect(patch1.length, 'aucun PATCH avant Confirmer').toBe(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toBeHidden()
  await expect(carteSurSite, 'Annuler : la carte revient « Sur site »').toHaveCount(1)
  expect(patch1.length, 'Annuler : aucun PATCH').toBe(0)
  expect(await servi(i1), 'Annuler : statut servi inchangé').toBe('sur_site')
  await glisser(p, carteSurSite, colonne(p, 'Validée'))
  await expect(boite).toContainText(`Passer ${nomI} à « Validée » ?`, { timeout: 30_000 })
  await boite.getByRole('button', { name: 'Confirmer' }).click()
  await expect.poll(() => patch1.length, { message: 'Confirmer : un PATCH' }).toBe(1)
  await expect.poll(() => servi(i1), { message: 'statut servi « validee »' }).toBe('validee')
  await expect(colonne(p, 'Validée').locator('.kb-drag-wrap'), 'carte en « Validée »').toHaveCount(1, { timeout: 30_000 })
  // Prête → En route : PATCH immédiat, toast « Annuler » qui repasse « Prête ».
  await glisser(p, cartePrete, colonne(p, 'En route'))
  await expect.poll(() => patch2.length, { message: 'PATCH immédiat' }).toBe(1)
  await expect(p.getByRole('alertdialog'), 'aucune boîte pour ce statut').toHaveCount(0)
  const t = toast(p, `passée à « En route »`)
  await expect(t, 'toast avec Annuler').toBeVisible({ timeout: 30_000 })
  await capturer(p, 'PF12.2-AERR29', 2)
  await expect.poll(() => servi(i2)).toBe('en_route')
  await t.getByRole('button', { name: 'Annuler' }).click()
  await expect.poll(() => servi(i2), { message: 'Annuler : « prete » servi' }).toBe('prete')
  await p.reload()
  await expect(colonne(p, 'Prête').locator('.kb-drag-wrap'), 'après rechargement : « Prête »').toHaveCount(1, { timeout: 60_000 })
  await expect(colonne(p, 'Validée').locator('.kb-drag-wrap'), 'après rechargement : « Validée »').toHaveCount(1)
  await auRepos(p)
})

// ═══ PF12.2 — AERR34 : relecture rejetée après un changement de statut : les 3 cartes restent, avis + Réessayer ═══
etape('PF12.2-AERR34', ['AERR34'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await chantierDe(m, 'AERR34', { interventions: [{ statut: 'prete' }, { statut: 'sur_site' }, { statut: 'en_route' }] })
  apres.push(() => retirerChantier(ids))
  const r = page.request
  const nom = `aerr34re_${m}`
  await compteRole(nom, 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, nom, { width: 1920, height: 1080 })
  const cartes = p.locator('.kb-drag-wrap')
  await p.goto(`/interventions?installation=${ids.inst}`)
  await expect(cartes, 'kanban : 3 interventions').toHaveCount(3, { timeout: 60_000 })
  const relecture = await panne(p, suivi, /\/api\/django\/installations\/interventions\/\?/)
  await glisser(p, colonne(p, 'Prête').locator('.kb-drag-wrap'), colonne(p, 'En route'))
  await expect(toast(p, 'passée à « En route »')).toBeVisible({ timeout: 30_000 })
  const avis = p.getByRole('alert').filter({ hasText: 'Liste pas à jour' })
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(cartes, 'les 3 cartes restent').toHaveCount(3)
  await expect(colonne(p, 'En route').locator('.kb-drag-wrap'), 'statut nouveau affiché').toHaveCount(2)
  await expect(p.getByText('Impossible de charger les interventions', { exact: true }), 'jamais l\'erreur pleine').toHaveCount(0)
  await capturer(p, 'PF12.2-AERR34', 1)
  expect(await py(`from apps.installations.models_intervention import Intervention
sortie(Intervention.objects.get(pk=${ids.ivs[0]}).statut)`), 'base : statut enregistré').toBe('en_route')
  // Rien de chargé (rechargement sous la panne) : l'écran d'erreur plein, avec Réessayer.
  await p.reload()
  await expect(p.getByText('Impossible de charger les interventions', { exact: true }), 'premier chargement rejeté : erreur pleine').toBeVisible({ timeout: 60_000 })
  await capturer(p, 'PF12.2-AERR34', 2)
  await relecture.lever()
  await p.getByRole('button', { name: 'Réessayer' }).first().click()
  await expect(cartes, 'Réessayer : les 3 cartes').toHaveCount(3, { timeout: 60_000 })
  await expect(p.getByRole('alert').filter({ hasText: 'Liste pas à jour' })).toHaveCount(0)
  expect((await lire(r, `/installations/interventions/${ids.ivs[0]}/`, 'relue')).statut).toBe('en_route')
  await auRepos(p)
})

// ═══ PF12.2 — AERR36 : Ma journée, tournée illisible SANS cache ⇒ « Tournée indisponible » + Réessayer ═══
etape('PF12.2-AERR36', ['AERR36'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr36te_${m}`
  await compteRole(nom, 'Technicien')
  const { p } = await ecran(page, suivi, testInfo, nom)
  await accordGps(p)
  const TOURNEE = /\/api\/django\/installations\/interventions\/ma-tournee\//
  const coupure = await panne(p, suivi, TOURNEE, { statut: 'reseau' })
  const indispo = p.getByText('Tournée indisponible — vérifiez la connexion')
  const vide = p.getByText("Aucune intervention aujourd'hui")
  await p.goto('/ma-journee')
  await expect(indispo, 'sans cache : tournée indisponible').toBeVisible({ timeout: 60_000 })
  await expect(p.getByRole('button', { name: 'Réessayer' }), 'Réessayer proposé').toBeVisible()
  await expect(vide, 'jamais « Aucune intervention aujourd\'hui »').toHaveCount(0)
  await capturer(p, 'PF12.2-AERR36', 1)
  await p.reload()
  await expect(indispo, 'après rechargement (toujours sans cache)').toBeVisible({ timeout: 60_000 })
  await expect(vide).toHaveCount(0)
  // « Réessayer » relance la lecture : réseau revenu, réponse vide réussie ⇒ journée vide.
  const n = coupure.vues.length
  await coupure.lever()
  await Promise.all([
    p.waitForResponse((x) => TOURNEE.test(x.url()) && x.status() === 200, T),
    p.getByRole('button', { name: 'Réessayer' }).click(),
  ])
  expect(n, 'la tournée a bien été demandée sous la coupure').toBeGreaterThan(0)
  await expect(vide, 'réponse vide réussie : « Aucune intervention aujourd\'hui »').toBeVisible({ timeout: 30_000 })
  await expect(indispo).toHaveCount(0)
  // Cache présent (réponse précédente) puis réseau coupé : tournée en cache avec son bandeau d'ancienneté.
  const seconde = await panne(p, suivi, TOURNEE, { statut: 'reseau' })
  await p.reload()
  await expect(p.getByTestId('bandeau-hors-ligne'), 'cache présent : bandeau d\'ancienneté').toBeVisible({ timeout: 60_000 })
  await expect(indispo, 'cache présent : pas « indisponible »').toHaveCount(0)
  await seconde.lever()
  await auRepos(p)
})

// ═══ PF12.2 — AERR78 : panneaux de la fiche d'intervention, lecture rejetée ⇒ « … non chargés » + Réessayer ═══
etape('PF12.2-AERR78', ['AERR78'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr78te_${m}`
  const uid = await compteRole(nom, 'Technicien')
  const ids = await chantierDe(m, 'AERR78', { interventions: [{ statut: 'prete', technicien: uid, aujourdhui: 'oui' }] })
  apres.push(() => retirerChantier(ids))
  const [iv] = ids.ivs
  const { p } = await ecran(page, suivi, testInfo, nom)
  await accordGps(p)
  const PANNEAUX =new RegExp(`/api/django/installations/interventions/${iv}/(serials|memos|reserves|tool-return)/$`)
  const coupure = await panne(p, suivi, PANNEAUX)
  const onglet = (n) => p.getByRole('tab', { name: n })
  const ouvrir = async () => {
    await p.goto('/ma-journee')
    await p.getByRole('button', { name: new RegExp(`AERR Client ${m}`) }).click({ timeout: 60_000 })
    await expect(onglet('N° série'), 'fiche d\'intervention ouverte').toBeVisible({ timeout: 30_000 })
  }
  const ATTENDUS = [
    ['N° série', 'Numéros de série non chargés.', null],
    ['Mémos', 'Mémos non chargés.', 'Aucun mémo.'],
    ['Réserves', 'Réserves non chargées.', 'Aucune réserve.'],
    ['Outils', "Retours d'outils non chargés.", 'Aucun outil dans le kit de préparation.'],
  ]
  const panneau = (n) => p.locator('[role="tabpanel"]:not([hidden])').filter({ hasText: n })
  await ouvrir()
  for (const [tab, echec, vide] of ATTENDUS) {
    await onglet(tab).click()
    await expect(p.getByText(echec), `${tab} : « ${echec} »`).toBeVisible({ timeout: 30_000 })
    await expect(panneau(echec).getByRole('button', { name: 'Réessayer' }), `${tab} : Réessayer`).toBeVisible()
    if (vide) await expect(p.getByText(vide, { exact: true }), `${tab} : jamais l'état vide`).toHaveCount(0)
    if (tab === 'N° série') await capturer(p, 'PF12.2-AERR78', 1)
  }
  // Réessayer RELANCE la lecture (toujours rejetée : l'avis reste).
  await onglet('N° série').click()
  const avant = coupure.vues.filter((u) => u.includes('/serials/')).length
  await panneau('Numéros de série non chargés.').getByRole('button', { name: 'Réessayer' }).click()
  await expect.poll(() => coupure.vues.filter((u) => u.includes('/serials/')).length, { message: 'Réessayer relance la lecture' }).toBe(avant + 1)
  await expect(p.getByText('Numéros de série non chargés.')).toBeVisible()
  // Rechargement : la fiche et son onglet sont restaurés (VX105), l'avis est réaffirmé.
  await p.reload()
  await expect(onglet('N° série'), 'après rechargement : fiche restaurée').toBeVisible({ timeout: 60_000 })
  await onglet('Réserves').click()
  await expect(p.getByText('Réserves non chargées.'), 'après rechargement : avis réaffirmé').toBeVisible({ timeout: 30_000 })
  // Serveur revenu : Réessayer rend chaque panneau (« aucun » seulement quand la lecture a RÉUSSI).
  await coupure.lever()
  for (const [tab, echec, vide] of ATTENDUS) {
    await onglet(tab).click()
    await panneau(echec).getByRole('button', { name: 'Réessayer' }).click()
    await expect(p.getByText(echec), `${tab} : avis retiré après lecture réussie`).toHaveCount(0, { timeout: 30_000 })
    if (vide) await expect(p.getByText(vide, { exact: true }), `${tab} : état vide après lecture réussie`).toBeVisible()
  }
  await auRepos(p)
})

// ═══ PF12.2 — AERR77 : « Valider la consommation » ⇒ boîte nommée (intervention, articles, quantités, définitif) ═══
etape('PF12.2-AERR77', ['AERR77'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await chantierDe(m, 'AERR77', { interventions: [{ statut: 'sur_site' }] })
  apres.push(() => retirerChantier(ids))
  const [iv] = ids.ivs
  await py(`from decimal import Decimal
from apps.installations.models_field import MaterielConsommation, ConsommationLigne
from apps.installations.models_intervention import Intervention
iv = Intervention.objects.get(pk=${iv})
c, _ = MaterielConsommation.objects.get_or_create(intervention=iv, defaults={'company_id': ${SOC}})
for n, (d, q) in enumerate([('Panneau 450 W ${m}', 12), ('Onduleur 5 kW ${m}', 1)]):
    ConsommationLigne.objects.create(company_id=${SOC}, consommation=c, designation=d, quantite_prevue=Decimal(q), quantite_utilisee=Decimal(q), hors_nomenclature=True, ordre=n)
sortie(c.pk)`)
  const r = page.request
  const relue = await lire(r, `/installations/interventions/${iv}/`, 'intervention')
  const nomI = relue.reference ?? relue.installation_reference ?? `#${iv}`
  const nom = `aerr77re_${m}`
  await compteRole(nom, 'Responsable')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const valides = compter(p, 'POST', new RegExp(`/api/django/installations/interventions/${iv}/valider-consommation/$`))
  const etatConso = () => py(`from apps.installations.models_field import MaterielConsommation
c = MaterielConsommation.objects.get(intervention_id=${iv}); sortie(c.valide)`)
  const ouvrirConso = async () => {
    await p.goto(`/interventions?installation=${ids.inst}&id=${iv}`)
    await p.getByRole('tab', { name: 'Consommé' }).click({ timeout: 60_000 })
  }
  await ouvrirConso()
  await expect(p.getByText(`Panneau 450 W ${m}`), 'ligne 1 affichée').toBeVisible({ timeout: 30_000 })
  await expect(p.getByText(`Onduleur 5 kW ${m}`), 'ligne 2 affichée').toBeVisible()
  await p.getByRole('button', { name: 'Valider la consommation' }).click()
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'boîte nommée : l\'intervention').toContainText(`Valider la consommation de ${nomI} ?`)
  // Quantités servies telles que la boîte les écrit (décimal du serveur : « 12.00 × … »).
  await expect(boite, 'article 1 et quantité').toContainText(new RegExp(`(^|[^\\d.])12(\\.0+)? × Panneau 450 W ${m}`))
  await expect(boite, 'article 2 et quantité').toContainText(new RegExp(`(^|[^\\d.])1(\\.0+)? × Onduleur 5 kW ${m}`))
  await expect(boite, 'caractère définitif').toContainText('Validation définitive : la consommation ne sera plus modifiable.')
  await capturer(p, 'PF12.2-AERR77', 1)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toBeHidden()
  expect(valides.length, 'Annuler : aucun appel validerConsommation').toBe(0)
  expect(await etatConso(), 'Annuler : consommation toujours modifiable').toBe(false)
  await expect(p.getByRole('button', { name: 'Valider la consommation' }), 'toujours proposée').toBeVisible()
  await p.getByRole('button', { name: 'Valider la consommation' }).click()
  await boite.getByRole('button', { name: 'Valider' }).click()
  await expect(toast(p, 'Consommation validée — stock mis à jour.')).toBeVisible({ timeout: 30_000 })
  expect(valides.length, 'Valider : un appel').toBe(1)
  expect(await etatConso(), 'base : consommation validée').toBe(true)
  await p.reload()
  await ouvrirConso()
  await expect(p.getByText('Validée — stock mis à jour'), 'après rechargement : validée').toBeVisible({ timeout: 30_000 })
  await expect(p.getByRole('button', { name: 'Valider la consommation' })).toHaveCount(0)
  await auRepos(p)
})

// ═══ PF12.2 — AERR38 : recette de pompage, mesure saisie puis Échap / clic extérieur ⇒ demande ; rester garde ═══
etape('PF12.2-AERR38', ['AERR38'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await chantierDe(m, 'AERR38', { agricole: true })
  apres.push(() => retirerChantier(ids))
  const r = page.request
  const ouverte = await r.post(`${API}/installations/chantiers/${ids.inst}/recette-pompage/`, { ...T, data: {} })
  expect(ouverte.status(), `fiche de recette ouverte : ${(await ouverte.text()).slice(0, 200)}`).toBeLessThan(300)
  const nom = `aerr38re_${m}`
  await compteRole(nom, 'Responsable')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
  const recette = p.getByRole('dialog', { name: 'Recette de pompage (IEC 62253)' })
  const debit = recette.locator('#recette-pompage-debit_mesure_m3h')
  // Fiche chantier → onglet « Jalons & gates » → « … fiche de recette » (fiche rouverte à chaque fois : au run
  // 43539824114, l'Échap qui ferme la recette ferme aussi la fiche chantier qui la porte).
  const ouvrir = async () => {
    await p.goto(`/chantiers?id=${ids.inst}`)
    await p.getByRole('tab', { name: /Jalons/ }).click({ timeout: 60_000 })
    await expect(p.getByTestId('ch6-recette')).toBeVisible({ timeout: 30_000 })
    await p.getByRole('button', { name: /fiche de recette/ }).first().click()
    await expect(recette).toBeVisible({ timeout: 30_000 })
    await expect(debit).toBeVisible()
  }
  // Aucune saisie : Échap ferme directement (aucune demande).
  await ouvrir()
  await p.keyboard.press('Escape')
  await expect(recette, 'sans saisie : fermeture directe').toBeHidden()
  expect(dem.vues, 'sans saisie : aucune demande').toBe(0)
  console.log(`[AERR38] après Échap sans saisie, fiche chantier encore ouverte : ${await p.getByTestId('ch6-recette').isVisible()}`)
  // Débit mesuré saisi : Échap ⇒ demande ; rester ⇒ mesure intacte.
  await ouvrir()
  await debit.fill('12.5')
  dem.prochaine = 'rester'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.vues, { message: 'Échap : demande posée' }).toBe(1)
  await expect(recette, 'rester : fiche ouverte').toBeVisible()
  await expect(debit, 'rester : mesure intacte').toHaveValue('12.5')
  // Clic hors de la boîte ⇒ demande ; rester ⇒ mesure intacte.
  dem.prochaine = 'rester'
  await p.mouse.click(8, 8)
  await expect.poll(() => dem.vues, { message: 'clic extérieur : demande posée' }).toBe(2)
  await expect(recette, 'rester (clic extérieur) : fiche ouverte').toBeVisible()
  await expect(debit).toHaveValue('12.5')
  await capturer(p, 'PF12.2-AERR38', 1)
  // Quitter : la fiche se ferme, rien n'est écrit.
  dem.prochaine = 'quitter'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.vues).toBe(3)
  await expect(recette).toBeHidden()
  const lue = await lire(r, `/installations/chantiers/${ids.inst}/recette-pompage/`, 'recette relue')
  expect(lue.record?.debit_mesure_m3h ?? null, 'base : aucune mesure enregistrée').toBeNull()
  await ouvrir()
  await expect(debit, 'fiche rouverte : mesure non enregistrée').toHaveValue('')
  await p.keyboard.press('Escape')
  await auRepos(p)
})

// ══════════════════════════════ STOCK / RÉGLAGES ══════════════════════════════

// ═══ PF12.3 — AERR33 : catalogue gardé quand la relecture d'après « Mettre à jour » est rejetée ═══
etape('PF12.3-AERR33', ['AERR33'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const prods = await py(`from apps.stock.models import Produit
sortie([Produit.objects.create(company_id=${SOC}, nom='AERR33 ${m} P%d' % n, prix_vente=100).pk for n in (1, 2, 3)])`)
  apres.push(() => py(`from apps.stock.models import Produit
for pk in ${J(prods)}:
    try: Produit.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage produit', pk, exc)`))
  const nom = `aerr33ad_${m}`
  // Administrateur : sous Responsable, le formulaire produit lit `prix-fournisseurs/` (403, sans `prix_achat_voir`),
  // défaut hors de StockList.jsx observé au run 43539824114.
  await compteRole(nom, 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const ligne = (n) => p.getByRole('row').filter({ hasText: `AERR33 ${m} P${n}` })
  const chercher = () => p.getByPlaceholder('Chercher partout…').fill(`AERR33 ${m}`, { timeout: 60_000 })
  await p.goto('/stock')
  await chercher()
  for (const n of [1, 2, 3]) await expect(ligne(n), `produit P${n} affiché`).toBeVisible({ timeout: 60_000 })
  await ligne(1).getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await p.getByRole('menuitem', { name: 'Éditer' }).click()
  const form = p.getByRole('dialog').filter({ has: p.locator('#pf-desc') })
  await expect(form).toBeVisible({ timeout: 30_000 })
  await form.locator('#pf-desc').fill(`Description AERR33 ${m}`)
  const relecture = await panne(p, suivi, /\/api\/django\/stock\/produits\/\?/)
  await form.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(form, 'formulaire enregistré et fermé').toBeHidden({ timeout: 30_000 })
  const avis = p.getByTestId('catalogue-pas-a-jour')
  await expect(avis, 'avis « Catalogue pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Catalogue pas à jour')
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  for (const n of [1, 2, 3]) await expect(ligne(n), `P${n} reste affiché`).toBeVisible()
  await expect(p.getByText('Erreur de chargement', { exact: true }), 'jamais l\'erreur pleine').toHaveCount(0)
  await capturer(p, 'PF12.3-AERR33', 1)
  expect(await py(`from apps.stock.models import Produit
sortie(Produit.objects.get(pk=${prods[0]}).description)`), 'base : produit enregistré').toBe(`Description AERR33 ${m}`)
  // « Réessayer » relance fetchProduits (toujours rejeté : l'avis reste, les produits aussi).
  const avant = relecture.vues.length
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect.poll(() => relecture.vues.length, { message: 'Réessayer relance la lecture' }).toBeGreaterThan(avant)
  await expect(ligne(1)).toBeVisible()
  // Aucun produit chargé (rechargement sous la panne) : erreur pleine AVEC Réessayer.
  await p.reload()
  const pleine = p.getByText('Erreur de chargement', { exact: true })
  await expect(pleine, 'premier chargement rejeté : erreur pleine').toBeVisible({ timeout: 60_000 })
  await expect(p.getByRole('button', { name: 'Réessayer' }).first(), 'erreur pleine : Réessayer').toBeVisible()
  await capturer(p, 'PF12.3-AERR33', 2)
  await relecture.lever()
  await p.getByRole('button', { name: 'Réessayer' }).first().click()
  await chercher()
  await expect(ligne(1), 'Réessayer : catalogue relu').toBeVisible({ timeout: 60_000 })
  await expect(p.getByTestId('catalogue-pas-a-jour')).toHaveCount(0)
  await auRepos(p)
})

/** Fournisseur + produits + BCF (statut, lignes) + modèles, par le shell. */
const achatsDe = (m, { bcfs = [], modeles = [] } = {}) => py(`from decimal import Decimal
from apps.stock.models import Fournisseur, Produit, ModeleBonCommandeFournisseur, ModeleBonCommandeFournisseurLigne
from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom=${J(`AERR Fournisseur ${m}`)})
prods = [Produit.objects.create(company_id=${SOC}, nom='AERR article %s ${m}' % n, prix_vente=100, prix_achat=60) for n in ('A', 'B')]
bs = []
for s in ${J(bcfs)}:
    b = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference=s['ref'], fournisseur=f, statut=s['statut'], date_commande=timezone.localdate())
    for pr, q in zip(prods, s['quantites']):
        LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=pr, quantite=q, prix_achat_unitaire=Decimal('60'))
    bs.append(b.pk)
ms = []
for nom in ${J(modeles)}:
    mo = ModeleBonCommandeFournisseur.objects.create(company_id=${SOC}, nom=nom, fournisseur=f)
    ModeleBonCommandeFournisseurLigne.objects.create(modele=mo, produit=prods[0], quantite=2)
    ms.append(mo.pk)
sortie(dict(f=f.pk, prods=[p.pk for p in prods], bcfs=bs, modeles=ms))`)
const retirerAchats = (ids) => py(`from apps.stock.models import Fournisseur, Produit, ModeleBonCommandeFournisseur
from apps.achats.models import BonCommandeFournisseur
for qs in (ModeleBonCommandeFournisseur.objects.filter(pk__in=${J(ids.modeles)}), BonCommandeFournisseur.objects.filter(pk__in=${J(ids.bcfs)}),
           Produit.objects.filter(pk__in=${J(ids.prods)}), Fournisseur.objects.filter(pk=${ids.f})):
    try: qs.delete()
    except Exception as exc: print('nettoyage achats', exc)`)

// ═══ PF12.3 — AERR35 : BCF et modèles jamais vidés sur lecture ratée ; premier chargement raté ⇒ erreur ═══
etape('PF12.3-AERR35-bcf', ['AERR35'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await achatsDe(m, { bcfs: [
    { ref: `BCF-AERR35-${m}-1`, statut: 'brouillon', quantites: [2, 3] },
    { ref: `BCF-AERR35-${m}-2`, statut: 'brouillon', quantites: [1, 1] },
  ] })
  apres.push(() => retirerAchats(ids))
  const nom = `aerr35ad_${m}`
  await compteRole(nom, 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const ligne = (n) => p.getByRole('row').filter({ hasText: `BCF-AERR35-${m}-${n}` })
  const chercher = () => p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(`BCF-AERR35-${m}`, { timeout: 60_000 })
  await p.goto('/stock/bons-commande-fournisseur')
  await chercher()
  await expect(ligne(1), 'BCF 1 affiché').toBeVisible({ timeout: 60_000 })
  await expect(ligne(2), 'BCF 2 affiché').toBeVisible()
  await ligne(1).getByText(`BCF-AERR35-${m}-1`).click()
  const dlg = p.getByRole('dialog').filter({ has: p.locator('#bcf-ref-fou') })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#bcf-ref-fou').fill(`REF-${m}`)
  const relecture = await panne(p, suivi, /\/api\/django\/stock\/bons-commande-fournisseur\/\?/)
  await dlg.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  await expect(dlg, 'BCF enregistré, boîte fermée').toBeHidden({ timeout: 30_000 })
  const avis = p.getByTestId('bcf-liste-pas-a-jour')
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(ligne(1), 'les 2 BCF restent').toBeVisible()
  await expect(ligne(2)).toBeVisible()
  await expect(p.getByText('Aucun bon de commande fournisseur'), 'jamais l\'état vide').toHaveCount(0)
  await capturer(p, 'PF12.3-AERR35-bcf', 1)
  expect(await py(`from apps.achats.models import BonCommandeFournisseur
sortie(BonCommandeFournisseur.objects.get(pk=${ids.bcfs[0]}).ref_fournisseur)`), 'base : BCF enregistré').toBe(`REF-${m}`)
  await p.reload()
  await expect(avis, 'premier chargement rejeté : avis + Réessayer').toBeVisible({ timeout: 60_000 })
  await expect(p.getByRole('grid', { name: 'Bons de commande fournisseur' }).getByText('Liste indisponible'), 'premier chargement rejeté : message d\'erreur').toBeVisible()
  await expect(p.getByText('Aucun bon de commande fournisseur')).toHaveCount(0)
  await capturer(p, 'PF12.3-AERR35-bcf', 2)
  await relecture.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis).toHaveCount(0, { timeout: 30_000 })
  await chercher()
  await expect(ligne(1), 'Réessayer : liste relue').toBeVisible({ timeout: 60_000 })
  await auRepos(p)
})

etape('PF12.3-AERR35-modeles', ['AERR35'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await achatsDe(m, { modeles: [`AERR35 Modèle ${m} A`, `AERR35 Modèle ${m} B`] })
  apres.push(() => retirerAchats(ids))
  const nom = `aerr35mo_${m}`
  await compteRole(nom, 'Administrateur')
  const { p } = await ecran(page, suivi, testInfo, nom)
  const ligne = (n) => p.getByRole('row').filter({ hasText: `AERR35 Modèle ${m} ${n}` })
  const chercher = () => p.getByPlaceholder('Rechercher (nom, fournisseur)…').fill(`AERR35 Modèle ${m}`, { timeout: 60_000 })
  await p.goto('/stock/modeles-bcf')
  await chercher()
  await expect(ligne('A'), 'modèle A affiché').toBeVisible({ timeout: 60_000 })
  await expect(ligne('B'), 'modèle B affiché').toBeVisible()
  await ligne('A').getByText(`AERR35 Modèle ${m} A`).click()
  const dlg = p.getByRole('dialog').filter({ hasText: `Modèle — AERR35 Modèle ${m} A` })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#modele-note').fill(`Note ${m}`)
  const relecture = await panne(p, suivi, /\/api\/django\/stock\/modeles-bcf\/\?/)
  await dlg.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  await expect(dlg, 'modèle enregistré, boîte fermée').toBeHidden({ timeout: 30_000 })
  const avis = p.getByTestId('modeles-liste-pas-a-jour')
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(ligne('A'), 'les 2 modèles restent').toBeVisible()
  await expect(ligne('B')).toBeVisible()
  await expect(p.getByText('Aucun modèle de bon de commande'), 'jamais l\'état vide').toHaveCount(0)
  await capturer(p, 'PF12.3-AERR35-modeles', 1)
  expect(await py(`from apps.stock.models import ModeleBonCommandeFournisseur
sortie(ModeleBonCommandeFournisseur.objects.get(pk=${ids.modeles[0]}).note)`), 'base : modèle enregistré').toBe(`Note ${m}`)
  await p.reload()
  await expect(avis, 'premier chargement rejeté : avis + Réessayer').toBeVisible({ timeout: 60_000 })
  await expect(p.getByRole('grid', { name: 'Modèles de bon de commande' }).getByText('Liste indisponible'), 'premier chargement rejeté : message d\'erreur').toBeVisible()
  await expect(p.getByText('Aucun modèle de bon de commande')).toHaveCount(0)
  await relecture.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis).toHaveCount(0, { timeout: 30_000 })
  await chercher()
  await expect(ligne('A'), 'Réessayer : liste relue').toBeVisible({ timeout: 60_000 })
  await auRepos(p)
})

// ═══ PF12.3 — AERR37 : réception (2 lignes, 3 séries) et BCF modifiés : clic extérieur / Échap demandent ═══
etape('PF12.3-AERR37-reception', ['AERR37'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ref = `BCF-AERR37-${m}`
  const ids = await achatsDe(m, { bcfs: [{ ref, statut: 'envoye', quantites: [2, 3] }] })
  apres.push(() => retirerAchats(ids))
  const nom = `aerr37ad_${m}`
  await compteRole(nom, 'Administrateur')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
  const dlg = p.getByRole('dialog').filter({ hasText: 'Nouvelle réception fournisseur' })
  await p.goto('/stock/receptions-fournisseur')
  // Formulaire non modifié : clic extérieur ⇒ fermeture directe.
  await p.getByRole('button', { name: 'Nouvelle réception' }).first().click({ timeout: 60_000 })
  await expect(dlg).toBeVisible()
  await p.mouse.click(8, 8)
  await expect(dlg, 'non modifié : fermeture directe').toBeHidden()
  expect(dem.vues, 'non modifié : aucune demande').toBe(0)
  // Saisie : BCF choisi, 2 lignes, 3 n° de série, note.
  await p.getByRole('button', { name: 'Nouvelle réception' }).first().click()
  await dlg.locator('#rec-bon').click()
  await p.getByPlaceholder('Référence ou fournisseur…').fill(ref)
  await p.getByRole('option', { name: new RegExp(ref) }).click()
  const lignes = dlg.locator('tbody tr')
  await expect(lignes, '2 lignes à réceptionner').toHaveCount(2, { timeout: 30_000 })
  await dlg.getByRole('button', { name: `N° de série / lot — AERR article A ${m}` }).click()
  await dlg.getByRole('button', { name: `N° de série / lot — AERR article B ${m}` }).click()
  const series = dlg.locator('textarea[id^="rec-series-"]')
  await expect(series).toHaveCount(2)
  await series.nth(0).fill(`SNA1-${m}\nSNA2-${m}`)
  await series.nth(1).fill(`SNB1-${m}`)
  await dlg.locator('#rec-note').fill(`Réception partielle ${m}`)
  const saisie = async (quand) => {
    await expect(dlg, `${quand} : boîte ouverte`).toBeVisible()
    await expect(dlg.locator('#rec-bon'), `${quand} : BCF choisi`).toContainText(ref)
    await expect(lignes, `${quand} : 2 lignes`).toHaveCount(2)
    await expect(series.nth(0), `${quand} : séries ligne A`).toHaveValue(`SNA1-${m}\nSNA2-${m}`)
    await expect(series.nth(1), `${quand} : série ligne B`).toHaveValue(`SNB1-${m}`)
    await expect(dlg.locator('#rec-note'), `${quand} : note`).toHaveValue(`Réception partielle ${m}`)
  }
  dem.prochaine = 'rester'
  await p.mouse.click(8, 8)
  await expect.poll(() => dem.vues, { message: 'clic sur le fond : demande posée' }).toBe(1)
  await saisie('rester (clic extérieur)')
  await capturer(p, 'PF12.3-AERR37-reception', 1)
  dem.prochaine = 'rester'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.vues, { message: 'Échap : demande posée' }).toBe(2)
  await saisie('rester (Échap)')
  dem.prochaine = 'quitter'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.vues).toBe(3)
  await expect(dlg, 'quitter : boîte fermée').toBeHidden()
  expect(await py(`from apps.achats.models import BonCommandeFournisseur
b = BonCommandeFournisseur.objects.get(pk=${ids.bcfs[0]})
sortie([b.statut, sum(l.quantite_recue for l in b.lignes.all())])`), 'base : rien réceptionné').toEqual(['envoye', 0])
  await p.reload()
  await p.getByRole('button', { name: 'Nouvelle réception' }).first().click({ timeout: 60_000 })
  await expect(dlg.locator('#rec-note'), 'après rechargement : formulaire vierge').toHaveValue('')
  await p.mouse.click(8, 8)
  await expect(dlg).toBeHidden()
  await auRepos(p)
})

etape('PF12.3-AERR37-bcf', ['AERR37'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ref = `BCF-AERR37B-${m}`
  const ids = await achatsDe(m, { bcfs: [{ ref, statut: 'brouillon', quantites: [2, 3] }] })
  apres.push(() => retirerAchats(ids))
  const nom = `aerr37bc_${m}`
  await compteRole(nom, 'Administrateur')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
  const dlg = p.getByRole('dialog').filter({ has: p.locator('#bcf-note') })
  const ouvrir = async () => {
    await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(ref, { timeout: 60_000 })
    await p.getByRole('row').filter({ hasText: ref }).getByText(ref).click({ timeout: 60_000 })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
  }
  await p.goto('/stock/bons-commande-fournisseur')
  await ouvrir()
  await p.keyboard.press('Escape')
  await expect(dlg, 'non modifié : fermeture directe').toBeHidden()
  expect(dem.vues).toBe(0)
  await ouvrir()
  await dlg.locator('#bcf-note').fill(`Livraison quai 2 ${m}`)
  dem.prochaine = 'rester'
  await p.mouse.click(8, 8)
  await expect.poll(() => dem.vues, { message: 'clic extérieur : demande posée' }).toBe(1)
  await expect(dlg, 'rester : boîte ouverte').toBeVisible()
  await expect(dlg.locator('#bcf-note'), 'rester : saisie gardée').toHaveValue(`Livraison quai 2 ${m}`)
  dem.prochaine = 'rester'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.vues, { message: 'Échap : demande posée' }).toBe(2)
  await expect(dlg.locator('#bcf-note')).toHaveValue(`Livraison quai 2 ${m}`)
  await capturer(p, 'PF12.3-AERR37-bcf', 1)
  dem.prochaine = 'quitter'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.vues).toBe(3)
  await expect(dlg).toBeHidden()
  expect(await py(`from apps.achats.models import BonCommandeFournisseur
sortie(BonCommandeFournisseur.objects.get(pk=${ids.bcfs[0]}).note)`), 'base : note non écrite').toBeNull()
  await p.reload()
  await ouvrir()
  await expect(dlg.locator('#bcf-note'), 'après rechargement : note vide').toHaveValue('')
  await p.keyboard.press('Escape')
  await auRepos(p)
})

// ═══ PF12.3 — AERR124 : « Gammes & marques » et « Achats » illisibles ⇒ avis + Réessayer, Enregistrer désactivé ═══
for (const [cle, chemin, api, regex, ecrit, message, champ, valeurLue] of [
  ['gammes', '/parametres/gammes', '/ventes/parametres-gammes/', /\/api\/django\/ventes\/parametres-gammes\/(\?.*)?$/,
    /\/api\/django\/ventes\/parametres-gammes\//, 'Réglages illisibles — la lecture a échoué', '#gm-nom-essentielle',
    (v) => v.nom_essentielle],
  ['achats', '/parametres/achats', '/stock/achats-parametres/', /\/api\/django\/stock\/achats-parametres\/(\?.*)?$/,
    /\/api\/django\/stock\/achats-parametres\//, 'Réglages illisibles — paramètres achats non lus', '#ap-tol-prix-pct',
    (v) => String(v.tolerance_prix_pct ?? '0')],
]) {
  etape(`PF12.3-AERR124-${cle}`, ['AERR124'], async ({ page, suivi, testInfo }) => {
    const r = page.request
    const avant = await lire(r, api, 'réglages avant')
    const m = marque()
    const nom = `aerr124${cle.slice(0, 2)}_${m}`
    await compteRole(nom, 'Administrateur')
    const { p } = await ecran(page, suivi, testInfo, nom)
    const ecritures = compter(p, 'PATCH', ecrit)
    const posts = compter(p, 'POST', ecrit)
    const puts = compter(p, 'PUT', ecrit)
    const lecture = await panne(p, suivi, regex)
    await p.goto(chemin)
    const avis = p.getByRole('alert').filter({ hasText: message })
    await expect(avis, 'avis « Réglages illisibles »').toBeVisible({ timeout: 60_000 })
    await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
    const enregistrer = p.locator('form').getByRole('button', { name: 'Enregistrer', exact: true })
    await expect(enregistrer, 'Enregistrer désactivé').toBeDisabled()
    // Entrée dans un champ (soumission clavier) : aucun envoi.
    await p.locator(champ).press('Enter')
    await capturer(p, `PF12.3-AERR124-${cle}`, 1)
    expect([ecritures.length, posts.length, puts.length], 'aucune écriture des réglages').toEqual([0, 0, 0])
    expect(await lire(r, api, 'réglages relus'), 'réglages intacts').toEqual(avant)
    // Réessayer (serveur revenu) : le formulaire est rempli et l'enregistrement rendu.
    await lecture.lever()
    await avis.getByRole('button', { name: 'Réessayer' }).click()
    await expect(avis, 'lecture réussie : avis retiré').toHaveCount(0, { timeout: 30_000 })
    await expect(enregistrer, 'Enregistrer rendu').toBeEnabled()
    await expect(p.locator(champ), 'formulaire rempli des valeurs lues').toHaveValue(valeurLue(avant))
    await p.reload()
    await expect(enregistrer, 'après rechargement : Enregistrer actif').toBeEnabled({ timeout: 60_000 })
    expect([ecritures.length, posts.length, puts.length], 'toujours aucune écriture').toEqual([0, 0, 0])
    await auRepos(p)
  })
}
