import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { espions, REPONSE_POSE } from '../../test/fixtures/calepinageApiMock'
import { SAISIE_SOL } from '../../test/fixtures/saisiesSurfacePose'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ENF15 — l'onglet « Terrain » (CALX1) est MONTÉ. Le détail (pas mesuré, dessin du
   champ, enregistrement) vit dans `__tests__/mode_terrain.test.jsx` ; ici, l'onglet
   tel que le rail le monte : saisie incomplète = aucune demande au moteur ; saisie
   complète = le compte de modules affiché est celui du moteur. */

// ACAL466 — `penteTerrain` s'ajoute à la doublure partagée (même forme que le contrat).
const { penteTerrain } = vi.hoisted(() => ({ penteTerrain: vi.fn() }))
vi.mock('../../api/calepinageApi', async () => {
  const doublure = (await import('../../test/fixtures/calepinageApiMock')).apiDocument({ moteur: true })
  doublure.default.calepinages.penteTerrain = (...a) => penteTerrain(...a)
  return doublure
})

const { default: ModeTerrain } = await import('./ModeTerrain')

const monter = () => render(<MemoryRouter><ModeTerrain calepinageId={7} /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  espions.layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'PAN-A' }] }, empreinte_document: 'E0' } })
  espions.pose.mockResolvedValue({ data: REPONSE_POSE })
})
afterEach(() => { cleanup() })

describe('ModeTerrain — onglet monté', () => {
  it('saisie incomplète : rien n’est envoyé au moteur, le refus est dit', async () => {
    monter()
    await waitFor(() => expect(espions.layout).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    expect(espions.pose).not.toHaveBeenCalled()
    expect(await screen.findByTestId('cal-terrain-message')).toHaveTextContent(/incomplètes/)
  })

  it('saisie complète : le compte de modules affiché est celui du moteur', async () => {
    monter()
    await waitFor(() => expect(espions.layout).toHaveBeenCalled())
    for (const [cle, valeur] of Object.entries(SAISIE_SOL)) {
      const champ = screen.queryByTestId(`cal-terrain-${cle}`)
      if (champ) fireEvent.change(champ, { target: { value: valeur } })
    }
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => expect(espions.pose).toHaveBeenCalledTimes(1))
    const modules = await screen.findByTestId('cal-terrain-modules')
    expect(modules).toHaveTextContent(String(REPONSE_POSE.plans[0].modules))
  })
})

describe('ModeTerrain — largeur de l’onglet (ACAL1511)', () => {
  it('les chiffres et les champs se rangent selon la largeur de l’onglet, pas de la fenêtre', async () => {
    monter()
    await waitFor(() => expect(espions.layout).toHaveBeenCalled())
    for (const [cle, valeur] of Object.entries(SAISIE_SOL)) {
      const champ = screen.queryByTestId(`cal-terrain-${cle}`)
      if (champ) fireEvent.change(champ, { target: { value: valeur } })
    }
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    const modules = await screen.findByTestId('cal-terrain-modules')
    const grille = modules.parentElement
    expect(grille.className).not.toMatch(/(^|\s)sm:grid-cols-5/)
    expect(grille.className).toMatch(/@3xl:grid-cols-5/)
    expect(screen.getByTestId('cal-terrain')).toHaveClass('@container')
    expect(screen.getByTestId('cal-terrain-largeurM').closest('div').className).not.toMatch(/(^|\s)sm:grid-cols-3/)
  })
})

