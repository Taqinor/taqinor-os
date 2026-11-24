// ACAL1315 / ACAL1748 / ACAL1806 — Comparaison PERMANENTE de l'écran réel avec les QUATORZE maquettes v2 du module Calepinage
// (`docs/audits/l5-calepinage/maquettes-v2/<Nom>.dc.html`, tailles natives dans `maquettes-v2/canvas.json`).
//
// UNE COMMANDE rend les 14 planches contre une pile qui tourne (un `vite preview` proxy vers une API, ou la pile de la CI) :
//   cd frontend && E2E_BASE_URL=http://127.0.0.1:<port> CAL_MAQUETTES_SORTIE=<dossier> \
//     node node_modules/@playwright/test/cli.js test e2e/calepinage-maquettes.spec.js --project=chromium
// `CAL_MAQUETTES_SORTIE` (défaut `frontend/test-results/maquettes`) reçoit les images. Ajouter `--no-deps` pour ne pas rejouer
// le projet `setup` quand `e2e/.auth/admin.json` existe déjà pour le compte voulu (pile de revue). `-g <Nom>` = un seul écran.
//
// Pour chaque écran, la spec écrit dans le dossier de sortie :
//   <Nom>-v2.png     la maquette v2, rendue en `file://` à sa taille native (hors ligne : toute requête http(s) est coupée ;
//                    `support.js`, absent du dossier, n'est PAS nécessaire — les maquettes sont du HTML/CSS statique) ;
//   <Nom>-v1.png     la maquette v1 du même écran quand elle existe (aucune pour « Presentation ») ;
//   <Nom>-reel.png   l'écran réel, MÊME taille, MÊME état que la maquette (étape, thème sombre, tablette 1180 × 820, téléphone
//                    390 × 844 avec écran tactile, Présentation = la route client à 1440 × 900) ; <Nom>-reel.txt = son texte visible ;
//   <Nom>-planche.png  UNE planche « maquette v2 | réel » avec une légende (état atteint ou NON ATTEINT et pourquoi, banc, libellés) ;
//   <Nom>-trio.png   la planche « v1 | v2 | réel » ;
//   <Nom>.rapport.json, rapport.json, paires.json : libellés trouvés / manquants, contrôles visibles, boîtes des blocs du cadre
//                    des deux côtés, débordement horizontal (information seule).
// La spec ÉCHOUE si un LIBELLÉ FIXE de la v2 manque à l'écran réel (liste `calepinage-maquettes.libelles.json` : `attendus` +
// `acceptes_absents` avec leur raison + `etat_ancre`) : changer une maquette ou une différence acceptée = une édition relue de ce
// fichier, jamais un libellé retiré pour passer au vert. Aucune comparaison de pixels : le verdict FIDÈLE / PROCHE / ÉLOIGNÉ reste
// celui d'un relecteur neuf sur les planches. Un état qui ne peut pas être atteint sur une pile (pas de matériel au catalogue,
// simulation trop longue, réglages de la société qui empêchent un résultat complet, société déjà réglée) est écrit « NON ATTEINT »
// avec sa raison dans la légende de la planche et dans le rapport — sans échec. Le banc (lead avec point de site, calepinage,
// matériel, série météo synthétique, simulation) est posé par l'API : voir `calepinage-maquettes.banc.js`.
// Jamais dans la liste par-PR de ci.yml (voir E2E_HOOKS.md). À LA DEMANDE tant que les écrans ne sont pas fidèles : les
// quatorze planches ne se jouent que si `CAL_MAQUETTES_SORTIE` est posé (la commande ci-dessus le pose) — sans cela le
// nocturne `release-verify` (`npx playwright test`) rougirait chaque nuit sur des libellés que le relecteur neuf suit déjà
// planche par planche (24/11/2026 : 5 écrans verts, 9 rouges sur des libellés de maquette). Retirer ce garde-fou quand la
// spec passe en entier contre une pile de revue.
import { test, expect } from '@playwright/test'
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { AUTH_FILE, API_DJANGO, rafraichirEtatPartage } from './helpers'
import { poserBanc } from './calepinage-maquettes.banc'

