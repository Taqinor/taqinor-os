// AMET90 — spec d'acceptation EXEMPLE (groupe ADEP) : étapes P5 d'ADEP99 +
// P4.2 d'ACHT69, jouées sur la pile locale (`scripts/acceptation.ps1 ADEP`).
// Format : `_format.md`. Les P1-P4 d'ADEP99 (sondes, builds, gardes) sont
// jouées par l'orchestrateur hors navigateur et FUSIONNÉES dans le même
// enregistrement (`_enregistrement.js --etapes-supplementaires`).
import { readFileSync } from 'node:fs'
import { inflateSync } from 'node:zlib'
import { expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { aujourdHui } from './_enregistrement.js'
import { uniq, lireJson, listeDe, setLeadsView, telephoneMobileUnique } from '../helpers.js'
import {
  PIPELINE_STAGES, STAGE_LABELS, NEW_STAGE, CONTACTED_STAGE, QUOTE_SENT_STAGE,
  FOLLOW_UP_STAGE, SIGNED_STAGE, COLD_STAGE,
} from '../../src/features/crm/stages.js'

const etape = groupe('ADEP', [
  'ADEP16', 'ADEP17', 'ADEP18', 'ADEP19', 'ADEP33', 'ADEP40', 'ADEP44', 'ADEP45', 'ADEP46',
  'ACHT69', 'ADEP99',
])
const API = '/api/django/installations'
const RESEAU = /\/api\/django\//
const SYNC = /\/api\/django\/installations\/sync\/$/

// Données PROPRES à l'étape (patron installations.spec.js), nettoyées à la fin :
// une intervention du JOUR assignée à l'utilisateur, pour qu'elle figure dans
// « Ma journée » (/ma-journee, l'écran terrain : ses panneaux restent montés hors
// ligne, la tournée est servie depuis le cache de lecture).
async function avecIntervention(page, corps, onglet = 'reserves') {
  const { request } = page
  const moi = (await (await request.get('/api/django/auth/me/')).json()).id
  const ch = await request.post(`${API}/chantiers/`, { data: {} })
  expect(ch.ok(), `chantier créé (${ch.status()})`).toBeTruthy()
  const chantier = (await ch.json()).id
  const iv = await request.post(`${API}/interventions/`, { data: {
    installation: chantier, type_intervention: 'controle', technicien: moi, date_prevue: aujourdHui(),
  } })
  expect(iv.ok(), `intervention créée (${iv.status()})`).toBeTruthy()
  const id = (await iv.json()).id
  // Technicien habitué (aide terrain déjà vue) ; la fiche de CETTE intervention
  // s'ouvre au chargement sur l'onglet demandé (restauration VX105 de Ma journée).
  await page.context().addInitScript(([ident, tab]) => {
    try {
      localStorage.setItem('taqinor.onboardingTerrain.anonyme', '1')
      sessionStorage.setItem('mj.activeId', String(ident))
      sessionStorage.setItem('mj.tab', tab)
    } catch { /* stockage indisponible */ }
  }, [id, onglet])
  try {
    await corps(id)
  } finally {
    await request.delete(`${API}/interventions/${id}/`).catch(() => null)
    await request.delete(`${API}/chantiers/${chantier}/`).catch(() => null)
  }
}

async function ouvrirReserves(page) {
  await page.goto('/ma-journee')
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByPlaceholder(/Réserve à reprendre/)).toBeVisible()
}

async function ajouterReserve(page, texte) {
  await page.getByPlaceholder(/Réserve à reprendre/).fill(texte)
  await page.getByRole('button', { name: 'Ajouter la réserve' }).click()
  await expect(page.getByText('Hors ligne — enregistré').first()).toBeVisible()
}

// Badge de synchro de l'en-tête (la fiche modale fermée d'abord).
async function ouvrirBadge(page) {
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByTestId('sync-status-badge').click()
}

// File terrain telle que persistée (IndexedDB `taqinor-field-outbox`, clé `queue`).
const fileLocale = (page) => page.evaluate(() => new Promise((ok) => {
  const req = indexedDB.open('taqinor-field-outbox', 1)
  req.onupgradeneeded = () => req.result.createObjectStore('ops')
  req.onsuccess = () => {
    const get = req.result.transaction('ops', 'readonly').objectStore('ops').get('queue')
    get.onsuccess = () => ok(Array.isArray(get.result) ? get.result : [])
    get.onerror = () => ok([])
  }
  req.onerror = () => ok([])
}))

async function reservesServeur(request, id) {
  const r = await request.get(`${API}/interventions/${id}/reserves/`)
  expect(r.ok(), `réserves lues (${r.status()})`).toBeTruthy()
  return (await r.json()).map((x) => x.description)
}

