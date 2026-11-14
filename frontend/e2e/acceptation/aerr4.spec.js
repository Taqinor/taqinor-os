// Preuves en direct du groupe AERR, lot 4 (audit de parcours PF12 « erreurs, pertes de saisie et gestes
// dangereux à l'écran », dossier docs/audits/2026-11-11-parcours-PF12.md) : AERR50, 52, 58, 61, 127 (socle de
// l'écran, deploy), AERR56, 59, 125 (paramètres), AERR57, 64 (sécurité), AERR65, 128 (documents), AERR121, 130
// (analyse). Chaque étape joue l'ÉCRAN nommé par la clause « Preuve en direct » sous un compte d'essai d'un rôle
// LIVRÉ du registre (société démo, session posée par la vraie route /token/), PROVOQUE l'échec (route Playwright
// déclarée AVANT par `suivi.attendre`, ou refus servi par le serveur), AFFIRME à l'écran ce que la clause nomme
// (message, saisie conservée, bouton désactivé, confirmation nommée, liste gardée), relit la base ou l'API, puis
// recharge et réaffirme. Données propres créées par l'API ou le shell Django, retirées en fin d'étape ; tout
// réglage de société modifié est rétabli en `finally`. Captures prises PENDANT que l'écran affirmé est visible
// (`ACCEPTATION-AERR-<étape>-<moment>.jpg`) en plus de la capture de fin d'étape du harnais.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { RACINE, cheminCapture } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, lireJson, listeDe, telephoneMobileUnique } from '../helpers.js'

// DÉFAUTS PRODUIT (rejeu runner du 14/11/2026) : les étapes d'AERR121, AERR125 et AERR130 échouent sur un défaut
// de l'écran (voir chaque étape). Elles ne sont jouées que sous `AERR4_DEFAUTS=1` (trace, jamais `couvre`) :
// l'enregistrement de clôture ne couvre que les tâches dont l'étape passe.
const DEFAUTS = !!process.env.AERR4_DEFAUTS
const etape = groupe('AERR', ['AERR50', 'AERR52', 'AERR58', 'AERR61', 'AERR127', 'AERR56', 'AERR59',
  'AERR57', 'AERR64', 'AERR65', 'AERR128', ...(DEFAUTS ? ['AERR125', 'AERR121', 'AERR130'] : [])])
const etapeDefaut = DEFAUTS ? etape : () => undefined
fermerDjangoApresTout()

// ÉCART ACCEPTÉ, BORNÉ (AERR50, AERR61, AERR127) : défaut ANTÉRIEUR aux tâches et HORS de leurs `Files:`.
const ECART_TOURNEE = {
  base: 'FAIL',
  raison: 'frontend/src/features/offlinesync/PrechargementTournee.jsx (NTMOB28, monté par Layout sur tout écran) lit '
    + 'installations/interventions/ma-tournee/ avant midi pour TOUT rôle ; le Commercial n\'a aucun code du module '
    + 'installations (LectureDuModule) ⇒ 403 d\'arrière-plan à chaque écran, sans rapport avec l\'écran rejoué. Borné : '
    + 'le corps de l\'étape échoue si un autre incident que ces 403 ma-tournee est observé.',
}
function seulsLes403Tournee(suivi) {
  const autres = suivi.incidents.filter((i) => !/\/installations\/interventions\/ma-tournee\//.test(i.texte))
  expect(autres, 'écart borné : aucun autre incident que les 403 de ma-tournee').toEqual([])
}
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 420_000 })
const SOC = `U.objects.get(username='demo_admin').company_id`
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const ouverts = []
const apres = []
const comptes = []
test.afterEach(async () => {
  for (const c of ouverts.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
  const noms = comptes.splice(0)
  if (noms.length) await py(`U.objects.filter(username__in=${J(noms)}).update(is_active=False)`).catch(() => undefined)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte })
const PDF = Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n')

/** Rejoue la sonde HÔTE du constat (`docs/audits/sondes/AERR/<c>.py`, lecture de source) : repro doit être faux. */
function sondeFausse(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AERR', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  expect(ligne, `sonde ${constat} exécutée : ${(r.stderr || '').trim().split('\n').pop()}`).toBeTruthy()
  const res = JSON.parse(ligne.slice(3))
  expect(res.repro, `sonde ${constat} : ${J(res.observe).slice(0, 400)}`).toBe(false)
  return res
}

/** Compte d'essai du rôle LIVRÉ `nomRole` (société démo) ; {nom, id}. Désactivé en fin d'étape. */
async function compteRole(prefixe, nomRole) {
  const nom = `${prefixe}_${marque()}`
  const id = await py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}).pk, societe=${SOC})
sortie(u.id)`)
  comptes.push(nom)
  return { nom, id }
}

/** Écran sous le compte `nom` : contexte neuf (SW bloqué, accueil et visites vus), session par /token/, observé.
 *  La page demo_admin de l'étape est refermée : la capture de fin montre l'écran du rôle joué. */
async function ecran(page, suivi, testInfo, nom, { viewport } = {}) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(viewport ? { viewport } : {}),
  })
  ouverts.push(ctx)
  await ctx.addInitScript(INIT)
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of listeDe(await visites.json())) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return suivi.surveiller(await ctx.newPage())
}

/** Panne INJECTÉE (déclarée au suivi AVANT) sur les requêtes `methode` d'URL `re` ; les autres passent. */
async function panne(p, suivi, re, { statut = 503, methode = 'GET', corps = { detail: 'Service indisponible (panne simulée, rejeu AERR).' } } = {}) {
  suivi.attendre(re, statut)
  const hits = { n: 0 }
  const h = (route) => {
    if (route.request().method() !== methode) return route.continue()
    hits.n += 1
    return route.fulfill({ status: statut, contentType: 'application/json', body: J(corps) })
  }
  await p.route(re, h)
  return { hits, lever: () => p.unroute(re, h) }
}

/** Compte les requêtes `methode` d'URL `re` parties de la page. */
function compteur(p, re, methode) {
  const c = { n: 0 }
  p.on('request', (q) => { if (q.method() === methode && re.test(q.url())) c.n += 1 })
  return c
}

/** Capture prise PENDANT que l'écran affirmé est visible. */
async function cliche(p, id, moment) {
  const abs = join(RACINE, cheminCapture('AERR', `${id}-${moment}`))
  mkdirSync(dirname(abs), { recursive: true })
  await p.screenshot({ path: abs, type: 'jpeg', quality: 60 })
}

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

/** Devis ENVOYÉ : lead + devis portés par `cree`, produit par demo_admin (`r`). */
async function devisEnvoye(r, cree, m, tag) {
  const l = await lireJson(await cree.post(`${API}/crm/leads/`, { ...T, data: { nom: `${tag} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${tag.toLowerCase()}-${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation ${tag} ${m}`, prix_vente: '5000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: l.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  expect(relu.statut, 'devis envoyé').toBe('envoye')
  return { id: d.id, reference: relu.reference, client: relu.client, leadId: l.id, produitId: p.id }
}
const nettoyerVente = (v) => py(`from apps.ventes.models import Devis
from apps.crm.models import Lead
from apps.stock.models import Produit
for f in (lambda: Devis.objects.filter(pk=${v.id}).delete(), lambda: Lead.all_objects.filter(pk=${v.leadId}).delete(), lambda: Produit.objects.filter(pk=${v.produitId}).delete()):
    try: f()
    except Exception as exc: print('nettoyage', exc)`)

// ═══ PF12.4 — AERR50 : boîte ouverte, « g l » et « ? » tapés sur un bouton ne naviguent pas, n'ouvrent pas l'aide ═══
etape('PF12.4-AERR50', ['AERR50'], async ({ page, context, suivi, testInfo }) => {
  sondeFausse('C-AERR-022')
  const r = context.request
  const m = marque()
  const co = await compteRole('aerr50co', 'Commercial')
  const p = await ecran(page, suivi, testInfo, co.nom)
  const v = await devisEnvoye(r, p.request, m, 'AERR50')
  apres.push(() => nettoyerVente(v))
  const dlg = p.getByRole('dialog').filter({ hasText: `Accepter le devis — ${v.reference}` })
  const champ = dlg.getByLabel('Nom de la personne qui accepte')
  const aide = p.getByRole('dialog').filter({ hasText: 'Raccourcis clavier' })
  const ouvrir = async () => {
    await p.goto(`/ventes/devis?devis=${v.id}`)
    const ligne = p.locator(`#devis-row-${v.id}`)
    await expect(ligne, 'ligne du devis envoyé').toBeVisible({ timeout: 60_000 })
    await ligne.getByRole('button', { name: 'Accepter', exact: true }).click()
    await expect(dlg, 'boîte « Accepter le devis » ouverte').toBeVisible({ timeout: 30_000 })
  }
  const frapper = async (quand) => {
    const saisie = `Signataire AERR50 ${m} ${quand}`
    await champ.fill(saisie)
    // Focus sur un BOUTON de la boîte (pas un champ de saisie) : seule la garde de boîte peut taire les séquences.
    await dlg.getByRole('button', { name: 'Annuler', exact: true }).focus()
    await p.keyboard.press('g')
    await p.keyboard.press('l')
    await p.keyboard.press('?')
    await expect(p, `${quand} : « g l » ne navigue pas`).toHaveURL(/\/ventes\/devis/)
    await expect(dlg, `${quand} : la boîte reste ouverte`).toBeVisible()
    await expect(aide, `${quand} : « ? » n'ouvre pas l'aide par-dessus`).toHaveCount(0)
    await expect(champ, `${quand} : la saisie de la boîte est conservée`).toHaveValue(saisie)
    // Un second aller-retour avec la page (frappe dans le champ) avant de relire : rien n'a bougé entre-temps.
    await champ.press('End')
    await expect(p).toHaveURL(/\/ventes\/devis/)
    await expect(champ).toHaveValue(saisie)
  }
  await ouvrir()
  await frapper('boîte ouverte')
  await cliche(p, 'PF12.4-AERR50', 'boite-ouverte')
  // Témoin : boîte fermée ⇒ « g l » navigue comme avant.
  await dlg.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(dlg).toHaveCount(0)
  await p.keyboard.press('g')
  await p.keyboard.press('l')
  await expect(p, 'boîte fermée : « g l » mène aux leads').toHaveURL(/\/crm\/leads/, { timeout: 15_000 })
  // Persistance : l'écran est rechargé (nouvelle visite), la garde tient toujours ; le devis n'est pas accepté.
  await ouvrir()
  await p.reload()
  await expect(p.locator(`#devis-row-${v.id}`)).toBeVisible({ timeout: 60_000 })
  await p.locator(`#devis-row-${v.id}`).getByRole('button', { name: 'Accepter', exact: true }).click()
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await frapper('après rechargement')
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${v.id}/`, T), 'devis relu')
  expect(relu.statut, 'en base : le devis reste envoyé (rien n\'est parti)').toBe('envoye')
  seulsLes403Tournee(suivi)
}, { ecart: ECART_TOURNEE })

// ═══ PF12.1 — AERR52 : Tiers → nouveau tiers, ICE refusé ⇒ le toast global NOMME le champ ═══
etape('PF12.1-AERR52', ['AERR52'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-024')
  const m = marque()
  const ad = await compteRole('aerr52ad', 'Administrateur')
  const p = await ecran(page, suivi, testInfo, ad.nom)
  const CREER = /\/api\/django\/tiers\/tiers\/$/
  suivi.attendre(CREER, 400)
  const nom = `AERR52 Tiers ${m}`
  const iceRefuse = `ICE${'9'.repeat(30)}`
  const essai = async (quand) => {
    await p.goto('/tiers')
    await p.getByRole('button', { name: 'Nouveau tiers' }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: 'Nouveau tiers' })
    await expect(dlg).toBeVisible({ timeout: 60_000 })
    await dlg.locator('#tiers-nom').fill(nom)
    await dlg.locator('#tiers-ice').fill(iceRefuse)
    const [rep] = await Promise.all([
      p.waitForResponse((x) => x.request().method() === 'POST' && CREER.test(x.url())),
      dlg.getByRole('button', { name: 'Créer le tiers' }).click(),
    ])
    expect(rep.status(), `${quand} : le serveur refuse l'ICE`).toBe(400)
    const corps = await rep.json()
    expect(Array.isArray(corps.ice) && corps.ice.length > 0, `${quand} : refus PAR CHAMP sur l'ICE ${J(corps)}`).toBe(true)
    expect(corps.detail, `${quand} : pas de detail global (le message vient du champ)`).toBeUndefined()
    const msg = String(corps.ice[0])
    await expect(toast(p, `ICE : ${msg}`), `${quand} : le toast global dit « ICE : ${msg} »`).toBeVisible({ timeout: 30_000 })
    const textes = await p.locator('[data-sonner-toast]').allInnerTexts()
    expect(textes.filter((t) => t.includes(msg) && !t.includes(`ICE : ${msg}`)), `${quand} : aucun toast au message nu`).toEqual([])
    await expect(dlg, `${quand} : la boîte reste ouverte`).toBeVisible()
    await expect(dlg.locator('#tiers-nom'), `${quand} : la saisie est conservée`).toHaveValue(nom)
    await expect(dlg.locator('#tiers-ice')).toHaveValue(iceRefuse)
    await cliche(p, 'PF12.1-AERR52', quand === 'premier essai' ? 'toast' : 'toast-apres-rechargement')
  }
  await essai('premier essai')
  const n = await py(`from apps.tiers.models import Tiers
sortie(Tiers.objects.filter(company_id=${SOC}, nom=${J(nom)}).count())`)
  expect(n, 'en base : aucun tiers créé par le refus').toBe(0)
  // Persistance : recharger l'écran puis rejouer le même geste ⇒ même toast nommé.
  await p.reload()
  await essai('après rechargement')
})

