// APDF99 — acceptation en direct du groupe APDF (documents / PDF client), jouée par
// l'ORCHESTRATEUR sur la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`).
// Chaque PDF est TÉLÉCHARGÉ par l'API réelle sous une session ouverte par /login
// (demo_admin = société 2 « TAQINOR Démo », anon_admin = société 4 « TAQINOR Anonymisé (QA) »),
// son texte extrait par pdfjs-dist (frontend) ET par PyMuPDF dans le conteneur Django
// (`docker cp` + `python -c`, sans Django), la page 1 de chaque PDF arabe rastérisée en JPEG
// sous `docs/qa-explorer/captures/<date>/`.
//
// Étapes jouées par cette spec (numérotation de la tâche APDF99) :
//   P1.1 /proposal des devis 741 (société 2), 461 / 524 / 445 (société 4) × formats ×
//        {fr, en, ar} — pages (CLAUDE.md), libellés d'APDF46 absents en en/ar, Total TTC
//        lisible en ar, statut inchangé
//   P1.2 dialogue PDF de la liste (anon_admin) : « Joindre la note de calcul » agricole seulement
//   P2   devis d'un client arabe : pièce jointe de l'e-mail console, PDF public, /proposal
//   P3   conditions : page publique (endpoint backend) = portail = PDF ; acceptation par
//        l'écran du portail
//   P7   Paramètres › Société : capital + forme juridique saisis à l'écran, relus, imprimés
//        par le devis suivant, puis restaurés
// Les étapes (4) facturation, (5) chantier / SAV / énergie et l'identité « SOLAIRE EXEMPLE
// SARL » sont rejouées par les sondes `docs/audits/sondes/APDF/C-APDF-ACC-*.py` (transaction
// annulée : profil, prix_achat et langue posés puis défaits) ; l'oracle 10
// (`manage.py audit_coherence`) est lancé par l'orchestrateur.
//
// LIMITES (dites, jamais contournées) :
// - le site public (apps/web) ne tourne pas : la « page /proposition » est lue par son
//   endpoint backend `GET /api/django/public/proposal/<jeton>/data/` ;
// - mot de passe d'anon_admin lu dans l'environnement (`E2E_ANON_PASSWORD`, valeur de
//   `qa_import_anonymise`), jamais écrit ici.
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync, copyFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { expect, test, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { RACINE, aujourdHui } from './_enregistrement.js'
import {
  API_DJANGO, assurerSessionPage, lireJson, listeDe,
  telephoneMobileUnique, textePdf, uniq, uiLoginJusquAuxApps,
} from '../helpers.js'

test.describe.configure({ timeout: 900_000 })
test.use({ viewport: { width: 1920, height: 1080 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const etapeBrute = groupe('APDF', ['APDF99', 'APDF46', 'APDF49', 'APDF17', 'APDF18', 'APDF36', 'APDF48', 'APDF22'])
/** Les `expect.soft` ne lèvent pas : sans ce filet l'étape serait enregistrée PASS malgré
 *  eux. Toute erreur douce du test fait tomber l'étape (verdict FAIL dans l'enregistrement). */
const etape = (id, taches, corps) => etapeBrute(id, taches, async (ctx) => {
  await corps(ctx)
  const douces = ctx.testInfo.errors
  if (douces.length) throw new Error(douces.map((e) => String(e.message).split('\n')[0]).join(' || '))
})
const ANON = { username: 'anon_admin', password: process.env.E2E_ANON_PASSWORD || '' }
/** Page ouverte par /login réel sous anon_admin (société 4). */
async function pageAnon(browser, baseURL, suivi) {
  expect(ANON.password, 'E2E_ANON_PASSWORD posé').toBeTruthy()
  const ctx = await browser.newContext({ baseURL, viewport: { width: 1600, height: 1000 }, serviceWorkers: 'block' })
  const p = suivi.surveiller(await ctx.newPage())
  await uiLoginJusquAuxApps(p, ANON)
  return { ctx, p }
}
const API = API_DJANGO
const T = { timeout: 240_000 }
const CONTENEUR = (process.env.E2E_DJANGO_EXEC || 'docker exec -i erp-agentique-django_core-1').trim().split(/\s+/).pop()
const CAPTURES = join(RACINE, 'docs', 'qa-explorer', 'captures', aujourdHui())
const ARABE = /[\u0600-\u06ff\ufb50-\ufdff\ufe70-\ufeff]/g
const nbArabe = (s) => (String(s).match(ARABE) || []).length
const plat = (s) => String(s).replace(/[\s\u00a0\u202f]+/g, '').replace(/,(\d{2})(?!\d)/g, '.$1')
const PRIX_ACHAT = '4321.09'
const INTERDITS_CLIENT = /prix_achat|prix d['’]achat|\bmarge\b|revendeur/i
// LA liste d'APDF46 (`apps/ventes/tests/test_pdf_apdf_arabe.py::LIBELLES_GABARIT_FR`).
const LIBELLES_GABARIT_FR = [
  'Valable jusqu', 'Votre installation solaire', 'Consultez votre proposition interactive', 'Bonjour',
  'kWc installés', 'Le détail de votre projet', 'VOTRE ÉQUIPEMENT', 'Pourquoi', 'NOS GARANTIES',
  'Prochaines étapes', 'Validité de l', 'Bon pour accord', 'La preuve, en ligne', 'Consultez votre', 'DEVIS N°',
  'PUISSANCE CRÊTE', 'PRODUCTION ANNUELLE', 'ÉCONOMIE ANNUELLE', 'PRIX PAR KWC', 'Validité : jusqu', 'Siège : ',
  'Acompte à la commande', 'Tarifs de référence', 'CLAUSES PARTICULIÈRES', 'Puissance · ', 'Et pour la planète',
  'Spécifique à l', 'Ce document chiffre l', 'autres lignes d', 'autre ligne d', 'Commande : ',
  'Livraison du matériel : ', 'Mise en service : ',
]
const REPLI_FR = 'Document disponible en français uniquement'
// Références des pièces créées ou rendues par la passe (oracle 10, P8).
const REFS = new Set()

// ── Outils serveur (conteneur Django) ────────────────────────────────────────
/** Python SANS Django dans le conteneur (PyMuPDF) : quelques secondes. */
function pythonConteneur(code, args = [], timeout = 300_000) {
  return execFileSync('docker', ['exec', '-i', CONTENEUR, 'python', '-c', code, ...args],
    { stdio: 'pipe', timeout, maxBuffer: 256 * 1024 * 1024 }).toString()
}

/** Python AVEC Django (settings du conteneur) : ~2 min de démarrage sur cette pile. */
function djangoConteneur(code, timeout = 1_200_000) {
  return pythonConteneur(`import django\ndjango.setup()\n${code}`, [], timeout)
}

const ANALYSE_PY = `
import fitz, json, sys, os, glob
d = sys.argv[1]; out = {}
for p in sorted(glob.glob(os.path.join(d, '*.pdf'))):
    n = os.path.basename(p); doc = fitz.open(p)
    out[n] = {
        'pages': doc.page_count,
        'texte': '\\n'.join(pg.get_text() for pg in doc),
        'images': [len(pg.get_images(full=True)) for pg in doc],
        'polices_p1': sorted({f[3] for f in doc[0].get_fonts()}),
        'titre': (doc.metadata or {}).get('title') or '',
    }
    if n.startswith('R_'):
        doc[0].get_pixmap(dpi=100).save(p[:-4] + '.jpg', jpg_quality=70)
print(json.dumps(out))
`

/** PyMuPDF sur un lot de PDF {nom: octets} : pages, texte, images, polices ; les noms
 *  `R_*` sont rastérisés (page 1) et copiés dans les captures du jour. */
function analyserLot(lot) {
  const local = mkdtempSync(join(tmpdir(), 'apdf99-'))
  for (const [nom, octets] of Object.entries(lot)) writeFileSync(join(local, `${nom}.pdf`), octets)
  const distant = `/tmp/${local.split(/[\\/]/).pop()}`
  execFileSync('docker', ['cp', local, `${CONTENEUR}:${distant}`], { stdio: 'pipe', timeout: 120_000 })
  const res = JSON.parse(pythonConteneur(ANALYSE_PY, [distant]))
  if (Object.keys(lot).some((n) => n.startsWith('R_'))) {
    const retour = mkdtempSync(join(tmpdir(), 'apdf99r-'))
    execFileSync('docker', ['cp', `${CONTENEUR}:${distant}/.`, retour], { stdio: 'pipe', timeout: 120_000 })
    mkdirSync(CAPTURES, { recursive: true })
    for (const f of readdirSync(retour).filter((x) => x.endsWith('.jpg'))) {
      copyFileSync(join(retour, f), join(CAPTURES, `ACCEPTATION-APDF-${f.slice(2)}`))
    }
    rmSync(retour, { recursive: true, force: true })
  }
  execFileSync('docker', ['exec', CONTENEUR, 'rm', '-rf', distant], { stdio: 'pipe' })
  rmSync(local, { recursive: true, force: true })
  return Object.fromEntries(Object.entries(res).map(([k, v]) => [k.replace(/\.pdf$/, ''), v]))
}

// ── Outils API ───────────────────────────────────────────────────────────────
async function telecharger(request, chemin, { methode = 'get', data } = {}) {
  const rep = methode === 'post'
    ? await request.post(`${API}/${chemin}`, { ...T, data: data ?? {} })
    : await request.get(`${API}/${chemin}`, T)
  const corps = await rep.body()
  expect(rep.status(), `${chemin} → ${rep.status()} ${corps.toString('utf8').slice(0, 300)}`).toBe(200)
  expect(rep.headers()['content-type'] || '', `${chemin} : application/pdf`).toContain('application/pdf')
  return { octets: corps, entete: rep.headers()['content-disposition'] || '' }
}

const lireDevis = async (request, id) => lireJson(await request.get(`${API}/ventes/devis/${id}/`, T), `devis ${id}`)

/** Sortie client : jamais prix_achat, marge, revendeur (oracle 7). */
function sansDonneeInterne(texte, quoi) {
  expect(String(texte), `${quoi} : aucun prix_achat / marge / revendeur`).not.toMatch(INTERDITS_CLIENT)
  expect(plat(texte), `${quoi} : prix_achat repère jamais imprimé`).not.toContain(PRIX_ACHAT)
}

const LIGNES = [
  { d: 'Onduleur hybride Deye 5kW Monophasé', q: '1', pu: '12345.67', tva: '20.00', marque: 'Deye' },
  { d: 'Panneau Canadian Solar 710W', q: '8', pu: '1234.57', tva: '10.00', marque: 'Canadian Solar' },
  { d: 'Structures acier', q: '8', pu: '416.67', tva: '20.00' },
  { d: 'Installation', q: '1', pu: '3333.33', tva: '20.00' },
]

async function creerClient(request, { langue = 'fr', tag = 'APDF99' } = {}) {
  const ice = `00${String(Date.now()).slice(-13)}`
  return lireJson(await request.post(`${API}/crm/clients/`, {
    ...T,
    data: {
      nom: uniq(tag), prenom: 'Acceptation', type_client: 'entreprise', telephone: telephoneMobileUnique(),
      email: `${uniq('apdf99').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.test`,
      ice, if_fiscal: `IF${String(Date.now()).slice(-7)}`, rc: `RC${String(Date.now()).slice(-6)}`,
      langue_document: langue, adresse: '3 rue Essai, Casablanca',
    },
  }), `client ${langue}`)
}

/** Devis résidentiel (lignes réelles, produits à prix_achat repère) pour un client. */
async function creerDevis(request, clientId, { accepter = false, envoyer = true } = {}) {
  const lignes = []
  for (const [i, l] of LIGNES.entries()) {
    const p = await lireJson(await request.post(`${API}/stock/produits/`, {
      ...T, data: { nom: `${l.d} ${Date.now()}-${i}`, prix_vente: l.pu, prix_achat: PRIX_ACHAT, ...(l.marque ? { marque: l.marque } : {}) },
    }), `produit ${l.d}`)
    lignes.push({ produit: p.id, designation: l.d, quantite: l.q, prix_unitaire: l.pu, remise: '0.00', taux_tva: l.tva, type_ligne: 'produit', ordre: i })
  }
  const devis = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', client: clientId, mode_installation: 'residentiel', lignes },
  }), 'devis')
  let lien = null
  if (envoyer) lien = await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  if (accepter) await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client APDF99' } }), 'acceptation')
  return { ...(await lireDevis(request, devis.id)), lien, produits: lignes.map((l) => l.produit) }
}

// ── Devis par marché (ids de la tâche, présents sur cette pile) ─────────────
// 741 = DEV-202610-0071 société 2 ; 461 / 524 / 445 = société 4 (jeu anonymisé).
// include_etude du 741 : 4 pages, ou 5 selon ACAL103 (texte de la tâche).
const MARCHES = {
  residentiel: { id: 741, societe: 2, pages: { defaut: [3], onepage: [1], include_etude: [4, 5], devis_final: [3] } },
  commercial: { id: 461, societe: 4, pages: { defaut: [3], onepage: [1], include_etude: [3], devis_final: [3] } },
  industriel: { id: 524, societe: 4, pages: { defaut: [4], onepage: [1], include_etude: [4], devis_final: [4] } },
  agricole: { id: 445, societe: 4, pages: { defaut: [3], onepage: [1], include_etude: [3], devis_final: [3], note_calcul: [4] } },
}
const FORMATS = {
  defaut: '', onepage: 'pdf_mode=onepage', include_etude: 'include_etude=1', devis_final: 'devis_final=1',
  note_calcul: 'include_note_calcul=1',
}

// ── P1.1 — /proposal : 4 marchés × formats × langues ─────────────────────────
etape('P1.1', ['APDF99', 'APDF46', 'APDF49'], async ({ page, context, suivi, testInfo }) => {
  const anon = await pageAnon(context.browser(), testInfo.project.use.baseURL, suivi)
  const req = (m) => (m.societe === 2 ? page.request : anon.p.request)
  const rendus = {}
  const lot = {}
  const avant = {}
  for (const [marche, m] of Object.entries(MARCHES)) {
    avant[marche] = (await lireDevis(req(m), m.id)).statut
    const combos = Object.keys(m.pages).map((f) => [f, 'fr'])
    for (const l of ['en', 'ar']) combos.push(['defaut', l], ['onepage', l])
    for (const [f, langue] of combos) {
      const q = [FORMATS[f], `langue=${langue}`].filter(Boolean).join('&')
      const { octets } = await telecharger(req(m), `ventes/devis/${m.id}/proposal/?${q}`)
      const cle = `${langue === 'ar' ? 'R_' : 'N_'}P1-${langue}-${m.id}-${f}`
      rendus[cle] = { marche, format: f, langue, texte: await textePdf(octets) }
      lot[cle] = octets
    }
  }
  const fitz = analyserLot(lot)
  const lignes = []
  for (const [cle, r] of Object.entries(rendus)) {
    const fz = fitz[cle]
    const attendu = MARCHES[r.marche].pages[r.format]
    const texte = `${r.texte}\n${fz.texte}`
    lignes.push(`${MARCHES[r.marche].id} ${r.marche} ${r.format} ${r.langue} : ${fz.pages} p. (attendu ${attendu.join(' ou ')}), arabe ${nbArabe(fz.texte)}`)
    expect.soft(attendu, `${r.marche} ${r.format} ${r.langue} : pages ${fz.pages}`).toContain(fz.pages)
    sansDonneeInterne(texte, cle)
    expect.soft(texte, `${cle} : aucun pictogramme hors BMP`).not.toMatch(/[\u{1F000}-\u{1FFFF}]/u)
    if (r.langue !== 'fr') {
      const restes = LIBELLES_GABARIT_FR.filter((lib) => texte.includes(lib))
      expect.soft(restes, `${cle} : libellés de gabarit français restés`).toEqual([])
    }
    if (r.langue === 'ar') {
      expect.soft(nbArabe(fz.texte), `${cle} : ≥ 100 caractères arabes`).toBeGreaterThanOrEqual(100)
      expect.soft(fz.polices_p1.join(' '), `${cle} : police arabe embarquée en page 1`).toMatch(/Arab|Noto/i)
    }
  }
  // Total TTC lisible (texte de l'arabe = chiffres du devis) — défaut ar de chaque marché.
  for (const [marche, m] of Object.entries(MARCHES)) {
    const d = await lireDevis(req(m), m.id)
    const entier = String(Math.round(Number(d.total_ttc)))
    if (Number(d.total_ttc) > 0) {
      expect.soft(plat(fitz[`R_P1-ar-${m.id}-defaut`].texte), `${marche} ar : Total TTC ${d.total_ttc} lisible`)
        .toContain(entier)
    }
    lignes.push(`${m.id} total_ttc ${d.total_ttc} statut ${avant[marche]} -> ${d.statut}`)
    // CLAUSE PERSISTANCE (règle #4) : les rendus ne changent aucun statut.
    expect(d.statut, `${marche} : statut inchangé par ${Object.keys(rendus).length} rendus`).toBe(avant[marche])
  }
  testInfo.annotations.push({ type: 'rendus', description: lignes.join(' | ') })
  console.log(`[P1.1] ${lignes.join('\n')}`)
  await anon.ctx.close()
  suivi.verifie(6)
  suivi.verifie(7)
})

// ── P1.2 — dialogue PDF : note de calcul agricole seulement ─────────────────
etape('P1.2', ['APDF17'], async ({ context, suivi, testInfo }) => {
  const anon = await pageAnon(context.browser(), testInfo.project.use.baseURL, suivi)
  const page = anon.p
  const res = await lireDevis(page.request, MARCHES.commercial.id)
  const ag = await lireDevis(page.request, MARCHES.agricole.id)
  const ouvrir = async (d) => {
    await page.goto('/ventes/devis')
    await page.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference)
    const ligne = page.locator('tr', { has: page.getByTestId(`ref-cell-${d.id}`) }).first()
    await expect(ligne).toBeVisible({ timeout: 60_000 })
    await ligne.getByRole('button', { name: 'PDF', exact: true }).click()
    const dialogue = page.getByRole('dialog').filter({ hasText: `Générer le PDF — ${d.reference}` })
    await expect(dialogue).toBeVisible({ timeout: 30_000 })
    return dialogue
  }
  // Commercial : la case est absente.
  let dialogue = await ouvrir(res)
  await expect(dialogue.getByRole('checkbox', { name: 'Joindre la note de calcul' })).toHaveCount(0)
  await dialogue.getByRole('button', { name: 'Annuler' }).click()
  // Agricole : visible, cochée → generer-pdf porte include_note_calcul: true.
  dialogue = await ouvrir(ag)
  const caseNote = dialogue.getByRole('checkbox', { name: 'Joindre la note de calcul' })
  await expect(caseNote).toBeVisible()
  await expect(caseNote).not.toBeChecked()
  await caseNote.click()
  const [req] = await Promise.all([
    page.waitForRequest((r) => r.method() === 'POST' && new RegExp(`/ventes/devis/${ag.id}/generer-pdf/$`).test(new URL(r.url()).pathname), { timeout: 60_000 }),
    dialogue.getByRole('button', { name: 'Générer' }).click(),
  ])
  expect(req.postDataJSON().include_note_calcul, 'corps generer-pdf : include_note_calcul').toBe(true)
  const rep = await req.response()
  expect(rep.status(), 'generer-pdf accepté').toBeLessThan(300)
  // CLAUSE PERSISTANCE : rouvert, la case est décochée par défaut ; statut inchangé.
  await page.keyboard.press('Escape').catch(() => undefined)
  dialogue = await ouvrir(ag)
  await expect(dialogue.getByRole('checkbox', { name: 'Joindre la note de calcul' })).not.toBeChecked()
  await page.screenshot({ path: join(CAPTURES, 'ACCEPTATION-APDF-P1.2-dialogue-agricole.jpg'), type: 'jpeg', quality: 60 }).catch(() => undefined)
  await dialogue.getByRole('button', { name: 'Annuler' }).click()
  expect((await lireDevis(page.request, ag.id)).statut).toBe(ag.statut)
  expect((await lireDevis(page.request, res.id)).statut).toBe(res.statut)
  await anon.ctx.close()
  suivi.verifie(5)
})

// ── P2 — client arabe : e-mail console, lien public, /proposal ───────────────
/** Pièce jointe PDF `Devis_<ref>.pdf` du dernier e-mail console (docker logs). */
function pieceJointeConsole(reference, depuis) {
  const logs = execFileSync('docker', ['logs', '--since', depuis, CONTENEUR], { stdio: 'pipe', maxBuffer: 512 * 1024 * 1024 })
  const tout = logs.toString('utf8')
  const i = tout.lastIndexOf(`filename="Devis_${reference}.pdf"`)
  if (i < 0) return null
  const bloc = (tout.slice(i).split(/\r?\n\r?\n/)[1] || '').split(/\r?\n--/)[0]
  return Buffer.from(bloc.replace(/[^A-Za-z0-9+/=]/g, ''), 'base64')
}

const p2 = {}

/** Connexion JWT du compte portail (comme `helpers.connecterPortail` : mot de passe
 *  temporaire changé, AUD139/N96) — mais un 429 du throttle `login` (5/min PAR IP, que la
 *  rejouée concurrente partage) est ATTENDU 65 s puis rejoué, jamais compté en échec. */
async function connexionPortail(playwright, baseURL, username, motDePasse) {
  const jeton = async (ctx, password) => {
    for (let essai = 0; essai < 5; essai += 1) {
      const r = await ctx.post(`${API}/token/`, { ...T, data: { username, password } })
      if (r.status() !== 429) return r
      await new Promise((ok) => { setTimeout(ok, 65_000) })
    }
    return ctx.post(`${API}/token/`, { ...T, data: { username, password } })
  }
  const premier = await playwright.request.newContext({ baseURL })
  expect((await jeton(premier, motDePasse)).status(), 'connexion du client portail').toBe(200)
  const nouveau = `${motDePasse}-${Date.now().toString(36)}`
  const change = await premier.post(`${API}/auth/change-password/`, { ...T, data: { current_password: motDePasse, new_password: nouveau } })
  expect(change.ok(), `changement du mot de passe portail → HTTP ${change.status()}`).toBeTruthy()
  await premier.dispose()
  const portail = await playwright.request.newContext({ baseURL })
  expect((await jeton(portail, nouveau)).status(), 'reconnexion du client portail').toBe(200)
  return portail
}
etape('P2', ['APDF99', 'APDF18'], async ({ page, suivi }) => {
  const depuis = new Date(Date.now() - 60_000).toISOString()
  const client = await creerClient(page.request, { langue: 'ar', tag: 'APDF99 Arabe' })
  const d = await creerDevis(page.request, client.id, { envoyer: false })
  const envoi = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/envoyer-email/`, { ...T, data: { pdf_mode: 'full' } }), 'envoyer-email')
  expect(envoi.devis_statut, 'devis envoyé').toBe('envoye')
  const pj = pieceJointeConsole(d.reference, depuis)
  expect(pj, `pièce jointe Devis_${d.reference}.pdf dans l'e-mail console`).toBeTruthy()
  const lien = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: {} }), 'lien')
  const publicPdf = await page.request.get(`${API}/public/proposal/${lien.token}/pdf/`, T)
  expect(publicPdf.status(), 'PDF public').toBe(200)
  const sansLangue = await telecharger(page.request, `ventes/devis/${d.id}/proposal/`)
  const fz = analyserLot({ 'R_P2-piece-jointe': pj, 'R_P2-pdf-public': await publicPdf.body(), 'R_P2-proposal': sansLangue.octets })
  // Devis résidentiel de 4 lignes : premium complet = 3 pages (CLAUDE.md).
  expect.soft(fz['R_P2-proposal'].pages, '/proposal résidentiel 4 lignes : 3 pages').toBe(3)
  for (const [nom, r] of Object.entries(fz)) {
    expect.soft(nbArabe(r.texte), `${nom} : PDF en arabe (≥ 100 caractères arabes)`).toBeGreaterThanOrEqual(100)
    expect.soft(LIBELLES_GABARIT_FR.filter((lib) => r.texte.includes(lib)), `${nom} : libellés français restés`).toEqual([])
    sansDonneeInterne(r.texte, nom)
  }
  console.log(`[P2] ${Object.entries(fz).map(([n, r]) => `${n} ${r.pages} p. arabe ${nbArabe(r.texte)}`).join(' | ')}`)
  REFS.add(d.reference)
  Object.assign(p2, { client, devis: d, jeton: lien.token, jetonInterne: lien.token_interne, texteProposal: fz['R_P2-proposal'].texte })
  expect((await lireDevis(page.request, d.id)).statut, 'statut inchangé par les rendus').toBe('envoye')
  suivi.verifie(7)
})

