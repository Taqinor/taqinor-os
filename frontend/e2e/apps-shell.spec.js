// ODY31 — LA GATE E2E DU PARADIGME « ERP-Apps » (fondateur 2026-08-01).
// ----------------------------------------------------------------------------
// Un seul parcours, de bout en bout, sur l'app RÉELLEMENT bâtie : on n'entre
// plus dans un écran, on entre dans une APP.
//
//   connexion (storageState partagé) → Menu d'accueil → type-ahead → CRM
//   → immersion (aucun lien d'une autre app, identité dans la topbar)
//   → lien croisé client → devis : la coquille bascule sur Ventes
//   → sortie par le ⊞ (LA sortie canonique, ODY5) → retour à la grille
//   → écran « app non activée » (ODY8)
//   → viewport mobile : barre d'onglets scopée + onglet « Apps » (ODY6)
//
// ANCRAGES. Ce spec ne réinvente aucun sélecteur : il réutilise ceux que les
// specs verts emploient déjà — `.header-title` (contrat e2e historique),
// `aside.sidebar[data-app]` (cross-app.spec.js), le kebab de ligne
// « Plus d'actions sur la ligne » (mobile.spec.js), le titre « Mes
// applications » (auth.setup.js) — plus les deux ancres que le paradigme a
// posées avec leur écran : `.home-menu-cell[data-app]` (ODY6) et
// `[data-testid="app-non-activee"]` (ODY8). Les apps sont TOUJOURS désignées
// par leur CLÉ, jamais par un libellé (le badge ODY10 rallonge le nom
// accessible d'une tuile, et un libellé peut être traduit).
import { test, expect } from '@playwright/test'

const MENU = '/apps'

// Ouvre le Menu d'accueil et attend qu'il soit réellement peint. Il ne
// déclenche AUCUNE requête bloquante (ODY2) : la grille vient du bootstrap.
async function ouvrirMenu(page) {
  await page.goto(MENU)
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
}

const tuile = (page, cle) => page.locator(`.home-menu-cell[data-app="${cle}"] .home-menu-tile`)

// Immersion : la coquille EST celle de `cle`, et le DOM de la nav ne contient
// AUCUNE destination de l'app `etrangere`.
async function attendreImmersion(page, cle, etrangere) {
  await expect(page.locator('.header-title')).toBeVisible()
  await expect(page.locator('aside.sidebar')).toHaveAttribute('data-app', cle)
  await expect(
    page.locator(`aside.sidebar .sidebar-nav a[href^="${etrangere}"]`),
    `fuite d'une autre app dans la nav de ${cle}`,
  ).toHaveCount(0)
}

