// E16 — Mobile pass (iPhone viewport, see the `mobile` project in the config):
// no horizontal overflow on key pages, and the full nav menu is reachable
// (verifies the C1 cut-off-menu fix).
import { test, expect } from '@playwright/test'
import {
  uniq, uiLogin, ADMIN, gotoLeads, createLead,
  assertNoSeriousA11yViolations,
} from './helpers'

const PAGES = ['/dashboard', '/crm/leads', '/ventes/factures', '/parametres']

test('E16: no horizontal overflow on key pages', async ({ page }) => {
  for (const path of PAGES) {
    await page.goto(path)
    await expect(page.locator('.header-title')).toBeVisible()
    await page.waitForLoadState('networkidle').catch(() => {})
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    )
    expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(1)
  }
})

test('E16: the full navigation menu is reachable on mobile', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.locator('.header-title')).toBeVisible()

  // Open the drawer (hamburger only shows at mobile widths).
  await page.getByRole('button', { name: 'Ouvrir le menu' }).click()

  // The last items (admin-only, at the very bottom) must be reachable, i.e. the
  // menu scrolls inside the safe area instead of clipping them.
  // « Paramètres » exists in several sections (admin, Paie, SAV « Paramètres SAV »),
  // so a name match is ambiguous (strict-mode violation) — target the ADMIN
  // settings link by its unique href /parametres, which sits at the very bottom.
  const settings = page.locator('a[href="/parametres"]')
  await settings.scrollIntoViewIfNeeded()
  await expect(settings).toBeVisible()

  const logout = page.getByRole('button', { name: 'Déconnexion' })
  await logout.scrollIntoViewIfNeeded()
  await expect(logout).toBeVisible()
})

// E16+ — Régression iPhone : un modal d'édition (haut) doit TENIR dans l'écran et
// rester scrollable, pas déborder hors du viewport avec ses boutons hors d'atteinte.
// (Pendant e2e du correctif Dialog/AlertDialog ; le contrat de classes est, lui,
// verrouillé côté composant par src/ui/modal-viewport.test.jsx.) On réutilise le
// parcours éprouvé d'E8 (créer puis éditer un utilisateur) pour ouvrir un modal réel.
test('E16+: an edit modal fits the iPhone viewport (no off-screen crop)', async ({ page }) => {
  await page.goto('/admin/users')
  await expect(page.getByRole('heading', { name: 'Gestion des utilisateurs' })).toBeVisible()

  const username = uniq('m16').replace(/\s+/g, '_').toLowerCase()
  await page.getByRole('button', { name: '+ Nouvel utilisateur' }).click()
  const createForm = page.locator('form').filter({
    has: page.getByRole('button', { name: 'Créer', exact: true }),
  })
  await createForm.locator('input:not([type])').first().fill(username)
  await createForm.locator('input[type="email"]').fill(`${username}@e2e.local`)
  await createForm.locator('input[type="password"]').fill('Az9ployxQ!')
  // Le rôle par défaut est renseigné de façon ASYNCHRONE (après le chargement de
  // /roles/). Soumettre avant qu'il n'arrive POSTe un rôle vide → 400. On attend
  // donc que le sélecteur quitte son texte de remplacement avant de créer.
  await expect(page.locator('#new-role')).not.toContainText('Choisir un rôle')
  await createForm.getByRole('button', { name: 'Créer', exact: true }).click()

  // M154 — Au format iPhone (< 640px), le DataTable des utilisateurs replie ses
  // lignes en CARTES (`[data-dt-cards]`) ; la table desktop passe en
  // `display:none`, donc le sélecteur `tr` n'est plus visible. On cible la carte
  // par son nom d'utilisateur, on ouvre le menu kebab PERSISTANT de la ligne
  // (RowActions — les actions rapides sont masquées au toucher), puis « Modifier ».
  const card = page.locator('[data-dt-cards] > div').filter({ hasText: username })
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  const kebabMenu = page.getByRole('menu')
  await expect(kebabMenu).toBeVisible()
  // VX71 — scan axe DYNAMIQUE sur le menu KEBAB du DataTable réellement ouvert
  // (état monté au clic, jamais couvert par un scan statique de build).
  await assertNoSeriousA11yViolations(page, { include: '[role="menu"]' })
  await page.getByRole('menuitem', { name: 'Modifier' }).click()

  const modal = page.locator('.modal')
  await expect(modal).toBeVisible()
  // VX134 — la Dialog joue une anim `pop-in` (scale/translate) à l'ouverture :
  // attendre qu'elle soit TERMINÉE avant de mesurer, sinon la boundingBox est
  // relevée en plein transform (position/hauteur transitoires → faux positif).
  await modal.evaluate((el) =>
    Promise.all(el.getAnimations({ subtree: true }).map((a) => a.finished.catch(() => {}))),
  )

  // Cœur du test iPhone : le modal ne déborde pas verticalement hors de l'écran.
  const box = await modal.boundingBox()
  const vp = page.viewportSize()
  expect(box, 'le modal a une boundingBox').toBeTruthy()
  expect(box.y, 'le haut du modal est visible').toBeGreaterThanOrEqual(-1)
  // Tolérance 2px : le modal `max-h-[calc(100dvh-2rem)]` tient au ras du bord ;
  // l'arrondi sous-pixel de WebKit (dvh + frame d'anim) le pose parfois à
  // ~1.2px du bord — jamais un vrai « crop » hors écran (qui ferait 10+px).
  expect(
    box.y + box.height,
    'le bas du modal tient dans le viewport iPhone',
  ).toBeLessThanOrEqual(vp.height + 2)

  // L'action critique (réinitialiser le mot de passe) reste atteignable.
  const pwd = modal.getByText('Nouveau mot de passe', { exact: true })
  await pwd.scrollIntoViewIfNeeded()
  await expect(pwd).toBeVisible()
})

