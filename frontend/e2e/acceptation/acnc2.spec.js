// Preuves en direct ACNC, lot 2 (audit PF9 « doubles clics, gestes rejoués, courses », dossier
// docs/audits/2026-11-11-parcours-PF9.md) : ACNC25, 26, 27, 33, 35, 41, 42, 44, 45, 46, 47, 49, 52, 53, 55.
//
// RÈGLE DU LOT — une preuve de concurrence joue VRAIMENT deux gestes et constate UN SEUL effet :
//   · COURSE RÉELLE (`course`) : le shell Django — une seconde connexion Postgres, « le collègue » — ouvre une
//     transaction et pose un verrou (ligne, table ou verrou consultatif) ; les deux requêtes partent par
//     `page.request` (ou deux clics à l'écran) ; on attend de VOIR dans `pg_stat_activity` les requêtes
//     bloquées EN MÊME TEMPS (preuve que les workers gunicorn les servent en parallèle : une course jouée l'une
//     après l'autre ne passerait jamais par là), puis le verrou tombe et les deux gestes reprennent ensemble ;
//   · on RELIT la base (shell Django) : un seul objet, un seul mouvement, un seul envoi en file ;
//   · écran nommé par la clause : bouton AFFIRMÉ occupé (`disabled` + `aria-busy`) pendant l'envoi tenu par une
//     route Playwright, un seul envoi compté, message affiché, puis relu après rechargement.
// Compte : demo_admin (rôle système « Administrateur » de la démo) sauf mention ; second compte au rôle
// livré « Directeur » pour la seconde session d'ACNC55. Données propres créées par le shell ou
// l'API, retirées en fin d'étape (best-effort : la base du runner est jetable).
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { createHash, createHmac } from 'node:crypto'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ACNC', ['ACNC25', 'ACNC26', 'ACNC27', 'ACNC33', 'ACNC35', 'ACNC41', 'ACNC42', 'ACNC44', 'ACNC45',
  'ACNC46', 'ACNC47', 'ACNC49', 'ACNC52', 'ACNC53', 'ACNC55'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 480_000 })
// Écran large : la fiche ticket SAV déborde du panneau latéral à 1280 px (constat asav.spec.js).
test.use({ viewport: { width: 1920, height: 1080 }, actionTimeout: 60_000 })
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
const ADMIN = `U.objects.get(username='demo_admin')`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()
const lire = async (r) => ({ s: r.status(), b: await r.json().catch(() => null) })
const statuts = (reps) => reps.map((x) => x.s).sort((a, b) => a - b)

// ── Course réelle (deux connexions Postgres) ──────────────────────────────────────────────────────────────────
const EN_ATTENTE = `from django.db import connection
with connection.cursor() as c:
    c.execute("select pg_stat_clear_snapshot()")
    c.execute("select left(query, 90) from pg_stat_activity where wait_event_type = 'Lock' and pid <> pg_backend_pid() and datname = current_database()")
    sortie([r[0] for r in c.fetchall()])`

/** Le shell pose `verrou` dans une transaction ouverte ; `gestes` partent ; on attend `n` requêtes bloquées
 *  ENSEMBLE dans Postgres (requêtes en attente relevées dans `pg_stat_activity`) ; `pendant` (code du collègue)
 *  s'exécute alors dans SA transaction ; enfin le shell valide (`valider`) ou annule — les gestes reprennent.
 *  Rend { reponses, attentes } (attentes = début des requêtes SQL qui attendaient). */
async function course({ verrou, gestes, n = 2, pendant = '', valider = false, quoi }) {
  await py(`from django.db import transaction
transaction.set_autocommit(False)
${verrou}
sortie(True)`)
  let enVol = null
  let attentes = []
  try {
    enVol = Promise.all(gestes.map((g) => g()))
    enVol.catch(() => undefined)
    await expect.poll(async () => { attentes = await py(EN_ATTENTE); return attentes.length },
      { message: `${quoi} : ${n} requête(s) bloquée(s) ensemble dans Postgres`, timeout: 90_000 }).toBeGreaterThanOrEqual(n)
    if (pendant) await py(`${pendant}\nsortie(True)`)
  } finally {
    await py(`from django.db import transaction
if ${valider ? 'True' : 'False'}:
    transaction.commit()
else:
    transaction.rollback()
transaction.set_autocommit(True)
sortie(True)`)
  }
  const reponses = await enVol
  console.log(`[${quoi}] requêtes bloquées ensemble : ${J(attentes)} → réponses ${J(reponses.map((x) => x?.s ?? x))}`)
  return { reponses, attentes }
}

/** Sonde HÔTE `docs/audits/sondes/ACNC/<c>.py` ; {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'ACNC', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
/** Sonde aux bouchons PÉRIMÉS (le code corrigé a changé les symboles qu'elle extrait : C-ACNC-007 lève NameError
 *  `_ecriture_bornee`, C-ACNC-011 ne peut plus importer `verrouiller_produit` et ses fils ne jouent aucun geste —
 *  « statuts: [] ») : NOMMÉE et relevée, jamais comptée ; la course réelle de l'étape la remplace. */
function sondePerimee(constat) {
  const s = sondeHote(constat)
  console.log(`[sonde ${constat}] périmée, non comptée : ${s.ok ? J(s.res).slice(0, 400) : s.err}`)
}

/** Compte d'essai du rôle LIVRÉ `nomRole` (société démo) ; renvoie son id. */
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
  contextesUi.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}

/** Tient une requête (méthode + chemin) jusqu'à `liberer()` ; `envois` compte les requêtes parties. */
async function tenir(p, methode, chemin) {
  let liberer
  const porte = new Promise((res) => { liberer = res })
  const etat = { envois: 0, liberer: () => liberer() }
  await p.route((u) => u.pathname === chemin, async (route) => {
    if (route.request().method() !== methode) { await route.fallback(); return }
    etat.envois += 1
    await porte
    await route.fallback().catch(() => undefined)
  })
  return etat
}
/** Affirme un bouton OCCUPÉ (désactivé + aria-busy), puis tente un second clic forcé (sans effet sur un bouton désactivé). */
async function boutonOccupe(bouton, quoi) {
  await expect(bouton, `${quoi} : désactivé pendant l'envoi`).toBeDisabled({ timeout: 30_000 })
  await expect(bouton, `${quoi} : aria-busy pendant l'envoi`).toHaveAttribute('aria-busy', 'true')
  await bouton.click({ force: true, timeout: 5_000 }).catch(() => undefined)
}

// ── Fixtures SAV ─────────────────────────────────────────────────────────────────────────────────────────────
const ticketSav = (m, tag, stock = 10) => py(`from decimal import Decimal as D
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.sav.models import Ticket
a = ${ADMIN}; co = a.company_id
cl = Client.objects.create(company_id=co, nom='${tag} ${m}', prenom='Essai', email='${tag.toLowerCase()}-${m}@example.invalid')
p = Produit.objects.create(company_id=co, nom='Piece ${tag} ${m}', sku='${tag}-${m}', prix_vente=D('100'), prix_achat=D('60'), quantite_stock=${stock})
t = Ticket.objects.create(company_id=co, reference='SAV-${tag}-${m}', client=cl, type=Ticket.Type.CORRECTIF, sous_garantie=Ticket.SousGarantie.NON, description='Panne ${tag} ${m}', created_by=a)
sortie(dict(client=cl.pk, produit=p.pk, nom=p.nom, ticket=t.pk, ref=t.reference))`)
const etatStock = (produit) => py(`from apps.stock.models import Produit, MouvementStock
mv = MouvementStock.objects.filter(produit_id=${produit}).order_by('pk')
sortie(dict(stock=float(Produit.objects.get(pk=${produit}).quantite_stock),
  entrees=[[float(m.quantite_avant), float(m.quantite_apres)] for m in mv if m.type_mouvement == 'entree'],
  sorties=[[float(m.quantite_avant), float(m.quantite_apres)] for m in mv if m.type_mouvement == 'sortie']))`)
const nettoyerSav = (x) => py(`from apps.sav.models import Ticket, PieceConsommee, PretEquipement
from apps.stock.models import Produit, MouvementStock
from apps.crm.models import Client
for f in (lambda: PieceConsommee.objects.filter(ticket__client_id=${x.client}).delete(),
          lambda: PretEquipement.objects.filter(ticket__client_id=${x.client}).delete(),
          lambda: Ticket.objects.filter(client_id=${x.client}).delete(),
          lambda: MouvementStock.objects.filter(produit_id=${x.produit}).delete(),
          lambda: Produit.objects.filter(pk=${x.produit}).delete(),
          lambda: Client.objects.filter(pk=${x.client}).delete()):
    try: f()
    except Exception as exc: print('nettoyage', exc)
sortie(True)`)
const section = (p, titre) => p.locator('details').filter({ has: p.locator('summary', { hasText: titre }) }).first()
const ouvrirTicket = async (p, id) => {
  await p.goto(`/sav?id=${id}`)
  await expect(p.getByText('Pièces consommées').first(), 'fiche ticket ouverte').toBeVisible({ timeout: 60_000 })
}

