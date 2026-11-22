// ACAL1315 — Comparaison PERMANENTE de l'écran réel avec les 13 maquettes du module Calepinage.
// Pour chaque maquette (`docs/audits/l5-calepinage/maquettes/<Nom>.dc.html`) :
//   1. la maquette est rendue en `file://` à sa taille native (1440×900 ; Tablette 1180×820 ; Telephone et
//      TelephoneClient 390×844) → `test-results/maquettes/<Nom>-maquette.png` ;
//   2. l'écran réel du même état, à la même taille → `<Nom>-reel.png` (et son texte visible `<Nom>-reel.txt`) ;
//   3. la spec ÉCHOUE si un LIBELLÉ FIXE de la maquette manque à l'écran réel. La liste vit dans
//      `calepinage-maquettes.libelles.json` (`attendus` + `acceptes_absents` avec leur raison) : changer une
//      maquette ou une différence acceptée = une édition relue de ce fichier, jamais un libellé retiré pour
//      passer au vert ;
//   4. `rapport.json` / `paires.json` : libellés trouvés / manquants, contrôles visibles, boîtes des blocs du
//      cadre des deux côtés (information seule).
// Aucune comparaison de pixels : le verdict FIDÈLE / PROCHE / ÉLOIGNÉ reste celui d'un relecteur neuf sur les paires.
// Auto-suffisante sur une pile fraîche (`seed_demo`) : le lead et le calepinage « K2 — » sont créés par l'API.
// Un état inatteignable sur une pile semée (résultat complet, résultat incomplet) est écrit « non atteint »
// avec sa raison, sans échec. Nocturne : jamais dans la liste par-PR de ci.yml (voir E2E_HOOKS.md).
import { test, expect } from '@playwright/test'
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { uniq, API_DJANGO, lireJson, telephoneMobileUnique } from './helpers'

const here = dirname(fileURLToPath(import.meta.url))
const DOSSIER_MAQUETTES = join(here, '../../docs/audits/l5-calepinage/maquettes')
const SORTIE = join(here, '../test-results/maquettes')
const LIBELLES = JSON.parse(readFileSync(join(here, 'calepinage-maquettes.libelles.json'), 'utf8'))
const SCHEMA_LAYOUT = join(here, '../../backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json')
const CAL = `${API_DJANGO}/calepinage`
const GRAND = [1440, 900]

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

const ATELIER = (etape, extra = {}) => ({ type: 'atelier', blocs: BLOCS_ATELIER, etape, ...extra })
const ECRANS = [
  { nom: 'Main', ...ATELIER('toit') },
  { nom: 'Panneaux', ...ATELIER('panneaux') },
  { nom: 'Electrique', ...ATELIER('electrique') },
  { nom: 'Schema', ...ATELIER(null, { chemin: (id) => `/calepinage/${id}?onglet=schema` }) },
  { nom: 'Resultats', ...ATELIER('resultats') },
  { nom: 'ResultatsIncomplet', ...ATELIER('resultats') },
  { nom: 'Documents', ...ATELIER('documents') },
  { nom: 'Liste', type: 'page', blocs: BLOCS_PAGE, chemin: () => '/calepinage', pret: 'text=Nouveau calepinage' },
  { nom: 'DemarrageRapide', type: 'page', blocs: BLOCS_PAGE, chemin: () => '/calepinage/reglages/demarrage-rapide', pret: 'text=Démarrage rapide' },
  { nom: 'ToitSombre', ...ATELIER('toit', { sombre: true }) },
  { nom: 'Tablette', vp: [1180, 820], ...ATELIER('panneaux') },
  { nom: 'Telephone', vp: [390, 844], type: 'page', blocs: BLOCS_PAGE, chemin: (id) => `/calepinage/${id}/releve`, pret: '[data-testid="releve-projet"]' },
  { nom: 'TelephoneClient', vp: [390, 844], type: 'page', blocs: BLOCS_PAGE, chemin: (id) => `/calepinage/${id}/client`, pret: '[data-testid="client-projet"]' },
]

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
  return { plein: document.body.innerText, items, controles, boites }
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

// Lead + calepinage + toit posé PAR L'API (le tracé à la souris n'est pas l'objet de cette spec).
let calId = null
async function assurerCalepinage(page) {
  if (calId) return calId
  await page.goto('/apps')
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible({ timeout: 60_000 })
  const T = { timeout: 120_000 }
  const request = page.request
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    ...T, data: { nom: uniq('K2 — Maquettes'), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '900' },
  }), 'lead')
  const cal = await lireJson(await request.post(`${CAL}/calepinages/`, { ...T, data: { lead: lead.id, titre: uniq('K2 — Maquettes') } }), 'calepinage')
  await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context (amorce)')
  const lu = await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout')
  const document = JSON.parse(readFileSync(SCHEMA_LAYOUT, 'utf8')).exemple
  await lireJson(await request.post(`${CAL}/calepinages/${cal.id}/layout/`, {
    ...T, headers: { 'If-Match': `"${lu.empreinte_document || ''}"` }, data: { roof_layout: document },
  }), 'écriture du layout')
  calId = cal.id
  return calId
}