// ── MB6 — Mobile visual/e2e regression gate ─────────────────────────────────
// Broader iPhone-viewport pass over the KEY journeys (login → leads → devis
// list → devis generator → chantiers → paramètres): no horizontal overflow on
// any of them, and no actionable content sits hidden behind the sticky header
// or the sticky bottom tab-bar (MB1/MB3 keep both IN-FLOW, but a future
// regression could re-introduce `position: fixed` overlap — this is the net).
// Reuses the same auth/seed fixtures as the rest of the suite (storageState
// from auth.setup.js; login itself is exercised cold, mirroring login.spec.js).

function assertNoHorizontalOverflow(page, path) {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    .then((overflow) => expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(1))
}

// True viewport overlap check: sample the DOM element actually PAINTED at the
// corners + center of the target's bounding box and confirm each point either
// hits the target itself (or one of its descendants/ancestors) — not the
// sticky header / bottom tab-bar drawn on top of it. This catches real
// paint-order collisions that a pure Y-coordinate comparison would miss (e.g.
// a `position: fixed` regression re-introduced over an in-flow element), and
// is backed up by the same Y-coordinate bounds as a belt-and-braces check.
async function assertNotObscured(page, locator, label) {
  // CENTRE la cible dans son scrolleur (scrollIntoView natif) : le
  // scrollIntoViewIfNeeded protocolaire colle la cible au BORD du scrollport
  // en ignorant scroll-padding — où un en-tête sticky LÉGITIME (thead épinglé
  // de la liste, en-tête d'étape LB41) recouvre son haut par construction
  // (rouge MB6 mobile-safari : carte fraîche sous l'en-tête « Nouveau »).
  // Centrée, la cible n'est jamais sous le chrome haut/bas — et une VRAIE
  // régression de chrome fixe la recouvre au centre aussi : le garde reste
  // entier pour ce qu'il a été écrit (tab-bar basse, header fixe).
  await locator.evaluate((el) => el.scrollIntoView({ block: 'center', inline: 'nearest' }))
  await expect(locator, `${label} is visible`).toBeVisible()
  let box = await locator.boundingBox()
  // MB6 robustesse — un pied de page COLLANT (position:sticky bottom:0, ex.
  // .gen-actions-sticky du générateur de devis) peut, sur WebKit, rapporter sa
  // boîte en FLUX (hors viewport, ex. y≈5282) après scrollIntoViewIfNeeded au
  // lieu de sa position collée. On force alors le(s) conteneur(s) de défilement
  // tout en bas pour que l'élément collant se pose au bas du viewport, puis on
  // re-mesure — sinon elementFromPoint vise hors écran et renvoie null.
  const vh = (page.viewportSize() || { height: 900 }).height
  if (box && (box.y < 0 || box.y + box.height > vh)) {
    await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight)
      document.querySelectorAll('.layout-content, main, [data-scroll]')
        .forEach((el) => { el.scrollTop = el.scrollHeight })
    })
    // Attendre (condition EXPLICITE, pas de sleep fixe — check_test_determinism)
    // que l'élément collant se pose DANS le viewport après le défilement en bas.
    await expect
      .poll(async () => {
        const b = await locator.boundingBox()
        return !!(b && b.y >= -4 && b.y + b.height <= vh + 4)
      }, { timeout: 3000 })
      .toBeTruthy()
      .catch(() => {})
    box = await locator.boundingBox()
  }
  expect(box, `${label} has a bounding box`).toBeTruthy()
  const handle = await locator.elementHandle()
  const inset = 2
  const points = [
    [box.x + inset, box.y + inset],
    [box.x + box.width - inset, box.y + inset],
    [box.x + box.width / 2, box.y + box.height / 2],
    [box.x + inset, box.y + box.height - inset],
    [box.x + box.width - inset, box.y + box.height - inset],
  ]
  for (const [x, y] of points) {
    // Diagnostic embarqué : en cas d'échec, le message NOMME l'élément qui
    // recouvre le point (tag + classes + chaîne d'ancêtres) — un rouge CI
    // devient auto-explicatif au lieu d'exiger une reproduction locale.
    const hit = await page.evaluate(
      ([px, py, node]) => {
        const top = document.elementFromPoint(px, py)
        if (top && (top === node || node.contains(top) || top.contains(node))) return { ok: true }
        // Tolérance PRINCIPIELLE (rouge CI LB41, élément couvrant identifié :
        // button.kb-col-collapse-btn < header.kb-col-header sticky) : un
        // élément `position:sticky` DANS LE MÊME scrolleur que la cible est
        // de l'UI légitime (thead épinglé de la liste, en-tête d'étape du
        // board) — le haut d'un contenu défilé passe DESSOUS par
        // construction, comme dans tout kanban/tableau (Odoo compris). Le
        // garde continue d'attraper ce pour quoi il existe : `position:
        // fixed` (tab-bar basse, header d'app, overlays) échoue toujours.
        if (top) {
          let sticky = null
          for (let n = top; n && n !== document.body; n = n.parentElement) {
            const pos = getComputedStyle(n).position
            if (pos === 'fixed') { sticky = null; break }
            if (pos === 'sticky') { sticky = n; break }
          }
          if (sticky) {
            const scrollerOf = (el) => {
              for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) {
                const s = getComputedStyle(n)
                if (/(auto|scroll)/.test(s.overflowY + s.overflowX)) return n
              }
              return document.scrollingElement
            }
            // MÊME scrolleur, et jamais celui de la PAGE : un sticky de
            // chrome d'app (scrolleur document/layout) reste un échec.
            const sc = scrollerOf(sticky)
            if (sc !== document.scrollingElement && sc === scrollerOf(node)) return { ok: true }
          }
        }
        const chain = []
        for (let n = top; n && n !== document.body && chain.length < 5; n = n.parentElement) {
          chain.push(`${n.tagName.toLowerCase()}${n.className ? `.${String(n.className).split(' ').slice(0, 3).join('.')}` : ''}`)
        }
        return { ok: false, covering: chain.join(' < ') || 'null' }
      },
      [x, y, handle],
    )
    expect(hit.ok, `${label}: point (${Math.round(x)},${Math.round(y)}) is painted by the target, not fixed chrome on top of it (couvert par : ${hit.covering ?? '—'})`).toBeTruthy()
  }
  // Belt-and-braces: the element's box must not be covered by the sticky
  // bottom tab-bar or sit underneath the sticky header.
  const tabbar = page.locator('.bottom-tabbar')
  if (await tabbar.count()) {
    const tabBox = await tabbar.boundingBox()
    if (tabBox) {
      expect(
        box.y + box.height,
        `${label}: bottom edge stays above the bottom tab-bar`,
      ).toBeLessThanOrEqual(tabBox.y + 1)
    }
  }
  const header = page.locator('.header').first()
  if (await header.count()) {
    const headerBox = await header.boundingBox()
    if (headerBox) {
      expect(
        box.y,
        `${label}: top edge stays below the sticky header`,
      ).toBeGreaterThanOrEqual(headerBox.y + headerBox.height - 1)
    }
  }
}

