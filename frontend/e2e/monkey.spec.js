// QAH7 — Marcheur aléatoire gremlins.js sur chaque écran principal des
// modules MVP (matrice e2e COMPLÈTE, jamais le smoke par-merge).
//
// POURQUOI (GROUPE QAH, recherche L2 du 27/09/2026) : un agent LLM explore
// bien et juge mal (GUI Testing Arena arXiv 2412.18426, GUITester arXiv
// 2601.04500 — « goal-oriented masking », « execution-bias attribution »).
// Ici on ne juge RIEN au jugement : un singe aléatoire (gremlins.js) clique/
// glisse/tape/défile sur chaque écran pendant que des ORACLES DURS écoutent
// — `pageerror` (exceptions non rattrapées ET rejets de promesse non gérés,
// que Chromium remonte tous deux via le même évènement CDP), `console.error`,
// et toute réponse HTTP ≥ 500. Un constat = un fait observé, jamais un avis.
//
// TAG `@monkey` — jamais dans le chemin rapide :
//   - le job `e2e-shard` de ci.yml liste ses fichiers de spec EXPLICITEMENT
//     (jamais un glob du dossier e2e/) : ce fichier n'y figure nulle part,
//     donc exclu de fait du shard par-merge ;
//   - le projet dédié `monkey` de playwright.config.js (comme `mobile`/
//     `mobile-safari`/`tablet`) le fait tourner UNE fois quand `e2e-full` de
//     release-verify.yml lance `npx playwright test --grep-invert @visual`
//     (aucun `--project` → tous les projets, `monkey` inclus, `@visual`
//     seul étant exclu).
//
// SÉCURITÉ — GROUPE QAH « NE PAS FAIRE » : aucune écriture (réelle ou
// simulée) vers un service externe. Avant de lâcher les gremlins sur CHAQUE
// écran, tout bouton/lien dont le libellé visible évoque une action
// destructive ou un envoi (supprimer, envoyer, WhatsApp, e-mail) est
// neutralisé PAR SÉLECTEUR (texte, pas une route ni un composant précis —
// générique à tous les modules) : `disabled`, `pointer-events: none`, et
// pour les liens, `href` retiré. Un `MutationObserver` répète l'opération en
// continu — un gremlin peut ouvrir une modale qui révèle un nouveau bouton
// « Supprimer » après coup. La mogwai `alert()` de gremlins.js neutralise en
// prime `window.alert`/`confirm`/`prompt` (jamais un dialogue natif qui
// bloquerait la horde).
//
// GRAINE FIXE (jamais `Math.random`) : chaque écran reçoit une graine dérivée
// DÉTERMINISTE de son chemin (voir `grainePourRoute`) — un run est rejouable
// à l'identique, et un échec rapporte l'écran ET la graine exacte qui l'a
// provoqué (rejouable seule via `MONKEY_ROUTE`/`MONKEY_GRAINE`, voir plus bas).
import { expect } from '@playwright/test'
import { createRequire } from 'node:module'
import {
  routesParModule, TITRE_ECRAN_ERREUR,
  // CAD177 — session partagée vérifiée au démarrage de chaque module, et
  // reprise entre deux écrans si un gremlin a cliqué « Déconnexion ».
  testSessionFraiche as test, assurerSessionPage,
} from './helpers.js'

const require = createRequire(import.meta.url)

// Budget par écran (ms). PACT8 dénombre ~190 routes principales (hors routes
// paramétrées) sur ~19 modules : à 4 s/écran la matrice complète prend
// environ 15 min de gremlins purs — release-verify (palier 3, nightly/
// manuel) ne garde pas `main`, un budget généreux n'y coûte rien.
// Surchargeable pour un run manuel ciblé, ex. :
//   MONKEY_MS_PAR_ECRAN=1000 npx playwright test --project=monkey
const DUREE_PAR_ECRAN_MS = Number(process.env.MONKEY_MS_PAR_ECRAN) || 4_000

// Délai entre deux actions gremlins (stratégie `allTogether`, voir
// `lacherGremlins`) — 20 ms est un compromis entre densité de l'attaque et un
// navigateur qui a le temps de peindre entre deux clics.
const DELAI_ENTRE_ACTIONS_MS = 20

