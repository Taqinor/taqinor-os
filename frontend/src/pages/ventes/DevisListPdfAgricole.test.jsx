/* AGR315 — le dialogue PDF annonce le VRAI document agricole.

   Le serveur rend désormais un devis agricole en document complet de 3 pages
   (renderer agricole, AGR312) et la version courte d'une page sur demande.
   Le libellé « Devis premium (4 pages — étude, schéma, rentabilité,
   garanties) » mentait depuis DV1 : il disparaît. Un devis résidentiel garde
   ses libellés. Aucune case du dialogue ne pilote une aide ou un montant.
*/
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, cleanup, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) =>
  (await import('../../test/fixtures/devisListMocks.js')).ventesSliceMock(await importOriginal()))

vi.mock('../../api/ventesApi', async (importOriginal) =>
  (await import('../../test/fixtures/devisListMocks.js')).ventesApiPdfMock(await importOriginal(), 1))

vi.mock('../../api/crmApi', async (importOriginal) =>
  (await import('../../test/fixtures/devisListMocks.js')).crmApiMock(await importOriginal()))

vi.mock('../../api/uxviewsApi', async () => (await import('../../test/fixtures/devisListMocks.js')).uxviewsApiMock())

import DevisList from './DevisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const AGRICOLE = {
  id: 315, reference: 'DEV-AGR315', client_nom: 'Ferme Ali', statut: 'brouillon',
  date_creation: '2026-10-05', total_ttc: 50000, nb_options: 1, version: 1,
  mode_installation: 'agricole',
  // Un kit de pompage n'a pas d'onduleur : le format ne doit pas être
  // rabattu sur une page pour autant.
  lignes: [
    { id: 1, designation: 'Pompe immergée OSP 30/8 10 CV', quantite: '1', prix_unitaire: '15000' },
    { id: 2, designation: 'Variateur VEICHI 7,5 kW', quantite: '1', prix_unitaire: '6000' },
  ],
}
const RESIDENTIEL = {
  id: 316, reference: 'DEV-RES315', client_nom: 'Villa Sami', statut: 'brouillon',
  date_creation: '2026-10-05', total_ttc: 90000, nb_options: 1, version: 1,
  mode_installation: 'residentiel',
  lignes: [{ id: 3, designation: 'Onduleur hybride 5kW', quantite: '1', prix_unitaire: '24000' }],
}

async function ouvrirDialogue(devis) {
  const store = configureStore({
    reducer: {
      ventes: (state = { devis: [devis], loading: false, error: null }) => state,
      auth: (state = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => state,
    },
  })
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis']}>
        <ThemeProvider><DevisList /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
  const ligne = screen.getByText(devis.reference).closest('tr')
  fireEvent.click(within(ligne).getByTitle('Générer le PDF (choix du format)'))
  return screen.findByRole('dialog')
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AGR315 — dialogue PDF d’un devis agricole', () => {
  it('annonce le document complet de 3 pages, plus jamais « 4 pages »', async () => {
    const dialog = await ouvrirDialogue(AGRICOLE)
    expect(within(dialog).queryByText(/4 pages/)).toBeNull()
    expect(within(dialog).getByText(
      'Document agricole complet (3 pages — eau et argent, fonctionnement, équipement et signature)',
    )).toBeInTheDocument()
    expect(within(dialog).getByText('Version courte (1 page)')).toBeInTheDocument()
  })

  it('le format complet est présélectionné (pas de rabattement faute d’onduleur)', async () => {
    const dialog = await ouvrirDialogue(AGRICOLE)
    const radios = within(dialog).getAllByRole('radio')
    expect(radios[0]).toHaveAttribute('aria-checked', 'true')
    expect(within(dialog).queryByText(/Options non détectées/)).toBeNull()
  })

  it('aucune case ne pilote une aide ou un montant', async () => {
    const dialog = await ouvrirDialogue(AGRICOLE)
    expect(within(dialog).queryByText(/FDA|subvention|aide/i)).toBeNull()
  })

  it('un devis résidentiel garde ses libellés', async () => {
    const dialog = await ouvrirDialogue(RESIDENTIEL)
    expect(within(dialog).getByText(
      'Devis premium (3 pages — options, analyse, garanties)',
    )).toBeInTheDocument()
    expect(within(dialog).getByText(
      'Devis une page (liste produits uniquement, sans graphiques)',
    )).toBeInTheDocument()
    expect(within(dialog).queryByText(/Document agricole/)).toBeNull()
  })
})
