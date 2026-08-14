// E3 lead lifecycle · E5 inline bill editing · E6 reassignment · E7 stage moves.
import { test, expect } from '@playwright/test'
import {
  gotoLeads, setLeadsView, createLead, openLead, closeLeadModal,
  generateAutoDevis, uniq, ADMIN, SECOND_USER,
  assertNoSeriousA11yViolations, boutonNouveauLead,
} from './helpers'

const modalXl = (page) => page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })

test('E3: create a lead, see it in list + kanban, open it', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Lifecycle') })

  await setLeadsView(page, 'kanban')
  await expect(page.locator('article.kb-card', { hasText: name })).toBeVisible()

  await setLeadsView(page, 'liste')
  await expect(page.locator('tr.lv-row', { hasText: name })).toBeVisible()

  await openLead(page, name)
  await expect(modalXl(page).locator('.modal-title')).toContainText(name)
  await closeLeadModal(page)
})

test('E5: the winter bill on a lead autosaves and reflects', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Bill') }) // no bill yet
  await openLead(page, name)
  const modal = modalXl(page)

  // LW13 — la saisie facture inline a disparu : la facture d'hiver est devenue
  // un champ normal (#lf-facture-hiver, section Énergie), AUTOSAUVÉ par le moteur
  // (plus de bouton de sauvegarde manuelle).
  const bill = modal.locator('#lf-facture-hiver')
  await bill.fill('800')
  await expect(bill).toHaveValue('800')
  // L'autosauvegarde confirme via le chip « ✓ Enregistré ».
  await expect(modal.getByText('✓ Enregistré')).toBeVisible()
  await closeLeadModal(page)

  // Réouverture : la valeur est bien persistée.
  await openLead(page, name)
  const reouvert = modalXl(page)
  // ROUND 5 (draftCore.sectionAutoRepliee) — une section dont le CŒUR est
  // complet se rouvre REPLIÉE, et un corps replié quitte le DOM
  // (SectionsPane). Le cœur de « Profil énergétique » est justement
  // `facture_hiver`, qu'on vient de renseigner : le champ n'est donc plus
  // monté à la réouverture. On déplie la section par son en-tête (son
  // affordance publique, `aria-expanded`) avant de relire la valeur — la
  // preuve reste la MÊME : la facture saisie a bien été persistée côté
  // serveur et se relit telle quelle.
  const energie = reouvert.locator('.lw-section[data-nav-id="energie"]')
  const teteEnergie = energie.locator('.lw-section-head')
  await expect(teteEnergie).toBeVisible() // le centre est monté avant qu'on lise son état
  if ((await teteEnergie.getAttribute('aria-expanded')) === 'false') {
    await teteEnergie.click()
  }
  // À la réouverture le champ lit l'écho serveur (décimal sérialisé en chaîne
  // « 800.00 ») — pendant la frappe, le texte tapé « 800 » ne snappe JAMAIS
  // (draftCore SET_FIELD garde le texte tapé, critique Fable #1).
  await expect(energie.locator('#lf-facture-hiver')).toHaveValue(/^800([.,]00)?$/)
  await closeLeadModal(page)
})

test('E6: reassign a lead from a kanban card and from the lead view', async ({ page }) => {
  await gotoLeads(page)
  await setLeadsView(page, 'kanban')
  const name = await createLead(page, { nom: uniq('Reassign') })

  // ── from the kanban card (immediate PATCH) ──
  const card = page.locator('article.kb-card', { hasText: name })
  await expect(card).toBeVisible()
  await card.locator('.ap-trigger').click()
  await page.locator('.ap-menu .ap-item', { hasText: SECOND_USER }).click()
  await expect(card.locator('.ap-trigger')).toHaveAttribute('title', new RegExp(SECOND_USER))

  // ── from the lead view (rail identité : picker → autosave) ──
  await openLead(page, name)
  const modal = modalXl(page)
  // VX71 — scan axe DYNAMIQUE : le lead EN ÉDITION (dialog ouvert, picker
  // assignee monté) est un état qu'un scan statique de build ne voit jamais.
  await assertNoSeriousA11yViolations(page, { include: '[role="dialog"]' })
  // LW13 — le responsable vit dans la triade du rail identité (.lw-rail-field),
  // plus dans un .form-group ; l'édition est AUTOSAUVÉE (aucune sauvegarde manuelle).
  const respField = modal.locator('.lw-rail-field', { hasText: 'Responsable' })
  await respField.locator('.ap-trigger').click()
  await page.locator('.ap-menu .ap-item', { hasText: ADMIN.username }).click()
  await expect(modal.getByText('✓ Enregistré')).toBeVisible()
  await closeLeadModal(page)

  await openLead(page, name)
  await expect(
    modalXl(page).locator('.lw-rail-field', { hasText: 'Responsable' }).locator('.ap-name'),
  ).toContainText(ADMIN.username)
  await closeLeadModal(page)
})

