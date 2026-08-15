// NTP2P43 — RFQ multi-fournisseurs → attribution → BCF verrouillé.
//
// Parcours : création d'une RFQ (écran interne « Consultation fournisseurs »,
// PAS la page publique sans login — celle-ci a déjà ses propres tests XPUR21) →
// invitation de fournisseurs catalogue → saisie de 3 offres (2 fournisseurs
// catalogue + 1 nom libre, la base démo n'en seed que 2) → attribution au
// moins-disant (`retenir`) → vérifie que le BCF adjugé porte EXACTEMENT le
// prix et le fournisseur de l'offre retenue (YPROC6, vue `views/rfq.py`).
import { test, expect } from '@playwright/test'
import { uniq } from './helpers'

test('NTP2P43: RFQ multi-fournisseurs → attribution → BCF verrouillé', async ({ page }) => {
  const objet = uniq('E2E RFQ')

  await page.goto('/chantiers/consultations')
  await expect(page.getByRole('heading', { name: 'Consultation fournisseurs' })).toBeVisible()

  // ── 1) Créer la RFQ ──────────────────────────────────────────────────────
  await page.getByRole('button', { name: 'Nouvelle RFQ' }).click()
  await page.locator('#rfq-objet').fill(objet)
  await page.getByRole('button', { name: 'Créer' }).click()
  await expect(page.getByRole('heading', { name: objet })).toBeVisible()

  // ── 2) Inviter les 2 fournisseurs catalogue de la base démo ─────────────
  for (const fournisseur of ['SunPro Maroc', 'Electra Distribution']) {
    await page.getByRole('button', { name: 'Consulter' }).click()
    await page.locator('#rfq-fournisseur').selectOption({ label: fournisseur })
    await page.getByRole('button', { name: 'Ajouter' }).click()
    await expect(page.getByText(fournisseur).first()).toBeVisible()
  }

  // ── 3) Saisir 3 offres — la moins chère est un fournisseur CATALOGUE
  //      (seule une offre à fournisseur catalogue peut adjuger un BCF). ────
  const offres = [
    { fournisseur: 'SunPro Maroc', montant: '9500', delai: '10' },
    { fournisseur: 'Electra Distribution', montant: '12000', delai: '15' },
    { nomLibre: 'Sous-traitant local E2E', montant: '15000', delai: '5' },
  ]
  for (const offre of offres) {
    await page.getByRole('button', { name: 'Nouvelle offre' }).click()
    if (offre.fournisseur) {
      await page.locator('#offre-fournisseur').selectOption({ label: offre.fournisseur })
    } else {
      await page.locator('#offre-libre').fill(offre.nomLibre)
    }
    await page.locator('#offre-montant').fill(offre.montant)
    await page.locator('#offre-delai').fill(offre.delai)
    await page.getByRole('button', { name: 'Créer' }).click()
  }
  await expect(page.getByText('Offres comparées (3)')).toBeVisible()

  // ── 4) Retenir l'offre la moins chère (SunPro Maroc, 9500) ──────────────
  const ligneSunPro = page.locator('[data-testid^="offre-"]', { hasText: 'SunPro Maroc' })
  await expect(ligneSunPro.getByText('Moins chère')).toBeVisible()
  await ligneSunPro.getByRole('button', { name: 'Retenir' }).click()
  await expect(ligneSunPro.getByText('Retenue')).toBeVisible()

  // ── 5) Le BCF adjugé porte EXACTEMENT le prix + le fournisseur retenus ──
  const rfqRes = await page.request.get(
    `/api/django/installations/rfq/?page_size=200`)
  expect(rfqRes.ok()).toBeTruthy()
  const rfqRows = (await rfqRes.json()).results ?? (await rfqRes.json())
  const rfq = rfqRows.find((r) => r.objet === objet)
  expect(rfq).toBeTruthy()
  expect(rfq.bon_commande).toBeTruthy()

  const bcfRes = await page.request.get(
    `/api/django/stock/bons-commande-fournisseur/${rfq.bon_commande}/`)
  expect(bcfRes.ok()).toBeTruthy()
  const bcf = await bcfRes.json()
  expect(bcf.fournisseur_nom).toBe('SunPro Maroc')
  expect(Number(bcf.total_achat)).toBeCloseTo(9500, 2)
})
