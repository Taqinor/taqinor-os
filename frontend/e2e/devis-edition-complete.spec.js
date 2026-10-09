// EDC10 — Preuves EN DIRECT de l'Édition complète du devis (Groupe EDC,
// docs/plans/PLAN_AUDIT_TRANSVERSE.md) : l'écran RÉEL, servi par la pile
// locale, à trois largeurs d'écran. Chaque assertion correspond à un constat
// du 09/10/2026 (fondateur) : table qui tient sans défilement horizontal,
// barre horizontale collante quand elle déborde, Entrée qui n'enregistre
// jamais, Échap qui prévient, enregistrement qui ne quitte plus l'éditeur,
// page pleine sans débordement avec le rail replié.
import { test, expect } from '@playwright/test'
import {
  gotoLeads, createLead, openLead, generateAutoDevis, uniq, API_DJANGO, lireJson, listeDe,
} from './helpers'

const GRAND_ECRAN = { width: 1600, height: 1000 }
const PORTABLE = { width: 1366, height: 768 }
// Sous ~900 px de conteneur la table déborde (somme des largeurs minimales
// des colonnes + colonne « Villa ») : c'est le cas qui exige la barre proxy.
const ETROIT = { width: 960, height: 700 }

/** Largeurs réelles du wrap de la table (débordement ⇔ scrollWidth > clientWidth). */
async function mesuresTable(page) {
  return page.locator('.lines-table-wrap').first().evaluate((el) => ({
    scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
  }))
}

/** Ouvre l'Édition complète depuis l'aperçu du panneau devis de la fiche lead. */
async function ouvrirEditionComplete(page) {
  await page.getByRole('button', { name: /Édition complète/ }).first().click()
  await expect(page.locator('.gen-root')).toBeVisible()
  // Jamais de passage par un aperçu intermédiaire : le canvas PDF a disparu.
  await expect(page.locator('.ldp-pdf-area canvas')).toHaveCount(0)
}

/** Le générateur et ses lignes sont montés (jamais mesurer une table vide). */
async function attendreLignes(page) {
  await expect(page.getByRole('toolbar', { name: /Actions du devis/ })).toBeVisible()
  await expect(page.locator('tr[data-line-key]').first()).toBeVisible()
}

/** Rend l'éditeur « modifié ». La fenêtre de référence QJR581 (1,5 s après
 *  le chargement) absorbe une frappe trop précoce comme référence : on retape
 *  une valeur croissante jusqu'à ce que la pastille apparaisse. */
async function modifierJusquaPastille(page, champ) {
  let valeur = 2
  await expect.poll(async () => {
    valeur += 1
    await champ.fill(String(valeur))
    return page.getByTestId('gen-barre-non-enregistre').isVisible()
  }, { timeout: 15_000, intervals: [500] }).toBe(true)
}

