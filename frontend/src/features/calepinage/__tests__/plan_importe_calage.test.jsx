import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CAL63 — LA TRANSFORMATION, PUIS L'ÉCRAN QUI S'EN SERT.
   ----------------------------------------------------------------------------
   La tâche exige un « test unitaire de la transformation » : la moitié haute
   de ce fichier appelle les fonctions PURES sans monter React. La moitié basse
   tient les deux promesses de l'écran : le calage est PERSISTÉ puis RELU, et
   l'échelle vient d'une DISTANCE SAISIE — sans elle, rien n'est enregistré et
   le refus se pose SOUS le champ fautif.
   ========================================================================== */

const layout = vi.fn()
const enregistrerLayout = vi.fn()
const importerPlan = vi.fn()
const envoyerFondPlan = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      enregistrerLayoutCalepinage: (...a) => enregistrerLayout(...a),
      importerPlan: (...a) => importerPlan(...a),
      envoyerFondPlan: (...a) => envoyerFondPlan(...a),
    },
  },
}))

const {
  default: PlanImporteCalage, echelleDepuisDeuxPoints,
} = await import('../PlanImporteCalage')
const { default: userEvent } = await import('@testing-library/user-event')
const { exempleContrat, reponseContrat } = await import('../../../test/fixtures/contractSamples')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

/* ── 1. LA TRANSFORMATION, PURE ────────────────────────────────────────── */

describe('CAL63 — l’échelle vient de la distance SAISIE, jamais d’une estimation', () => {
  it('deux points distants de 4 unités pour 10 m réels : 2,5 m par unité', () => {
    const mesure = echelleDepuisDeuxPoints([0, 0], [4, 0], 10)
    expect(mesure.echelle).toBeCloseTo(2.5, 10)
    expect(mesure.distancePlan).toBeCloseTo(4, 10)
    expect(mesure.source).toBe('saisie')
  })

  it('sans distance réelle saisie : AUCUNE échelle — jamais un repli sur 1', () => {
    expect(echelleDepuisDeuxPoints([0, 0], [4, 0], null)).toBeNull()
    expect(echelleDepuisDeuxPoints([0, 0], [4, 0], '')).toBeNull()
    expect(echelleDepuisDeuxPoints([0, 0], [4, 0], 0)).toBeNull()
    expect(echelleDepuisDeuxPoints([0, 0], [4, 0], -3)).toBeNull()
  })

  it('deux points confondus, ou un point manquant : aucune échelle', () => {
    expect(echelleDepuisDeuxPoints([2, 2], [2, 2], 10)).toBeNull()
    expect(echelleDepuisDeuxPoints(null, [4, 0], 10)).toBeNull()
    expect(echelleDepuisDeuxPoints([0, 0], undefined, 10)).toBeNull()
  })
})

/* ACAL70 — la rotation, l'échelle et la translation du contour sont désormais
   calculées par le SERVEUR (`importer-plan/`, `contour_lnglat`, un seul repère
   local) : les copies locales `appliquerCalage` / `calerContour` / `aimanter`
   (unités de plan comparées à des degrés — porte SIT-G2-05) n'existent plus. */

/* ── 2. L'ÉCRAN : le plan se pose comme pan, par le serveur ──────────── */

const contrat = (variante) => exempleContrat('calepinage', 'calepinage_import_plan', variante)
const reponse = (variante) => reponseContrat('calepinage', 'calepinage_import_plan', variante)
const PLAN = () => new File(['0\nSECTION\n'], 'plan-toiture.dxf', { type: 'application/dxf' })

const rendre = (props = {}) => render(
  <MemoryRouter><PlanImporteCalage calepinageId={7} {...props} /></MemoryRouter>,
)

/** Dépose le plan, choisit le calque d'enveloppe et obtient son contour. */
const proposerLeContour = async (utilisateur) => {
  await screen.findByTestId('cal-calage-sans-plan')
  await utilisateur.upload(screen.getByTestId('cal-calage-fichier'), PLAN())
  await utilisateur.click(screen.getByTestId('cal-calage-analyser'))
  await screen.findByTestId('cal-calage-analyse')
  await utilisateur.selectOptions(screen.getByTestId('cal-calage-calque'), contrat('exemple').calque)
  await utilisateur.click(screen.getByTestId('cal-calage-proposer'))
  await screen.findByTestId('cal-calage-plan')
}