// ── P3 — conditions page publique = portail = PDF ; acceptation par le portail ─
etape('P3', ['APDF99', 'APDF36', 'APDF48'], async ({ page, context, suivi, testInfo }) => {
  const playwright = { request: pwRequest }
  const browser = context.browser()
  expect(p2.devis, 'P2 doit avoir monté le devis du client arabe').toBeTruthy()
  const d = p2.devis
  const pub = await lireJson(await page.request.get(`${API}/public/proposal/${p2.jeton}/data/`, T), 'données publiques')
  expect(Array.isArray(pub.conditions) && pub.conditions.length > 0, 'conditions publiques servies').toBeTruthy()
  // Compte portail du client : provisionné, mot de passe d'essai posé côté serveur.
  const comptes = listeDe(await lireJson(await page.request.get(`${API}/portail/comptes-portail/`, T), 'comptes'))
  const compte = comptes.find((c) => c.client === p2.client.id)
    ?? await lireJson(await page.request.post(`${API}/portail/comptes-portail/`, { ...T, data: { client: p2.client.id } }), 'compte portail')
  const prov = await lireJson(await page.request.post(`${API}/portail/comptes-portail/${compte.id}/provisionner-acces/`, { ...T, data: {} }), 'accès portail')
  const mdp = `Apdf99-${Date.now().toString(36)}!`
  djangoConteneur(`from django.contrib.auth import get_user_model as g\nu = g().objects.get(username=${JSON.stringify(prov.username)})\nu.set_password(${JSON.stringify(mdp)}); u.save()`)
  const baseURL = testInfo.project.use.baseURL
  const api = await connexionPortail(playwright, baseURL, prov.username, mdp)
  const mes = listeDe(await lireJson(await api.get(`${API}/portail/mes-devis/`, T), 'mes-devis'))
  const md = mes.find((x) => x.id === d.id)
  expect(md, 'le devis figure dans « Mes devis »').toBeTruthy()
  // Page publique = portail (titre + puces), et chaque puce dans le PDF.
  expect(md.conditions_titre, 'titre portail = page publique').toBe(pub.conditions_titre)
  expect(md.conditions, 'puces portail = page publique').toEqual(pub.conditions)
  // Comparaison MOT À MOT : l'extraction PyMuPDF d'un PDF arabe réordonne les fragments
  // bidi (« 30% » / « %30 ») et décompose la ligature lam-alef (« استلام » lu « استالم ») ;
  // alif / lam / ya sont donc retirés des deux côtés avant de chercher chaque mot.
  const neutre = (s) => String(s).normalize('NFKC').replace(/[\sالىيإأآ]+/g, '').toLowerCase()
  const pdfNeutre = neutre(p2.texteProposal)
  const absentes = pub.conditions.flatMap((c) => String(c).normalize('NFKC').split(/[\s:·%/()]+/)
    .filter((m) => neutre(m).length >= 2 && !pdfNeutre.includes(neutre(m))).map((m) => `${m} (« ${c} »)`))
  expect.soft(absentes, 'mots des puces publiques absents du PDF du devis').toEqual([])
  // Écran du portail : connexion par le formulaire réel, « Accepter », case obligatoire.
  const ctx = await browser.newContext({ baseURL, viewport: { width: 1600, height: 1000 }, serviceWorkers: 'block' })
  const portail = suivi.surveiller(await ctx.newPage())
  const etat = await api.storageState()
  await ctx.addCookies(etat.cookies)
  await portail.goto('/portail/client/devis')
  await expect(portail.getByText(d.reference).first()).toBeVisible({ timeout: 60_000 })
  // Le client n'a qu'UN devis : le seul bouton « Accepter » est le sien.
  await expect(portail.getByRole('button', { name: 'Accepter', exact: true })).toHaveCount(1)
  await portail.getByRole('button', { name: 'Accepter', exact: true }).click()
  const dlg = portail.getByRole('dialog').filter({ hasText: `Accepter le devis ${d.reference}` })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  const section = dlg.getByTestId('portail-devis-conditions')
  await expect(section).toContainText(pub.conditions_titre)
  for (const c of pub.conditions) await expect(section).toContainText(c)
  await dlg.locator('#portail-signataire').fill('Client APDF99 Portail')
  const confirmer = dlg.getByRole('button', { name: /Confirmer l.acceptation/ })
  await expect(confirmer).toBeDisabled()
  await dlg.getByRole('checkbox').first().check()
  await expect(confirmer).toBeEnabled()
  const [rep] = await Promise.all([
    portail.waitForResponse((r) => r.request().method() === 'POST' && new RegExp(`/portail/mes-devis/${d.id}/accepter/$`).test(new URL(r.url()).pathname), { timeout: 120_000 }),
    confirmer.click(),
  ])
  expect(rep.status(), await rep.text()).toBe(200)
  expect(rep.request().postDataJSON().accepte_conditions, 'accepte_conditions envoyé').toBe(true)
  // CLAUSE PERSISTANCE : rechargé, le devis est accepté (portail et ERP).
  await portail.reload()
  await expect(portail.getByText(d.reference).first()).toBeVisible({ timeout: 60_000 })
  const relu = listeDe(await lireJson(await api.get(`${API}/portail/mes-devis/`, T), 'mes-devis relu')).find((x) => x.id === d.id)
  expect(relu.accepte, 'portail : accepté').toBeTruthy()
  expect((await lireDevis(page.request, d.id)).statut, 'ERP : accepté').toBe('accepte')
  await portail.screenshot({ path: join(CAPTURES, 'ACCEPTATION-APDF-P3-portail.jpg'), type: 'jpeg', quality: 60 }).catch(() => undefined)
  await ctx.close()
  await api.dispose()
  suivi.verifie(5)
})