// Base de la graine : un nombre fixe, jamais tiré au hasard. Combinée au
// chemin de chaque écran (hash déterministe) pour ne pas rejouer EXACTEMENT
// la même séquence de clics sur 190 DOM différents tout en restant 100 %
// reproductible d'un run à l'autre.
const GRAINE_BASE = 424_242

/** Hash déterministe (jamais `Math.random`) — une graine stable par chemin. */
function grainePourRoute(chemin) {
  let h = 0
  for (let i = 0; i < chemin.length; i += 1) {
    h = (h * 31 + chemin.charCodeAt(i)) | 0
  }
  return GRAINE_BASE + Math.abs(h)
}

// Libellés (texte visible, casse ignorée) des actions destructives/d'envoi à
// neutraliser sur CHAQUE écran, quel que soit le module — jamais une liste
// par écran à maintenir. Étoffer avec l'accord du fondateur (règle #5 /
// prudence anti-envoi de GROUPE QAH), jamais en retirer une sans lui.
const LIBELLES_NEUTRALISES = [
  'supprimer', 'delete', 'effacer',
  'envoyer', 'envoi ', 'send',
  'whatsapp',
  'e-mail', 'email', 'courriel',
  // CAD177 : « Déconnexion » tuait la session du contexte, la reconnexion API
  // tapait le throttle login (429, 5/min/IP) et le module entier tombait.
  'déconnect', 'deconnect', 'logout', 'log out', 'sign out',
]

// ── Injecté dans la page (jamais exécuté côté Node) ─────────────────────────
// Neutralise en continu tout bouton/lien dangereux : une passe au chargement,
// puis un `MutationObserver` — un gremlin peut ouvrir une modale qui révèle
// un nouveau bouton après coup. Fonction sérialisée par Playwright
// (`page.addInitScript(fn, arg)`), donc SANS closure sur une variable du
// module Node : tout ce dont elle a besoin lui est passé en argument.
function scriptNeutralisation(libelles) {
  // CAD177 — COÛT. La version d'origine relisait TOUT le document
  // (`querySelectorAll` + `innerText`) à CHAQUE mutation : `innerText` force
  // un layout par élément, et une page React mute sans arrêt sous les
  // gremlins. Profil CPU mesuré (Chrome, /admin/demo/nouveau) : ~13 s sur
  // 22 s passés dans ce seul script — les « gremlins sans retour après
  // 24000 ms » du nocturne n'étaient pas une page gelée mais le singe qui
  // s'étouffait lui-même. Désormais : `textContent` (aucun layout ; inclut le
  // texte masqué, donc PLUS prudent, jamais moins) et, après la passe
  // initiale, seuls les nœuds touchés par la mutation sont examinés.
  const CIBLES =
    'button, a[href], input[type="submit"], input[type="button"], [role="button"]'
  function estDangereux(texte) {
    const t = (texte || '').toLowerCase()
    return libelles.some((mot) => t.includes(mot))
  }
  function neutraliserElement(el) {
    if (el.dataset.monkeyNeutralise) return
    const texte = [el.textContent, el.getAttribute('aria-label'), el.title]
      .filter(Boolean)
      .join(' ')
    if (!estDangereux(texte)) return
    el.dataset.monkeyNeutralise = '1'
    el.setAttribute('disabled', 'true')
    el.style.pointerEvents = 'none'
    // <a> ignore `disabled` — seule la neutralisation du `href` empêche la
    // navigation (ex. `wa.me/...`, `mailto:...`).
    if (el.tagName === 'A') el.removeAttribute('href')
  }
  function neutraliserSous(racine) {
    if (!racine || racine.nodeType !== 1) return
    if (racine.matches(CIBLES)) neutraliserElement(racine)
    racine.querySelectorAll(CIBLES).forEach(neutraliserElement)
  }
  function surMutations(enregistrements) {
    for (const m of enregistrements) {
      // Le texte (ou l'aria-label) d'un contrôle existant a pu changer : on
      // remonte au contrôle qui l'englobe.
      const cible = m.target.nodeType === 1 ? m.target : m.target.parentElement
      const controle = cible && cible.closest ? cible.closest(CIBLES) : null
      if (controle) neutraliserElement(controle)
      m.addedNodes.forEach(neutraliserSous)
    }
  }
  const demarrer = () => {
    neutraliserSous(document.documentElement)
    new MutationObserver(surMutations).observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ['aria-label', 'title', 'href', 'role', 'type'],
    })
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer, { once: true })
  } else {
    demarrer()
  }
}

