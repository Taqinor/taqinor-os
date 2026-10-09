// QJR534 — le panneau devis du cockpit lead : « Édition complète » seulement si
// le serveur dit le devis modifiable, sinon « Réviser » ; un envoyé s'ouvre en
// édition sur SON id (DevisGenerator monté avec editId). Droits lus de
// l'exemple COMMITTÉ `devis_modifiabilite.json` (PACT10).
// Run : npx vitest run src/pages/crm/leads/LeadDevisPanelEdition.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(),
    // Aperçu jamais résolu : seul l'état des boutons est sous test.
    getProposalPdf: vi.fn(() => new Promise(() => {})),
    reviserDevis: vi.fn(),
    // CIQ127 — le devis automatique C&I part au serveur.
    creerDevisAuto: vi.fn(),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
// EDC8 — `montageGenerateur` compte chaque rendu du générateur : « jamais monté »
// se prouve par 0 appel, pas par un test fait après coup sur le DOM.
const { montageGenerateur } = vi.hoisted(() => ({ montageGenerateur: vi.fn() }))
vi.mock('../../ventes/DevisGenerator', () => ({
  default: ({ editId }) => {
    montageGenerateur(editId)
    return <div data-testid="generateur-monte">editId={String(editId)}</div>
  },
}))

import ventesApi from '../../../api/ventesApi'
import { toast } from '../../../ui/confirm'
import LeadDevisPanel from './LeadDevisPanel'

const LEAD = { id: 77, nom: 'Khalid' }

function rendre(props = {}) {
  const store = configureStore({ reducer: { r: (s = {}) => s } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <LeadDevisPanel lead={LEAD} mode="view" onClose={vi.fn()} existingDevisId={414} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getProposalPdf.mockImplementation(() => new Promise(() => {}))
})

describe('QJR534 — LeadDevisPanel : Édition complète ou Réviser selon le serveur', () => {
  it('accepté → pas d\'« Édition complète », « Réviser » présent et appelle le serveur', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_accepte'),
    })
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 99, reference: 'DEV-V2' } })
    rendre()
    const reviser = await screen.findByRole('button', { name: /Réviser/ })
    expect(screen.queryByRole('button', { name: /Édition complète/ })).toBeNull()
    await userEvent.click(reviser)
    await waitFor(() => expect(ventesApi.reviserDevis).toHaveBeenCalledWith(414))
  })

  it('envoyé → « Édition complète » ; le clic monte DevisGenerator avec editId', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
    })
    rendre({ existingDevisId: 413 })
    const edition = await screen.findByRole('button', { name: /Édition complète/ })
    expect(screen.queryByRole('button', { name: /Réviser/ })).toBeNull()
    await userEvent.click(edition)
    expect((await screen.findByTestId('generateur-monte')).textContent).toBe('editId=413')
  })

  it('mode edit sur un devis existant → ouvre directement l\'édition sur son id', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
    })
    rendre({ existingDevisId: 413, mode: 'edit' })
    expect((await screen.findByTestId('generateur-monte')).textContent).toBe('editId=413')
  })
})

