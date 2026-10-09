import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const post = vi.hoisted(() => vi.fn())
vi.mock('../../../api/axios', () => ({
  default: { post, get: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

import FactureRow, { AnnulationFactureDialog } from './FactureRow'
import { annulerFacture } from '../../../features/ventes/store/ventesSlice'

/* AFAC13 — l'écran DEMANDE où va l'argent avant d'annuler et TRANSMET la
   directive ; réponses simulées LUES dans le contrat facture_annulation.json. */

const ICI = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(join(
  ICI, '..', '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'facturation',
  'contract_samples', 'facture_annulation.json'), 'utf8'))

const ctxBase = {
  selectedIds: [], toggleSelect: () => {},
  pdfGenerating: {}, pdfDownloading: {}, waBusy: {}, payLinkBusy: {}, dgiBusy: {},
  actionId: null, histoCache: {}, canManage: true, isAdmin: true,
}

const facture = {
  id: 118, reference: 'FAC-2026-10-0007', client: 5, client_nom: 'X',
  statut: 'emise', montant_paye: '20000.00', montant_du: '25000.00',
}
const cible = { id: 121, reference: 'FAC-2026-10-0008', client: 5, statut: 'emise' }
const autreClient = { id: 130, reference: 'FAC-AUTRE', client: 9, statut: 'emise' }

beforeEach(() => post.mockReset())

describe('AFAC13 — annulation d’une facture qui porte de l’argent', () => {
  it('le menu « Annuler la facture » ouvre le dialogue de directive', async () => {
    const demanderAnnulation = vi.fn()
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <table><tbody>
          <FactureRow f={facture} ctx={{ ...ctxBase, demanderAnnulation }} />
        </tbody></table>
      </MemoryRouter>,
    )
    await user.click(screen.getByTitle("Plus d'actions"))
    await user.click(await screen.findByText('Annuler la facture'))
    expect(demanderAnnulation).toHaveBeenCalledWith(facture)
  })

  it('transmet la directive transférer avec la facture cible du même client', async () => {
    const onConfirm = vi.fn()
    render(<AnnulationFactureDialog facture={facture} factures={[facture, cible, autreClient]}
      onConfirm={onConfirm} onClose={() => {}} />)
    const select = screen.getByLabelText('Facture cible')
    expect(screen.queryByText('FAC-AUTRE')).toBeNull()
    fireEvent.change(select, { target: { value: '121' } })
    fireEvent.click(screen.getByRole('button', { name: 'Annuler la facture' }))
    expect(onConfirm).toHaveBeenCalledWith(CONTRAT.requete.acompte)
  })

  it('transmet la directive rembourser', () => {
    const onConfirm = vi.fn()
    render(<AnnulationFactureDialog facture={facture} factures={[facture]}
      onConfirm={onConfirm} onClose={() => {}} />)
    fireEvent.click(screen.getByLabelText('Rembourser'))
    fireEvent.click(screen.getByRole('button', { name: 'Annuler la facture' }))
    expect(onConfirm).toHaveBeenCalledWith(CONTRAT.requete_rembourser.acompte)
  })

  it('affiche le refus serveur sous le choix', () => {
    render(<AnnulationFactureDialog facture={facture} factures={[facture]}
      erreur={CONTRAT.exemple_refus.detail} onConfirm={() => {}} onClose={() => {}} />)
    expect(screen.getByTestId('annulation-erreur')).toHaveTextContent(CONTRAT.exemple_refus.detail)
  })

  it('le thunk envoie le corps {acompte} (transmet la directive)', async () => {
    post.mockResolvedValue({ data: CONTRAT.exemple })
    const dispatch = vi.fn()
    await annulerFacture({ id: 118, directive: CONTRAT.requete.acompte })(dispatch, () => ({}), undefined)
    expect(post).toHaveBeenCalledWith('/ventes/factures/118/annuler/', { acompte: CONTRAT.requete.acompte })
  })

  it('le thunk reste rétro-compatible avec un id seul (sans corps)', async () => {
    post.mockResolvedValue({ data: CONTRAT.exemple })
    await annulerFacture(118)(vi.fn(), () => ({}), undefined)
    expect(post).toHaveBeenCalledWith('/ventes/factures/118/annuler/', undefined)
  })
})
