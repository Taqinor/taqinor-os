import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// AlertDialog (Radix) peut sonder matchMedia — même filet que
// ClientRgpdActions.test.jsx (autre écran utilisant AlertDialog).
function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

/* ODX5 — Onglet « Applications » : catalogue de modules (ODX3) admin-gated,
   toggle par module, confirmation de désactivation en cascade, motif
   (`raison`) affiché sous un module désactivé.

   ODY24 — la matrice ODX5 est CONSERVÉE ; trois attentes ont été adaptées à la
   boutique, parce que le comportement qu'elles assertaient a délibérément
   changé (jamais une spec cassée léguée à la tâche suivante) :
     1. l'état s'écrit « Installée » / « Disponible » (langage du Menu
        d'accueil) et non plus « Activé » / « Désactivé » ;
     2. les dépendances se lisent « Nécessite : … » ;
     3. la cascade est ANNONCÉE AVANT la bascule (aperçu calculé sur le graphe
        `depends` du catalogue déjà chargé) : désactiver un module dont un
        dépendant est actif n'envoie plus un premier appel voué au 400 — le
        dialogue s'ouvre d'abord. Le chemin 400 serveur reste testé plus bas
        comme FILET (divergence aperçu/serveur). */

const CATALOGUE = [
  {
    key: 'stock', label: 'Stock', icone: 'package', depends: [],
    installable: true, description: 'Gestion des stocks.', categorie: 'Stock', actif: true,
  },
  {
    key: 'sav', label: 'Après-vente', icone: 'wrench', depends: ['stock'],
    installable: true, description: '', categorie: 'Services', actif: true,
  },
  {
    key: 'flotte', label: 'Flotte', icone: 'truck', depends: [],
    installable: true, description: '', categorie: 'Stock', actif: false,
  },
  // ODY24 — module DISPONIBLE dont la dépendance est elle aussi disponible :
  // l'installer doit annoncer l'auto-install de « Flotte » avant de l'écrire.
  {
    key: 'logistique', label: 'Logistique', icone: 'truck', depends: ['flotte'],
    installable: true, description: '', categorie: 'Stock', actif: false,
  },
]

const TOGGLES = [
  { id: 10, module: 'flotte', actif: false, raison: 'Hors offre pilote' },
]

const { catalogue, activer, desactiver, listToggles } = vi.hoisted(() => ({
  catalogue: vi.fn(),
  activer: vi.fn(() => Promise.resolve({ data: { actives: [] } })),
  desactiver: vi.fn(),
  listToggles: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/coreApi', () => ({
  default: {
    modules: {
      catalogue, activer, desactiver,
      toggles: { list: listToggles },
    },
  },
}))

import ApplicationsSection from './ApplicationsSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderWithRole(role) {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(<Provider store={store}><ApplicationsSection /></Provider>)
}

