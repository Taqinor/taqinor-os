// NTI18N47 — parcours e2e « bascule de langue + devis multilingue » :
// interface en arabe (NTI18N8/N93) → client `langue_document=ar` → devis pour
// CE client → génération du PDF premium sans erreur de rendu (NTI18N4/N5).
//
// CE QUE CE SPEC ASSERTE (chaque sélecteur est vérifié dans le code de l'app) :
//   1. le sélecteur de langue du Header (`data-testid="lang-switcher"` /
//      `lang-option-ar`, components/layout/LanguageSwitcher.jsx) bascule
//      `<html>` en `dir="rtl" lang="ar"` — contrat déjà verrouillé côté
//      unitaire (frontend/src/i18n/i18n.test.jsx) ;
//   2. « Langue des documents » du formulaire client (Segmented → `role=radio`,
//      pages/crm/ClientForm.jsx) accepte l'arabe ET la valeur PERSISTE
//      (relecture du client : l'option arabe revient `aria-checked="true"`) —
//      une préférence perdue au POST rendrait le PDF en français sans que rien
//      ne le signale ;
//   3. un devis se crée pour ce client via le générateur (combobox
//      `#gen-client`, pages/ventes/DevisGenerator.jsx), SANS lead : la langue
//      du document vient donc bien du client, pas du chrome ;
//   4. la génération du PDF premium ABOUTIT pour un client arabe — la ligne du
//      devis finit par exposer l'action « Télécharger », qui n'existe que
//      lorsque `devis.fichier_pdf` est présent côté serveur. Si le chemin de
//      rendu arabe (NTI18N5, `apps/ventes/utils/libelles_ar.py` + moteur
//      `/proposal`) échouait, aucun fichier ne serait produit et cette étape
//      tomberait.
//
// CE QUE CE SPEC N'ASSERTE PAS, ET POURQUOI — le critère de la tâche demandait
// aussi de vérifier, PAR EXTRACTION DE TEXTE DU PDF, que les libellés
// structurels sont en arabe (et donc de rougir si l'un retombe en français). La
// tâche supposait cette extraction « déjà utilisée ailleurs dans la suite e2e » :
// VÉRIFICATION FAITE, elle ne l'est pas — aucun spec de `frontend/e2e/` n'extrait
// de texte d'un PDF (le seul usage de pdf.js dans l'app est un rendu sur
// `<canvas>`, sans couche texte lisible depuis Playwright). Improviser ici un
// extracteur jamais éprouvé dans cette suite ajouterait un spec instable sur un
// chemin CI requis. La moitié manquante est donc NOMMÉE : un helper
// d'extraction de texte PDF dans `frontend/e2e/helpers.js` (`pdfjs-dist` est
// déjà une dépendance de `frontend/package.json`), puis l'assertion « libellé
// structurel en arabe, jamais un repli français » à brancher sur l'étape 4.
//
// EXÉCUTION EN CI — À SAVOIR. Le job `e2e-shard` ne lance PAS tout le dossier :
// il énumère explicitement 5 specs (`fumee-ecrans-1/2/3`, `devis`, `health` —
// voir `.github/workflows/ci.yml`), choix de BUDGET assumé puisque ce job fixe
// le plancher du gate. Ce spec ne tourne donc pas encore en CI ; l'y ajouter est
// une décision de budget CI (le parcours complet écrit ici coûte plusieurs
// dizaines de secondes à cause de la génération du PDF premium), pas une
// omission. En local : `npx playwright test i18n-quote-journey.spec.js`.
import { expect, test } from '@playwright/test'

import { uniq } from './helpers'

// Libellés de l'option « arabe » : « Arabe » quand l'interface est en français,
// « العربية » après la bascule (catalogues i18n, clé `client.langue_document.ar`).
// On accepte les deux pour ne pas coupler ce spec à l'ordre des étapes.
const OPTION_ARABE = /^(Arabe|العربية)$/