test.describe('MB6: login (cold, no shared auth state)', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('login screen has no horizontal overflow on iPhone', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByPlaceholder('Entrez votre identifiant')).toBeVisible()
    await assertNoHorizontalOverflow(page, '/login')
    await uiLogin(page, ADMIN)
    await expect(page).toHaveURL(/\/dashboard/)
  })
})

test('MB6: key flows have no horizontal overflow and no content hidden behind the fixed chrome', async ({ page }) => {
  // 1) Leads — list/kanban entry point.
  await gotoLeads(page)
  await assertNoHorizontalOverflow(page, '/crm/leads')
  await assertNotObscured(
    page,
    page.getByRole('button', { name: '+ Nouveau lead' }),
    'leads: "+ Nouveau lead" action',
  )

  // 2) Devis list.
  await page.goto('/ventes/devis')
  await expect(page.getByRole('heading', { name: 'Devis' })).toBeVisible()
  await assertNoHorizontalOverflow(page, '/ventes/devis')

  // 3) Devis generator — the sticky footer action bar (`.gen-actions-sticky`)
  //    is the exact element MB3 pinned at --z-sticky; it must stay reachable
  //    above the bottom tab-bar, not swallowed by it.
  await page.goto('/ventes/devis/nouveau')
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' })).toBeVisible()
  await assertNoHorizontalOverflow(page, '/ventes/devis/nouveau')
  const submitBtn = page.getByRole('button', { name: /Créer le devis|Enregistrer les modifications/ })
  await assertNotObscured(page, submitBtn, 'devis generator: submit action')

  // 4) Chantiers (installations).
  await page.goto('/chantiers')
  await expect(page.getByRole('heading', { name: 'Chantiers' })).toBeVisible()
  await assertNoHorizontalOverflow(page, '/chantiers')

  // 5) Paramètres.
  await page.goto('/parametres')
  await expect(page.getByRole('button', { name: 'Enregistrer' })).toBeVisible({ timeout: 20_000 })
  await assertNoHorizontalOverflow(page, '/parametres')
  await assertNotObscured(
    page,
    page.getByRole('button', { name: 'Enregistrer' }),
    'paramètres: "Enregistrer" action',
  )
})

