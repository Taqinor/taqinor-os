import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

// CH6 — timeline de cycle de vie du chantier (remplace le simple statut) :
// (1) rend chaque étape avec son état de gate + raisons de blocage en
// français ; (2) surface la prochaine action (avancer-etape) et remonte les
// raisons de blocage d'un 400 ; (3) met en avant CH3 (recette) + CH4 (pack de
// remise) ; (4) dégrade proprement quand la société n'a configuré aucune
// étape (comportement historique préservé).

const api = vi.hoisted(() => ({
  getEtapesChantier: vi.fn(),
  avancerEtape: vi.fn(),
  getRecette: vi.fn(),
  ouvrirRecette: vi.fn(),
  getPackRemise: vi.fn(),
  genererPackRemise: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))

import ChantierGateTimeline from './ChantierGateTimeline'

const ETAPES_RESPONSE = {
  installation: 1,
  reference: 'CH-001',
  etape_courante: 'montage_mecanique',
  etapes: [
    {
      cle: 'etude_site', libelle: 'Étude de site', ordre: 0, bloquant: false,
      satisfait: true, raisons: [], id: 1, statut_legacy: null, courante: false,
    },
    {
      cle: 'montage_mecanique', libelle: 'Montage mécanique', ordre: 1,
      bloquant: true, satisfait: true, raisons: [], id: 2,
      statut_legacy: 'installe', courante: true,
    },
    {
      cle: 'mise_en_service', libelle: 'Mise en service', ordre: 2,
      bloquant: true, satisfait: false,
      raisons: ["Fiche de recette IEC 62446-1 non passée."],
      id: 3, statut_legacy: 'mise_en_service', courante: false,
    },
  ],
}

beforeEach(() => {
  api.getEtapesChantier.mockResolvedValue({ data: ETAPES_RESPONSE })
  api.getRecette.mockResolvedValue({ data: { installation: 1, record: null } })
  api.getPackRemise.mockResolvedValue({
    data: { installation: 1, reference: 'CH-001', pieces: [], complet: false, persiste: false },
  })
  api.avancerEtape.mockResolvedValue({ data: {} })
  api.ouvrirRecette.mockResolvedValue({ data: { id: 1, record: null } })
  api.genererPackRemise.mockResolvedValue({ data: { complet: true, pieces: [] } })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ChantierGateTimeline (CH6)', () => {
  it('affiche chaque étape du parcours avec son libellé', async () => {
    render(<ChantierGateTimeline installationId={1} />)
    await waitFor(() => expect(api.getEtapesChantier).toHaveBeenCalledWith(1))
    expect(screen.getByText('Étude de site')).toBeInTheDocument()
    expect(screen.getByText('Montage mécanique')).toBeInTheDocument()
    expect(screen.getByText('Mise en service')).toBeInTheDocument()
    // Étape courante marquée explicitement.
    expect(screen.getByText('Étape en cours')).toBeInTheDocument()
  })

  it('surface la prochaine action et les raisons de blocage françaises', async () => {
    render(<ChantierGateTimeline installationId={1} />)
    await waitFor(() => expect(api.getEtapesChantier).toHaveBeenCalled())
    // Prochaine étape après « Montage mécanique » (courante) = « Mise en service ».
    expect(screen.getByText(/Avancer vers/)).toBeInTheDocument()
    // Les raisons de blocage de l'étape non satisfaite sont visibles.
    expect(screen.getByText(/Fiche de recette IEC 62446-1 non passée/)).toBeInTheDocument()
  })

  it("appelle avancer-etape et affiche les raisons d'un 400 bloqué", async () => {
    api.avancerEtape.mockRejectedValue({
      response: { data: { detail: 'Étape bloquée par un gate.', raisons: ['Checklist incomplète.'] } },
    })
    render(<ChantierGateTimeline installationId={1} />)
    await waitFor(() => expect(api.getEtapesChantier).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ch6-avancer-btn'))
    await waitFor(() => expect(api.avancerEtape).toHaveBeenCalledWith(1, 'mise_en_service'))
    await waitFor(() =>
      expect(screen.getByTestId('ch6-blocked-reasons')).toHaveTextContent('Checklist incomplète.'))
  })

  it('met en avant la recette CH3 et le pack de remise CH4', async () => {
    render(<ChantierGateTimeline installationId={1} />)
    await waitFor(() => expect(api.getRecette).toHaveBeenCalledWith(1))
    expect(screen.getByTestId('ch6-recette')).toHaveTextContent('Recette de mise en service')
    expect(screen.getByTestId('ch6-pack-remise')).toHaveTextContent('Pack de remise client')
  })

  it('dégrade proprement quand aucune étape n\'est configurée', async () => {
    api.getEtapesChantier.mockResolvedValue({
      data: { installation: 1, reference: 'CH-001', etape_courante: null, etapes: [] },
    })
    render(<ChantierGateTimeline installationId={1} />)
    await waitFor(() => expect(api.getEtapesChantier).toHaveBeenCalled())
    expect(screen.getByText(/Aucune étape de cycle de vie configurée/)).toBeInTheDocument()
    expect(screen.queryByTestId('ch6-gate-timeline')).toBeNull()
  })
})
