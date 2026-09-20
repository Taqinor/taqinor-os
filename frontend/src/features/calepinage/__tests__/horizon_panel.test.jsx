import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CAL93 — L'HORIZON LOINTAIN : au moins deux points pour s'activer, jamais un
   horizon inventé, TOUJOURS un poste séparé de l'ombrage proche.

   CAL92 — le bouton « Récupérer depuis PVGIS » consomme
   `calepinageApi.calepinages.horizon(id)` (contrat
   `apps/calepinage/contract_samples/calepinage_horizon.json`, PACT13 : la
   charge utile vient de l'exemple COMMITTÉ, jamais d'un mock écrit à la
   main). La saisie manuelle reste possible ensuite.
   ========================================================================== */

const layout = vi.fn()
const enregistrerLayoutCalepinage = vi.fn()
const horizon = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      enregistrerLayoutCalepinage: (...a) => enregistrerLayoutCalepinage(...a),
      horizon: (...a) => horizon(...a),
    },
  },
}))

const {
  default: HorizonPanel,
} = await import('../HorizonPanel')
const {
  sortedHorizonPoints, horizonHeightAtAzimuth, horizonMaxHeightDeg, sunPosition,
  heuresMasqueesEstimation, JOUR_EQUINOXE,
} = await import('../horizonMath')

beforeEach(() => {
  vi.clearAllMocks()
  layout.mockResolvedValue({ data: { roof_layout: {} } })
})
afterEach(() => { cleanup() })

const CONTRAT = 'calepinage_horizon'

/* ── 1. Le moteur pur (mêmes garanties que apps/web/tests/horizonEngine.test.ts) ── */

describe('CAL93 — horizonMath (moteur pur)', () => {
  it('trie par azimut et écarte les points non finis', () => {
    const sorted = sortedHorizonPoints([
      { azimuthDeg: 200, heightDeg: 5 },
      { azimuthDeg: 10, heightDeg: 2 },
      { azimuthDeg: Number.NaN, heightDeg: 9 },
    ])
    expect(sorted.map((p) => p.azimuthDeg)).toEqual([10, 200])
  })

  it('interpole entre deux points, et boucle circulairement', () => {
    const pts = [{ azimuthDeg: 0, heightDeg: 0 }, { azimuthDeg: 180, heightDeg: 10 }]
    expect(horizonHeightAtAzimuth(pts, 90)).toBeCloseTo(5, 10)
  })

  it('moins de deux points ⇒ null (aucun horizon plat inventé)', () => {
    expect(horizonHeightAtAzimuth([], 90)).toBeNull()
  })

  it('hauteur maximale réelle, jamais recalculée ailleurs', () => {
    expect(horizonMaxHeightDeg([{ azimuthDeg: 0, heightDeg: 3 }, { azimuthDeg: 90, heightDeg: 12 }])).toBe(12)
  })

  it('sunPosition : à midi solaire à l’équinoxe, élévation ≈ 90 − latitude', () => {
    const lat = 33.5731
    const midi = sunPosition(lat, JOUR_EQUINOXE, 12)
    expect(Math.abs(midi.elevationDeg - (90 - lat))).toBeLessThan(1)
  })

  it('heuresMasqueesEstimation : 0 sans profil exploitable, > 0 avec un mur haut partout', () => {
    expect(heuresMasqueesEstimation(33.5731, [])).toBe(0)
    const mur = [
      { azimuthDeg: 0, heightDeg: 60 }, { azimuthDeg: 90, heightDeg: 60 },
      { azimuthDeg: 180, heightDeg: 60 }, { azimuthDeg: 270, heightDeg: 60 },
    ]
    expect(heuresMasqueesEstimation(33.5731, mur)).toBeGreaterThan(0)
  })
})

/* ── 2. L'écran ────────────────────────────────────────────────────────── */

const rendre = (props = {}) => render(
  <MemoryRouter><HorizonPanel calepinageId={7} {...props} /></MemoryRouter>,
)