async function rendreMaquette(context, ecran, vp) {
  const p = await context.newPage()
  await p.setViewportSize({ width: vp[0], height: vp[1] })
  await p.route(/^https?:/, (route) => route.abort()) // polices distantes : hors ligne, déterministe
  await p.goto(pathToFileURL(join(DOSSIER_MAQUETTES, `${ecran.nom}.dc.html`)).href, { waitUntil: 'domcontentloaded' })
  await expect.poll(() => p.evaluate(() => document.body.innerText.trim().length), { timeout: 30_000 }).toBeGreaterThan(20)
  await attendreStable(p)
  await p.screenshot({ path: join(SORTIE, `${ecran.nom}-maquette.png`) })
  const brut = await p.evaluate(lirePage, { blocs: ecran.blocs, cote: 'maquette', sel: SEL_CONTROLES })
  await p.close()
  return brut
}

async function ouvrirReel(page, ecran, id) {
  if (ecran.sombre) {
    await page.addInitScript(() => { try { localStorage.setItem('taqinor-theme', 'dark') } catch { /* ignoré */ } })
    await page.emulateMedia({ colorScheme: 'dark' })
  }
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

// Un fichier par écran (un test rouge relance le processus de test : rien ne doit vivre en mémoire entre deux écrans),
// fusionnés dans rapport.json / paires.json après chaque écran.
function ecrireRapports(rapportEcran) {
  mkdirSync(SORTIE, { recursive: true })
  const json = (v) => `${JSON.stringify(v, null, 2)}\n`
  if (rapportEcran) writeFileSync(join(SORTIE, `${rapportEcran.ecran}.rapport.json`), json(rapportEcran))
  const ecrans = ECRANS.map((e) => join(SORTIE, `${e.nom}.rapport.json`)).filter((p) => existsSync(p)).map((p) => JSON.parse(readFileSync(p, 'utf8')))
  writeFileSync(join(SORTIE, 'rapport.json'), json({ ecrans }))
  const paires = ecrans.map((r) => ({
    ecran: r.ecran, taille: r.taille, maquette: `${r.ecran}-maquette.png`, reel: `${r.ecran}-reel.png`,
    etat_atteint: r.etat_atteint, libelles_trouves: r.libelles_trouves, libelles_manquants: r.libelles_manquants,
  }))
  writeFileSync(join(SORTIE, 'paires.json'), json({ paires }))
}

for (const ecran of ECRANS) {
  test(`ACAL1315: ${ecran.nom} — la maquette et l'écran réel, libellés fixes`, async ({ page, context }) => {
    test.setTimeout(600_000)
    mkdirSync(SORTIE, { recursive: true })
    rmSync(join(SORTIE, `${ecran.nom}.rapport.json`), { force: true }) // jamais le rapport d'un run précédent
    const vp = ecran.vp || GRAND
    const donnees = LIBELLES[ecran.nom]
    expect(donnees, `libellés de « ${ecran.nom} » absents de calepinage-maquettes.libelles.json`).toBeTruthy()

    const maquette = preparer(await rendreMaquette(context, ecran, vp))
    // Garde de la liste : un libellé attendu doit exister dans la maquette elle-même (sinon la liste a dérivé).
    const orphelins = donnees.attendus.filter((l) => !trouve(l, maquette))
    expect(orphelins, `libellés attendus absents de la maquette « ${ecran.nom} » (liste à corriger)`).toEqual([])

    await page.setViewportSize({ width: vp[0], height: vp[1] })
    // Comme auth.setup.js : ni accueil « Bienvenue » ni bannière d'installation devant l'écran photographié.
    await page.addInitScript(() => {
      try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* ignoré */ }
      try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* ignoré */ }
    })
    const id = await assurerCalepinage(page)
    await ouvrirReel(page, ecran, id)
    await page.screenshot({ path: join(SORTIE, `${ecran.nom}-reel.png`) })
    const brut = await page.evaluate(lirePage, { blocs: ecran.blocs, cote: 'reel', sel: SEL_CONTROLES })
    writeFileSync(join(SORTIE, `${ecran.nom}-reel.txt`), brut.plein)
    const reel = preparer(brut)

    // État de la maquette atteint ? (résultat complet / incomplet : inatteignable sur une pile semée)
    const atteint = donnees.etat_ancre ? trouve(donnees.etat_ancre, reel) : true
    const trouves = donnees.attendus.filter((l) => trouve(l, reel))
    const manquants = donnees.attendus.filter((l) => !trouve(l, reel))
    const rapport = {
      ecran: ecran.nom,
      taille: `${vp[0]}x${vp[1]}`,
      url_reelle: page.url().replace(/^https?:\/\/[^/]+/, ''),
      etat_atteint: atteint,
      raison_non_atteint: atteint ? null : `l'écran réel ne montre pas l'état de la maquette (« ${donnees.etat_ancre} » absent) : aucun calepinage de la pile semée n'a de résultat de ce genre`,
      libelles_attendus: donnees.attendus.length,
      libelles_trouves: trouves,
      libelles_manquants: atteint ? manquants : [],
      libelles_non_evalues: atteint ? [] : manquants,
      acceptes_absents: donnees.acceptes_absents.map((a) => ({ ...a, present: trouve(a.libelle, reel) })),
      controles_visibles: { maquette: maquette.controles, reel: reel.controles },
      boites: Object.fromEntries(ecran.blocs.map((b) => [b.nom, { maquette: maquette.boites[b.nom], reel: reel.boites[b.nom] }])),
    }
    ecrireRapports(rapport)

    if (!atteint) {
      test.info().annotations.push({ type: 'non atteint', description: rapport.raison_non_atteint })
      return
    }
    expect(manquants, `Écran « ${ecran.nom} » : libellé(s) fixe(s) de la maquette absent(s) de l'écran réel`).toEqual([])
  })
}