async function armerNeutralisation(page) {
  await page.addInitScript(scriptNeutralisation, LIBELLES_NEUTRALISES)
}

/**
 * Injecte gremlins.js AVANT tout script de la page (`addInitScript`), comme
 * demandé par QAH7 — `window.gremlins` est donc disponible dès le premier
 * paint, sur CHAQUE navigation de ce `page` (addInitScript survit à
 * `page.goto`). Résolu paresseusement (à l'exécution du test, jamais au
 * chargement du fichier) : lister/analyser ce spec ne dépend pas de
 * `gremlins.js` étant déjà installé dans un `node_modules` local.
 */
async function armerGremlins(page) {
  const cheminGremlins = require.resolve('gremlins.js/dist/gremlins.min.js')
  await page.addInitScript({ path: cheminGremlins })
}

/**
 * Lâche gremlins.js sur l'écran déjà ouvert, pendant `dureeMs`, avec la
 * `graine` donnée (Chance.js interne à gremlins — un run rejouable à
 * l'identique). Stratégie `allTogether` : durée EXACTE et prévisible
 * (`nb * delay`), contrairement à la stratégie `distribution` par défaut
 * (courbe calme-tempête-calme, moins prévisible pour un budget par écran).
 * Espèces d'interaction seulement (clicker/toucher/formFiller/scroller/
 * typer) + la seule mogwai `alert()` (neutralise `window.alert/confirm/
 * prompt` — jamais `gizmo`, qui arrêterait la horde après 10 erreurs : on
 * VEUT observer tout le budget de temps, pas s'arrêter au premier défaut).
 */
async function lacherGremlins(page, { dureeMs, graine }) {
  // CAD177 : garde-fou DUR côté Node. Sans lui, une page gelée ou une requête
  // synchrone interminable laissait `page.evaluate` pendre jusqu'à l'expiration
  // du test entier (« Test timeout of 300000ms exceeded » sans dire où). Ici le
  // blocage ÉCHOUE VITE, nommé, et le singe passe à l'écran suivant.
  const delaiDurMs = dureeMs + 20_000
  let minuteur
  const garde = new Promise((_, rejeter) => {
    minuteur = setTimeout(() => rejeter(new Error(
      `gremlins sans retour après ${delaiDurMs} ms (page gelée ? requête bloquante ?)`
    )), delaiDurMs)
  })
  try {
    await Promise.race([evaluerGremlins(page, { dureeMs, graine }), garde])
  } finally {
    clearTimeout(minuteur)
  }
}

async function evaluerGremlins(page, { dureeMs, graine }) {
  await page.evaluate(
    async ({ dureeMs, graine, delai }) => {
      const nb = Math.max(20, Math.round(dureeMs / delai))
      const horde = window.gremlins.createHorde({
        randomizer: new window.gremlins.Chance(graine),
        species: [
          window.gremlins.species.clicker(),
          window.gremlins.species.toucher(),
          window.gremlins.species.formFiller(),
          window.gremlins.species.scroller(),
          window.gremlins.species.typer(),
        ],
        mogwais: [window.gremlins.mogwais.alert()],
        strategies: [window.gremlins.strategies.allTogether({ nb, delay: delai })],
      })
      await horde.unleash()
    },
    { dureeMs, graine, delai: DELAI_ENTRE_ACTIONS_MS }
  )
}

const PAR_MODULE = routesParModule()

