import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within, renderHook, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const post = vi.hoisted(() => vi.fn())
const get = vi.hoisted(() => vi.fn())
const del = vi.hoisted(() => vi.fn())
const ouvrirBlob = vi.hoisted(() => vi.fn())
const toastMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), message: vi.fn(), info: vi.fn() }))
vi.mock('../../../api/axios', () => ({
  default: { post, get, patch: vi.fn(), put: vi.fn(), delete: del },
}))
vi.mock('../../../utils/pdfBlob', async (importOriginal) => ({
  ...(await importOriginal()), openPdfBlob: ouvrirBlob,
}))
vi.mock('../../../ui/Toaster', async (importOriginal) => ({
  ...(await importOriginal()), toast: toastMock,
}))

import FactureRow, { AnnulationFactureDialog } from './FactureRow'
import { annulerFacture } from '../../../features/ventes/store/ventesSlice'
import { useActionsVente } from '../../../features/ventes/vente/useActionsVente'

/* AFAC13 — l'écran DEMANDE où va l'argent avant d'annuler et TRANSMET la
   directive ; réponses simulées LUES dans le contrat facture_annulation.json.
   VNT46 — annulation en 1 clic (avoir nommé), directive NON pré-cochée,
   Supprimer un BROUILLON-<id>, Reçu par paiement ; erreurs sous la facture. */

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

beforeEach(() => {
  post.mockReset(); get.mockReset(); del.mockReset()
  ouvrirBlob.mockReset()
  Object.values(toastMock).forEach((m) => m.mockReset())
})

function rendreLigne(f, ctx = {}) {
  return render(
    <MemoryRouter>
      <table><tbody>
        <FactureRow f={{ client: 5, client_nom: 'X', ...f }} ctx={{ ...ctxBase, ...ctx }} />
      </tbody></table>
    </MemoryRouter>,
  )
}
const ouvrirMenu = async (user) => user.click(screen.getByTitle("Plus d'actions"))