etape('P5.1', ['ADEP16', 'ADEP17', 'ADEP99'], async ({ page, context, suivi }) => {
  // Deux onglets hors ligne, une saisie dans chacun, retour du réseau : 2 effets, 0 perte.
  suivi.attendre(RESEAU, 'reseau')
  await avecIntervention(page, async (id) => {
    const b = suivi.surveiller(await context.newPage())
    for (const p of [page, b]) await ouvrirReserves(p)
    const [da, db] = [uniq('ADEP-P51-A'), uniq('ADEP-P51-B')]
    await context.setOffline(true)
    await ajouterReserve(page, da)
    await ajouterReserve(b, db)
    expect((await fileLocale(page)).map((op) => op.payload.description).sort()).toEqual([da, db].sort())
    await context.setOffline(false) // événement `online` : chaque onglet vide la file
    await expect.poll(() => fileLocale(page), { timeout: 30_000 }).toEqual([])
    expect((await reservesServeur(page.request, id)).sort()).toEqual([da, db].sort())
    for (const p of [page, b]) { // persistance : rechargé, la liste montre les deux
      await ouvrirReserves(p)
      for (const d of [da, db]) await expect(p.getByText(d)).toHaveCount(1)
    }
    expect(await fileLocale(b)).toEqual([])
    suivi.verifie(5)
  })
})

etape('P5.2', ['ADEP16', 'ADEP99'], async ({ page, suivi }) => {
  // L'appel en ligne APPLIQUE l'effet puis expire : la file rejoue la MÊME clé → 1 effet.
  await avecIntervention(page, async (id) => {
    await ouvrirReserves(page)
    const enLigne = new RegExp(`/installations/interventions/${id}/ajouter-reserve/$`)
    suivi.attendre(enLigne, 'reseau')
    let statutServeur = null
    await page.route(enLigne, async (route) => {
      statutServeur = (await route.fetch()).status()
      await route.abort('timedout')
    }, { times: 1 })
    const d = uniq('ADEP-P52')
    await ajouterReserve(page, d)
    expect([200, 201], 'effet appliqué par l’appel en ligne').toContain(statutServeur)
    const [op] = await fileLocale(page)
    expect(op?.op_type).toBe('intervention.reserve')
    await ouvrirBadge(page)
    const [rep] = await Promise.all([
      page.waitForResponse(SYNC),
      page.getByTestId('sync-status-flush').click(),
    ])
    const res = (await rep.json()).results.find((r) => r.client_op_id === op.client_op_id)
    expect(res?.status, 'même client_op_id rejoué').toBe('replayed')
    await expect.poll(() => fileLocale(page)).toEqual([])
    expect((await reservesServeur(page.request, id)).filter((x) => x === d)).toHaveLength(1)
    await ouvrirReserves(page)
    await expect(page.getByText(d)).toHaveCount(1)
    suivi.verifie(5)
  })
})

// Lot refusé par le point de synchro : chaque op marquée, visible, abandonnable.
async function loteRefuse({ page, context, suivi }, statut, detail) {
  suivi.attendre(RESEAU, 'reseau')
  suivi.attendre(SYNC, statut)
  await page.route(SYNC, (route) => route.fulfill({
    status: statut, contentType: 'application/json', body: JSON.stringify({ detail }),
  }))
  await avecIntervention(page, async (id) => {
    await ouvrirReserves(page)
    await context.setOffline(true)
    await ajouterReserve(page, uniq(`ADEP-${statut}-1`))
    await ajouterReserve(page, uniq(`ADEP-${statut}-2`))
    await context.setOffline(false) // `online` : le flush reçoit le refus
    await expect.poll(async () => (await fileLocale(page)).map((op) => op.serverError))
      .toEqual([detail, detail])
    await ouvrirBadge(page) // journal des refus : op_type — détail, rien en attente silencieuse
    await expect(page.getByTestId('sync-status-badge')).toHaveAttribute('data-sync-state', 'erreur')
    await expect(page.getByText(detail)).toHaveCount(2)
    await expect(page.getByText('intervention.reserve', { exact: true })).toHaveCount(2)
    await page.keyboard.press('Escape')
    await ouvrirReserves(page) // persistance : rechargé, toujours en échec
    await page.getByRole('tab', { name: 'Photos' }).click() // l'abandon vit dans l'indicateur terrain
    const indicateur = page.getByTestId('offline-sync-indicator').filter({ visible: true })
    await indicateur.getByRole('button', { name: /2 action\(s\) en échec/ }).click()
    await expect(indicateur.getByText(`intervention.reserve — ${detail}`)).toHaveCount(2)
    for (let i = 0; i < 2; i += 1) await indicateur.getByRole('button', { name: 'Abandonner' }).first().click()
    await expect.poll(() => fileLocale(page)).toEqual([])
    await expect(indicateur).toHaveCount(0)
    expect(await reservesServeur(page.request, id)).toEqual([])
  })
}

