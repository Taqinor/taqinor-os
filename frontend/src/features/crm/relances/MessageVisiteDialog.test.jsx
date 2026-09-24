import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* CAD111 — le message qui propose la visite laisse une TRACE et son lien wa.me
   est construit par le SERVEUR (E.164). Charges utiles = les exemples
   COMMITTÉS `apps/crm/contract_samples/lead_message_visite.json` (le rendu,
   liens compris) et `lead_message_visite_ouvert.json` (la trace) — jamais un
   objet retapé à la main (PACT10). */
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const RENDU = exempleContrat('crm', 'lead_message_visite')
const RENDU_MASQUE = exempleContrat('crm', 'lead_message_visite', 'exemple_numero_masque')
const TRACE = exempleContrat('crm', 'lead_message_visite_ouvert')

vi.mock('../../../lib/toast', () => ({ toastSuccess: vi.fn() }))
vi.mock('../../../api/crmApi', () => ({
  default: {
    getMessageVisite: vi.fn(),
    journaliserMessageVisiteOuvert: vi.fn(),
  },
}))

import crmApi from '../../../api/crmApi'
import MessageVisiteDialog from './MessageVisiteDialog'

const LEAD = 1490

beforeEach(() => {
  crmApi.getMessageVisite.mockResolvedValue({ data: RENDU })
  crmApi.journaliserMessageVisiteOuvert.mockResolvedValue({ data: TRACE })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CAD111 — message de visite : trace + lien serveur', () => {
  it('l’ouverture écrit une trace au chatter, rattachée à la touche, APRÈS window.open', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    const onOpenChange = vi.fn()
    render(
      <MessageVisiteDialog leadId={LEAD} etapeId={TRACE.etape} open onOpenChange={onOpenChange} />,
    )
    await screen.findByText(RENDU.corps_fr)
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(openSpy).toHaveBeenCalledWith(RENDU.wa_url_fr, '_blank', 'noopener')
    await waitFor(() => expect(crmApi.journaliserMessageVisiteOuvert).toHaveBeenCalledWith(
      LEAD, { cle: 'visite_proposition', langue: 'fr', etape: TRACE.etape }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    openSpy.mockRestore()
  })

  it('le lien ouvert est celui du SERVEUR, en E.164 (jamais un « 06… » brut)', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    render(<MessageVisiteDialog leadId={LEAD} open onOpenChange={() => {}} />)
    await screen.findByText(RENDU.corps_fr)
    fireEvent.click(screen.getByRole('button', { name: 'Darija' }))
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    const url = openSpy.mock.calls[0][0]
    expect(url).toBe(RENDU.wa_url_darija)
    expect(url.startsWith('https://wa.me/212')).toBe(true)
    // Sans touche : la trace part sans `etape`, dans la langue ouverte.
    await waitFor(() => expect(crmApi.journaliserMessageVisiteOuvert).toHaveBeenCalledWith(
      LEAD, { cle: 'visite_proposition', langue: 'darija' }))
    openSpy.mockRestore()
  })

  it('un échec de la trace ne bloque jamais (WhatsApp est déjà ouvert)', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    crmApi.journaliserMessageVisiteOuvert.mockRejectedValue(new Error('réseau'))
    const onOpenChange = vi.fn()
    render(<MessageVisiteDialog leadId={LEAD} open onOpenChange={onOpenChange} />)
    await screen.findByText(RENDU.corps_fr)
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    await waitFor(() => expect(crmApi.journaliserMessageVisiteOuvert).toHaveBeenCalled())
    openSpy.mockRestore()
  })

  it('aucun numéro servi (absent ou masqué par les droits) : CTA désactivé', async () => {
    crmApi.getMessageVisite.mockResolvedValue({ data: RENDU_MASQUE })
    render(<MessageVisiteDialog leadId={LEAD} open onOpenChange={() => {}} />)
    await screen.findByText(RENDU_MASQUE.corps_fr)
    expect(screen.getByRole('button', { name: /Ouvrir WhatsApp/ })).toBeDisabled()
    expect(screen.getByText(/Aucun numéro WhatsApp exploitable/)).toBeInTheDocument()
  })
})
