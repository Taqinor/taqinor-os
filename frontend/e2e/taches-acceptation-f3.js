// Aides de l'ACCEPTATION EN DIRECT « Tâches », fusion 3 (TCH141, TCH171, TCH143 — `e2e/acceptation/tch2.spec.js`).
// Complète `taches-acceptation.js` (fusion 2 : scénario, connexion `demo_taches`, vues, captures) sans le recopier :
//   - le jeton d'un usage créé À L'ÉCRAN Mon iPhone (le clair n'existe qu'à l'écran, une fois) ;
//   - les appels « Siri / Calendrier / Scriptable » : `request` de Playwright sur l'origine du front, jeton en Bearer
//     (jamais un jeton écrit dans un fichier ni dans un journal) ;
//   - le balayage `apps.taches.balayage.executer` joué à un instant DONNÉ par le shell Django des specs ;
//   - le service d'IA branché sous `/api/fastapi/` comme derrière nginx (convention de `aic.spec.js` : route Playwright
//     → `E2E_IA_URL`, jeton de session relayé en Bearer) ;
//   - les captures de relecture visuelle de la fusion 3 (iPhone et bureau, clair et sombre).
// Aucune attente fixe : on attend un état visible ou une réponse observée.
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { expect, request as pwRequest } from '@playwright/test'
import { py } from './acceptation/_django.js'
import { VUES } from './taches-acceptation.js'

export const DOSSIER_CAPTURES_F3 = process.env.E2E_TACHES_CAPTURES || '/opt/taches-cloud/captures/f3'
export const VRAI_ASSISTANT_REQUIS = 'vrai assistant requis : E2E_IA_URL + clé du dépôt'

// --- Mon iPhone : un jeton créé à l'écran ---------------------------------------------------------------------------

/** Les cinq étapes de Mon iPhone (boutons repliables, dans l'ordre de l'écran). */
export const etapesIphone = (p) => p.locator('ol.ep-etapes > li > button.ep-etape-i')

/** Le contenu déplié de l'étape `numero` (1-5). */
export const etapeOuverte = (p, numero) => p.locator('ol.ep-etapes > li').nth(numero - 1).locator('.ep-etape-ouverte')

/** Ouvre l'étape `numero` (1-5) si elle est repliée ; rend son bouton. */
export async function deplier(p, numero) {
  const bouton = etapesIphone(p).nth(numero - 1)
  if ((await bouton.getAttribute('aria-expanded')) !== 'true') await bouton.click()
  await expect(bouton).toHaveAttribute('aria-expanded', 'true')
  return bouton
}

/** Crée le jeton d'un usage par SON bouton de Mon iPhone et lit le clair affiché UNE fois (`code.ep-jeton-valeur`).
 *  La réponse de `POST jetons/` est attendue : le clair lu à l'écran est celui que le serveur vient d'émettre. */
export async function jetonParEcran(p, numero, libelleCreer) {
  await deplier(p, numero)
  const zone = etapeOuverte(p, numero)
  const reponse = p.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/django\/taches\/jetons\/$/.test(r.url()))
  await zone.getByRole('button', { name: libelleCreer, exact: true }).click()
  const r = await reponse
  expect(r.status(), `POST jetons/ (${libelleCreer})`).toBe(201)
  const clair = (await zone.locator('code.ep-jeton-valeur').textContent())?.trim() ?? ''
  expect(clair, 'le jeton en clair est affiché une fois').toMatch(/^tq[a-z]_/)
  return { clair, fiche: await r.json() }
}

/** Client HTTP « hors navigateur » (raccourci Siri, Calendrier, Scriptable) : AUCUN cookie de session. */
export async function clientNu(baseURL) {
  return pwRequest.newContext({ baseURL, extraHTTPHeaders: {} })
}

// --- Le balayage, à un instant donné ---------------------------------------------------------------------------------