const here = dirname(fileURLToPath(import.meta.url))
const DOSSIER_V2 = join(here, '../../docs/audits/l5-calepinage/maquettes-v2')
const DOSSIER_V1 = join(here, '../../docs/audits/l5-calepinage/maquettes')
const SORTIE = resolve(process.env.CAL_MAQUETTES_SORTIE || join(here, '../test-results/maquettes'))
const FICHIER_BANC = join(here, '../test-results/.banc-maquettes.json') // survit au redémarrage du processus d'un test rouge, dans UN run
const LIBELLES = JSON.parse(readFileSync(join(here, 'calepinage-maquettes.libelles.json'), 'utf8'))
const SCHEMA_LAYOUT = join(here, '../../backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json')
const lireCanvas = (dossier) => (existsSync(join(dossier, 'canvas.json')) ? JSON.parse(readFileSync(join(dossier, 'canvas.json'), 'utf8')) : { boards: {}, order: [] })
const CANVAS_V2 = lireCanvas(DOSSIER_V2)
const CANVAS_V1 = lireCanvas(DOSSIER_V1)
const CAL = `${API_DJANGO}/calepinage`

// Blocs du cadre : sélecteur réel (data-testid / id) et sélecteur de la maquette (balises sémantiques).
// `dernier` : l'élément le plus BAS (puis le plus large) parmi ceux qui correspondent — le bouton du pied du panneau, le bouton du bandeau.
const BLOCS_ATELIER = [
  { nom: 'bandeau', reel: '[data-testid="cal-barre-projet"]', maquette: 'header' },
  { nom: 'rail', reel: '[data-testid="cal-rail-etapes"]', maquette: 'nav[aria-label="Étapes"]' },
  { nom: 'carte', reel: '#rp9-studio-scene', maquette: 'main' },
  { nom: 'outils_carte', reel: '[data-testid="cal-barre-outils-carte"]', maquette: '[role="toolbar"]' },
  { nom: 'panneau', reel: '[data-testid="cal-panneau-etape"]', maquette: 'aside' },
  { nom: 'bouton_pied_panneau', reel: '[data-testid="cal-action-etape-suivante"]', maquette: 'aside button', dernier: true },
  { nom: 'bouton_devis', reel: '[data-testid="cal-bouton-devis"], [data-testid="cal-generer-devis"]', maquette: 'header button', dernier: true },
]
const BLOCS_PAGE = [
  { nom: 'titre', reel: 'h1, h2', maquette: 'h1, h2' },
  { nom: 'contenu', reel: 'main', maquette: 'main, [role="main"]' },
  { nom: 'premier_bouton', reel: 'button', maquette: 'button' },
]

// `besoin` : ce que l'état de la maquette suppose du banc (matériel désigné, simulation terminée) ; `variante` du banc ;
// `tactile` : écran tactile (téléphone, tablette) ; `sombre` : thème sombre. La taille vient de `canvas.json` de la v2.
const ATELIER = (etape, extra = {}) => ({ type: 'atelier', blocs: BLOCS_ATELIER, etape, ...extra })
const PAGE = (extra) => ({ type: 'page', blocs: BLOCS_PAGE, ...extra })
const ECRANS = [
  { nom: 'Main', ...ATELIER('toit') },
  { nom: 'Panneaux', ...ATELIER('panneaux', { besoin: 'simulation' }) },
  { nom: 'Electrique', ...ATELIER('electrique', { besoin: 'simulation' }) },
  { nom: 'Schema', ...ATELIER(null, { chemin: (id) => `/calepinage/${id}?onglet=schema`, besoin: 'simulation' }) },
  { nom: 'Resultats', ...ATELIER('resultats', { besoin: 'simulation' }) },
  { nom: 'ResultatsIncomplet', ...ATELIER('resultats', { besoin: 'simulation' }) },
  { nom: 'Documents', ...ATELIER('documents', { besoin: 'simulation' }) },
  { nom: 'ToitSombre', ...ATELIER('toit', { sombre: true }) },
  { nom: 'Liste', ...PAGE({ chemin: () => '/calepinage', pret: 'text=Nouveau calepinage', sansBanc: true }) },
  { nom: 'DemarrageRapide', ...PAGE({ chemin: () => '/calepinage/reglages/demarrage-rapide', pret: 'text=Démarrage rapide', sansBanc: true }) },
  { nom: 'Presentation', ...PAGE({ chemin: (id) => `/calepinage/${id}/client`, pret: '[data-testid="client-projet"]', besoin: 'simulation' }) },
  { nom: 'Tablette', ...ATELIER('panneaux', { tactile: true, besoin: 'simulation' }) },
  { nom: 'Telephone', ...PAGE({ chemin: (id) => `/calepinage/${id}/releve`, pret: '[data-testid="releve-projet"]', tactile: true, variante: 'releve' }) },
  { nom: 'TelephoneClient', ...PAGE({ chemin: (id) => `/calepinage/${id}/client`, pret: '[data-testid="client-projet"]', tactile: true, besoin: 'simulation' }) },
]
const tailleV2 = (nom) => {
  const b = CANVAS_V2.boards[`${nom}.dc.html`]
  return b ? [b.w, b.h] : null
}
const tailleV1 = (nom) => {
  const b = CANVAS_V1.boards[`${nom}.dc.html`]
  return b ? [b.w, b.h] : tailleV2(nom)
}