// Un test PAR MODULE (comme la fumée PACT8) : un rouge NOMME le module
// fautif, et le budget de temps est proportionnel à son nombre d'écrans
// plutôt qu'un unique test de ~190 navigations qui expirerait avant de rien
// dire.
for (const [module, chemins] of PAR_MODULE) {
  test(
    `@monkey marcheur aléatoire — ${module} (${chemins.length} écran(s))`,
    { tag: '@monkey' },
    async ({ page }) => {
      // CAD177 : 8 s de marge par écran ne suffisaient pas (goto + coquille +
      // reprise de session sur un serveur à 3 workers) → budget global élargi.
      test.setTimeout(Math.max(120_000, chemins.length * (DUREE_PAR_ECRAN_MS + 25_000)))

      const casses = []
      let routeActuelle = null
      let graineActuelle = null
      const consigner = (defaut) => {
        casses.push(`${routeActuelle} (graine ${graineActuelle}) → ${defaut}`)
      }

      // `pageerror` couvre à la fois les exceptions non rattrapées ET les
      // rejets de promesse non gérés (Chromium remonte les deux via le même
      // évènement CDP `Runtime.exceptionThrown`) — la pile (`err.stack`) est
      // incluse dans le constat, comme demandé par QAH7.
      page.on('pageerror', (err) => {
        consigner(
          `exception non rattrapée ou rejet de promesse non géré : ${err.message}\n${err.stack || '(pas de pile)'}`
        )
      })
      page.on('console', (msg) => {
        if (msg.type() !== 'error') return
        // CAD177 : Chromium journalise en console.error TOUT 4xx (« Failed to
        // load resource… status of 403 »). Un singe qui clique au hasard
        // provoque légitimement 401/403/409/400 (droits, état, saisie
        // invalide) : ce n'est pas un défaut. Les vrais oracles restent les
        // exceptions JS, les console.error applicatifs et toute réponse >= 500.
        if (/Failed to load resource: the server responded with a status of 4\d\d/.test(msg.text())) return
        consigner(`console.error : ${msg.text()}`)
      })
      page.on('response', (res) => {
        if (res.status() >= 500) {
          consigner(`réponse ${res.status()} : ${res.request().method()} ${res.url()}`)
        }
      })

      await armerNeutralisation(page)
      await armerGremlins(page)

      for (const chemin of chemins) {
        routeActuelle = chemin
        graineActuelle = grainePourRoute(chemin)

        // CAD177 — les gremlins cliquent PARTOUT, y compris « Déconnexion »
        // (run 36990128960, /admin/impersonation) : sans reprise, chaque écran
        // suivant s'ouvrait sur /login et se signalait « page blanche » à
        // tort. On rétablit la session (API) avant d'ouvrir l'écran suivant.
        await assurerSessionPage(page)

        await page.goto(chemin, { waitUntil: 'domcontentloaded' })

        // Même attente que la fumée PACT8 : la coquille authentifiée
        // (`.header-title`) ou l'écran de récupération, jamais `networkidle`
        // (lent/instable sur des écrans qui interrogent en continu).
        const coquille = page.locator('.header-title')
        const ecranErreur = page.getByRole('heading', { name: TITRE_ECRAN_ERREUR })
        try {
          await coquille.or(ecranErreur).first().waitFor({ state: 'visible', timeout: 15_000 })
        } catch {
          consigner(
            'page blanche avant même le lâcher des gremlins : ni la coquille '
              + 'applicative (.header-title) ni un écran d’erreur n’est apparu'
          )
          continue // rien à secouer sur un écran qui n'a jamais rendu
        }

        try {
          await lacherGremlins(page, { dureeMs: DUREE_PAR_ECRAN_MS, graine: graineActuelle })
        } catch (err) {
          // Un gremlin qui clique un lien NAVIGUE : le contexte d'exécution
          // disparaît, ce n'est pas un défaut. Tout autre échec (dont le
          // garde-fou de gel) est un constat nommé.
          if (!/Execution context was destroyed|navigation/i.test(err.message)) {
            consigner(`gremlins interrompus : ${err.message}`)
          }
        }
      }

      expect(
        casses,
        `constats du marcheur aléatoire sur le module « ${module} » `
          + '(chaque ligne : écran (graine) → constat — rejouable seul avec cette graine)'
      ).toEqual([])
    }
  )
}
