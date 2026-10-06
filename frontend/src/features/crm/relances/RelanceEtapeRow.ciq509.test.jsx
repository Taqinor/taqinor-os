// CIQ509 — « En attente d'un accord » : choisir la RAISON de l'attente
// (obligatoire), libellés pros. La touche et la table viennent du contrat
// COMMITTÉ (`relance_etape_v2.json`, `parcours_suivi.json`) — jamais un objet
// retapé à la main. Le corps envoyé porte `raison_attente` (CIQ508).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn() }))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

const ETAPE_APPEL = exempleContrat('crm', 'relance_etape_v2').results[0]
const DOC_V2 = exempleContrat('crm', 'relance_etape_v2')
const RAISONS = exempleContrat('crm', 'relance_etape_v2', 'ajout_ciq10_raison_attente')

afterEach(() => { cleanup(); vi.clearAllMocks(); vi.useRealTimers() })

function ouvrirFait(etape, props = {}) {
  const r = render(
    <RelanceEtapeRow
      etape={etape} onFait={() => Promise.resolve({})} onSauter={() => {}}
      onReporter={() => {}} onOuvrirMessage={() => {}} {...props}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
  return r
}

const INDUSTRIEL = { ...ETAPE_APPEL, lead_segment: 'industriel' }

describe('CIQ509 — la raison de l’attente est obligatoire', () => {
  it('sans raison : message SOUS le champ, Confirmer désactivé, aucun POST', () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    ouvrirFait(INDUSTRIEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: "En attente d'un accord" }))
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: '2099-10-14' } })
    const champ = screen.getByLabelText('Raison de l’attente')
    expect(screen.getByTestId('erreur-raison-attente')).toHaveTextContent('Raison de l’attente')
    // Le message est rendu DANS le bloc du champ (sous le sélecteur).
    expect(screen.getByTestId('raison-attente')).toContainElement(champ)
    expect(screen.getByTestId('raison-attente')).toContainElement(screen.getByTestId('erreur-raison-attente'))
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(onFait).not.toHaveBeenCalled()
  })

  it('les raisons proposées sont celles de la table (liste du contrat CIQ10)', () => {
    ouvrirFait(INDUSTRIEL)
    fireEvent.click(screen.getByRole('button', { name: "En attente d'un accord" }))
    const options = [...screen.getByLabelText('Raison de l’attente').querySelectorAll('option')]
      .map((o) => o.value).filter(Boolean)
    expect(options).toEqual(RAISONS.raisons)
  })

  it('avec raison : le corps porte raison_attente, puis l’accusé est proposé (lead industriel)', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-09-23T09:00:00Z'))
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    const onOuvrirMessage = vi.fn()
    ouvrirFait(INDUSTRIEL, { onFait, onOuvrirMessage })
    fireEvent.click(screen.getByRole('button', { name: "En attente d'un accord" }))
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: '2026-10-14' } })
    fireEvent.change(screen.getByLabelText('Raison de l’attente'), {
      target: { value: RAISONS.corps_fait.raison_attente } })
    expect(screen.queryByTestId('erreur-raison-attente')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(INDUSTRIEL.id, {
      reponse: RAISONS.corps_fait.reponse, rappel_le: '2026-10-14',
      raison_attente: RAISONS.corps_fait.raison_attente,
    }))
    await waitFor(() => expect(onOuvrirMessage).toHaveBeenCalledWith(
      { ...INDUSTRIEL, message_cle: 'attente_accord_accuse' }))
  })

  it('un lead résidentiel garde le libellé actuel et aucun accusé n’est proposé', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-09-23T09:00:00Z'))
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    const onOuvrirMessage = vi.fn()
    ouvrirFait({ ...ETAPE_APPEL, lead_segment: 'residentiel' }, { onFait, onOuvrirMessage })
    fireEvent.click(screen.getByRole('button', { name: "En attente d'un accord (DPA / banque)" }))
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: '2026-10-14' } })
    fireEvent.change(screen.getByLabelText('Raison de l’attente'), { target: { value: 'administration' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(ETAPE_APPEL.id, {
      reponse: 'attente_accord', rappel_le: '2026-10-14', raison_attente: 'administration',
    }))
    expect(onOuvrirMessage).not.toHaveBeenCalled()
  })

  it('un refus serveur sur raison_attente s’affiche SOUS le champ', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-09-23T09:00:00Z'))
    const message = '« Raison de l\'attente » (raison_attente) : valeur requise parmi : direction.'
    const onFait = vi.fn(() => Promise.reject({
      response: { status: 400, data: { erreurs: { raison_attente: message } } } }))
    ouvrirFait(INDUSTRIEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: "En attente d'un accord" }))
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: '2026-10-14' } })
    fireEvent.change(screen.getByLabelText('Raison de l’attente'), { target: { value: 'direction' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByTestId('erreur-raison-attente')).toHaveTextContent(message)
  })

  it('le contrat de la touche reste celui du serveur : attente_accord figure dans ses suites', () => {
    expect(DOC_V2.results[0].suites).toHaveProperty('attente_accord')
  })
})
