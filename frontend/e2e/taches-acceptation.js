// Aides de l'ACCEPTATION EN DIRECT « Tâches » (TCH136-TCH140, TCH144 — `e2e/acceptation/tch.spec.js`).
//
// Ce que ce module fait, et seulement ça :
//   - poser un SCÉNARIO sur la pile : semis `seed_taches_demo --reinitialiser <options>` puis horloge du serveur
//     (commande `E2E_TACHES_PILE`, jamais un chemin en dur) ; le semis n'est rejoué que si l'étape d'avant a pu
//     écrire (une étape en lecture seule laisse la pile propre pour la suivante) ;
//   - ouvrir une page NEUVE, connectée en `demo_taches` (mot de passe lu dans `TACHES_DEMO_PASSWORD`, jamais
//     écrit), à l'heure du scénario côté NAVIGATEUR aussi (`page.clock.install` avant le premier `goto`), en vue
//     iPhone (390 × 844, tactile) ou bureau (1440 × 900), fuseau `UTC` par défaut (le Maroc est à GMT toute l'année
//     depuis le 20/09/2026 ; le Chromium de la machine a des fuseaux périmés) ;
//   - les gestes tactiles au doigt (balayage, appui long) par des événements pointeur `pointerType: 'touch'` ;
//   - les captures de relecture visuelle (iPhone et bureau, clair et sombre) hors du dépôt.
// Aucune attente fixe : on attend un état visible ou une réponse observée.
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { test, expect } from '@playwright/test'

export const COMPTE = 'demo_taches'
export const API = '/api/django/taches'
export const DOSSIER_CAPTURES = '/opt/taches-cloud/captures/f2'

const UA_IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
  + 'Version/17.0 Mobile/15E148 Safari/604.1'
export const VUES = {
  iphone: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, userAgent: UA_IPHONE },
  bureau: { viewport: { width: 1440, height: 900 } },
}

// --- La pile : semis et horloge ----------------------------------------------------------------------------------

/** Lance la commande de pile (`acc.sh`) ; sa sortie est rendue (diagnostic d'un semis refusé). */
export function pile(...args) {
  const commande = process.env.E2E_TACHES_PILE
  if (!commande) throw new Error('E2E_TACHES_PILE absent : la commande de pile des acceptations Tâches est requise')
  return execFileSync(commande, args, { encoding: 'utf8', timeout: 900_000, stdio: ['ignore', 'pipe', 'pipe'] })
}

let etat = { semis: null, horloge: null, propre: false }

/** Pose le scénario `semis` (options de `seed_taches_demo`, `--reinitialiser` ajouté) à l'heure `horloge`
 *  (« AAAA-MM-JJ HH:MM » du Maroc, ou « reel »). `lecture: true` = l'étape n'écrit rien : la suivante pourra
 *  réutiliser la pile sans semer de nouveau. Rend l'instant ISO à donner au navigateur. */
export function scenario(semis, horloge, { lecture = false } = {}) {
  const cle = semis.join(' ')
  if (etat.semis !== cle || !etat.propre) {
    pile('semer', '--reinitialiser', ...semis)
    etat = { semis: cle, horloge: null, propre: true }
  }
  if (etat.horloge !== horloge) {
    pile('horloge', horloge)
    etat.horloge = horloge
  }
  if (!lecture) etat.propre = false
  return horloge === 'reel' ? null : `${horloge.replace(' ', 'T')}:00Z`
}

/** Une étape a écrit hors de `scenario` (ou a échoué au milieu) : la suivante sèmera de nouveau. */
export function salir() { etat.propre = false }

// --- Pages connectées ---------------------------------------------------------------------------------------------

const contextes = []
// Fermés APRÈS chaque test (donc après la capture de l'étape, prise dans le corps du test par le harnais).
test.afterEach(async () => {
  for (const c of contextes.splice(0)) await c.close().catch(() => undefined)
})

