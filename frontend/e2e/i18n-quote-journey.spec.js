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
//   4. la génération du PDF premium ABOUTIT pour un client arabe — l'écran
//      lance `generer-pdf` (202) et le moteur rend le document par le chemin
//      canonique `/proposal` (200, un vrai PDF). Si le chemin de rendu arabe
//      (NTI18N5, `apps/ventes/utils/libelles_ar.py` + moteur `/proposal`)
//      échouait, cette étape tomberait (CAD177 : plus d'attente de
//      « Télécharger », qui exige un worker Celery absent du job e2e-full).
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

import { API_DJANGO, lireJson, listeDe, uniq } from './helpers'

// Libellés de l'option « arabe » : « Arabe » quand l'interface est en français,
// « العربية » après la bascule (catalogues i18n, clé `client.langue_document.ar`).
// On accepte les deux pour ne pas coupler ce spec à l'ordre des étapes.
const OPTION_ARABE = /^(Arabe|العربية)$/

// CAD177 — la bascule de langue est PERSISTÉE côté serveur sur le compte
// (`CustomUser.langue_interface`, NTI18N3 — `PATCH /auth/me/langue/`). Or ce
// compte, `demo_admin`, est celui de TOUTE la suite (storageState partagé) :
// sans remise à `fr`, chaque spec suivant tournait en arabe/RTL (run
// 36990128960 : leads-board, leads-density, leads, parcours-budget,
// procure-to-pay, reliability, ux-* — 15 échecs en cascade). On restaure la
// langue d'origine dans un `afterEach`, qui tourne MÊME si le test échoue.
test.afterEach(async ({ page }) => {
  const res = await page.request.patch('/api/django/auth/me/langue/', {
    data: { langue_interface: 'fr' },
  })
  expect(res.ok(), `remise de la langue d'interface à fr (${res.status()})`).toBeTruthy()
})

test('NTI18N47: interface en arabe, client arabe, devis multilingue généré', async ({ page }) => {
  // Générateur (≤45 s de chargement du stock) + rendu premium synchrone.
  test.setTimeout(180_000)
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

  // CAD177 — DEUX boutons « Créer le devis » existent en desktop depuis le
  // rail récapitulatif VX16 (be7caa72, `form="gen-form"`, lg+) : on vise
  // celui du formulaire lui-même, présent à toutes les largeurs.
  // CAD177 — la composition par défaut porte des panneaux/onduleurs à 0 : sans
  // lead il n'y a AUCUN auto-dimensionnement, et la garde QX20 (« un devis
  // solaire doit contenir ≥ 1 panneau ET ≥ 1 onduleur ») bloque l'envoi AVANT
  // tout appel serveur (aucun POST, donc jamais d'écran de succès — rouge du
  // nocturne 37446060068). Ce parcours teste la LANGUE du document, pas le
  // dimensionnement : on prend l'échappatoire documentée de la garde.
  await page.getByRole('switch', { name: /Composition libre/ }).check()
  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname), { timeout: 30_000 })
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const reponseCreation = await creation
  expect(reponseCreation.status(), `création du devis : ${await reponseCreation.text()}`)
    .toBeLessThan(300)
  // Écran de succès du générateur — texte stable, jamais un libellé de bouton
  // (les actions proposées y évoluent).
  await expect(page.getByText('Devis enregistré')).toBeVisible({ timeout: 45_000 })

  // CAD177 — la composition libre ne porte QUE des lignes sans matériel
  // (accessoires, pose, transport, suivi) : le moteur REFUSE de rendre un devis
  // dont aucune option ne contient d'onduleur (500 « règle de sécurité »,
  // nocturne 37585800165). Ce parcours teste la LANGUE du document, pas le
  // dimensionnement : on y ajoute par l'API un onduleur et des panneaux du
  // catalogue (lignes ordinaires, prix catalogue), pour que le moteur rende.
  const devisCree = await reponseCreation.json()
  for (const [recherche, motCle, quantite] of [
    // Un onduleur RÉSEAU : le classifieur d'options du moteur (builder.py,
    // « Sans batterie » = onduleur réseau/injection) ne range pas un
    // micro-onduleur — la 1re passe (« Micro-onduleur 800W ») gardait le 500.
    ['Onduleur réseau', /onduleur r[ée]seau/i, 1], ['Panneau', /panneau/i, 10],
  ]) {
    const produits = listeDe(await lireJson(await page.request.get(
      `${API_DJANGO}/stock/produits/?search=${encodeURIComponent(recherche)}`), `catalogue ${recherche}`))
    const produit = produits.find((p) => motCle.test(p.nom) && Number(p.prix_vente) > 0)
    expect(produit, `un produit « ${recherche} » prix renseigné au catalogue de démonstration`).toBeTruthy()
    await lireJson(await page.request.post(`${API_DJANGO}/ventes/devis-lignes/`, {
      data: {
        devis: devisCree.id, produit: produit.id, designation: produit.nom,
        quantite: String(quantite), prix_unitaire: String(produit.prix_vente),
      },
    }), `ligne ${recherche}`)
  }

  // ── 4. Le PDF premium se génère pour un client arabe ─────────────────────
  await page.goto('/ventes/devis')
  const ligneDevis = page.locator('tr[id^="devis-row-"]')
    .filter({ hasText: nomClient })
    .first()
  await expect(ligneDevis).toBeVisible({ timeout: 30_000 })

  // CAD177 — le bouton « Générer » du dialogue lance la génération ASYNCHRONE
  // (`generer-pdf` → tâche Celery, 202). Le job e2e-full ne démarre AUCUN
  // worker Celery (release-verify.yml : gunicorn seul) : la tâche reste
  // « en_cours » pour toujours et « Télécharger » n'apparaît jamais (run
  // nocturne 37573380397 : 50 s d'`etat-pdf` en_cours, puis délai du test).
  // On prouve donc (a) que l'écran déclenche bien la génération pour ce devis
  // (202), puis (b) que LE MOTEUR rend le document de ce client arabe par le
  // chemin canonique synchrone `/proposal` (règle #4 — même moteur que la
  // tâche, `langue_sortie` résolue depuis `Client.langue_document`, NTI18N4).
  const idLigne = await ligneDevis.getAttribute('id')
  const devisId = Number(String(idLigne).replace('devis-row-', ''))
  expect(devisId, `id du devis lu sur la ligne (${idLigne})`).toBeGreaterThan(0)

  await ligneDevis.getByRole('button', { name: /^PDF$/ }).click()
  const dialogPdf = page.getByRole('dialog')
  await expect(dialogPdf).toBeVisible()
  const lancement = page.waitForResponse((r) => r.request().method() === 'POST'
    && new URL(r.url()).pathname.endsWith(`/ventes/devis/${devisId}/generer-pdf/`),
  { timeout: 30_000 })
  await dialogPdf.getByRole('button', { name: /^Générer$/ }).click()
  const reponseLancement = await lancement
  expect(reponseLancement.status(), `generer-pdf : ${await reponseLancement.text()}`)
    .toBeLessThan(300)

  const pdf = await page.request.get(
    `/api/django/ventes/devis/${devisId}/proposal/?pdf_mode=full`, { timeout: 90_000 })
  expect(pdf.status(), '/proposal du devis du client arabe').toBe(200)
  expect(pdf.headers()['content-type'] || '').toContain('application/pdf')
  const octets = await pdf.body()
  expect(octets.subarray(0, 5).toString('latin1'), 'en-tête PDF').toBe('%PDF-')
})