// ═══ PF9.2 — ACNC26 (API) : deux « Retirer » croisés = une ENTRÉE (le 2ᵉ 404) ; pose renvoyée avec la même clé = une pièce ═══
etape('PF9.2-ACNC26-api', ['ACNC26'], async ({ page }) => {
  sondePerimee('C-ACNC-011')
  const r = page.request
  const m = marque()
  const x = await ticketSav(m, 'ACNC26')
  apres.push(() => nettoyerSav(x))
  const url = `${API}/sav/tickets/${x.ticket}/pieces/`
  const cle = `acnc26-${m}`
  const poser = () => r.post(url, { ...T, data: { produit: x.produit, quantite: '3', decrement: true }, headers: { 'Idempotency-Key': cle } }).then(lire)
  // Rejeu réseau : la même pose (même clé) envoyée deux fois EN PARALLÈLE, puis une troisième fois après coup.
  const [a1, a2] = await Promise.all([poser(), poser()])
  console.log(`[ACNC26] pose doublée (même clé) : ${J([a1.s, a2.s])} ${J([a1.b?.id ?? a1.b?.code, a2.b?.id ?? a2.b?.code])}`)
  const creees = [a1, a2].filter((a) => a.s === 201)
  expect(creees.length, 'au moins une pose 201').toBeGreaterThanOrEqual(1)
  for (const a of [a1, a2]) {
    expect(a.s === 201 || (a.s === 409 && a.b?.code === 'idempotency_en_cours'), `réponse ${a.s} ${J(a.b)} : 201 (rejeu) ou 409 « en cours »`).toBe(true)
  }
  expect(new Set(creees.map((a) => a.b.id)).size, 'les 201 portent la MÊME pièce').toBe(1)
  const a3 = await poser()
  expect([a3.s, a3.b?.id], 'renvoi après coup (même clé) : la même pièce rejouée').toEqual([201, creees[0].b.id])
  const piece = creees[0].b.id
  const apresPose = await py(`from apps.sav.models import PieceConsommee
sortie(list(PieceConsommee.objects.filter(ticket_id=${x.ticket}).values_list('pk', flat=True)))`)
  expect(apresPose, 'une seule pièce posée').toEqual([piece])
  const s0 = await etatStock(x.produit)
  expect([s0.stock, s0.sorties], 'une seule SORTIE 10 → 7').toEqual([7, [[10, 7]]])
  // Course : deux DELETE de la même pièce, bloqués ensemble sur la pièce verrouillée par le collègue.
  const retirer = () => r.delete(`${url}${piece}/`, T).then(lire)
  const { reponses } = await course({
    quoi: 'ACNC26 retraits croisés',
    verrou: `from apps.sav.models import PieceConsommee\nPieceConsommee.objects.select_for_update().get(pk=${piece})`,
    gestes: [retirer, retirer],
  })
  expect(statuts(reponses), 'un retrait 204, le second 404').toEqual([204, 404])
  const s1 = await etatStock(x.produit)
  expect([s1.stock, s1.entrees], 'une seule ENTRÉE 7 → 10').toEqual([10, [[7, 10]]])
  expect(await py(`from apps.sav.models import PieceConsommee
sortie(PieceConsommee.objects.filter(ticket_id=${x.ticket}).count())`), 'pièce retirée').toBe(0)
})

// ═══ PF9.4 — ACNC26 (écran /sav) : « Retirer » désactivé pendant l'envoi, deux clics = un DELETE, une ENTRÉE ═══
etape('PF9.4-ACNC26-ecran', ['ACNC26'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await ticketSav(m, 'ACNC26E')
  apres.push(() => nettoyerSav(x))
  const pose = await lireJson(await r.post(`${API}/sav/tickets/${x.ticket}/pieces/`, { ...T, data: { produit: x.produit, quantite: '3', decrement: true } }), 'pose')
  await ouvrirTicket(page, x.ticket)
  const ligne = section(page, 'Pièces consommées').locator('li').filter({ hasText: x.nom })
  await expect(ligne, 'pièce listée, stock −').toContainText('stock −', { timeout: 60_000 })
  const tenu = await tenir(page, 'DELETE', `${API}/sav/tickets/${x.ticket}/pieces/${pose.id}/`)
  const bouton = ligne.getByRole('button', { name: 'Retirer' })
  await bouton.click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Retirer' }).click()
  await expect.poll(() => tenu.envois, { message: 'le DELETE est parti' }).toBe(1)
  await boutonOccupe(bouton, '« Retirer »')
  await expect(page.getByRole('alertdialog'), 'le 2ᵉ clic ne rouvre pas la confirmation').toHaveCount(0)
  tenu.liberer()
  await expect(ligne, 'la pièce quitte la liste').toHaveCount(0, { timeout: 60_000 })
  expect(tenu.envois, 'un seul DELETE envoyé').toBe(1)
  const s = await etatStock(x.produit)
  expect([s.stock, s.entrees], 'une seule ENTRÉE 7 → 10').toEqual([10, [[7, 10]]])
  await page.reload()
  await expect(page.getByText('Pièces consommées').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('Aucune pièce enregistrée.').first(), 'après rechargement : aucune pièce').toBeVisible({ timeout: 60_000 })
  await page.unrouteAll({ behavior: 'ignoreErrors' })
})

// ═══ PF9.2 — ACNC27 (API) : deux prêts simultanés = stock 8 (10→9, 9→8) ; deux « Retourner » croisés = une ENTRÉE ═══
etape('PF9.2-ACNC27-api', ['ACNC27'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await ticketSav(m, 'ACNC27')
  apres.push(() => nettoyerSav(x))
  const preter = () => r.post(`${API}/sav/tickets/${x.ticket}/prets-equipement/`, { ...T, data: { produit: x.produit } }).then(lire)
  const prets = await course({
    quoi: 'ACNC27 prêts simultanés',
    verrou: `from apps.stock.models import Produit\nProduit.objects.select_for_update().get(pk=${x.produit})`,
    gestes: [preter, preter],
  })
  expect(statuts(prets.reponses), 'deux prêts 201').toEqual([201, 201])
  const s0 = await etatStock(x.produit)
  expect([s0.stock, s0.sorties], 'stock 8 : 10 → 9 puis 9 → 8').toEqual([8, [[10, 9], [9, 8]]])
  const pret = prets.reponses[0].b.id
  const retourner = () => r.post(`${API}/sav/tickets/${x.ticket}/prets-equipement/${pret}/retourner/`, { ...T, data: {} }).then(lire)
  const retours = await course({
    quoi: 'ACNC27 retours croisés',
    verrou: `from apps.sav.models import PretEquipement\nPretEquipement.objects.select_for_update().get(pk=${pret})`,
    gestes: [retourner, retourner],
  })
  expect(statuts(retours.reponses), 'deux réponses 200').toEqual([200, 200])
  expect(retours.reponses.map((a) => a.b?.statut), 'les deux rendent le prêt « retourné »').toEqual(['retourne', 'retourne'])
  const s1 = await etatStock(x.produit)
  expect([s1.stock, s1.entrees], 'une seule ENTRÉE 8 → 9').toEqual([9, [[8, 9]]])
  expect(await py(`from apps.sav.models import PretEquipement
p = PretEquipement.objects.get(pk=${pret}); sortie([p.statut, p.stock_reintegre])`), 'prêt relu').toEqual(['retourne', true])
})

// ═══ PF9.4 — ACNC27 (écran /sav « Actions avancées ») : « Retourner » désactivé pendant l'envoi, un retour, une ENTRÉE ═══
etape('PF9.4-ACNC27-ecran', ['ACNC27'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await ticketSav(m, 'ACNC27E')
  apres.push(() => nettoyerSav(x))
  const pret = await lireJson(await r.post(`${API}/sav/tickets/${x.ticket}/prets-equipement/`, { ...T, data: { produit: x.produit } }), 'prêt')
  await ouvrirTicket(page, x.ticket)
  await expect(page.getByText('Actions avancées').first()).toBeVisible({ timeout: 60_000 })
  const ligne = section(page, 'Actions avancées').locator('li').filter({ hasText: `${x.nom} — sorti le` })
  const bouton = ligne.getByRole('button', { name: 'Retourner' })
  await expect(bouton, 'prêt en cours listé').toBeVisible({ timeout: 60_000 })
  const tenu = await tenir(page, 'POST', `${API}/sav/tickets/${x.ticket}/prets-equipement/${pret.id}/retourner/`)
  await bouton.click()
  await expect.poll(() => tenu.envois, { message: 'le retour est parti' }).toBe(1)
  await boutonOccupe(bouton, '« Retourner »')
  tenu.liberer()
  await expect(toast(page, 'Prêt retourné'), 'message affiché').toBeVisible({ timeout: 60_000 })
  await expect(ligne, 'prêt marqué retourné').toContainText('retourné le', { timeout: 60_000 })
  await expect(ligne.getByRole('button', { name: 'Retourner' }), 'plus de bouton « Retourner »').toHaveCount(0)
  expect(tenu.envois, 'un seul retour envoyé').toBe(1)
  const s = await etatStock(x.produit)
  expect([s.stock, s.entrees], 'une seule ENTRÉE 9 → 10').toEqual([10, [[9, 10]]])
  await page.reload()
  await expect(ligne, 'après rechargement : retourné').toContainText('retourné le', { timeout: 60_000 })
  await page.unrouteAll({ behavior: 'ignoreErrors' })
})

