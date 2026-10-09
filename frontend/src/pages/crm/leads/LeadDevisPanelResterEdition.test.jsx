// EDC11 — moitié panneau du contrat EDC : après « Enregistrer » d'un devis
// EXISTANT le panneau RESTE en phase `edit` (plus de retour d'un coup à
// l'aperçu) ; « Voir le PDF » est un geste explicite qui demande confirmation
// s'il reste des modifications non enregistrées ; la création (`onDone`)
// continue de basculer en aperçu. `DevisGenerator` est mocké : le test appelle
// directement les props du contrat (onEnregistre / onVoirPdf / onDirtyChange).
// Run : npx vitest run src/pages/crm/leads/LeadDevisPanelResterEdition.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import ConfirmProvider from '../../../providers/ConfirmProvider'

vi.mock('../../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(),
    // Aperçu jamais résolu : seul le passage de phase est sous test.
    getProposalPdf: vi.fn(() => new Promise(() => {})),
    reviserDevis: vi.fn(),
    creerDevisAuto: vi.fn(),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
// Les props reçues par le générateur sont gardées : le test joue le rôle de
// DevisGenerator et appelle les rappels du contrat.
const { generateur } = vi.hoisted(() => ({ generateur: { props: null } }))
vi.mock('../../ventes/DevisGenerator', () => ({
  default: (props) => {
    generateur.props = props
    return <div data-testid="generateur-monte">editId={String(props.editId)}</div>
  },
}))

import ventesApi from '../../../api/ventesApi'
import LeadDevisPanel from './LeadDevisPanel'

const LEAD = { id: 77, nom: 'Khalid' }
const envoye = () => ({
  data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
})

function rendre(props = {}) {
  const onClose = vi.fn()
  const onDevisChanged = vi.fn()
  const store = configureStore({ reducer: { r: (s = {}) => s } })
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ConfirmProvider>
          <LeadDevisPanel lead={LEAD} mode="edit" existingDevisId={413}
                          onClose={onClose} onDevisChanged={onDevisChanged} {...props} />
        </ConfirmProvider>
      </MemoryRouter>
    </Provider>,
  )
  return { onClose, onDevisChanged }
}

// Ouvre l'éditeur d'un devis existant et attend que le générateur soit monté.
async function ouvrirEdition(props) {
  const rendu = rendre(props)
  await screen.findByTestId('generateur-monte')
  return rendu
}

const enPhaseEdition = () => screen.queryByTestId('generateur-monte') !== null
const enPhaseApercu = () => screen.queryByRole('button', { name: /Télécharger le PDF/ }) !== null

beforeEach(() => {
  vi.clearAllMocks()
  generateur.props = null
  ventesApi.getProposalPdf.mockImplementation(() => new Promise(() => {}))
  ventesApi.getDevisById.mockResolvedValue(envoye())
})