describe('CAL93 — l’écran', () => {
  it('affiche le diagramme et « — » tant qu’aucun point n’est saisi', async () => {
    rendre()
    await screen.findByTestId('cal-horizon')
    expect(screen.getByTestId('cal-horizon-diagramme')).toBeInTheDocument()
    expect(screen.getByTestId('cal-horizon-hauteur-max')).toHaveTextContent('—')
    expect(screen.getByTestId('cal-horizon-heures-masquees')).toHaveTextContent('—')
  })

  it('un seul point ne suffit pas à activer le profil', async () => {
    rendre()
    await screen.findByTestId('cal-horizon')
    fireEvent.change(screen.getByLabelText(/Azimut/), { target: { value: '180' } })
    fireEvent.change(screen.getByLabelText(/Hauteur angulaire/), { target: { value: '15' } })
    fireEvent.click(screen.getByText('Ajouter le point'))
    fireEvent.click(screen.getByText('Enregistrer le profil'))
    await waitFor(() => expect(enregistrerLayoutCalepinage).toHaveBeenCalledTimes(1))
    const [, document] = enregistrerLayoutCalepinage.mock.calls[0]
    expect(document.horizonProfile).toBeUndefined()
  })

  it('deux points ou plus activent le profil, persisté dans le document', async () => {
    rendre()
    await screen.findByTestId('cal-horizon')
    fireEvent.change(screen.getByLabelText(/Azimut/), { target: { value: '90' } })
    fireEvent.change(screen.getByLabelText(/Hauteur angulaire/), { target: { value: '20' } })
    fireEvent.click(screen.getByText('Ajouter le point'))
    fireEvent.change(screen.getByLabelText(/Azimut/), { target: { value: '270' } })
    fireEvent.change(screen.getByLabelText(/Hauteur angulaire/), { target: { value: '30' } })
    fireEvent.click(screen.getByText('Ajouter le point'))

    expect(screen.getByTestId('cal-horizon-points').children).toHaveLength(2)

    fireEvent.click(screen.getByText('Enregistrer le profil'))
    await waitFor(() => expect(enregistrerLayoutCalepinage).toHaveBeenCalledTimes(1))
    const [id, document] = enregistrerLayoutCalepinage.mock.calls[0]
    expect(id).toBe(7)
    expect(document.horizonProfile.source).toBe('saisie')
    expect(document.horizonProfile.points).toHaveLength(2)
    expect(document.horizonProfile.hauteurMaxDeg).toBe(30)
  })

  it('retirer un point le fait disparaître de la liste', async () => {
    rendre()
    await screen.findByTestId('cal-horizon')
    fireEvent.change(screen.getByLabelText(/Azimut/), { target: { value: '90' } })
    fireEvent.change(screen.getByLabelText(/Hauteur angulaire/), { target: { value: '20' } })
    fireEvent.click(screen.getByText('Ajouter le point'))
    expect(screen.getByTestId('cal-horizon-points').children).toHaveLength(1)
    fireEvent.click(screen.getByLabelText(/Retirer le point/))
    expect(screen.getByText('Aucun point saisi.')).toBeInTheDocument()
  })

  it('RELIT un profil déjà enregistré et affiche sa hauteur maximale', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.5731, lng: -7.5 },
          horizonProfile: {
            source: 'saisie',
            points: [{ azimuthDeg: 0, heightDeg: 5 }, { azimuthDeg: 180, heightDeg: 25 }],
            hauteurMaxDeg: 25,
          },
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-horizon')
    await waitFor(() => expect(screen.getByTestId('cal-horizon-hauteur-max')).toHaveTextContent('25.0°'))
    expect(screen.getByTestId('cal-horizon-points').children).toHaveLength(2)
  })

  it('champs libres de saisie (jamais de snap)', async () => {
    rendre()
    await screen.findByTestId('cal-horizon')
    expect(screen.getByLabelText(/Azimut/)).toHaveAttribute('step', 'any')
    expect(screen.getByLabelText(/Hauteur angulaire/)).toHaveAttribute('step', 'any')
  })
})

describe('CAL92 — bouton « Récupérer depuis PVGIS »', () => {
  it('remplit le profil depuis l’exemple de contrat et affiche sa source', async () => {
    layout.mockResolvedValue({
      data: { roof_layout: { pin: { lat: 33.5731, lng: -7.5898 } } },
    })
    horizon.mockResolvedValue(reponseContrat('calepinage', CONTRAT))
    rendre()
    await screen.findByTestId('cal-horizon')

    fireEvent.click(screen.getByText('Récupérer depuis PVGIS'))
    await waitFor(() => expect(horizon).toHaveBeenCalledWith(7))

    const exemple = exempleContrat('calepinage', CONTRAT)
    await waitFor(() =>
      expect(screen.getByTestId('cal-horizon-points').children).toHaveLength(exemple.points.length))
    expect(screen.getByText(/Profil PVGIS récupéré/)).toBeInTheDocument()
  })

  it('sans épingle posée, le serveur rend `points: []` et le dit — rien n’est ajouté', async () => {
    horizon.mockResolvedValue(reponseContrat('calepinage', CONTRAT, 'exemple_vide'))
    rendre()
    await screen.findByTestId('cal-horizon')

    fireEvent.click(screen.getByText('Récupérer depuis PVGIS'))
    await waitFor(() => expect(horizon).toHaveBeenCalledTimes(1))
    expect(screen.getByText('Aucun point saisi.')).toBeInTheDocument()
    expect(screen.getByText(
      /Aucune épingle n'est posée sur ce calepinage/,
    )).toBeInTheDocument()
  })

  it('la saisie manuelle reste possible après un appel PVGIS', async () => {
    horizon.mockResolvedValue(reponseContrat('calepinage', CONTRAT, 'exemple_vide'))
    rendre()
    await screen.findByTestId('cal-horizon')
    fireEvent.click(screen.getByText('Récupérer depuis PVGIS'))
    await waitFor(() => expect(horizon).toHaveBeenCalledTimes(1))

    fireEvent.change(screen.getByLabelText(/Azimut/), { target: { value: '90' } })
    fireEvent.change(screen.getByLabelText(/Hauteur angulaire/), { target: { value: '20' } })
    fireEvent.click(screen.getByText('Ajouter le point'))
    expect(screen.getByTestId('cal-horizon-points').children).toHaveLength(1)
  })
})

describe('CAL93 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/horizon` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/horizon')
    expect(route, 'route horizon absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})