describe('ModeTerrain — pente du relief (ACAL466, contrat calepinage_pente_terrain.json)', () => {
  const contrat = (cle) => exempleContrat('calepinage', 'calepinage_pente_terrain', cle)
  const SURFACE = { id: 'TERRAIN', kind: 'sol', vertices: [[-7.59, 33.57], [-7.58, 33.57], [-7.58, 33.56]] }

  beforeEach(() => {
    espions.layout.mockResolvedValue({
      data: { roof_layout: { zones: [{ id: 'PAN-A' }], poseSurfaces: [SURFACE] }, empreinte_document: 'E0' },
    })
  })

  it('lit le relief, affiche pente, source et attribution, et « Utiliser » remplit le champ saisi', async () => {
    penteTerrain.mockResolvedValue({ data: contrat('exemple') })
    monter()
    await waitFor(() => expect(screen.getByTestId('cal-terrain-relief-lire')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('cal-terrain-relief-lire'))
    expect(await screen.findByTestId('cal-terrain-relief-pente')).toHaveTextContent(`${contrat('exemple').pente_deg} °`)
    expect(penteTerrain).toHaveBeenCalledWith(7, 'TERRAIN')
    expect(screen.getByTestId('cal-terrain-relief-source')).toHaveTextContent(contrat('exemple').source)
    expect(screen.getByTestId('cal-terrain-relief-attribution')).toHaveTextContent(contrat('exemple').attribution)
    expect(screen.queryByTestId('cal-terrain-relief-ancrage')).toBeNull()
    expect(screen.getByTestId('cal-terrain-penteTerrainDeg').value).toBe('')
    fireEvent.click(screen.getByTestId('cal-terrain-relief-utiliser'))
    expect(screen.getByTestId('cal-terrain-penteTerrainDeg').value).toBe(String(contrat('exemple').pente_deg))
  })

  it('relief illisible : le motif est dit, aucune pente n’est proposée ni écrite', async () => {
    penteTerrain.mockResolvedValue({ data: contrat('exemple_sans_pente') })
    monter()
    await waitFor(() => expect(screen.getByTestId('cal-terrain-relief-lire')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('cal-terrain-relief-lire'))
    expect(await screen.findByTestId('cal-terrain-relief-motif')).toHaveTextContent(contrat('exemple_sans_pente').motif)
    expect(screen.queryByTestId('cal-terrain-relief-utiliser')).toBeNull()
    expect(screen.getByTestId('cal-terrain-penteTerrainDeg').value).toBe('')
  })

  it('champ non enregistré : la lecture est désactivée et le dit', async () => {
    espions.layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'PAN-A' }] }, empreinte_document: 'E0' } })
    monter()
    await waitFor(() => expect(espions.layout).toHaveBeenCalled())
    expect(screen.getByTestId('cal-terrain-relief-lire')).toBeDisabled()
    expect(screen.getByTestId('cal-terrain-relief-aide')).toBeInTheDocument()
  })

  it('contour saisi en mètres : le serveur dit que le relief est lu autour de l’épingle', async () => {
    penteTerrain.mockResolvedValue({ data: { ...contrat('exemple'), ancrage: 'epingle_du_site' } })
    monter()
    await waitFor(() => expect(screen.getByTestId('cal-terrain-relief-lire')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('cal-terrain-relief-lire'))
    expect(await screen.findByTestId('cal-terrain-relief-ancrage')).toHaveTextContent(/épingle du site/)
  })
})

describe('ModeTerrain — champ enregistré depuis un contour tracé (ACAL1425)', () => {
  const TRACE = {
    kind: 'sol', id: 'sol-1', label: 'Champ au sol 1', areaM2: 183.4,
    vertices: [[-7.59, 33.57], [-7.58, 33.57], [-7.58, 33.56], [-7.585, 33.555], [-7.59, 33.56]],
    contourM: [[0, 0], [20, 0], [20, 9], [10, 12], [0, 9]],
    engine: { modules: 50, tables: [] },
  }

  it('la surface tracée est reconnue : relief actif, surface dite, largeur × profondeur sans objet', async () => {
    espions.layout.mockResolvedValue({
      data: { roof_layout: { zones: [{ id: 'PAN-A' }], poseSurfaces: [TRACE] }, empreinte_document: 'E0' },
    })
    monter()
    await waitFor(() => expect(screen.getByTestId('cal-terrain-relief-lire')).not.toBeDisabled())
    expect(screen.queryByTestId('cal-terrain-relief-aide')).toBeNull()
    const mention = await screen.findByTestId('cal-terrain-contour-trace')
    expect(mention).toHaveTextContent('Champ enregistré — contour tracé, 183 m²')
    expect(mention).toHaveTextContent('ne s’appliquent pas')
  })

  it('un champ saisi au rectangle ne porte pas la mention du contour tracé', async () => {
    espions.layout.mockResolvedValue({
      data: {
        roof_layout: {
          zones: [{ id: 'PAN-A' }],
          // Un rectangle saisi n'écrit pas `vertices` (marqueur du tracé sur la carte).
          poseSurfaces: [{ ...TRACE, vertices: undefined, id: 'TERRAIN', contourM: [[0, 0], [30, 0], [30, 22], [0, 22]] }],
        },
        empreinte_document: 'E0',
      },
    })
    monter()
    await waitFor(() => expect(screen.getByTestId('cal-terrain-relief-lire')).not.toBeDisabled())
    expect(screen.queryByTestId('cal-terrain-contour-trace')).toBeNull()
  })

  it('un contour tracé à QUATRE coins porte la mention ; un rectangle stocké en anneau fermé de 5 points ne l’a pas', async () => {
    const quatre = { ...TRACE, vertices: TRACE.vertices.slice(0, 4), contourM: [[0, 0], [20, 0], [20, 9], [0, 9]] }
    espions.layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'PAN-A' }], poseSurfaces: [quatre] }, empreinte_document: 'E0' } })
    monter()
    expect(await screen.findByTestId('cal-terrain-contour-trace')).toHaveTextContent('contour tracé')
    cleanup()
    const anneau = { ...TRACE, vertices: undefined, contourM: [[0, 0], [30, 0], [30, 22], [0, 22], [0, 0]] }
    espions.layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'PAN-A' }], poseSurfaces: [anneau] }, empreinte_document: 'E0' } })
    monter()
    await waitFor(() => expect(screen.getByTestId('cal-terrain-relief-lire')).not.toBeDisabled())
    expect(screen.queryByTestId('cal-terrain-contour-trace')).toBeNull()
  })
})
