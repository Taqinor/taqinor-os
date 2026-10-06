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
const decision = vi.fn()

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      enregistrerLayoutCalepinage: (...a) => enregistrerLayout(...a),
      decisionSuggestionPente: (...a) => decision(...a),
    },
    parametres: {
      suggestionPenteDisponible: (...a) => disponibilite(...a),
    },
  },
}))

const { default: SaisiePente } = await import('../SaisiePente')

/** Le pan tel que le serveur le persiste après `proposer` (ACAL65) : la
 *  suggestion est la pente du TERRAIN, `pitchDeg` du pan n'est jamais touché. */
const suggestion = (statut = 'suggeree') => ({
  status: statut,
  valeurDeg: 27.4,
  source: 'IGN — RGE ALTI® / LiDAR HD',
  sourceUrl: 'https://data.geopf.fr/altimetrie/',
  suggestedAt: '2026-09-21T08:00:00+00:00',
  decidedAt: null,
  libelle: 'pente du terrain',
  points: 4,
})
const documentAvec = (statut) => ({
  zones: [{ id: 'pan-1', pitchDeg: 18, vertices: [[0, 0], [1, 0], [1, 1]], pitchSuggestion: suggestion(statut) }],
})
const reponseDecision = (statut, empreinte = 'E1') => ({
  data: { roof_layout: documentAvec(statut), empreinte_document: empreinte, inchange: false, version: 2 },
})

const DOCUMENT_LAYOUT = { zones: [{ id: 'pan-1', vertices: [[0, 0], [1, 0], [1, 1]] }] }

beforeEach(() => {
  vi.clearAllMocks()
  layout.mockResolvedValue({ data: { roof_layout: DOCUMENT_LAYOUT, empreinte_document: 'E0' } })
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
    expect(decision).not.toHaveBeenCalled()
  })
})