/** `executer(maintenant=<instant AWARE du Maroc>)` → les compteurs du passage. */
export async function balayer(heureMaroc) {
  return py(`import zoneinfo
from apps.taches.balayage import executer
m = datetime.datetime.fromisoformat('${heureMaroc}').replace(tzinfo=zoneinfo.ZoneInfo('Africa/Casablanca'))
sortie(executer(maintenant=m))`)
}

/** Les notifications de `demo_taches` (toutes, dans l'ordre de création). */
export async function notificationsDe(username = 'demo_taches') {
  return py(`from apps.notifications.models import Notification
u = U.objects.get(username='${username}')
sortie([dict(id=n.pk, type=n.event_type, titre=n.title, corps=n.body, lien=n.link, lue=n.read)
        for n in Notification.objects.filter(recipient=u).order_by('pk')])`)
}

/** Vide la cloche de `demo_taches` (le semis ne la touche pas) : chaque étape part de zéro. TOUTES ses notifications,
 *  pas seulement celles de Tâches : chaque connexion d'un navigateur neuf en écrit une (« Nouvelle connexion depuis un
 *  appareil inconnu »), et la cloche ne montre que sa première page — vingt connexions de la spec en chassaient la
 *  notification que l'étape regarde. */
export async function viderCloche(username = 'demo_taches') {
  return py(`from apps.notifications.models import Notification
u = U.objects.get(username='${username}')
sortie(Notification.objects.filter(recipient=u).delete()[0])`)
}

// --- Le service d'IA (FastAPI) sous /api/fastapi --------------------------------------------------------------------

const IA = process.env.E2E_IA_URL

/** Remet le service d'IA à l'heure de Django quand la pile le demande (`E2E_IA_RELANCER` = commande + arguments,
 *  séparés par des espaces ; ex. `/opt/taches-cloud/ia-f3.sh demarrer <worktree>` sur la machine cloud). Sur un runner,
 *  `zz-taches-pile.sh horloge` relance déjà les deux ensemble : variable absente, rien à faire. Un jeton émis par Django
 *  porte son `iat`/`exp` : le service d'IA doit vivre à la même heure (PyJWT refuse un `iat` futur ou un `exp` passé). */
export function relancerIA() {
  const commande = (process.env.E2E_IA_RELANCER || '').trim()
  if (!commande) return
  const [cmd, ...args] = commande.split(/\s+/)
  execFileSync(cmd, args, { encoding: 'utf8', timeout: 300_000, stdio: ['ignore', 'pipe', 'pipe'] })
}

/** Branche `/api/fastapi/…` de la page sur `E2E_IA_URL` (comme nginx en production), jeton de session en Bearer. */
export async function brancherIA(p) {
  expect(IA, `service d'IA lancé (E2E_IA_URL) — ${VRAI_ASSISTANT_REQUIS}`).toBeTruthy()
  const requetes = []
  await p.route(/\/api\/fastapi\//, async (route) => {
    const req = route.request()
    const u = new URL(req.url())
    requetes.push(`${req.method()} ${u.pathname}`)
    const headers = { ...req.headers() }
    delete headers.host; delete headers.cookie; delete headers['content-length']
    const jeton = (await p.context().cookies()).find((c) => c.name === 'access_token')?.value || ''
    if (jeton) headers.authorization = `Bearer ${jeton}`
    try {
      const rep = await route.fetch({
        url: `${IA}${u.pathname.replace(/^\/api\/fastapi/, '')}${u.search}`, headers, timeout: 300_000, maxRedirects: 0,
      })
      await route.fulfill({ response: rep })
    } catch {
      await route.abort().catch(() => undefined)
    }
  })
  return requetes
}

