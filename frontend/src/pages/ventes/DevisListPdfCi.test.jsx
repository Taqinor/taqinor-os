/* CIQ325 — le dialogue PDF annonce le VRAI document C&I.

   Commercial : 3 pages ; industriel : 4 pages (D-QJR5-12). En C&I, plus de
   pré-coche « Inclure l'étude » (elle envoyait le rendu au moteur legacy alors
   que le lien du client reçoit le premium), plus de case « Inclure l'étude » ni
   « Économies mensuelles » (aucun gabarit C&I ne la lit : l'étude est intégrée).
   Résidentiel et agricole inchangés.

   Run : npx vitest run src/pages/ventes/DevisListPdfCi.test.jsx
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
import { libelleFormatComplet } from './devisList/devisListHelpers.js'

const LIGNES = [{ id: 3, designation: 'Onduleur réseau 100kW', quantite: '1', prix_unitaire: '240000' }]
const base = (id, mode, extra = {}) => ({
  id, reference: `DEV-CIQ325-${id}`, client_nom: 'Client', statut: 'brouillon',
  date_creation: '2026-10-05', total_ttc: 500000, nb_options: 1, version: 1,
  mode_installation: mode, lignes: LIGNES, ...extra,
})
// Un devis industriel DISPOSANT de données d'étude : c'est exactement le cas où
// l'ancienne pré-coche s'activait.
const INDUSTRIEL = base(1, 'industriel', { etude_params: { mode: 'industriel', tension: 'mt' } })
const COMMERCIAL = base(2, 'commercial', { etude_params: { mode: 'commercial' } })
const RESIDENTIEL = base(3, 'residentiel')

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

describe('CIQ325 — dialogue PDF d\'un devis C&I', () => {
  it('industriel : « 4 pages », et aucune case cochée qui change de moteur', async () => {
    const dialog = await ouvrirDialogue(INDUSTRIEL)
    expect(within(dialog).getByText(
      'Document industriel (4 pages — synthèse, équipements, rentabilité, conditions et signature)',
    )).toBeInTheDocument()
    expect(within(dialog).queryByText(/Devis premium \(3 pages/)).toBeNull()
    expect(within(dialog).queryByText(/Inclure l'étude/)).toBeNull()
    expect(within(dialog).queryByText(/Économies mensuelles/)).toBeNull()
    for (const case_ of within(dialog).queryAllByRole('checkbox')) {
      expect(case_).not.toBeChecked()
    }
  })

  it('commercial : « 3 pages », sans case étude ni économies mensuelles', async () => {
    const dialog = await ouvrirDialogue(COMMERCIAL)
    expect(within(dialog).getByText(
      'Document commercial (3 pages — votre installation, l\'investissement et son retour, conditions et signature)',
    )).toBeInTheDocument()
    expect(within(dialog).queryByText(/Inclure l'étude/)).toBeNull()
    expect(within(dialog).queryByText(/Économies mensuelles/)).toBeNull()
  })

  it('résidentiel : inchangé (libellé premium, case étude et économies mensuelles)', async () => {
    const dialog = await ouvrirDialogue(RESIDENTIEL)
    expect(within(dialog).getByText(
      'Devis premium (3 pages — options, analyse, garanties)',
    )).toBeInTheDocument()
    expect(within(dialog).getByText(/Inclure l'étude/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Économies mensuelles/)).toBeInTheDocument()
  })

  it('libellé du format complet : un libellé par marché', () => {
    expect(libelleFormatComplet({ targetIsAgricole: true, targetMode: 'agricole' }))
      .toMatch(/Document agricole complet \(3 pages/)
    expect(libelleFormatComplet({ targetIsAgricole: false, targetMode: 'industriel' })).toMatch(/4 pages/)
    expect(libelleFormatComplet({ targetIsAgricole: false, targetMode: 'commercial' })).toMatch(/3 pages/)
    expect(libelleFormatComplet({ targetIsAgricole: false, targetMode: 'residentiel' }))
      .toMatch(/Devis premium \(3 pages/)
  })
})
