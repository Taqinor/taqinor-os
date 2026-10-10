// AMET90 — spec d'acceptation EXEMPLE (groupe ADEP) : étapes P5 d'ADEP99 +
// P4.2 d'ACHT69, jouées sur la pile locale (`scripts/acceptation.ps1 ADEP`).
// Format : `_format.md`. Les P1-P4 d'ADEP99 (sondes, builds, gardes) sont
// jouées par l'orchestrateur hors navigateur et FUSIONNÉES dans le même
// enregistrement (`_enregistrement.js --etapes-supplementaires`).
import { expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { aujourdHui } from './_enregistrement.js'
import { uniq } from '../helpers.js'

const etape = groupe('ADEP', ['ADEP16', 'ADEP17', 'ADEP18', 'ADEP19', 'ADEP33', 'ACHT69', 'ADEP99'])
const API = '/api/django/installations'
const RESEAU = /\/api\/django\//
const SYNC = /\/api\/django\/installations\/sync\/$/

// Données PROPRES à l'étape (patron installations.spec.js), nettoyées à la fin :
// une intervention du JOUR assignée à l'utilisateur, pour qu'elle figure dans
// « Ma journée » (/ma-journee, l'écran terrain : ses panneaux restent montés hors
// ligne, la tournée est servie depuis le cache de lecture).
async function avecIntervention(page, corps) {
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
  // s'ouvre au chargement sur l'onglet Réserves (restauration VX105 de Ma journée).
  await page.context().addInitScript((ident) => {
    try {
      localStorage.setItem('taqinor.onboardingTerrain.anonyme', '1')
      sessionStorage.setItem('mj.activeId', String(ident))
      sessionStorage.setItem('mj.tab', 'reserves')
    } catch { /* stockage indisponible */ }
  }, id)
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
