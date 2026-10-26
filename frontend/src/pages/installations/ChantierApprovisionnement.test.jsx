import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
// PACT13 — la réponse mockée est l'exemple COMMITTÉ côté serveur, jamais un
// payload écrit à la main.
import CONTRAT from '../../../../backend/django_core/apps/installations/contract_samples/chantier_approvisionnement.json'

const mocks = vi.hoisted(() => ({ commanderBesoin: vi.fn(), peutCommander: true }))

vi.mock('../../features/stock/useVoitPrixAchat', () => ({
  usePermissionAchats: () => mocks.peutCommander,
}))

vi.mock('../../api/installationsApi', () => ({
  default: { commanderBesoin: (...a) => mocks.commanderBesoin(...a) },
}))

import ChantierApprovisionnement from './ChantierApprovisionnement'

const EXEMPLE = CONTRAT.exemple
const VIDE = CONTRAT.exemple_vide

const rendre = (props = {}) => render(
  <MemoryRouter>
    <ChantierApprovisionnement chantierId={43} data={EXEMPLE} {...props} />
  </MemoryRouter>,
)

afterEach(() => { cleanup(); vi.clearAllMocks(); mocks.peutCommander = true })

describe('ChantierApprovisionnement — contrat chantier_approvisionnement.json', () => {
  it('affiche les pastilles de synthèse et le verdict « pas prêt » avec ses raisons', () => {
    rendre()
    expect(screen.getByText('1 manque')).toBeTruthy()
    expect(screen.getByText('1 article en commande')).toBeTruthy()
    expect(screen.getByText('0 article reçu')).toBeTruthy()
    expect(screen.getByText('Pas encore prêt à poser')).toBeTruthy()
    expect(screen.getByText('Date de pose non fixée')).toBeTruthy()
  })

  it('trie les lignes par manque décroissant, montre « N en route », cache « Déjà sorti » quand tout est à 0', () => {
    rendre()
    const lignes = screen.getAllByRole('row').slice(1)
    // 1re ligne de données = l'article en manque.
    expect(within(lignes[0]).getByText('Tableau de protection AC/DC')).toBeTruthy()
    expect(within(lignes[0]).getByText('à renseigner')).toBeTruthy()
    expect(screen.getByText('2 en route')).toBeTruthy()
    expect(screen.queryByText('Déjà sorti')).toBeNull()
    // Aucun prix nulle part.
    expect(screen.queryByText(/prix|MAD|DH/i)).toBeNull()
  })

  it('montre un brouillon en texte discret', () => {
    const data = {
      ...EXEMPLE,
      lignes: EXEMPLE.lignes.map((l, i) => (i === 0 ? { ...l, en_commande_brouillon: 4 } : l)),
    }
    rendre({ data })
    expect(screen.getByText('brouillon 4')).toBeTruthy()
  })

  it('« Commander les manques » envoie les produits en manque puis liste les BCF et les articles sans fournisseur', async () => {
    mocks.commanderBesoin.mockResolvedValue({
      data: {
        bons_commande: [{ id: 9, reference: 'BCF-202610-0009', statut: 'brouillon', fournisseur_nom: 'SunPro Maroc' }],
        sans_fournisseur: [{ produit_id: 60, designation: 'Tableau de protection AC/DC' }],
        statut_chantier: 'materiel_commande',
        statut_raison: 'Matériel commandé',
      },
    })
    const onReload = vi.fn()
    const onChantierChange = vi.fn()
    const user = userEvent.setup()
    rendre({ onReload, onChantierChange })

    await user.click(screen.getByRole('button', { name: /Commander les manques \(1\)/ }))

    await waitFor(() => expect(mocks.commanderBesoin).toHaveBeenCalledWith(43, { produits: [60] }))
    const lien = await screen.findByRole('link', { name: 'BCF-202610-0009' })
    expect(lien.getAttribute('href')).toBe('/stock/bons-commande-fournisseur')
    expect(screen.getByText(/Sans fournisseur : Tableau de protection AC\/DC/)).toBeTruthy()
    expect(onReload).toHaveBeenCalled()
    expect(onChantierChange).toHaveBeenCalled()
  })

  it('un refus serveur (409) est affiché, jamais avalé', async () => {
    mocks.commanderBesoin.mockRejectedValue({ response: { data: { detail: 'Chantier annulé.' } } })
    const user = userEvent.setup()
    rendre()
    await user.click(screen.getByRole('button', { name: /Commander les manques/ }))
    expect(await screen.findByText('Chantier annulé.')).toBeTruthy()
  })

  it('liste les BCF du chantier avec avancement, les DA et les réservations', () => {
    rendre()
    expect(screen.getByRole('link', { name: 'BCF-202610-0003' })).toBeTruthy()
    expect(screen.getByRole('progressbar', { name: 'Réception BCF-202610-0003' })
      .getAttribute('aria-valuenow')).toBe('0')
    const da = screen.getByRole('link', { name: 'DA-202610-0001' })
    // F1 — ouvre le DÉTAIL de la DA (?da=), jamais le formulaire de création (?chantier=).
    expect(da.getAttribute('href')).toBe('/chantiers/demandes-achat?da=3')
    expect(screen.getByText('10 × Panneau Canadian Solar 710W')).toBeTruthy()
  })

  it('F3 : sans la permission achats_commander, « Commander les manques » n’est pas proposé', () => {
    mocks.peutCommander = false
    rendre()
    expect(screen.queryByRole('button', { name: /Commander les manques/ })).toBeNull()
    expect(screen.getByText(/Permission achats_commander requise/)).toBeTruthy()
  })

  it('états vides en français quand le chantier n’a rien', () => {
    rendre({ data: VIDE })
    expect(screen.getByText(/Aucune ligne de matériel/)).toBeTruthy()
    expect(screen.getByText('Aucun bon de commande fournisseur lié à ce chantier.')).toBeTruthy()
    expect(screen.getByText('Nomenclature vide')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Commander les manques/ })).toBeNull()
  })

  it('affiche une erreur de chargement avec « Réessayer »', async () => {
    const onReload = vi.fn()
    const user = userEvent.setup()
    rendre({ data: null, error: 'Matériel indisponible pour le moment.', onReload })
    expect(screen.getByRole('alert').textContent).toContain('Matériel indisponible')
    await user.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(onReload).toHaveBeenCalled()
  })

  it('affiche un squelette pendant le premier chargement', () => {
    rendre({ data: null, loading: true })
    expect(screen.getByRole('status', { name: 'Chargement du matériel' })).toBeTruthy()
  })
})
