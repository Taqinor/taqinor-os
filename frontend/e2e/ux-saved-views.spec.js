// NTUX36 — cycle de vie complet d'une vue sauvegardée partagée (NTUX1/NTUX2) :
// créer une vue filtrée -> la partager à l'équipe et la définir par défaut
// pour un rôle -> vérifier qu'elle s'applique automatiquement AU CHARGEMENT
// pour une session de ce même rôle -> la dupliquer en vue personnelle et la
// renommer sans affecter l'originale.
//
// ÉCRAN : `/ventes/devis` (DevisList.jsx), pas `/crm/leads`. `ViewsManagerPopover`
// (NTUX2, le sélecteur de vues serveur) n'est câblé QUE sur Devis/Factures/
// Tickets/Stock à ce jour — `/crm/leads` utilise encore l'ancien hook
// `useSavedViews` (localStorage, jamais migré côté écran). Vérifié dans le
// code (`grep ViewsManagerPopover frontend/src`) avant d'écrire ce spec :
// cibler l'écran RÉELLEMENT câblé, jamais celui du libellé du plan.
//
// RÔLE : le jeu de données `seed_demo` ne contient QUE deux comptes
// (`demo_admin` = rôle système « Directeur », `demo_resp` = rôle système
// « Responsable ») — deux rôles DIFFÉRENTS, et « Définir par défaut pour mon
// rôle » ne pose le défaut QUE pour le rôle de l'appelant (jamais un rôle
// arbitraire choisi). Une propagation cross-UTILISATEUR PHYSIQUE avec deux
// comptes du MÊME rôle exigerait de provisionner un 3ᵉ compte. Ce spec prouve
// donc le mécanisme réel testable avec les fixtures existantes : propagation
// CROSS-SESSION (deux contextes navigateur indépendants, même compte
// `demo_admin`/rôle Directeur — exactement le mécanisme qui casserait si
// NTUX2 régressait, cf. `useServerSavedViews.js` `defaultRoleView`).
import { test, expect } from '@playwright/test'
import { uniq, ADMIN, uiLogin } from './helpers'

const ECRAN_DEVIS = '/ventes/devis'

test('NTUX36: créer, partager, définir par défaut de rôle, propager en session neuve, dupliquer', async ({ page, browser }) => {
  const nomVue = uniq('Vue E2E Partagée')

  await page.goto(ECRAN_DEVIS)
  const enregistrerBtn = page.getByRole('button', { name: /Enregistrer cette vue/ })
  await expect(
    enregistrerBtn,
    'la barre de filtres (et « Enregistrer cette vue ») n\'apparaît que si la société de démonstration a au moins un devis',
  ).toBeVisible()

  // ── 1) Directeur crée une vue FILTRÉE ("Envoyé") ────────────────────────
  await page.getByRole('radio', { name: 'Envoyé' }).click()
  await expect(page.getByRole('radio', { name: 'Envoyé' })).toHaveAttribute('aria-checked', 'true')

  page.once('dialog', (dialog) => dialog.accept(nomVue))
  await enregistrerBtn.click()

  // ── 2) Ouvre « Vues », retrouve la vue en « Mes vues » ──────────────────
  const ouvrirVues = page.getByTestId('uxviews-open-btn')
  await ouvrirVues.click()
  const rowOriginale = page.getByTestId('uxviews-view-row').filter({ hasText: nomVue })
  await expect(rowOriginale).toBeVisible()

  // ── 3) La partage à l'équipe puis la définit par défaut pour SON rôle
  //      (Directeur) — l'action pose visibilite=EQUIPE ET est_defaut_role
  //      EN UN SEUL geste côté serveur (SavedViewViewSet.definir_par_defaut_role).
  await rowOriginale.getByRole('button', { name: 'Définir par défaut pour mon rôle' }).click()
  await expect(page.getByText(/est maintenant la vue par défaut de votre rôle/)).toBeVisible()
  // L'étoile de « vue par défaut » (NTUX2) marque désormais la ligne.
  await expect(rowOriginale.locator('svg.fill-warning')).toBeVisible()
  await page.keyboard.press('Escape') // ferme le popover

  // Repli le filtre à « Tous » pour prouver que la PROCHAINE ouverture de
  // l'écran réapplique bien le filtre de la vue par défaut, pas un état
  // laissé par cette session.
  await page.getByRole('radio', { name: 'Tous' }).click()

  // ── 4) Session NEUVE (même rôle Directeur) : la vue par défaut s'applique
  //      AUTOMATIQUEMENT au chargement, sans action utilisateur ────────────
  const secondContext = await browser.newContext()
  const secondPage = await secondContext.newPage()
  try {
    await uiLogin(secondPage, ADMIN)
    await expect(secondPage).toHaveURL(/\/apps/)
    await secondPage.goto(ECRAN_DEVIS)
    await expect(
      secondPage.getByRole('radio', { name: 'Envoyé' }),
      'la vue par défaut du rôle Directeur doit appliquer son filtre "Envoyé" sans action utilisateur',
    ).toHaveAttribute('aria-checked', 'true', { timeout: 15_000 })

    // ── 5) Duplique la vue d'équipe en vue PERSONNELLE, la renomme ────────
    await secondPage.getByTestId('uxviews-open-btn').click()
    const rowEquipe = secondPage.getByTestId('uxviews-view-row').filter({ hasText: nomVue })
    await expect(rowEquipe).toBeVisible()
    await rowEquipe.getByRole('button', { name: 'Dupliquer' }).click()

    const nomCopie = `${nomVue} (copie)`
    const rowCopie = secondPage.getByTestId('uxviews-view-row').filter({ hasText: nomCopie })
    await expect(rowCopie).toBeVisible()

    const nomModifie = uniq('Vue perso modifiée')
    await rowCopie.getByRole('button', { name: 'Renommer' }).click()
    const input = secondPage.getByDisplayValue(nomCopie)
    await input.fill(nomModifie)
    await input.press('Enter')
    await expect(secondPage.getByTestId('uxviews-view-row').filter({ hasText: nomModifie })).toBeVisible()

    // ── 6) L'originale partagée à l'équipe n'a JAMAIS bougé ───────────────
    await expect(
      secondPage.getByTestId('uxviews-view-row').filter({ hasText: nomVue, hasNotText: nomModifie }),
      'modifier la copie personnelle ne doit jamais renommer la vue d\'équipe originale',
    ).toBeVisible()
  } finally {
    await secondContext.close()
  }
})
