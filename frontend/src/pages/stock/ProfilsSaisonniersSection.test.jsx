import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   AGR623 — profils saisonniers de réappro (saison d'irrigation) saisissables
   depuis la fiche produit. Le contrat partagé `profils_saisonniers.json` est
   LU (PACT10) : la charge utile n'est jamais recopiée à la main. */

const contrat = documentContrat('stock', 'profils_saisonniers')
const EXEMPLE = contrat.exemple

const { getProfils, createProfil, updateProfil, deleteProfil } = vi.hoisted(() => ({
  getProfils: vi.fn(),
  createProfil: vi.fn(),
  updateProfil: vi.fn(),
  deleteProfil: vi.fn(),
}))

vi.mock('../../api/stockApi', () => ({
  default: {
    getProfilsSaisonniers: (...a) => getProfils(...a),
    createProfilSaisonnier: (...a) => createProfil(...a),
    updateProfilSaisonnier: (...a) => updateProfil(...a),
    deleteProfilSaisonnier: (...a) => deleteProfil(...a),
  },
}))

import ProfilsSaisonniersSection from './ProfilsSaisonniersSection.jsx'

function wrapper({ children }) {
  return <MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter>
}

const PRODUIT = { id: EXEMPLE.produit, nom: EXEMPLE.produit_nom }

function renderSection(props = {}) {
  return render(<ProfilsSaisonniersSection produit={PRODUIT} canWrite {...props} />, { wrapper })
}

beforeEach(() => {
  vi.clearAllMocks()
  getProfils.mockResolvedValue({ data: { results: [] } })
  createProfil.mockResolvedValue({ data: EXEMPLE })
  updateProfil.mockResolvedValue({ data: EXEMPLE })
  deleteProfil.mockResolvedValue({ data: {} })
})

describe('AGR623 — création', () => {
  it('le formulaire part VIDE (aucun défaut) et la création envoie les valeurs tapées', async () => {
    renderSection()
    await screen.findByText(/Aucun profil saisonnier/)
    fireEvent.click(screen.getByRole('button', { name: /Ajouter un profil/ }))

    for (const libelle of ['Nom', 'Mois de début', 'Mois de fin', 'Seuil minimum', 'Seuil maximum', 'Quantité cible']) {
      expect(screen.getByLabelText(libelle)).toHaveValue(libelle === 'Nom' ? '' : null)
    }
    // jamais de snap : step="any" sur les nombres, formulaire noValidate
    expect(screen.getByLabelText('Mois de début')).toHaveAttribute('step', 'any')
    expect(screen.getByTestId('profil-saisonnier-form')).toHaveAttribute('novalidate')

    fireEvent.change(screen.getByLabelText('Nom'), { target: { value: EXEMPLE.nom } })
    fireEvent.change(screen.getByLabelText('Mois de début'), { target: { value: String(EXEMPLE.mois_debut) } })
    fireEvent.change(screen.getByLabelText('Mois de fin'), { target: { value: String(EXEMPLE.mois_fin) } })
    fireEvent.change(screen.getByLabelText('Seuil minimum'), { target: { value: String(EXEMPLE.seuil_min) } })
    fireEvent.change(screen.getByLabelText('Quantité cible'), { target: { value: String(EXEMPLE.quantite_cible) } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le profil' }))

    await waitFor(() => expect(createProfil).toHaveBeenCalledTimes(1))
    expect(createProfil.mock.calls[0][0]).toEqual({
      produit: EXEMPLE.produit,
      nom: EXEMPLE.nom,
      mois_debut: EXEMPLE.mois_debut,
      mois_fin: EXEMPLE.mois_fin,
      seuil_min: EXEMPLE.seuil_min,
      seuil_max: null, // laissé vide : null, jamais 0
      quantite_cible: EXEMPLE.quantite_cible,
    })
    // Toutes les clés envoyées existent dans le contrat.
    for (const cle of Object.keys(createProfil.mock.calls[0][0])) {
      expect(Object.keys(EXEMPLE)).toContain(cle)
    }
  })

  it('le 400 de chevauchement s’affiche sous le champ des mois', async () => {
    createProfil.mockRejectedValue({
      response: { status: 400, data: contrat.exemple_erreur_chevauchement },
    })
    renderSection()
    await screen.findByText(/Aucun profil saisonnier/)
    fireEvent.click(screen.getByRole('button', { name: /Ajouter un profil/ }))
    fireEvent.change(screen.getByLabelText('Mois de début'), { target: { value: '6' } })
    fireEvent.change(screen.getByLabelText('Mois de fin'), { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le profil' }))

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(contrat.exemple_erreur_chevauchement.detail)
    // l'erreur est rattachée aux champs de mois, et le formulaire reste ouvert
    expect(screen.getByLabelText('Mois de début')).toHaveAttribute('aria-describedby', alerte.id)
    expect(screen.getByLabelText('Mois de fin')).toHaveAttribute('aria-describedby', alerte.id)
    expect(screen.getByTestId('profil-saisonnier-form')).toBeInTheDocument()
  })

  it('une erreur par champ du serveur s’affiche sous CE champ', async () => {
    createProfil.mockRejectedValue({
      response: { status: 400, data: { quantite_cible: ['Doit être un nombre.'] } },
    })
    renderSection()
    await screen.findByText(/Aucun profil saisonnier/)
    fireEvent.click(screen.getByRole('button', { name: /Ajouter un profil/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le profil' }))
    expect(await screen.findByText('Doit être un nombre.')).toBeInTheDocument()
  })
})

describe('AGR623 — liste, modification, suppression', () => {
  beforeEach(() => {
    getProfils.mockResolvedValue({ data: { results: [EXEMPLE] } })
  })

  it('liste les profils du produit (filtrés par produit)', async () => {
    renderSection()
    const ligne = await screen.findByTestId(`profil-saisonnier-${EXEMPLE.id}`)
    expect(ligne).toHaveTextContent(EXEMPLE.nom)
    expect(ligne).toHaveTextContent(`mois ${EXEMPLE.mois_debut} → ${EXEMPLE.mois_fin}`)
    expect(getProfils).toHaveBeenCalledWith({ produit: EXEMPLE.produit })
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = le même PATCH', async () => {
    renderSection()
    await screen.findByTestId(`profil-saisonnier-${EXEMPLE.id}`)

    const patches = []
    for (let passage = 0; passage < 2; passage += 1) {
      fireEvent.click(screen.getByRole('button', { name: `Modifier le profil ${EXEMPLE.nom}` }))
      fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le profil' }))
      await waitFor(() => expect(updateProfil).toHaveBeenCalledTimes(passage + 1))
      patches.push(updateProfil.mock.calls[passage])
      await waitFor(() => expect(screen.queryByTestId('profil-saisonnier-form')).not.toBeInTheDocument())
    }
    expect(patches[0]).toEqual(patches[1])
    expect(patches[0][0]).toBe(EXEMPLE.id)
    expect(patches[0][1]).toEqual({
      nom: EXEMPLE.nom,
      mois_debut: EXEMPLE.mois_debut,
      mois_fin: EXEMPLE.mois_fin,
      seuil_min: EXEMPLE.seuil_min,
      seuil_max: null,
      quantite_cible: EXEMPLE.quantite_cible,
    })
  })

  it('supprime un profil', async () => {
    renderSection()
    await screen.findByTestId(`profil-saisonnier-${EXEMPLE.id}`)
    fireEvent.click(screen.getByRole('button', { name: `Supprimer le profil ${EXEMPLE.nom}` }))
    await waitFor(() => expect(deleteProfil).toHaveBeenCalledWith(EXEMPLE.id))
  })

  it('en lecture seule : la liste se voit, aucun bouton d’écriture', async () => {
    renderSection({ canWrite: false })
    const ligne = await screen.findByTestId(`profil-saisonnier-${EXEMPLE.id}`)
    expect(within(ligne).queryByRole('button')).toBeNull()
    expect(screen.queryByRole('button', { name: /Ajouter un profil/ })).toBeNull()
  })
})