// ── Lecture d'une page (exécutée DANS la page, maquette ou réelle) ──
const SEL_CONTROLES = 'button, a[href], input, select, textarea, [role=tab]'
function lirePage({ blocs, cote, sel }) {
  const visible = (el) => {
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.display === 'none') return false
    if (cs.display === 'contents') return true
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  }
  const items = []
  for (const el of document.body.querySelectorAll('*')) {
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || !visible(el)) continue
    items.push([...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' '))
    for (const a of ['aria-label', 'title', 'placeholder']) if (el.getAttribute(a)) items.push(el.getAttribute(a))
    if (el.tagName === 'INPUT' && el.value) items.push(el.value)
  }
  const vw = window.innerWidth
  const vh = window.innerHeight
  const controles = [...document.querySelectorAll(sel)].filter((el) => {
    if (!visible(el)) return false
    const r = el.getBoundingClientRect()
    return r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw
  }).length
  const boites = {}
  for (const b of blocs) {
    const css = b[cote]
    const trouves = [...document.querySelectorAll(css)].filter(visible)
    trouves.sort((a, c) => (b.dernier ? (c.getBoundingClientRect().bottom - a.getBoundingClientRect().bottom) || (c.getBoundingClientRect().width - a.getBoundingClientRect().width) : 0))
    const el = trouves[0]
    const r = el?.getBoundingClientRect()
    boites[b.nom] = r ? { x: Math.round(r.x), y: Math.round(r.y), l: Math.round(r.width), h: Math.round(r.height) } : null
  }
  return { plein: document.body.innerText, items, controles, boites, debordement_horizontal: document.documentElement.scrollWidth > vw + 1 }
}

const norm = (s) => String(s).normalize('NFC') // le motif d'espace couvre déjà les espaces insécables et fines
  .replace(/[’‘]/g, "'").replace(/\s+/g, ' ').trim().toLowerCase()

/** Un libellé d'un seul mot doit être le texte PROPRE d'un élément (« Toit » ne se satisfait pas de « Toiture ») ;
 *  un libellé de plusieurs mots est cherché dans le texte visible de la page et dans les attributs lisibles. */
function trouve(libelle, lecture) {
  const l = norm(libelle)
  if (!/\s/.test(l)) return lecture.itemsNorm.has(l)
  return lecture.foin.includes(l)
}

function preparer(brut) {
  const itemsNorm = new Set(brut.items.map(norm).filter(Boolean))
  return { ...brut, itemsNorm, foin: `${norm(brut.plein)} | ${[...itemsNorm].join(' | ')}` }
}

// ── Attentes sans pause fixe : on attend un ÉTAT ──
async function attendreStable(page, mesure = (p) => p.evaluate(() => `${document.body.innerText.length}|${document.querySelectorAll('*').length}`)) {
  await page.waitForLoadState('networkidle').catch(() => { /* réseau jamais calme : la stabilité du texte tranche */ })
  let precedent = null
  let egales = 0
  await expect.poll(async () => {
    const v = await mesure(page)
    egales = v === precedent ? egales + 1 : 0
    precedent = v
    return egales
  }, { intervals: [500], timeout: 90_000 }).toBeGreaterThanOrEqual(4)
}