// CIQ127 — « Devis automatique » d'un lead commercial / industriel : UN appel
// `POST /ventes/devis/auto/` ; les alertes du moteur sont listées, les
// INTERNES marquées « vendeur seulement » ; un 422 affiche le message serveur.
describe('CIQ127 — LeadDevisPanel : devis automatique C&I par le serveur', () => {
  const LEAD_INDUS = { id: 91, nom: 'Usine', type_installation: 'industriel' }
  const rendreAuto = () => render(
    <Provider store={configureStore({ reducer: { r: (s = {}) => s } })}>
      <MemoryRouter>
        <LeadDevisPanel lead={LEAD_INDUS} mode="auto" onClose={vi.fn()} />
      </MemoryRouter>
    </Provider>,
  )

  it('lead industriel : un seul appel serveur, alertes listées, internes marquées', async () => {
    const alertes = exempleContrat('ventes', 'etude_ci_preview').alertes
    ventesApi.creerDevisAuto.mockResolvedValueOnce({ data: { id: 615, alertes } })
    ventesApi.getDevisById.mockResolvedValue({ data: { id: 615, reference: 'DEV-615' } })
    rendreAuto()
    const bloc = await screen.findByTestId('ldp-alertes-auto')
    expect(ventesApi.creerDevisAuto).toHaveBeenCalledTimes(1)
    expect(ventesApi.creerDevisAuto.mock.calls[0][0]).toMatchObject({ lead: 91 })
    for (const a of alertes) expect(bloc).toHaveTextContent(a.message)
    expect(screen.getAllByTestId('ldp-alerte-interne'))
      .toHaveLength(alertes.filter((a) => a.interne === true).length)
  })

  it('422 du serveur : le message est affiché tel quel', async () => {
    const detail = 'Consommation du site absente : renseignez les kWh mensuels du lead.'
    ventesApi.creerDevisAuto.mockRejectedValueOnce({ response: { status: 422, data: { detail, field: 'consommation' } } })
    rendreAuto()
    expect(await screen.findByText(detail)).toBeInTheDocument()
  })
})

// EDC1 — panneau d'Édition complète pleine largeur : la classe large n'existe
// qu'en phase `edit`, le générateur vit dans `.ldp-edit-inner` (le défileur
// `.ldp-edit` n'a plus de padding) et l'en-tête dit la référence + le statut.
describe("EDC1 — LeadDevisPanel : panneau d'Édition complète pleine largeur", () => {
  const envoye = () => ({
    data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
  })

  it('phase edit : SheetContent large (1 800 px) et générateur dans .ldp-edit-inner', async () => {
    ventesApi.getDevisById.mockResolvedValue(envoye())
    rendre({ existingDevisId: 413 })
    await userEvent.click(await screen.findByRole('button', { name: /Édition complète/ }))
    const generateur = await screen.findByTestId('generateur-monte')
    const panneau = screen.getByRole('dialog')
    expect(panneau.className).toContain('w-[min(1800px,100%)]')
    expect(panneau.className).not.toContain('w-[min(1500px,100%)]')
    const interieur = generateur.closest('.ldp-edit-inner')
    expect(interieur).not.toBeNull()
    // Le défileur est le parent direct : c'est lui qui perd son padding (CSS),
    // le retrait de 16 px vit sur l'intérieur.
    expect(interieur.parentElement).toHaveClass('ldp-edit')
    expect(interieur.parentElement.parentElement).toHaveClass('ldp-body')
  })

  it('phase preview : le panneau garde sa largeur de 1 500 px, pas la classe large', async () => {
    ventesApi.getDevisById.mockResolvedValue(envoye())
    rendre({ existingDevisId: 413 })
    await screen.findByRole('button', { name: /Édition complète/ })
    const panneau = screen.getByRole('dialog')
    expect(panneau.className).toContain('w-[min(1500px,100%)]')
    expect(panneau.className).not.toContain('w-[min(1800px,100%)]')
    expect(screen.queryByTestId('generateur-monte')).toBeNull()
  })

  it("l'en-tête montre la référence et le badge de statut du devis chargé", async () => {
    ventesApi.getDevisById.mockResolvedValue(envoye())
    rendre({ existingDevisId: 413 })
    const badge = await screen.findByTestId('ldp-statut')
    expect(badge).toHaveTextContent('Envoyé')
    expect(screen.getByText('DEV-202609-0012')).toBeInTheDocument()
  })

  it('un devis accepté porte le libellé « Accepté » (libellés de devisStatuts.js)', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_accepte'),
    })
    rendre({ existingDevisId: 414 })
    expect(await screen.findByTestId('ldp-statut')).toHaveTextContent('Accepté')
  })
})

