/* ACAL737 — l'histogramme d'écrêtage : l'exemple du contrat rend barres,
   borne et phrase ; étape omise ⇒ motif ; périmée / guidé ⇒ rien. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { resultat: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import HistogrammeEcretage, { HistogrammeEcretageVue } from './HistogrammeEcretage'

const CLE_EXPERT = 'calepinage.mode_expert.anonyme'
const ecretage = () => structuredClone(
  exempleContrat('calepinage', 'calepinage_pertes_cascade', 'exemple_entrees_onduleur').ecretage)
const etape = (entree, extra = {}) => ({ etape: 'ecretage', entree, motif_omission: '', ...extra })

const servir = (modifier) => {
  const data = { simule: true, simulation_perimee: false, cascade: { etapes: [etape(ecretage())] } }
  modifier?.(data)
  calepinageApi.calepinages.resultat.mockResolvedValue({ data })
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })

describe('HistogrammeEcretageVue (ACAL737)', () => {
  it('l\'exemple du contrat : phrase servie, table par classe, « au-dessus de la borne » en mots', () => {
    render(<HistogrammeEcretageVue etape={etape(ecretage())} />)
    expect(screen.getByTestId('acal737-phrase'))
      .toHaveTextContent('9,5 % de l\'énergie des panneaux est perdue : l\'onduleur plafonne à 5 kW')
    const lignes = screen.getAllByRole('row')
    expect(lignes).toHaveLength(5) // en-tête + 4 classes
    expect(within(lignes[1]).getByText(/1 – 1,25 kW/)).toBeInTheDocument()
    expect(lignes[1]).not.toHaveTextContent('au-dessus de la borne')
    expect(lignes[2]).not.toHaveTextContent('au-dessus de la borne') // 4,75 < 5
    expect(lignes[3]).toHaveTextContent('au-dessus de la borne') // de_kw = borne
    expect(lignes[4]).toHaveTextContent('au-dessus de la borne')
    expect(lignes[3]).toHaveTextContent('10,2 kWh')
    expect(screen.getByText(/rendement de conversion n'est pas retiré/)).toBeInTheDocument()
  })

  it('distribution null : le motif servi remplace le graphe ; étape omise : « Écrêtage non calculé »', () => {
    const entree = { ...ecretage(), distribution: null, motif_distribution: 'Aucune production à répartir.' }
    render(<HistogrammeEcretageVue etape={etape(entree)} />)
    expect(screen.getByTestId('acal737-sans-distribution')).toHaveTextContent('Aucune production à répartir.')
    expect(screen.queryByTestId('acal737-histogramme')).toBeNull()
    cleanup()
    render(<HistogrammeEcretageVue etape={etape(null, { motif_omission: 'Puissance AC de l\'onduleur inconnue.' })} />)
    expect(screen.getByTestId('acal737-omise'))
      .toHaveTextContent('Écrêtage non calculé : Puissance AC de l\'onduleur inconnue.')
  })

  it('mutant : une autre clé que part_ecretee_pct ne donne pas 9,5 %', () => {
    const d = ecretage()
    d.distribution.part_ecretee_pct = 12.3
    render(<HistogrammeEcretageVue etape={etape(d)} />)
    expect(screen.getByTestId('acal737-phrase')).toHaveTextContent('12,3 %')
  })
})

describe('HistogrammeEcretage (ACAL737) — monté sur le résultat', () => {
  it('expert + simulé : la carte s\'affiche', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servir()
    render(<HistogrammeEcretage calepinageId={7} />)
    expect(await screen.findByTestId('acal737-carte')).toHaveTextContent('9,5 %')
  })

  it('guidé, périmée ou jamais simulée : rien', async () => {
    servir()
    render(<HistogrammeEcretage calepinageId={7} />)
    expect(screen.queryByTestId('acal737-carte')).toBeNull()
    cleanup()
    localStorage.setItem(CLE_EXPERT, '1')
    servir((d) => { d.simulation_perimee = true })
    render(<HistogrammeEcretage calepinageId={7} />)
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
    expect(screen.queryByTestId('acal737-carte')).toBeNull()
    cleanup()
    servir((d) => { d.simule = false })
    render(<HistogrammeEcretage calepinageId={7} />)
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(2))
    expect(screen.queryByTestId('acal737-carte')).toBeNull()
  })
})