async function attendreAtelier(page) {
  await expect(page.getByTestId('cal-rail-etapes')).toBeVisible({ timeout: 240_000 })
  // Sans clé de carte (CI) l'atelier n'amorce pas la carte : ses panneaux se rendent quand même.
  await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/, { timeout: 60_000 }).catch(() => { /* carte absente */ })
}

// ── Le banc : posé UNE fois par variante, partagé entre les écrans (et entre deux processus d'un même run) ──
const bancs = {}
async function banc(request, variante) {
  if (bancs[variante]) return bancs[variante]
  let fichier = {}
  try { fichier = JSON.parse(readFileSync(FICHIER_BANC, 'utf8')) } catch { /* premier écran du run */ }
  const connu = fichier[variante]
  if (connu && (await request.get(`${CAL}/calepinages/${connu.calId}/`)).ok()) {
    bancs[variante] = connu
    return connu
  }
  const exemple = JSON.parse(readFileSync(SCHEMA_LAYOUT, 'utf8')).exemple
  bancs[variante] = await poserBanc(request, { exemple, variante })
  mkdirSync(dirname(FICHIER_BANC), { recursive: true })
  writeFileSync(FICHIER_BANC, JSON.stringify({ ...fichier, [variante]: bancs[variante] }))
  return bancs[variante]
}

async function rendreMaquette(context, dossier, ecran, vp, fichierPng) {
  const p = await context.newPage()
  try {
    await p.setViewportSize({ width: vp[0], height: vp[1] })
    await p.route(/^https?:/, (route) => route.abort()) // polices distantes : hors ligne, déterministe
    await p.goto(pathToFileURL(join(dossier, `${ecran.nom}.dc.html`)).href, { waitUntil: 'domcontentloaded' })
    await expect.poll(() => p.evaluate(() => document.body.innerText.trim().length), { timeout: 30_000 }).toBeGreaterThan(20)
    await attendreStable(p)
    await p.screenshot({ path: fichierPng })
    return await p.evaluate(lirePage, { blocs: ecran.blocs || BLOCS_PAGE, cote: 'maquette', sel: SEL_CONTROLES })
  } finally {
    await p.close()
  }
}

async function ouvrirReel(page, ecran, id) {
  await page.goto(ecran.chemin ? ecran.chemin(id) : `/calepinage/${id}`)
  if (ecran.type === 'atelier') {
    await attendreAtelier(page)
    if (ecran.etape) {
      const tuile = page.getByTestId(`cal-etape-${ecran.etape}`)
      await expect(tuile).toBeVisible()
      await tuile.click()
    }
  } else {
    await expect(page.locator(ecran.pret).first()).toBeVisible({ timeout: 120_000 })
  }
  await attendreStable(page)
}

// ── La planche : les images posées côte à côte, à leur taille native, sous une légende ──
const echapper = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const base64 = (png) => readFileSync(png).toString('base64')
async function ecrirePlanche(context, { titre, lignes, colonnes, sortie }) {
  const largeur = colonnes.reduce((s, c) => s + c.largeur, 0) + 24 * (colonnes.length + 1)
  const hauteurImg = Math.max(...colonnes.map((c) => c.hauteur))
  const corps = colonnes.map((c) => `<figure><figcaption>${echapper(c.titre)}</figcaption>${c.png
    ? `<img width="${c.largeur}" height="${c.hauteur}" src="data:image/png;base64,${base64(c.png)}">`
    : `<div class="vide" style="width:${c.largeur}px;height:${c.hauteur}px">${echapper(c.absent || 'absent')}</div>`}</figure>`).join('')
  const html = `<!doctype html><meta charset="utf-8"><style>
    body{margin:0;padding:24px;background:#1b2036;color:#f1f3f9;font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;width:${largeur - 48}px}
    h1{font-size:22px;margin:0 0 8px}.l{margin:2px 0;color:#c9cee0}.l b{color:#fff}.ko{color:#ffb4a8}.ok{color:#a8e6b8}
    .row{display:flex;gap:24px;margin-top:16px;align-items:flex-start}figure{margin:0}figcaption{font-weight:600;margin:0 0 6px;color:#e7c25a}
    img{display:block;border:1px solid #4a5170}.vide{display:flex;align-items:center;justify-content:center;border:1px dashed #4a5170;color:#8a91ab;box-sizing:border-box}
  </style><h1>${echapper(titre)}</h1>${lignes.map((l) => `<div class="l ${l.classe || ''}">${l.texte}</div>`).join('')}<div class="row" style="min-height:${hauteurImg}px">${corps}</div>`
  const p = await context.newPage()
  try {
    await p.setViewportSize({ width: largeur, height: 400 })
    await p.setContent(html, { waitUntil: 'load' })
    await p.screenshot({ path: sortie, fullPage: true })
  } finally {
    await p.close()
  }
}