// ═══ PF9.2 — ACNC33 (API) : « Créer un devis » rejoué puis croisé = un devis (200 même id) ; deux tickets identiques = un (409) ═══
const devisDuClient = (client) => py(`from apps.ventes.models import Devis
sortie(list(Devis.objects.filter(client_id=${client}).values_list('id', 'reference')))`)
const nettoyerDevis = (client) => py(`from apps.ventes.models import Devis
try: Devis.objects.filter(client_id=${client}).delete()
except Exception as exc: print('nettoyage devis', exc)
sortie(True)`)
etape('PF9.2-ACNC33-api', ['ACNC33'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await ticketSav(m, 'ACNC33')
  apres.push(() => nettoyerSav(x))
  apres.unshift(() => nettoyerDevis(x.client))
  const url = (t) => `${API}/sav/tickets/${t}/creer-devis/`
  // (a) rejeu séquentiel : le second appel (après le commit du premier) rend le devis lié.
  const d1 = await lire(await r.post(url(x.ticket), { ...T, data: {} }))
  const d2 = await lire(await r.post(url(x.ticket), { ...T, data: {} }))
  expect([d1.s, d2.s], 'séquentiel : 201 puis 200').toEqual([201, 200])
  expect(d2.b.devis_id, 'même devis').toBe(d1.b.devis_id)
  // (b) course : deux « Créer un devis » sur un 2ᵉ ticket, bloqués ensemble sur le ticket verrouillé.
  const t2 = await py(`from apps.sav.models import Ticket
a = ${ADMIN}
t = Ticket.objects.create(company_id=a.company_id, reference='SAV-ACNC33B-${m}', client_id=${x.client}, type=Ticket.Type.CORRECTIF, sous_garantie=Ticket.SousGarantie.NON, description='Panne 2 ${m}', created_by=a)
sortie(t.pk)`)
  const creer = () => r.post(url(t2), { ...T, data: {} }).then(lire)
  const { reponses } = await course({
    quoi: 'ACNC33 créer-devis croisés',
    verrou: `from apps.sav.models import Ticket\nTicket.objects.select_for_update().get(pk=${t2})`,
    gestes: [creer, creer],
  })
  expect(statuts(reponses), 'un 201, l\'autre 200').toEqual([200, 201])
  expect(reponses[0].b.devis_id, 'les deux réponses portent le même devis').toBe(reponses[1].b.devis_id)
  const devis = await devisDuClient(x.client)
  expect(devis.length, 'un devis par ticket (aucun orphelin)').toBe(2)
  const lies = await py(`from apps.sav.models import Ticket
sortie([Ticket.objects.get(pk=${x.ticket}).devis_id_ext, Ticket.objects.get(pk=${t2}).devis_id_ext])`)
  expect(lies, 'chaque ticket lié à son devis').toEqual([d1.b.devis_id, reponses[0].b.devis_id])
  // (c) deux créations simultanées du même ticket (corps identique) : une seule, l'autre 409 nommant la référence.
  const corps = { client: x.client, description: `Onduleur muet ACNC33 ${m}`, type: 'correctif', priorite: 'normale' }
  const creerTicket = () => r.post(`${API}/sav/tickets/`, { ...T, data: corps }).then(lire)
  const tickets = await course({
    quoi: 'ACNC33 tickets identiques simultanés',
    verrou: `from apps.crm.models import Client\nClient.objects.select_for_update().get(pk=${x.client})`,
    gestes: [creerTicket, creerTicket],
  })
  expect(statuts(tickets.reponses), 'un 201, l\'autre 409').toEqual([201, 409])
  const cree = tickets.reponses.find((a) => a.s === 201).b
  expect(tickets.reponses.find((a) => a.s === 409).b?.reference_existante, '409 nomme la référence existante').toBe(cree.reference)
  expect(await py(`from apps.sav.models import Ticket
sortie(Ticket.objects.filter(client_id=${x.client}, description=${J(corps.description)}).count())`), 'un seul ticket en base').toBe(1)
})

// ═══ PF9.4 — ACNC33 (écran /sav, deux onglets) : « Créer un devis » dans chacun = un devis, le 2ᵉ onglet l'ouvre ═══
etape('PF9.4-ACNC33-ecran', ['ACNC33'], async ({ page, context, suivi }) => {
  const m = marque()
  const x = await ticketSav(m, 'ACNC33E')
  apres.push(() => nettoyerSav(x))
  apres.unshift(() => nettoyerDevis(x.client))
  const p2 = suivi.surveiller(await context.newPage())
  await p2.addInitScript(INIT)
  await ouvrirTicket(page, x.ticket)
  await ouvrirTicket(p2, x.ticket)
  const b1 = page.getByRole('button', { name: 'Créer un devis' })
  const b2 = p2.getByRole('button', { name: 'Créer un devis' })
  await expect(b1).toBeVisible({ timeout: 60_000 })
  await expect(b2).toBeVisible({ timeout: 60_000 })
  await course({
    quoi: 'ACNC33 écran deux onglets',
    verrou: `from apps.sav.models import Ticket\nTicket.objects.select_for_update().get(pk=${x.ticket})`,
    gestes: [() => b1.click(), () => b2.click()],
  })
  for (const p of [page, p2]) await expect(p.getByText('Devis créé').first(), 'les deux réponses sont revenues').toBeVisible({ timeout: 60_000 })
  const devis = await devisDuClient(x.client)
  expect(devis.length, 'un seul devis en base').toBe(1)
  const ref = devis[0][1]
  for (const [p, nom] of [[page, 'onglet 1'], [p2, 'onglet 2']]) {
    await expect(toast(p, ref), `${nom} : le message nomme le MÊME devis ${ref}`).toBeVisible({ timeout: 60_000 })
    await expect(p.getByText('Devis créé').first(), `${nom} : « Devis créé »`).toBeVisible({ timeout: 30_000 })
  }
  expect(await py(`from apps.sav.models import Ticket
sortie(Ticket.objects.get(pk=${x.ticket}).devis_id_ext)`), 'ticket lié au devis').toBe(devis[0][0])
  await p2.reload()
  await expect(p2.getByText('Devis créé').first(), 'après rechargement : « Devis créé »').toBeVisible({ timeout: 60_000 })
  await expect(p2.getByRole('button', { name: 'Créer un devis' })).toHaveCount(0)
  await p2.close()
})

// ═══ PF9.2 — ACNC35 (API) : deux « Générer les visites dues » croisés = un ticket préventif par contrat dû ═══
const contratDu = (client, m) => py(`from datetime import timedelta
from apps.sav.models import ContratMaintenance
c = ContratMaintenance.objects.create(company_id=${SOC}, client_id=${client}, periodicite='annuel', date_debut=timezone.localdate() - timedelta(days=400), notes='ACNC35 ${m}')
sortie(dict(id=c.pk, due=c.prochaine_visite().isoformat(), du=c.is_due()))`)
/** Contrats dus de la démo hors `exclure` (« Générer » les traite aussi) : relevés avant ; après l'étape, leurs
 *  tickets générés sont retirés et leur échéance rétablie. */
async function garderContratsDemo(exclure) {
  const autres = await py(`from apps.sav.models import ContratMaintenance
sortie([[k.pk, str(k.derniere_visite) if k.derniere_visite else None] for k in ContratMaintenance.objects.filter(company_id=${SOC}, actif=True).exclude(pk=${exclure}) if k.is_due()])`)
  const t0 = await py(`sortie(timezone.now().isoformat())`)
  apres.unshift(() => py(`from apps.sav.models import Ticket, ContratMaintenance
from django.utils.dateparse import parse_datetime
for pk, d in ${J(autres)}:
    Ticket.objects.filter(type='preventif', description__contains='(contrat #%d)' % pk, date_creation__gte=parse_datetime(${J(t0)})).delete()
    ContratMaintenance.objects.filter(pk=pk).update(derniere_visite=d)
sortie(True)`))
  return autres
}
const preventifs = (contrat) => py(`from apps.sav.models import Ticket, ContratMaintenance
sortie(dict(n=Ticket.objects.filter(type='preventif', description__contains='(contrat #${contrat})').count(),
  derniere=str(ContratMaintenance.objects.get(pk=${contrat}).derniere_visite)))`)
etape('PF9.2-ACNC35-api', ['ACNC35'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await ticketSav(m, 'ACNC35')
  apres.push(() => nettoyerSav(x))
  const c = await contratDu(x.client, m)
  expect(c.du, 'contrat dû').toBe(true)
  const autres = await garderContratsDemo(c.id)
  apres.unshift(() => py(`from apps.sav.models import Ticket, ContratMaintenance
Ticket.objects.filter(description__contains='(contrat #${c.id})').delete()
ContratMaintenance.objects.filter(pk=${c.id}).delete()
sortie(True)`))
  const generer = () => r.post(`${API}/sav/contrats-maintenance/generer-dus/`, { ...T, data: {} }).then(lire)
  const { reponses } = await course({
    quoi: 'ACNC35 générations croisées',
    verrou: `from apps.sav.models import ContratMaintenance\nContratMaintenance.objects.select_for_update().get(pk=${c.id})`,
    gestes: [generer, generer],
  })
  expect(statuts(reponses), 'deux 200').toEqual([200, 200])
  const nb = reponses.map((a) => a.b.tickets_generes)
  expect(nb[0] + nb[1], `un ticket par contrat dû (${autres.length + 1} contrat(s) dû(s))`).toBe(autres.length + 1)
  if (autres.length === 0) expect(nb.sort(), 'le second appel rend tickets_generes: 0').toEqual([0, 1])
  expect(await preventifs(c.id), 'un seul ticket préventif, derniere_visite avancée à l\'échéance').toEqual({ n: 1, derniere: c.due })
  for (const [pk] of autres) expect((await preventifs(pk)).n, `contrat de démo #${pk} : un seul ticket`).toBeLessThanOrEqual(1)
})