etape('P5.3', ['ADEP18', 'ACHT69', 'ADEP99'], (ctx) => loteRefuse(ctx, 403,
  "Vous n'avez pas la permission d'effectuer cette action."))

etape('P5.3-500', ['ACHT69', 'ADEP99'], (ctx) => loteRefuse(ctx, 500, 'Erreur interne du serveur.'))

etape('P5.4', ['ADEP19', 'ADEP33', 'ADEP99'], async ({ page, suivi }) => {
  // fetchMe échoue SANS 401/403 (réseau, puis 503) : écran « Hors ligne », jamais /login.
  const me = /\/api\/django\/auth\/me\/(\?.*)?$/
  for (const panne of ['reseau', 503]) {
    suivi.attendre(me, panne)
    await page.route(me, (r) => (panne === 'reseau' ? r.abort('connectionfailed') : r.fulfill({
      status: 503, contentType: 'application/json', body: '{"detail":"Service indisponible."}',
    })))
    await page.goto('/dashboard')
    for (let fois = 0; fois < 2; fois += 1) { // persistance : rechargé, même écran
      await expect(page.getByRole('heading', { name: 'Hors ligne' })).toBeVisible()
      await expect(page).toHaveURL(/\/dashboard$/)
      if (fois === 0) await page.reload()
    }
    await page.unroute(me)
    await page.getByRole('button', { name: 'Hors ligne — réessayer' }).click()
    await expect(page.getByRole('heading', { name: 'Hors ligne' })).toHaveCount(0)
    await expect(page).not.toHaveURL(/\/login/)
  }
})

// ── P1.13 — ADEP40 : le logo de l'écran Paramètres est DANS le rapport PDF ──
const PROFIL = '/api/django/parametres/'
const RAPPORT_PDF = '/api/django/reporting/reports/sales/?export=pdf'
// Logo de test : une image du dépôt (192 × 192 px), reconnue par sa taille
// dans le dictionnaire de l'image embarquée.
const LOGO = { name: 'logo-adep40.png', mimeType: 'image/png',
  buffer: readFileSync(new URL('../../public/pwa-192.png', import.meta.url)) }

// Texte d'un PDF : octets bruts + chaque flux FlateDecode décompressé (les
// dictionnaires d'objets peuvent vivre dans un flux d'objets compressé).
function textePdf(octets) {
  const brut = octets.toString('latin1')
  const parts = [brut]
  const re = /stream\r?\n/g
  for (let m = re.exec(brut); m; m = re.exec(brut)) {
    const debut = m.index + m[0].length
    const fin = brut.indexOf('endstream', debut)
    if (fin < 0) break
    try { parts.push(inflateSync(octets.subarray(debut, fin)).toString('latin1')) } catch { /* flux non compressé */ }
  }
  return parts.join('\n')
}

async function exporterRapport(request) {
  const r = await request.get(RAPPORT_PDF)
  expect(r.ok(), `export PDF du rapport (${r.status()})`).toBeTruthy()
  expect(r.headers()['content-type']).toContain('application/pdf')
  const pdf = textePdf(await r.body())
  return { image: /\/Subtype\s*\/Image/.test(pdf), largeur192: /\/Width\s+192\b/.test(pdf) }
}