describe('EDC11 — LeadDevisPanel : on reste dans l\'éditeur après l\'enregistrement', () => {
  it('le panneau passe au générateur les trois props du contrat EDC (+ onDone / onCancel)', async () => {
    await ouvrirEdition()
    const p = generateur.props
    expect(p.embedded).toBe(true)
    expect(p.editId).toBe(413)
    for (const nom of ['onDone', 'onCancel', 'onEnregistre', 'onVoirPdf', 'onDirtyChange']) {
      expect(typeof p[nom]).toBe('function')
    }
  })

  it('onEnregistre : phase edit conservée, onDevisChanged appelé, devis relu', async () => {
    const { onDevisChanged, onClose } = await ouvrirEdition()
    expect(ventesApi.getDevisById).toHaveBeenCalledTimes(1)
    await act(async () => { generateur.props.onEnregistre(413) })
    expect(enPhaseEdition()).toBe(true)
    expect(enPhaseApercu()).toBe(false)
    expect(generateur.props.editId).toBe(413)
    expect(onDevisChanged).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()
    // Le devis est relu : l'en-tête et l'aperçu ne montrent pas un état périmé.
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledTimes(2))
  })

  it('onEnregistre : l\'en-tête suit la nouvelle lecture du devis (référence, statut)', async () => {
    ventesApi.getDevisById
      .mockResolvedValueOnce({ data: { ...envoye().data, reference: 'DEV-AVANT', statut: 'brouillon' } })
      .mockResolvedValueOnce({ data: { ...envoye().data, reference: 'DEV-APRES', statut: 'envoye' } })
    await ouvrirEdition()
    expect(screen.getByText('DEV-AVANT')).toBeInTheDocument()
    expect(screen.getByTestId('ldp-statut')).toHaveTextContent('Brouillon')
    await act(async () => { generateur.props.onEnregistre(413) })
    expect(await screen.findByText('DEV-APRES')).toBeInTheDocument()
    expect(screen.getByTestId('ldp-statut')).toHaveTextContent('Envoyé')
    expect(enPhaseEdition()).toBe(true)
  })

  it("après l'enregistrement, le générateur dit lui-même « plus rien à enregistrer » : « Voir le PDF » ne demande plus rien", async () => {
    await ouvrirEdition()
    await act(async () => { generateur.props.onDirtyChange(true) })
    // Le VRAI générateur : `marquerEnregistre()` fait passer `dirty` à faux et
    // `onDirtyChange(false)` suit — le panneau n'écrase jamais ce drapeau.
    await act(async () => { generateur.props.onEnregistre(413); generateur.props.onDirtyChange(false) })
    await act(async () => { generateur.props.onVoirPdf() })
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(enPhaseEdition()).toBe(false)
  })

  it("une frappe PENDANT l'enregistrement garde la garde : le générateur reste « modifié », « Voir le PDF » demande", async () => {
    await ouvrirEdition()
    await act(async () => { generateur.props.onDirtyChange(true) })
    // Enregistrement réussi… mais l'ouvrier a tapé entre-temps : le générateur
    // ne redescend pas à faux (revue du 09/10 : le panneau ne doit pas l'écraser).
    await act(async () => { generateur.props.onEnregistre(413) })
    await act(async () => { generateur.props.onVoirPdf() })
    expect(await screen.findByRole('alertdialog')).toHaveTextContent(/Voir le PDF sans enregistrer/)
    expect(enPhaseEdition()).toBe(true)
  })

  it('onDone (CRÉATION) continue de basculer en aperçu, sur l\'id créé', async () => {
    ventesApi.getDevisById.mockResolvedValue({ data: { id: 777, reference: 'DEV-777' } })
    // Pas de devis existant : mode edit = création, l'éditeur est monté d'emblée.
    const { onDevisChanged } = await ouvrirEdition({ existingDevisId: null })
    expect(generateur.props.editId).toBeNull()
    await act(async () => { generateur.props.onDone(777) })
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(enPhaseEdition()).toBe(false)
    expect(onDevisChanged).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(ventesApi.getProposalPdf).toHaveBeenCalled())
    expect(ventesApi.getProposalPdf.mock.calls[0][0]).toBe(777)
  })
})

describe('EDC11 — LeadDevisPanel : « Voir le PDF » explicite', () => {
  it('sans modification : aperçu direct, aucune confirmation', async () => {
    await ouvrirEdition()
    await act(async () => { generateur.props.onVoirPdf() })
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(enPhaseEdition()).toBe(false)
  })

  it('avec modifications non enregistrées : confirmation ; « Rester » garde l\'éditeur', async () => {
    await ouvrirEdition()
    await act(async () => { generateur.props.onDirtyChange(true) })
    await act(async () => { generateur.props.onVoirPdf() })
    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent('Voir le PDF sans enregistrer ?')
    await userEvent.click(screen.getByRole('button', { name: 'Rester' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(enPhaseEdition()).toBe(true)
    expect(enPhaseApercu()).toBe(false)
  })

  it('avec modifications non enregistrées : « Voir sans enregistrer » ouvre l\'aperçu', async () => {
    await ouvrirEdition()
    await act(async () => { generateur.props.onDirtyChange(true) })
    await act(async () => { generateur.props.onVoirPdf() })
    await userEvent.click(await screen.findByRole('button', { name: 'Voir sans enregistrer' }))
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(enPhaseEdition()).toBe(false)
  })

  it('depuis l\'aperçu, « Édition complète » remonte le générateur sur le MÊME devis', async () => {
    await ouvrirEdition()
    await act(async () => { generateur.props.onVoirPdf() })
    await userEvent.click(await screen.findByRole('button', { name: /Édition complète/ }))
    expect((await screen.findByTestId('generateur-monte')).textContent).toBe('editId=413')
    expect(generateur.props.editId).toBe(413)
  })

  it('« Annuler » du générateur : retour à l\'aperçu du devis existant (comportement conservé)', async () => {
    await ouvrirEdition()
    await act(async () => { generateur.props.onCancel() })
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
  })
})