// ═══ PF9.4 — ACNC35 (écran /sav/contrats, /sav/warranty-claims) : « Générer », « Ajouter » (contrat), « Créer » (réclamation) occupés ═══
etape('PF9.4-ACNC35-ecran', ['ACNC35'], async ({ page }) => {
  const m = marque()
  const x = await ticketSav(m, 'ACNC35E')
  const c = await contratDu(x.client, m)
  await garderContratsDemo(c.id)
  const eq = await py(`from apps.installations.models import Installation
from apps.sav.models import Equipement
inst = Installation.objects.create(company_id=${SOC}, reference='CHT-ACNC35-${m}', client_id=${x.client})
e = Equipement.objects.create(company_id=${SOC}, produit_id=${x.produit}, installation=inst, numero_serie='SN-ACNC35-${m}', date_pose=timezone.localdate() - datetime.timedelta(days=30))
sortie(dict(inst=inst.pk, eq=e.pk))`)
  apres.unshift(() => py(`from apps.sav.models import Ticket, ContratMaintenance, WarrantyClaim, Equipement
from apps.installations.models import Installation
WarrantyClaim.objects.filter(equipement_id=${eq.eq}).delete()
Ticket.objects.filter(client_id=${x.client}).delete()
ContratMaintenance.objects.filter(client_id=${x.client}).delete()
Equipement.objects.filter(pk=${eq.eq}).delete()
Installation.objects.filter(pk=${eq.inst}).delete()
sortie(True)`))
  apres.push(() => nettoyerSav(x))
  // « Générer les visites dues » : requête tenue, bouton occupé, double clic = un envoi.
  await page.goto('/sav/contrats')
  const generer = page.getByRole('button', { name: 'Générer les visites dues' })
  await expect(generer).toBeVisible({ timeout: 60_000 })
  const tg = await tenir(page, 'POST', `${API}/sav/contrats-maintenance/generer-dus/`)
  await generer.dblclick()
  await expect.poll(() => tg.envois, { message: 'la génération est partie' }).toBe(1)
  await boutonOccupe(generer, '« Générer les visites dues »')
  tg.liberer()
  await expect(page.locator('[data-sonner-toast]').filter({ hasText: /ticket\(s\) de maintenance généré\(s\)/ }).first(), 'compte généré affiché').toBeVisible({ timeout: 60_000 })
  expect(tg.envois, 'un seul envoi pour un double clic').toBe(1)
  expect((await preventifs(c.id)).n, 'un ticket préventif pour le contrat dû').toBe(1)
  // « Ajouter » (contrat) : deux Entrée = un envoi.
  const form = page.locator('form').filter({ has: page.getByRole('button', { name: 'Ajouter' }) }).first()
  await form.getByRole('combobox').first().click()
  await page.getByRole('option', { name: new RegExp(`ACNC35E ${m}`) }).click()
  await form.locator('input[type="date"]').first().fill(await py(`sortie(timezone.localdate().isoformat())`))
  const prix = `1${Math.floor(Math.random() * 900 + 100)}.55`
  await form.locator('input[type="number"]').nth(0).fill(prix)
  const duree = form.locator('input[type="number"]').nth(1)
  await duree.fill('12')
  const tc = await tenir(page, 'POST', `${API}/sav/contrats-maintenance/`)
  await duree.press('Enter')
  await expect.poll(() => tc.envois, { message: 'la création est partie' }).toBe(1)
  await duree.press('Enter')
  await boutonOccupe(form.getByRole('button', { name: 'Ajouter' }), '« Ajouter » (contrat)')
  tc.liberer()
  await expect.poll(() => py(`from apps.sav.models import ContratMaintenance
sortie(ContratMaintenance.objects.filter(client_id=${x.client}, prix=${J(prix)}).count())`), { message: 'contrat créé', timeout: 60_000 }).toBe(1)
  expect(tc.envois, 'deux Entrée = un seul envoi').toBe(1)
  // « Créer » (réclamation) : deux Entrée = un envoi.
  await page.goto('/sav/warranty-claims')
  const f2 = page.locator('form').filter({ has: page.getByRole('button', { name: 'Créer' }) }).first()
  await f2.getByRole('combobox').first().click({ timeout: 60_000 })
  await page.getByRole('option', { name: new RegExp(`SN-ACNC35-${m}`) }).click()
  await f2.locator('textarea').first().fill(`Défaut ACNC35 ${m}`)
  const rma = f2.locator('input:not([type="date"]):not([type="hidden"]):not([type="checkbox"])').first()
  await rma.fill(`RMA-${m}`)
  const tw = await tenir(page, 'POST', `${API}/sav/warranty-claims/`)
  await rma.press('Enter')
  await expect.poll(() => tw.envois, { message: 'la réclamation est partie' }).toBe(1)
  await rma.press('Enter')
  await boutonOccupe(f2.getByRole('button', { name: 'Créer' }), '« Créer » (réclamation)')
  tw.liberer()
  await expect(toast(page, 'Réclamation garantie créée'), 'message affiché').toBeVisible({ timeout: 60_000 })
  expect(tw.envois, 'deux Entrée = un seul envoi').toBe(1)
  expect(await py(`from apps.sav.models import WarrantyClaim
sortie(WarrantyClaim.objects.filter(equipement_id=${eq.eq}).count())`), 'une seule réclamation').toBe(1)
  // Persistance : recharger les contrats — le contrat créé est listé une fois.
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await page.goto('/sav/contrats')
  await expect(page.getByRole('row').filter({ hasText: `ACNC35E ${m}` }).first(),
    'après rechargement : les contrats du client sont listés').toBeVisible({ timeout: 60_000 })
})

// ═══ PF9.5 — ACNC41 (API) : un PATCH {note} d'un BC dont un collègue commite « confirmé » pendant l'écriture ═══
const bcEnAttente = async (r, m, tag) => {
  const cl = await py(`from apps.crm.models import Client
sortie(Client.objects.create(company_id=${SOC}, nom='${tag} ${m}', prenom='Essai', email='${tag.toLowerCase()}-${m}@example.invalid').pk)`)
  const bc = await lireJson(await r.post(`${API}/ventes/bons-commande/`, { ...T, data: { client: cl, note: 'avant' } }), 'BC')
  return { client: cl, bc: bc.id, reference: bc.reference }
}
const etatBc = (id) => py(`from apps.ventes.models import BonCommande
b = BonCommande.objects.get(pk=${id}); sortie([b.statut, b.note])`)
const nettoyerBc = (x) => py(`from apps.ventes.models import BonCommande
from apps.crm.models import Client
BonCommande.objects.filter(client_id=${x.client}).delete(); Client.objects.filter(pk=${x.client}).delete()
sortie(True)`)
etape('PF9.5-ACNC41-api', ['ACNC41'], async ({ page }) => {
  sondePerimee('C-ACNC-007')
  const r = page.request
  const x = await bcEnAttente(r, marque(), 'ACNC41')
  apres.push(() => nettoyerBc(x))
  expect(await etatBc(x.bc)).toEqual(['en_attente', 'avant'])
  const { reponses, attentes } = await course({
    quoi: 'ACNC41 PATCH croisé avec « Confirmer »',
    verrou: `from apps.ventes.models import BonCommande\nBonCommande.objects.select_for_update().get(pk=${x.bc})`,
    gestes: [() => r.patch(`${API}/ventes/bons-commande/${x.bc}/`, { ...T, data: { note: 'après' } }).then(lire)],
    n: 1,
    pendant: `from apps.ventes.models import BonCommande\nBonCommande.objects.filter(pk=${x.bc}).update(statut='confirme')`,
    valider: true,
  })
  expect(attentes[0], 'le PATCH attendait sur son ÉCRITURE (sa lecture était déjà faite)').toMatch(/^UPDATE /)
  expect(reponses[0].s, 'PATCH 200').toBe(200)
  expect(await etatBc(x.bc), 'statut commité par le collègue CONSERVÉ, note écrite').toEqual(['confirme', 'après'])
})

// ═══ PF9.4 — ACNC41 (écran /ventes/bons-commande) : « Mettre à jour » croisé avec la confirmation ; puis BC confirmé édité ═══
etape('PF9.4-ACNC41-ecran', ['ACNC41'], async ({ page }) => {
  const r = page.request
  const x = await bcEnAttente(r, marque(), 'ACNC41E')
  apres.push(() => nettoyerBc(x))
  await page.goto('/ventes/bons-commande')
  const ligne = page.getByRole('row').filter({ hasText: x.reference })
  await expect(ligne, 'BC listé').toBeVisible({ timeout: 60_000 })
  await ligne.getByRole('button', { name: 'Éditer' }).click()
  const dlg = page.getByRole('dialog')
  await expect(dlg).toContainText(`Éditer — ${x.reference}`)
  await dlg.locator('#bc-note').fill('Livrer le matin')
  const { attentes } = await course({
    quoi: 'ACNC41 écran : « Mettre à jour » croisé avec « Confirmer »',
    verrou: `from apps.ventes.models import BonCommande\nBonCommande.objects.select_for_update().get(pk=${x.bc})`,
    gestes: [() => dlg.getByRole('button', { name: 'Mettre à jour' }).click()],
    n: 1,
    pendant: `from apps.ventes.models import BonCommande\nBonCommande.objects.filter(pk=${x.bc}).update(statut='confirme')`,
    valider: true,
  })
  expect(attentes[0], 'la mise à jour attendait sur son ÉCRITURE').toMatch(/^UPDATE /)
  await expect(dlg, 'dialogue refermé').toHaveCount(0, { timeout: 60_000 })
  expect(await etatBc(x.bc), 'en base : confirmé conservé, note de l\'écran écrite').toEqual(['confirme', 'Livrer le matin'])
  await page.reload()
  await expect(ligne, 'après rechargement : « Confirmé »').toContainText('Confirmé', { timeout: 60_000 })
  // Clause littérale : PUT d'un BC CONFIRMÉ depuis l'écran ⇒ seule la note change.
  await ligne.getByRole('button', { name: 'Éditer' }).click()
  await expect(page.getByRole('dialog').locator('#bc-note')).toHaveValue('Livrer le matin')
  await page.getByRole('dialog').locator('#bc-note').fill('Appeler avant')
  await page.getByRole('dialog').getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0, { timeout: 60_000 })
  expect(await etatBc(x.bc), 'BC confirmé édité : statut inchangé, note changée').toEqual(['confirme', 'Appeler avant'])
  await page.reload()
  await expect(ligne, 'après rechargement : toujours « Confirmé »').toContainText('Confirmé', { timeout: 60_000 })
})

