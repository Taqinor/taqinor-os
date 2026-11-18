// aerr13 : preuves en direct ÉCRAN du groupe AERR, lot 13 (acceptation du 18/11/2026) des trois tâches dont le code est livré sur
// dev-all depuis le 13/11 et dont la preuve en direct restait due : AERR4 (Ventes → Relances), AERR100 (/crm/leads, fiche ouverte),
// AERR102 (fiche lead → « Appeler »). Chaque étape rejoue la sonde nommée (repro False exigé), provoque la panne par une route
// Playwright déclarée AVANT par `suivi.attendre` et posée APRÈS le premier chargement de l'écran, affirme les textes de la clause,
// rétablit la route, clique « Réessayer » et affirme la reprise, puis recharge. Données propres, retirées en fin d'étape.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('AERR', ['AERR4', 'AERR100', 'AERR102'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const ouverts = []
const apres = []
test.afterEach(async () => {
  for (const c of ouverts.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const PANNE = { status: 500, contentType: 'application/json', body: J({ detail: 'Panne simulée (acceptation AERR).' }) }

/** Rejoue une sonde HÔTE (`docs/audits/sondes/AERR/<c>.py`, sans Django ni base) ; {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AERR', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
function sondeFausse(constat) {
  const s = sondeHote(constat)
  expect(s.ok, `sonde ${constat} exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde ${constat} : ${J(s.res.observe)}`).toBe(false)
}
/** Compte d'essai du rôle LIVRÉ `nomRole` de la société démo ; {id, porte: encaisser ?}. */
const compteDuRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
sortie({'id': u.id, 'porte': 'encaisser' in (r.permissions or []), 'systeme': r.est_systeme})`)

/** Écran sous le compte `nom` : contexte neuf (accueil et visites vus, SW bloqué), observé ; la page demo_admin est
 *  refermée (la capture montre l'écran du rôle). `api` = requêtes de CE compte (même jarre de cookies). */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.viewport ? { viewport: u.viewport } : {}),
  })
  ouverts.push(ctx)
  // Pré-chargement matinal de la tournée (NTMOB28, `PrechargementTournee.jsx`, monté par Layout sur tout écran avant
  // midi) marqué « fait aujourd'hui » : pour un rôle sans lecture des interventions il appelle `ma-tournee` en 403
  // (défaut antérieur, hors des Files des tâches AERR, rapporté à part) — il n'est pas l'objet de ces étapes.
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

/** Lead + produit + devis (porté par `cree`) ; `envoye` ⇒ lien client émis (vraie route share-link). */
async function devisDe(cree, admin, m, { ci = false, envoye = false, ht = '10000.00' } = {}) {
  const l = await lireJson(await cree.post(`${API}/crm/leads/`, { ...T, data: {
    nom: `AERR ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `aerr-${m}@example.invalid`, 
  } }), 'lead')
  const p = await lireJson(await admin.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation AERR ${m}`, prix_vente: ht, prix_achat: '1.00' } }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, { ...T, data: {
    taux_tva: '20.00', remise_globale: '0', lead: l.id, ...(ci ? { mode_installation: 'commercial' } : {}),
    lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: ht, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
  } }), 'devis')
  if (envoye) await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const relu = await lireJson(await cree.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  return { id: d.id, reference: relu.reference, statut: relu.statut, leadId: l.id }
}
/** Vente acceptée (demo_admin) puis facturée « complete » par `cree` (créateur = le rôle joué) ; 10 000 HT = 12 000 TTC.
 *  L'acceptation pose un acompte automatique BROUILLON (référence provisoire) : il est remplacé (`remplacer_brouillons`). */
async function factureDe(cree, admin, m, { emettre }) {
  const d = await devisDe(cree, admin, m, { envoye: true })
  await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AERR' } }), 'accepter')
  const rep = await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'complete', emettre, remplacer_brouillons: true } }), 'facturer')
  return { id: rep.facture.id, reference: rep.facture.reference, statut: rep.facture.statut, ttc: Number(rep.facture.total_ttc) }
}

/** Route tenue : chaque requête qui passe attend `lacher()`, puis `issue(route)` (abort par défaut). */
function porte() {
  let lacher
  let signaler
  const ouverte = new Promise((r) => { lacher = r })
  const arrivee = new Promise((r) => { signaler = r })
  return {
    arrivee, lacher: () => lacher(),
    gestion: (issue = (route) => route.abort('failed')) => async (route) => { signaler(); await ouverte; await issue(route) },
  }
}
/** Compteur de requêtes (méthode + chemin) observées par la page. */
function compteur(p, methode, cheminOk) {
  const c = { n: 0, corps: [], urls: [] }
  p.on('request', (r) => {
    if (r.method() !== methode) return
    const u = new URL(r.url())
    if (!cheminOk(u.pathname, u)) return
    c.n += 1
    c.urls.push(`${u.pathname}${u.search}`)
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
/** Étape de relance (RelanceEtape) due aujourd'hui sur le lead. */
const creerEtapes = (lead, etapes) => py(`from apps.crm.models import RelanceEtape, Lead
l = Lead.objects.get(pk=${lead})
out = []
for i, d in enumerate(json.loads(${J(J(etapes))})):
    out.append(RelanceEtape.objects.create(company_id=l.company_id, lead=l, ordre=i + 1, due_at=timezone.now(),
        due_date=timezone.localdate(), **d).pk)
sortie(out)`)

/** Coupe les GET dont le chemin vérifie `cheminOk` (500 JSON) ; les autres méthodes passent. */
async function couperLecture(p, cheminOk) {
  const filtre = (u) => cheminOk(u.pathname, u)
  await p.route(filtre, (route) => (route.request().method() === 'GET' ? route.fulfill(PANNE) : route.fallback()))
  return () => p.unroute(filtre)
}
// ═══ AERR4 ═══
etape('PF-AERR4-relances-lecture-ratee', ['AERR4'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-004')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr4co_${m}`
  expect((await compteDuRole(nom, 'Commercial')).porte).toBe(true)
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const fs = [await factureDe(api, admin, `${m}a`, { emettre: true }), await factureDe(api, admin, `${m}b`, { emettre: true })]
  const file = await lireJson(await api.get(`${API}/ventes/relances/`, T), 'file servie')
  expect(fs.every((f) => file.some((r) => r.id === f.id)), 'Given : les 2 impayées sont dans « Toutes »').toBe(true)
  expect((await lireJson(await api.get(`${API}/ventes/relances/?mes_relances=1`, T), 'mes relances')).length, '« Mes relances » servie vide').toBe(0)
  const table = p.getByRole('table', { name: 'Factures à relancer' })
  const ligne = (f) => table.getByRole('row').filter({ hasText: f.reference })
  const FESTIF = 'Aucune facture impayée'
  const TOUTES = /\/api\/django\/ventes\/relances\/$/
  const MES = /\/api\/django\/ventes\/relances\/\?mes_relances=1/

  // Lecture rejetée au chargement : erreur + Réessayer, jamais l'état festif.
  suivi.attendre(TOUTES, 'reseau')
  await p.route(TOUTES, (route) => route.abort('failed'))
  await p.goto('/ventes/relances')
  const erreur = p.getByTestId('relances-erreur')
  await expect(erreur, 'erreur de lecture affichée').toBeVisible({ timeout: 60_000 })
  await expect(erreur).toContainText('Impossible de charger la file de relances.')
  await expect(erreur.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(p.getByText(FESTIF), 'jamais « Aucune facture impayée » sur une panne').toHaveCount(0)
  await p.unroute(TOUTES)
  await erreur.getByRole('button', { name: 'Réessayer' }).click()
  for (const f of fs) await expect(ligne(f), `Réessayer : ${f.reference}`).toBeVisible({ timeout: 60_000 })
  await expect(erreur).toBeHidden()

  // Deux bascules : « Mes relances » (réponse TENUE, arrive en dernier) puis « Toutes ».
  const g = porte()
  await p.route(MES, g.gestion((route) => route.continue()))
  const choisir = async (libelle) => {
    await p.getByRole('combobox', { name: 'Filtrer la file de relance' }).click()
    await p.getByRole('option', { name: libelle, exact: true }).click()
  }
  await choisir('Mes relances')
  await g.arrivee
  for (const f of fs) await expect(ligne(f), `relecture EN COURS : ${f.reference} reste affichée`).toBeVisible()
  const toutes = p.waitForResponse((x) => TOUTES.test(x.url()), T)
  await choisir('Toutes les factures')
  expect((await toutes).status()).toBe(200)
  const tardive = p.waitForResponse((x) => MES.test(x.url()), T)
  g.lacher()
  const rtardive = await tardive
  expect(rtardive.status(), 'la réponse « Mes relances » arrive en dernier').toBe(200)
  // Déterministe : la réponse tardive doit avoir été LIVRÉE ET TRAITÉE par la page avant de vérifier (sinon l'étape
  // passerait sans la garde d'ordre). Corps reçu, réseau calme, puis deux images rendues + un tour de boucle : les
  // `.then` d'axios et le rendu React qui en découle sont passés.
  expect(await rtardive.json(), 'la réponse tardive est bien « Mes relances » : vide').toEqual([])
  await p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
  await p.evaluate(() => new Promise((fin) => {
    requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(fin, 0)))
  }))
  await expect(p.getByRole('combobox', { name: 'Filtrer la file de relance' })).toContainText('Toutes les factures')
  for (const f of fs) await expect(ligne(f), `seule la dernière demandée s'affiche : ${f.reference}`).toBeVisible()
  await expect(p.getByText('Aucune relance qui vous soit assignée'), 'la réponse tardive est ignorée').toHaveCount(0)
  await p.unroute(MES)
  // Persistance : recharger ⇒ la file servie.
  await p.reload()
  for (const f of fs) await expect(ligne(f), `rechargé : ${f.reference}`).toBeVisible({ timeout: 60_000 })
  await expect(p.getByText(FESTIF)).toHaveCount(0)
})