describe('ApplicationsSection (ODX5 + boutique ODY24)', () => {
  it('un rôle non-admin voit un accès restreint (admin-gated, plus strict que responsable)', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    renderWithRole('responsable')
    expect(await screen.findByText('Accès restreint')).toBeInTheDocument()
    expect(catalogue).not.toHaveBeenCalled()
  })

  it('un admin voit le catalogue groupé par catégorie, avec état et motif', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    renderWithRole('admin')

    // « Stock » désigne à la fois le titre de la catégorie et le libellé du
    // module — on scope la recherche à la carte du module (data-testid) pour
    // ne pas être ambigu vis-à-vis du titre de groupe (même texte).
    const stockRow = await screen.findByTestId('module-row-stock')
    expect(within(stockRow).getByText('Stock')).toBeInTheDocument()
    expect(screen.getByText('Après-vente')).toBeInTheDocument()
    expect(screen.getByText('Flotte')).toBeInTheDocument()
    // Catégories du manifest rendues comme titres de groupe.
    expect(screen.getByText('Services')).toBeInTheDocument()
    // Dépendance affichée en clair (libellé résolu, pas la clé technique).
    expect(screen.getByText(/Nécessite : Stock/)).toBeInTheDocument()
    // Motif de désactivation affiché sous le module désactivé.
    expect(screen.getByText(/Motif : Hors offre pilote/)).toBeInTheDocument()
    // États rendus (langage boutique ODY24).
    expect(screen.getAllByText('Installée').length).toBe(2)
    expect(screen.getAllByText('Disponible').length).toBe(2)
  })

  it('active un module désactivé sans dépendance manquante (interrupteur → activer)', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('Flotte')

    await user.click(screen.getByRole('switch', { name: 'Activer le module Flotte' }))

    await waitFor(() => expect(activer).toHaveBeenCalledWith('flotte'))
  })

  it('désactive un module sans dépendant actif directement', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    desactiver.mockResolvedValueOnce({ data: { desactives: ['sav'] } })
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('Après-vente')

    await user.click(screen.getByRole('switch', { name: 'Désactiver le module Après-vente' }))

    await waitFor(() => expect(desactiver).toHaveBeenCalledWith('sav', { cascade: false }))
  })

  it('ODY24 — annonce la cascade AVANT la désactivation, puis désactive en cascade', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    desactiver.mockResolvedValueOnce({ data: { desactives: ['stock', 'sav'] } })
    const user = userEvent.setup()
    renderWithRole('admin')
    // « Stock » est ambigu (titre de catégorie + libellé de module) : on
    // attend la carte du module Stock via son data-testid.
    await screen.findByTestId('module-row-stock')

    await user.click(screen.getByRole('switch', { name: 'Désactiver le module Stock' }))

    // Aperçu AVANT tout appel serveur : aucune requête n'est partie.
    expect(await screen.findByText('Désactiver « Stock » ?')).toBeInTheDocument()
    expect(screen.getByText(/Les modules actifs suivants en dépendent : Après-vente/))
      .toBeInTheDocument()
    expect(desactiver).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Désactiver en cascade' }))

    await waitFor(() => expect(desactiver).toHaveBeenCalledWith('stock', { cascade: true }))
    expect(desactiver).toHaveBeenCalledTimes(1)
  })

  it('ODY24 — annonce l’auto-install des dépendances AVANT d’activer', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByTestId('module-row-logistique')

    await user.click(screen.getByRole('switch', { name: 'Activer le module Logistique' }))

    expect(await screen.findByText('Installer « Logistique » ?')).toBeInTheDocument()
    expect(screen.getByText(/Cette application a besoin de : Flotte/)).toBeInTheDocument()
    expect(activer).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Installer avec ses dépendances' }))

    await waitFor(() => expect(activer).toHaveBeenCalledWith('logistique'))
  })

  it('ODY24 — le 400 de dépendance reste le FILET si l’aperçu et le serveur divergent', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    desactiver
      .mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            detail: "Impossible de désactiver « sav » : les modules actifs suivants en dépendent — monitoring.",
            dependants: ['monitoring'],
          },
        },
      })
      .mockResolvedValueOnce({ data: { desactives: ['sav', 'monitoring'] } })
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('Après-vente')

    // Le catalogue chargé ne connaît aucun dépendant actif de « sav » : la
    // bascule part directement, et c'est le serveur qui ouvre le dialogue.
    await user.click(screen.getByRole('switch', { name: 'Désactiver le module Après-vente' }))

    expect(await screen.findByText('Désactiver « Après-vente » ?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Désactiver en cascade' }))

    await waitFor(() => expect(desactiver).toHaveBeenNthCalledWith(2, 'sav', { cascade: true }))
  })

  it('ODY24 — la recherche filtre la boutique (libellé, insensible aux accents)', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByTestId('module-row-stock')

    await user.type(screen.getByLabelText('Rechercher une application'), 'apres')

    await waitFor(() => expect(screen.queryByTestId('module-row-stock')).toBeNull())
    expect(screen.getByTestId('module-row-sav')).toBeInTheDocument()
  })
})
