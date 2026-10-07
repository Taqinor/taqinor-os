/* ACAL105 (D-ACAL-6) — le bandeau de provenance affiche la production du
   DEVIS (imprimée au client) et l'écart au P50 de l'étude, tels que servis par
   `GET resultat/` (`ecart_devis`, ACAL104). Aucune charge utile écrite à la
   main : l'échantillon vient du contrat partagé
   `apps/calepinage/contract_samples/calepinage_resultat.json` (PACT10). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { resultat: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import BandeauProvenanceProduction from './BandeauProvenanceProduction'

// Charge du contrat partagé (variante nommée), servie par le mock d'API,
// puis bandeau rendu sous un routeur mémoire.
function afficherAvec(variante) {
  calepinageApi.calepinages.resultat.mockResolvedValue(
    reponseContrat('calepinage', 'calepinage_resultat', variante))
  return render(
    <MemoryRouter><BandeauProvenanceProduction calepinageId={1} /></MemoryRouter>)
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BandeauProvenanceProduction — écart devis (ACAL105)', () => {
  it('affiche la production du devis et l’écart', async () => {
    afficherAvec('exemple_ecart_devis')

    const ecart = await screen.findByTestId('acal-ecart-devis')
    // `production_devis_kwh` 12600 et `ecart_pct` 3.2 de l'échantillon,
    // affichés tels quels (formatNumber met une espace fine dans « 12 600 »).
    expect(ecart).toHaveTextContent(/Devis : 12.600 kWh\/an/)
    expect(ecart).toHaveTextContent('(production imprimée au client)')
    expect(ecart).toHaveTextContent('écart +3,2 %')
  })

  it('rien sans ecart_devis', async () => {
    afficherAvec('exemple')

    await screen.findByTestId('calx65-simulation')
    expect(screen.queryByTestId('acal-ecart-devis')).toBeNull()
  })
})