// ═══ PF12.3 — AERR58 : GED → Corbeille, restaurer avec la relecture coupée ⇒ lignes gardées + « Liste peut-être pas à jour » ═══
etape('PF12.3-AERR58', ['AERR58'], async ({ page, context, suivi, testInfo }) => {
  const s = sondeFausse('C-AERR-028')
  if ((s.observe?.introuvable || []).length) console.log(`[AERR58] sonde C-AERR-028 : ancre introuvable (${J(s.observe.introuvable)}), repro faux non probant ; preuve portée par l'écran`)
  const r = context.request
  const m = marque()
  const cab = await lireJson(await r.post(`${API}/ged/cabinets/`, { ...T, data: { nom: `AERR58 ${m}` } }), 'armoire')
  apres.push(() => py(`from apps.ged.models import Cabinet
try: Cabinet.objects.filter(pk=${cab.id}).delete()
except Exception as exc: print('nettoyage', exc)`))
  const dos = await lireJson(await r.post(`${API}/ged/dossiers/`, { ...T, data: { nom: `Dossier AERR58 ${m}`, cabinet: cab.id } }), 'dossier')
  const docs = []
  for (const x of ['A', 'B']) {
    const d = await lireJson(await r.post(`${API}/ged/documents/`, { ...T, data: { nom: `AERR58 ${x} ${m}.pdf`, folder: dos.id } }), `document ${x}`)
    await lireJson(await r.post(`${API}/ged/documents/${d.id}/mettre-en-corbeille/`, { ...T, data: {} }), `corbeille ${x}`)
    docs.push(d)
  }
  const di = await compteRole('aerr58di', 'Directeur')
  const p = await ecran(page, suivi, testInfo, di.nom)
  const ligne = (x) => p.getByRole('row').filter({ hasText: `AERR58 ${x} ${m}` })
  const avis = p.locator('[data-dt-stale]')
  const filtrer = async () => {
    await p.getByLabel('Recherche globale').first().fill(`AERR58`)
    await expect(ligne('A').or(ligne('B')).first()).toBeVisible({ timeout: 60_000 })
  }
  const restaurer = async (x) => {
    await ligne(x).getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
    await p.getByRole('menuitem', { name: 'Restaurer' }).click()
    await expect(toast(p, 'Document restauré.')).toBeVisible({ timeout: 30_000 })
  }
  const enCorbeille = async () => new Set((await lignes(r, `${API}/ged/documents/corbeille/`)).map((d) => d.id))
  const LISTE = /\/api\/django\/ged\/documents\/corbeille\/(\?|$)/
  await p.goto('/ged/corbeille')
  await filtrer()
  await expect(ligne('A')).toBeVisible()
  await expect(ligne('B')).toBeVisible()
  // La relecture qui suit la restauration est coupée (5xx).
  let coupure = await panne(p, suivi, LISTE)
  await restaurer('A')
  await expect.poll(() => coupure.hits.n, { message: 'la relecture après restauration a bien échoué', timeout: 30_000 }).toBeGreaterThan(0)
  await expect(avis, 'avis « Liste peut-être pas à jour »').toContainText('Liste peut-être pas à jour', { timeout: 30_000 })
  await expect(ligne('A'), 'la liste affichée est gardée (A)').toBeVisible()
  await expect(ligne('B'), 'la liste affichée est gardée (B)').toBeVisible()
  await expect(p.getByText('Erreur de chargement'), 'jamais l\'état d\'erreur à la place des lignes').toHaveCount(0)
  await expect(p.getByText('Corbeille vide')).toHaveCount(0)
  await cliche(p, 'PF12.3-AERR58', 'relecture-coupee')
  let ids = await enCorbeille()
  expect([ids.has(docs[0].id), ids.has(docs[1].id)], 'en base : A restauré, B toujours en corbeille').toEqual([false, true])
  // Persistance : API rétablie, recharger ⇒ A a quitté la corbeille, B y est.
  await coupure.lever()
  await p.reload()
  await filtrer()
  await expect(ligne('B')).toBeVisible()
  await expect(ligne('A'), 'après rechargement : A restauré, hors corbeille').toHaveCount(0)
  await expect(avis).toHaveCount(0)
  // Réaffirmé après le rechargement : nouvelle restauration sous coupure ⇒ la ligne reste avec l'avis.
  coupure = await panne(p, suivi, LISTE)
  await restaurer('B')
  await expect(avis).toContainText('Liste peut-être pas à jour', { timeout: 30_000 })
  await expect(ligne('B'), 'après rechargement : la ligne reste affichée avec l\'avis').toBeVisible()
  ids = await enCorbeille()
  expect(ids.has(docs[1].id), 'en base : B restauré').toBe(false)
})

