// APDF99 — acceptation en direct du groupe APDF (documents / PDF client), jouée par
// l'ORCHESTRATEUR sur la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`).
// Chaque PDF est TÉLÉCHARGÉ par l'API réelle (session demo_admin), son texte extrait
// par pdfjs-dist (frontend) ET par PyMuPDF dans le conteneur Django (`docker cp` +
// `python -c`, sans Django : rapide), la page 1 de chaque PDF arabe rastérisée en JPEG
// sous `docs/qa-explorer/captures/<date>/`.
//
// Étapes (numérotation de la tâche APDF99) :
//   P1.1 /proposal 4 marchés × formats × {fr, en, ar} — pages (CLAUDE.md), libellés de
//        gabarit français absents en en/ar (liste d'APDF46), arabe lisible, statut inchangé
//   P1.2 dialogue PDF de la liste : « Joindre la note de calcul » agricole seulement (APDF17)
//   P2   devis d'un client arabe : pièce jointe de l'e-mail console, PDF public, /proposal (APDF18)
//   P3   conditions : page publique (endpoint backend) = portail = PDF ; acceptation par
//        l'écran du portail (APDF36, APDF48)
//   P4   facture / avoir / ND / pro-forma / reçu / BC / relance, client fr puis ar (APDF31…)
//   P5   BL, PV, dossier de remise, compte-rendu à deux photos, rapport SAV, rapport énergie
//   P6   identité « SOLAIRE EXEMPLE SARL » posée dans une transaction ANNULÉE (sonde serveur,
//        `python -c` dans le conteneur, APIClient → /proposal et documents chantier réels)
//   P7   Paramètres › Société : capital + forme juridique saisis à l'écran, relus, imprimés
//        par le devis suivant, puis restaurés (APDF22)
//   P8   oracle 10 : `manage.py audit_coherence --no-persist` sur les objets de la passe
//
// LIMITES CONSTATÉES (dites, jamais contournées) :
// - les devis 741 / 461 / 524 / 445 de la tâche sont des ids du jeu ANONYMISÉ (prod) :
//   absents de cette pile ; remplacés par les devis démo de la société 1 (résidentiel 885,
//   commercial 830, industriel 831) et un devis agricole monté par l'API (pompe à courbe) ;
// - `anon_admin` : mot de passe inconnu sur cette pile → aucune passe société 4 ;
// - le site public (apps/web) ne tourne pas : la « page /proposition » est lue par son
//   endpoint backend `GET /api/django/public/proposal/<jeton>/data/` (8010 via le proxy) ;
// - le libellé de la case est « Joindre la note de calcul » (la tâche APDF17 disait
//   « Note de calcul FDA (+1 page) ») ;
// - le portail monitoring (APDF43) n'est pas joué (aucune installation suivie démo) ;
// - P6 : « taqinor.ma/proposition » (ligne « Votre proposition en ligne » du C&I) est le LIEN
//   DE PROPOSITION, toléré par APDF5 / la garde APDF45 ; il est listé, jamais compté interdit.
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync, copyFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { expect, test, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { RACINE, aujourdHui } from './_enregistrement.js'
import {
  API_DJANGO, PNG_1PX, assurerSessionPage, lireJson, listeDe,
  telephoneMobileUnique, textePdf, uniq,
} from '../helpers.js'

test.describe.configure({ timeout: 900_000 })
test.use({ viewport: { width: 1920, height: 1080 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const etape = groupe('APDF', [
  'APDF99', 'APDF46', 'APDF49', 'APDF17', 'APDF18', 'APDF36', 'APDF48', 'APDF31', 'APDF32',
  'APDF33', 'APDF39', 'APDF41', 'APDF42', 'APDF45', 'APDF22',
])
const API = API_DJANGO
const T = { timeout: 240_000 }
const CONTENEUR = (process.env.E2E_DJANGO_EXEC || 'docker exec -i accept-replay-django').trim().split(/\s+/).pop()
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
const lireFacture = async (request, id) => lireJson(await request.get(`${API}/ventes/factures/${id}/`, T), `facture ${id}`)

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

// ── Devis par marché ─────────────────────────────────────────────────────────
const MARCHES = {
  // 885 = DEV-202610-0058 : 20 lignes, deux options → mise en page « devis chargé » du premium
  // résidentiel (page « Rentabilité de votre investissement » dédiée = 4 pages, variante
  // « plus10 » de test_quote_engine_residential) ; le cas 3 pages est rejoué en P2 (4 lignes).
  residentiel: { id: 885, pages: { defaut: 4, onepage: 1, include_etude: 4, devis_final: 4 } },
  commercial: { id: 830, pages: { defaut: 3, onepage: 1, include_etude: 3, devis_final: 3 } },
  industriel: { id: 831, pages: { defaut: 4, onepage: 1, include_etude: 4, devis_final: 4 } },
  agricole: { id: null, pages: { defaut: 3, onepage: 1, include_etude: 3, devis_final: 3, note_calcul: 4 } },
}
const FORMATS = {
  defaut: '', onepage: 'pdf_mode=onepage', include_etude: 'include_etude=1', devis_final: 'devis_final=1',
  note_calcul: 'include_note_calcul=1',
}

/** Devis agricole de la passe, monté par l'API réelle (POST devis + replace-lines avec les
 *  entrées v2 de l'étude pompage — le serveur calcule la promesse, AGR123), comme
 *  `agricole-chantier-recette.spec.js` : il n'en existe aucun dans la société démo, et le
 *  générateur à l'écran ne finit pas de charger sur cette pile chargée (constaté le 30/10 :
 *  « Chargement des données… » > 45 s puis « La connexion a expiré »). */
async function devisAgricole(page) {
  if (MARCHES.agricole.id) return MARCHES.agricole.id
  const r = page.request
  const pompes = listeDe(await lireJson(await r.get(`${API}/stock/produits/?search=OSP&page_size=100`, T), 'pompes OSP'))
  const pompe = pompes.find((p) => p.courbe_pompe && Object.keys(p.courbe_pompe).length)
  expect(pompe, 'pompe à courbe au catalogue (seed_catalogue)').toBeTruthy()
  const panneaux = listeDe(await lireJson(await r.get(`${API}/stock/produits/?search=Panneau&page_size=50`, T), 'panneaux'))
  const panneau = panneaux.find((p) => parseFloat(p.prix_vente) > 0)
  const variateurs = listeDe(await lireJson(await r.get(`${API}/stock/produits/?search=VEICHI&page_size=50`, T), 'variateurs'))
  const variateur = variateurs.find((p) => parseFloat(p.prix_vente) > 0)
  const client = await creerClient(r, { tag: 'APDF99 Ferme' })
  const devis = await lireJson(await r.post(`${API}/ventes/devis/`, {
    ...T, data: { client: client.id, taux_tva: '20.00', mode_installation: 'agricole' },
  }), 'devis agricole')
  const lignes = [{ produit: pompe.id, designation: pompe.nom, quantite: '1.00', prix_unitaire: '12500.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }]
  if (panneau) lignes.push({ produit: panneau.id, designation: panneau.nom, quantite: '10.00', prix_unitaire: String(panneau.prix_vente), remise: '0.00', taux_tva: '10.00', type_ligne: 'produit', ordre: 1 })
  if (variateur) lignes.push({ produit: variateur.id, designation: variateur.nom, quantite: '1.00', prix_unitaire: String(variateur.prix_vente), remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 2 })
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/replace-lines/`, {
    ...T,
    data: {
      lignes,
      etude_params: {
        mode_pompe: 'neuve',
        besoin: { mode: 'volume_declare', volume_m3_jour: 60, mois_pointe: 7, cultures: [], region: null },
        source: { niveau_dynamique_m: 40, niveau_statique_m: 32 },
        hmt_entrees: { saisie_m: 45 },
        alim: 'tri', type_pompe: 'immergee', options_cochees: [], taille: 'recommandee',
      },
    },
  }), 'lignes et étude agricoles')
  MARCHES.agricole.id = devis.id
  return devis.id
}

// ── P1.1 — /proposal : 4 marchés × formats × langues ─────────────────────────
etape('P1.1', ['APDF99', 'APDF46', 'APDF49'], async ({ page, suivi, testInfo }) => {
  await devisAgricole(page)
  const rendus = {}
  const lot = {}
  const avant = {}
  for (const [marche, m] of Object.entries(MARCHES)) {
    avant[marche] = (await lireDevis(page.request, m.id)).statut
    const combos = Object.keys(m.pages).map((f) => [f, 'fr'])
    for (const l of ['en', 'ar']) combos.push(['defaut', l], ['onepage', l])
    for (const [f, langue] of combos) {
      const q = [FORMATS[f], `langue=${langue}`].filter(Boolean).join('&')
      const { octets } = await telecharger(page.request, `ventes/devis/${m.id}/proposal/?${q}`)
      const cle = `${langue === 'ar' ? 'R_' : 'N_'}P1-${langue}-${marche}-${f}`
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
    lignes.push(`${r.marche} ${r.format} ${r.langue} : ${fz.pages} p. (attendu ${attendu}), arabe ${nbArabe(fz.texte)}`)
    expect.soft(fz.pages, `${r.marche} ${r.format} ${r.langue} : pages`).toBe(attendu)
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
    const d = await lireDevis(page.request, m.id)
    const entier = String(Math.round(Number(d.total_ttc)))
    if (Number(d.total_ttc) > 0) {
      expect.soft(plat(fitz[`R_P1-ar-${marche}-defaut`].texte), `${marche} ar : Total TTC ${d.total_ttc} lisible`)
        .toContain(entier)
    }
    // CLAUSE PERSISTANCE (règle #4) : les rendus ne changent aucun statut.
    expect(d.statut, `${marche} : statut inchangé par ${Object.keys(rendus).length} rendus`).toBe(avant[marche])
  }
  testInfo.annotations.push({ type: 'rendus', description: lignes.join(' | ') })
  console.log(`[P1.1] ${lignes.join('\n')}`)
  suivi.verifie(6)
  suivi.verifie(7)
})

// ── P1.2 — dialogue PDF : note de calcul agricole seulement ─────────────────
etape('P1.2', ['APDF17'], async ({ page, suivi }) => {
  const agri = await devisAgricole(page)
  const res = await lireDevis(page.request, MARCHES.residentiel.id)
  const ag = await lireDevis(page.request, agri)
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
  // Résidentiel : la case est absente.
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
  await dialogue.getByRole('button', { name: 'Annuler' }).click()
  expect((await lireDevis(page.request, ag.id)).statut).toBe(ag.statut)
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

// ── P4 — documents de facturation, client fr puis ar ─────────────────────────
etape('P4', ['APDF99', 'APDF31'], async ({ page, suivi }) => {
  const notes = []
  for (const langue of ['fr', 'ar']) {
    const client = await creerClient(page.request, { langue, tag: `APDF99 Fact ${langue}` })
    const d = await creerDevis(page.request, client.id, { accepter: true })
    const bc = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
    await lireJson(await page.request.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer BC')
    const brouillon = await lireJson(await page.request.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'facture du BC')
    await lireJson(await page.request.patch(`${API}/ventes/factures/${brouillon.id}/`, { ...T, data: { date_livraison: '2026-10-20' } }), 'date de livraison')
    await lireJson(await page.request.post(`${API}/ventes/factures/${brouillon.id}/emettre/`, { ...T, data: {} }), 'émission')
    const fp = await lireJson(await page.request.post(`${API}/ventes/factures/${brouillon.id}/enregistrer-paiement/`, {
      ...T, data: { montant: '1000.00', mode: 'virement', date_paiement: new Date().toISOString().slice(0, 10), reference: uniq('VIR') },
    }), 'paiement')
    const paiementId = fp.paiements.at(-1).id
    const nd = await lireJson(await page.request.post(`${API}/ventes/factures/${brouillon.id}/creer-note-debit/`, { ...T, data: { montant: '500.00', taux_tva: '20', motif: 'Complément APDF99' } }), 'note de débit')
    const av = await lireJson(await page.request.post(`${API}/ventes/factures/${brouillon.id}/creer-avoir/`, {
      ...T, data: { motif: 'Geste APDF99', type: 'geste_commercial', lignes: [{ designation: 'Geste commercial', produit: d.produits[2], quantite: '1', prix_unitaire: '100.00' }] },
    }), 'avoir')
    const avant = await lireFacture(page.request, brouillon.id)
    for (const x of [d.reference, avant.reference, bc.reference]) REFS.add(x)
    const docs = {
      facture: await telecharger(page.request, `ventes/factures/${brouillon.id}/telecharger-pdf/`),
      recu: await telecharger(page.request, `ventes/paiements/${paiementId}/recu-pdf/`),
      recu2: await telecharger(page.request, `ventes/paiements/${paiementId}/recu-pdf/`),
      avoir: await telecharger(page.request, `ventes/avoirs/${av.id}/telecharger-pdf/`),
      nd: await telecharger(page.request, `ventes/notes-debit/${nd.id}/telecharger-pdf/`),
      proforma: await telecharger(page.request, `ventes/devis/${d.id}/proforma-pdf/`, { methode: 'post' }),
      bc: await telecharger(page.request, `ventes/bons-commande/${bc.id}/pdf/`),
      relance: await telecharger(page.request, `ventes/factures/${brouillon.id}/lettre-relance-pdf/`),
    }
    const lot = Object.fromEntries(Object.entries(docs).map(([k, v]) => [`${langue === 'ar' ? 'R_' : 'N_'}P4-${langue}-${k}`, v.octets]))
    const fz = analyserLot(lot)
    const t = (k) => fz[`${langue === 'ar' ? 'R_' : 'N_'}P4-${langue}-${k}`]
    for (const k of Object.keys(docs)) {
      sansDonneeInterne(t(k).texte, `${langue} ${k}`)
      notes.push(`${langue} ${k} ${t(k).pages} p. arabe ${nbArabe(t(k).texte)}`)
    }
    // ICE / IF / RC du client sur avoir et ND.
    for (const k of ['avoir', 'nd']) {
      for (const v of [client.ice, client.if_fiscal, client.rc]) expect.soft(plat(t(k).texte), `${langue} ${k} : identifiant client ${v}`).toContain(v)
    }
    // Facture : date de livraison et pagination.
    expect.soft(t('facture').texte, `${langue} facture : date de livraison 20/10/2026`).toContain('20/10/2026')
    expect.soft(t('facture').texte, `${langue} facture : pagination « i / N »`).toMatch(/1\s*\/\s*\d/)
    // Reçu : numéro de série de la société, stable.
    const num = (docs.recu.entete.match(/Quittance_(REC-\d+)/) || [])[1]
    expect.soft(num, `${langue} reçu : numéro REC- de série`).toBeTruthy()
    expect.soft(t('recu').texte, `${langue} reçu : numéro imprimé`).toContain(num)
    expect.soft(docs.recu2.entete, `${langue} reçu : même numéro au second rendu`).toContain(num)
    // D-APDF-3 : traduits (avoir, ND, reçu, relance) ; repli imprimé (BC, pro-forma).
    for (const k of ['avoir', 'nd', 'recu', 'relance', 'facture']) {
      if (langue === 'ar') expect.soft(nbArabe(t(k).texte), `ar ${k} : traduit (≥ 50 caractères arabes)`).toBeGreaterThanOrEqual(50)
      else expect.soft(nbArabe(t(k).texte), `fr ${k} : aucun arabe`).toBe(0)
    }
    for (const k of ['bc', 'proforma']) {
      if (langue === 'ar') expect.soft(t(k).texte, `ar ${k} : mention de repli imprimée`).toContain(REPLI_FR)
      else expect.soft(t(k).texte, `fr ${k} : aucune mention de repli`).not.toContain('uniquement')
    }
    // CLAUSE PERSISTANCE : les rendus ne changent ni la facture ni le devis.
    const apres = await lireFacture(page.request, brouillon.id)
    expect(apres.statut, `${langue} facture : statut inchangé par les rendus`).toBe(avant.statut)
    expect(apres.montant_du, `${langue} facture : dû inchangé`).toBe(avant.montant_du)
    expect((await lireDevis(page.request, d.id)).statut).toBe('accepte')
  }
  console.log(`[P4] ${notes.join(' | ')}`)
  suivi.verifie(7)
})

// ── P5 — documents chantier ──────────────────────────────────────────────────
etape('P5', ['APDF99', 'APDF33', 'APDF41', 'APDF42', 'APDF39'], async ({ page, suivi }) => {
  const C55 = 55 // CHT-202610-0001 : 7,10 kWc, nomenclature avec Installation + Transport (service)
  const C11 = 11 // CHT-202609-0001 : intervention démo de demo_tech
  const inter137 = await lireJson(await page.request.get(`${API}/installations/interventions/137/`, T), 'intervention démo')
  const techId = inter137.technicien
  const inter = await lireJson(await page.request.post(`${API}/installations/interventions/`, {
    ...T, data: { installation: C11, type_intervention: 'controle', technicien: techId, date_prevue: new Date().toISOString().slice(0, 10) },
  }), 'intervention')
  const crAvant = await telecharger(page.request, `installations/interventions/${inter.id}/compte-rendu/`)
  // Deux créneaux de la liste de prises de vue active (seules les photos rangées dans un
  // créneau sont rendues par le compte-rendu, `intervention_pdf._photos_payload`).
  const creneaux = (await lireJson(await page.request.get(`${API}/installations/interventions/${inter.id}/photos/`, T), 'créneaux photo'))
    .groupes.avant.map((c) => c.cle).slice(0, 2)
  expect(creneaux.length, 'deux créneaux « avant » dans la liste de prises de vue').toBe(2)
  for (const slot of creneaux) {
    const r = await page.request.post(`${API}/installations/interventions/${inter.id}/ajouter-photo/`, {
      ...T, multipart: { file: { name: `apdf99-${slot}.png`, mimeType: 'image/png', buffer: PNG_1PX }, slot },
    })
    expect(r.status(), `photo ${slot} : ${await r.text()}`).toBe(201)
  }
  const ticket = await lireJson(await page.request.post(`${API}/sav/tickets/`, {
    ...T, data: { client: 3, installation: C11, type: 'correctif', description: 'APDF99 rapport SAV', technicien_responsable: techId },
  }), 'ticket SAV')
  const profil = await lireJson(await page.request.get(`${API}/parametres/`, T), 'profil')
  const docs = {
    pv: await telecharger(page.request, `documents/chantiers/${C55}/pv-reception/`),
    bl: await telecharger(page.request, `documents/chantiers/${C55}/bon-livraison/`),
    remise: await telecharger(page.request, `documents/chantiers/${C55}/dossier-remise/`),
    cr_avant: crAvant,
    cr: await telecharger(page.request, `installations/interventions/${inter.id}/compte-rendu/`),
    sav: await telecharger(page.request, `sav/tickets/${ticket.id}/rapport-pdf/`),
    energie: await telecharger(page.request, `installations/chantiers/${C55}/rapport-energie/`),
  }
  const fz = analyserLot(Object.fromEntries(Object.entries(docs).map(([k, v]) => [`N_P5-${k}`, v.octets])))
  const t = (k) => fz[`N_P5-${k}`]
  const notes = Object.keys(docs).map((k) => `${k} ${t(k).pages} p. images ${t(k).images.reduce((a, b) => a + b, 0)}`)
  console.log(`[P5] ${notes.join(' | ')}`)
  for (const k of Object.keys(docs)) {
    sansDonneeInterne(t(k).texte, `P5 ${k}`)
    expect.soft(t(k).texte, `P5 ${k} : aucun identifiant de connexion`).not.toMatch(/demo_tech|demo_admin/)
  }
  // APDF33 / D-APDF-4 : prestations hors PV et BL ; section « Prestations » sans garantie.
  expect.soft(t('pv').texte.replace(/Installation photovolta[iï]que/g, ''), 'PV : aucune prestation « Installation »').not.toMatch(/\bInstallation\b/)
  expect.soft(t('pv').texte, 'PV : aucune prestation « Transport »').not.toContain('Transport')
  expect.soft(t('bl').texte, 'BL : aucune prestation « Transport »').not.toContain('Transport')
  expect.soft(t('remise').texte, 'remise : section Prestations').toContain('Prestations')
  // La section « Prestations » (après le tableau des garanties matériel) ne porte aucune garantie.
  const prestations = (t('remise').texte.split(/\nPrestations\n/)[1] || '').split(/Pièces du dossier/)[0]
  expect.soft(prestations, 'remise : section Prestations lue').toMatch(/Installation[\s\S]*Transport/)
  expect.soft(prestations, 'remise : aucune garantie sur une prestation').not.toMatch(/Garantie/i)
  // APDF37 / APDF41 : deux photos embarquées dans le compte-rendu.
  const img = (k) => t(k).images.reduce((a, b) => a + b, 0)
  expect.soft(img('cr') - img('cr_avant'), 'compte-rendu : une image par photo (2)').toBe(2)
  // APDF39 : tarif et puissance lus de Paramètres.
  const tarif = Number(profil.onee_tarif_kwh).toFixed(2)
  expect.soft(plat(t('energie').texte), `rapport énergie : tarif de Paramètres ${tarif} MAD/kWh`).toContain(`${tarif}MAD/kWh`)
  expect.soft(plat(t('energie').texte), 'rapport énergie : jamais le 1,40 codé').not.toContain('1.40MAD/kWh')
  expect.soft(plat(t('energie').texte), 'rapport énergie : 7,10 kWc').toContain('7.10')
  suivi.verifie(7)
})

// ── P6 — identité « SOLAIRE EXEMPLE SARL » (transaction annulée, sonde serveur) ─
etape('P6', ['APDF99', 'APDF45', 'APDF32'], async ({ page, suivi }) => {
  await devisAgricole(page)
  const ids = Object.fromEntries(Object.entries(MARCHES).map(([k, m]) => [k, m.id]))
  const code = `
import json, fitz, glob, os
from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.parametres.models import CompanyProfile
from apps.installations.models import Installation
from PIL import Image
u = get_user_model().objects.get(username='demo_admin')
IDS = ${JSON.stringify(ids)}
FORMATS = {'defaut': {}, 'onepage': {'pdf_mode': 'onepage'}, 'include_etude': {'include_etude': '1'},
           'devis_final': {'devis_final': '1'}, 'devis_final+include_etude': {'devis_final': '1', 'include_etude': '1'}}
INTERDITS = ['taqinor', 'Saham', '691213', '003799642000067', '022 780', 'Reda Kasri', 'Zerktouni', 'TAQINOR Démo']
import apps.ventes.quote_engine as qe
tailles = set()
for f in glob.glob(os.path.join(os.path.dirname(qe.__file__), '**', '*logo*'), recursive=True):
    try: tailles.add(Image.open(f).size)
    except Exception: pass
res = {'cas': [], 'chantier': [], 'tailles_logo': sorted(tailles)}
class Annule(Exception): pass
try:
    with transaction.atomic():
        p = CompanyProfile.get(company=u.company)
        for k, v in dict(nom='SOLAIRE EXEMPLE SARL', ice='001111111000011', identifiant_fiscal='IF-APDF99', rc='RC-APDF99',
                         patente='PAT-APDF99', rib='', banque='', site_web='', logo_key='', adresse='7 rue Exemple, Rabat',
                         telephone='+212 5 37 11 11 11', email='contact@solaire-exemple.test').items():
            setattr(p, k, v)
        p.save()
        c = APIClient(HTTP_HOST='localhost'); c.force_authenticate(u)
        for marche, did in IDS.items():
            for fmt, q in FORMATS.items():
                for langue in (['fr', 'ar'] if fmt == 'defaut' else ['fr']):
                    r = c.get(f'/api/django/ventes/devis/{did}/proposal/', {**q, 'langue': langue})
                    cas = {'marche': marche, 'format': fmt, 'langue': langue, 'http': r.status_code}
                    if r.status_code == 200:
                        doc = fitz.open(stream=b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content, filetype='pdf')
                        texte = '\\n'.join(pg.get_text() for pg in doc)
                        liens = [l.get('uri', '') for pg in doc for l in pg.get_links()]
                        sans_prop = '\\n'.join(x for x in texte.split('\\n') if '/proposition' not in x and '/proposal' not in x)
                        cas['lignes_lien_proposition'] = [x for x in texte.split('\\n') if 'taqinor' in x.lower() and ('/proposition' in x or '/proposal' in x)]
                        cas.update(pages=doc.page_count, titre=(doc.metadata or {}).get('title') or '',
                                   interdits=[m for m in INTERDITS if m.lower() in sans_prop.lower()],
                                   liens_taqinor=[l for l in liens if 'taqinor' in l.lower() and '/proposition/' not in l and '/proposal/' not in l],
                                   logo=[(i[2], i[3]) for pg in doc for i in pg.get_images(full=True) if (i[2], i[3]) in tailles],
                                   solaire='SOLAIRE EXEMPLE' in texte.upper())
                    res['cas'].append(cas)
        inst = Installation.objects.get(pk=55)
        for langue in ('fr', 'ar'):
            if langue == 'ar':
                inst.client.langue_document = 'ar'; inst.client.save(update_fields=['langue_document'])
            for route in ('bon-livraison', 'pv-reception', 'dossier-remise'):
                if langue == 'ar' and route != 'bon-livraison': continue
                r = c.get(f'/api/django/documents/chantiers/55/{route}/')
                ligne = {'route': route, 'langue': langue, 'http': r.status_code}
                if r.status_code == 200:
                    contenu = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
                    texte = '\\n'.join(pg.get_text() for pg in fitz.open(stream=contenu, filetype='pdf'))
                    ligne['manquants'] = [v for v in ('001111111000011', 'IF-APDF99', 'RC-APDF99', 'PAT-APDF99') if v not in texte]
                    ligne['interdits'] = [m for m in INTERDITS if m.lower() in texte.lower()]
                res['chantier'].append(ligne)
        raise Annule()
except Annule:
    pass
p = CompanyProfile.get(company=u.company)
res['profil_apres'] = {'nom': p.nom, 'ice': p.ice, 'rc': p.rc}
print('APDF99JSON' + json.dumps(res, ensure_ascii=False))
`
  const sortie = djangoConteneur(code)
  const res = JSON.parse(sortie.slice(sortie.lastIndexOf('APDF99JSON') + 'APDF99JSON'.length))
  console.log(`[P6] ${JSON.stringify(res)}`)
  for (const cas of res.cas) {
    const quoi = `${cas.marche} ${cas.format} ${cas.langue}`
    expect.soft(cas.http, `${quoi} : /proposal 200`).toBe(200)
    if (cas.http !== 200) continue
    expect.soft(cas.interdits, `${quoi} : aucune trace TAQINOR sous SOLAIRE EXEMPLE`).toEqual([])
    expect.soft(cas.liens_taqinor, `${quoi} : aucun lien taqinor.ma`).toEqual([])
    expect.soft(cas.titre.toUpperCase(), `${quoi} : titre du PDF`).not.toContain('TAQINOR')
    expect.soft(cas.logo, `${quoi} : aucune image à la taille d'un logo TAQINOR`).toEqual([])
    expect.soft(cas.solaire, `${quoi} : l'émetteur SOLAIRE EXEMPLE est nommé`).toBeTruthy()
  }
  for (const l of res.chantier) {
    expect.soft(l.http, `${l.route} ${l.langue} : 200`).toBe(200)
    expect.soft(l.manquants, `${l.route} ${l.langue} : ICE / IF / RC / patente du profil`).toEqual([])
    expect.soft(l.interdits, `${l.route} ${l.langue} : aucune trace TAQINOR`).toEqual([])
  }
  // Transaction annulée : le profil démo est intact.
  expect(res.profil_apres.nom, 'profil restauré').toBe('TAQINOR Démo')
  suivi.verifie(7)
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

// ── P8 — oracle 10 : audit_coherence sur les objets de la passe ──────────────
etape('P8', ['APDF99'], async ({ page, suivi, testInfo }) => {
  // Société démo seule (`taqinor-demo`) : la passe sur toute la base dépasse l'heure ici.
  testInfo.setTimeout(3_600_000)
  const sortie = execFileSync('docker', ['exec', CONTENEUR, 'python', 'manage.py', 'audit_coherence', '--company', 'taqinor-demo', '--json', '--no-persist'],
    { stdio: 'pipe', timeout: 3_300_000, maxBuffer: 512 * 1024 * 1024 }).toString()
  const res = JSON.parse(sortie.slice(sortie.indexOf('{')))
  const refs = REFS
  for (const m of Object.values(MARCHES)) if (m.id) REFS.add((await lireDevis(page.request, m.id)).reference)
  const ids = new Set([...Object.values(MARCHES).map((m) => m.id), p2.devis?.id].filter(Boolean))
  const miennes = res.violations.filter((v) => refs.has(v.reference) || (v.object_type === 'devis' && ids.has(v.object_id)))
  console.log(`[P8] violations totales ${res.violations.length}, sur les devis de la passe : ${JSON.stringify(miennes)}`)
  expect(miennes, 'audit_coherence : aucune violation sur les devis rendus par la passe').toEqual([])
  expect(res.rule_errors.filter((e) => ids.has(e.object_id)), 'aucune règle en erreur sur ces devis').toEqual([])
  suivi.verifie(10)
})