describe('AFAC13 — annulation d’une facture qui porte de l’argent', () => {
  it('le menu « Annuler la facture » ouvre le dialogue qui nomme l’avoir (VNT46)', async () => {
    const user = userEvent.setup()
    rendreLigne(facture)
    await ouvrirMenu(user)
    await user.click(await screen.findByText('Annuler la facture'))
    const dlg = await screen.findByRole('dialog')
    expect(within(dlg).getByTestId('annulation-avoir').textContent).toMatch(/avoir de contre-passation/)
    expect(within(dlg).getByTestId('annulation-avoir').textContent).toMatch(/reste tracée/)
  })

  it('un Commercial ne voit ni Annuler ni Supprimer (palier responsable/admin)', async () => {
    const user = userEvent.setup()
    rendreLigne({ ...facture, statut: 'brouillon', reference: 'BROUILLON-119', montant_paye: '0.00' },
      { canManage: false, isAdmin: false })
    await ouvrirMenu(user)
    await screen.findByRole('menu')
    expect(screen.queryByText('Annuler la facture')).toBeNull()
    expect(screen.queryByText('Supprimer le brouillon')).toBeNull()
  })

  it('transmet la directive transférer avec la facture cible du même client', async () => {
    const onConfirm = vi.fn()
    render(<AnnulationFactureDialog facture={facture} factures={[facture, cible, autreClient]}
      onConfirm={onConfirm} onClose={() => {}} />)
    fireEvent.click(screen.getByLabelText('Transférer sur une autre facture'))
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

  it('aucune directive n’est pré-cochée : Annuler la facture reste fermé tant qu’on n’a pas choisi', () => {
    const onConfirm = vi.fn()
    render(<AnnulationFactureDialog facture={facture} factures={[facture]}
      onConfirm={onConfirm} onClose={() => {}} />)
    for (const radio of screen.getAllByRole('radio')) expect(radio.checked).toBe(false)
    const bouton = screen.getByRole('button', { name: 'Annuler la facture' })
    expect(bouton.disabled).toBe(true)
    fireEvent.click(screen.getByLabelText('Garder en avance client'))
    expect(bouton.disabled).toBe(false)
    fireEvent.click(bouton)
    expect(onConfirm).toHaveBeenCalledWith(CONTRAT.requete_garder_en_avance.acompte)
  })

  it('sans argent rattaché : pas de choix, confirmation directe sans directive', () => {
    const onConfirm = vi.fn()
    render(<AnnulationFactureDialog facture={{ ...facture, montant_paye: '0.00' }} factures={[]}
      onConfirm={onConfirm} onClose={() => {}} />)
    expect(screen.queryAllByRole('radio')).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Annuler la facture' }))
    expect(onConfirm).toHaveBeenCalledWith(undefined)
  })

  it('un BROUILLON-<id> est annulé sans avoir (dit à l’écran)', () => {
    render(<AnnulationFactureDialog facture={{ ...facture, reference: 'BROUILLON-119', montant_paye: '0.00' }}
      factures={[]} onConfirm={() => {}} onClose={() => {}} />)
    expect(screen.getByTestId('annulation-avoir').textContent).toMatch(/sans avoir/)
  })

  it('affiche le refus serveur sous le choix', () => {
    render(<AnnulationFactureDialog facture={facture} factures={[facture]}
      erreur={CONTRAT.exemple_refus.detail} onConfirm={() => {}} onClose={() => {}} />)
    expect(screen.getByTestId('annulation-erreur')).toHaveTextContent(CONTRAT.exemple_refus.detail)
  })

  it('depuis la ligne : rembourser → POST annuler avec la directive du contrat, dialogue fermé, aucun toast', async () => {
    post.mockResolvedValue({ data: CONTRAT.exemple })
    const user = userEvent.setup()
    rendreLigne(facture)
    await ouvrirMenu(user)
    await user.click(await screen.findByText('Annuler la facture'))
    await user.click(await screen.findByLabelText('Rembourser'))
    await user.click(screen.getByRole('button', { name: 'Annuler la facture' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/ventes/factures/118/annuler/', CONTRAT.requete_rembourser))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(toastMock.success).not.toHaveBeenCalled()
    expect(toastMock.error).not.toHaveBeenCalled()
  })

  it('depuis la ligne : le refus directive_acompte_requise reste SOUS le choix', async () => {
    post.mockRejectedValue({ response: { status: 400, data: CONTRAT.exemple_refus } })
    const user = userEvent.setup()
    rendreLigne({ ...facture, montant_paye: '0.00' })
    await ouvrirMenu(user)
    await user.click(await screen.findByText('Annuler la facture'))
    await user.click(screen.getByRole('button', { name: 'Annuler la facture' }))
    const erreur = await screen.findByTestId('annulation-erreur')
    expect(erreur.textContent).toBe(CONTRAT.exemple_refus.detail)
    // Le serveur a parlé d'argent : le choix apparaît, non pré-coché.
    expect(screen.getAllByRole('radio').length).toBe(3)
    expect(toastMock.error).not.toHaveBeenCalled()
  })

  it('Supprimer : seulement un BROUILLON-<id> ; confirmation puis DELETE', async () => {
    del.mockResolvedValue({ data: null })
    const user = userEvent.setup()
    rendreLigne({ id: 119, reference: 'BROUILLON-119', statut: 'brouillon', montant_paye: '0.00' })
    await ouvrirMenu(user)
    await user.click(await screen.findByTestId('supprimer-brouillon'))
    await user.click(await screen.findByTestId('supprimer-brouillon-confirmer'))
    await waitFor(() => expect(del).toHaveBeenCalledWith('/ventes/factures/119/'))
  })

  it('un brouillon à numéro légal ne propose pas Supprimer (il s’annule)', async () => {
    const user = userEvent.setup()
    rendreLigne({ id: 120, reference: 'FAC-2026-10-0009', statut: 'brouillon', montant_paye: '0.00' })
    await ouvrirMenu(user)
    await screen.findByTestId('annuler-facture')
    expect(screen.queryByTestId('supprimer-brouillon')).toBeNull()
  })

  it('Supprimer refusé par le serveur : message SOUS la facture (role=alert), aucun toast', async () => {
    del.mockRejectedValue({ response: { status: 400, data: {
      code: 'reference_legale',
      detail: 'Cette facture porte le numéro FAC-2026-10-0009 : annulez-la.' } } })
    const user = userEvent.setup()
    rendreLigne({ id: 119, reference: 'BROUILLON-119', statut: 'brouillon', montant_paye: '0.00' })
    await ouvrirMenu(user)
    await user.click(await screen.findByTestId('supprimer-brouillon'))
    await user.click(await screen.findByTestId('supprimer-brouillon-confirmer'))
    const alerte = await screen.findByTestId('facture-erreur')
    expect(alerte.getAttribute('role')).toBe('alert')
    expect(alerte.textContent).toContain('annulez-la')
    expect(toastMock.error).not.toHaveBeenCalled()
  })

  it('Reçu : un bouton par paiement encaissé (jamais pour un rejeté) → GET recu-pdf, fichier Quittance', async () => {
    const blob = new Blob(['%PDF'], { type: 'application/pdf' })
    get.mockResolvedValue({ data: blob, headers: { 'content-disposition': 'inline; filename="Quittance_REC-2026-0001.pdf"' } })
    const user = userEvent.setup()
    rendreLigne({ ...facture, paiements: [
      { id: 31, statut: 'encaisse', montant: '15000.00', date_paiement: '2026-10-12', numero_recu: 'REC-2026-0001' },
      { id: 32, statut: 'rejete', montant: '5000.00', date_paiement: '2026-10-13' },
    ] })
    const boutons = screen.getAllByTestId('recu-paiement')
    expect(boutons).toHaveLength(1)
    await user.click(boutons[0])
    await waitFor(() => expect(get).toHaveBeenCalledWith('/ventes/paiements/31/recu-pdf/', { responseType: 'blob' }))
    await waitFor(() => expect(ouvrirBlob).toHaveBeenCalledWith(blob, 'Quittance_REC-2026-0001.pdf'))
  })

  it('Reçu indisponible (500) : message sous la facture, aucun toast', async () => {
    get.mockRejectedValue({ response: { status: 500, data: { detail: 'PDF du reçu indisponible.' } } })
    const user = userEvent.setup()
    rendreLigne({ ...facture, paiements: [{ id: 31, statut: 'encaisse', montant: '15000.00', date_paiement: '2026-10-12' }] })
    await user.click(screen.getByTestId('recu-paiement'))
    expect((await screen.findByTestId('facture-erreur')).textContent).toBe('PDF du reçu indisponible.')
    expect(toastMock.error).not.toHaveBeenCalled()
  })

  it('useActionsVente : emettre → POST emettre ; pdf → génère puis ouvre (sondage borné)', async () => {
    post.mockResolvedValue({ data: {} })
    const blob = new Blob(['%PDF'], { type: 'application/pdf' })
    get.mockResolvedValue({ data: blob, headers: {} })
    const { result } = renderHook(() => useActionsVente())
    let r
    await act(async () => { r = await result.current.emettre({ id: 118 }) })
    expect(r.ok).toBe(true)
    expect(post).toHaveBeenCalledWith('/ventes/factures/118/emettre/')
    post.mockClear()
    await act(async () => { r = await result.current.pdf({ id: 118, reference: 'FAC-1' }, { essais: 2, delaiMs: 1 }) })
    expect(post).toHaveBeenCalledWith('/ventes/factures/118/generer-pdf/')
    expect(get).toHaveBeenCalledWith('/ventes/factures/118/telecharger-pdf/', { responseType: 'blob' })
    expect(r.ok).toBe(true)
    expect(ouvrirBlob).toHaveBeenCalledWith(blob, 'FAC-1.pdf')
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
