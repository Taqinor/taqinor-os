// ERR-QAH-VENTES-ENVOYE-FAUX-STATUT — le dialogue « Envoyer par WhatsApp » ne
// prétend jamais un changement de statut qui n'a pas eu lieu.
//
// Réalité serveur (apps/ventes/views/devis.py) : `whatsapp-preview` est une
// LECTURE (aucun `mark_devis_sent`, réponse `devis_statut: "brouillon"`) ; seul
// le clic « Ouvrir WhatsApp » appelle l'action `whatsapp`, qui marque le devis
// « Envoyé ». Observé (qa-explorer 2026-09-28) : après le seul aperçu, le
// dialogue affirmait « Le devis est marqué « Envoyé » » et l'info-bulle du
// bouton « marque le devis « Envoyé » ».
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../lib/monitoring.js', () => ({
  sentryDsn: () => '', isMonitoringEnabled: () => false,
  initMonitoring: async () => {}, bindCompany: () => {},
  suivreSocieteDuStore: () => {}, captureException: async () => {},
}))

vi.mock('./store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }),
  }
})

vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getVariantes: vi.fn(() => Promise.resolve({ data: [] })),
      historiqueDevis: vi.fn(() => Promise.resolve({ data: [] })),
      whatsappPreviewDevis: vi.fn(() => Promise.resolve({
        data: {
          wa_url: 'https://wa.me/212600000000', message: 'Bonjour',
          devis_statut: 'brouillon', preview: true,
        },
      })),
      whatsappDevis: vi.fn(() => Promise.resolve({ data: { statut: 'envoye' } })),
    },
  }
})

vi.mock('../../api/uxviewsApi', async () => (await import('../../test/mocksVentesEcrans.js')).uxviewsApiVide())

import DevisList from '../../pages/ventes/DevisList'
import ventesApi from '../../api/ventesApi'
import { renderList } from '../../pages/ventes/devisListTestHelpers.jsx'

const brouillon = () => ([{
  id: 31, reference: 'DEV-QAH-ENV', client_nom: 'Alaoui', statut: 'brouillon',
  date_creation: '2026-09-28', total_ttc: 60000, nb_options: 1, version: 1,
}])

describe('DevisList — ERR-QAH-VENTES-ENVOYE-FAUX-STATUT', () => {
  let openSpy
  beforeEach(() => {
    ventesApi.whatsappDevis.mockClear()
    openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
  })
  afterEach(() => { openSpy.mockRestore() })

  it('après le seul aperçu, le dialogue ne dit pas que le devis est « Envoyé »', async () => {
    const user = userEvent.setup()
    renderList(brouillon())
    const row = screen.getByText('DEV-QAH-ENV').closest('tr')
    const bouton = within(row).getByRole('button', { name: /^Envoyer$/ })
    // L'info-bulle décrit ce qui se passe VRAIMENT (au clic « Ouvrir WhatsApp »).
    expect(bouton.getAttribute('title')).not.toMatch(/—\s*marque le devis/)
    expect(bouton.getAttribute('title')).toMatch(/ouvr/i)
    await user.click(bouton)
    await screen.findByRole('button', { name: /Ouvrir WhatsApp/ })
    expect(ventesApi.whatsappPreviewDevis).toHaveBeenCalledWith(31)
    expect(ventesApi.whatsappDevis).not.toHaveBeenCalled()
    // Observé avant le correctif : « Le devis est marqué « Envoyé ». … »
    expect(screen.queryByText(/est marqué « Envoyé »/)).toBeNull()
    expect(screen.getByText(/passera « Envoyé » quand vous ouvrirez WhatsApp/)).toBeTruthy()
  })
})
