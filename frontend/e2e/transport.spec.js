// NTLOG48 — E2E : parcours ordre de transport complet.
// ----------------------------------------------------------------------------
// Couvre, avec l'app RÉELLE (pattern `installations.spec.js`/`devis.spec.js`) :
//  1. création d'un ordre via le wizard 3 étapes (NTLOG32) ;
//  2. affectation affrètement via le comparateur de transporteurs (NTLOG7),
//     intégré à l'étape 2 du wizard ;
//  3. progression des étapes (l'étape « enlèvement » passe « fait ») ;
//  4. tentative de clôture de la livraison SANS POD — doit échouer (NTLOG9,
//     le garde-fou serveur `EtapeTransportViewSet.livrer`) ;
//  5. upload d'une pièce jointe (photo/signature) sur l'étape livraison ;
//  6. clôture réussie (le kanban `/transport/ordres` bascule la carte en
//     colonne « Livré », NTLOG25) ;
//  7. vérification de la ligne d'historique (NTLOG8, chatter générique) sur
//     l'écran détail.
//
// Le wizard (`CreerOrdreTransportWizard.jsx`) n'accepte PAS de création
// imbriquée lignes/étapes (serializer read-only) — il émet donc plusieurs
// appels réseau (ordre → lignes → étapes), jamais un seul POST atomique côté
// serveur ; seul le POST de l'ordre est intercepté ici, pour récupérer son id.
//
// Aucune UI n'existe pour attacher une pièce jointe DIRECTEMENT à une
// `EtapeTransport` (seule `ReserveEtLitigeWizard` monte `AttachmentsPanel`,
// ciblant `transport.reservereception`) — l'upload POD (étape 5) et la
// progression de l'étape « enlèvement » (étape 3) passent donc par
// `page.request` sur les mêmes endpoints REST que l'app utilise en interne
// (même patron que `comptes-justes.spec.js`), cookie d'auth déjà posé par le
// projet `setup`. La véritable ASSERTION de non-régression (garde-fou POD)
// reste intégralement pilotée par l'UI : clic réel sur « Marquer livré »,
// deux fois, avant/après l'upload.
import { test, expect } from '@playwright/test'
import { uniq } from './helpers'

const POD_BYTES = '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'

