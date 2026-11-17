import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* « Déléguer mes dossiers » (17/11/2026) — l'aperçu et le résultat viennent de
   l'exemple COMMITTÉ `apps/crm/contract_samples/lead_deleguer.json` (PACT10),
   jamais d'un objet retapé à la main. */
const APERCU = exempleContrat('crm', 'lead_deleguer', 'exemple_apercu')
const RESULTAT = exempleContrat('crm', 'lead_deleguer')

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(),
    apercuDelegation: vi.fn(),
    deleguerDossiers: vi.fn(),
  },
}))
vi.mock('../../../lib/toast', () => ({ toastSuccess: vi.fn(), toastError: vi.fn() }))
const droit = vi.fn(() => true)
vi.mock('../../sav/useDroitMetier', () => ({ default: (code) => droit(code) }))

import crmApi from '../../../api/crmApi'
import { toastSuccess } from '../../../lib/toast'
import BoutonDeleguerDossiers from './DelegationDialog'

beforeEach(() => {
  droit.mockReturnValue(true)
  crmApi.getAssignableUsers.mockResolvedValue({ data: [
    { id: 3, username: 'reda' }, { id: 12, username: 'meryem' },
  ] })
  crmApi.apercuDelegation.mockResolvedValue({ data: APERCU })
  crmApi.deleguerDossiers.mockResolvedValue({ data: RESULTAT })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

async function ouvrirEtChoisir() {
  fireEvent.click(screen.getByRole('button', { name: /Déléguer mes dossiers/ }))
  const select = await screen.findByLabelText('Collègue')
  await screen.findByRole('option', { name: 'meryem' })
  fireEvent.change(select, { target: { value: '12' } })
}

describe('BoutonDeleguerDossiers', () => {
  it('reste caché sans le droit crm_reassign', () => {
    droit.mockReturnValue(false)
    render(<BoutonDeleguerDossiers />)
    expect(droit).toHaveBeenCalledWith('crm_reassign')
    expect(screen.queryByRole('button')).toBeNull()
  })

  it("annonce l'aperçu du serveur puis délègue, prévenir les clients coché par défaut", async () => {
    const onDone = vi.fn()
    render(<BoutonDeleguerDossiers onDone={onDone} />)
    await ouvrirEtChoisir()
    expect(crmApi.apercuDelegation).toHaveBeenCalledWith({ vers: '12' })
    expect(await screen.findByTestId('delegation-apercu')).toHaveTextContent(
      '26 dossiers, dont 41 étapes ouvertes (40 en retard), passeront à Meryem.')
    expect(screen.getByRole('checkbox')).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Déléguer' }))
    await waitFor(() => expect(crmApi.deleguerDossiers).toHaveBeenCalledWith(
      { vers: 12, prevenir_clients: true }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith(
      '26 dossiers confiés à Meryem.'))
    expect(onDone).toHaveBeenCalledWith(RESULTAT)
  })

  it('décocher la passation est transmis au serveur', async () => {
    render(<BoutonDeleguerDossiers />)
    await ouvrirEtChoisir()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Déléguer' }))
    await waitFor(() => expect(crmApi.deleguerDossiers).toHaveBeenCalledWith(
      { vers: 12, prevenir_clients: false }))
  })

  it('agit sur un autre responsable avec `de`', async () => {
    render(<BoutonDeleguerDossiers de={3} deNom="reda" />)
    fireEvent.click(screen.getByRole('button', { name: /Déléguer les dossiers de reda/ }))
    const select = await screen.findByLabelText('Collègue')
    await screen.findByRole('option', { name: 'meryem' })
    // le propriétaire des dossiers n'est pas proposé comme cible
    expect(screen.queryByRole('option', { name: 'reda' })).toBeNull()
    fireEvent.change(select, { target: { value: '12' } })
    await waitFor(() => expect(crmApi.apercuDelegation).toHaveBeenCalledWith(
      { vers: '12', de: 3 }))
    fireEvent.click(screen.getByRole('button', { name: 'Déléguer' }))
    await waitFor(() => expect(crmApi.deleguerDossiers).toHaveBeenCalledWith(
      { vers: 12, prevenir_clients: true, de: 3 }))
  })

  it('un refus du serveur s’affiche sous le champ, sans toast', async () => {
    crmApi.deleguerDossiers.mockRejectedValue({
      response: { status: 400, data: exempleContrat('crm', 'lead_deleguer', 'exemple_refus') },
    })
    render(<BoutonDeleguerDossiers />)
    await ouvrirEtChoisir()
    fireEvent.click(screen.getByRole('button', { name: 'Déléguer' }))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Ce collègue est désactivé')
    expect(screen.getByLabelText('Collègue')).toHaveAttribute('aria-invalid', 'true')
    expect(toastSuccess).not.toHaveBeenCalled()
  })

  it('sans collègue choisi, la consigne s’affiche sous le champ et rien n’est écrit', async () => {
    render(<BoutonDeleguerDossiers />)
    fireEvent.click(screen.getByRole('button', { name: /Déléguer mes dossiers/ }))
    await screen.findByLabelText('Collègue')
    fireEvent.click(screen.getByRole('button', { name: 'Déléguer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Choisissez le collègue')
    expect(crmApi.deleguerDossiers).not.toHaveBeenCalled()
  })
})
