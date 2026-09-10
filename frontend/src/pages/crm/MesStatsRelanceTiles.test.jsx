// CKP4/CKP6 (fondateur 2026-09-10) — 3 tuiles PERSO du Cockpit. Charge utile
// venant du contrat COMMITTÉ `apps/crm/contract_samples/mes_stats_relance.json`
// (CKP0/PACT10) — jamais un objet retapé à la main.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../test/fixtures/contractSamples'

const STATS = exempleContrat('crm', 'mes_stats_relance')

vi.mock('../../api/crmApi', () => ({
  default: { getMesStatsRelance: vi.fn() },
}))

import crmApi from '../../api/crmApi'
import MesStatsRelanceTiles from './MesStatsRelanceTiles'

beforeEach(() => {
  crmApi.getMesStatsRelance.mockResolvedValue({ data: STATS })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

// Une tuile porte son libellé PUIS sa valeur en frère suivant (patron
// `KpiRelancesPanel.mry21f.test.jsx`).
const valeurTuile = (label) => screen.getByText(label).nextSibling.textContent

describe('CKP4 MesStatsRelanceTiles', () => {
  it('affiche les 3 tuiles perso avec les valeurs du contrat', async () => {
    render(<MesStatsRelanceTiles />)
    await waitFor(() => expect(crmApi.getMesStatsRelance).toHaveBeenCalled())
    await screen.findByText('À faire maintenant')
    expect(valeurTuile('À faire maintenant')).toBe(String(STATS.a_faire_maintenant))
    expect(valeurTuile("Mon à-l'heure (7 j)")).toBe(`${STATS.a_lheure_7j_pct} %`)
    expect(valeurTuile('Série sans retard')).toBe(String(STATS.serie_jours_sans_retard))
  })

  it('un dénominateur nul affiche « pas encore de données », jamais un 0 % inventé', async () => {
    const { a_lheure_7j_pct: _omis, ...statsSansTaux } = STATS
    crmApi.getMesStatsRelance.mockResolvedValue({ data: { ...statsSansTaux, a_lheure_7j_pct: null } })
    render(<MesStatsRelanceTiles />)
    await waitFor(() => expect(crmApi.getMesStatsRelance).toHaveBeenCalled())
    await screen.findByText('À faire maintenant')
    expect(valeurTuile("Mon à-l'heure (7 j)")).toBe('pas encore de données')
    expect(screen.queryByText('0 %')).not.toBeInTheDocument()
  })

  it('jamais comparatif : aucun texte de classement/moyenne équipe', async () => {
    render(<MesStatsRelanceTiles />)
    await screen.findByText('À faire maintenant')
    expect(screen.queryByText(/moyenne|classement|équipe/i)).not.toBeInTheDocument()
  })

  it('indisponible : ne casse pas l\'écran sur un échec réseau', async () => {
    crmApi.getMesStatsRelance.mockRejectedValue(new Error('boom'))
    render(<MesStatsRelanceTiles />)
    expect(await screen.findByText(/Indisponible pour le moment/)).toBeInTheDocument()
  })
})