// ═══ PF9.5 — ACNC25 (API) : PATCH {technicien} croisé avec « terminée » ; PATCH {note} croisé avec « Expédier » ═══
etape('PF9.5-ACNC25-api', ['ACNC25'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const tech = await compteRole(`acnc25te_${m}`, 'Technicien')
  const x = await py(`from apps.installations.models import Installation, Intervention, Livraison
from apps.stock.models import EmplacementStock
a = ${ADMIN}; co = a.company_id
inst = Installation.objects.create(company_id=co, reference='CHT-ACNC25-${m}')
iv = Intervention.objects.create(company_id=co, installation=inst, type_intervention='pose', created_by=a, technicien=a, statut=Intervention.Statut.SUR_SITE)
depot = EmplacementStock.objects.filter(company_id=co).order_by('-is_principal', 'pk').first() or EmplacementStock.objects.create(company_id=co, nom='Dépôt ACNC25 ${m}', is_principal=False, ordre=990)
liv = Livraison.objects.create(company_id=co, installation=inst, depot=depot, reference='LIV-ACNC25-${m}')
sortie(dict(inst=inst.pk, iv=iv.pk, liv=liv.pk, statut_liv=liv.statut))`)
  apres.push(() => py(`from apps.installations.models import Installation, Intervention, Livraison
Livraison.objects.filter(pk=${x.liv}).delete(); Intervention.objects.filter(pk=${x.iv}).delete(); Installation.objects.filter(pk=${x.inst}).delete()
sortie(True)`))
  const iv = await course({
    quoi: 'ACNC25 PATCH technicien croisé avec « terminée »',
    verrou: `from apps.installations.models import Intervention\nIntervention.objects.select_for_update().get(pk=${x.iv})`,
    gestes: [() => r.patch(`${API}/installations/interventions/${x.iv}/`, { ...T, data: { technicien: tech } }).then(lire)],
    n: 1,
    pendant: `from apps.installations.models import Intervention\nIntervention.objects.filter(pk=${x.iv}).update(statut='terminee')`,
    valider: true,
  })
  expect(iv.attentes[0], 'le PATCH attendait sur son ÉCRITURE').toMatch(/^UPDATE /)
  expect(iv.reponses[0].s, `PATCH 200 ${J(iv.reponses[0].b)}`).toBe(200)
  expect(await py(`from apps.installations.models import Intervention
i = Intervention.objects.get(pk=${x.iv}); sortie([i.statut, i.technicien_id])`), 'terminée conservée, technicien B écrit').toEqual(['terminee', tech])
  const liv = await course({
    quoi: 'ACNC25 PATCH note croisé avec « Expédier »',
    verrou: `from apps.installations.models import Livraison\nLivraison.objects.select_for_update().get(pk=${x.liv})`,
    gestes: [() => r.patch(`${API}/installations/livraisons/${x.liv}/`, { ...T, data: { note: 'Appeler avant' } }).then(lire)],
    n: 1,
    pendant: `from apps.installations.models import Livraison\nLivraison.objects.filter(pk=${x.liv}).update(statut='en_transit', stock_mouvemente=True)`,
    valider: true,
  })
  expect(liv.attentes[0], 'le PATCH attendait sur son ÉCRITURE').toMatch(/^UPDATE /)
  expect(liv.reponses[0].s, `PATCH 200 ${J(liv.reponses[0].b)}`).toBe(200)
  expect(await py(`from apps.installations.models import Livraison
l = Livraison.objects.get(pk=${x.liv}); sortie([l.statut, l.stock_mouvemente, l.note])`), 'en transit, stock mouvementé, note écrite').toEqual(['en_transit', true, 'Appeler avant'])
})

// ═══ PF9.3 — ACNC44 (API) : deux vidages simultanés du même lot `crm.lead.noter` = une note ═══
etape('PF9.3-ACNC44-api', ['ACNC44'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await py(`from apps.crm.models import Lead
a = ${ADMIN}
sortie(Lead.objects.create(company_id=a.company_id, nom='ACNC44 ${m}', telephone='${telephoneMobileUnique()}', owner=a).pk)`)
  apres.push(() => py(`from apps.crm.models import Lead
from apps.offlinesync.models import OfflineOperation
OfflineOperation.objects.filter(client_op_id__startswith='acnc44-${m}').delete(); Lead.all_objects.filter(pk=${lead}).delete()
sortie(True)`))
  const notes = (corps) => py(`from apps.crm.models import LeadActivity
sortie(LeadActivity.objects.filter(lead_id=${lead}, kind=LeadActivity.Kind.NOTE, body=${J(corps)}).count())`)
  const vider = (cle, corps) => () => r.post(`${API}/offlinesync/operations/batch/`, {
    ...T, data: { ops: [{ client_op_id: cle, op_type: 'crm.lead.noter', payload: { lead, body: corps } }] },
  }).then(lire)
  // (a) op NEUVE : les deux vidages bloqués ensemble à l'insertion du journal (table verrouillée par le collègue).
  const c1 = `Client rappelé A ${m}`
  const a = await course({
    quoi: 'ACNC44 deux vidages (op neuve)',
    verrou: `from django.db import connection
from apps.offlinesync.models import OfflineOperation
connection.cursor().execute('LOCK TABLE %s IN SHARE ROW EXCLUSIVE MODE' % OfflineOperation._meta.db_table)`,
    gestes: [vider(`acnc44-${m}-a`, c1), vider(`acnc44-${m}-a`, c1)],
  })
  expect(statuts(a.reponses), 'deux 200').toEqual([200, 200])
  expect(a.reponses.map((x) => x.b.results[0].status).sort(), 'appliquée une fois, rejouée une fois').toEqual(['applied', 'replayed'])
  expect(await notes(c1), 'une seule note').toBe(1)
  // (b) op déjà JOURNALISÉE « en attente » (vidage précédent interrompu) : deux vidages croisés sur la ligne de journal.
  const c2 = `Client rappelé B ${m}`
  const op = await py(`from apps.offlinesync.models import OfflineOperation
a = ${ADMIN}
o = OfflineOperation.objects.create(company_id=a.company_id, user=a, module='crm', op_type='crm.lead.noter', payload={'lead': ${lead}, 'body': ${J(c2)}}, client_op_id='acnc44-${m}-b', statut=OfflineOperation.Statut.EN_ATTENTE)
sortie(o.pk)`)
  const b = await course({
    quoi: 'ACNC44 deux vidages (op en attente)',
    verrou: `from apps.offlinesync.models import OfflineOperation\nOfflineOperation.objects.select_for_update().get(pk=${op})`,
    gestes: [vider(`acnc44-${m}-b`, c2), vider(`acnc44-${m}-b`, c2)],
  })
  expect(statuts(b.reponses), 'deux 200').toEqual([200, 200])
  console.log(`[ACNC44] op en attente : statuts ${J(b.reponses.map((x) => x.b.results[0].status))}`)
  expect(await notes(c2), 'une seule note (op en attente rejouée deux fois en même temps)').toBe(1)
  expect(await py(`from apps.offlinesync.models import OfflineOperation
sortie(OfflineOperation.objects.get(pk=${op}).statut)`), 'journal : appliquée').toBe('appliquee')
})

// ═══ PF9.3 — ACNC45 (API + écran, deux onglets) : deux « Importer » du même fichier de leads = aucun doublon ═══
const csvLeads = (m) => Buffer.from(`nom,email,telephone\nACNC45 A ${m},acnc45a-${m}@example.invalid,${telephoneMobileUnique()}\nACNC45 B ${m},acnc45b-${m}@example.invalid,${telephoneMobileUnique()}\n`)
const VERROU_LOT = `from apps.dataimport.services import _verrou_lot
from authentication.models import Company
with _verrou_lot(Company.objects.get(pk=${SOC}), 'leads'):
    pass`
const leadsImportes = (m) => py(`from apps.crm.models import Lead
sortie(Lead.all_objects.filter(nom__startswith='ACNC45 ', nom__endswith=' ${m}').count())`)
const nettoyerImport = (m) => py(`from apps.crm.models import Lead
Lead.all_objects.filter(nom__startswith='ACNC45 ', nom__endswith=' ${m}').delete()
sortie(True)`)
etape('PF9.3-ACNC45-api', ['ACNC45'], async ({ page }) => {
  const r = page.request
  const m = marque()
  apres.push(() => nettoyerImport(m))
  const fichier = csvLeads(m)
  const importer = () => r.post(`${API}/imports/commit/`, {
    ...T, multipart: { file: { name: `leads-${m}.csv`, mimeType: 'text/csv', buffer: fichier }, target: 'leads' },
  }).then(lire)
  const { reponses } = await course({ quoi: 'ACNC45 deux imports (API)', verrou: VERROU_LOT, gestes: [importer, importer] })
  expect(statuts(reponses), 'deux 200').toEqual([200, 200])
  expect(reponses.map((x) => x.b.created).sort(), 'créés : 2 puis 0').toEqual([0, 2])
  expect(reponses.map((x) => x.b.skipped.length).sort(), 'le second ignore les 2 lignes (doublons)').toEqual([0, 2])
  expect(await leadsImportes(m), 'en base : 2 leads, pas 4').toBe(2)
})
etape('PF9.4-ACNC45-ecran', ['ACNC45'], async ({ page, context, suivi }) => {
  const m = marque()
  apres.push(() => nettoyerImport(m))
  const fichier = csvLeads(m)
  const p2 = suivi.surveiller(await context.newPage())
  await p2.addInitScript(INIT)
  const preparer = async (p) => {
    await p.goto('/crm/leads')
    await p.getByRole('button', { name: "Plus d'actions", exact: true }).first().click({ timeout: 60_000 })
    await p.getByRole('menuitem', { name: 'Importer' }).click()
    await p.locator('input[type="file"][accept=".csv,.xlsx"]').setInputFiles({ name: `leads-${m}.csv`, mimeType: 'text/csv', buffer: fichier })
    const b = p.getByRole('button', { name: /^Importer 2 ligne\(s\)$/ })
    await expect(b, 'aperçu : 2 lignes importables').toBeEnabled({ timeout: 60_000 })
    return b
  }
  const b1 = await preparer(page)
  const b2 = await preparer(p2)
  await course({ quoi: 'ACNC45 écran deux onglets', verrou: VERROU_LOT, gestes: [() => b1.click(), () => b2.click()] })
  const bilan = async (p) => (await p.locator('.alert-info').filter({ hasText: 'créé(s)' }).first().innerText({ timeout: 60_000 })).replace(/\s+/g, ' ')
  const textes = [await bilan(page), await bilan(p2)].sort()
  console.log(`[ACNC45] bilans affichés : ${J(textes)}`)
  expect(textes[0], 'un onglet : 0 créé, 2 ignorés').toMatch(/^0 créé\(s\).* 2 ignoré\(s\)/)
  expect(textes[1], 'l\'autre : 2 créés').toMatch(/^2 créé\(s\).* 0 ignoré\(s\)/)
  expect(await leadsImportes(m), 'en base : 2 leads').toBe(2)
  await p2.goto(`/crm/leads?view=liste&q=${encodeURIComponent(`ACNC45 A ${m}`)}`)
  await expect(p2.locator('tr.lv-row').filter({ hasText: `ACNC45 A ${m}` }), 'après rechargement : le lead importé, une fois').toHaveCount(1, { timeout: 60_000 })
  await p2.close()
})