test('NTI18N47: interface en arabe, client arabe, devis multilingue généré', async ({ page }) => {
  // ── 1. Bascule de l'interface en arabe (NTI18N8) ─────────────────────────
  await page.goto('/crm')
  await page.getByTestId('lang-switcher').click()
  await page.getByTestId('lang-option-ar').click()

  const html = page.locator('html')
  await expect(html).toHaveAttribute('dir', 'rtl', { timeout: 10_000 })
  await expect(html).toHaveAttribute('lang', 'ar')

  // ── 2. Client dont les DOCUMENTS sont en arabe ───────────────────────────
  // La langue du document est INDÉPENDANTE de la langue d'interface (NTI18N4) :
  // on la pose explicitement sur le client.
  const nomClient = uniq('I18N47')

  await page.locator('.lp-header-actions')
    .getByRole('button', { name: /Nouveau client/ }).click()
  const formClient = page.getByRole('dialog')
  await expect(formClient).toBeVisible()
  await formClient.locator('#cf-nom').fill(nomClient)
  await formClient.getByRole('radio', { name: OPTION_ARABE }).click()
  await formClient.getByRole('button', { name: /Créer le client/ }).click()
  await expect(formClient).toBeHidden({ timeout: 20_000 })

  // Relecture : le kebab PERSISTANT de la ligne (DataTable `RowActions`,
  // libellé « Plus d'actions sur la ligne ») plutôt que l'action rapide, qui
  // n'apparaît qu'au survol.
  const ligneClient = page.locator('tr').filter({ hasText: nomClient }).first()
  await expect(ligneClient).toBeVisible({ timeout: 20_000 })
  await ligneClient.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await page.getByRole('menuitem', { name: /Éditer/ }).click()

  const formRelu = page.getByRole('dialog')
  await expect(formRelu).toBeVisible({ timeout: 20_000 })
  await expect(formRelu.getByRole('radio', { name: OPTION_ARABE }))
    .toHaveAttribute('aria-checked', 'true')
  await formRelu.getByRole('button', { name: /Annuler/ }).click()
  await expect(formRelu).toBeHidden()

  // ── 3. Devis pour CE client, sans lead ───────────────────────────────────
  await page.goto('/ventes/devis/nouveau')
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  // La composition par défaut du simulateur n'est posée qu'une fois le stock
  // chargé : attendre cette condition EXPLICITE (jamais une pause fixe) avant
  // d'interagir — même précaution que mobile.spec.js.
  await expect(page.locator('table.lines-table tbody tr').first())
    .toBeVisible({ timeout: 45_000 })

  await page.locator('#gen-client').click()
  // Champ de recherche du Combobox ouvert (ui/Combobox.jsx, `role=searchbox`).
  await page.locator('[role="searchbox"]').last().fill(nomClient)
  await page.getByRole('option', { name: nomClient }).first().click()

  await page.getByRole('button', { name: /Créer le devis/ }).click()
  // Écran de succès du générateur — texte stable, jamais un libellé de bouton
  // (les actions proposées y évoluent).
  await expect(page.getByText('Devis enregistré')).toBeVisible({ timeout: 45_000 })

  // ── 4. Le PDF premium se génère pour un client arabe ─────────────────────
  await page.goto('/ventes/devis')
  const ligneDevis = page.locator('tr[id^="devis-row-"]')
    .filter({ hasText: nomClient })
    .first()
  await expect(ligneDevis).toBeVisible({ timeout: 30_000 })

  await ligneDevis.getByRole('button', { name: /^PDF$/ }).click()
  const dialogPdf = page.getByRole('dialog')
  await expect(dialogPdf).toBeVisible()
  await dialogPdf.getByRole('button', { name: /^Générer$/ }).click()

  // « Télécharger » n'apparaît dans le menu « Plus d'actions » de la ligne que
  // lorsque `devis.fichier_pdf` existe : son apparition PROUVE que le moteur a
  // rendu le document de ce client arabe sans échouer. La génération premium
  // prend plusieurs dizaines de secondes (cf. `generateAutoDevis`, 45 s), d'où
  // la relance du menu par `toPass` au lieu d'un unique clic.
  await expect(async () => {
    await ligneDevis.getByRole('button', { name: /Plus d'actions/ }).click()
    await expect(page.getByRole('menuitem', { name: /Télécharger/ }).first())
      .toBeVisible({ timeout: 5_000 })
  }).toPass({ timeout: 120_000 })
})