// ═══ AERR100 ═══
etape('PF-AERR100-leads-relecture-ratee', ['AERR100'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-044')
  const m = marque()
  const nom = `aerr100_${m}`
  const cr = (await compteDuRole(nom, 'Commercial responsable')).id
  const ids = await creerLeads(cr, ['A', 'B', 'C'].map((x) => ({ nom: `AERR100 ${x} ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' })))
  apres.push(() => supprimerLeads(ids))
  const { p } = await ecran(page, suivi, testInfo, nom)
  const lignes = p.locator('tr.lv-row').filter({ hasText: m })
  const ligneB = lignes.filter({ hasText: `AERR100 B ${m}` })
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  await expect(lignes, 'les 3 leads sont listés').toHaveCount(3, { timeout: 60_000 })
  await ligneB.locator('button.lv-lead-name').click()
  const fiche = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: new RegExp(`AERR100 B ${m}`) }) })
  await expect(fiche, 'la fiche du 2e lead est ouverte').toBeVisible({ timeout: 60_000 })
  // Panne : la relecture de la liste (GET /crm/leads/?page=…) répond 500 — coupée AVANT tout geste.
  suivi.attendre(/\/api\/django\/crm\/leads\/\?/, 500)
  const retablir = await couperLecture(p, (ch) => ch === `${API}/crm/leads/`)
  const avis = p.getByTestId('leads-pas-a-jour')
  // 1) API coupée puis un champ modifié : l'autosauvegarde réussie change sa seule ligne, AUCUNE relecture de la liste.
  const relectures = compteur(p, 'GET', (ch) => ch === `${API}/crm/leads/`)
  // Ville canonique (le serveur normalise la ville saisie : « Fes x » est servie « Fès ») : on tape un nom déjà canonique.
  const ville = 'Rabat'
  const patchVille = p.waitForResponse((r) => r.url().endsWith(`/crm/leads/${ids[1]}/`) && r.request().method() === 'PATCH'
    && (r.request().postData() || '').includes(ville), T)
  const historique = p.waitForResponse((r) => r.url().includes(`/crm/leads/${ids[1]}/historique/`), T)
  await fiche.locator('#lf-ville').fill(ville)
  expect((await patchVille).status(), 'autosauvegarde réussie').toBe(200)
  await historique
  await expect(ligneB, 'la ligne du lead porte la ville enregistrée').toContainText(ville, { timeout: 15_000 })
  expect(relectures.n, `aucune relecture de toute la liste après l'autosauvegarde : ${relectures.urls.join(', ')}`).toBe(0)
  await expect(avis, 'aucune relecture ⇒ aucun avis').toHaveCount(0)
  // 2) Geste qui relit la liste : changement d'étape au clavier (« 2 » → Contacté) ⇒ relecture en 500.
  await fiche.getByRole('heading', { name: new RegExp(`AERR100 B ${m}`) }).click()
  const patchEtape = p.waitForResponse((r) => r.url().endsWith(`/crm/leads/${ids[1]}/`) && r.request().method() === 'PATCH'
    && (r.request().postData() || '').includes('CONTACTED'), T)
  await p.keyboard.press('2')
  expect((await patchEtape).status(), 'changement d\'étape enregistré').toBe(200)
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Liste pas à jour')
  // La fiche est modale (Radix) : la liste derrière est `aria-hidden`, d'où un repérage CSS du bouton.
  const reessayer = avis.locator('button', { hasText: 'Réessayer' })
  await expect(reessayer, 'bouton « Réessayer » de l\'avis').toBeVisible()
  await expect(fiche, 'la fiche reste montée').toBeVisible()
  await expect(lignes, 'les 3 lignes restent').toHaveCount(3)
  await expect(ligneB, 'la ligne garde la ville').toContainText(ville)
  await expect(avis, 'l\'avis reste tant que la relecture n\'a pas réussi').toBeVisible()
  // Réessayer après rétablissement (fiche fermée : la liste redevient cliquable) : l'avis s'efface.
  await fiche.getByRole('button', { name: 'Fermer' }).first().click()
  await expect(fiche).toHaveCount(0)
  await retablir()
  await reessayer.click()
  await expect(avis, 'relecture réussie : avis effacé').toHaveCount(0, { timeout: 30_000 })
  const lu = await py(`from apps.crm.models import Lead
l = Lead.objects.get(pk=${ids[1]}); sortie([l.stage, l.ville])`)
  expect(lu, 'en base : étape et ville du 2e lead').toEqual(['CONTACTED', ville])
  // Persistance : recharger relit le serveur.
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  await expect(lignes, 'après rechargement : 3 lignes').toHaveCount(3, { timeout: 60_000 })
  await expect(ligneB).toContainText(ville)
})

// ═══ AERR102 ═══
etape('PF-AERR102-etapes-lecture-ratee', ['AERR102'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-046')
  const m = marque()
  const nom = `aerr102_${m}`
  const cr = (await compteDuRole(nom, 'Commercial responsable')).id
  const [lead] = await creerLeads(cr, [{ nom: `AERR102 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const libelle = `Appel AERR102 ${m}`
  await creerEtapes(lead, [{ cadence: 'contact', canal: 'appel', libelle }])
  const { p } = await ecran(page, suivi, testInfo, nom)
  const frise = p.waitForResponse((r) => r.url().includes('/crm/relance-etapes/?') && r.url().includes(`lead=${lead}`), T)
  await p.goto(`/crm/leads/${lead}`)
  await frise
  const rail = p.getByTestId('lw-identity-rail')
  await expect(rail).toBeVisible({ timeout: 60_000 })
  suivi.attendre(new RegExp(`/api/django/crm/relance-etapes/\\?.*lead=${lead}`), 500)
  const retablir = await couperLecture(p, (ch, u) => ch === `${API}/crm/relance-etapes/` && u.searchParams.get('lead') === String(lead))
  await rail.getByRole('button', { name: "Plus d'actions" }).click()
  await p.getByRole('menuitem', { name: /Appeler$/ }).click()
  const fenetre = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: /^Appel — / }) })
  await expect(fenetre, 'fenêtre « Appel » ouverte').toBeVisible({ timeout: 30_000 })
  const illisibles = fenetre.getByTestId('lw-appel-etapes-illisibles')
  await expect(illisibles, '« Étapes de suivi illisibles »').toBeVisible({ timeout: 30_000 })
  await expect(illisibles).toContainText('Étapes de suivi illisibles')
  await expect(fenetre.getByText(/Aucune étape de suivi ouverte/), 'jamais « relancez la cadence » sur une panne').toHaveCount(0)
  await retablir()
  await illisibles.getByRole('button', { name: 'Réessayer' }).click()
  await expect(fenetre.getByTestId('lw-appel-touches'), 'Réessayer relit et montre la touche').toContainText(libelle, { timeout: 30_000 })
  await expect(illisibles).toHaveCount(0)
  // Persistance (lecture) : rechargée, la fenêtre montre la touche ouverte.
  await p.keyboard.press('Escape')
  await p.reload()
  await expect(rail).toBeVisible({ timeout: 60_000 })
  await rail.getByRole('button', { name: "Plus d'actions" }).click()
  await p.getByRole('menuitem', { name: /Appeler$/ }).click()
  await expect(p.getByTestId('lw-appel-touches'), 'après rechargement : touche affichée').toContainText(libelle, { timeout: 30_000 })
})