/** Connexion API (cookies posés dans le contexte) ; le throttle « login » peut répondre 429 : on réessaie. */
export async function connecter(requete, username = COMPTE, password = process.env.TACHES_DEMO_PASSWORD) {
  expect(password, 'TACHES_DEMO_PASSWORD (posée par la commande de pile)').toBeTruthy()
  await expect(async () => {
    const res = await requete.post('/api/django/token/', { data: { username, password } })
    expect(res.status(), `connexion de ${username}`).toBe(200)
  }).toPass({ intervals: [5_000, 10_000, 15_000], timeout: 90_000 })
}

/** Ouvre une page NEUVE (contexte neuf, jamais le `storageState` de demo_admin), connectée, surveillée par les
 *  oracles, horloge du navigateur posée à `instant`. La page de la fixture (demo_admin) est fermée : la capture
 *  de l'étape est alors prise sur CETTE page. */
export async function ouvrir({ page, suivi, testInfo }, {
  vue = 'iphone', instant = null, timezoneId = 'UTC', username = COMPTE, password,
} = {}) {
  if (page && !page.isClosed()) await page.close()
  const browser = suivi.navigateur ?? page.context().browser()
  suivi.navigateur = browser
  const ctx = await browser.newContext({
    ...VUES[vue], baseURL: testInfo.project.use.baseURL, timezoneId, locale: 'fr-FR', serviceWorkers: 'block',
    colorScheme: 'light',
  })
  contextes.push(ctx)
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1')
      localStorage.setItem('taqinor:welcome:seen:v1', '1')
    } catch { /* mode privé */ }
  })
  await connecter(ctx.request, username, password ?? (username === COMPTE ? process.env.TACHES_DEMO_PASSWORD : undefined))
  const p = await ctx.newPage()
  suivi.surveiller(p)
  if (process.env.TCH_JOURNAL) { // mise au point : journal des écritures de l'API (jamais en rejeu normal)
    p.on('request', (q) => { if (q.url().includes('/api/') && q.method() !== 'GET') console.log('[req]', q.method(), q.url()) })
    p.on('requestfailed', (q) => { if (q.url().includes('/api/')) console.log('[échec]', q.method(), q.url(), q.failure()?.errorText) })
  }
  if (instant) await p.clock.install({ time: new Date(instant) })
  return p
}

/** Ouvre un écran Tâches et attend sa coquille. */
export async function aller(p, chemin, ecran) {
  await p.goto(chemin)
  await expect(p.locator(`.tch[data-ecran="${ecran}"]`)).toBeVisible({ timeout: 30_000 })
}

// --- Lectures API ------------------------------------------------------------------------------------------------