test('E-TRANSPORT: wizard → affrètement → étapes → garde POD → livraison → historique', async ({ page }) => {
  const destinataire = uniq('Destinataire E2E')
  const transporteurNom = uniq('Transporteur E2E')

  // Pré-requis : au moins un transporteur actif pour que le comparateur
  // (étape 2 du wizard) ait une carte à afficher — `seed_demo` n'en pose
  // aucun (`installations.Transporteur`).
  const transporteurRes = await page.request.post(
    '/api/django/installations/transporteurs/',
    { data: { nom: transporteurNom, tarif_base: '350.00' } },
  )
  expect(transporteurRes.ok()).toBeTruthy()

  // ── 1. Wizard « Créer un ordre de transport » ─────────────────────────
  await page.goto('/transport/ordres/nouveau')
  await expect(page.getByRole('heading', { name: 'Créer un ordre de transport' })).toBeVisible()

  // Étape 1 — marchandises.
  await page.getByPlaceholder('Désignation').fill('Palette matériel solaire')
  await page.getByPlaceholder('Quantité').fill('2')
  await page.getByPlaceholder('Poids (kg)').fill('120')
  await page.getByRole('button', { name: 'Suivant' }).click()

  // Étape 2 — mode transport (affrètement par défaut) + comparateur NTLOG7 :
  // sélectionner le transporteur seedé ci-dessus.
  await expect(page.getByText('Comparateur de transporteurs')).toBeVisible()
  await page.getByRole('button', { name: new RegExp(transporteurNom) }).click()
  await page.getByRole('button', { name: 'Suivant' }).click()

  // Étape 3 — destinataire + dates.
  await page.locator('#wiz-destinataire').fill(destinataire)
  await page.locator('#wiz-destinataire-adresse').fill('12 Zone Industrielle, Casablanca')

  const [ordreResp] = await Promise.all([
    page.waitForResponse((r) => (
      r.url().includes('/api/django/transport/ordres-transport/')
      && r.request().method() === 'POST'
    )),
    page.getByRole('button', { name: "Créer l'ordre" }).click(),
  ])
  expect(ordreResp.ok()).toBeTruthy()
  const ordre = await ordreResp.json()
  expect(ordre.installations_transporteur_id).toBeTruthy()

  // Le wizard redirige vers la liste une fois l'ordre + ses lignes/étapes créés.
  await expect(page).toHaveURL(/\/transport\/ordres$/)

  // ── 2/3. Progression des étapes — l'« enlèvement » passe « fait » ─────
  const etapesRes = await page.request.get(
    `/api/django/transport/ordres-transport/${ordre.id}/etapes/`,
  )
  expect(etapesRes.ok()).toBeTruthy()
  const etapes = await etapesRes.json()
  const enlevement = etapes.find((e) => e.type_etape === 'enlevement')
  const livraison = etapes.find((e) => e.type_etape === 'livraison')
  expect(enlevement).toBeTruthy()
  expect(livraison).toBeTruthy()

  const patchEnlevement = await page.request.patch(
    `/api/django/transport/etapes-transport/${enlevement.id}/`,
    { data: { statut_etape: 'fait' } },
  )
  expect(patchEnlevement.ok()).toBeTruthy()

  // Rafraîchit la liste (créée/avancée hors-UI) puis bascule en vue kanban
  // (NTLOG25) — seule vue portant l'action réelle « Marquer livré ».
  await page.reload()
  await page.getByRole('radio', { name: 'Kanban' }).click()

  const carte = page.locator('.rounded-lg.border.bg-card', { hasText: ordre.numero })
  await expect(carte).toBeVisible()

  // ── 4. Tentative de clôture SANS POD — doit échouer (NTLOG9) ──────────
  await carte.getByRole('button', { name: 'Marquer livré' }).click()
  await expect(page.getByText('Photo ou signature requise avant de clôturer la livraison.')).toBeVisible()
  // Garde-fou de non-régression : la carte reste HORS de la colonne « Livré ».
  await expect(
    page.locator('section', { hasText: 'Livré' }).locator('.rounded-lg.border.bg-card', { hasText: ordre.numero }),
  ).toHaveCount(0)
  await expect(carte.getByRole('button', { name: 'Marquer livré' })).toBeVisible()

  // ── 5. Upload de la pièce jointe POD sur l'étape livraison ────────────
  const uploadRes = await page.request.post('/api/django/records/attachments/', {
    multipart: {
      model: 'transport.etapetransport',
      id: String(livraison.id),
      file: {
        name: `pod-${Date.now()}.pdf`,
        mimeType: 'application/pdf',
        buffer: Buffer.from(POD_BYTES),
      },
    },
  })
  expect(uploadRes.ok()).toBeTruthy()

  // ── 6. Clôture réussie ─────────────────────────────────────────────────
  await carte.getByRole('button', { name: 'Marquer livré' }).click()
  await expect(page.getByText('Ordre livré.')).toBeVisible()
  await expect(
    page.locator('section', { hasText: 'Livré' }).locator('.rounded-lg.border.bg-card', { hasText: ordre.numero }),
  ).toBeVisible()

  // ── 7. Historique (NTLOG8) sur l'écran détail ──────────────────────────
  await page.getByRole('radio', { name: 'Liste' }).click()
  await page.locator('[data-dt-table] tr', { hasText: destinataire }).click()
  await expect(page.getByRole('tab', { name: 'Historique' })).toBeVisible()
  const historique = page.locator('.chatter-timeline')
  await expect(historique).toBeVisible()
  await expect(historique).toContainText('→ livre')
  await expect(historique).toContainText('Étape 2')
})