// Un fichier par écran (un test rouge relance le processus de test : rien ne doit vivre en mémoire entre deux écrans),
// fusionnés dans rapport.json / paires.json après chaque écran.
function ecrireRapports(rapportEcran) {
  mkdirSync(SORTIE, { recursive: true })
  const json = (v) => `${JSON.stringify(v, null, 2)}\n`
  if (rapportEcran) writeFileSync(join(SORTIE, `${rapportEcran.ecran}.rapport.json`), json(rapportEcran))
  const ecrans = ECRANS.map((e) => join(SORTIE, `${e.nom}.rapport.json`)).filter((p) => existsSync(p)).map((p) => JSON.parse(readFileSync(p, 'utf8')))
  writeFileSync(join(SORTIE, 'rapport.json'), json({ ecrans }))
  const paires = ecrans.map((r) => ({
    ecran: r.ecran, taille: r.taille, v2: `${r.ecran}-v2.png`, v1: r.v1_disponible ? `${r.ecran}-v1.png` : null, reel: `${r.ecran}-reel.png`,
    planche: `${r.ecran}-planche.png`, trio: `${r.ecran}-trio.png`, etat_atteint: r.etat_atteint, raison_non_atteint: r.raison_non_atteint,
    libelles_trouves: r.libelles_trouves, libelles_manquants: r.libelles_manquants,
  }))
  writeFileSync(join(SORTIE, 'paires.json'), json({ paires }))
}

test('ACAL1806: les quatorze écrans de la v2 (canvas.json) sont tous comparés, chacun avec sa liste de libellés', () => {
  const dansCanvas = CANVAS_V2.order.map((f) => f.replace(/\.dc\.html$/, ''))
  expect(dansCanvas, 'écrans de maquettes-v2/canvas.json').toHaveLength(14)
  expect(ECRANS.map((e) => e.nom), 'écrans comparés par la spec').toEqual(dansCanvas)
  for (const nom of dansCanvas) {
    expect(existsSync(join(DOSSIER_V2, `${nom}.dc.html`)), `maquette v2 « ${nom} » absente du dossier`).toBe(true)
    expect(LIBELLES[nom], `libellés de « ${nom} » absents de calepinage-maquettes.libelles.json`).toBeTruthy()
    expect(tailleV2(nom), `taille native de « ${nom} » absente de canvas.json`).toBeTruthy()
  }
})