etape('P1.13', ['ADEP40'], async ({ page }) => {
  const { request } = page
  // Logo d'avant lu D'ABORD (restauré à la fin) — si on ne peut pas le relire,
  // on s'arrête avant de toucher à quoi que ce soit.
  const avant = (await lireJson(await request.get(PROFIL), 'profil société')).logo_url
  let octetsAvant = null
  if (avant) {
    const r = await request.get(avant)
    expect(r.ok(), `logo existant relu pour restauration (${r.status()})`).toBeTruthy()
    octetsAvant = await r.body()
  }
  try {
    // Témoin : sans logo, le rapport ne porte AUCUNE image (le seul <img> du
    // gabarit `report_pdf` est le logo) — l'image d'après vient donc du logo.
    await lireJson(await request.delete(`${PROFIL}delete-logo/`), 'logo retiré (témoin)')
    expect((await exporterRapport(request)).image, 'témoin sans logo : aucune image').toBe(false)

    // Téléversement par le VRAI écran Paramètres › Société & identité.
    await page.goto('/parametres')
    const zone = page.getByText('Affiché en en-tête du PDF').locator('..')
    const [rep] = await Promise.all([
      page.waitForResponse((r) => /\/parametres\/upload-logo\/$/.test(r.url())),
      zone.locator('input[type="file"]').setInputFiles(LOGO),
    ])
    expect(rep.status(), 'logo téléversé').toBe(200)
    expect((await rep.json()).logo_url, 'profil : logo posé').toBeTruthy()

    // Le rapport exporté porte le logo (image 192 px embarquée) — donc
    // `_logo_data_uri` a relu le bucket d'upload : il ne renvoie None (et ne
    // journalise « Logo fetch failed ») que quand la lecture MinIO échoue.
    // CLAUSE PERSISTANCE : ré-exporté, toujours là.
    for (let fois = 0; fois < 2; fois += 1) {
      expect(await exporterRapport(request), `export n° ${fois + 1}`).toEqual({ image: true, largeur192: true })
    }
    // Profil relu : le logo téléversé y est toujours.
    expect((await lireJson(await request.get(PROFIL), 'profil relu')).logo_url).toBeTruthy()
  } finally {
    if (octetsAvant) {
      await request.post(`${PROFIL}upload-logo/`, { multipart: {
        file: { name: avant.split('?')[0].split('/').pop() || 'logo.png', mimeType: 'image/png', buffer: octetsAvant },
      } })
    } else {
      await request.delete(`${PROFIL}delete-logo/`).catch(() => null)
    }
  }
})

// ── P5.5 — ADEP44 + ADEP45 : ajout d'un n° de série, réponse en ligne coupée ──
async function seriesServeur(request, id) {
  const r = await request.get(`${API}/interventions/${id}/serials/`)
  expect(r.ok(), `séries lues (${r.status()})`).toBeTruthy()
  return (await r.json()).map((x) => x.designation)
}

async function ouvrirSeries(page) {
  await page.goto('/ma-journee')
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByPlaceholder('Composant (onduleur, panneau…)')).toBeVisible()
}

etape('P5.5', ['ADEP44', 'ADEP45'], async ({ page, suivi }) => {
  // L'appel en ligne `ajouter-serial` ATTEINT le serveur (effet appliqué), puis
  // sa réponse est coupée : la file rejoue la MÊME clé → `replayed`, 1 série.
  await avecIntervention(page, async (id) => {
    await ouvrirSeries(page)
    const enLigne = new RegExp(`/installations/interventions/${id}/ajouter-serial/$`)
    suivi.attendre(enLigne, 'reseau')
    let statutServeur = null
    let cleEnLigne = null
    await page.route(enLigne, async (route) => {
      cleEnLigne = /name="client_op_id"\r\n\r\n([^\r\n]+)/.exec(route.request().postData() || '')?.[1] ?? null
      statutServeur = (await route.fetch()).status()
      await route.abort('timedout')
    }, { times: 1 })
    const d = uniq('ADEP-P55')
    await page.getByPlaceholder('Composant (onduleur, panneau…)').fill(d)
    await page.getByPlaceholder('N° de série (optionnel)').fill(`SN-${d.replace(/\W+/g, '-')}`)
    await page.getByRole('button', { name: 'Ajouter le relevé' }).click()
    await expect(page.getByText('Hors ligne — enregistré').first()).toBeVisible()
    expect([200, 201], 'effet appliqué par l’appel en ligne').toContain(statutServeur)
    expect(cleEnLigne, 'clé d’idempotence envoyée par l’appel en ligne (ADEP45)').toBeTruthy()
    const [op] = await fileLocale(page)
    expect(op?.op_type).toBe('intervention.serial')
    expect(op.client_op_id, 'l’op filée porte la clé de l’appel en ligne').toBe(cleEnLigne)
    // L'effet est DÉJÀ en base avant la synchro : c'est le rejeu qui doit s'abstenir.
    expect((await seriesServeur(page.request, id)).filter((x) => x === d)).toHaveLength(1)
    await ouvrirBadge(page)
    const [rep] = await Promise.all([
      page.waitForResponse(SYNC),
      page.getByTestId('sync-status-flush').click(),
    ])
    const res = (await rep.json()).results.find((r) => r.client_op_id === cleEnLigne)
    expect(res?.status, 'même client_op_id rejoué (ADEP44)').toBe('replayed')
    await expect.poll(() => fileLocale(page)).toEqual([])
    expect((await seriesServeur(page.request, id)).filter((x) => x === d)).toHaveLength(1)
    await ouvrirSeries(page) // CLAUSE PERSISTANCE : rechargé, une seule série à l'écran
    await expect(page.getByText(d, { exact: true })).toHaveCount(1)
    suivi.verifie(5)
  }, 'serials')
})

