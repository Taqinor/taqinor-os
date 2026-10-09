// EDC10 — Preuves EN DIRECT de l'Édition complète du devis (Groupe EDC,
// docs/plans/PLAN_AUDIT_TRANSVERSE.md) : l'écran RÉEL, servi par la pile
// locale, à deux largeurs d'écran. Chaque assertion correspond à un constat
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

test.describe('EDC10 — Édition complète du devis, en direct', () => {
  test('grand écran : table sans défilement, Entrée/Échap/Enregistrer ne jettent plus dehors', async ({ page }) => {
    await page.setViewportSize(GRAND_ECRAN)
    await gotoLeads(page)
    const nom = await createLead(page, { nom: uniq('EDC'), facture: 900 })
    await openLead(page, nom)
    await generateAutoDevis(page)
    await ouvrirEditionComplete(page)

    // (b) la table des lignes tient dans le panneau à 1 600 px — aucun
    // défilement horizontal, donc aucune barre proxy.
    const m = await mesuresTable(page)
    expect(m.scrollWidth, `table ${m.scrollWidth}px dans ${m.clientWidth}px`).toBeLessThanOrEqual(m.clientWidth + 1)
    await expect(page.locator('.bdc-proxy:visible')).toHaveCount(0)

    // La barre d'actions en tête est là, avec Enregistrer et Annuler.
    const barre = page.getByRole('toolbar', { name: /Actions du devis/ })
    await expect(barre).toBeVisible()
    await expect(barre.getByRole('button', { name: /Enregistrer/ })).toBeVisible()

    // (d) Entrée dans « Qté » : aucune soumission — aucune requête
    // replace-lines, l'éditeur reste monté.
    const ecritures = []
    page.on('request', (req) => { if (/replace-lines/.test(req.url())) ecritures.push(req.url()) })
    const qte = page.locator('tr[data-line-key] [data-role="line-qty"]').first()
    await qte.click()
    await qte.press('Enter')
    await page.waitForTimeout(500)
    expect(ecritures).toHaveLength(0)
    await expect(page.locator('.gen-root')).toBeVisible()
    // Entrée a déplacé le focus sur la Qté de la ligne suivante (même colonne).
    const lignes = page.locator('tr[data-line-key]')
    if (await lignes.count() > 1) {
      await expect(lignes.nth(1).locator('[data-role="line-qty"]')).toBeFocused()
    }

    // (e) une frappe puis Échap : le dialogue « Quitter sans enregistrer ? »
    // s'affiche, « Rester » garde l'éditeur.
    await qte.fill('3')
    await expect(page.getByText(/Modifications non enregistrées/)).toBeVisible()
    await qte.press('Escape')
    const dialogue = page.getByRole('alertdialog')
    await expect(dialogue).toBeVisible()
    await expect(dialogue).toContainText(/Quitter sans enregistrer/)
    await dialogue.getByRole('button', { name: /Rester/ }).click()
    await expect(page.locator('.gen-root')).toBeVisible()

    // (f) Enregistrer depuis la barre en tête : toast, éditeur toujours
    // monté, « Voir le PDF » offert ; la pastille s'éteint.
    await barre.getByRole('button', { name: /Enregistrer/ }).click()
    await expect(page.getByText(/Modifications enregistrées/)).toBeVisible()
    await expect(page.locator('.gen-root')).toBeVisible()
    await expect(barre.getByRole('button', { name: /Voir le PDF/ })).toBeVisible()
    await expect(page.getByText(/Modifications non enregistrées/)).toHaveCount(0)
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

    // Colonne « Villa » en plus + conteneur étroit ⇒ la table déborde.
    await page.setViewportSize(ETROIT)
    const multi = page.locator('details', { hasText: 'Plusieurs propriétés' })
    if (!(await multi.getAttribute('open'))) await multi.locator('summary').click()
    await page.getByRole('button', { name: '+ Villas différentes' }).click()
    await expect.poll(async () => {
      const m = await mesuresTable(page)
      return m.scrollWidth > m.clientWidth + 1
    }, { message: 'la table doit déborder à 960 px avec la colonne Villa' }).toBe(true)

    // (c) descendre jusqu'au milieu de la table : son pied est hors écran,
    // la barre proxy reste visible dans la fenêtre et pilote la table.
    const table = page.locator('.lines-table').first()
    await table.locator('thead').scrollIntoViewIfNeeded()
    const proxy = page.locator('.bdc-proxy').first()
    await expect(proxy).toBeVisible()
    const boite = await proxy.boundingBox()
    expect(boite.y + boite.height).toBeLessThanOrEqual(ETROIT.height + 1)
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
    await expect(page.getByRole('toolbar', { name: /Actions du devis/ })).toBeVisible()
    await expect(page.locator('.gen-summary-rail')).toBeHidden()
    const m = await mesuresTable(page)
    expect(m.scrollWidth, `table ${m.scrollWidth}px dans ${m.clientWidth}px`).toBeLessThanOrEqual(m.clientWidth + 1)
  })
})