test('ODY31: le paradigme ERP-Apps, de la grille à la sortie', async ({ page }) => {
  // ── 1. La porte d'entrée : mes apps, et rien d'autre ─────────────────────
  await ouvrirMenu(page)
  // La grille est celle des apps INSTALLÉES pour cette société et autorisées
  // pour ce rôle (ODY1). Les apps ci-dessous sont exactement celles dont
  // cross-app.spec.js prouve déjà qu'elles se résolvent pour le compte du
  // seed : leur tuile existe donc nécessairement, la grille et la coquille
  // lisant la MÊME source.
  for (const cle of ['crm', 'ventes', 'installations', 'stock', 'sav']) {
    await expect(tuile(page, cle), `tuile manquante : ${cle}`).toBeVisible()
  }

  // ── 2. Type-ahead à la Odoo : taper filtre, Entrée ouvre la première ─────
  const recherche = page.getByRole('searchbox', { name: /Rechercher une application/ })
  await recherche.fill('crm')
  await expect(page.getByRole('heading', { name: 'Résultats' })).toBeVisible()
  await expect(tuile(page, 'crm')).toBeVisible()
  await expect(page.locator('.home-menu-cell[data-app="ventes"]')).toHaveCount(0)
  await recherche.press('Enter')

  // ── 3. Immersion CRM : on est DANS une app ───────────────────────────────
  await attendreImmersion(page, 'crm', '/ventes')
  // L'identité de l'app est lisible dans la topbar (ODY5) : l'utilisateur sait
  // toujours où il est.
  await expect(page.locator('.header-app-pill-name')).toHaveText('CRM')

  // ── 4. Un lien CROISÉ bascule proprement sur l'app cible ─────────────────
  // Parcours RÉEL recensé par l'audit ODY7 : depuis la liste Clients (CRM),
  // l'action de ligne « Nouveau devis » ouvre le générateur, qui appartient à
  // Ventes. Le kebab de ligne est PERSISTANT (DataTable H131), donc atteignable
  // sans survol — même sélecteur que mobile.spec.js.
  await page.goto('/crm')
  // Le titre porte le compteur (« Clients 5 ») : préfixe, jamais nom exact.
  await expect(page.getByRole('heading', { name: /^Clients/ }).first()).toBeVisible()
  const kebab = page.getByRole('button', { name: "Plus d'actions sur la ligne" }).first()
  await expect(kebab).toBeVisible({ timeout: 20_000 })
  await kebab.click()
  await page.getByRole('menuitem', { name: 'Nouveau devis' }).click()

  await expect(page).toHaveURL(/\/ventes\/devis\/nouveau/)
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' })).toBeVisible()
  // La coquille est ENTIÈREMENT celle de Ventes : aucun reste de CRM.
  await attendreImmersion(page, 'ventes', '/crm')
  await expect(page.locator('.header-app-pill-name')).toHaveText('VENTES')

  // ── 5. LA sortie canonique : le ⊞ de l'en-tête (ODY5) ────────────────────
  // Ce bouton, et lui seul, est la sortie testée. Le lanceur overlay VX9 reste
  // un raccourci power-user, jamais la sortie. Le rôle `button` le distingue du
  // jumeau au pied de la Sidebar, qui est un `link` de même nom.
  await page.getByRole('button', { name: 'Toutes les apps' }).click()
  await expect(page).toHaveURL(/\/apps/)
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
  // De retour au neutre : plus aucune app n'est « ouverte » (l'attribut
  // `data-app` n'est même pas posé — Sidebar le rend `undefined`).
  await expect(page.locator('aside.sidebar[data-app]')).toHaveCount(0)

  // ── 6. Une app non activée : une vraie porte, pas un renvoi muet (ODY8) ──
  // On atteint l'écran par SA route. Déclencher la redirection demanderait de
  // désactiver un module pour la société du seed (mutation d'un réglage
  // partagé par toute la suite) ; le garde lui-même — UNE implémentation, deux
  // points d'appel — est verrouillé par les tests du routeur.
  await page.goto('/app-non-activee?app=flotte')
  const ecran = page.getByTestId('app-non-activee')
  await expect(ecran).toBeVisible()
  // L'app est NOMMÉE (son nom de catalogue) et la marche à suivre est donnée.
  await expect(ecran).toContainText('FLOTTE')
  await expect(ecran).toContainText(/activée/)
  await ecran.getByRole('link', { name: /Menu d’accueil|Menu d'accueil/ }).click()
  await expect(page).toHaveURL(/\/apps/)

  // ── 7. Le même paradigme au pouce (ODY6) ─────────────────────────────────
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
  // Le Menu d'accueil EST l'accueil mobile : aucune barre d'onglets qui
  // pointerait vers l'écran courant.
  await expect(page.locator('nav.bottom-tabbar')).toHaveCount(0)

  await tuile(page, 'crm').click()
  await attendreImmersion(page, 'crm', '/ventes')
  const tabbar = page.locator('nav.bottom-tabbar')
  await expect(tabbar).toBeVisible()
  await expect(tabbar).toHaveAttribute('data-app', 'crm')
  // La barre est SCOPÉE : plus d'onglet « Accueil » figé sur /dashboard, aucune
  // destination d'une autre app…
  await expect(tabbar.locator('a[href="/dashboard"]')).toHaveCount(0)
  await expect(tabbar.locator('a[href^="/ventes"]')).toHaveCount(0)
  // …et l'onglet « Apps » est la sortie au pouce.
  const ongletApps = tabbar.getByRole('link', { name: 'Apps' })
  await expect(ongletApps).toBeVisible()
  await ongletApps.click()
  await expect(page).toHaveURL(/\/apps/)
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
})
