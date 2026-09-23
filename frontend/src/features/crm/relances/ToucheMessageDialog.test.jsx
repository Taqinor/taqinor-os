import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* Lane CAD-ROW3 — la modale d'aperçu du message d'une touche (canaux,
   langues, messages). Charges utiles = les exemples COMMITTÉS
   `apps/crm/contract_samples/relance_etape_message.json` (le rendu) et
   `relance_etape_v2.json` (la touche) — jamais un objet retapé à la main
   (PACT10). */
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const TOUCHES = exempleContrat('crm', 'relance_etape_v2').results
// La touche WhatsApp du contrat (lead en français).
const ETAPE = TOUCHES.find((t) => t.canal === 'whatsapp')
const MESSAGE = exempleContrat('crm', 'relance_etape_message')
const MESSAGE_DARIJA = exempleContrat('crm', 'relance_etape_message', 'exemple_darija')

vi.mock('../../../api/crmApi', () => ({
  default: {
    getRelanceEtapeMessage: vi.fn(),
    getRelanceEtapeMessageLangue: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    whatsappRelanceEtapeLangue: vi.fn(),
    definirLangueRelanceEtape: vi.fn(),
  },
}))

import crmApi from '../../../api/crmApi'
import ToucheMessageDialog from './ToucheMessageDialog'

beforeEach(() => {
  crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE })
  crmApi.getRelanceEtapeMessageLangue.mockResolvedValue({ data: MESSAGE_DARIJA })
  crmApi.whatsappRelanceEtape.mockResolvedValue({ data: { ...MESSAGE, etape: ETAPE } })
  crmApi.whatsappRelanceEtapeLangue.mockResolvedValue({ data: { ...MESSAGE_DARIJA, etape: ETAPE } })
  crmApi.definirLangueRelanceEtape.mockResolvedValue({ data: { ...ETAPE, lead_langue: 'darija' } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CAD63 — changer la langue au moment utile', () => {
  it('le basculeur recharge le texte dans l’autre langue, sans toucher la fiche', async () => {
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    expect(await screen.findByText(MESSAGE.message)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'FR' })).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByRole('button', { name: 'Darija' }))
    await waitFor(() => expect(crmApi.getRelanceEtapeMessageLangue)
      .toHaveBeenCalledWith(ETAPE.id, { cle: undefined, langue: 'darija' }))
    expect(await screen.findByText(MESSAGE_DARIJA.message)).toBeInTheDocument()
    // Basculer l'aperçu n'enregistre rien : seule la confirmation le fait.
    expect(crmApi.definirLangueRelanceEtape).not.toHaveBeenCalled()
  })

  it('« C’est sa langue » enregistre la darija sur la fiche (confirmation explicite)', async () => {
    const onLangueEnregistree = vi.fn()
    render(
      <ToucheMessageDialog
        etape={ETAPE} open onOpenChange={() => {}} onLangueEnregistree={onLangueEnregistree}
      />,
    )
    await screen.findByText(MESSAGE.message)
    // Aucune proposition tant que la langue affichée est celle de la fiche.
    expect(screen.queryByTestId('enregistrer-langue-client')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Darija' }))
    await screen.findByText(MESSAGE_DARIJA.message)
    fireEvent.click(screen.getByTestId('enregistrer-langue-client'))
    await waitFor(() => expect(crmApi.definirLangueRelanceEtape)
      .toHaveBeenCalledWith(ETAPE.id, 'darija'))
    await waitFor(() => expect(onLangueEnregistree).toHaveBeenCalledWith(ETAPE.id, 'darija'))
  })

  it('« Ouvrir WhatsApp » après bascule : le serveur vérifie le rendu dans la langue choisie', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(MESSAGE.message)
    fireEvent.click(screen.getByRole('button', { name: 'Darija' }))
    await screen.findByText(MESSAGE_DARIJA.message)
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(openSpy).toHaveBeenCalledWith(MESSAGE_DARIJA.wa_url, '_blank', 'noopener')
    await waitFor(() => expect(crmApi.whatsappRelanceEtapeLangue)
      .toHaveBeenCalledWith(ETAPE.id, 'darija'))
    expect(crmApi.whatsappRelanceEtape).not.toHaveBeenCalled()
    openSpy.mockRestore()
  })
})