// EDC8 — plus de flash « ouvre puis referme » : le panneau ne monte le
// générateur qu'une fois le devis lu et modifiable. « Édition complète » n'est
// plus offerte AVANT la lecture (editable ne vaut plus `true` par défaut).
describe("EDC8 — LeadDevisPanel : le générateur ne se monte qu'après la lecture du devis", () => {
  const differe = () => {
    let resolve
    let reject
    const promesse = new Promise((a, b) => { resolve = a; reject = b })
    return { promesse, resolve, reject }
  }
  const exemple = (cas) => ({ data: exempleContrat('ventes', 'devis_modifiabilite', cas) })

  it('devis non modifiable ouvert en edit : jamais de générateur, toast de la raison serveur, aperçu', async () => {
    const erreur = vi.spyOn(toast, 'error').mockImplementation(() => {})
    ventesApi.getDevisById.mockResolvedValue(exemple('exemple_accepte'))
    rendre({ existingDevisId: 414, mode: 'edit' })
    // « Réviser » est offert dans l'aperçu (revision_possible côté serveur).
    expect(await screen.findByRole('button', { name: /Réviser/ })).toBeInTheDocument()
    expect(erreur).toHaveBeenCalledWith('Devis accepté : révisez-le')
    expect(montageGenerateur).not.toHaveBeenCalled()
    expect(screen.queryByTestId('generateur-monte')).toBeNull()
    expect(screen.queryByRole('button', { name: /Édition complète/ })).toBeNull()
    erreur.mockRestore()
  })

  it('devis modifiable ouvert en edit : spinner puis générateur monté APRÈS la lecture', async () => {
    const erreur = vi.spyOn(toast, 'error').mockImplementation(() => {})
    const lecture = differe()
    ventesApi.getDevisById.mockReturnValue(lecture.promesse)
    rendre({ existingDevisId: 412, mode: 'edit' })
    expect(await screen.findByText(/Ouverture du devis/)).toBeInTheDocument()
    expect(montageGenerateur).not.toHaveBeenCalled()
    await act(async () => { lecture.resolve(exemple('exemple_brouillon')) })
    expect((await screen.findByTestId('generateur-monte')).textContent).toBe('editId=412')
    expect(screen.queryByText(/Ouverture du devis/)).toBeNull()
    expect(erreur).not.toHaveBeenCalled()
    erreur.mockRestore()
  })

  it('aperçu AVANT la lecture : pas de bouton « Édition complète » ; il apparaît une fois le devis lu modifiable', async () => {
    const lecture = differe()
    ventesApi.getDevisById.mockReturnValue(lecture.promesse)
    rendre({ existingDevisId: 413 })
    expect(screen.queryByRole('button', { name: /Édition complète/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Réviser/ })).toBeNull()
    await act(async () => { lecture.resolve(exemple('exemple_envoye')) })
    expect(await screen.findByRole('button', { name: /Édition complète/ })).toBeInTheDocument()
  })

  it("lecture impossible d'un devis ouvert en edit : message d'erreur, aucun générateur, aucune édition offerte", async () => {
    ventesApi.getDevisById.mockRejectedValue(new Error('réseau'))
    rendre({ existingDevisId: 412, mode: 'edit' })
    expect(await screen.findByRole('alert')).toHaveTextContent(/n'a pas pu être ouvert/)
    expect(montageGenerateur).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /édition complète/i })).toBeNull()
    expect(screen.getByRole('button', { name: 'Fermer' })).toBeInTheDocument()
  })

  it("échec de la création automatique (aucun devis) : l'éditeur reste offert pour créer à la main", async () => {
    const detail = 'Consommation du site absente : renseignez les kWh mensuels du lead.'
    ventesApi.creerDevisAuto.mockRejectedValueOnce({ response: { status: 422, data: { detail } } })
    render(
      <Provider store={configureStore({ reducer: { r: (s = {}) => s } })}>
        <MemoryRouter>
          <LeadDevisPanel lead={{ id: 91, nom: 'Usine', type_installation: 'industriel' }}
                          mode="auto" onClose={vi.fn()} />
        </MemoryRouter>
      </Provider>,
    )
    expect(await screen.findByText(detail)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Ouvrir l'édition complète/ }))
    expect((await screen.findByTestId('generateur-monte')).textContent).toBe('editId=null')
  })
})