test('E7: move a lead between stages, including into Signé', async ({ page }) => {
  await gotoLeads(page)
  // Needs a devis so the Signé dialog can record the accepted quote.
  const name = await createLead(page, { nom: uniq('Stage'), facture: 950 })
  await openLead(page, name)
  await generateAutoDevis(page)
  await page.locator('.ldp-header .modal-close').click()
  await closeLeadModal(page)

  // Stage moves happen inline in the list (the canonical control besides kanban).
  await setLeadsView(page, 'liste')
  const row = page.locator('tr.lv-row', { hasText: name })

  // NEW → CONTACTED (a plain transition).
  await row.locator('.ie-cell').filter({ hasText: 'Nouveau' }).click()
  await page.locator('select.ie-input').selectOption({ label: 'Contacté' })
  await page.keyboard.press('Tab') // blur → commit
  await expect(row).toContainText('Contacté')

  // → Signé opens the acceptance dialog (A2) instead of moving directly.
  await row.locator('.ie-cell').filter({ hasText: 'Contacté' }).click()
  await page.locator('select.ie-input').selectOption({ label: 'Signé' })
  await page.keyboard.press('Tab')

  // VX182 — SigneDialog est passé à ResponsiveDialog (Radix) : son conteneur
  // n'a plus la classe `.modal`, mais garde son en-tête `<h3 class="modal-title">`.
  // On cible donc LE dialogue par son titre — même preuve (la boîte
  // d'acceptation s'ouvre au lieu d'un passage direct en Signé, puis disparaît
  // une fois confirmée).
  const dialog = page.locator('[role="dialog"]')
    .filter({ has: page.locator('.modal-title', { hasText: 'Passer en « Signé »' }) })
  await expect(dialog).toBeVisible()
  const devisSelect = dialog.locator('#sd-devis')
  const values = await devisSelect
    .locator('option')
    .evaluateAll((opts) => opts.map((o) => o.value).filter(Boolean))
  expect(values.length).toBeGreaterThan(0)
  await devisSelect.selectOption(values[0])
  // Two-option devis require an explicit battery choice.
  const optionRadios = dialog.locator('input[name="sd-option"]')
  if (await optionRadios.count()) {
    await optionRadios.first().check()
  }
  // The label uses a typographic apostrophe (l’acceptation) — match either.
  await dialog.getByRole('button', { name: /Confirmer l['’]acceptation/ }).click()
  await expect(dialog).toHaveCount(0)

  await expect(page.locator('tr.lv-row', { hasText: name })).toContainText('Signé')
})

// VX71 — a11y DYNAMIQUE : le FORMULAIRE EN ERREUR (soumission avec Nom vide)
// est un état affiché uniquement après interaction — un scan statique ne le
// rend jamais. Le formulaire est `noValidate` (règle générateur de devis) :
// la validation « Nom requis » est gérée côté React (LeadForm.jsx).
test('VX71: lead form validation error state has no serious/critical a11y violation', async ({ page }) => {
  await gotoLeads(page)
  await boutonNouveauLead(page).click()
  const modal = page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })
  await expect(modal.getByRole('heading', { name: 'Nouveau lead' })).toBeVisible()

  // Nom laissé vide → soumission déclenche l'erreur inline.
  await modal.getByRole('button', { name: 'Créer le lead' }).click()
  await expect(modal.getByText('Nom requis')).toBeVisible()

  await assertNoSeriousA11yViolations(page, { include: '[role="dialog"]' })

  await modal.locator('.modal-close').first().click()
})

// LB34 — passe axe FINALE sur la page LEADS redessinée (blueprint §STRATÉGIE
// E2E, clôture du batch LB). VX71 ci-dessus ne scanne que le FORMULAIRE lead ;
// la refonte a ajouté des surfaces interactives (tuiles KPI `aria-pressed`,
// ViewSwitcher `radiogroup`, colonnes nommées + chevrons de repli labellisés,
// zones de scroll `tabindex=0`+label, menu ••• DropdownMenu, barre bulk
// flottante). On scanne la page réelle en kanban PUIS en liste — scope
// `.lp-page` (la surface REDESSINÉE ; le chrome global sidebar/header a son
// propre garde et n'est pas l'objet de cette tâche) — plus la barre flottante
// et le menu ••• ouvert (états montés au clic, jamais vus par un scan statique
// de build). Le menu Radix est portalé HORS de `.lp-page` → scanné à part.
// Échoue UNIQUEMENT sur serious/critical (même seuil anti-flake que VX71).
test('LB34: la page leads redessinée (KPI + kanban + barre flottante + menu ••• + liste) — 0 violation a11y sérieuse', async ({ page }) => {
  await gotoLeads(page) // vue kanban par défaut
  // LB51 (blueprint cockpit) : les tuiles KPI sont devenues des chips-filtres
  // comptées dans la ligne de contrôle ; le picker de vues porte le titre.
  await expect(page.locator('.lp-quick-chips')).toBeVisible()
  await expect(page.getByRole('button', { name: /Vues — vue active/ })).toBeVisible()
  await expect(page.locator('.kb-board')).toBeVisible()
  // Cockpit + board redessinés (KPI, ViewSwitcher, colonnes/chevrons/zones de scroll).
  await assertNoSeriousA11yViolations(page, { include: '.lp-page' })

  // Barre bulk FLOTTANTE : révélée en cochant une carte (la case existe dans le
  // DOM en `opacity:0` jusqu'au survol/sélection → `force` sans dépendre du hover).
  await page.locator('.kb-card-check').first().check({ force: true })
  await expect(page.locator('.lp-bulk-float')).toBeVisible()
  await assertNoSeriousA11yViolations(page, { include: '.lp-bulk-float' })
  await page.keyboard.press('Escape') // vide la sélection → referme la barre
  await expect(page.locator('.lp-bulk-float')).toHaveCount(0)

  // Menu ••• ouvert (DropdownMenu Radix, portalé sur <body>).
  await page.getByRole('button', { name: "Plus d'actions" }).click()
  await expect(page.getByRole('menu')).toBeVisible()
  await assertNoSeriousA11yViolations(page, { include: '[role="menu"]' })
  await page.keyboard.press('Escape') // referme le menu avant de changer de vue

  // Vue liste : table épinglée, cellules d'édition en place, chooser de colonnes.
  await setLeadsView(page, 'liste')
  await expect(page.locator('.lv-wrap')).toBeVisible()
  await assertNoSeriousA11yViolations(page, { include: '.lp-page' })
})

// LWZ — le menu « ⋯ » du rail identité DANS l'enveloppe Dialog (kanban/liste).
// Le contenu du menu est portalé en FRÈRE du DialogContent (--z-modal 1300) :
// à --z-dropdown (1000) il se peignait DERRIÈRE le panneau opaque — menu
// « ouvert » (aria-expanded) mais invisible, clic muet (bug prod du 14/08).
// Aucun autre test n'ouvre ce menu-là : LB34 teste le ••• de la PAGE liste
// (hors dialog), IdentityRail.test.jsx rend le rail sans Dialog en jsdom (aucun
// empilement calculé). Le clic Playwright sur un item recouvert échoue (contrôle
// d'actionnabilité « reçoit les événements pointeur ») → ce test verrouille
// l'ordre de peinture (--z-popover requis sur DropdownMenuContent).
test('LWZ: le menu ⋯ du rail est visible et cliquable dans le Dialog lead', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('MenuRail') })
  await openLead(page, name)

  await modalXl(page).getByRole('button', { name: "Plus d'actions" }).click()
  const menu = page.getByRole('menu')
  await expect(menu).toBeVisible()
  await expect(menu.getByRole('menuitem', { name: /Concevoir la toiture \(3D\)/ })).toBeVisible()

  // Clic RÉEL sur un item — un item peint sous la modale le ferait échouer.
  await menu.getByRole('menuitem', { name: 'Convertir en client' }).click()
  const convert = page.locator('[role="dialog"]')
    .filter({ has: page.getByRole('heading', { name: 'Convertir en client' }) })
  await expect(convert).toBeVisible()
  await convert.locator('.modal-close').click()
  await expect(convert).toHaveCount(0)
  await closeLeadModal(page)
})