describe('CALX29 / ACAL66 — société en France : suggestions par pan, décidées par le serveur', () => {
  const dispo = () => disponibilite.mockResolvedValue({ data: { disponible: true, suggestions: [], detail: '' } })

  it('le bouton propose par le SERVEUR (proposer + base_empreinte) et la suggestion s’affiche avec sa source', async () => {
    dispo()
    decision.mockResolvedValue(reponseDecision('suggeree'))
    rendre()

    fireEvent.click(await screen.findByTestId('cal-pente-lidar-suggerer'))

    await waitFor(() => expect(decision).toHaveBeenCalledTimes(1))
    expect(decision).toHaveBeenCalledWith(7, { operation: 'proposer', base_empreinte: 'E0' })
    expect(await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')).toBeInTheDocument()
    expect(screen.getByTestId('cal-pente-lidar-source-pan-1'))
      .toHaveTextContent('IGN — RGE ALTI® / LiDAR HD')
  })

  it('la carte dit « Pente du terrain » et que la pente du pan n’est jamais modifiée', async () => {
    dispo()
    decision.mockResolvedValue(reponseDecision('suggeree'))
    rendre()
    fireEvent.click(await screen.findByTestId('cal-pente-lidar-suggerer'))
    const carte = await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')
    expect(carte).toHaveTextContent('Pente du terrain (LiDAR IGN)')
    expect(carte).toHaveTextContent('jamais recopiée dans la pente du pan')
    expect(carte).toHaveTextContent('27.4')
  })

  it('la mention sur les obstacles apparaît dès qu’une suggestion est affichée', async () => {
    dispo()
    decision.mockResolvedValue(reponseDecision('suggeree'))
    rendre()
    fireEvent.click(await screen.findByTestId('cal-pente-lidar-suggerer'))
    await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')
    expect(screen.getByTestId('cal-pente-lidar-mention')).toHaveTextContent('obstacles')
  })

  it('rouvrir l’onglet retrouve une suggestion déjà persistée (« suggeree »)', async () => {
    dispo()
    layout.mockResolvedValue({ data: { roof_layout: documentAvec('suggeree'), empreinte_document: 'E0' } })
    rendre()
    expect(await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')).toBeInTheDocument()
    expect(decision).not.toHaveBeenCalled()
  })

  it('Jeter → POST suggestions-pente/ operation refuser (persisté), la pente saisie reste intacte', async () => {
    dispo()
    layout.mockResolvedValue({ data: { roof_layout: documentAvec('suggeree'), empreinte_document: 'E0' } })
    decision.mockResolvedValue(reponseDecision('refusee', 'E2'))
    rendre()
    fireEvent.change(await screen.findByLabelText(/Pente \(°\)/), { target: { value: '12' } })
    await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')

    fireEvent.click(screen.getByTestId('cal-pente-lidar-jeter-pan-1'))

    await waitFor(() => expect(decision).toHaveBeenCalledTimes(1))
    expect(decision).toHaveBeenCalledWith(7, { operation: 'refuser', zone_id: 'pan-1', base_empreinte: 'E0' })
    await waitFor(() => {
      expect(screen.queryByTestId('cal-pente-lidar-suggestion-pan-1')).not.toBeInTheDocument()
    })
    expect(enregistrerLayout).not.toHaveBeenCalled()
    expect(screen.getByTestId('cal-pente-valeur')).toHaveTextContent('12.0')
  })

  it('Accepter n’écrit pas pitchDeg : décision serveur seule, aucune écriture locale du document', async () => {
    dispo()
    layout.mockResolvedValue({ data: { roof_layout: documentAvec('suggeree'), empreinte_document: 'E0' } })
    decision.mockResolvedValue(reponseDecision('validee', 'E2'))
    rendre()
    await screen.findByTestId('cal-pente-lidar-suggestion-pan-1')

    fireEvent.click(screen.getByTestId('cal-pente-lidar-accepter-pan-1'))

    await waitFor(() => expect(decision).toHaveBeenCalledTimes(1))
    expect(decision).toHaveBeenCalledWith(7, { operation: 'accepter', zone_id: 'pan-1', base_empreinte: 'E0' })
    // Aucune écriture du document entier (l'ancienne copie inline `{...layout, zones}`).
    expect(enregistrerLayout).not.toHaveBeenCalled()
    await waitFor(() => {
      expect(screen.queryByTestId('cal-pente-lidar-suggestion-pan-1')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('cal-pente-lidar-message')).toHaveTextContent('pente du terrain')
    expect(screen.getByTestId('cal-pente-lidar-message')).toHaveTextContent('la pente du pan n’est pas modifiée')
    // La pente du pan (18°) n'a pas été remplacée par les 27,4° du terrain.
    expect(screen.getByTestId('cal-pente-valeur')).not.toHaveTextContent('27.4')
  })

  it('pousse le document rendu dans l’atelier vivant, avec son jeton, et signe avec celui de l’atelier', async () => {
    dispo()
    const documentVivant = { empreinte: 'EATELIER', appliquerSection: vi.fn() }
    decision.mockResolvedValue(reponseDecision('suggeree', 'E5'))
    rendre({ documentVivant })
    fireEvent.click(await screen.findByTestId('cal-pente-lidar-suggerer'))
    await waitFor(() => expect(documentVivant.appliquerSection).toHaveBeenCalledTimes(1))
    expect(decision.mock.calls[0][1].base_empreinte).toBe('EATELIER')
    const [cle, zones, empreinte] = documentVivant.appliquerSection.mock.calls[0]
    expect(cle).toBe('zones')
    expect(zones[0].pitchSuggestion.status).toBe('suggeree')
    expect(empreinte).toBe('E5')
  })

  it('jeton périmé (409) : message, document relu, rien d’écrit', async () => {
    dispo()
    decision.mockRejectedValue({ response: { status: 409, data: { code: 'document_modifie' } } })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-pente-lidar-suggerer'))
    expect(await screen.findByTestId('cal-pente-lidar-message')).toHaveTextContent('changé ailleurs')
    await waitFor(() => expect(layout).toHaveBeenCalledTimes(2))
    expect(enregistrerLayout).not.toHaveBeenCalled()
  })

  it('lecture du document en échec : aucune suggestion demandée', async () => {
    dispo()
    layout.mockRejectedValue(new Error('500'))
    rendre()
    fireEvent.click(await screen.findByTestId('cal-pente-lidar-suggerer'))
    expect(decision).not.toHaveBeenCalled()
  })

  it('le décalage x/y/z (jamais envoyé) est retiré', async () => {
    dispo()
    rendre()
    await screen.findByTestId('cal-pente-lidar-suggerer')
    expect(screen.queryByTestId('cal-pente-lidar-decalage')).not.toBeInTheDocument()
    expect(screen.queryByTestId('cal-pente-lidar-decalage-x')).not.toBeInTheDocument()
  })
})
