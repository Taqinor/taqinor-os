import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* CIQ638 — écran Dossiers réglementaires : régime et pièces SOURCÉS, étude,
   capacité, convention, exploitation, échéance des travaux, équipements figés
   et alertes de modification. Les dossiers du test viennent de l'exemple
   COMMITTÉ `ventes/contract_samples/dossier_8221.json` (check_api_shapes),
   jamais d'une charge utile écrite à la main. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/ventesApi', () => ({
  default: {
    getReglementaire: vi.fn(),
    getCalendrierReglementaire: vi.fn(),
    patchReglementaire: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import DossiersReglementairesPage from './DossiersReglementairesPage'

const BT = exempleContrat('ventes', 'dossier_8221')
const MT = exempleContrat('ventes', 'dossier_8221', 'exemple_mt')

// Une ligne de la liste = l'objet du contrat + les champs propres à la liste.
const ligne = (contrat, extra = {}) => ({
  statut: 'depose', devis: 10, chantier: 55, reference_dossier: 'REF-638',
  ...contrat, ...extra,
})

const CALENDRIER_VIDE = {
  today: '2026-10-05', seuil_imminent_jours: 30, validite_accord_jours: 365,
  echeances: [], resume: { expire: 0, imminent: 0, a_venir: 0, sans_echeance: 0 },
}

async function ouvrirDetail(dossier) {
  const user = userEvent.setup()
  ventesApi.getReglementaire.mockResolvedValue({ data: [dossier] })
  render(<MemoryRouter><DossiersReglementairesPage /></MemoryRouter>)
  await waitFor(() => expect(ventesApi.getReglementaire).toHaveBeenCalled())
  await user.click(screen.getByRole('radio', { name: 'File de travail' }))
  await user.click(await screen.findByRole('button', { name: 'Détail 82-21' }))
  return { user, detail: await screen.findByTestId('dossier-detail-8221') }
}

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getCalendrierReglementaire.mockResolvedValue({ data: CALENDRIER_VIDE })
})

describe('DossiersReglementairesPage (CIQ638)', () => {
  it('affiche le régime avec sa base et le guichet « à confirmer »', async () => {
    const { detail } = await ouvrirDetail(ligne(BT))
    expect(within(detail).getByText(BT.regime.libelle)).toBeInTheDocument()
    expect(within(detail).getByText(`Base : ${BT.regime.base}`)).toBeInTheDocument()
    expect(within(detail).getByText(/Guichet : .*à confirmer/)).toBeInTheDocument()
  })

  it('groupe les pièces par étape, chacune avec sa source', async () => {
    const { detail } = await ouvrirDetail(ligne(BT))
    const depot = detail.querySelector('[data-etape="depot"]')
    expect(depot).toBeTruthy()
    expect(within(depot).getByText('Planning de réalisation')).toBeInTheDocument()
    expect(depot.textContent).toContain('Source : décret 2.25.100 art. 12')
    const exploitation = detail.querySelector('[data-etape="exploitation"]')
    expect(within(exploitation).getByText("Attestation d'assurance")).toBeInTheDocument()
    expect(exploitation.textContent).toContain('art. 15')
    // Une pièce manquante du résumé est signalée telle quelle.
    expect(within(depot).getAllByText('Manquante')).toHaveLength(
      BT.resume.pieces_manquantes.length)
  })

  it("affiche l'échéance des travaux et les équipements figés", async () => {
    const { detail } = await ouvrirDetail(ligne(MT))
    expect(within(detail).getByTestId('echeance-travaux').textContent)
      .toContain(MT.resume.travaux_limite_le)
    expect(detail.textContent).toContain(
      `× ${MT.resume.equipements_figes[0].quantite}`)
  })

  it('rend visible une alerte de modification du matériel figé', async () => {
    const { detail } = await ouvrirDetail(ligne(BT))
    const alerte = within(detail).getByRole('alert')
    expect(alerte.textContent).toContain(BT.resume.alertes_modification[0].message)
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', async () => {
    const { user } = await ouvrirDetail(ligne(MT))
    ventesApi.patchReglementaire.mockImplementation((_r, _id, data) => Promise.resolve({
      data: ligne(MT, { id: MT.id, ...data }),
    }))
    await user.click(screen.getByRole('button', { name: 'Enregistrer le dossier' }))
    await waitFor(() => expect(ventesApi.patchReglementaire).toHaveBeenCalledTimes(1))
    const premier = ventesApi.patchReglementaire.mock.calls[0]
    expect(premier[0]).toBe('dossiers-reglementaires')
    expect(premier[1]).toBe(MT.id)

    // Le formulaire est ré-ouvert depuis la réponse serveur.
    await screen.findByRole('button', { name: 'Enregistrer le dossier' })
    await user.click(screen.getByRole('button', { name: 'Enregistrer le dossier' }))
    await waitFor(() => expect(ventesApi.patchReglementaire).toHaveBeenCalledTimes(2))
    expect(ventesApi.patchReglementaire.mock.calls[1][2]).toEqual(premier[2])
    // Les valeurs du dossier sont celles du contrat, rien d'inventé.
    expect(premier[2].convention_signee_le).toBe(MT.resume.convention_signee_le)
    expect(premier[2].capacite_etat).toBe(MT.resume.capacite.etat)
  })

  it('une erreur de validation s’affiche sous le champ fautif', async () => {
    const { user } = await ouvrirDetail(ligne(BT))
    ventesApi.patchReglementaire.mockRejectedValue({
      response: { data: { etude_payee_le: ['Date invalide.'] } },
    })
    await user.click(screen.getByRole('button', { name: 'Enregistrer le dossier' }))
    const champ = screen.getByLabelText('Étude payée le')
    const bloc = champ.parentElement
    expect(await within(bloc).findByText('Date invalide.')).toBeInTheDocument()
  })

  it('les onglets recette ventes renvoient vers la fiche chantier', async () => {
    const user = userEvent.setup()
    ventesApi.getReglementaire.mockResolvedValue({ data: [ligne(BT)] })
    render(<MemoryRouter><DossiersReglementairesPage /></MemoryRouter>)
    await user.click(screen.getByRole('radio', { name: 'Recette IEC 62446' }))
    const avis = await screen.findByTestId('recette-sur-chantier')
    expect(avis.textContent).toContain(
      'La recette de ce chantier se saisit sur la fiche chantier')
    expect(within(avis).getByRole('link').getAttribute('href'))
      .toBe('/chantiers?id=55')
    // Les autres ressources n'affichent pas cet avis.
    await user.click(screen.getByRole('radio', { name: 'Checklists' }))
    await waitFor(() => expect(screen.queryByTestId('recette-sur-chantier')).toBeNull())
  })
})
