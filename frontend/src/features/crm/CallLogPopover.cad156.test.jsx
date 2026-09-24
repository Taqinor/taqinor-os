import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* CAD156 — « Je vous rappelle jeudi à 18 h » : l'heure promise au journal
   d'appel voyage AVEC la date (même PATCH, `relance_heure`) et le serveur
   reporte la touche à cette heure (chemin du report de touche). Corps et
   refus = le contrat COMMITTÉ `apps/crm/contract_samples/lead_relance_heure.json`
   (PACT10) — jamais un objet retapé. */
import { documentContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', () => ({
  default: {
    logInteraction: vi.fn(() => Promise.resolve({ data: {} })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../lib/toast', () => ({ toastSuccess: vi.fn(), toastError: vi.fn() }))

import crmApi from '../../api/crmApi'
import { toastError } from '../../lib/toast'
import CallLogPopover from './CallLogPopover'

const CONTRAT = documentContrat('crm', 'lead_relance_heure')

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CAD156 — l’heure promise a un champ, et atteint la touche', () => {
  it('l’heure saisie part AVEC la date, dans le corps du contrat', async () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    fireEvent.click(screen.getByText('À rappeler'))
    // Pas de date → pas de champ heure (une heure seule n'a pas de sens).
    expect(screen.queryByLabelText('Heure promise (facultative)')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Demain'))
    fireEvent.change(screen.getByLabelText('Heure promise (facultative)'),
      { target: { value: CONTRAT.corps.relance_heure } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalled())
    const [lead, corps] = crmApi.updateLead.mock.calls[0]
    expect(lead).toBe(42)
    expect(Object.keys(corps).sort()).toEqual(Object.keys(CONTRAT.corps).sort())
    expect(corps.relance_heure).toBe(CONTRAT.corps.relance_heure)
  })

  it('sans heure, le corps historique est inchangé (date seule)', async () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    fireEvent.click(screen.getByText('À rappeler'))
    fireEvent.click(screen.getByText('Demain'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalled())
    expect(Object.keys(crmApi.updateLead.mock.calls[0][1])).toEqual(['relance_date'])
  })

  it('un refus du serveur sur l’heure s’affiche SOUS le champ, jamais un toast générique', async () => {
    crmApi.updateLead.mockRejectedValueOnce(
      { response: { status: 400, data: CONTRAT.exemple_erreur_heure } })
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} mode="planification" />)
    fireEvent.click(screen.getByText('Demain'))
    fireEvent.change(screen.getByLabelText('Heure promise (facultative)'),
      { target: { value: '18:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByTestId('clp-erreur-heure'))
      .toHaveTextContent(CONTRAT.exemple_erreur_heure.relance_heure[0])
    expect(toastError).not.toHaveBeenCalled()
  })
})
