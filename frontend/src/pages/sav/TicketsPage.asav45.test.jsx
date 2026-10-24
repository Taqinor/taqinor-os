import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import CONTRAT from '../../../../backend/django_core/apps/sav/contract_samples/ticket_detail.json'

// ASAV45 — bandeau et sélecteur lisent la garantie EFFECTIVE servie par le
// serveur (contrat ticket_detail.json), sans recalcul local sur la date
// constructeur.

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__tests__/ticketDetailMocks.js')).ticketsSliceMock(await io()))
vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailMocks.js')).savApiMock())
vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailMocks.js')).axiosMock())
vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore } from './__tests__/ticketDetailMocks.js'

beforeEach(() => { vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(new Date('2026-10-09T10:00:00')) })
afterEach(() => { cleanup(); vi.useRealTimers() })

function renderDetail(ticket) {
  return render(<Provider store={ticketStore('responsable')}><MemoryRouter>
    <TicketDetail ticket={{ ...CONTRAT.exemple, type: 'correctif', description: '',
      sous_garantie: 'a_determiner', couverture: 'a_determiner', devis_id_ext: null,
      facture_id_ext: null, instructions: '', ...ticket }}
      onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

describe('TicketDetail — ASAV45 garantie effective servie', () => {
  it('a : constructeur absent, légale servie → sélecteur « Oui » et bandeau légal', async () => {
    renderDetail({ equipement_fin_garantie: null,
      equipement_fin_garantie_effective: '2027-02-10', sous_garantie_effectif: 'oui' })
    expect((await screen.findAllByText(/Garantie jusqu'au 10\/02\/2027 \(légale\)/)).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('combobox').some((c) => c.textContent === 'Oui')).toBe(true)
  })

  it('b : constructeur expiré mais légale en cours → pas de « Garantie expirée »', async () => {
    renderDetail({ equipement_fin_garantie: '2026-08-09',
      equipement_fin_garantie_effective: '2026-12-12', sous_garantie_effectif: 'oui' })
    expect((await screen.findAllByText(/Garantie jusqu'au 12\/12\/2026 \(légale\)/)).length).toBeGreaterThan(0)
    expect(screen.queryByText(/Garantie expirée/)).toBeNull()
    expect(screen.getAllByRole('combobox').some((c) => c.textContent === 'Oui')).toBe(true)
  })
})

describe('TicketDetail — ASAV110 mise en attente client réservée aux tickets ouverts', () => {
  const MISE_EN_ATTENTE = { name: /Mettre en attente client/ }
  const REPRISE = { name: /Reprendre après attente client/ }

  it('un ticket résolu n\'offre aucun bouton « Mettre en attente client »', async () => {
    renderDetail({ statut: 'resolu', en_attente_client: false })
    await screen.findByText('Suivi client & SLA')
    expect(screen.queryByRole('button', MISE_EN_ATTENTE)).toBeNull()
    expect(screen.queryByRole('button', REPRISE)).toBeNull()
  })

  it('un ticket annulé n\'offre aucun bouton « Mettre en attente client »', async () => {
    renderDetail({ statut: 'en_cours', annule: true, en_attente_client: false })
    await screen.findByText('Suivi client & SLA')
    expect(screen.queryByRole('button', MISE_EN_ATTENTE)).toBeNull()
  })

  it('un ticket en cours offre le bouton « Mettre en attente client »', async () => {
    renderDetail({ statut: 'en_cours', annule: false, en_attente_client: false })
    expect(await screen.findByRole('button', MISE_EN_ATTENTE)).not.toBeNull()
    expect(screen.queryByRole('button', REPRISE)).toBeNull()
  })

  it('un ticket encore en pause garde « Reprendre après attente client »', async () => {
    renderDetail({ statut: 'resolu', en_attente_client: true, attente_depuis: '2026-10-06' })
    expect(await screen.findByRole('button', REPRISE)).not.toBeNull()
    expect(screen.queryByRole('button', MISE_EN_ATTENTE)).toBeNull()
  })
})

describe('TicketDetail — ASAV111 bandeau de garantie = verdict servi', () => {
  it('c : horloge du navigateur au 01/01/2028, verdict servi « oui » → « Garantie jusqu\'au », jamais expirée', async () => {
    vi.setSystemTime(new Date('2028-01-01T10:00:00'))
    renderDetail({ equipement_fin_garantie: '2026-04-02',
      equipement_fin_garantie_effective: '2027-02-10', sous_garantie_effectif: 'oui' })
    const [bandeau] = await screen.findAllByText(/Garantie jusqu'au 10\/02\/2027 \(légale\)/)
    // Le texte du bandeau est le verdict seul : aucun compte de jours.
    expect(bandeau.textContent).toBe('Garantie jusqu\'au 10/02/2027 (légale)')
    expect(screen.queryByText(/Garantie expirée/)).toBeNull()
  })

  it('d : verdict servi « non » → « Garantie expirée le », sans compte de jours', async () => {
    renderDetail({ equipement_fin_garantie: '2026-04-02',
      equipement_fin_garantie_effective: '2026-12-12', sous_garantie_effectif: 'non' })
    const [bandeau] = await screen.findAllByText(/Garantie expirée le 12\/12\/2026 \(légale\)/)
    expect(bandeau.textContent).toBe('Garantie expirée le 12/12/2026 (légale)')
    expect(screen.queryByText(/Garantie jusqu'au/)).toBeNull()
  })
})