// ═══ PF12.3 — AERR61 : fiche lead, lecture des pièces jointes coupée ⇒ « Pièces jointes non chargées » + Réessayer ═══
etape('PF12.3-AERR61', ['AERR61'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-031')
  const m = marque()
  const co = await compteRole('aerr61co', 'Commercial')
  const lead = await py(`from apps.crm.models import Lead
l = Lead.objects.create(company_id=${SOC}, nom='AERR61 ${m}', telephone='${telephoneMobileUnique()}', owner_id=${co.id}, stage='NEW')
sortie(l.pk)`)
  apres.push(() => py(`from apps.crm.models import Lead
from apps.records.models import Attachment
try: Attachment.objects.filter(object_id=${lead}).delete()
except Exception as exc: print('nettoyage', exc)
try: Lead.all_objects.filter(pk=${lead}).delete()
except Exception as exc: print('nettoyage', exc)`))
  const p = await ecran(page, suivi, testInfo, co.nom, { viewport: { width: 1600, height: 1000 } })
  const fichier = `piece-aerr61-${m}.pdf`
  await lireJson(await p.request.post(`${API}/records/attachments/`, { ...T, multipart: { model: 'crm.lead', id: String(lead), file: { name: fichier, mimeType: 'application/pdf', buffer: PDF } } }), 'pièce jointe')
  const LECTURE = /\/api\/django\/records\/attachments\/\?/
  const avis = p.getByRole('alert').filter({ hasText: 'Pièces jointes non chargées.' })
  const ouvrirPieces = async () => {
    await p.goto(`/crm/leads/${lead}`)
    await p.getByRole('tab', { name: /^Pièces/ }).click({ timeout: 60_000 })
  }
  let coupure = await panne(p, suivi, LECTURE)
  await ouvrirPieces()
  await expect(avis, 'avis « Pièces jointes non chargées »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(p.getByText('Aucune pièce jointe.'), 'jamais « Aucune pièce jointe. » sur une lecture rejetée').toHaveCount(0)
  await cliche(p, 'PF12.3-AERR61', 'lecture-coupee')
  // « Réessayer » relance la lecture (API rétablie) et montre la pièce servie.
  await coupure.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(p.getByText(fichier), 'Réessayer : la pièce servie s\'affiche').toBeVisible({ timeout: 30_000 })
  await expect(avis).toHaveCount(0)
  const servies = listeDe(await lireJson(await p.request.get(`${API}/records/attachments/?model=crm.lead&id=${lead}`, T), 'pièces'))
  expect(servies.map((a) => a.filename), 'en base : la pièce existe').toContain(fichier)
  // Persistance : recharger la fiche ⇒ la pièce est listée ; puis rechargée sous coupure ⇒ l'avis, jamais le vide.
  await ouvrirPieces()
  await expect(p.getByText(fichier)).toBeVisible({ timeout: 30_000 })
  coupure = await panne(p, suivi, LECTURE)
  await p.reload()
  await p.getByRole('tab', { name: /^Pièces/ }).click({ timeout: 60_000 })
  await expect(avis, 'après rechargement : avis, pas « Aucune pièce jointe. »').toBeVisible({ timeout: 30_000 })
  await expect(p.getByText('Aucune pièce jointe.')).toHaveCount(0)
  seulsLes403Tournee(suivi)
}, { ecart: ECART_TOURNEE })

// ═══ PF12.3 — AERR127 : cloche, sondage du fil rejeté ⇒ les 3 notifications restent ; 1er chargement rejeté ⇒ « Notifications indisponibles » ═══
etape('PF12.3-AERR127', ['AERR127'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await compteRole('aerr127co', 'Commercial')
  await py(`from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
u = U.objects.get(pk=${co.id})
Notification.objects.filter(recipient=u).delete()
for i in range(3):
    Notification.objects.create(company_id=u.company_id, recipient=u, event_type=EventType.LEAD_ASSIGNED, title='AERR127 lue %d ${m}' % i, read=True)
sortie(1)`)
  apres.push(() => py(`from apps.notifications.models import Notification
Notification.objects.filter(recipient_id=${co.id}).delete()`))
  const p = await ecran(page, suivi, testInfo, co.nom)
  const cloche = p.getByRole('button', { name: /^Notifications \(\d+\)$/ }).first()
  const panneau = p.locator('.nb-panel')
  const lues = panneau.locator('.nb-item').filter({ hasText: `AERR127 lue` })
  const FIL = /\/api\/django\/notifications\/notifications\/\?/
  // Le panneau se ferme par un clic hors de lui ou un second clic sur la cloche (Échap ne le ferme pas).
  const ouvrir = async () => { await cloche.click({ timeout: 60_000 }); await expect(panneau).toBeVisible({ timeout: 30_000 }) }
  const fermer = async () => { await cloche.click(); await expect(panneau).toBeHidden({ timeout: 15_000 }) }
  await p.goto('/apps')
  await ouvrir()
  await expect(lues, 'avant : les 3 notifications sont listées').toHaveCount(3, { timeout: 30_000 })
  await fermer()
  // Le sondage suivant du fil est rejeté : une nouvelle notification fait monter le compteur, ce qui relit le fil.
  let coupure = await panne(p, suivi, FIL)
  await py(`from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
u = U.objects.get(pk=${co.id})
Notification.objects.create(company_id=u.company_id, recipient=u, event_type=EventType.LEAD_ASSIGNED, title='AERR127 nouvelle ${m}')
sortie(1)`)
  await expect.poll(() => coupure.hits.n, { message: 'le fil a été relu (sondage) et la lecture rejetée', timeout: 75_000 }).toBeGreaterThan(0)
  await ouvrir()
  await expect(lues, 'sondage rejeté : les 3 notifications restent dans le menu').toHaveCount(3, { timeout: 30_000 })
  await expect(panneau.getByText('Rien à signaler 🎉'), 'jamais « Rien à signaler » sur un sondage rejeté').toHaveCount(0)
  await cliche(p, 'PF12.3-AERR127', 'sondage-rejete')
  await fermer()
  // Persistance : API rétablie, recharger ⇒ le fil relu montre les 4 (base).
  await coupure.lever()
  await p.reload()
  await ouvrir()
  await expect(panneau.locator('.nb-item').filter({ hasText: 'AERR127' }), 'après rechargement : 4 notifications').toHaveCount(4, { timeout: 30_000 })
  const n = await py(`from apps.notifications.models import Notification
sortie(Notification.objects.filter(recipient_id=${co.id}, title__startswith='AERR127').count())`)
  expect(n, 'en base : 4 notifications').toBe(4)
  await fermer()
  // Premier chargement rejeté (recharger sous coupure) ⇒ « Notifications indisponibles », jamais le message vide.
  coupure = await panne(p, suivi, FIL)
  await p.reload()
  await ouvrir()
  await expect(panneau.getByText('Notifications indisponibles'), 'premier chargement rejeté : avis').toBeVisible({ timeout: 30_000 })
  await expect(panneau.getByText('Rien à signaler 🎉')).toHaveCount(0)
  await cliche(p, 'PF12.3-AERR127', 'premier-chargement-rejete')
  seulsLes403Tournee(suivi)
}, { ecart: ECART_TOURNEE })

// ═══ PF12.2 — AERR56 : lecture d'un réglage rejetée ⇒ « Réglages non chargés » + Réessayer, rien d'enregistrable, aucun PATCH ═══
etape('PF12.2-AERR56', ['AERR56'], async ({ page, context, suivi, testInfo }) => {
  sondeFausse('C-AERR-027')
  const r = context.request
  const m = marque()
  const ad = await compteRole('aerr56ad', 'Administrateur')
  const p = await ecran(page, suivi, testInfo, ad.nom)
  const avis = p.getByRole('alert').filter({ hasText: 'Réglages non chargés' })
  const enregistrer = p.getByRole('button', { name: /Enregistrer/ })
  const lire = async (url) => lireJson(await r.get(`${API}${url}`, T), url)
  // Rejoue un écran : lecture coupée ⇒ avis, aucun bouton Enregistrer, aucun PATCH, configuration intacte en base ;
  // Réessayer (API rétablie) ⇒ formulaire ; recharger sous coupure ⇒ avis de nouveau.
  const rejouer = async ({ quoi, chemin, coupe, ecrit, relire, formulaire }) => {
    const avant = await lire(relire)
    const patchs = compteur(p, ecrit, 'PATCH')
    let coupure = await panne(p, suivi, coupe)
    await p.goto(chemin)
    await expect(avis, `${quoi} : avis « Réglages non chargés »`).toBeVisible({ timeout: 60_000 })
    await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
    await expect(enregistrer, `${quoi} : aucun formulaire proposé à l'enregistrement`).toHaveCount(0)
    await cliche(p, 'PF12.2-AERR56', `${quoi}-lecture-coupee`)
    expect(patchs.n, `${quoi} : aucun PATCH`).toBe(0)
    expect(await lire(relire), `${quoi} : configuration serveur intacte`).toEqual(avant)
    await coupure.lever()
    await avis.getByRole('button', { name: 'Réessayer' }).click()
    await formulaire(avant)
    await expect(avis).toHaveCount(0)
    await expect(enregistrer.first(), `${quoi} : lecture réussie ⇒ formulaire enregistrable`).toBeVisible()
    coupure = await panne(p, suivi, coupe)
    await p.reload()
    await expect(avis, `${quoi} : après rechargement sous coupure, l'avis encore`).toBeVisible({ timeout: 60_000 })
    await expect(enregistrer).toHaveCount(0)
    expect(patchs.n, `${quoi} : toujours aucun PATCH`).toBe(0)
    expect(await lire(relire), `${quoi} : configuration toujours intacte`).toEqual(avant)
    await coupure.lever()
  }
  // Tarification (barème ONEE).
  await rejouer({
    quoi: 'tarification', chemin: '/parametres?onglet=tarification',
    coupe: /\/api\/django\/parametres\/tarification\/(\?|$)/, ecrit: /\/parametres\/tarification\/update\//,
    relire: '/parametres/tarification/',
    formulaire: async (avant) => {
      const prix = p.getByLabel('Prix palier 1')
      await expect(prix, 'tarification relue : barème affiché').toBeVisible({ timeout: 30_000 })
      if ((avant.residential_tiers || []).length) await expect(prix).toHaveValue(String(avant.residential_tiers[0].prix_kwh_ttc))
    },
  })
  // Documents : titre des CGV marqué avant, jamais effacé par un formulaire vide.
  const docAvant = await lire('/parametres/document-templates/')
  const titre = `CGV AERR56 ${m}`
  await lireJson(await r.patch(`${API}/parametres/document-templates/update/`, { ...T, data: { cgv_titre: titre } }), 'titre CGV marqué')
  try {
    await rejouer({
      quoi: 'documents', chemin: '/parametres?onglet=documents',
      coupe: /\/api\/django\/parametres\/document-templates\/(\?|$)/, ecrit: /\/parametres\/document-templates\/update\//,
      relire: '/parametres/document-templates/',
      formulaire: async (avant) => {
        expect(avant.cgv_titre, 'documents : la marque est en base avant le geste').toBe(titre)
        await expect.poll(() => p.locator('input, textarea').evaluateAll((els, v) => els.some((e) => e.value === v), titre),
          { message: 'documents relus : le titre CGV servi est affiché', timeout: 30_000 }).toBe(true)
      },
    })
  } finally {
    await r.patch(`${API}/parametres/document-templates/update/`, { ...T, data: { cgv_titre: docAvant.cgv_titre ?? '' } })
  }
  // Fiabilité.
  await rejouer({
    quoi: 'fiabilite', chemin: '/parametres/fiabilite-reglages',
    coupe: /\/api\/django\/core\/fiabilite\/reglages\/(\?|$)/, ecrit: /\/core\/fiabilite\/reglages\//,
    relire: '/core/fiabilite/reglages/',
    formulaire: async (avant) => {
      await expect(p.locator('#fiab-region'), 'fiabilité relue : formulaire affiché').toBeVisible({ timeout: 30_000 })
      await expect(p.locator('#fiab-region')).toHaveValue(String(avant.notifier_incident_region ?? ''))
    },
  })
  // Réglages UX : seule la lecture des RÔLES échoue (constat) ; les réglages UX eux-mêmes restent servis.
  await rejouer({
    quoi: 'ux', chemin: '/parametres/ux',
    coupe: /\/api\/django\/roles\/(\?|$)/, ecrit: /\/uxviews\/parametres\//,
    relire: '/uxviews/parametres/',
    formulaire: async () => {
      await expect(p.getByText('Autoriser les vues partagées d\'équipe'), 'réglages UX relus : formulaire affiché').toBeVisible({ timeout: 30_000 })
    },
  })
  // Fin d'étape sur l'écran affirmé : Tarification, lecture coupée.
  await panne(p, suivi, /\/api\/django\/parametres\/tarification\/(\?|$)/)
  await p.goto('/parametres?onglet=tarification')
  await expect(avis).toBeVisible({ timeout: 60_000 })
})

// ═══ PF12.2 — AERR57 : Sécurité & identité → Bannière, profil illisible ⇒ avis + Réessayer, Enregistrer désactivé, aucun updateProfile ═══
etape('PF12.2-AERR57', ['AERR57'], async ({ page, context, suivi, testInfo }) => {
  sondeFausse('C-AERR-027')
  const r = context.request
  const m = marque()
  const profil = async () => lireJson(await r.get(`${API}/parametres/`, T), 'profil')
  const origine = await profil()
  const banniere = `Accès réservé — AERR57 ${m}`
  await lireJson(await r.patch(`${API}/parametres/update/`, { ...T, data: { login_banner_text: banniere, lockout_max_attempts: 7 } }), 'bannière marquée')
  try {
    const ad = await compteRole('aerr57ad', 'Administrateur')
    const p = await ecran(page, suivi, testInfo, ad.nom)
    const PROFIL = /\/api\/django\/parametres\/(\?|$)/
    const patchs = compteur(p, /\/api\/django\/parametres\/update\//, 'PATCH')
    const avis = p.getByRole('alert').filter({ hasText: 'n\'ont pas pu être lus' })
    const enregistrer = p.getByRole('button', { name: 'Enregistrer', exact: true })
    const ouvrirBanniere = async () => {
      await expect(p.getByRole('heading', { name: 'Sécurité & Identité' })).toBeVisible({ timeout: 60_000 })
      await p.getByRole('tab', { name: /Bannière/ }).click()
    }
    await p.goto('/admin/securite-identite')
    let coupure = await panne(p, suivi, PROFIL)
    await ouvrirBanniere()
    await expect(avis, 'avis : réglages non lus, rien ne peut être enregistré').toBeVisible({ timeout: 30_000 })
    await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
    await expect(enregistrer, 'Enregistrer désactivé').toBeDisabled()
    await cliche(p, 'PF12.2-AERR57', 'lecture-coupee')
    expect(patchs.n, 'aucun updateProfile').toBe(0)
    let lu = await profil()
    expect([lu.login_banner_text, lu.lockout_max_attempts], 'en base : bannière et seuil intacts').toEqual([banniere, 7])
    // Réessayer (API rétablie) ⇒ les valeurs servies, Enregistrer actif.
    await coupure.lever()
    await avis.getByRole('button', { name: 'Réessayer' }).click()
    await expect(p.locator('#banner'), 'relu : bannière servie').toHaveValue(banniere, { timeout: 30_000 })
    await expect(p.locator('#lockout'), 'relu : seuil servi').toHaveValue('7')
    await expect(enregistrer).toBeEnabled()
    // Persistance : recharger sous coupure ⇒ même avis, bouton désactivé, base intacte.
    coupure = await panne(p, suivi, PROFIL)
    await p.reload()
    await ouvrirBanniere()
    await expect(avis, 'après rechargement : avis').toBeVisible({ timeout: 30_000 })
    await expect(enregistrer).toBeDisabled()
    expect(patchs.n).toBe(0)
    lu = await profil()
    expect([lu.login_banner_text, lu.lockout_max_attempts], 'en base : toujours intacts').toEqual([banniere, 7])
  } finally {
    await r.patch(`${API}/parametres/update/`, { ...T, data: { login_banner_text: origine.login_banner_text ?? '', lockout_max_attempts: origine.lockout_max_attempts ?? 0 } })
  }
})

// ═══ PF12.4 — AERR64 : supprimer une plage IP, un compte de service, une règle SoD ⇒ boîte nommée, « Annuler » n'envoie rien ═══
etape('PF12.4-AERR64', ['AERR64'], async ({ page, context, suivi, testInfo }) => {
  sondeFausse('C-AERR-033')
  const r = context.request
  const m = marque()
  const cidr = `10.${Math.floor(Math.random() * 200) + 20}.${Math.floor(Math.random() * 250)}.0/24`
  const ip = await py(`from apps.identity.models import NetworkPolicy, IpAllowRule
pol = NetworkPolicy.objects.filter(company_id=${SOC}).first()
cree = pol is None
if cree: pol = NetworkPolicy.objects.create(company_id=${SOC}, mode='off')
regle = IpAllowRule.objects.create(company_id=${SOC}, policy=pol, cidr=${J(cidr)}, label='Bureau AERR64 ${m}')
sortie(dict(regle=regle.pk, pol=pol.pk, cree=cree))`)
  const sa = await lireJson(await r.post(`${API}/identity/service-accounts/`, { ...T, data: { nom: `Intégration AERR64 ${m}` } }), 'compte de service')
  const sod = await py(`from apps.accessreview.models import SodRule
from apps.roles.permissions_registre import ALL_PERMISSIONS
codes = sorted(ALL_PERMISSIONS)
pris = set(SodRule.objects.filter(company_id=${SOC}).values_list('permission_a', 'permission_b'))
a, b = next((a, b) for i, a in enumerate(codes) for b in codes[i + 1:] if (a, b) not in pris and (b, a) not in pris)
s = SodRule.objects.create(company_id=${SOC}, permission_a=a, permission_b=b, severite='warning', libelle='AERR64 ${m}')
sortie(dict(id=s.pk, a=a, b=b))`)
  apres.push(() => py(`from apps.identity.models import NetworkPolicy, IpAllowRule
from apps.accessreview.models import SodRule
from apps.publicapi.models import ServiceAccount
IpAllowRule.objects.filter(pk=${ip.regle}).delete()
if ${ip.cree ? 'True' : 'False'}: NetworkPolicy.objects.filter(pk=${ip.pol}, rules__isnull=True).delete()
SodRule.objects.filter(pk=${sod.id}).delete()
ServiceAccount.objects.filter(pk=${sa.id}).delete()`))
  const existe = () => py(`from apps.identity.models import IpAllowRule
from apps.accessreview.models import SodRule
from apps.publicapi.models import ServiceAccount
sortie([IpAllowRule.objects.filter(pk=${ip.regle}).exists(), ServiceAccount.objects.filter(pk=${sa.id}).exists(), SodRule.objects.filter(pk=${sod.id}).exists()])`)
  const ad = await compteRole('aerr64ad', 'Administrateur')
  const p = await ecran(page, suivi, testInfo, ad.nom)
  const suppressions = compteur(p, /\/api\/django\/(identity\/ip-allow-rules|identity\/service-accounts|accessreview\/sod-rules)\/\d+\/$/, 'DELETE')
  const boite = p.getByRole('alertdialog')
  // Ouvre la boîte d'une ligne, vérifie qu'elle NOMME l'objet, « Annuler » ⇒ aucune requête.
  const annuler = async (ligne, bouton, titre, quoi) => {
    await ligne.getByRole('button', { name: bouton }).click()
    await expect(boite, `${quoi} : boîte nommée`).toContainText(titre, { timeout: 15_000 })
    return boite
  }
  // ── Réseau : la plage IP.
  const regle = () => p.getByTestId('ip-rules').locator('div.rounded-md').filter({ hasText: cidr })
  await p.goto('/admin/securite-identite')
  await expect(regle(), 'plage listée').toBeVisible({ timeout: 60_000 })
  const b1 = await annuler(regle(), 'Supprimer la règle', `Supprimer la plage « ${cidr} » ?`, 'plage IP')
  await expect(b1, 'la boîte dit l\'effet (perte d\'accès)').toContainText('perdra l’accès')
  await cliche(p, 'PF12.4-AERR64', 'plage-ip-boite')
  await b1.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(boite).toHaveCount(0)
  expect(suppressions.n, 'plage : « Annuler » n\'envoie aucune suppression').toBe(0)
  // ── Comptes de service.
  const compteSa = () => p.getByTestId('service-accounts').locator('div.rounded-md').filter({ hasText: `Intégration AERR64 ${m}` })
  await p.getByRole('tab', { name: /Comptes de service/ }).click()
  await expect(compteSa(), 'compte de service listé').toBeVisible({ timeout: 30_000 })
  const b2 = await annuler(compteSa(), 'Supprimer le compte de service', `Supprimer le compte de service « Intégration AERR64 ${m} » ?`, 'compte de service')
  await cliche(p, 'PF12.4-AERR64', 'compte-service-boite')
  await b2.getByRole('button', { name: 'Annuler', exact: true }).click()
  expect(suppressions.n, 'compte de service : « Annuler » n\'envoie rien').toBe(0)
  // ── Règle SoD.
  const ligneSod = () => p.getByTestId('sod').locator('div.rounded-md').filter({ has: p.locator('code', { hasText: new RegExp(`^${sod.a}$`) }) })
    .filter({ has: p.locator('code', { hasText: new RegExp(`^${sod.b}$`) }) })
  await p.goto('/admin/gouvernance-acces')
  await p.getByRole('tab', { name: /Règles SoD/ }).click({ timeout: 60_000 })
  await expect(ligneSod(), 'règle SoD listée').toBeVisible({ timeout: 30_000 })
  const b3 = await annuler(ligneSod(), 'Supprimer la règle', `Supprimer la règle SoD « ${sod.a} ⊗ ${sod.b} » ?`, 'règle SoD')
  await cliche(p, 'PF12.4-AERR64', 'regle-sod-boite')
  await b3.getByRole('button', { name: 'Annuler', exact: true }).click()
  expect(suppressions.n, 'règle SoD : « Annuler » n\'envoie rien').toBe(0)
  expect(await existe(), 'en base après « Annuler » : plage, compte et règle intacts').toEqual([true, true, true])
  // Persistance : recharger ⇒ les trois toujours listés ; puis « Supprimer » dans la boîte ⇒ UN appel, objet parti.
  await p.reload()
  await p.getByRole('tab', { name: /Règles SoD/ }).click({ timeout: 60_000 })
  await expect(ligneSod(), 'après rechargement : règle SoD toujours listée').toBeVisible({ timeout: 30_000 })
  await annuler(ligneSod(), 'Supprimer la règle', `« ${sod.a} ⊗ ${sod.b} »`, 'règle SoD')
  await boite.getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect(ligneSod()).toHaveCount(0, { timeout: 30_000 })
  await p.goto('/admin/securite-identite')
  await expect(regle(), 'après rechargement : plage toujours listée').toBeVisible({ timeout: 60_000 })
  await annuler(regle(), 'Supprimer la règle', `Supprimer la plage « ${cidr} » ?`, 'plage IP')
  await boite.getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect(regle()).toHaveCount(0, { timeout: 30_000 })
  await p.getByRole('tab', { name: /Comptes de service/ }).click()
  await expect(compteSa(), 'après rechargement : compte toujours listé').toBeVisible({ timeout: 30_000 })
  await annuler(compteSa(), 'Supprimer le compte de service', `« Intégration AERR64 ${m} »`, 'compte de service')
  await boite.getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect(compteSa()).toHaveCount(0, { timeout: 30_000 })
  expect(suppressions.n, '« Supprimer » confirmé : exactement trois suppressions').toBe(3)
  expect(await existe(), 'en base après confirmation : les trois supprimés').toEqual([false, false, false])
  // Fin d'étape sur la boîte nommée (écran affirmé) : nouvelle plage, boîte ouverte.
  const cidr2 = cidr.replace('.0/24', '.128/25')
  await py(`from apps.identity.models import IpAllowRule
IpAllowRule.objects.create(company_id=${SOC}, policy_id=${ip.pol}, cidr=${J(cidr2)}, label='Bureau AERR64 bis ${m}')`)
  apres.push(() => py(`from apps.identity.models import IpAllowRule
IpAllowRule.objects.filter(company_id=${SOC}, cidr=${J(cidr2)}).delete()`))
  await p.getByRole('tab', { name: /Réseau/ }).click()
  await p.reload()
  const regle2 = p.getByTestId('ip-rules').locator('div.rounded-md').filter({ hasText: cidr2 })
  await expect(regle2).toBeVisible({ timeout: 60_000 })
  await annuler(regle2, 'Supprimer la règle', `Supprimer la plage « ${cidr2} » ?`, 'plage IP bis')
})

// ═══ PF12.4 — AERR65 : GED → Approbations → signatures : « Marquer comme signée », « Annuler la demande », tag ⇒ boîte nommée ═══
etape('PF12.4-AERR65', ['AERR65'], async ({ page, context, suivi, testInfo }) => {
  sondeFausse('C-AERR-034')
  const r = context.request
  const m = marque()
  const di = await compteRole('aerr65di', 'Directeur')
  const ids = await py(`from apps.ged.models import Cabinet, Folder, Document
from apps.ged import services
di = U.objects.get(pk=${di.id})
cab = Cabinet.objects.create(company_id=${SOC}, nom='AERR65 ${m}')
fol = Folder.objects.create(company_id=${SOC}, cabinet=cab, nom='Dossier AERR65 ${m}')
da = Document.objects.create(company_id=${SOC}, folder=fol, nom='Contrat AERR65 A ${m}.pdf')
db = Document.objects.create(company_id=${SOC}, folder=fol, nom='Contrat AERR65 B ${m}.pdf')
sa = services.demander_signature(da, signataire_nom='Client A', signataire_email='a-${m}@example.invalid', company=da.company, created_by=di, notifier=False)
sb = services.demander_signature(db, signataire_nom='Client B', signataire_email='b-${m}@example.invalid', company=db.company, created_by=di, notifier=False)
sortie(dict(cab=cab.pk, a=sa.pk, b=sb.pk))`)
  const tag = await lireJson(await r.post(`${API}/ged/tags/`, { ...T, data: { nom: `Tag AERR65 ${m}` } }), 'tag')
  apres.push(() => py(`from apps.ged.models import Cabinet, DemandeSignatureDocument
for f in (lambda: DemandeSignatureDocument.objects.filter(pk__in=[${ids.a}, ${ids.b}]).delete(), lambda: Cabinet.objects.filter(pk=${ids.cab}).delete()):
    try: f()
    except Exception as exc: print('nettoyage', exc)`))
  apres.push(async () => { await r.delete(`${API}/ged/tags/${tag.id}/`, T) })
  const statuts = () => py(`from apps.ged.models import DemandeSignatureDocument as D
sortie([D.objects.get(pk=${ids.a}).statut, D.objects.get(pk=${ids.b}).statut])`)
  const p = await ecran(page, suivi, testInfo, di.nom)
  const signe = compteur(p, new RegExp(`/ged/demandes-signature/${ids.a}/marquer-signe/$`), 'POST')
  const annule = compteur(p, new RegExp(`/ged/demandes-signature/${ids.b}/annuler/$`), 'POST')
  const supTag = compteur(p, new RegExp(`/ged/tags/${tag.id}/$`), 'DELETE')
  const boite = p.getByRole('alertdialog')
  const ligne = (x) => p.getByRole('row').filter({ hasText: `Contrat AERR65 ${x} ${m}.pdf` })
  const action = async (x, libelle) => {
    await ligne(x).getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
    await p.getByRole('menuitem', { name: libelle }).click()
  }
  const ouvrirSignatures = async () => {
    await p.goto('/ged/approbation')
    await p.getByRole('tab', { name: 'Signatures' }).click({ timeout: 60_000 })
    await p.getByLabel('Recherche globale').first().fill(`AERR65`)
    await expect(ligne('A')).toBeVisible({ timeout: 60_000 })
    await expect(ligne('B')).toBeVisible()
  }
  await ouvrirSignatures()
  // « Marquer comme signée » puis « Annuler » : aucune requête, la boîte nomme le document.
  await action('A', 'Marquer comme signée')
  await expect(boite).toContainText('Marquer la demande comme signée ?', { timeout: 15_000 })
  await expect(boite, 'la boîte nomme le document').toContainText(`Contrat AERR65 A ${m}.pdf`)
  await cliche(p, 'PF12.4-AERR65', 'marquer-signee-boite')
  await boite.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(boite).toHaveCount(0)
  // « Annuler la demande » puis « Garder » : aucune requête, la boîte nomme le document.
  await action('B', 'Annuler la demande')
  await expect(boite).toContainText('Annuler la demande de signature ?', { timeout: 15_000 })
  await expect(boite).toContainText(`Contrat AERR65 B ${m}.pdf`)
  await cliche(p, 'PF12.4-AERR65', 'annuler-demande-boite')
  await boite.getByRole('button', { name: 'Garder', exact: true }).click()
  await expect(boite).toHaveCount(0)
  expect([signe.n, annule.n], 'aucun appel marquer-signé / annuler').toEqual([0, 0])
  expect(await statuts(), 'en base : les deux demandes restent en attente').toEqual(['en_attente', 'en_attente'])
  // Tag : « Supprimer » puis « Annuler » ⇒ aucun DELETE, la boîte nomme le tag.
  await p.goto('/ged/tags')
  await p.getByLabel('Recherche globale').first().fill(`Tag AERR65 ${m}`)
  const ligneTag = p.getByRole('row').filter({ hasText: `Tag AERR65 ${m}` }).first()
  await expect(ligneTag).toBeVisible({ timeout: 60_000 })
  await ligneTag.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await p.getByRole('menuitem', { name: 'Supprimer' }).click()
  await expect(boite).toContainText('Supprimer ce tag ?', { timeout: 15_000 })
  await expect(boite, 'la boîte nomme le tag').toContainText(`« Tag AERR65 ${m} »`)
  await cliche(p, 'PF12.4-AERR65', 'tag-boite')
  await boite.getByRole('button', { name: 'Annuler', exact: true }).click()
  expect(supTag.n, 'tag : aucun DELETE').toBe(0)
  expect((await r.get(`${API}/ged/tags/${tag.id}/`, T)).status(), 'en base : le tag existe').toBe(200)
  // Persistance : recharger ⇒ statuts et objets inchangés ; « Marquer comme signée » confirmé ⇒ UN appel, statut signé.
  await ouvrirSignatures()
  await p.reload()
  await p.getByRole('tab', { name: 'Signatures' }).click({ timeout: 60_000 })
  await p.getByLabel('Recherche globale').first().fill(`AERR65`)
  await expect(ligne('A'), 'après rechargement : A toujours là').toBeVisible({ timeout: 60_000 })
  await action('A', 'Marquer comme signée')
  await expect(boite).toContainText(`Contrat AERR65 A ${m}.pdf`, { timeout: 15_000 })
  await boite.getByRole('button', { name: 'Marquer comme signée', exact: true }).click()
  await expect(toast(p, 'Signature enregistrée.')).toBeVisible({ timeout: 30_000 })
  expect(signe.n, 'confirmé : exactement un appel').toBe(1)
  expect(await statuts(), 'en base : A signée, B toujours en attente').toEqual(['signe', 'en_attente'])
  // Fin d'étape sur une boîte nommée (B, Annuler la demande).
  await action('B', 'Annuler la demande')
  await expect(boite).toContainText(`Contrat AERR65 B ${m}.pdf`, { timeout: 15_000 })
})

// ═══ PF12.3 — AERR128 : portail client → SAV, relecture rejetée après l'envoi ⇒ message, formulaire et liste gardés ═══
etape('PF12.3-AERR128', ['AERR128'], async ({ page, context, suivi, testInfo }) => {
  const r = context.request
  const m = marque()
  const v = await devisEnvoye(r, r, m, 'AERR128')
  apres.push(() => nettoyerVente(v))
  const existants = listeDe(await lireJson(await r.get(`${API}/portail/comptes-portail/`, T), 'comptes portail'))
  const comptePortail = existants.find((c) => c.client === v.client)
    ?? await lireJson(await r.post(`${API}/portail/comptes-portail/`, { ...T, data: { client: v.client } }), 'compte portail')
  const prov = await lireJson(await r.post(`${API}/portail/comptes-portail/${comptePortail.id}/provisionner-acces/`, { ...T, data: {} }), 'accès portail')
  await py(`u = U.objects.get(username=${J(prov.username)})
u.set_password(${J(MDP_ESSAI)}); u.must_change_password = False; u.failed_login_count = 0; u.locked_until = None; u.is_active = True; u.save()`)
  comptes.push(prov.username)
  const p = await ecran(page, suivi, testInfo, prov.username)
  const creees = []
  for (const k of [1, 2]) {
    const d = await lireJson(await p.request.post(`${API}/portail/mes-demandes-sav/`, { ...T, data: { sujet: `AERR128 ancienne ${k} ${m}`, description: 'Onduleur en défaut.' } }), `demande ${k}`)
    creees.push(d.id)
  }
  apres.push(() => py(`from apps.portail.models import DemandeTicketPortail
DemandeTicketPortail.objects.filter(sujet__contains=${J(m)}).delete()`))
  const mesDemandes = async () => listeDe(await lireJson(await p.request.get(`${API}/portail/mes-demandes-sav/`, T), 'mes demandes'))
    .filter((d) => String(d.sujet).includes(m))
  const LISTE = /\/api\/django\/portail\/mes-demandes-sav\/(\?|$)/
  const anciennes = p.getByText(new RegExp(`AERR128 ancienne [12] ${m}`))
  await p.goto('/portail/client/sav')
  await expect(anciennes, 'avant : 2 demandes listées').toHaveCount(2, { timeout: 60_000 })
  let coupure = await panne(p, suivi, LISTE)
  await p.getByLabel('Sujet').fill(`AERR128 nouvelle ${m}`)
  await p.getByLabel('Description').fill('Production nulle depuis hier.')
  await p.getByRole('button', { name: 'Envoyer la demande' }).click()
  await expect(p.getByRole('status').filter({ hasText: 'Demande envoyée.' }), '« Demande envoyée… » reste affiché').toBeVisible({ timeout: 30_000 })
  await expect.poll(() => coupure.hits.n, { message: 'la relecture après l\'envoi a échoué', timeout: 30_000 }).toBeGreaterThan(0)
  await expect(p.getByRole('status').filter({ hasText: 'Liste pas à jour' }), 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(p.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(anciennes, 'les 2 demandes déjà listées restent').toHaveCount(2)
  await expect(p.getByRole('button', { name: 'Envoyer la demande' }), 'le formulaire reste').toBeVisible()
  await expect(p.getByText('Demandes indisponibles'), 'jamais « Demandes indisponibles » après l\'envoi').toHaveCount(0)
  await cliche(p, 'PF12.3-AERR128', 'relecture-rejetee')
  expect((await mesDemandes()).length, 'API : une seule demande créée (3 au total)').toBe(3)
  // Réessayer (API rétablie) ⇒ la nouvelle demande apparaît ; recharger ⇒ 3.
  await coupure.lever()
  await p.getByRole('button', { name: 'Réessayer' }).click()
  await expect(p.getByText(`AERR128 nouvelle ${m}`)).toBeVisible({ timeout: 30_000 })
  await p.reload()
  await expect(p.getByText(new RegExp(`AERR128 (ancienne [12]|nouvelle) ${m}`)), 'après rechargement : 3 demandes').toHaveCount(3, { timeout: 60_000 })
  // Acceptation de devis refusée (sans champ) ⇒ UNE seule notification.
  const detail = `Acceptation refusée par le serveur (rejeu AERR128 ${m}).`
  coupure = await panne(p, suivi, new RegExp(`/api/django/portail/mes-devis/${v.id}/accepter/$`), { statut: 409, methode: 'POST', corps: { detail } })
  await p.goto('/portail/client/devis')
  await expect(p.getByText(v.reference).first()).toBeVisible({ timeout: 60_000 })
  await p.getByRole('button', { name: 'Accepter', exact: true }).click()
  const dlg = p.getByRole('dialog').filter({ hasText: `Accepter le devis ${v.reference}` })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#portail-signataire').fill('Client AERR128')
  await dlg.getByRole('checkbox').first().click()
  const confirmer = dlg.getByRole('button', { name: 'Confirmer l’acceptation' })
  await confirmer.click()
  await expect(toast(p, detail), 'le refus est dit').toBeVisible({ timeout: 30_000 })
  await expect(confirmer, 'la requête est terminée (bouton rendu)').toBeEnabled({ timeout: 30_000 })
  await expect(toast(p, detail), 'une seule notification pour ce refus').toHaveCount(1)
  expect(coupure.hits.n).toBe(1)
  await cliche(p, 'PF12.3-AERR128', 'acceptation-refusee')
  expect((await lireJson(await r.get(`${API}/ventes/devis/${v.id}/`, T), 'devis')).statut, 'en base : le devis reste envoyé').toBe('envoye')
  await coupure.lever()
  // Fin d'étape sur l'écran SAV affirmé : nouvel envoi sous relecture coupée.
  coupure = await panne(p, suivi, LISTE)
  await p.goto('/portail/client/sav')
  await expect(p.getByText('Demandes indisponibles'), 'premier chargement rejeté : état d\'erreur conservé').toBeVisible({ timeout: 60_000 })
  await coupure.lever()
  await p.reload()
  await expect(p.getByText(new RegExp(`AERR128 (ancienne [12]|nouvelle) ${m}`))).toHaveCount(3, { timeout: 60_000 })
  coupure = await panne(p, suivi, LISTE)
  await p.getByLabel('Sujet').fill(`AERR128 suivante ${m}`)
  await p.getByRole('button', { name: 'Envoyer la demande' }).click()
  await expect(p.getByRole('status').filter({ hasText: 'Demande envoyée.' })).toBeVisible({ timeout: 30_000 })
  await expect(p.getByRole('status').filter({ hasText: 'Liste pas à jour' })).toBeVisible({ timeout: 30_000 })
  await expect(p.getByText(new RegExp(`AERR128 (ancienne [12]|nouvelle) ${m}`)), 'après rechargement : les 3 restent').toHaveCount(3)
})

// ═══ PF12.3 — AERR121 : accueil mobile commercial (375 px), relances et agenda coupés ⇒ avis + Réessayer, jamais « Rien d'urgent » ═══
etapeDefaut('PF12.3-AERR121', ['AERR121'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-092')
  const m = marque()
  const co = await compteRole('aerr121co', 'Commercial')
  const nomLead = `AERR121 ${m}`
  const lead = await py(`from apps.crm.models import Lead
l = Lead.objects.create(company_id=${SOC}, nom=${J(nomLead)}, telephone='${telephoneMobileUnique()}', owner_id=${co.id}, stage='NEW')
Lead.objects.filter(pk=l.pk).update(relance_date=timezone.localdate())
sortie(l.pk)`)
  apres.push(() => py(`from apps.crm.models import Lead
Lead.all_objects.filter(pk=${lead}).delete()`))
  const MOBILE = { width: 375, height: 812 }
  const p = await ecran(page, suivi, testInfo, co.nom, { viewport: MOBILE })
  const RELANCES = /\/api\/django\/crm\/leads\/relances\/(\?|$)/
  const AGENDA = /\/api\/django\/reporting\/calendar\/(\?|$)/
  const avis = p.getByRole('status').filter({ hasText: 'Une partie de la journée n\'a pas pu être lue.' })
  const lectureImpossible = p.getByText('Lecture impossible', { exact: true })
  const affirmerPanne = async (quand) => {
    await expect(avis, `${quand} : avis de lecture incomplète`).toBeVisible({ timeout: 60_000 })
    await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
    await expect(p.getByText('Rien d\'urgent aujourd\'hui'), `${quand} : jamais « Rien d'urgent »`).toHaveCount(0)
    await expect(lectureImpossible, `${quand} : état d'erreur à la place des deux listes`).toHaveCount(2, { timeout: 30_000 })
    await expect(p.getByText('Aucune relance due aujourd\'hui')).toHaveCount(0)
    await expect(p.getByText('Aucun rendez-vous aujourd\'hui')).toHaveCount(0)
  }
  let c1 = await panne(p, suivi, RELANCES)
  let c2 = await panne(p, suivi, AGENDA)
  await p.goto('/mobile/commercial')
  await affirmerPanne('lecture coupée')
  await cliche(p, 'PF12.3-AERR121', 'accueil-commercial-coupe')
  // Réessayer (API rétablie) ⇒ la relance du jour s'affiche dans le widget et dans « Mes leads du jour ».
  await c1.lever()
  await c2.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis).toHaveCount(0, { timeout: 30_000 })
  await expect(p.locator('[data-widget="a-faire-aujourdhui"]').getByText(nomLead), 'widget relu : la relance du jour').toBeVisible({ timeout: 30_000 })
  await p.getByRole('button', { name: 'Réessayer' }).first().click()
  await expect(lectureImpossible).toHaveCount(0, { timeout: 30_000 })
  await expect(p.getByText(nomLead), 'widget ET « Mes leads du jour » relus : la relance deux fois').toHaveCount(2, { timeout: 30_000 })
  // Accueil d'équipe (Commercial responsable) : relances coupées ⇒ « Lecture impossible », jamais « Aucune relance en retard ».
  const cr = await compteRole('aerr121cr', 'Commercial responsable')
  const q = await ecran(page, suivi, testInfo, cr.nom, { viewport: MOBILE })
  const c3 = await panne(q, suivi, RELANCES)
  await q.goto('/mobile/equipe-commerciale')
  await q.getByRole('radio', { name: 'Équipe' }).click({ timeout: 60_000 })
  await expect(q.getByText('Lecture impossible', { exact: true }), 'équipe : état d\'erreur').toBeVisible({ timeout: 30_000 })
  await expect(q.getByText('Aucune relance en retard dans l\'équipe')).toHaveCount(0)
  await cliche(q, 'PF12.3-AERR121', 'accueil-equipe-coupe')
  await c3.lever()
  await q.close()
  // Persistance : recharger l'accueil sous coupure ⇒ même avis (fin d'étape sur l'écran affirmé).
  c1 = await panne(p, suivi, RELANCES)
  c2 = await panne(p, suivi, AGENDA)
  await p.reload()
  await affirmerPanne('après rechargement')
})

// ═══ PF12.3 — AERR59 : Approbations, relecture rejetée après une décision ⇒ les 2 autres demandes restent + avis + Réessayer ═══
etape('PF12.3-AERR59', ['AERR59'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-029')
  const m = marque()
  const ids = await py(`from apps.automation.models import AutomationApproval
dem = U.objects.get(username='demo_admin')
sortie([AutomationApproval.objects.create(company_id=${SOC}, description='AERR59 ${m} n%d' % k, requested_by=dem).pk for k in (1, 2, 3)])`)
  apres.push(() => py(`from apps.automation.models import AutomationApproval
AutomationApproval.objects.filter(pk__in=${J(ids)}).delete()`))
  const etats = () => py(`from apps.automation.models import AutomationApproval as A
sortie([A.objects.get(pk=pk).status for pk in ${J(ids)}])`)
  const di = await compteRole('aerr59di', 'Directeur')
  const p = await ecran(page, suivi, testInfo, di.nom)
  const LISTE = /\/api\/django\/reporting\/approbations-en-attente\/(\?|$)/
  const ligne = (k) => p.getByRole('row').filter({ hasText: `AERR59 ${m} n${k}` })
  const avis = p.getByTestId('approbations-pas-a-jour')
  const filtrer = async () => {
    await p.getByLabel('Recherche globale').first().fill(`AERR59 ${m}`)
  }
  await p.goto('/approbations')
  await filtrer()
  for (const k of [1, 2, 3]) await expect(ligne(k), `demande ${k} listée`).toBeVisible({ timeout: 60_000 })
  let coupure = await panne(p, suivi, LISTE)
  await ligne(1).getByTestId(`approbation-approve-automation-${ids[0]}`).click()
  await expect(toast(p, 'Demande approuvée.')).toBeVisible({ timeout: 30_000 })
  await expect.poll(() => coupure.hits.n, { message: 'la relecture après décision a échoué', timeout: 30_000 }).toBeGreaterThan(0)
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await filtrer()
  await expect(ligne(2), 'demande 2 gardée').toBeVisible()
  await expect(ligne(3), 'demande 3 gardée').toBeVisible()
  await expect(ligne(1), 'la ligne décidée est retirée').toHaveCount(0)
  await expect(p.getByText('Aucune demande en attente'), 'jamais « Aucune demande en attente »').toHaveCount(0)
  await expect(toast(p, 'Chargement des approbations impossible'), 'aucun toast local en double').toHaveCount(0)
  await cliche(p, 'PF12.3-AERR59', 'relecture-rejetee')
  expect(await etats(), 'en base : 1 approuvée, 2 en attente').toEqual(['approved', 'pending', 'pending'])
  // Réessayer (API rétablie) ⇒ avis levé, 2 et 3 listées.
  await coupure.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis).toHaveCount(0, { timeout: 30_000 })
  await filtrer()
  await expect(ligne(2)).toBeVisible({ timeout: 30_000 })
  await expect(ligne(3)).toBeVisible()
  // Persistance : recharger ⇒ 2 et 3, pas 1 ; puis nouvelle décision sous coupure ⇒ même rendu (fin sur l'écran affirmé).
  await p.reload()
  await filtrer()
  await expect(ligne(2)).toBeVisible({ timeout: 60_000 })
  await expect(ligne(1)).toHaveCount(0)
  coupure = await panne(p, suivi, LISTE)
  await ligne(2).getByTestId(`approbation-approve-automation-${ids[1]}`).click()
  await expect(avis).toBeVisible({ timeout: 30_000 })
  await filtrer()
  await expect(ligne(3), 'après rechargement : la demande restante est gardée').toBeVisible()
  await expect(p.getByText('Aucune demande en attente')).toHaveCount(0)
  expect(await etats()).toEqual(['approved', 'approved', 'pending'])
})

// ═══ PF12.5 — AERR125 : délégation d'un seul jour ⇒ fin à 23:59:59.999 locale, « Active » ; refus date_fin nommé sous la période ═══
etapeDefaut('PF12.5-AERR125', ['AERR125'], async ({ page, suivi, testInfo }) => {
  const ad = await compteRole('aerr125ad', 'Administrateur')
  const sup = await compteRole('aerr125su', 'Commercial')
  apres.push(() => py(`from apps.automation.models import ApprovalDelegation
ApprovalDelegation.objects.filter(delegant_id=${ad.id}).delete()`))
  const p = await ecran(page, suivi, testInfo, ad.nom)
  const CREER = /\/api\/django\/automation\/approval-delegations\/$/
  const periode = p.locator('#delegation-periode')
  const ouvrirOnglet = async () => {
    await p.goto('/approbations')
    await p.getByRole('tab', { name: 'Délégations' }).click({ timeout: 60_000 })
    await expect(periode).toBeVisible({ timeout: 30_000 })
  }
  const choisir = async () => {
    await p.locator('#delegation-suppleant').click()
    await p.getByRole('option', { name: sup.nom, exact: true }).click()
    await periode.click()
    const jour = p.locator('[role="gridcell"][aria-current="date"]')
    await jour.click()
    await jour.click()
    await expect(periode, 'période d\'un seul jour choisie').toContainText('→')
  }
  const ligneActive = p.locator('li').filter({ hasText: sup.nom }).filter({ hasText: 'Active' })
  const attendu = await p.evaluate(() => {
    const d = new Date(); d.setHours(0, 0, 0, 0)
    const f = new Date(); f.setHours(23, 59, 59, 999)
    return [d.toISOString(), f.toISOString()]
  })
  await ouvrirOnglet()
  // 1) Refus 400 {date_fin} servi (injecté) ⇒ message SOUS le sélecteur de période, saisie gardée, rien créé.
  const motif = 'La date de fin est refusée (rejeu AERR125).'
  const refus = await panne(p, suivi, CREER, { statut: 400, methode: 'POST', corps: { date_fin: [motif] } })
  await choisir()
  const [reqRefus] = await Promise.all([
    p.waitForRequest((q) => q.method() === 'POST' && CREER.test(q.url())),
    p.getByRole('button', { name: 'Déléguer' }).click(),
  ])
  const corpsRefus = reqRefus.postDataJSON()
  expect([corpsRefus.date_debut, corpsRefus.date_fin], 'un seul jour : début 00:00 et fin 23:59:59.999 locales').toEqual(attendu)
  // Erreur du FormField « Période » (`<id>-error`) ; le toast global dit aussi « Date fin : <motif> » (AERR52).
  await expect(p.locator('#delegation-periode-error'), 'le refus est rendu sous la période').toContainText(motif, { timeout: 30_000 })
  await expect(periode, 'saisie de la période conservée').toContainText('→')
  expect(refus.hits.n).toBe(1)
  await cliche(p, 'PF12.5-AERR125', 'refus-date-fin')
  await refus.lever()
  // 2) Création RÉELLE (serveur) avec la même saisie ⇒ attendu 201, délégation « Active ».
  const [req] = await Promise.all([
    p.waitForRequest((q) => q.method() === 'POST' && CREER.test(q.url())),
    p.getByRole('button', { name: 'Déléguer' }).click(),
  ])
  const corps = req.postDataJSON()
  expect([corps.date_debut, corps.date_fin], 'création réelle : mêmes bornes').toEqual(attendu)
  const rep = await req.response()
  const texteRep = await rep.text()
  console.log(`[AERR125] création réelle : HTTP ${rep.status()} ${texteRep.slice(0, 400)} ; corps envoyé ${J(corps)}`)
  await cliche(p, 'PF12.5-AERR125', 'creation-reelle')
  expect(rep.status(), `création réelle refusée par le serveur : ${texteRep.slice(0, 300)} (corps envoyé ${J(corps)})`).toBe(201)
  await expect(toast(p, 'Délégation créée.')).toBeVisible({ timeout: 30_000 })
  await expect(ligneActive, 'la délégation est listée « Active » (en cours)').toBeVisible({ timeout: 30_000 })
  await cliche(p, 'PF12.5-AERR125', 'delegation-active')
  const base = await py(`from apps.automation.models import ApprovalDelegation
n = timezone.now()
sortie([dict(debut=d.date_debut.timestamp() * 1000, fin=d.date_fin.timestamp() * 1000, active=d.date_debut <= n <= d.date_fin) for d in ApprovalDelegation.objects.filter(delegant_id=${ad.id})])`)
  expect(base.length, 'en base : une délégation').toBe(1)
  expect([Math.round(base[0].debut), Math.round(base[0].fin)], 'en base : bornes envoyées').toEqual([Date.parse(attendu[0]), Date.parse(attendu[1])])
  expect(base[0].active, 'en base : en cours maintenant').toBe(true)
  // Persistance : recharger l'onglet ⇒ toujours « Active ».
  await p.reload()
  await p.getByRole('tab', { name: 'Délégations' }).click({ timeout: 60_000 })
  await expect(ligneActive, 'après rechargement : « Active »').toBeVisible({ timeout: 30_000 })
})

// ═══ PF12.3 — AERR130 : /reporting/classeurs, suppression puis relecture coupée ⇒ le classeur restant reste + avis ═══
etapeDefaut('PF12.3-AERR130-classeurs', ['AERR130'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ad = await compteRole('aerr130ad', 'Administrateur')
  const p = await ecran(page, suivi, testInfo, ad.nom)
  const cls = []
  for (const x of ['A', 'B']) cls.push(await lireJson(await p.request.post(`${API}/reporting/classeurs/`, { ...T, data: { titre: `Classeur AERR130 ${x} ${m}`, cellules: {}, liens: {} } }), `classeur ${x}`))
  apres.push(() => py(`from apps.reporting.models import Classeur
Classeur.objects.filter(titre__contains=${J(m)}).delete()`))
  const LISTE = /\/api\/django\/reporting\/classeurs\/(\?|$)/
  const ligne = (x) => p.getByRole('row').filter({ hasText: `Classeur AERR130 ${x} ${m}` })
  const avis = p.getByRole('status').filter({ hasText: 'Liste pas à jour' })
  await p.goto('/reporting/classeurs')
  await expect(ligne('A')).toBeVisible({ timeout: 60_000 })
  await expect(ligne('B')).toBeVisible()
  let coupure = await panne(p, suivi, LISTE)
  await ligne('A').getByRole('button', { name: 'Supprimer' }).click()
  const boite = p.getByRole('alertdialog')
  await expect(boite).toContainText(`Classeur AERR130 A ${m}`, { timeout: 15_000 })
  await boite.getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect(toast(p, 'Classeur supprimé.')).toBeVisible({ timeout: 30_000 })
  await expect(p, 'on reste sur la liste des classeurs').toHaveURL(/\/reporting\/classeurs$/)
  await expect.poll(() => coupure.hits.n, { message: 'la relecture après suppression a échoué', timeout: 30_000 }).toBeGreaterThan(0)
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(ligne('B'), 'le classeur restant est toujours listé').toBeVisible()
  await expect(ligne('A'), 'la ligne supprimée est retirée localement').toHaveCount(0)
  await expect(p.getByText('Aucun classeur', { exact: true }), 'jamais « Aucun classeur »').toHaveCount(0)
  await cliche(p, 'PF12.3-AERR130-classeurs', 'relecture-coupee')
  const restants = (await lignes(p.request, `${API}/reporting/classeurs/`)).map((c) => c.id)
  expect([restants.includes(cls[0].id), restants.includes(cls[1].id)], 'en base : A supprimé, B présent').toEqual([false, true])
  await coupure.lever()
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis).toHaveCount(0, { timeout: 30_000 })
  await expect(ligne('B')).toBeVisible()
  // Persistance : recharger sous coupure ⇒ avis + Réessayer, jamais « Aucun classeur ».
  coupure = await panne(p, suivi, LISTE)
  await p.reload()
  await expect(avis, 'premier chargement rejeté : avis').toBeVisible({ timeout: 60_000 })
  await expect(p.getByText('Aucun classeur', { exact: true })).toHaveCount(0)
})

// ═══ PF12.3 — AERR130 (même règle, « Aucune configuration ») : /reporting/dashboards, suppression puis relecture coupée ═══
etapeDefaut('PF12.3-AERR130-configurations', ['AERR130'], async ({ page, suivi, testInfo }) => {
  const ad = await compteRole('aerr130cf', 'Administrateur')
  const u1 = await compteRole('aerr130u1', 'Commercial')
  const u2 = await compteRole('aerr130u2', 'Commercial')
  const p = await ecran(page, suivi, testInfo, ad.nom)
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
  await expect(toast(p, 'Configuration supprimée.')).toBeVisible({ timeout: 30_000 })
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