for (const ecran of ECRANS) {
  test(`ACAL1806: ${ecran.nom} : planche maquette v2 | réel écrite, libellés fixes`, async ({ browser, baseURL, playwright }) => {
    test.skip(!process.env.CAL_MAQUETTES_SORTIE, 'banc des maquettes à la demande : poser CAL_MAQUETTES_SORTIE (voir l’en-tête)')
    test.setTimeout(600_000)
    mkdirSync(SORTIE, { recursive: true })
    rmSync(join(SORTIE, `${ecran.nom}.rapport.json`), { force: true }) // jamais le rapport d'un run précédent
    const vp = tailleV2(ecran.nom)
    const donnees = LIBELLES[ecran.nom]
    expect(vp, `taille native de « ${ecran.nom} » absente de maquettes-v2/canvas.json`).toBeTruthy()
    expect(donnees, `libellés de « ${ecran.nom} » absents de calepinage-maquettes.libelles.json`).toBeTruthy()
    const png = (suffixe) => join(SORTIE, `${ecran.nom}-${suffixe}.png`)

    // 1. Les maquettes, dans un contexte simple (rendues comme dessinées : ni tactile ni thème de l'ERP).
    const contexteMaquette = await browser.newContext({ viewport: { width: vp[0], height: vp[1] }, deviceScaleFactor: 1 })
    let v2
    const v1Disponible = existsSync(join(DOSSIER_V1, `${ecran.nom}.dc.html`))
    try {
      v2 = preparer(await rendreMaquette(contexteMaquette, DOSSIER_V2, ecran, vp, png('v2')))
      if (v1Disponible) await rendreMaquette(contexteMaquette, DOSSIER_V1, ecran, tailleV1(ecran.nom), png('v1'))
    } finally {
      await contexteMaquette.close()
    }
    // Garde de la liste : un libellé attendu doit exister dans la maquette v2 elle-même (sinon la liste a dérivé).
    const orphelins = donnees.attendus.filter((l) => !trouve(l, v2))
    expect(orphelins, `libellés attendus absents de la maquette v2 « ${ecran.nom} » (liste à corriger)`).toEqual([])

    // 2. L'écran réel, dans le MÊME état : taille native, tactile pour le téléphone et la tablette, thème sombre pour ToitSombre.
    await rafraichirEtatPartage(playwright, baseURL)
    const contexteReel = await browser.newContext({
      baseURL, storageState: AUTH_FILE, viewport: { width: vp[0], height: vp[1] }, deviceScaleFactor: 1,
      ...(ecran.tactile ? { hasTouch: true, isMobile: true } : {}),
      ...(ecran.sombre ? { colorScheme: 'dark' } : {}),
    })
    let atelier = null
    let lecture = null
    let erreurReel = null
    let reel = null
    let leBanc = null
    try {
      // Comme auth.setup.js : ni accueil « Bienvenue » ni bannière d'installation devant l'écran photographié.
      await contexteReel.addInitScript(() => {
        try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* ignoré */ }
        try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* ignoré */ }
      })
      if (ecran.sombre) await contexteReel.addInitScript(() => { try { localStorage.setItem('taqinor-theme', 'dark') } catch { /* ignoré */ } })
      atelier = await contexteReel.newPage()
      if (ecran.sansBanc) {
        await ouvrirReel(atelier, ecran, null) // écran sans calepinage (liste, démarrage rapide)
      } else {
        leBanc = await banc(contexteReel.request, ecran.variante || 'complet')
        await ouvrirReel(atelier, ecran, leBanc.calId)
      }
      await atelier.screenshot({ path: png('reel') })
      lecture = await atelier.evaluate(lirePage, { blocs: ecran.blocs, cote: 'reel', sel: SEL_CONTROLES })
      writeFileSync(join(SORTIE, `${ecran.nom}-reel.txt`), lecture.plein)
      reel = preparer(lecture)
    } catch (e) {
      erreurReel = e
    } finally {
      await contexteReel.close()
    }

    // 3. L'état de la maquette est-il atteint ? (ancre de la liste + ce que le banc a pu poser)
    let raison = null
    if (erreurReel) {
      raison = `écran réel NON photographié : ${String(erreurReel.message).split('\n')[0].slice(0, 200)}`
    } else if (ecran.besoin === 'simulation' && leBanc && leBanc.simulation.etat !== 'terminee') {
      raison = `le banc n'a pas de simulation terminée : ${leBanc.simulation.raison}`
    } else if (donnees.etat_ancre && !trouve(donnees.etat_ancre, reel)) {
      raison = `l'écran réel ne montre pas l'état de la maquette (« ${donnees.etat_ancre} » absent) : ${ecran.besoin ? 'les réglages de la société de la pile ne donnent pas ce résultat' : 'la société de la pile n’est pas dans l’état de la maquette (réglages déjà posés)'}`
    }
    const atteint = !raison
    const trouves = reel ? donnees.attendus.filter((l) => trouve(l, reel)) : []
    const manquants = reel ? donnees.attendus.filter((l) => !trouve(l, reel)) : donnees.attendus
    const rapport = {
      ecran: ecran.nom,
      taille: `${vp[0]}x${vp[1]}`,
      tactile: !!ecran.tactile,
      theme: ecran.sombre ? 'sombre' : 'clair',
      v1_disponible: v1Disponible,
      url_reelle: atelier && !erreurReel ? atelier.url().replace(/^https?:\/\/[^/]+/, '') : null,
      banc: leBanc ? { calepinage: leBanc.calId, variante: leBanc.variante, materiel: leBanc.materiel, simulation: leBanc.simulation } : null,
      etat_atteint: atteint,
      raison_non_atteint: raison,
      libelles_attendus: donnees.attendus.length,
      libelles_trouves: trouves,
      libelles_manquants: atteint ? manquants : [],
      libelles_non_evalues: atteint ? [] : manquants,
      acceptes_absents: reel ? donnees.acceptes_absents.map((a) => ({ ...a, present: trouve(a.libelle, reel) })) : [],
      controles_visibles: { maquette: v2.controles, reel: reel?.controles ?? null },
      debordement_horizontal_reel: lecture?.debordement_horizontal ?? null,
      boites: Object.fromEntries((ecran.blocs || BLOCS_PAGE).map((b) => [b.nom, { maquette: v2.boites[b.nom], reel: lecture?.boites[b.nom] ?? null }])),
    }
    ecrireRapports(rapport)

    // 4. La planche (écrite AVANT toute assertion : un écran rouge a aussi sa planche).
    const contextePlanche = await browser.newContext({ deviceScaleFactor: 1 })
    try {
      const resume = erreurReel ? 'écran réel non photographié' : (atteint
        ? `${trouves.length}/${donnees.attendus.length} libellés fixes de la v2 trouvés${manquants.length ? ` ; MANQUENT : ${manquants.join(' · ')}` : ''}`
        : `${trouves.length}/${donnees.attendus.length} libellés trouvés (non évalués : état non atteint)`)
      const lignes = [
        atteint
          ? { texte: `<b>État atteint</b> : l'écran réel est dans l'état de la maquette.`, classe: 'ok' }
          : { texte: `<b>NON ATTEINT</b> : ${echapper(raison)}`, classe: 'ko' },
        { texte: `<b>Libellés</b> : ${echapper(resume)}`, classe: manquants.length && atteint ? 'ko' : '' },
        ...(leBanc ? [{ texte: `<b>Banc</b> : calepinage ${leBanc.calId} (${leBanc.variante}) · matériel : ${echapper(leBanc.materiel ? (leBanc.materiel.ok ? `${leBanc.materiel.module} + ${leBanc.materiel.onduleur}` : leBanc.materiel.raison) : 'sans objet')} · simulation : ${echapper(leBanc.simulation.etat)}${leBanc.simulation.raison ? ` (${echapper(leBanc.simulation.raison)})` : ''} · le banc ne pose ni cheminement de câble ni matrice d'ombrage et ne règle rien sur la société` }] : []),
        { texte: `<b>Taille</b> : ${vp[0]} × ${vp[1]}${ecran.tactile ? ' · tactile' : ''}${ecran.sombre ? ' · thème sombre' : ''}${lecture?.debordement_horizontal ? ' · <span class="ko">débordement horizontal</span>' : ''}` },
      ]
      const colonneReel = { titre: `réel · ${ecran.nom}${atteint ? '' : ' (état non atteint)'}`, largeur: vp[0], hauteur: vp[1], png: erreurReel ? null : png('reel'), absent: 'écran réel non photographié' }
      const colonneV2 = { titre: `maquette v2 · ${ecran.nom}`, largeur: vp[0], hauteur: vp[1], png: png('v2') }
      const titre = `${ecran.nom} — maquette v2 | réel`
      await ecrirePlanche(contextePlanche, { titre, lignes, colonnes: [colonneV2, colonneReel], sortie: png('planche') })
      const t1 = tailleV1(ecran.nom)
      await ecrirePlanche(contextePlanche, {
        titre: `${ecran.nom} — maquette v1 | maquette v2 | réel`,
        lignes,
        colonnes: [
          v1Disponible
            ? { titre: `maquette v1 · ${ecran.nom}`, largeur: t1[0], hauteur: t1[1], png: png('v1') }
            : { titre: 'maquette v1', largeur: vp[0], hauteur: vp[1], png: null, absent: `pas de maquette v1 pour « ${ecran.nom} »` },
          colonneV2,
          colonneReel,
        ],
        sortie: png('trio'),
      })
    } finally {
      await contextePlanche.close()
    }

    if (erreurReel) throw erreurReel
    if (!atteint) {
      test.info().annotations.push({ type: 'non atteint', description: raison })
      return
    }
    expect(manquants, `Écran « ${ecran.nom} » : libellé(s) fixe(s) de la maquette v2 absent(s) de l'écran réel`).toEqual([])
  })
}
