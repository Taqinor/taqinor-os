// aerr12 : preuves en direct ÉCRAN du groupe AERR, vague d'acceptation 8 (runner GitHub, 17/11/2026) des correctifs de la
// vague 7 (AERR112, AERR176, AERR177, AERR178, AERR179) et de ce qu'ils débloquent (AERR69, AERR132). AERR114 « Suppr sous la
// boîte » est dans `aerr12b.spec.js` (jouée SEULE : son FAIL éventuel ne couvre rien et ne doit pas faire tomber cet enregistrement).
// Chaque étape joue le geste À L'ÉCRAN sous un compte d'un rôle LIVRÉ (relu par son nom dans la société démo, connexion par
// /token/), PROVOQUE le refus ou la panne (route Playwright déclarée AVANT par `suivi.attendre`), AFFIRME ce que la clause
// nomme, relit la base (API / shell Django) et recharge. Aucune attente à durée fixe : conditions seulement.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique, STAGE_LABELS } from '../helpers.js'

const etape = groupe('AERR', ['AERR69', 'AERR112', 'AERR132', 'AERR176', 'AERR177', 'AERR178', 'AERR179'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const ouverts = []
const apres = []
test.afterEach(async () => {
  for (const c of ouverts.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const pad = (n) => String(n).padStart(2, '0')
const isoJour = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte })
/** Deux images peintes : un effet synchrone (état React, requête déjà émise) est rendu / parti. */
const peindre = (p) => p.evaluate(() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(ok)))))