/** Le panneau du Copilote, ouvert par le bouton « Copilote » de l'en-tête de Tâches. */
export async function ouvrirCopilote(p) {
  const panneau = p.getByTestId('copilot-panel')
  if (await panneau.isVisible().catch(() => false)) return panneau
  await p.locator('.tch').getByRole('button', { name: 'Copilote', exact: true }).click()
  await expect(panneau, 'panneau du Copilote ouvert').toBeVisible({ timeout: 30_000 })
  await expect(panneau.getByRole('group', { name: 'Demandes prêtes' })).toBeVisible()
  return panneau
}

/** Une demande prête du panneau → la carte `carte-taches-<cle>` (dernière rendue). */
export async function demandePrete(panneau, question, cle) {
  await panneau.getByRole('group', { name: 'Demandes prêtes' }).getByRole('button', { name: question, exact: true }).click()
  const carte = panneau.getByTestId(`carte-taches-${cle}`).last()
  await expect(carte, `carte ${cle} de « ${question} »`).toBeVisible({ timeout: 30_000 })
  return carte
}

/** Pose une question LIBRE au Copilote (le vrai modèle) ; rend le corps JSON de `/sql-agent/query`.
 *  Sans clé d'IA, le service répond par son message de configuration : l'étape échoue alors, ROUGE et dite. */
export async function demanderAuCopilote(p, panneau, question) {
  const zone = panneau.getByRole('textbox').last()
  await expect(zone).toBeEnabled({ timeout: 60_000 })
  await zone.fill(question)
  const rep = p.waitForResponse((r) => r.request().method() === 'POST'
    && /\/api\/fastapi\/sql-agent\/query$/.test(new URL(r.url()).pathname), { timeout: 300_000 })
  await panneau.getByRole('button', { name: 'Envoyer' }).click()
  const r = await rep
  const corps = await r.json().catch(() => ({}))
  expect(r.status(), `réponse de l'assistant : ${JSON.stringify(corps).slice(0, 300)}`).toBe(200)
  expect(String(corps.answer || ''), VRAI_ASSISTANT_REQUIS).not.toContain("L'assistant n'est pas disponible pour le moment")
  await expect(zone, 'tour terminé').toBeEnabled({ timeout: 60_000 })
  console.log(`[TCH143] « ${question.slice(0, 60)} » → moteur=${corps.moteur} outils=${JSON.stringify(corps.outils_appeles || [])} `
    + `cartes=${JSON.stringify((corps.cartes || []).map((c) => c.carte))}`)
  return corps
}

// --- Captures de relecture visuelle (fusion 3) ----------------------------------------------------------------------

/** Pleine page à 390 × 844 et 1440 × 900, clair et sombre, dans `DOSSIER_CAPTURES_F3/<ecran>-<vue>-<theme>.png`.
 *  `cadre` : un élément à capturer seul (un panneau en superposition) au lieu de la page entière.
 *  Une capture n'est jamais un oracle : un échec est dit en console, l'étape continue. */
export async function capturerF3(p, ecran, { cadre = null, vues = ['iphone', 'bureau'] } = {}) {
  const taille = p.viewportSize()
  try {
    mkdirSync(DOSSIER_CAPTURES_F3, { recursive: true })
    for (const vue of vues) {
      await p.setViewportSize(VUES[vue].viewport)
      for (const [theme, schema] of [['clair', 'light'], ['sombre', 'dark']]) {
        await p.emulateMedia({ colorScheme: schema })
        await expect(p.locator('html')).toHaveAttribute('data-theme', schema)
        await expect(p.locator('html.theme-transitioning')).toHaveCount(0)
        const chemin = `${DOSSIER_CAPTURES_F3}/${ecran}-${vue}-${theme}.png`
        if (cadre) await cadre.screenshot({ path: chemin })
        else await p.screenshot({ path: chemin, fullPage: true })
      }
    }
  } catch (e) {
    console.log(`[captures] ${ecran} : ${String(e.message).split('\n')[0]}`)
  } finally {
    await p.emulateMedia({ colorScheme: 'light' }).catch(() => undefined)
    if (taille) await p.setViewportSize(taille).catch(() => undefined)
  }
}
