// CIQ324 — le dialogue « Signé » d'un lead : trois champs FACULTATIFS
// d'identité d'entreprise pour un devis commercial / industriel, corps du
// contrat partagé `acceptation_entreprise.json` ; résidentiel inchangé.
//
// Run : npx vitest run src/pages/crm/leads/SigneDialogEntreprise.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getDevis: vi.fn(),
      accepterDevis: vi.fn(() => Promise.resolve({ data: {} })),
    },
  }
})

import SigneDialog from './SigneDialog'
import ventesApi from '../../../api/ventesApi'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const ERP = exempleContrat('ventes', 'acceptation_entreprise', 'exemple_erp').corps

const devis = (mode) => ({
  id: 77, reference: 'DEV-SIGNE-77', statut: 'envoye', total_ttc: 90000, nb_options: 1,
  date_creation: '2026-09-01', mode_installation: mode,
})

async function ouvrir(mode) {
  ventesApi.getDevis.mockResolvedValue({ data: { results: [devis(mode)] } })
  ventesApi.accepterDevis.mockClear()
  render(<SigneDialog lead={{ id: 5, nom: 'Exemple', prenom: 'Karim' }}
                      onClose={() => {}} onConfirmed={() => {}} />)
  await screen.findByLabelText('Devis accepté')
}

const confirmer = () => fireEvent.click(screen.getByRole('button', { name: /Confirmer|Marquer|Passer/ }))

describe('SigneDialog — CIQ324 identité d\'entreprise', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('industriel : trois champs, corps avec le bloc `entreprise`', async () => {
    await ouvrir('industriel')
    fireEvent.change(screen.getByLabelText('Raison sociale'),
      { target: { value: ERP.entreprise.raison_sociale } })
    fireEvent.change(screen.getByLabelText('Qualité du signataire'),
      { target: { value: 'Directeur général' } })
    fireEvent.change(screen.getByLabelText('ICE'), { target: { value: '000000000000000' } })
    confirmer()
    await waitFor(() => expect(ventesApi.accepterDevis).toHaveBeenCalledTimes(1))
    const [id, corps] = ventesApi.accepterDevis.mock.calls[0]
    expect(id).toBe(77)
    expect(corps.entreprise).toEqual({
      raison_sociale: ERP.entreprise.raison_sociale,
      signataire_qualite: 'Directeur général',
      ice: '000000000000000',
    })
    expect(Object.keys(corps.entreprise).sort()).toEqual(Object.keys(ERP.entreprise).sort())
  })

  it('résidentiel : aucun champ d\'entreprise, corps {nom, date, option}', async () => {
    await ouvrir('residentiel')
    expect(screen.queryByTestId('identite-entreprise')).toBeNull()
    confirmer()
    await waitFor(() => expect(ventesApi.accepterDevis).toHaveBeenCalledTimes(1))
    expect(Object.keys(ventesApi.accepterDevis.mock.calls[0][1]).sort())
      .toEqual(['date', 'nom', 'option'])
  })
})
