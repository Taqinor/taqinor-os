import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CALX29 — SUGGESTION DE PENTE LIDAR IGN, FRANCE SEULEMENT.
   ----------------------------------------------------------------------------
   Le bouton « Suggérer depuis l'IGN » n'existe QUE si la lecture locale
   (`GET .../parametres/suggestion-pente/`) dit `disponible: true` — une
   société marocaine n'a ni bouton ni appel de suggestion. Une société
   française reçoit une suggestion PAR PAN, avec sa source et son horodatage,
   qu'elle accepte (la pente s'écrit, tracée) ou jette (la saisie reste seule
   vérité). La limite de la donnée (obstacles absents) est dite dès qu'une
   suggestion est affichée.
   ========================================================================== */

const layout = vi.fn()
const enregistrerLayout = vi.fn()
const disponibilite = vi.fn()
const suggererPentes = vi.fn()

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      enregistrerLayoutCalepinage: (...a) => enregistrerLayout(...a),
    },
    parametres: {
      suggestionPenteDisponible: (...a) => disponibilite(...a),
      suggererPentesIGN: (...a) => suggererPentes(...a),
    },
  },
}))

const { default: SaisiePente } = await import('../SaisiePente')

const UNE_SUGGESTION = {
  zoneId: 'pan-1',
  pitchDeg: 27.4,
  facingAzimuthDeg: 180.0,
  source: 'IGN — RGE ALTI® / LiDAR HD',
  sourceUrl: 'https://data.geopf.fr/altimetrie/',
  suggestedAt: '2026-09-21T08:00:00+00:00',
  status: 'suggeree',
  points: 4,
}

const DOCUMENT_LAYOUT = { zones: [{ id: 'pan-1', vertices: [[0, 0], [1, 0], [1, 1]] }] }

beforeEach(() => {
  vi.clearAllMocks()
  layout.mockResolvedValue({ data: { roof_layout: DOCUMENT_LAYOUT } })
  enregistrerLayout.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><SaisiePente calepinageId={7} {...props} /></MemoryRouter>,
)

describe('CALX29 — société hors France : aucun bouton, aucun appel', () => {
  it('pays "ma" ⇒ disponible: false ⇒ pas de bouton, jamais de suggestion demandée', async () => {
    disponibilite.mockResolvedValue({ data: { disponible: false, suggestions: [], detail: '' } })
    rendre()
    await waitFor(() => expect(disponibilite).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('cal-pente-lidar-suggerer')).not.toBeInTheDocument()
    expect(screen.queryByTestId('cal-pente-lidar')).not.toBeInTheDocument()
    expect(suggererPentes).not.toHaveBeenCalled()
  })
})

describe('CALX29 — société en France : suggestions par pan, avec source', () => {
  it('le bouton apparaît, et une suggestion par pan s’affiche avec sa source', async () => {
    disponibilite.mockResolvedValue({ data: { disponible: true, suggestions: [], detail: '' } })
    suggererPentes.mockResolvedValue({ data: { disponible: true, suggestions: [UNE_SUGGESTION], detail: '' } })
    rendre()

    const bouton = await screen.findByTestId('cal-pente-lidar-suggerer')
    fireEvent.click(bouton)

    await waitFor(() => expect(suggererPentes).toHaveBeenCalledTimes(1))
    expect(await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')).toBeInTheDocument()
    expect(screen.getByTestId('cal-pente-lidar-source-pan-1'))
      .toHaveTextContent('IGN — RGE ALTI® / LiDAR HD')
  })

  it('la mention sur les obstacles apparaît dès qu’une suggestion est affichée', async () => {
    disponibilite.mockResolvedValue({ data: { disponible: true, suggestions: [], detail: '' } })
    suggererPentes.mockResolvedValue({ data: { disponible: true, suggestions: [UNE_SUGGESTION], detail: '' } })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-pente-lidar-suggerer'))
    await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')
    expect(screen.getByTestId('cal-pente-lidar-mention')).toHaveTextContent('obstacles')
  })

  it('une suggestion JETÉE laisse la pente saisie intacte — rien n’est enregistré', async () => {
    disponibilite.mockResolvedValue({ data: { disponible: true, suggestions: [], detail: '' } })
    suggererPentes.mockResolvedValue({ data: { disponible: true, suggestions: [UNE_SUGGESTION], detail: '' } })
    rendre()
    fireEvent.change(await screen.findByLabelText(/Pente \(°\)/), { target: { value: '12' } })

    fireEvent.click(screen.getByTestId('cal-pente-lidar-suggerer'))
    await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')
    fireEvent.click(screen.getByTestId('cal-pente-lidar-jeter-pan-1'))

    expect(screen.queryByTestId('cal-pente-lidar-suggestion-pan-1')).not.toBeInTheDocument()
    expect(enregistrerLayout).not.toHaveBeenCalled()
    // La pente saisie à la main n'a pas bougé.
    expect(screen.getByTestId('cal-pente-valeur')).toHaveTextContent('12.0')
  })

  it('une suggestion ACCEPTÉE écrit la pente AVEC sa source et son horodatage', async () => {
    disponibilite.mockResolvedValue({ data: { disponible: true, suggestions: [], detail: '' } })
    suggererPentes.mockResolvedValue({ data: { disponible: true, suggestions: [UNE_SUGGESTION], detail: '' } })
    rendre()

    fireEvent.click(await screen.findByTestId('cal-pente-lidar-suggerer'))
    await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')
    fireEvent.click(screen.getByTestId('cal-pente-lidar-accepter-pan-1'))

    await waitFor(() => expect(enregistrerLayout).toHaveBeenCalledTimes(1))
    const [, document] = enregistrerLayout.mock.calls[0]
    const pan = document.zones.find((z) => z.id === 'pan-1')
    expect(pan.pitchDeg).toBe(27.4)
    expect(pan.pitchSuggestion.source).toBe('IGN — RGE ALTI® / LiDAR HD')
    expect(pan.pitchSuggestion.status).toBe('validee')
    expect(pan.pitchSuggestion.decidedAt).toBeTruthy()

    // La suggestion acceptée disparaît de la liste des suggestions en attente.
    expect(screen.queryByTestId('cal-pente-lidar-suggestion-pan-1')).not.toBeInTheDocument()
  })
})
