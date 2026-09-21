import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import OkrDashboard from './OkrDashboard.jsx'

/* NTHCM9 — écran « Mes OKR ». PACT10 : la charge utile vient de l'exemple
   committé `apps/rh/contract_samples/okr_tableau_de_bord.json`, le même
   fichier que `scripts/check_api_shapes.py` compare au dictionnaire réellement
   renvoyé par `OkrIndividuelViewSet.tableau_de_bord`. */

const CONTRAT = exempleContrat('rh', 'okr_tableau_de_bord')
const MON_OKR = CONTRAT.mes_okr[0]
const OKR_EQUIPE = CONTRAT.equipe[0]
const OBJECTIF = CONTRAT.entreprise[0]
const OBJECTIF_SANS_CONTRIBUTEUR = CONTRAT.entreprise[1]

vi.mock('../../api/rhApi', () => ({
  default: { getTableauBordOkr: vi.fn() },
}))

function renderEcran() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <OkrDashboard />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('OkrDashboard (NTHCM9)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('distingue mes OKR, ceux de l’équipe et ceux de l’entreprise', async () => {
    rhApi.getTableauBordOkr.mockResolvedValue(
      reponseContrat('rh', 'okr_tableau_de_bord'))
    renderEcran()

    expect(await screen.findByText(MON_OKR.titre)).toBeTruthy()
    expect(screen.getByText(OKR_EQUIPE.titre)).toBeTruthy()
    expect(screen.getByText(OBJECTIF.titre)).toBeTruthy()
    // Trois sections distinctes, jamais une liste unique fusionnée.
    expect(screen.getByText('OKR de mon équipe')).toBeTruthy()
    expect(screen.getByText('Objectifs d’entreprise (rollup)')).toBeTruthy()
  })

  it('n’affiche jamais « 0 % » pour un objectif sans contributeur', async () => {
    rhApi.getTableauBordOkr.mockResolvedValue(
      reponseContrat('rh', 'okr_tableau_de_bord'))
    renderEcran()

    await screen.findByText(OBJECTIF_SANS_CONTRIBUTEUR.titre)
    // `progression_okr_pct` est null : l'écran le dit, il n'invente pas un 0 %
    // qui se lirait comme « tout le monde est à zéro ».
    expect(screen.getAllByText('non mesuré').length).toBeGreaterThan(0)
    expect(screen.getByText(`${OBJECTIF.progression_okr_pct} %`)).toBeTruthy()
  })

  it('transmet la période au serveur (jamais un filtrage local)', async () => {
    rhApi.getTableauBordOkr.mockResolvedValue(
      reponseContrat('rh', 'okr_tableau_de_bord'))
    renderEcran()
    await screen.findByText(MON_OKR.titre)

    fireEvent.change(screen.getByLabelText('Période'),
      { target: { value: 'T2-2027' } })

    await waitFor(() => {
      expect(rhApi.getTableauBordOkr)
        .toHaveBeenCalledWith({ periode: 'T2-2027' })
    })
  })

  it('rend l’état vide du contrat sans planter', async () => {
    rhApi.getTableauBordOkr.mockResolvedValue(
      reponseContrat('rh', 'okr_tableau_de_bord', 'exemple_vide'))
    renderEcran()

    expect(await screen.findByText(/Aucun OKR ne vous est rattaché/))
      .toBeTruthy()
    expect(screen.getByText(/Aucun rapport direct ne porte/)).toBeTruthy()
    expect(screen.getByText('Aucun objectif d’entreprise')).toBeTruthy()
  })
})
