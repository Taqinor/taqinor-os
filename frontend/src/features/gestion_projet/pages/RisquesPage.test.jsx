import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gestionProjetApi from '../../../api/gestionProjetApi'
import RisquesPage from './RisquesPage'

/* ZPRJ7-9 — Lien d'évaluation CSAT (idempotent), rapport d'avancement PDF
   (WeasyPrint interne — jamais le moteur premium client) et heatmap des
   risques (P × I) dans RisquesPage. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getProjets: vi.fn(() => Promise.resolve({ data: [{ id: 10, code: 'P-1', nom: 'Villa Fès' }] })),
    getRisques: vi.fn(() => Promise.resolve({ data: [] })),
    getActions: vi.fn(() => Promise.resolve({ data: [] })),
    getComptesRendus: vi.fn(() => Promise.resolve({ data: [] })),
    getDocuments: vi.fn(() => Promise.resolve({ data: [] })),
    getCommentaires: vi.fn(() => Promise.resolve({ data: [] })),
    getModeles: vi.fn(() => Promise.resolve({ data: [] })),
    // WIR87 — le carnet lit/écrit désormais le master DC34
    // (`installations/sous-traitants/`), plus `gestion_projet.SousTraitant`.
    getSousTraitantsMaster: vi.fn(() => Promise.resolve({ data: [] })),
    createSousTraitantMaster: vi.fn(() => Promise.resolve({ data: {} })),
    updateSousTraitantMaster: vi.fn(() => Promise.resolve({ data: {} })),
    getLotsSousTraitance: vi.fn(() => Promise.resolve({ data: [] })),
    getMatriceRisques: vi.fn(() => Promise.resolve({
      data: {
        grille: [{ probabilite: 4, impact: 5, nombre: 2 }],
        total_ouverts_surveilles: 2,
        top_risques: [{ id: 1, libelle: 'Retard livraison onduleur', probabilite: 4, impact: 5, criticite: 20, statut: 'ouvert' }],
      },
    })),
    getLienEvaluation: vi.fn(() => Promise.resolve({ data: { projet_id: 10, token: 'abc123', deja_soumis: false } })),
    getRapportAvancementPdf: vi.fn(() => Promise.resolve({ data: new Blob(['pdf']), headers: {} })),
    // WIR203 — écriture des 6 ressources UX42 (16 fonctions CRUD jusqu'ici
    // orphelines) + dépôt d'une révision de document.
    createRisque: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    updateRisque: vi.fn(() => Promise.resolve({ data: {} })),
    createAction: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
    updateAction: vi.fn(() => Promise.resolve({ data: {} })),
    createCompteRendu: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
    updateCompteRendu: vi.fn(() => Promise.resolve({ data: {} })),
    createDocument: vi.fn(() => Promise.resolve({ data: { id: 4 } })),
    deposerVersionDocument: vi.fn(() => Promise.resolve({ data: { id: 5 } })),
    createCommentaire: vi.fn(() => Promise.resolve({ data: { id: 6 } })),
    createLotSousTraitance: vi.fn(() => Promise.resolve({ data: { id: 7 } })),
    updateLotSousTraitance: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('RisquesPage — ZPRJ7-9', () => {
  it('affiche la matrice des risques après sélection du projet', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await waitFor(() => expect(gestionProjetApi.getMatriceRisques).toHaveBeenCalledWith('10'))
    await user.click(screen.getByRole('tab', { name: 'Matrice P × I' }))
    expect(await screen.findByText('Retard livraison onduleur')).toBeInTheDocument()
  })

  it('« Lien CSAT » appelle l\'action serveur dédiée', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await user.click(await screen.findByRole('button', { name: /Lien CSAT/ }))
    await waitFor(() => expect(gestionProjetApi.getLienEvaluation).toHaveBeenCalledWith('10'))
  })

  it('« Rapport PDF » télécharge le rapport d\'avancement', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await user.click(await screen.findByRole('button', { name: /Rapport PDF/ }))
    await waitFor(() => expect(gestionProjetApi.getRapportAvancementPdf).toHaveBeenCalledWith('10'))
  })
})

/* WIR203 — l'onglet était 100 % lecture seule : 16 fonctions CRUD sans aucun
   appelant. Les 6 ressources sont désormais créables depuis l'écran, le projet
   sélectionné est PRÉ-REMPLI (jamais saisi), et la page recharge après écriture
   — donc la matrice P × I est recalculée par le serveur. */