/** Sonde HÔTE `docs/audits/sondes/AERR/<c>.py` rejouée : `repro` DOIT être false (code réparé). */
function sondeRepro(constat) {
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AERR', `${constat}.py`)
  for (const exe of [process.env.E2E_PYTHON, 'python3', 'python'].filter(Boolean)) {
    const r = spawnSync(exe, ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
    const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
    if (ligne) return JSON.parse(ligne.slice(3))
  }
  throw new Error(`sonde ${constat} non exécutée`)
}

/** Compte d'essai du rôle LIVRÉ `nomRole` de la société démo ; renvoie son id. */
const compteRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
sortie(u.id)`)

/** Écran sous le compte `nom` : contexte neuf (accueil et visites vus, SW bloqué), observé ; la page demo_admin est
 *  refermée. `api` = requêtes de CE compte (même jarre de cookies). */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
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
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return { p: suivi.surveiller(await ctx.newPage()), api: ctx.request, ctx }
}

/** Route tenue : chaque requête qui passe attend `lacher()`, puis `issue(route)` (continue par défaut). */
function porte() {
  let lacher
  let signaler
  const ouverte = new Promise((r) => { lacher = r })
  const arrivee = new Promise((r) => { signaler = r })
  return {
    arrivee, lacher: () => lacher(),
    gestion: (issue = (route) => route.continue()) => async (route) => { signaler(); await ouverte; await issue(route) },
  }
}
/** Compteur de requêtes (méthode(s) + chemin) observées par la page. */
function compteur(p, methodes, cheminOk) {
  const c = { n: 0, corps: [], urls: [] }
  p.on('request', (r) => {
    if (!methodes.includes(r.method())) return
    const u = new URL(r.url())
    if (!cheminOk(u.pathname, u)) return
    c.n += 1
    c.urls.push(`${r.method()} ${u.pathname}${u.search}`)
    c.corps.push(r.postData() || '')
  })
  return c
}

/** Leads de la société démo, propriétaire `owner` ; `liste` = champs du modèle. Renvoie leurs pk. */
const creerLeads = (owner, liste) => py(`from apps.crm.models import Lead
out = []
for d in json.loads(${J(J(liste))}):
    out.append(Lead.objects.create(company_id=${SOC}, owner_id=${owner}, **d).pk)
sortie(out)`)
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
try:
    from apps.ventes.models import Devis
    Devis.all_objects.filter(lead_id__in=${J(pks)}).delete() if hasattr(Devis, 'all_objects') else Devis.objects.filter(lead_id__in=${J(pks)}).delete()
except Exception as exc:
    print('devis', exc)
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
const etapeLead = (lead) => py(`from apps.crm.models import Lead
sortie(Lead.objects.get(pk=${lead}).stage)`)

// ═══ Palette ⌘K : « Changer le stage du lead sélectionné » (AERR69, AERR178, AERR179) ═══
async function lancerChangerStage(p) {
  await p.keyboard.press('Control+k')
  const champ = p.getByRole('textbox', { name: 'Recherche rapide' })
  await expect(champ, 'palette ouverte').toBeVisible({ timeout: 30_000 })
  await champ.fill('Changer le stage')
  await p.getByText('Changer le stage du lead sélectionné').first().click()
}
const patchsDe = (p, id) => compteur(p, ['PATCH'], (ch) => ch === `${API}/crm/leads/${id}/`)
async function ouvrirFiche(p, id, nomLead) {
  await p.goto(`/crm/leads?lead=${id}`)
  await expect(p.getByText(nomLead).first(), `fiche de ${nomLead} affichée`).toBeVisible({ timeout: 60_000 })
}

etape('PF12.178-AERR178', ['AERR178'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr178_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [A] = await creerLeads(cr, [{ nom: `Karim B. ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'CONTACTED' }])
  apres.push(() => supprimerLeads([A]))
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const pa = patchsDe(p, A)
  await ouvrirFiche(p, A, `Karim B. ${m}`)
  await lancerChangerStage(p)
  const t = toast(p, `Karim B. ${m} → ${STAGE_LABELS.QUOTE_SENT}`).first()
  await expect(t, 'toast nommé « <nom> → Devis envoyé »').toBeVisible({ timeout: 30_000 })
  await expect.poll(() => pa.n, { timeout: 15_000 }).toBe(1)
  expect(JSON.parse(pa.corps[0]), 'premier PATCH : l\'avancée').toEqual({ stage: 'QUOTE_SENT' })
  expect(await etapeLead(A), 'base : avancé en QUOTE_SENT').toBe('QUOTE_SENT')
  const retour = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/crm/leads/${A}/`) && r.request().postData() !== pa.corps[0], T)
  await t.getByRole('button', { name: 'Annuler' }).click({ timeout: 15_000 })
  const rep = await retour
  expect(JSON.parse(rep.request().postData()), 'second PATCH = étape d\'origine + undo:true, exactement').toEqual({ stage: 'CONTACTED', undo: true })
  expect(rep.status(), 'accepté par le serveur (aucun 409 « On ne recule pas une étape »)').toBeLessThan(300)
  expect(pa.n, 'deux PATCH en tout').toBe(2)
  await expect.poll(() => etapeLead(A), { timeout: 30_000, message: 'base : retour en CONTACTED' }).toBe('CONTACTED')
  const relu = await lireJson(await api.get(`${API}/crm/leads/${A}/`, T), 'lead relu')
  expect(relu.stage, 'persistance : le lead relu est en CONTACTED').toBe('CONTACTED')
  // Sonde C-AERR-038 (détecteur de l'écriture sans garde) : réparée ⇒ repro false.
  expect(sondeRepro('C-AERR-038').repro, 'sonde C-AERR-038 rejouée ⇒ repro false').toBe(false)
})

etape('PF12.179-AERR179', ['AERR179'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr179_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [A] = await creerLeads(cr, [{ nom: `Modale ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'CONTACTED' }])
  apres.push(() => supprimerLeads([A]))
  const { p } = await ecran(page, suivi, testInfo, nom)
  const pa = patchsDe(p, A)
  await ouvrirFiche(p, A, `Modale ${m}`)
  const modale = p.getByRole('dialog').filter({ hasText: `Modale ${m}` })
  await expect(modale, 'la fiche lead est ouverte EN MODALE (?lead=<id>)').toBeVisible({ timeout: 30_000 })
  await lancerChangerStage(p)
  const t = toast(p, `Modale ${m} → ${STAGE_LABELS.QUOTE_SENT}`).first()
  await expect(t, 'toast à action « Annuler » posé sous la modale').toBeVisible({ timeout: 30_000 })
  const annuler = t.getByRole('button', { name: 'Annuler' })
  await expect(annuler).toBeVisible()
  expect(await annuler.evaluate((el) => getComputedStyle(el).pointerEvents), 'le bouton du toast reçoit les événements souris').not.toBe('none')
  await expect.poll(() => pa.n, { timeout: 15_000 }).toBe(1)
  const retour = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/crm/leads/${A}/`) && r.request().postData() !== pa.corps[0], T)
  // Clic RÉEL (aucun `force`, aucun `dispatchEvent`) : Playwright vérifie que le bouton reçoit le clic au point visé.
  await annuler.click({ timeout: 15_000 })
  const rep = await retour
  expect(JSON.parse(rep.request().postData()), 'l\'action du toast est appelée : retour à l\'étape d\'origine').toMatchObject({ stage: 'CONTACTED' })
  expect(rep.status(), 'retour accepté').toBeLessThan(300)
  await peindre(p)
  expect(pa.n, 'l\'action n\'est appelée qu\'UNE fois (avancée + un seul retour)').toBe(2)
  await expect(modale, 'la modale reste ouverte').toBeVisible()
  await expect.poll(() => etapeLead(A), { timeout: 30_000, message: 'base : retour en CONTACTED' }).toBe('CONTACTED')
})

etape('PF12.69-AERR69', ['AERR69'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr69_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [A, B, C] = await creerLeads(cr, [
    { nom: `Karim B. ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'CONTACTED' },
    { nom: `Relance ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'FOLLOW_UP' },
    { nom: `Panne ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'CONTACTED' },
  ])
  apres.push(() => supprimerLeads([A, B, C]))
  const { p, api } = await ecran(page, suivi, testInfo, nom)

  // (1) Lead CONTACTED : un PATCH {stage: QUOTE_SENT}, toast « <nom> → Devis envoyé » + « Annuler » qui le remet en CONTACTED.
  const pa = patchsDe(p, A)
  await ouvrirFiche(p, A, `Karim B. ${m}`)
  await lancerChangerStage(p)
  const t = toast(p, `Karim B. ${m} → ${STAGE_LABELS.QUOTE_SENT}`).first()
  await expect(t, 'toast nommé « <nom du lead> → Devis envoyé »').toBeVisible({ timeout: 30_000 })
  await expect(t.getByRole('button', { name: 'Annuler' }), 'toast avec « Annuler »').toBeVisible()
  await expect.poll(() => pa.n, { timeout: 15_000 }).toBe(1)
  expect(JSON.parse(pa.corps[0]), 'PATCH de l\'avancée').toEqual({ stage: 'QUOTE_SENT' })
  expect(await etapeLead(A), 'base : avancé en QUOTE_SENT').toBe('QUOTE_SENT')
  const retour = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/crm/leads/${A}/`) && r.request().postData() !== pa.corps[0], T)
  await t.getByRole('button', { name: 'Annuler' }).click({ timeout: 15_000 })
  const rep = await retour
  expect(JSON.parse(rep.request().postData()), '« Annuler » PATCHe l\'étape d\'origine').toMatchObject({ stage: 'CONTACTED' })
  expect(rep.status(), '« Annuler » accepté par le serveur (aucun 409)').toBeLessThan(300)
  await expect.poll(() => etapeLead(A), { timeout: 30_000, message: 'base : retour en CONTACTED' }).toBe('CONTACTED')
  const relu = await lireJson(await api.get(`${API}/crm/leads/${A}/`, T), 'lead relu')
  expect(relu.stage, 'persistance : le lead relu est en CONTACTED').toBe('CONTACTED')

  // (2) Lead en Relance : une boîte nommée AVANT tout passage en « Signé » ; « Annuler » ⇒ aucun PATCH.
  const pb = patchsDe(p, B)
  await ouvrirFiche(p, B, `Relance ${m}`)
  await lancerChangerStage(p)
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'boîte nommée avant « Signé »').toBeVisible({ timeout: 30_000 })
  await expect(boite).toContainText(`Passer « Relance ${m} » en « ${STAGE_LABELS.SIGNED} » ?`)
  expect(pb.n, 'la boîte précède tout PATCH').toBe(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  expect(await etapeLead(B), 'base : le lead reste en FOLLOW_UP').toBe('FOLLOW_UP')
  await peindre(p)
  expect(pb.n, '« Annuler » : aucun PATCH').toBe(0)

  // (3) Échec serveur : UN SEUL toast (celui de l'intercepteur global).
  suivi.attendre(new RegExp(`/api/django/crm/leads/${C}/$`), 500)
  await p.route((u) => u.pathname === `${API}/crm/leads/${C}/`, (route) => (route.request().method() === 'PATCH'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: J({ detail: 'panne injectée AERR69' }) })
    : route.fallback()))
  const pc = patchsDe(p, C)
  await ouvrirFiche(p, C, `Panne ${m}`)
  await lancerChangerStage(p)
  await expect.poll(() => pc.n, { timeout: 30_000 }).toBeGreaterThanOrEqual(1)
  await expect(p.locator('[data-sonner-toast]').first(), 'l\'échec est dit').toBeVisible({ timeout: 15_000 })
  await expect(p.locator('[data-sonner-toast]'), 'un seul message pour un échec').toHaveCount(1)
  await peindre(p)
  expect(await p.locator('[data-sonner-toast]').count(), 'toujours un seul toast (aucun toast local qui double celui de l\'intercepteur)').toBe(1)
  expect(await etapeLead(C), 'base : rien d\'écrit sur échec').toBe('CONTACTED')

  // Sonde C-AERR-038 rejouée ⇒ repro false.
  expect(sondeRepro('C-AERR-038').repro, 'sonde C-AERR-038 rejouée ⇒ repro false').toBe(false)
})

// ═══ AERR177 — « Produit mis à jour. » à l'enregistrement d'une fiche en édition ═══
const produitEdition = (prefixe, m, stock) => py(`from apps.stock.models import Produit
p = Produit.objects.create(company_id=${SOC}, nom='${prefixe} ${m}', prix_vente=12)
Produit.objects.filter(pk=p.pk).update(quantite_stock=${stock})
sortie(p.pk)`)
const effacerProduit = (prod) => () => py(`from apps.stock.models import Produit
try: Produit.objects.filter(pk=${prod}).delete()
except Exception as exc: print('nettoyage produit', exc)`)
const lirePrixStock = (prod) => py(`from apps.stock.models import Produit
p = Produit.objects.get(pk=${prod}); sortie([str(p.prix_vente), p.quantite_stock])`)
async function ouvrirEdition(p, motif) {
  await p.goto('/stock')
  await p.getByPlaceholder('Chercher partout…').fill(motif, { timeout: 60_000 })
  const ligne = p.getByRole('row').filter({ hasText: motif })
  await expect(ligne, 'la fiche est listée').toBeVisible({ timeout: 60_000 })
  await ligne.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await p.getByRole('menuitem', { name: 'Éditer' }).click()
  const form = p.getByRole('dialog').filter({ has: p.locator('#pf-vente') })
  await expect(form, 'fiche ouverte en édition').toBeVisible({ timeout: 30_000 })
  return { form, ligne }
}

etape('PF12.177-AERR177', ['AERR177'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr177_${m}`
  await compteRole(nom, 'Directeur')
  const prod = await produitEdition('Câble AERR177', m, 5)
  apres.push(effacerProduit(prod))
  expect(await lirePrixStock(prod), 'Given : prix 12, stock 5').toEqual(['12.00', 5])
  const { p } = await ecran(page, suivi, testInfo, nom)
  const URL_PRODUIT = new RegExp(`/api/django/stock/produits/${prod}/$`)
  const sur_URL_PRODUIT = (u) => URL_PRODUIT.test(u.pathname)
  // Échec d'abord : le serveur refuse (400) ⇒ la fiche reste ouverte et AUCUN toast de succès.
  suivi.attendre(URL_PRODUIT, 400)
  await p.route(sur_URL_PRODUIT, (route) => (route.request().method() === 'PATCH'
    ? route.fulfill({ status: 400, contentType: 'application/json', body: J({ detail: 'Refus injecté (AERR177).' }) })
    : route.fallback()))
  const { form } = await ouvrirEdition(p, `AERR177 ${m}`)
  await form.locator('#pf-vente').fill('13')
  const [refus] = await Promise.all([
    p.waitForResponse((r) => URL_PRODUIT.test(new URL(r.url()).pathname) && r.request().method() === 'PATCH', T),
    form.getByRole('button', { name: 'Mettre à jour' }).click(),
  ])
  expect(refus.status(), 'refus injecté').toBe(400)
  await expect(form, 'refus : la fiche reste ouverte').toBeVisible()
  await peindre(p)
  await expect(toast(p, 'Produit mis à jour.'), 'refus : aucun toast de succès').toHaveCount(0)
  expect(await lirePrixStock(prod), 'refus : rien d\'écrit').toEqual(['12.00', 5])
  // Succès : la route d'échec est retirée.
  await p.unroute(sur_URL_PRODUIT)
  await form.locator('#pf-vente').fill('13')
  const [ok] = await Promise.all([
    p.waitForResponse((r) => URL_PRODUIT.test(new URL(r.url()).pathname) && r.request().method() === 'PATCH', T),
    form.getByRole('button', { name: 'Mettre à jour' }).click(),
  ])
  expect(ok.status(), 'enregistrement accepté').toBeLessThan(300)
  await expect(toast(p, 'Produit mis à jour.').first(), 'toast de succès « Produit mis à jour. »').toBeVisible({ timeout: 30_000 })
  await expect(form, 'la fiche se ferme').toBeHidden({ timeout: 30_000 })
  expect(await lirePrixStock(prod), 'persistance : prix 13, stock 5 inchangé').toEqual(['13.00', 5])
})

