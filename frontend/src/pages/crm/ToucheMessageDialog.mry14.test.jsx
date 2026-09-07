import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* MRY14/MRY13 — modale d'aperçu du message d'une touche AVANT ouverture de
   WhatsApp (décision D5 : aucun envoi automatique, le clic humain reste seul
   maître). Charge utile issue du contrat committé
   `apps/crm/contract_samples/relance_etape_message.json` (PACT10). */
import { exempleContrat } from '../../test/fixtures/contractSamples'

const MESSAGE = exempleContrat('crm', 'relance_etape_message')
const MESSAGE_OMISE = exempleContrat('crm', 'relance_etape_message', 'exemple_phrase_omise')
const MESSAGE_INVALIDE = exempleContrat('crm', 'relance_etape_message', 'exemple_numero_invalide')

const ETAPE = { id: 412, lead: 1489, lead_nom: 'Aziz Benali' }

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import ToucheMessageDialog from './ToucheMessageDialog'

beforeEach(() => {
  crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE })
  crmApi.whatsappRelanceEtape.mockResolvedValue({
    data: { ...MESSAGE, etape: { ...ETAPE, statut: 'fait' } },
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('MRY14 ToucheMessageDialog', () => {
  it('charge et affiche le message rendu au montage', async () => {
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await waitFor(() => expect(crmApi.getRelanceEtapeMessage).toHaveBeenCalledWith(ETAPE.id))
    expect(await screen.findByText(MESSAGE.message)).toBeInTheDocument()
  })

  it('« Ouvrir WhatsApp » ouvre le lien PUIS marque la touche côté serveur', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    const onSent = vi.fn()
    const onOpenChange = vi.fn()
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={onOpenChange} onSent={onSent} />)
    await screen.findByText(MESSAGE.message)
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(openSpy).toHaveBeenCalledWith(MESSAGE.wa_url, '_blank', 'noopener')
    await waitFor(() => expect(crmApi.whatsappRelanceEtape).toHaveBeenCalledWith(ETAPE.id))
    await waitFor(() => expect(onSent).toHaveBeenCalledWith(ETAPE.id, expect.any(Object)))
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    openSpy.mockRestore()
  })

  it('affiche l\'avertissement quand une phrase a été omise (placeholder manquant)', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE_OMISE })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    expect(await screen.findByText(MESSAGE_OMISE.message)).toBeInTheDocument()
    expect(screen.getByText(/date_validite/)).toBeInTheDocument()
  })

  it('numéro inexploitable : bouton « Ouvrir WhatsApp » désactivé', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE_INVALIDE })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(MESSAGE_INVALIDE.message)
    expect(screen.getByRole('button', { name: /Ouvrir WhatsApp/ })).toBeDisabled()
    expect(screen.getByText(/Aucun numéro exploitable/)).toBeInTheDocument()
  })

  it('un message en darija se lit de droite à gauche (dir="rtl")', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: { ...MESSAGE, langue: 'darija' } })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    const bloc = await screen.findByText(MESSAGE.message)
    expect(bloc).toHaveAttribute('dir', 'rtl')
    expect(bloc).toHaveAttribute('lang', 'ar')
  })

  it('un message en français garde le sens de lecture automatique', async () => {
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    const bloc = await screen.findByText(MESSAGE.message)
    expect(bloc).toHaveAttribute('dir', 'auto')
  })

  it('ne charge rien quand fermé', () => {
    render(<ToucheMessageDialog etape={ETAPE} open={false} onOpenChange={() => {}} />)
    expect(crmApi.getRelanceEtapeMessage).not.toHaveBeenCalled()
  })
})