// ═══ PF9.3 — ACNC46 (API publique) : relance d'un import en cours → 400 ; deux relances d'un job bloqué = une ═══
etape('PF9.3-ACNC46-api', ['ACNC46'], async () => {
  const m = marque()
  const k = await py(`from datetime import timedelta
from apps.publicapi.models import ApiKey, BulkJob
from apps.publicapi.portees import SCOPE_WRITE_LEADS
from authentication.models import Company
co = Company.objects.get(pk=${SOC})
cle, brute = ApiKey.issue(company=co, label='ACNC46 ${m}', scopes=[SCOPE_WRITE_LEADS])
mk = lambda curseur: BulkJob.objects.create(company=co, api_key=cle, type=BulkJob.TYPE_IMPORT, entite='leads', params={}, statut=BulkJob.STATUT_EN_COURS, cursor=curseur, total=5)
actif, bloque = mk(2), mk(3)
BulkJob.objects.filter(pk=actif.pk).update(updated_at=timezone.now() - timedelta(minutes=1))
BulkJob.objects.filter(pk=bloque.pk).update(updated_at=timezone.now() - timedelta(minutes=11))
sortie(dict(cle=cle.pk, brute=brute, actif=actif.pk, bloque=bloque.pk))`)
  apres.push(() => py(`from apps.publicapi.models import ApiKey, BulkJob
BulkJob.objects.filter(api_key_id=${k.cle}).delete(); ApiKey.objects.filter(pk=${k.cle}).delete()
sortie(True)`))
  const ctx = await pwRequest.newContext({ baseURL: process.env.E2E_API_TARGET || 'http://127.0.0.1:8000', extraHTTPHeaders: { Authorization: `Api-Key ${k.brute}` } })
  try {
    const relancer = (id) => () => ctx.post(`/api/public/v1/jobs/${id}/relancer/`, T).then(lire)
    const job = (id) => py(`from apps.publicapi.models import BulkJob
j = BulkJob.objects.get(pk=${id}); sortie([j.statut, j.cursor])`)
    // Import qui progresse encore (1 min) : deux relances simultanées, toutes deux refusées, job intact.
    const actif = await Promise.all([relancer(k.actif)(), relancer(k.actif)()])
    expect(statuts(actif), 'job en cours récent : 400 aux deux').toEqual([400, 400])
    expect(J(actif[0].b), 'motif : encore en cours').toContain('encore en cours')
    expect(await job(k.actif), 'job refusé relu : en cours, curseur inchangé').toEqual(['en_cours', 2])
    // Job bloqué (> 10 min) : deux relances croisées, bloquées ensemble sur le job verrouillé → une seule passe.
    const { reponses } = await course({
      quoi: 'ACNC46 relances croisées d\'un job bloqué',
      verrou: `from apps.publicapi.models import BulkJob\nBulkJob.objects.select_for_update().get(pk=${k.bloque})`,
      gestes: [relancer(k.bloque), relancer(k.bloque)],
    })
    expect(statuts(reponses), 'une relance 200, la seconde 400').toEqual([200, 400])
    expect(reponses.find((x) => x.s === 200).b.statut, 'relancé : en file').toBe('en_file')
    expect(await job(k.bloque), 'job relu : en file, curseur inchangé (reprise à la ligne 4)').toEqual(['en_file', 3])
  } finally { await ctx.dispose() }
})

// ═══ PF9.3 — ACNC47 (webhook entrant signé) : même corps livré deux fois en même temps = une exécution de la règle ═══
etape('PF9.3-ACNC47-api', ['ACNC47'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const secret = `secret-acnc47-${m}`
  const x = await py(`from apps.automation.models import AutomationRule, IncomingWebhookTrigger, TriggerType, ActionType
co = ${SOC}
regle = AutomationRule.objects.create(company_id=co, nom='ACNC47 ${m}', trigger_type=TriggerType.WEBHOOK_INBOUND, trigger_config={}, action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'Webhook ACNC47'}, enabled=True)
t = IncomingWebhookTrigger.objects.create(company_id=co, rule=regle, hmac_secret=${J(secret)})
sortie(dict(regle=regle.pk, trigger=t.pk, token=t.token))`)
  apres.push(() => py(`from apps.automation.models import AutomationRule, AutomationRun, IncomingWebhookTrigger
from core.idempotency import ProcessedWebhookEvent
AutomationRun.objects.filter(rule_id=${x.regle}).delete(); IncomingWebhookTrigger.objects.filter(pk=${x.trigger}).delete()
AutomationRule.objects.filter(pk=${x.regle}).delete(); ProcessedWebhookEvent.objects.filter(source='automation_webhook:${x.trigger}').delete()
sortie(True)`))
  const runs = () => py(`from apps.automation.models import AutomationRun
sortie(AutomationRun.objects.filter(rule_id=${x.regle}).count())`)
  const poster = (corps) => () => r.post(`${API}/public/hooks/${x.token}/`, {
    ...T, data: corps, headers: { 'Content-Type': 'application/json', 'X-Signature': createHmac('sha256', secret).update(corps).digest('hex') },
  }).then(lire)
  const VERROU = `from django.db import connection
from core.idempotency import ProcessedWebhookEvent
connection.cursor().execute('LOCK TABLE %s IN SHARE ROW EXCLUSIVE MODE' % ProcessedWebhookEvent._meta.db_table)`
  for (const [nom, corps] of [['avec event_id', J({ event_id: `evt-${m}`, x: 1 })], ['sans event_id (empreinte du corps)', J({ x: m })]]) {
    const avant = await runs()
    const { reponses } = await course({ quoi: `ACNC47 double livraison ${nom}`, verrou: VERROU, gestes: [poster(corps), poster(corps)] })
    expect(statuts(reponses), `${nom} : 202 aux deux`).toEqual([202, 202])
    expect(reponses.map((a) => a.b.detail).sort(), `${nom} : reçu une fois, « Déjà reçu. » l'autre`).toEqual(['Déjà reçu.', 'Reçu.'])
    expect(await runs(), `${nom} : une seule exécution de la règle`).toBe(avant + 1)
    const tardif = await poster(corps)()
    expect([tardif.s, tardif.b.detail], `${nom} : redélivrance tardive`).toEqual([202, 'Déjà reçu.'])
    expect(await runs(), `${nom} : toujours une exécution`).toBe(avant + 1)
  }
  const temoin = await poster(J({ event_id: `evt2-${m}`, x: 1 }))()
  expect(temoin.s, 'témoin : un autre event_id').toBe(202)
  expect(await runs(), 'témoin : deux event_id distincts = une exécution de plus').toBe(3)
  expect(await py(`from core.idempotency import ProcessedWebhookEvent
sortie(ProcessedWebhookEvent.objects.filter(source='automation_webhook:${x.trigger}').count())`), 'trois événements enregistrés').toBe(3)
})

// ═══ PF9.3 — ACNC49 (approbations) : approuver et rejeter la même étape en même temps = une décision, état cohérent ═══
etape('PF9.3-ACNC49-api', ['ACNC49'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await py(`from authentication.models import Company
from core.models import WorkflowDefinition, WorkflowStepDefinition
from core import workflow
co = Company.objects.get(pk=${SOC})
wf = WorkflowDefinition.objects.create(company=co, code='acnc49-${m}', nom='ACNC49 ${m}')
for o, nom in ((1, 'Manager'), (2, 'Directeur')):
    WorkflowStepDefinition.objects.create(definition=wf, ordre=o, nom=nom, sla_heures=24)
inst = workflow.demarrer_workflow(wf, co, co)
sortie(dict(wf=wf.pk, inst=inst.pk, etape=workflow.etape_courante_de(inst).pk))`)
  apres.push(() => py(`from core.models import WorkflowDefinition, WorkflowInstance
WorkflowInstance.objects.filter(pk=${x.inst}).delete(); WorkflowDefinition.objects.filter(pk=${x.wf}).delete()
sortie(True)`))
  const decider = (decision) => () => r.post(`${API}/reporting/approbations-en-attente/decider/`, {
    ...T, data: { source: 'workflow', id: x.etape, decision, ...(decision === 'refuser' ? { motif: 'Non (ACNC49)' } : {}) },
  }).then(lire)
  const { reponses } = await course({
    quoi: 'ACNC49 approuver et rejeter croisés',
    verrou: `from core.models import WorkflowInstance\nWorkflowInstance.objects.select_for_update().get(pk=${x.inst})`,
    gestes: [decider('approuver'), decider('refuser')],
  })
  expect(statuts(reponses), 'une décision 200, l\'autre 400').toEqual([200, 400])
  expect(reponses.find((a) => a.s === 400).b.detail, 'refus : « Aucune étape en attente »').toMatch(/Aucune étape en attente/)
  const e = await py(`from core.models import WorkflowInstance
i = WorkflowInstance.objects.get(pk=${x.inst})
etapes = {s.ordre: [s.statut, s.decided_le is not None] for s in i.step_instances.all()}
sortie(dict(instance=i.statut, courante=i.etape_courante, e1=etapes[1], e2=etapes[2]))`)
  console.log(`[ACNC49] état relu : ${J(e)}`)
  const approuve = reponses[0].s === 200
  if (approuve) {
    expect(e, 'approbation gagnante : étape 1 approuvée, étape 2 active, instance en cours').toMatchObject({ instance: 'en_cours', courante: 2, e1: ['approuve', true], e2: ['en_attente', false] })
  } else {
    expect(e, 'rejet gagnant : étape 1 rejetée, instance terminée, étape 2 jamais décidée').toMatchObject({ instance: 'termine', e1: ['rejete', true], e2: ['en_attente', false] })
  }
})