describe('ACAL70 — « Poser comme pan du toit » (le serveur géoréférence, l’atelier pose)', () => {
  const builderApi = () => ({ ajouterPanDepuisContour: vi.fn(() => ({ ok: true, id: 'pan-3' })) })

  beforeEach(() => {
    layout.mockResolvedValue({ data: { roof_layout: {}, empreinte_document: 'E0' } })
    importerPlan
      .mockResolvedValueOnce(reponse('exemple_sans_calque'))
      .mockResolvedValueOnce(reponse('exemple'))
  })

  it('Poser comme pan → ajouterPanDepuisContour reçoit des [lng,lat] proches de l’épingle ; aucun POST layout/', async () => {
    const utilisateur = userEvent.setup()
    const atelier = builderApi()
    rendre({ builderApi: atelier })
    await proposerLeContour(utilisateur)

    importerPlan.mockResolvedValueOnce(reponse('exemple'))
    fireEvent.change(screen.getByLabelText(/Distance réelle/), { target: { value: '30' } })
    fireEvent.change(screen.getByLabelText(/Sommet de référence B/), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Poser comme pan du toit' }))

    await waitFor(() => expect(atelier.ajouterPanDepuisContour).toHaveBeenCalledTimes(1))
    const contour = atelier.ajouterPanDepuisContour.mock.calls[0][0]
    expect(contour.length).toBeGreaterThanOrEqual(3)
    // Le contour du contrat est posé autour de l'épingle (-7.6, 33.5).
    for (const [lng, lat] of contour) {
      expect(Math.abs(lng - (-7.6))).toBeLessThan(0.01)
      expect(Math.abs(lat - 33.5)).toBeLessThan(0.01)
    }
    expect(enregistrerLayout).not.toHaveBeenCalled()
    expect(await screen.findByTestId('cal-calage-message')).toHaveTextContent('Pan posé dans l’atelier')
  })

  it('le calage part au serveur : points A/B du plan, distance saisie, rotation', async () => {
    const utilisateur = userEvent.setup()
    rendre({ builderApi: builderApi() })
    await proposerLeContour(utilisateur)

    importerPlan.mockResolvedValueOnce(reponse('exemple'))
    fireEvent.change(screen.getByLabelText(/Distance réelle/), { target: { value: '30' } })
    fireEvent.change(screen.getByLabelText(/Rotation/), { target: { value: '15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Poser comme pan du toit' }))

    await waitFor(() => expect(importerPlan).toHaveBeenCalledTimes(3))
    const [id, corps] = importerPlan.mock.calls[2]
    expect(id).toBe(7)
    expect(corps.get('calque')).toBe(contrat('exemple').calque)
    const calage = JSON.parse(corps.get('calage'))
    const contour = contrat('exemple').contour
    expect(calage).toEqual({
      pointA: contour[0], pointB: contour[1], distanceM: 30, rotationDeg: 15,
    })
  })

  it('sans distance réelle : refus SOUS le champ, aucun appel, aucun pan', async () => {
    const utilisateur = userEvent.setup()
    const atelier = builderApi()
    rendre({ builderApi: atelier })
    await proposerLeContour(utilisateur)

    fireEvent.click(screen.getByRole('button', { name: 'Poser comme pan du toit' }))
    expect(screen.getByTestId('cal-calage-erreur-distanceReelleM')).toHaveTextContent('distance réelle')
    expect(importerPlan).toHaveBeenCalledTimes(2) // analyse + contour, rien de plus
    expect(atelier.ajouterPanDepuisContour).not.toHaveBeenCalled()
    expect(screen.getByTestId('cal-calage-facteur')).toHaveTextContent('aucune échelle n’est estimée')
  })

  it('l’atelier refuse le contour (il se croise) : le motif nommé est affiché, rien n’est posé', async () => {
    const utilisateur = userEvent.setup()
    const atelier = { ajouterPanDepuisContour: vi.fn(() => ({ ok: false, motif: 'Le contour se croise (nœud papillon).' })) }
    rendre({ builderApi: atelier })
    await proposerLeContour(utilisateur)

    importerPlan.mockResolvedValueOnce(reponse('exemple'))
    fireEvent.change(screen.getByLabelText(/Distance réelle/), { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Poser comme pan du toit' }))

    expect(await screen.findByTestId('cal-calage-bandeau-import')).toHaveTextContent('se croise')
    expect(screen.queryByText(/Pan posé dans l’atelier/)).toBeNull()
  })

  it('sans épingle, le refus 400 du serveur nomme `pin`', async () => {
    const utilisateur = userEvent.setup()
    const atelier = builderApi()
    rendre({ builderApi: atelier })
    await proposerLeContour(utilisateur)

    importerPlan.mockRejectedValueOnce({ response: { data: contrat('refus_sans_epingle_400') } })
    fireEvent.change(screen.getByLabelText(/Distance réelle/), { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Poser comme pan du toit' }))

    expect(await screen.findByTestId('cal-calage-bandeau-import')).toHaveTextContent('pin')
    expect(atelier.ajouterPanDepuisContour).not.toHaveBeenCalled()
  })

  it('hors atelier (pas de builderApi) : le dit, sans appel serveur', async () => {
    const utilisateur = userEvent.setup()
    rendre()
    await proposerLeContour(utilisateur)

    fireEvent.change(screen.getByLabelText(/Distance réelle/), { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Poser comme pan du toit' }))

    expect(await screen.findByTestId('cal-calage-bandeau-import')).toHaveTextContent('atelier')
    expect(importerPlan).toHaveBeenCalledTimes(2)
  })

  it('sans plan déposé, il le DIT au lieu d’afficher un calque vide', async () => {
    importerPlan.mockReset()
    rendre()
    expect(await screen.findByTestId('cal-calage-sans-plan')).toBeInTheDocument()
  })
})

describe('ACAL73 — une image de plan se pose comme fond de l’atelier', () => {
  const IMAGE = () => new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'plan.png', { type: 'image/png' })
  const contratFond = () => exempleContrat('calepinage', 'calepinage_plan_importe', 'fond_plan').exemple

  beforeEach(() => {
    layout.mockResolvedValue({ data: { roof_layout: {}, empreinte_document: 'E0' } })
    envoyerFondPlan.mockResolvedValue({ data: { ...contratFond(), roof_layout: {} } })
  })

  const deposerImage = async (utilisateur) => {
    await screen.findByTestId('cal-calage-sans-plan')
    await waitFor(() => expect(layout).toHaveBeenCalled())
    await utilisateur.upload(screen.getByLabelText('Image de plan (PNG ou JPEG)'), IMAGE())
  }

  it('image déposée → POST fond-plan/ puis appliquerSection underlay', async () => {
    const utilisateur = userEvent.setup()
    const documentVivant = { empreinte: 'EATELIER', appliquerSection: vi.fn() }
    rendre({ documentVivant })
    await deposerImage(utilisateur)

    await utilisateur.click(screen.getByRole('button', { name: 'Poser comme fond de l’atelier' }))

    await waitFor(() => expect(envoyerFondPlan).toHaveBeenCalledTimes(1))
    const [id, corps] = envoyerFondPlan.mock.calls[0]
    expect(id).toBe(7)
    expect(corps).toBeInstanceOf(FormData)
    expect(corps.get('fichier')).toBeTruthy()
    // Le jeton de l'atelier vivant prime sur celui de la lecture de l'onglet.
    expect(corps.get('base_empreinte')).toBe('EATELIER')
    await waitFor(() => expect(documentVivant.appliquerSection).toHaveBeenCalledTimes(1))
    expect(documentVivant.appliquerSection).toHaveBeenCalledWith(
      'underlay', contratFond().underlay, contratFond().empreinte_document)
    expect(await screen.findByText(/Image posée comme fond de l’atelier/)).toBeInTheDocument()
    expect(enregistrerLayout).not.toHaveBeenCalled()
  })

  it('sans atelier vivant, le jeton est celui de la lecture du document', async () => {
    const utilisateur = userEvent.setup()
    rendre()
    await deposerImage(utilisateur)
    await utilisateur.click(screen.getByRole('button', { name: 'Poser comme fond de l’atelier' }))
    await waitFor(() => expect(envoyerFondPlan).toHaveBeenCalledTimes(1))
    expect(envoyerFondPlan.mock.calls[0][1].get('base_empreinte')).toBe('E0')
  })

  it('sans image choisie : refus sous le geste, aucun appel', async () => {
    const utilisateur = userEvent.setup()
    rendre()
    await screen.findByTestId('cal-calage-sans-plan')
    await utilisateur.click(screen.getByRole('button', { name: 'Poser comme fond de l’atelier' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Choisissez une image de plan')
    expect(envoyerFondPlan).not.toHaveBeenCalled()
  })

  it('échec → le message du serveur est affiché, rien n’est poussé dans l’atelier', async () => {
    const utilisateur = userEvent.setup()
    const documentVivant = { empreinte: 'E0', appliquerSection: vi.fn() }
    const refus = exempleContrat('calepinage', 'calepinage_plan_importe', 'fond_plan').refus_400
    envoyerFondPlan.mockRejectedValue({ response: { status: 400, data: refus } })
    rendre({ documentVivant })
    await deposerImage(utilisateur)
    await utilisateur.click(screen.getByRole('button', { name: 'Poser comme fond de l’atelier' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(refus.fichier)
    expect(documentVivant.appliquerSection).not.toHaveBeenCalled()
  })

  it('jeton périmé (409) : le dit et relit le document', async () => {
    const utilisateur = userEvent.setup()
    envoyerFondPlan.mockRejectedValue({ response: { status: 409, data: { code: 'document_modifie' } } })
    rendre()
    await deposerImage(utilisateur)
    await utilisateur.click(screen.getByRole('button', { name: 'Poser comme fond de l’atelier' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('changé ailleurs')
    await waitFor(() => expect(layout).toHaveBeenCalledTimes(2))
  })

  it('document illisible : rien n’est envoyé', async () => {
    const utilisateur = userEvent.setup()
    layout.mockRejectedValue(new Error('500'))
    rendre()
    await screen.findByTestId('cal-calage-sans-plan')
    await utilisateur.upload(screen.getByLabelText('Image de plan (PNG ou JPEG)'), IMAGE())
    await utilisateur.click(screen.getByRole('button', { name: 'Poser comme fond de l’atelier' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Conception illisible')
    expect(envoyerFondPlan).not.toHaveBeenCalled()
  })
})

describe('CAL63 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/plan` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/plan')
    expect(route, 'route de calage du plan absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})