// ── P7 — Paramètres › Société : capital et forme juridique (APDF22) ─────────
etape('P7', ['APDF22'], async ({ page }) => {
  const avant = await lireJson(await page.request.get(`${API}/parametres/`, T), 'profil')
  const CAPITAL = '123 456,00 MAD'
  const FORME = 'SARL AU'
  try {
    await page.goto('/parametres?onglet=societe')
    const capital = page.getByLabel('Capital social')
    await expect(capital).toBeVisible({ timeout: 60_000 })
    await capital.fill(CAPITAL)
    await page.getByLabel('Forme juridique').fill(FORME)
    const [rep] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'PATCH' && /\/parametres\/update\/$/.test(new URL(r.url()).pathname), { timeout: 60_000 }),
      page.getByRole('button', { name: 'Enregistrer', exact: true }).first().click(),
    ])
    expect(rep.status(), await rep.text()).toBeLessThan(300)
    const corps = rep.request().postDataJSON()
    expect(corps.capital_social, 'PATCH : capital_social').toBe(CAPITAL)
    expect(corps.forme_juridique, 'PATCH : forme_juridique').toBe(FORME)
    await expect(page.getByText('Profil enregistré avec succès.')).toBeVisible({ timeout: 30_000 })
    // CLAUSE PERSISTANCE : rechargé, l'écran relit les valeurs.
    await page.reload()
    await expect(page.getByLabel('Capital social')).toHaveValue(CAPITAL, { timeout: 60_000 })
    await expect(page.getByLabel('Forme juridique')).toHaveValue(FORME)
    // CLAUSE CLIENT : le devis suivant imprime ces mentions (bande légale, APDF3).
    const { octets } = await telecharger(page.request, `ventes/devis/${MARCHES.residentiel.id}/proposal/`)
    const texte = await textePdf(octets)
    expect.soft(plat(texte), 'devis : capital social imprimé').toContain(plat(CAPITAL).replace('MAD', ''))
    expect.soft(texte, 'devis : forme juridique imprimée').toContain(FORME)
  } finally {
    await page.request.patch(`${API}/parametres/update/`, {
      ...T, data: { capital_social: avant.capital_social, forme_juridique: avant.forme_juridique },
    })
  }
  const apres = await lireJson(await page.request.get(`${API}/parametres/`, T), 'profil restauré')
  expect(apres.capital_social, 'capital restauré').toBe(avant.capital_social)
  expect(apres.forme_juridique, 'forme restaurée').toBe(avant.forme_juridique)
})