// ═══ AERR132 — fiche produit à stock négatif : changer le prix s'enregistre, rien sous « Quantité en stock », toast de succès ═══
etape('PF12.132-AERR132', ['AERR132'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr132_${m}`
  await compteRole(nom, 'Directeur')
  const prod = await produitEdition('Câble 6 mm² AERR132', m, -3)
  apres.push(effacerProduit(prod))
  expect(await lirePrixStock(prod), 'Given : prix 12, stock -3').toEqual(['12.00', -3])
  const { p } = await ecran(page, suivi, testInfo, nom)
  const envois = compteur(p, ['PATCH', 'PUT'], (ch) => ch === `${API}/stock/produits/${prod}/`)
  const { form } = await ouvrirEdition(p, `AERR132 ${m}`)
  await expect(form.locator('#pf-qte'), 'quantité en stock grisée à -3').toBeDisabled()
  await expect(form.locator('#pf-qte')).toHaveValue('-3')
  await form.locator('#pf-vente').fill('13')
  await form.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(toast(p, 'Produit mis à jour.').first(), 'toast de succès à l\'enregistrement').toBeVisible({ timeout: 30_000 })
  await expect(form, 'la fiche se ferme (enregistrée)').toBeHidden({ timeout: 30_000 })
  await expect.poll(() => envois.n, { timeout: 15_000, message: 'updateProduit appelé' }).toBe(1)
  const corps = JSON.parse(envois.corps[0])
  expect(corps.prix_vente, 'le prix de vente part à 13').toMatch(/^13(\.0+)?$/)
  expect(Object.keys(corps), 'sans quantite_stock').not.toContain('quantite_stock')
  expect(await lirePrixStock(prod), 'persistance : prix 13, stock -3 inchangé').toEqual(['13.00', -3])
  await p.reload()
  await p.getByPlaceholder('Chercher partout…').fill(`AERR132 ${m}`, { timeout: 60_000 })
  const ligneRelue = p.getByRole('row').filter({ hasText: `AERR132 ${m}` })
  await expect(ligneRelue, 'après rechargement : la fiche est listée').toBeVisible({ timeout: 60_000 })
  await expect(ligneRelue, 'après rechargement : prix de vente 13 sur la ligne').toContainText(/13[,.]00/)
  await expect(ligneRelue, 'après rechargement : stock -3 sur la ligne').toContainText(/-\s?3/)
  // La fiche rouverte : aucun message sous « Quantité en stock ».
  await ligneRelue.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await p.getByRole('menuitem', { name: 'Éditer' }).click()
  const rouverte = p.getByRole('dialog').filter({ has: p.locator('#pf-vente') })
  await expect(rouverte.locator('#pf-vente'), 'fiche relue : prix 13').toHaveValue(/^13(\.0+)?$/, { timeout: 30_000 })
  await expect(rouverte.locator('#pf-qte'), 'fiche relue : stock -3').toHaveValue('-3')
  await expect(rouverte.getByText('Saisissez un nombre entier'), 'aucun message sous « Quantité en stock »').toHaveCount(0)
  // Sonde C-AERR-VER1-140 (vraie fonction JS sous node) rejouée ⇒ repro false.
  expect(sondeRepro('C-AERR-VER1-140').repro, 'sonde C-AERR-VER1-140 rejouée ⇒ repro false').toBe(false)
})

// ═══ AERR176 — un 400 {notes} marque le champ Notes du rendez-vous, pas la date ═══
etape('PF12.176-AERR176', ['AERR176'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr176_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR176 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const nbRdv = () => py(`from apps.crm.models import Appointment
sortie(Appointment.objects.filter(lead_id=${lead}).count())`)
  const { p } = await ecran(page, suivi, testInfo, nom)
  const APPT = /\/api\/django\/crm\/appointments\/$/
  const corpsRefus = { courant: { notes: ['Texte trop long.'] } }
  suivi.attendre(APPT, 400)
  await p.route(APPT, (route) => (route.request().method() === 'POST'
    ? route.fulfill({ status: 400, contentType: 'application/json', body: J(corpsRefus.courant) })
    : route.fallback()))
  await p.goto(`/crm/leads/${lead}`)
  await p.getByRole('navigation', { name: 'Sections du lead' }).getByRole('button', { name: /Visite technique/ }).click({ timeout: 60_000 })
  await p.locator('summary').filter({ hasText: 'Autre rendez-vous' }).click()
  await p.getByRole('button', { name: '+ Planifier une visite' }).first().click({ timeout: 60_000 })
  const futur = new Date(); futur.setDate(futur.getDate() + 10)
  const quand = `${isoJour(futur)}T10:00`
  const date = p.locator('#appt-scheduled-at')
  const notes = p.locator('#appt-notes')
  await date.fill(quand)
  await notes.fill('Visite AERR176')
  // (a) 400 {notes}
  await p.getByRole('button', { name: 'Confirmer', exact: true }).click()
  const erreur = p.locator('#appt-error')
  await expect(erreur, 'message nommé « Notes : Texte trop long. »').toHaveText('Notes : Texte trop long.', { timeout: 20_000 })
  await expect(notes, '#appt-notes en aria-invalid').toHaveAttribute('aria-invalid', 'true')
  await expect(notes, '#appt-notes relié au message').toHaveAttribute('aria-describedby', 'appt-error')
  await expect(date, '#appt-scheduled-at n\'est pas invalide').not.toHaveAttribute('aria-invalid', 'true')
  await expect(date, '#appt-scheduled-at sans lien vers le message').not.toHaveAttribute('aria-describedby', 'appt-error')
  await expect(notes, 'la saisie des notes est gardée').toHaveValue('Visite AERR176')
  await expect(date, 'la saisie de la date est gardée').toHaveValue(quand)
  expect(await nbRdv(), 'base : aucun RDV créé sur refus').toBe(0)
  // (b) 400 {scheduled_at} : la date seule est marquée.
  corpsRefus.courant = { scheduled_at: ['Date invalide (AERR176).'] }
  await p.getByRole('button', { name: 'Confirmer', exact: true }).click()
  await expect(erreur, 'message de la date').toHaveText('Date invalide (AERR176).', { timeout: 20_000 })
  await expect(date, '#appt-scheduled-at en aria-invalid').toHaveAttribute('aria-invalid', 'true')
  await expect(date, '#appt-scheduled-at relié au message').toHaveAttribute('aria-describedby', 'appt-error')
  await expect(notes, '#appt-notes n\'est plus invalide').not.toHaveAttribute('aria-invalid', 'true')
  expect(await nbRdv(), 'base : aucun RDV créé sur refus').toBe(0)
})

// ═══ AERR112 — « introuvable » seulement sur un 404 ; la dernière visite demandée l'emporte ═══
etape('PF12.112-AERR112-lead', ['AERR112'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr112l_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR112L ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const { p } = await ecran(page, suivi, testInfo, nom)
  const FICHE = new RegExp(`/api/django/crm/leads/${lead}/$`)
  const sur_FICHE = (u) => FICHE.test(u.pathname)
  // 500 sur la lecture de la fiche pleine page : « Lecture impossible » + Réessayer, jamais « introuvable ».
  suivi.attendre(FICHE, 500)
  await p.route(sur_FICHE, (route) => (route.request().method() === 'GET'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: J({ detail: 'panne injectée AERR112' }) })
    : route.fallback()))
  await p.goto(`/crm/leads/${lead}`)
  await expect(p.getByText('Lecture impossible').first(), '500 : « Lecture impossible »').toBeVisible({ timeout: 60_000 })
  await expect(p.getByRole('button', { name: 'Réessayer' }), '500 : bouton Réessayer').toBeVisible()
  await expect(p.getByText('Lead introuvable'), '500 : jamais « Lead introuvable »').toHaveCount(0)
  // Réessayer une fois la panne levée : la fiche s'affiche.
  await p.unroute(sur_FICHE)
  await p.getByRole('button', { name: 'Réessayer' }).click()
  await expect(p.getByText(`AERR112L ${m}`).first(), 'Réessayer : la fiche s\'affiche').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('Lecture impossible'), 'Réessayer : l\'avis disparaît').toHaveCount(0)
  // 404 (vrai : lead inexistant) : « Lead introuvable ».
  suivi.attendre(/\/api\/django\/crm\/leads\/999999999\/$/, 404)
  await p.goto('/crm/leads/999999999')
  await expect(p.getByText('Lead introuvable').first(), '404 : « Lead introuvable »').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('Lecture impossible'), '404 : pas « Lecture impossible »').toHaveCount(0)
})

etape('PF12.112-AERR112-visite', ['AERR112'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr112v_${m}`
  await compteRole(nom, 'Administrateur')
  const r = page.request
  const mk = async (suffixe) => {
    const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AERR112${suffixe} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${suffixe}${m}@example.invalid`, type_installation: 'residentiel', facture_hiver: '900' } }), 'lead')
    const visite = await lireJson(await r.post(`${API}/visites/visites/`, { ...T, data: { lead: lead.id } }), 'visite')
    await py(`from apps.visites.models import VisiteTerrain
VisiteTerrain.objects.filter(pk=${visite.id}).update(statut='terminee')
sortie(1)`)
    return { lead: lead.id, visite: visite.id, nom: `AERR112${suffixe} ${m}` }
  }
  const A = await mk('A')
  const B = await mk('B')
  apres.push(async () => {
    await py(`from apps.visites.models import VisiteTerrain
VisiteTerrain.objects.filter(pk__in=[${A.visite}, ${B.visite}]).delete()
sortie(1)`)
    await supprimerLeads([A.lead, B.lead])
  })
  const { p } = await ecran(page, suivi, testInfo, nom)
  const URL_A = new RegExp(`/api/django/visites/visites/${A.visite}/$`)
  const sur_URL_A = (u) => URL_A.test(u.pathname)
  const URL_B = new RegExp(`/api/django/visites/visites/${B.visite}/$`)
  // (1) A (réponse lente) puis B : seule B s'affiche, même quand la réponse de A arrive après.
  const lenteA = porte()
  await p.route(sur_URL_A, (route) => (route.request().method() === 'GET' ? lenteA.gestion()(route) : route.fallback()))
  await p.goto('/visites/revue')
  const carteA = p.getByText(A.nom).first()
  const carteB = p.getByText(B.nom).first()
  await expect(carteA, 'la visite A est listée à revoir').toBeVisible({ timeout: 90_000 })
  await expect(carteB, 'la visite B est listée à revoir').toBeVisible()
  await carteA.click()
  await lenteA.arrivee
  await carteB.click()
  await expect(p.getByText(B.nom).first(), 'B ouverte : son détail s\'affiche').toBeVisible({ timeout: 60_000 })
  await expect(p.getByRole('button', { name: /Retour/ }).first(), 'le détail (et non la liste) est affiché').toBeVisible()
  const repA = p.waitForResponse((x) => URL_A.test(new URL(x.url()).pathname) && x.request().method() === 'GET', T)
  lenteA.lacher()
  await repA
  await peindre(p)
  await peindre(p)
  await expect(p.getByText(B.nom).first(), 'après la réponse de A : B reste affichée').toBeVisible()
  await expect(p.getByText(A.nom), 'après la réponse de A : A n\'est jamais affichée').toHaveCount(0)
  await p.unroute(sur_URL_A)
  // (2) 500 sur la lecture d'une visite : « Lecture impossible », jamais « introuvable ».
  await p.reload()
  await expect(p.getByText(A.nom).first()).toBeVisible({ timeout: 90_000 })
  suivi.attendre(URL_A, 500)
  await p.route(sur_URL_A, (route) => (route.request().method() === 'GET'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: J({ detail: 'panne injectée AERR112' }) })
    : route.fallback()))
  await p.getByText(A.nom).first().click()
  await expect(toast(p, 'Lecture impossible'), '500 : « Lecture impossible »').toBeVisible({ timeout: 30_000 })
  await expect(p.getByText(/introuvable/i), '500 : jamais « introuvable »').toHaveCount(0)
  await expect(p.getByText(A.nom).first(), '500 : la liste reste là').toBeVisible()
})

etape('PF12.112-AERR112-calage', ['AERR112'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr112c_${m}`
  await compteRole(nom, 'Administrateur')
  const r = page.request
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AERR112C ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `c${m}@example.invalid`, type_installation: 'residentiel', facture_hiver: '900' } }), 'lead')
  const visite = await lireJson(await r.post(`${API}/visites/visites/`, { ...T, data: { lead: lead.id } }), 'visite')
  apres.push(async () => {
    await py(`from apps.visites.models import VisiteTerrain
VisiteTerrain.objects.filter(pk=${visite.id}).delete()
sortie(1)`)
    await supprimerLeads([lead.id])
  })
  const { p } = await ecran(page, suivi, testInfo, nom)
  const URL_V = new RegExp(`/api/django/visites/visites/${visite.id}/$`)
  const sur_URL_V = (u) => URL_V.test(u.pathname)
  suivi.attendre(URL_V, 500)
  await p.route(sur_URL_V, (route) => (route.request().method() === 'GET'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: J({ detail: 'panne injectée AERR112' }) })
    : route.fallback()))
  await p.goto(`/visites/${visite.id}/calage`)
  await expect(p.getByText('Lecture impossible.'), '500 : « Lecture impossible. »').toBeVisible({ timeout: 60_000 })
  await expect(p.getByRole('button', { name: 'Réessayer' }), '500 : bouton Réessayer').toBeVisible()
  await expect(p.getByText(/introuvable/i), '500 : jamais « introuvable »').toHaveCount(0)
  await p.unroute(sur_URL_V)
  await p.getByRole('button', { name: 'Réessayer' }).click()
  await expect(p.getByText('Calage du toit').first(), 'Réessayer : l\'écran du calage s\'affiche').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('Lecture impossible.'), 'Réessayer : l\'avis disparaît').toHaveCount(0)
  // 404 (vrai : visite inexistante) : « Visite introuvable. »
  suivi.attendre(/\/api\/django\/visites\/visites\/999999999\/$/, 404)
  await p.goto('/visites/999999999/calage')
  await expect(p.getByText('Visite introuvable.'), '404 : « Visite introuvable. »').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('Lecture impossible.'), '404 : pas « Lecture impossible. »').toHaveCount(0)
})