// ═══ PF9.4 — ACNC52 (écran « Mouvements de stock ») : écriture expirée ⇒ « l'action a peut-être abouti » ; lecture expirée ⇒ ancien texte ═══
etape('PF9.4-ACNC52-ecran', ['ACNC52'], async ({ page, suivi }) => {
  const m = marque()
  const x = await py(`from decimal import Decimal as D
from apps.stock.models import Produit
p = Produit.objects.create(company_id=${SOC}, nom='Article ACNC52 ${m}', sku='ACNC52-${m}', prix_vente=D('10'), prix_achat=D('5'), quantite_stock=5)
sortie(dict(id=p.pk, nom=p.nom))`)
  apres.push(() => py(`from apps.stock.models import Produit, MouvementStock
MouvementStock.objects.filter(produit_id=${x.id}).delete(); Produit.objects.filter(pk=${x.id}).delete()
sortie(True)`))
  const MSG_ECRITURE = "La réponse n'est pas arrivée : l'action a peut-être abouti. Vérifiez avant de recommencer."
  const MSG_LECTURE = 'La connexion a expiré. Vérifiez votre connexion et réessayez.'
  suivi.attendre(/\/api\/django\/stock\/mouvements\/$/, 'reseau')
  await page.goto('/stock/mouvements')
  await page.getByRole('button', { name: 'Saisir mouvement' }).click({ timeout: 60_000 })
  const dlg = page.getByRole('dialog')
  await dlg.locator('#mv-produit').click()
  await page.getByRole('option', { name: new RegExp(`Article ACNC52 ${m}`) }).click()
  await dlg.locator('#mv-quantite').fill('2')
  await dlg.locator('#mv-reference').fill(`ACNC52-${m}`)
  // Le serveur APPLIQUE le mouvement, mais sa réponse n'arrive jamais au navigateur (délai de 20 s dépassé).
  let servi = null
  let liberer
  const porte = new Promise((res) => { liberer = res })
  await page.route((u) => u.pathname === `${API}/stock/mouvements/`, async (route) => {
    if (route.request().method() !== 'POST') { await route.fallback(); return }
    const rep = await route.fetch()
    servi = rep.status()
    await porte
    await route.abort('timedout').catch(() => undefined)
  })
  await dlg.getByRole('button', { name: 'Enregistrer le mouvement' }).click()
  await expect.poll(() => servi, { message: 'le serveur a appliqué le mouvement', timeout: 60_000 }).toBe(201)
  await expect(toast(page, MSG_ECRITURE), 'toast : « l\'action a peut-être abouti »').toBeVisible({ timeout: 45_000 })
  console.log(`[ACNC52] message du formulaire (hors clause) : ${J(await dlg.locator('[role="alert"]').allInnerTexts().catch(() => []))}`)
  await expect(toast(page, MSG_LECTURE), 'jamais « réessayez » sur une écriture').toHaveCount(0)
  liberer()
  expect(await py(`from apps.stock.models import MouvementStock, Produit
sortie([MouvementStock.objects.filter(produit_id=${x.id}, reference='ACNC52-${m}').count(), float(Produit.objects.get(pk=${x.id}).quantite_stock)])`),
  'le mouvement a bien abouti, une fois').toEqual([1, 7])
  // Lecture expirée : la liste des mouvements ne répond pas ⇒ l'ancien texte.
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  let liberer2
  const porte2 = new Promise((res) => { liberer2 = res })
  await page.route((u) => u.pathname === `${API}/stock/mouvements/`, async (route) => {
    if (route.request().method() !== 'GET') { await route.fallback(); return }
    await porte2
    await route.abort('timedout').catch(() => undefined)
  })
  await page.reload()
  await expect(toast(page, MSG_LECTURE), 'lecture expirée : « La connexion a expiré… »').toBeVisible({ timeout: 45_000 })
  await expect(toast(page, MSG_ECRITURE), 'jamais le texte d\'écriture sur une lecture').toHaveCount(0)
  liberer2()
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  // Persistance : rechargé sans entrave, le mouvement est listé une fois.
  await page.reload()
  await expect(page.locator('[aria-label="Mouvements de stock"]').getByRole('row').filter({ hasText: `ACNC52-${m}` }),
    'après rechargement : le mouvement, une ligne').toHaveCount(1, { timeout: 60_000 })
})

// ═══ PF9.4 — ACNC53 (Leads, kanban) : sortie de « Signé » appliquée, réponse perdue ⇒ la carte prend l'étape SERVIE ═══
etape('PF9.4-ACNC53-ecran', ['ACNC53'], async ({ page, suivi }) => {
  const m = marque()
  const nom = `ACNC53 ${m}`
  const lead = await py(`from apps.crm import stages
from apps.crm.models import Lead
a = ${ADMIN}
sortie(Lead.objects.create(company_id=a.company_id, nom=${J(nom)}, telephone='${telephoneMobileUnique()}', email='acnc53-${m}@example.invalid', owner=a, stage=stages.SIGNED).pk)`)
  apres.push(() => py(`from apps.crm.models import Lead
Lead.all_objects.filter(pk=${lead}).delete()
sortie(True)`))
  await page.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(nom)}`)
  const carte = page.locator(`[data-lead-id="${lead}"]`)
  const signe = page.locator('[aria-label^="Étape Signé"]').first()
  const contacte = page.locator('[aria-label^="Étape Contacté"]').first()
  await expect(signe.locator(`[data-lead-id="${lead}"]`), 'carte en « Signé »').toBeVisible({ timeout: 60_000 })
  // Le PATCH part, le serveur l'APPLIQUE, puis le réseau coupe : le navigateur ne reçoit aucune réponse.
  suivi.attendre(new RegExp(`/api/django/crm/leads/${lead}/$`), 'reseau')
  const servis = []
  await page.route((u) => u.pathname === `${API}/crm/leads/${lead}/`, async (route) => {
    if (route.request().method() !== 'PATCH') { await route.fallback(); return }
    const rep = await route.fetch()
    servis.push(rep.status())
    await route.abort('internetdisconnected')
  })
  const a = await carte.boundingBox()
  const b = await contacte.boundingBox()
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
  await page.mouse.down()
  await page.mouse.move(a.x + a.width / 2 + 15, a.y + a.height / 2 + 5, { steps: 4 })
  await page.mouse.move(b.x + b.width / 2, b.y + 60, { steps: 12 })
  await page.mouse.up()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Ramener' }).click()
  await expect.poll(() => servis, { message: 'le serveur a appliqué le changement d\'étape', timeout: 60_000 }).toEqual([200])
  await expect(contacte.locator(`[data-lead-id="${lead}"]`), 'sans rechargement : la carte est dans l\'étape SERVIE').toBeVisible({ timeout: 60_000 })
  await expect(signe.locator(`[data-lead-id="${lead}"]`), 'jamais revenue en « Signé »').toHaveCount(0)
  await expect(page.getByText("Le changement d'étape n'a pas pu être enregistré"), 'aucun message d\'échec').toHaveCount(0)
  expect(await py(`from apps.crm.models import Lead
from apps.crm import stages
sortie(Lead.objects.get(pk=${lead}).stage == stages.CONTACTED)`), 'en base : étape « Contacté »').toBe(true)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await page.reload()
  await expect(contacte.locator(`[data-lead-id="${lead}"]`), 'après rechargement : même étape').toBeVisible({ timeout: 60_000 })
})

// ═══ PF9.3 — ACNC55 (API) : deux « Rejouer » simultanés d'un payload sans téléphone ni clé = un lead, un devis en file ═══
const payloadSansTel = (m, tag) => py(`from apps.crm.models import WebsiteLeadPayload
p = WebsiteLeadPayload.objects.create(company_id=${SOC}, payload={'fullName': '${tag} ${m}', 'email': '${tag.toLowerCase()}-${m}@example.invalid', 'consent': True}, processed=False, error='ValueError: mapping cassé (essai ${tag})')
sortie(p.pk)`)
const etatPayload = (id, m, tag) => py(`from apps.crm.models import Lead, WebsiteLeadPayload
p = WebsiteLeadPayload.objects.get(pk=${id})
sortie(dict(lead=p.lead_id, processed=p.processed, leads=list(Lead.all_objects.filter(email='${tag.toLowerCase()}-${m}@example.invalid').values_list('pk', flat=True))))`)
const enFileDevisAuto = (lead) => py(`import json
import redis
from django.conf import settings
rc = redis.Redis.from_url(settings.CELERY_BROKER_URL)
n = 0
for k in rc.keys('*'):
    if rc.type(k) != b'list':
        continue
    for brut in rc.lrange(k, 0, -1):
        try:
            h = json.loads(brut).get('headers') or {}
        except Exception:
            continue
        if h.get('task') == 'ventes.devis_automatique_depuis_lead' and str(h.get('argsrepr', '')).startswith('[%d,' % ${lead}):
            n += 1
sortie(n)`)
const nettoyerPayload = (id, m, tag) => py(`from apps.crm.models import Lead, WebsiteLeadPayload
WebsiteLeadPayload.objects.filter(pk=${id}).delete(); Lead.all_objects.filter(email='${tag.toLowerCase()}-${m}@example.invalid').delete()
sortie(True)`)
etape('PF9.3-ACNC55-api', ['ACNC55'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const id = await payloadSansTel(m, 'ACNC55')
  apres.push(() => nettoyerPayload(id, m, 'ACNC55'))
  const rejouer = () => r.post(`${API}/crm/website-lead-payloads/${id}/replay/`, { ...T, data: {} }).then(lire)
  const { reponses } = await course({
    quoi: 'ACNC55 deux « Rejouer » simultanés',
    verrou: `from apps.crm.models import WebsiteLeadPayload\nWebsiteLeadPayload.objects.select_for_update().get(pk=${id})`,
    gestes: [rejouer, rejouer],
  })
  expect(statuts(reponses), 'deux 200').toEqual([200, 200])
  const e = await etatPayload(id, m, 'ACNC55')
  expect(e.leads.length, 'un seul lead créé').toBe(1)
  expect(e, 'payload rattaché au lead, traité').toMatchObject({ lead: e.leads[0], processed: true })
  expect(reponses.map((a) => a.b.detail).sort(), 'un « créé », l\'autre « Déjà rattaché »').toEqual([`Déjà rattaché au lead #${e.leads[0]} — aucun nouveau lead.`, 'Lead créé.'].sort())
  expect(await enFileDevisAuto(e.leads[0]), 'un seul devis automatique mis en file (courtier Redis relu)').toBe(1)
})