describe('RisquesPage — WIR203 : les 6 ressources sont écrivables', () => {
  const choisirProjet = async (user) => {
    withProviders(<RisquesPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await waitFor(() => expect(gestionProjetApi.getMatriceRisques).toHaveBeenCalledWith('10'))
  }

  it('crée un risque avec le projet pré-rempli (criticité laissée au serveur)', async () => {
    const user = userEvent.setup()
    await choisirProjet(user)

    await user.click(await screen.findByRole('button', { name: /Nouveau risque/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/^Libellé/), 'Retard onduleur')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(gestionProjetApi.createRisque).toHaveBeenCalledWith(
      expect.objectContaining({ projet: '10', libelle: 'Retard onduleur' })))
    const corps = gestionProjetApi.createRisque.mock.calls[0][0]
    // Champs posés/calculés côté serveur : jamais envoyés.
    expect(corps).not.toHaveProperty('criticite')
    expect(corps).not.toHaveProperty('company')
    // La matrice est rechargée après écriture (recalcul serveur).
    await waitFor(() => expect(gestionProjetApi.getMatriceRisques.mock.calls.length)
      .toBeGreaterThan(1))
  })

  it('crée une action avec le projet pré-rempli', async () => {
    const user = userEvent.setup()
    await choisirProjet(user)

    await user.click(await screen.findByRole('tab', { name: 'Actions' }))
    await user.click(await screen.findByRole('button', { name: /Nouvelle action/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/^Libellé/), 'Relancer le fournisseur')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(gestionProjetApi.createAction).toHaveBeenCalledWith(
      expect.objectContaining({
        projet: '10', libelle: 'Relancer le fournisseur',
        priorite: 'moyenne', statut: 'a_faire',
      })))
    expect(gestionProjetApi.createAction.mock.calls[0][0]).not.toHaveProperty('company')
  })

  it('sans projet sélectionné, la création reste désactivée', async () => {
    withProviders(<RisquesPage />)
    expect((await screen.findAllByRole('button', { name: /Nouveau risque/ }))[0]).toBeDisabled()
  })
})

describe('RisquesPage — carnet de sous-traitants sur le master DC34 (WIR87)', () => {
  it('lit le carnet via le master (installations/sous-traitants/), plus le carnet local', async () => {
    gestionProjetApi.getSousTraitantsMaster.mockResolvedValueOnce({
      data: [{
        id: 7, raison_sociale: 'Terrass’Pro', metier: 'terrassement',
        metier_display: 'Terrassement', contact_nom: 'Karim', telephone: '0600000000',
        actif: true,
      }],
    })
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Sous-traitance' }))

    // DataTable rend la table desktop ET le repli carte mobile (CSS seul,
    // les deux existent dans le DOM en jsdom) : getAllByText, premier match.
    expect((await screen.findAllByText('Terrass’Pro'))[0]).toBeInTheDocument()
    expect(screen.getAllByText('Terrassement')[0]).toBeInTheDocument()
    expect(gestionProjetApi.getSousTraitantsMaster).toHaveBeenCalled()
    expect(gestionProjetApi.getSousTraitants).toBeUndefined()
  })

  it('crée un sous-traitant via le master — jamais le carnet local', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Sous-traitance' }))
    await user.click(await screen.findByRole('button', { name: /Nouveau sous-traitant/ }))

    const dialog = await screen.findByRole('dialog')
    // Label « Raison sociale » requis : le champ affiche un « * » additionnel
    // (Label required, cf. ui/Label.jsx) → correspondance en préfixe.
    await user.type(within(dialog).getByLabelText(/^Raison sociale/), 'Élec’Sud')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(gestionProjetApi.createSousTraitantMaster).toHaveBeenCalledWith(
        expect.objectContaining({ raison_sociale: 'Élec’Sud', metier: 'autre' }))
    })
    expect(gestionProjetApi.getSousTraitantsMaster).toHaveBeenCalledTimes(2) // chargement initial + rechargement post-création
  })

  it('modifier un sous-traitant existant appelle updateSousTraitantMaster', async () => {
    gestionProjetApi.getSousTraitantsMaster.mockResolvedValue({
      data: [{
        id: 7, raison_sociale: 'Terrass’Pro', metier: 'terrassement',
        metier_display: 'Terrassement', contact_nom: 'Karim', telephone: '0600000000',
        actif: true,
      }],
    })
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Sous-traitance' }))
    await screen.findAllByText('Terrass’Pro')

    await user.click(screen.getAllByRole('button', { name: 'Modifier' })[0])
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(gestionProjetApi.updateSousTraitantMaster).toHaveBeenCalledWith(
        7, expect.objectContaining({ raison_sociale: 'Terrass’Pro' }))
    })
  })
})