export async function lire(p, chemin, params) {
  const res = await p.request.get(`${API}/${chemin}`, params ? { params } : undefined)
  expect(res.ok(), `GET ${chemin} → ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}
export const liste = (corps) => (Array.isArray(corps) ? corps : (corps?.results ?? []))

/** La tâche du compte qui porte EXACTEMENT ce titre (faites comprises) ; échoue si absente ou en double. */
export async function tacheNommee(p, titre) {
  const trouvees = liste(await lire(p, 'taches/', { q: titre, inclure_faites: 'true' })).filter((t) => t.titre === titre)
  expect(trouvees, `une seule tâche « ${titre} »`).toHaveLength(1)
  return lire(p, `taches/${trouvees[0].id}/`)
}

/** Tous les items de `aujourdhui/` (sections + Proposé), à plat. */
export function itemsDe(journee) {
  const listes = ['essentiel', 'journee', 'ce_soir', 'a_decider', 'en_attente', 'faites']
  return [...listes.flatMap((c) => journee[c] ?? []), ...(journee.propose?.pour_objectif ?? [])]
}

// --- Gestes au doigt -----------------------------------------------------------------------------------------------

// Un VRAI doigt : `Input.dispatchTouchEvent` (CDP) — le navigateur en tire lui-même les événements pointeur
// `pointerType: 'touch'` (pointeur actif, `setPointerCapture` valide), comme sur un écran tactile.
// UNE session par page, jamais détachée : détacher une session CDP efface l'émulation réseau de la page
// (`context.setOffline` repassait `navigator.onLine` à vrai au milieu du parcours hors ligne — constaté en P144.2).
const sessions = new WeakMap()
async function doigt(p) {
  if (!sessions.has(p)) sessions.set(p, await p.context().newCDPSession(p))
  return sessions.get(p)
}
const point = (x, y) => ({ touchPoints: [{ x: Math.round(x), y: Math.round(y), id: 1, radiusX: 4, radiusY: 4, force: 1 }] })

async function boiteDe(ligneCadre, quoi) {
  const cible = ligneCadre.locator('.ligne').first()
  // au CENTRE de l'écran : en bas, la barre d'onglets fixe de l'iPhone recouvrirait la ligne (le doigt la toucherait)
  await cible.evaluate((el) => el.scrollIntoView({ block: 'center' }))
  const boite = await cible.boundingBox()
  expect(boite, `la ligne ${quoi} est affichée`).toBeTruthy()
  return boite
}

/** Balayage d'une ligne (`.ligne` d'un `[data-ligne]`) : `sens` −1 = vers la gauche (Reporter), +1 = droite (Fait).
 *  Balayage COMPLET (au-delà de la moitié de la largeur) : le geste se déclenche au lâcher. */
export async function balayer(p, ligneCadre, sens) {
  const boite = await boiteDe(ligneCadre, 'à balayer')
  const y = boite.y + boite.height / 2
  const x0 = boite.x + boite.width / 2 + (sens < 0 ? boite.width / 3 : -boite.width / 3)
  const cdp = await doigt(p)
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', ...point(x0, y) })
  for (const pas of [10, 30, 60, 100, 150, 200, 250, 290]) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', ...point(x0 + sens * pas, y) })
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
}

/** Appui long : on pose le doigt et on attend que le menu s'ouvre (le minuteur de 500 ms est celui de la page). */
export async function appuiLong(p, ligneCadre, menuitem) {
  const boite = await boiteDe(ligneCadre, 'à presser')
  const cdp = await doigt(p)
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', ...point(boite.x + boite.width / 3, boite.y + boite.height / 2) })
  await expect(p.getByRole('menu'), "l'appui long ouvre le menu de la ligne").toBeVisible()
  await expect(p.getByRole('menuitem', { name: menuitem })).toBeVisible()
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
}

// --- Captures de relecture visuelle -------------------------------------------------------------------------------

/** Capture pleine page de l'écran courant à 390 × 844 et 1440 × 900, thème clair et sombre (préférence système
 *  `prefers-color-scheme`, que `design/theme.js` suit par défaut), puis rend la page dans son état d'avant.
 *  Une capture qui échoue ne fait jamais tomber l'étape (elle n'est pas un oracle) : elle est dite en console. */
export async function capturer(p, ecran) {
  const taille = p.viewportSize()
  try {
    mkdirSync(DOSSIER_CAPTURES, { recursive: true })
    for (const [vue, viewport] of [['iphone', VUES.iphone.viewport], ['bureau', VUES.bureau.viewport]]) {
      await p.setViewportSize(viewport)
      for (const [theme, schema] of [['clair', 'light'], ['sombre', 'dark']]) {
        await p.emulateMedia({ colorScheme: schema })
        await expect(p.locator('html')).toHaveAttribute('data-theme', schema)
        await expect(p.locator('html.theme-transitioning')).toHaveCount(0)
        await p.screenshot({ path: `${DOSSIER_CAPTURES}/${ecran}-${vue}-${theme}.png`, fullPage: true })
      }
    }
  } catch (e) {
    console.log(`[captures] ${ecran} : ${String(e.message).split('\n')[0]}`)
  } finally {
    await p.emulateMedia({ colorScheme: 'light' }).catch(() => undefined)
    if (taille) await p.setViewportSize(taille).catch(() => undefined)
  }
}