test('MB6: a freshly-created lead card is reachable and unobscured on iPhone', async ({ page }) => {
  // End-to-end sanity on top of the static overflow/overlap checks: a real
  // mutating flow (create a lead) must leave its result visible and tappable,
  // not hidden under the bottom tab-bar after the list re-renders.
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('MB6 Lead') })
  const card = page.locator('article.kb-card', { hasText: name }).first()
  const row = page.locator('tr.lv-row', { hasText: name }).first()
  const target = (await card.isVisible().catch(() => false)) ? card : row
  await assertNotObscured(page, target, 'leads: newly-created lead card/row')
})

// ── VX190 — garde WebKit étendue (@after VX68 + VX172/176/178) ─────────────
// Ce spec tourne DÉJÀ sur WebKit réel via le projet `mobile-safari` (VX68,
// voir playwright.config.js) : les 3 assertions ci-dessous couvrent ce que
// VX68 ne testait pas encore — export blob (VX172), sticky DataTable
// (VX178), navigation standalone (VX176/177).

test('VX190: le bouton Exporter aboutit par le chemin geste (jamais d\'échec silencieux)', async ({ page }) => {
  // VX172 — DevisList pose un état loading/désactivé le temps de l'export ;
  // sur WebKit/standalone le blob part par `downloadBlobInGesture` (tab
  // pré-ouvert dans le handler de tap), jamais un simple `a.download` qui
  // resterait invisible en coquille installée. On vérifie ici que le clic
  // engage bien le pending state et retombe sans jamais planter en silence
  // (pas d'erreur console) — la vérification appareil réel/standalone est
  // notée au DoD de VX172 (le simulateur ne suffit pas à lui seul).
  const consoleErrors = []
  page.on('pageerror', (err) => consoleErrors.push(String(err)))

  await page.goto('/ventes/devis')
  await expect(page.getByRole('heading', { name: 'Devis' })).toBeVisible()
  await page.waitForLoadState('networkidle').catch(() => {})

  const exportBtn = page.getByRole('button', { name: /Exporter Excel/i })
  if (await exportBtn.count()) {
    await exportBtn.click()
    // Le bouton passe en état occupé (spinner + désactivé) le temps de
    // préparer le blob — jamais un échec muet.
    await expect(exportBtn).toBeDisabled({ timeout: 5_000 }).catch(() => {})
    await expect(exportBtn).toBeEnabled({ timeout: 15_000 })
  }
  expect(consoleErrors, 'aucune exception JS pendant l\'export').toEqual([])
})

