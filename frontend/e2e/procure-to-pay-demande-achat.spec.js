// NTP2P42 — Demande d'achat (depuis le catalogue) → approbation → BCF.
//
// Parcours : le demandeur crée une DemandeAchat depuis le catalogue interne
// (NTP2P3, `CatalogueAchatPicker`) → la soumission déclenche l'étape
// d'approbation (NTP2P2) → l'approbateur valide → conversion en BCF
// brouillon (`generer-bcf`, YPROC5) avec les MÊMES lignes/quantités.
//
// L'écran ne porte encore AUCUN bouton pour `generer-bcf` (aucune UI câblée
// à ce jour pour cette action) : cette étape passe donc par l'API REST
// directement, comme la vérification finale du BCF (même patron que
// `procure-to-pay-rfq.spec.js`, qui vérifie le BCF adjugé par requête API).
//
// L'approbation, elle, tente d'abord le chemin UI (bouton « Approuver »,
// décision directe) puis se replie sur la décision étape par étape
// (`approuver-etape`) si CET environnement a une `RegleApprobationAchat`
// active couvrant le montant de la demande (NTP2P2, config-dépendant selon
// les données de démo) — le spec ne suppose donc PAS qu'un plan
// d'approbation est ou n'est pas configuré ici.
import { test, expect } from '@playwright/test'
import { uniq } from './helpers'

test('NTP2P42: demande d\'achat (catalogue) → approbation → BCF', async ({ page }) => {
  const objet = uniq('E2E Demande Achat')

  await page.goto('/chantiers/demandes-achat')
  await expect(page.getByRole('heading', { name: "Demandes d'achat" })).toBeVisible()

  // ── 1) Créer depuis le catalogue interne (NTP2P3) + soumettre ───────────
  await page.getByRole('button', { name: 'Nouvelle demande' }).click()
  await expect(page.getByRole('heading', { name: "Nouvelle demande d'achat" })).toBeVisible()
  await page.locator('#da-objet').fill(objet)

  await page.locator('[data-testid="catalogue-achat-trigger"]').first().click()
  const premiereOption = page.getByRole('option').first()
  await expect(premiereOption).toBeVisible({ timeout: 10_000 })
  await premiereOption.click()

  await page.getByLabel('Quantité').first().fill('3')
  await page.getByRole('button', { name: 'Créer et soumettre' }).click()
  await expect(page.getByRole('heading', { name: "Nouvelle demande d'achat" })).toHaveCount(0)

  // ── 2) Retrouver la demande dans la liste, statut « Soumise » ────────────
  const recherche = page.getByPlaceholder('Rechercher (référence, objet)…')
  await recherche.fill(objet)
  const ligne = page.getByRole('row', { name: new RegExp(objet) })
  await expect(ligne).toBeVisible()
  await ligne.click()
  // Scopé au dialogue de détail (d'AUTRES lignes de la liste, en arrière-plan,
  // peuvent aussi porter le statut « Soumise » — strict mode Playwright).
  const dialogue = page.getByRole('dialog')
  await expect(dialogue.getByText('Soumise', { exact: true })).toBeVisible()

  // Lignes attendues (source de vérité pour le contrôle final quantité par
  // quantité, ligne par ligne).
  const listeDemandesRes = await page.request.get(
    '/api/django/installations/demandes-achat/?page_size=200')
  const listeDemandesBody = await listeDemandesRes.json()
  const demandes = listeDemandesBody.results ?? listeDemandesBody
  const demande = demandes.find((d) => d.objet === objet)
  expect(demande, 'la demande créée doit être retrouvable par API').toBeTruthy()
  const lignesAttendues = demande.lignes.map((l) => ({
    produit: l.produit, quantite: Number(l.quantite),
  }))
  expect(lignesAttendues.length).toBeGreaterThan(0)

  // ── 3) Approuver — chemin direct via l'UI, repli étape par étape si un
  //      plan d'approbation NTP2P2 couvre ce montant sur cet environnement ─
  // Attente sur la VRAIE réponse réseau du clic (jamais un waitForTimeout) :
  // le bouton « Approuver » est toujours rendu quand isManager, que la
  // décision directe soit acceptée (200) ou refusée (400, plan actif).
  const [approuverResp] = await Promise.all([
    page.waitForResponse((r) => (
      r.url().includes('/demandes-achat/') && r.url().includes('/approuver/')
      && r.request().method() === 'POST')),
    dialogue.getByRole('button', { name: 'Approuver' }).click(),
  ])
  let etat = approuverResp.ok()
    ? await approuverResp.json()
    : await (await page.request.get(
        `/api/django/installations/demandes-achat/${demande.id}/`)).json()
  if (etat.statut !== 'approuvee') {
    // Plan d'approbation NTP2P2 actif sur cet environnement : décide chaque
    // étape séquentielle (l'endpoint résout lui-même « la prochaine en
    // attente » sans corps requis) jusqu'à ce que la demande soit approuvée.
    for (let i = 0; i < 10 && etat.statut !== 'approuvee'; i += 1) {
      const etapeRes = await page.request.post(
        `/api/django/installations/demandes-achat/${demande.id}/approuver-etape/`)
      if (!etapeRes.ok()) break
      etat = await (await page.request.get(
        `/api/django/installations/demandes-achat/${demande.id}/`)).json()
    }
  }
  expect(etat.statut, 'la demande doit être APPROUVÉE avant la conversion BCF').toBe('approuvee')

  // ── 4) Conversion en BCF (YPROC5) — aucun bouton UI câblé à ce jour,
  //      appel direct à l'action serveur (même patron que la RFQ ci-dessus)
  const fournisseursRes = await page.request.get(
    '/api/django/stock/fournisseurs/?page_size=1')
  const fournisseursBody = await fournisseursRes.json()
  const fournisseurs = fournisseursBody.results ?? fournisseursBody
  test.skip(
    fournisseurs.length === 0,
    'aucun fournisseur au catalogue de cet environnement — conversion BCF non rejouable')
  const fournisseurId = fournisseurs[0].id

  const genererRes = await page.request.post(
    `/api/django/installations/demandes-achat/${demande.id}/generer-bcf/`,
    { data: { fournisseur: fournisseurId } })
  expect(genererRes.ok(), await genererRes.text()).toBeTruthy()
  const demandeCommandee = await genererRes.json()
  expect(demandeCommandee.statut).toBe('commandee')
  expect(demandeCommandee.bon_commande).toBeTruthy()

  // ── 5) Le BCF porte EXACTEMENT les mêmes lignes/quantités que la demande ─
  const bcfRes = await page.request.get(
    `/api/django/stock/bons-commande-fournisseur/${demandeCommandee.bon_commande}/`)
  expect(bcfRes.ok()).toBeTruthy()
  const bcf = await bcfRes.json()
  expect(bcf.lignes.length).toBe(lignesAttendues.length)
  for (const attendue of lignesAttendues) {
    const trouvee = bcf.lignes.find(
      (l) => String(l.produit) === String(attendue.produit))
    expect(trouvee, `ligne produit ${attendue.produit} absente du BCF`).toBeTruthy()
    expect(Number(trouvee.quantite)).toBe(attendue.quantite)
  }
})
