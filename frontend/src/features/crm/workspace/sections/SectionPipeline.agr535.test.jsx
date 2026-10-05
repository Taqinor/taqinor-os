// AGR535 — « Envoyer le résumé à un associé » (fiche lead). Réponses issues du
// contrat COMMITTÉ `apps/crm/contract_samples/lead_resume_associe.json`
// (PACT10), jamais un objet retapé. Le serveur PRÉPARE le lien ; l'humain
// l'ouvre (window.open au clic) ; l'étiquette n'est posée que sur clic.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { initState } from '../draftCore'
import SectionPipeline from './SectionPipeline'
import { documentContrat } from '../../../../test/fixtures/contractSamples'

vi.mock('../../../../api/crmApi', () => ({
  default: {
    initialiserRelance: vi.fn(),
    arreterCadence: vi.fn(),
    resumeAssocie: vi.fn(),
    getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../../../api/ventesApi', () => ({
  default: {
    getDevis: vi.fn(() => Promise.resolve({
      data: { results: [{ id: 4021, reference: 'DEV-2026-0042', statut: 'envoye' }] },
    })),
  },
}))

import crmApi from '../../../../api/crmApi'

const CONTRAT = documentContrat('crm', 'lead_resume_associe')
const REF_DATA = { users: [], tagOptions: [], motifOptions: [] }

beforeEach(() => {
  vi.spyOn(window, 'open').mockImplementation(() => null)
})
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks() })

function renderSection(over = {}, setField = vi.fn()) {
  const state = initState({
    lead: {
      id: 77, contact_secondaire_nom: 'Karim', contact_secondaire_telephone: '0661223344',
      ...over,
    },
    mode: 'edit',
  })
  render(<SectionPipeline state={state} setField={setField} errors={{}} refData={REF_DATA} />)
  return setField
}

const bouton = () => screen.getByRole('button', { name: 'Envoyer le résumé à un associé' })

describe('SectionPipeline — AGR535 (résumé à l’associé)', () => {
  it('bouton inactif tant que la case d’accord n’est pas cochée', async () => {
    renderSection()
    await screen.findByRole('option', { name: 'DEV-2026-0042' })
    expect(bouton()).toBeDisabled()
    fireEvent.click(screen.getByLabelText('Le client a demandé ou accepté ce partage'))
    expect(bouton()).toBeEnabled()
  })

  it('succès : le corps suit le contrat et wa_url est ouvert au clic', async () => {
    crmApi.resumeAssocie.mockResolvedValue({ data: CONTRAT.exemple })
    renderSection()
    await screen.findByRole('option', { name: 'DEV-2026-0042' })
    fireEvent.click(screen.getByLabelText('Le client a demandé ou accepté ce partage'))
    fireEvent.click(bouton())
    await waitFor(() => expect(window.open).toHaveBeenCalled())
    expect(window.open.mock.calls[0][0]).toBe(CONTRAT.exemple.wa_url)
    const [id, corps] = crmApi.resumeAssocie.mock.calls[0]
    expect(id).toBe(77)
    expect(Object.keys(corps).every((k) => k in CONTRAT.corps)).toBe(true)
    expect(corps).toMatchObject({ devis_id: 4021, accord_client: true })
  })

  it('400 : le message s’affiche sous le champ nommé, rien n’est ouvert', async () => {
    crmApi.resumeAssocie.mockRejectedValue({
      response: { status: 400, data: CONTRAT.exemple_400_telephone },
    })
    renderSection()
    await screen.findByRole('option', { name: 'DEV-2026-0042' })
    fireEvent.click(screen.getByLabelText('Le client a demandé ou accepté ce partage'))
    fireEvent.click(bouton())
    expect(await screen.findByText(
      CONTRAT.exemple_400_telephone.contact_secondaire_telephone[0])).toBeInTheDocument()
    expect(window.open).not.toHaveBeenCalled()
  })

  it('400 devis_id : message sous le champ « Devis »', async () => {
    crmApi.resumeAssocie.mockRejectedValue({
      response: { status: 400, data: CONTRAT.exemple_400_devis },
    })
    renderSection()
    await screen.findByRole('option', { name: 'DEV-2026-0042' })
    fireEvent.click(screen.getByLabelText('Le client a demandé ou accepté ce partage'))
    fireEvent.click(bouton())
    expect(await screen.findByText(CONTRAT.exemple_400_devis.devis_id[0])).toBeInTheDocument()
  })

  it('suggestion d’étiquette : rien n’est écrit sans clic, puis la pose', () => {
    const setField = renderSection({ type_installation: 'agricole', tags: '' })
    expect(setField).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /Ajouter l’étiquette « Décision à plusieurs »/ }))
    expect(setField).toHaveBeenCalledWith('tags', 'Décision à plusieurs')
  })

  it('pas de suggestion si l’étiquette est déjà là, ou hors agricole', () => {
    renderSection({ type_installation: 'agricole', tags: 'VIP, Decision a plusieurs' })
    expect(screen.queryByTestId('suggestion-tag-decision')).not.toBeInTheDocument()
    cleanup()
    renderSection({ type_installation: 'residentiel', tags: '' })
    expect(screen.queryByTestId('suggestion-tag-decision')).not.toBeInTheDocument()
  })
})