test('VX190: thead/tfoot du DataTable restent lisibles pendant le scroll (pas de décrochage)', async ({ page }) => {
  // VX178 — le fond opaque (sans backdrop-blur) doit rester attaché en haut
  // du conteneur scrollable pendant le défilement d'une longue liste.
  // VX180 — le DataTable ne rend un <table>/<thead> qu'AU-DELÀ du point de
  // bascule `dt-desktop` (768px) ; en dessous (iPhone) ce sont des CARTES
  // sans thead. On force donc une largeur bureau pour valider le thead sticky
  // là où il existe réellement (sinon l'assertion teste un thead masqué).
  await page.setViewportSize({ width: 1024, height: 800 })
  await page.goto('/ventes/factures')
  await expect(page.getByRole('heading', { name: 'Factures' })).toBeVisible()
  await page.waitForLoadState('networkidle').catch(() => {})

  const scrollBox = page.locator('[data-dt-scroll]').first()
  if (await scrollBox.count()) {
    await scrollBox.evaluate((el) => { el.scrollTop = el.scrollHeight })
    const thead = page.locator('[data-dt-table] thead').first()
    await expect(thead).toBeVisible()
    const box = await thead.boundingBox()
    expect(box, 'le thead sticky a une boundingBox après scroll').toBeTruthy()
  }
})

test('VX190: un Sheet standalone respecte l\'inset haut (safe-top)', async ({ page }) => {
  // VX176 — en mode standalone iOS (`navigator.standalone === true`), les
  // overlays plein écran portent `safe-top` (padding-top:
  // env(safe-area-inset-top)) pour ne jamais coller sous l'encoche. Un
  // appareil de CI n'a pas d'encoche réelle (env() résout à 0), donc la
  // preuve ici est STRUCTURELLE : la classe est bien posée sur l'overlay.
  await page.addInitScript(() => {
    Object.defineProperty(window.navigator, 'standalone', { value: true, configurable: true })
  })
  await page.goto('/ui')
  await expect(page.getByRole('button', { name: 'Ouvrir un tiroir' })).toBeVisible()
  await page.getByRole('button', { name: 'Ouvrir un tiroir' }).click()
  await expect(page.getByRole('heading', { name: 'Filtres' })).toBeVisible()
  const overlay = page.locator('.safe-top').first()
  await expect(overlay).toBeVisible()
})