// ── P5.6 — ADEP46 : la vue Kanban des leads, colonnes et probabilités inchangées ──
// Probabilités AFFICHÉES AVANT ADEP46, relevées dans
// `git show 3f57c26e0:frontend/src/pages/crm/leads/views/KanbanView.jsx`
// (l.61-68, `STAGE_PROBABILITY` ; 3f57c26e0 = parent du commit ADEP46 1754b429f),
// en pourcentage, comme le titre de la colonne les montre. Clés = constantes
// d'étape importées (règle CLAUDE.md #2), jamais des littéraux.
const PROBA_AVANT_ADEP46 = {
  [NEW_STAGE]: 10,
  [CONTACTED_STAGE]: 25,
  [QUOTE_SENT_STAGE]: 50,
  [FOLLOW_UP_STAGE]: 70,
  [SIGNED_STAGE]: 100,
  [COLD_STAGE]: 5,
}
const API_DJ = '/api/django'
const colonne = (page, cle) => page.getByRole('region', {
  name: new RegExp(`^Étape ${STAGE_LABELS[cle]} — \\d+ leads?$`),
})

async function verifierColonnes(page) {
  // Ordre et libellés des colonnes = PIPELINE_STAGES / STAGE_LABELS (miroir de STAGES.py).
  await expect(page.locator('section.kb-col .kb-col-title'))
    .toHaveText(PIPELINE_STAGES.map((cle) => STAGE_LABELS[cle]))
  for (const cle of PIPELINE_STAGES) {
    await expect(colonne(page, cle).locator('.kb-col-money')).toHaveAttribute('title',
      `Prévisionnel pondéré à ${PROBA_AVANT_ADEP46[cle]} % (probabilité de conversion à cette étape)`)
  }
}

etape('P5.6', ['ADEP46'], async ({ page }) => {
  const { request } = page
  const prefixe = uniq('ADEP-P56')
  const crees = { leads: [], devis: [] }
  try {
    // Une ligne de devis référence un produit : le premier produit prix
    // renseigné du catalogue de démonstration.
    const produit = listeDe(await lireJson(await request.get(`${API_DJ}/stock/produits/?page_size=50`),
      'catalogue')).find((p) => Number(p.prix_vente) > 0)
    expect(produit, 'un produit prix renseigné au catalogue de démonstration').toBeTruthy()
    // Un lead PROPRE par étape, chacun avec un devis chiffré : chaque colonne
    // affiche alors son « Prév. » et sa probabilité.
    for (const cle of PIPELINE_STAGES) {
      const lead = await lireJson(await request.post(`${API_DJ}/crm/leads/`, { data: {
        nom: `${prefixe} ${STAGE_LABELS[cle]}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), stage: cle,
      } }), `lead ${STAGE_LABELS[cle]}`)
      crees.leads.push(lead.id)
      const devis = await lireJson(await request.post(`${API_DJ}/ventes/devis/`, {
        data: { lead: lead.id, taux_tva: '20.00' } }), `devis ${STAGE_LABELS[cle]}`)
      crees.devis.push(devis.id)
      await lireJson(await request.post(`${API_DJ}/ventes/devis-lignes/`, { data: {
        devis: devis.id, produit: produit.id, designation: produit.nom, quantite: '1',
        prix_unitaire: String(produit.prix_vente),
      } }), `ligne ${STAGE_LABELS[cle]}`)
      const relu = await lireJson(await request.get(`${API_DJ}/crm/leads/${lead.id}/`), 'lead relu')
      expect(relu.stage, `lead resté en ${STAGE_LABELS[cle]}`).toBe(cle)
    }
    await page.goto('/crm/leads')
    await setLeadsView(page, 'kanban')
    await page.getByPlaceholder('Rechercher nom, téléphone, email…').fill(prefixe)
    for (const cle of PIPELINE_STAGES) {
      await expect(colonne(page, cle).getByText(`${prefixe} ${STAGE_LABELS[cle]}`)).toBeVisible()
    }
    await verifierColonnes(page)
    await page.reload() // CLAUSE PERSISTANCE : rechargée, mêmes colonnes, mêmes probabilités
    await setLeadsView(page, 'kanban')
    await verifierColonnes(page)
  } finally {
    for (const id of crees.devis) await request.delete(`${API_DJ}/ventes/devis/${id}/`).catch(() => null)
    for (const id of crees.leads) await request.delete(`${API_DJ}/crm/leads/${id}/`).catch(() => null)
  }
})