// ═══ PF9.4 — ACNC55 (écran /crm/payloads-site-web, deux sessions) : « Rejouer » dans les deux = un lead ═══
etape('PF9.4-ACNC55-ecran', ['ACNC55'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const id = await payloadSansTel(m, 'ACNC55E')
  apres.push(() => nettoyerPayload(id, m, 'ACNC55E'))
  // Seconde session : rôle livré « Directeur » (responsable). Sous « Commercial responsable » le run 2 a vu 6 × 403
  // d'arrière-plan sur `installations/interventions/ma-tournee/` (préchargement hors ligne du shell, hors ACNC55).
  const nomCr = `acnc55di_${m}`
  await compteRole(nomCr, 'Directeur')
  const p2 = await ecran(page, suivi, testInfo, nomCr)
  const ligne = (p) => p.getByRole('row').filter({ has: p.getByRole('cell', { name: String(id), exact: true }) })
  for (const p of [page, p2]) {
    await p.goto('/crm/payloads-site-web')
    await expect(ligne(p).getByRole('button', { name: 'Rejouer' }), 'payload listé, rejouable').toBeVisible({ timeout: 60_000 })
  }
  await course({
    quoi: 'ACNC55 écran deux sessions',
    verrou: `from apps.crm.models import WebsiteLeadPayload\nWebsiteLeadPayload.objects.select_for_update().get(pk=${id})`,
    gestes: [() => ligne(page).getByRole('button', { name: 'Rejouer' }).click(), () => ligne(p2).getByRole('button', { name: 'Rejouer' }).click()],
  })
  for (const p of [page, p2]) await expect(p.locator('.alert-info').first(), 'les deux réponses sont revenues').toBeVisible({ timeout: 60_000 })
  const e = await etatPayload(id, m, 'ACNC55E')
  expect(e.leads.length, 'un seul lead').toBe(1)
  const msg = async (p) => (await p.locator('.alert-info').first().innerText({ timeout: 60_000 })).trim()
  const textes = [await msg(page), await msg(p2)].sort()
  console.log(`[ACNC55] messages affichés : ${J(textes)}`)
  expect(textes, 'une session : « Lead créé. », l\'autre : « Déjà rattaché au lead #… »').toEqual([`Déjà rattaché au lead #${e.leads[0]} — aucun nouveau lead.`, 'Lead créé.'].sort())
  expect(await enFileDevisAuto(e.leads[0]), 'un seul devis automatique en file').toBe(1)
  await p2.reload()
  await expect(p2.getByRole('heading', { name: /Payloads leads site web/ })).toBeVisible({ timeout: 60_000 })
  await expect(ligne(p2), 'après rechargement : le payload rattaché a quitté la liste « à traiter »').toHaveCount(0, { timeout: 60_000 })
})

// ═══ PF9.3 — ACNC42 (service IA réel, /sql-agent/confirm) : deux confirmations simultanées du même jeton = un paiement ═══
etape('PF9.3-ACNC42-api', ['ACNC42'], async ({ page }) => {
  const s = sondeHote('C-ACNC-018')
  expect(s.ok, `sonde C-ACNC-018 exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde C-ACNC-018 : ${J(s.res.observe)}`).toBe(false)
  const IA = process.env.E2E_IA_URL
  const PY = process.env.E2E_IA_PYTHON
  expect(IA && PY, 'service IA lancé par le workflow (E2E_IA_URL, E2E_IA_PYTHON)').toBeTruthy()
  const r = page.request
  const m = marque()
  // Facture émise (devis accepté → facture complète) ; reste à payer > 1 000.
  const produit = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Article ACNC42 ${m}`, prix_vente: '5000.00', prix_achat: '3000.00' } }), 'produit')
  const client = await py(`from apps.crm.models import Client
sortie(Client.objects.create(company_id=${SOC}, nom='ACNC42 ${m}', prenom='Essai', email='acnc42-${m}@example.invalid').pk)`)
  const devis = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { client, taux_tva: '20.00', lignes: [{ produit: produit.id, designation: produit.nom, quantite: '1.00', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client ACNC42' } }), 'acceptation')
  const fc = await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  const facture = fc.facture_id
  apres.push(() => py(`from apps.ventes.models import Paiement, Facture, Devis
from apps.crm.models import Client
for f in (lambda: Paiement.objects.filter(facture_id=${facture}).delete(), lambda: Facture.objects.filter(devis_id=${devis.id}).delete(),
          lambda: Devis.objects.filter(pk=${devis.id}).delete(), lambda: Client.objects.filter(pk=${client}).delete()):
    try: f()
    except Exception as exc: print('nettoyage', exc)
sortie(True)`))
  const jeton = await py(`from authentication.serializers import CustomTokenObtainPairSerializer as S
sortie(str(S.get_token(${ADMIN}).access_token))`)
  // Proposition « Enregistrer un paiement » stashée par le VRAI code du service IA (catalogue relu chez Django).
  const inputs = { id: facture, montant: 1000, date_paiement: await py(`sortie(timezone.localdate().isoformat())`), mode: 'virement' }
  const script = `import sys, json
from app.services.action_tools import ActionContext, resolve_caller_permissions, _catalogue_by_key, _stash_proposal, _human_preview
ctx = ActionContext(company_id=int(sys.argv[1]), role='', permissions=[], token=sys.argv[2], is_superuser=False)
resolve_caller_permissions(ctx)
action = _catalogue_by_key(ctx).get('ventes.facture.enregistrer_paiement')
if action is None:
    print('@@E' + json.dumps('action absente du catalogue'))
    sys.exit(0)
inputs = json.loads(sys.argv[3])
print('@@T' + json.dumps(_stash_proposal(ctx, action, inputs, _human_preview(action, inputs))))`
  const societe = await py(`sortie(${SOC})`)
  const sp = spawnSync(PY, ['-c', script, String(societe), jeton, J(inputs)], { cwd: join(RACINE, 'backend', 'fastapi_ia'), encoding: 'utf8', env: process.env })
  const lt = (sp.stdout || '').split('\n').find((l) => l.startsWith('@@T'))
  expect(lt, `proposition stashée : ${(sp.stdout || '').slice(-300)} ${(sp.stderr || '').slice(-600)}`).toBeTruthy()
  const token = JSON.parse(lt.slice(3))
  expect(token, 'jeton de confirmation').toBeTruthy()
  const ia = await pwRequest.newContext({ baseURL: IA, extraHTTPHeaders: { Authorization: `Bearer ${jeton}` } })
  try {
    const confirmer = () => ia.post('/sql-agent/confirm', { ...T, data: { token } }).then(lire)
    const reps = await Promise.all([confirmer(), confirmer()])
    console.log(`[ACNC42] deux confirmations simultanées : ${J(reps)}`)
    expect(statuts(reps), 'deux réponses 200').toEqual([200, 200])
    expect(reps.map((a) => a.b.ok).sort(), 'une exécutée, l\'autre refusée').toEqual([false, true])
    expect(reps.find((a) => !a.b.ok).b.detail, 'refus : proposition introuvable (jeton consommé)').toMatch(/Proposition introuvable/)
    const tardive = await confirmer()
    expect([tardive.b.ok, tardive.b.detail], 'troisième confirmation tardive : refusée').toEqual([false, expect.stringMatching(/Proposition introuvable/)])
  } finally { await ia.dispose() }
  const p = await py(`from apps.ventes.models import Paiement
ps = list(Paiement.objects.filter(facture_id=${facture}))
sortie(dict(n=len(ps), montants=[float(x.montant) for x in ps], cles=[getattr(x, 'idempotency_key', None) for x in ps]))`)
  expect(p.n, 'un seul paiement en base').toBe(1)
  expect(p.montants, 'montant du paiement').toEqual([1000])
  const empreinte = createHash('sha256').update(token).digest('hex')
  if (p.cles[0] !== undefined && p.cles[0] !== null) expect(p.cles[0], 'clé d\'idempotence = empreinte SHA-256 du jeton (jamais le jeton)').toBe(empreinte)
  console.log(`[ACNC42] clé d'idempotence relue sur le paiement : ${J(p.cles)} ; empreinte attendue ${empreinte}`)
  expect(await py(`import os, redis
rc = redis.Redis(host=os.environ.get('REDIS_HOST', 'redis'), port=int(os.environ.get('REDIS_PORT', '6379')), db=2)
sortie(rc.exists('agent_proposal:${token}'))`), 'Redis relu : la proposition est consommée').toBe(0)
})
