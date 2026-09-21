import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gestionProjetApi from '../../../api/gestionProjetApi'
import RisquesPage from './RisquesPage'

/* ZPRJ7-9 — Lien d'évaluation CSAT (idempotent), rapport d'avancement PDF
   (WeasyPrint interne — jamais le moteur premium client) et heatmap des
   risques (P × I) dans RisquesPage.

   WIR203 — l'onglet « Risques, actions & CR » était lecture seule totale sur
   6 ressources (risques/actions/CR/documents+versions/commentaires/lots) :
   16 fonctions `gestionProjetApi` orphelines. Ces tests couvrent les
   créations (risque/action explicitement requises) + un échantillon
   représentatif de modification/suppression/upload pour prouver le câblage. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getProjets: vi.fn(() => Promise.resolve({ data: [{ id: 10, code: 'P-1', nom: 'Villa Fès' }] })),
    getRisques: vi.fn(() => Promise.resolve({ data: [] })),
    createRisque: vi.fn(() => Promise.resolve({ data: {} })),
    updateRisque: vi.fn(() => Promise.resolve({ data: {} })),
    deleteRisque: vi.fn(() => Promise.resolve({ data: {} })),
    getActions: vi.fn(() => Promise.resolve({ data: [] })),
    createAction: vi.fn(() => Promise.resolve({ data: {} })),
    updateAction: vi.fn(() => Promise.resolve({ data: {} })),
    deleteAction: vi.fn(() => Promise.resolve({ data: {} })),
    getComptesRendus: vi.fn(() => Promise.resolve({ data: [] })),
    createCompteRendu: vi.fn(() => Promise.resolve({ data: {} })),
    updateCompteRendu: vi.fn(() => Promise.resolve({ data: {} })),
    deleteCompteRendu: vi.fn(() => Promise.resolve({ data: {} })),
    getDocuments: vi.fn(() => Promise.resolve({ data: [] })),
    createDocument: vi.fn(() => Promise.resolve({ data: {} })),
    deleteDocument: vi.fn(() => Promise.resolve({ data: {} })),
    getDocumentVersions: vi.fn(() => Promise.resolve({ data: [] })),
    deposerVersionDocument: vi.fn(() => Promise.resolve({ data: {} })),
    getCommentaires: vi.fn(() => Promise.resolve({ data: [] })),
    createCommentaire: vi.fn(() => Promise.resolve({ data: {} })),
    deleteCommentaire: vi.fn(() => Promise.resolve({ data: {} })),
    getModeles: vi.fn(() => Promise.resolve({ data: [] })),
    // WIR87 — le carnet lit/écrit désormais le master DC34
    // (`installations/sous-traitants/`), plus `gestion_projet.SousTraitant`.
    getSousTraitantsMaster: vi.fn(() => Promise.resolve({ data: [] })),
    createSousTraitantMaster: vi.fn(() => Promise.resolve({ data: {} })),
    updateSousTraitantMaster: vi.fn(() => Promise.resolve({ data: {} })),
    // WIR203 — carnet LOCAL, utilisé UNIQUEMENT pour peupler le sélecteur du
    // dialogue « Nouveau lot » (LotSousTraitance.sous_traitant y référence,
    // distinct du master DC34 — voir docstring LotForm).
    getSousTraitants: vi.fn(() => Promise.resolve({ data: [] })),
    getLotsSousTraitance: vi.fn(() => Promise.resolve({ data: [] })),
    createLotSousTraitance: vi.fn(() => Promise.resolve({ data: {} })),
    updateLotSousTraitance: vi.fn(() => Promise.resolve({ data: {} })),
    deleteLotSousTraitance: vi.fn(() => Promise.resolve({ data: {} })),
    getMatriceRisques: vi.fn(() => Promise.resolve({
      data: {
        grille: [{ probabilite: 4, impact: 5, nombre: 2 }],
        total_ouverts_surveilles: 2,
        top_risques: [{ id: 1, libelle: 'Retard livraison onduleur', probabilite: 4, impact: 5, criticite: 20, statut: 'ouvert' }],
      },
    })),
    getLienEvaluation: vi.fn(() => Promise.resolve({ data: { projet_id: 10, token: 'abc123', deja_soumis: false } })),
    getRapportAvancementPdf: vi.fn(() => Promise.resolve({ data: new Blob(['pdf']), headers: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

beforeEach(() => {
  // WIR203 — `confirmDelete` (useConfirmDialog) retombe sur `window.confirm`
  // natif hors <ConfirmProvider> (voir providers/confirm-context.js) : ce
  // banc de test n'en monte pas, comme les autres pages du module.
  window.confirm = vi.fn(() => true)
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

async function selectionnerProjet(user) {
  await screen.findByRole('option', { name: /Villa Fès/ })
  await user.selectOptions(screen.getByLabelText('Projet'), '10')
}

describe('RisquesPage — ZPRJ7-9', () => {
  it('affiche la matrice des risques après sélection du projet', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await waitFor(() => expect(gestionProjetApi.getMatriceRisques).toHaveBeenCalledWith('10'))
    await user.click(screen.getByRole('tab', { name: 'Matrice P × I' }))
    expect(await screen.findByText('Retard livraison onduleur')).toBeInTheDocument()
  })

  it('« Lien CSAT » appelle l\'action serveur dédiée', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('button', { name: /Lien CSAT/ }))
    await waitFor(() => expect(gestionProjetApi.getLienEvaluation).toHaveBeenCalledWith('10'))
  })

  it('« Rapport PDF » télécharge le rapport d\'avancement', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('button', { name: /Rapport PDF/ }))
    await waitFor(() => expect(gestionProjetApi.getRapportAvancementPdf).toHaveBeenCalledWith('10'))
  })
})

describe('RisquesPage — WIR203 registre des risques (CRUD câblé)', () => {
  it('« Nouveau risque » crée le risque via createRisque et recharge la matrice', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await waitFor(() => expect(gestionProjetApi.getMatriceRisques).toHaveBeenCalledTimes(1))

    await user.click(await screen.findByRole('button', { name: /Nouveau risque/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/^Libellé/), 'Retard livraison onduleur')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(gestionProjetApi.createRisque).toHaveBeenCalledWith(
        expect.objectContaining({
          projet: '10', libelle: 'Retard livraison onduleur', categorie: 'autre',
          probabilite: 1, impact: 1, statut: 'ouvert',
        }))
    })
    // Rechargement complet (dont la matrice — Done WIR203).
    await waitFor(() => expect(gestionProjetApi.getMatriceRisques).toHaveBeenCalledTimes(2))
  })

  it('« Modifier » un risque appelle updateRisque', async () => {
    gestionProjetApi.getRisques.mockResolvedValue({
      data: [{ id: 5, libelle: 'Fuite toiture', categorie: 'technique', probabilite: 3, impact: 4, criticite: 12, statut: 'ouvert' }],
    })
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    // WIR203 (fix Fable) — DataTable rend la table desktop ET le repli carte
    // mobile (CSS seul, les deux existent dans le DOM en jsdom) : findAllByText.
    await screen.findAllByText('Fuite toiture')

    const table = document.querySelector('[data-dt-table]')
    await user.click(within(table).getAllByLabelText("Plus d'actions sur la ligne")[0])
    await user.click(await screen.findByText('Modifier'))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(gestionProjetApi.updateRisque).toHaveBeenCalledWith(
      5, expect.objectContaining({ libelle: 'Fuite toiture' })))
  })

  it('« Supprimer » un risque appelle deleteRisque (après confirmation)', async () => {
    gestionProjetApi.getRisques.mockResolvedValue({
      data: [{ id: 5, libelle: 'Fuite toiture', categorie: 'technique', probabilite: 3, impact: 4, criticite: 12, statut: 'ouvert' }],
    })
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    // WIR203 (fix Fable) — DataTable rend la table desktop ET le repli carte
    // mobile (CSS seul, les deux existent dans le DOM en jsdom) : findAllByText.
    await screen.findAllByText('Fuite toiture')

    const table = document.querySelector('[data-dt-table]')
    await user.click(within(table).getAllByLabelText("Plus d'actions sur la ligne")[0])
    await user.click(await screen.findByText('Supprimer'))
    await waitFor(() => expect(gestionProjetApi.deleteRisque).toHaveBeenCalledWith(5))
  })
})

describe('RisquesPage — WIR203 plan d\'actions (CRUD câblé)', () => {
  it('« Nouvelle action » crée l\'action via createAction', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('tab', { name: 'Actions' }))
    await user.click(await screen.findByRole('button', { name: /Nouvelle action/ }))

    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/^Libellé/), 'Relancer le fournisseur')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(gestionProjetApi.createAction).toHaveBeenCalledWith(
        expect.objectContaining({
          projet: '10', libelle: 'Relancer le fournisseur', statut: 'a_faire', priorite: 'moyenne',
        }))
    })
  })
})

describe('RisquesPage — WIR203 comptes-rendus, documents & commentaires', () => {
  it('« Nouveau compte-rendu » crée le CR via createCompteRendu', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('tab', { name: 'Comptes-rendus' }))
    await user.click(await screen.findByRole('button', { name: /Nouveau compte-rendu/ }))

    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/^Titre/), 'Réunion de chantier')
    await user.type(within(dialog).getByLabelText(/^Date de la réunion/), '2026-08-20')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(gestionProjetApi.createCompteRendu).toHaveBeenCalledWith(
        expect.objectContaining({ projet: '10', titre: 'Réunion de chantier', date_reunion: '2026-08-20' }))
    })
  })

  it('« Ajouter une version » dépose un fichier via deposerVersionDocument', async () => {
    gestionProjetApi.getDocuments.mockResolvedValue({
      data: [{ id: 3, nom: 'Plan de calepinage', type_doc: 'plan', derniere_version: 1, versions: [] }],
    })
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('tab', { name: 'Documents' }))
    // WIR203 (fix Fable) — desktop + repli carte mobile : findAllByText.
    await screen.findAllByText('Plan de calepinage')

    const table = document.querySelector('[data-dt-table]')
    await user.click(within(table).getAllByLabelText("Plus d'actions sur la ligne")[0])
    await user.click(await screen.findByText('Ajouter une version'))

    const fichier = new File(['contenu'], 'plan-v2.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, fichier)

    await waitFor(() => expect(gestionProjetApi.deposerVersionDocument).toHaveBeenCalledWith(
      3, expect.any(FormData)))
  })

  it('« Ajouter » un commentaire appelle createCommentaire', async () => {
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('tab', { name: 'Documents' }))

    const zone = await screen.findByLabelText('Nouveau commentaire')
    await user.type(zone, 'À vérifier avec le client')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await waitFor(() => expect(gestionProjetApi.createCommentaire).toHaveBeenCalledWith(
      { projet: '10', texte: 'À vérifier avec le client', cible_type: 'projet' }))
  })

  it('supprimer un commentaire existant appelle deleteCommentaire', async () => {
    gestionProjetApi.getCommentaires.mockResolvedValue({
      data: [{ id: 9, texte: 'À vérifier avec le client', auteur_nom: 'Amine' }],
    })
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('tab', { name: 'Documents' }))
    await screen.findByText('À vérifier avec le client')

    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(gestionProjetApi.deleteCommentaire).toHaveBeenCalledWith(9))
  })
})

describe('RisquesPage — WIR203 lots de sous-traitance (carnet LOCAL distinct du master)', () => {
  it('« Nouveau lot » charge le carnet LOCAL (getSousTraitants) et crée via createLotSousTraitance', async () => {
    gestionProjetApi.getSousTraitants.mockResolvedValueOnce({
      data: [{ id: 42, nom: 'Terrass’Pro Local' }],
    })
    const user = userEvent.setup()
    withProviders(<RisquesPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('tab', { name: 'Sous-traitance' }))
    expect(gestionProjetApi.getSousTraitants).not.toHaveBeenCalled()

    await user.click(await screen.findByRole('button', { name: /Nouveau lot/ }))
    await waitFor(() => expect(gestionProjetApi.getSousTraitants).toHaveBeenCalledTimes(1))

    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/Libellé du lot/), 'Terrassement villa')
    await user.selectOptions(within(dialog).getByLabelText(/^Sous-traitant/), '42')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(gestionProjetApi.createLotSousTraitance).toHaveBeenCalledWith(
        expect.objectContaining({ projet: '10', sous_traitant: 42, libelle: 'Terrassement villa', statut: 'prevu' }))
    })
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
    // WIR203 — le carnet LOCAL existe désormais (dialogue Lot), mais n'est
    // JAMAIS appelé par le simple affichage du carnet DC34 ci-dessus.
    expect(gestionProjetApi.getSousTraitants).not.toHaveBeenCalled()
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