test.describe('EDC10 — Édition complète du devis, en direct', () => {
  // Chaque parcours génère un devis automatique (rendu PDF ~30 s à froid) :
  // même budget que figures-parite.spec.js pour le même trajet.
  test.setTimeout(150_000)

  test('grand écran : table sans défilement, Entrée/Échap/Enregistrer ne jettent plus dehors', async ({ page }) => {
    await page.setViewportSize(GRAND_ECRAN)
    await gotoLeads(page)
    const nom = await createLead(page, { nom: uniq('EDC'), facture: 900 })
    await openLead(page, nom)
    await generateAutoDevis(page)
    await ouvrirEditionComplete(page)
    await attendreLignes(page)

    // (b) la table des lignes tient dans le panneau à 1 600 px — aucun
    // défilement horizontal, donc aucune barre proxy (celle de la table des
    // lignes : les tableaux d'étude en ont une aussi, dans une carte repliée).
    const m = await mesuresTable(page)
    expect(m.scrollWidth, `table ${m.scrollWidth}px dans ${m.clientWidth}px`).toBeLessThanOrEqual(m.clientWidth + 1)
    await expect(page.locator('.lines-table-wrap + .bdc-proxy')).toBeHidden()

    // La barre d'actions en tête est là, avec Enregistrer et Annuler.
    const barre = page.getByRole('toolbar', { name: /Actions du devis/ })
    await expect(barre.getByRole('button', { name: /Enregistrer/ })).toBeVisible()

    // (d) Entrée dans « Qté » : aucune soumission — aucune requête
    // replace-lines, l'éditeur reste monté.
    const ecritures = []
    page.on('request', (req) => { if (/replace-lines/.test(req.url())) ecritures.push(req.url()) })
    const lignes = page.locator('tr[data-line-key]')
    expect(await lignes.count(), 'un devis automatique a plusieurs lignes').toBeGreaterThan(1)
    const qte = lignes.first().locator('[data-role="line-qty"]')
    await qte.click()
    await qte.press('Enter')
    // Entrée a déplacé le focus sur la Qté de la ligne suivante (même colonne) :
    // la touche est traitée, et aucune écriture n'est partie.
    await expect(lignes.nth(1).locator('[data-role="line-qty"]')).toBeFocused()
    expect(ecritures).toHaveLength(0)
    await expect(page.locator('.gen-root')).toBeVisible()

    // (e) une frappe puis Échap : le dialogue « Quitter sans enregistrer ? »
    // s'affiche, « Rester » garde l'éditeur.
    await modifierJusquaPastille(page, qte)
    await qte.press('Escape')
    const dialogue = page.getByRole('alertdialog')
    await expect(dialogue).toBeVisible()
    await expect(dialogue).toContainText(/Quitter sans enregistrer/)
    await dialogue.getByRole('button', { name: /Rester/ }).click()
    await expect(dialogue).toBeHidden()
    await expect(page.locator('.gen-root')).toBeVisible()

    // (f) Enregistrer depuis la barre en tête : toast, éditeur toujours
    // monté, « Voir le PDF » offert ; la pastille s'éteint.
    await barre.getByRole('button', { name: /Enregistrer/ }).click()
    await expect(page.getByText(/Modifications enregistrées/)).toBeVisible({ timeout: 45_000 })
    await expect(page.locator('.gen-root')).toBeVisible()
    await expect(barre.getByRole('button', { name: /Voir le PDF/ })).toBeVisible()
    await expect(page.getByTestId('gen-barre-non-enregistre')).toBeHidden()
    expect(ecritures.length, 'un seul enregistrement').toBe(1)

    // Sans modification, Échap revient à l'aperçu (devis existant) sans dialogue.
    await page.keyboard.press('Escape')
    await expect(page.getByRole('alertdialog')).toHaveCount(0)
    await expect(page.locator('.ldp-pdf-area')).toBeVisible()
  })

  test('écran étroit : la barre horizontale collante est visible au milieu de la table', async ({ page }) => {
    await page.setViewportSize(GRAND_ECRAN)
    await gotoLeads(page)
    const nom = await createLead(page, { nom: uniq('EDCp'), facture: 900 })
    await openLead(page, nom)
    await generateAutoDevis(page)
    await ouvrirEditionComplete(page)
    await attendreLignes(page)

    // Colonne « Villa » en plus + conteneur étroit ⇒ la table déborde.
    await page.setViewportSize(ETROIT)
    const multi = page.locator('details', { hasText: 'Plusieurs propriétés' })
    if (!(await multi.evaluate((el) => el.open))) await multi.locator('summary').click()
    // Les options du Segmented sont des boutons radio (ui/Segmented.jsx).
    await page.getByRole('radio', { name: '+ Villas différentes' }).click()
    await expect.poll(async () => {
      const m = await mesuresTable(page)
      return m.scrollWidth > m.clientWidth + 1
    }, { message: 'la table doit déborder à 960 px avec la colonne Villa' }).toBe(true)

    // (c) descendre jusqu'au haut de la table : son pied est hors écran,
    // la barre proxy reste visible dans la fenêtre et pilote la table.
    const table = page.locator('.lines-table').first()
    await table.locator('thead').scrollIntoViewIfNeeded()
    // LA barre de la table des lignes (frère immédiat du wrap) — pas celle,
    // repliée, des tableaux d'étude plus haut dans le DOM.
    const proxy = page.locator('.lines-table-wrap + .bdc-proxy')
    await expect(proxy).toBeVisible()
    const boite = await proxy.boundingBox()
    expect(boite.y + boite.height).toBeLessThanOrEqual(ETROIT.height + 1)
    // Le pied de la table est hors écran : la barre est bien « à chaque hauteur ».
    const basTable = await table.evaluate((el) => el.getBoundingClientRect().bottom)
    expect(basTable).toBeGreaterThan(ETROIT.height)
    const avant = await page.locator('.lines-table-wrap').first().evaluate((el) => el.scrollLeft)
    await proxy.evaluate((el) => { el.scrollLeft = 120 })
    await expect.poll(() => page.locator('.lines-table-wrap').first().evaluate((el) => el.scrollLeft)).toBeGreaterThan(avant)
  })

  test('page pleine à 1 366 px : rail replié, table sans débordement', async ({ page }) => {
    await page.setViewportSize(GRAND_ECRAN)
    await gotoLeads(page)
    const nom = await createLead(page, { nom: uniq('EDCpage'), facture: 900 })
    await openLead(page, nom)
    await generateAutoDevis(page)
    const ref = (await page.locator('.ldp-ref').first().textContent())?.trim()
    expect(ref, 'référence du devis affichée dans le panneau').toBeTruthy()
    // La liste est triée `-date_creation` (Devis.Meta) : le devis qui vient
    // d'être créé est en page 1 ; on tolère deux pages de plus par prudence.
    let devis = null
    let url = `${API_DJANGO}/ventes/devis/`
    for (let page_ = 0; page_ < 3 && url && !devis; page_ += 1) {
      const corps = await lireJson(await page.request.get(url), 'liste des devis')
      devis = listeDe(corps).find((d) => d.reference === ref) || null
      url = corps?.next || null
    }
    expect(devis, `devis ${ref} retrouvé par l'API`).toBeTruthy()

    // (g) page pleine sur un portable avec barre latérale : le rail se replie
    // (container query) et la table tient.
    await page.setViewportSize(PORTABLE)
    await page.goto(`/ventes/devis/nouveau?edit=${devis.id}`)
    await expect(page.locator('.gen-root')).toBeVisible()
    await attendreLignes(page)
    await expect(page.locator('.gen-summary-rail')).toBeHidden()
    const m = await mesuresTable(page)
    expect(m.scrollWidth, `table ${m.scrollWidth}px dans ${m.clientWidth}px`).toBeLessThanOrEqual(m.clientWidth + 1)
  })
})
