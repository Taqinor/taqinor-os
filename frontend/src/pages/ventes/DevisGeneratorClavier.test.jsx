// EDC5 — clavier de l'Édition complète : Entrée n'enregistre JAMAIS le devis
// (la soumission implicite du navigateur faisait quitter l'éditeur) ; Entrée
// dans une cellule de la table passe au même champ de la ligne suivante, et
// sur la dernière ligne ajoute une ligne ; Ctrl/Cmd+S enregistre (même chemin
// qu'un clic) ; Entrée dans le ProduitPicker ouvert garde son sens (sélection).
//
// `user-event` simule la soumission implicite (Entrée dans un champ ⇒ clic du
// bouton submit) : sans la garde, ces tests verraient `replaceLignesDevis`.
// Écran RÉEL rendu, API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorClavier.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import {
  PANNEAU, ONDULEUR, makeStoreGenerateur, renderGenerateurEdition,
  preparerApisGenerateur, attendreEdition,
} from '../../test/generateurEmbarque'

// EDC (gardes CI) : fabriques partagées — src/test/mocksApiDevis.js.
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock())

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'

const PANNEAU_JINKO = {
  id: 103, nom: 'Panneau Jinko Tiger 600W', prix_vente: 1000, tva: 10,
  is_archived: false, prix_achat: 700,
}

// Commercial responsable + `stock_creer` : la désignation est modifiable (QP2)
// — c'est elle qui reçoit le focus d'une ligne ajoutée par Entrée.
const RENOMMEUR = { roleNom: 'Commercial responsable', permissions: ['stock_creer'] }

const lignes = () => [...document.querySelectorAll('table.lines-table tbody tr[data-line-key]')]
const qteDe = (tr) => tr.querySelector('[data-role="line-qty"]')
const pause = (ms) => new Promise((r) => setTimeout(r, ms))

beforeEach(() => preparerApisGenerateur({
  stockApi, ventesApi, produits: [PANNEAU, PANNEAU_JINKO, ONDULEUR],
}))

async function ouvrir({ peutRenommer = true } = {}) {
  renderGenerateurEdition({}, { store: makeStoreGenerateur(peutRenommer ? RENOMMEUR : {}) })
  await attendreEdition({ designation: ONDULEUR.nom })
}

describe('EDC5 — Entrée n\'enregistre jamais le devis', () => {
  it('Entrée dans « Qté » : aucune soumission, focus sur la Qté de la ligne suivante', async () => {
    const user = userEvent.setup()
    await ouvrir()
    const [premiere, seconde] = lignes()
    await user.click(qteDe(premiere))
    await user.keyboard('{Enter}')
    await pause(300)
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(qteDe(seconde))
    // Écran inchangé : toujours l'éditeur, même nombre de lignes.
    expect(screen.getByRole('button', { name: /Enregistrer les modifications/ })).toBeInTheDocument()
    expect(lignes()).toHaveLength(2)
  })

  it('Entrée dans « Prix unit. » de la dernière ligne : une ligne de plus, focus sur sa désignation', async () => {
    const user = userEvent.setup()
    await ouvrir()
    const derniere = lignes().at(-1)
    await user.click(derniere.querySelector('td[data-label="Prix unit. TTC"] input'))
    await user.keyboard('{Enter}')
    await waitFor(() => expect(lignes()).toHaveLength(3))
    const nouvelle = lignes().at(-1)
    await waitFor(() => expect(document.activeElement)
      .toBe(nouvelle.querySelector('td[data-label="Désignation"] input')))
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
  })

  it('rôle sans droit de renommer (désignation verrouillée) : la ligne ajoutée reçoit le focus sur son sélecteur produit', async () => {
    const user = userEvent.setup()
    await ouvrir({ peutRenommer: false })
    await user.click(qteDe(lignes().at(-1)))
    await user.keyboard('{Enter}')
    await waitFor(() => expect(lignes()).toHaveLength(3))
    const nouvelle = lignes().at(-1)
    await waitFor(() => expect(document.activeElement)
      .toBe(within(nouvelle.querySelector('td[data-label="Produit (stock)"]')).getByRole('button')))
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
  })

  it('Entrée dans un champ hors table (puissance cible) et dans la désignation : aucune soumission', async () => {
    const user = userEvent.setup()
    await ouvrir()
    await user.click(screen.getByLabelText('Puissance cible (kWc)'))
    await user.keyboard('{Enter}')
    await user.click(lignes()[0].querySelector('td[data-label="Désignation"] input'))
    await user.keyboard('{Enter}')
    await pause(300)
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Enregistrer les modifications/ })).toBeInTheDocument()
  })

  it('Ctrl+S : enregistre UNE fois, par le chemin normal (replace-lines)', async () => {
    const user = userEvent.setup()
    await ouvrir()
    await user.click(screen.getByPlaceholderText(/Conditions particulières/))
    await user.keyboard('{Control>}s{/Control}')
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1))
    expect(ventesApi.replaceLignesDevis.mock.calls[0][0]).toBe(42)
    await pause(200)
    expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1)
  })

  it('Ctrl+Entrée dans une cellule : enregistre aussi', async () => {
    const user = userEvent.setup()
    await ouvrir()
    await user.click(qteDe(lignes()[0]))
    await user.keyboard('{Control>}{Enter}{/Control}')
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1))
  })

  it('Entrée dans le ProduitPicker ouvert garde son sens : elle SÉLECTIONNE, sans soumettre', async () => {
    const user = userEvent.setup()
    await ouvrir()
    const premiere = lignes()[0]
    const cellule = premiere.querySelector('td[data-label="Produit (stock)"]')
    await user.click(within(cellule).getByRole('button', { name: /Canadien Solar/ }))
    const recherche = await screen.findByPlaceholderText(/Chercher un produit/)
    await user.type(recherche, 'Jinko')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(within(cellule).getByRole('button', { name: /Jinko Tiger/ })).toBeInTheDocument())
    await waitFor(() => expect(premiere.querySelector('td[data-label="Désignation"] input'))
      .toHaveValue(PANNEAU_JINKO.nom))
    await pause(200)
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(lignes()).toHaveLength(2)
  })
})
