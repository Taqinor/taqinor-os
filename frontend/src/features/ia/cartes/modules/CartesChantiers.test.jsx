import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'
import { CONTRATS_CARTES, CONTRATS_JUMEAUX } from '../contrats'
import { COMPOSANTS } from '../registre'

/* Nouveau fichier car : composant neuf, aucun module de test existant. Payloads = échantillons
   committés des contrats, jamais écrits à la main. */

const { ouvrir } = vi.hoisted(() => ({ ouvrir: vi.fn() }))
vi.mock('../useCarte', () => ({ useOuvrirEcran: () => ouvrir }))
beforeEach(() => ouvrir.mockClear())

/** Rend la carte `cle` avec son échantillon (ou celui de son jumeau, servi par une autre action). */
function monter(cle, { variante = 'exemple', jumeau = false } = {}) {
  const [app, nom] = (jumeau ? CONTRATS_JUMEAUX : CONTRATS_CARTES)[cle]
  const Carte = COMPOSANTS[cle]
  return render(<Carte carte={{ type: 'resultat', carte: cle, donnees: exempleContrat(app, nom, variante) }} />)
}

describe('liste_chantiers', () => {
  it('chantiers bloqués : blocages, prochain geste, lien vers le chantier', async () => {
    monter('liste_chantiers')
    expect(screen.getByText(/Chantiers bloqués \(2\)/)).toBeInTheDocument()
    expect(screen.getByText(/CHT-202611-0012 — Driss Lahlou/)).toBeInTheDocument()
    expect(screen.getAllByText('Pas de technicien').length).toBe(1)
    expect(screen.getByText('Acompte non encaissé')).toBeInTheDocument()
    expect(screen.getByText(/À faire : Encaisser l’acompte/)).toBeInTheDocument()
    expect(screen.getByText(/Matériel : lire installations.chantier.etat/)).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: 'Ouvrir le chantier' })[1])
    expect(ouvrir).toHaveBeenCalledWith('/chantiers?id=9')
  })

  it('poses de la semaine : rien à débloquer, le geste est « Poser »', () => {
    monter('liste_chantiers', { variante: 'exemple_poses_semaine' })
    expect(screen.getByText(/Chantiers poses de la semaine \(1\)/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Poser/)).toBeInTheDocument()
    expect(screen.queryByText('Pas de technicien')).not.toBeInTheDocument()
  })
})

describe('fiche_chantier', () => {
  it('pas prêt : raisons, matériel en quantités, aucune notion de prix', () => {
    monter('fiche_chantier')
    expect(screen.getByText('Pas prêt à poser')).toBeInTheDocument()
    expect(screen.getByText('1 article en manque')).toBeInTheDocument()
    expect(screen.getByText(/Tableau de protection AC\/DC : manque 1/)).toBeInTheDocument()
    expect(screen.getByText(/À faire : Commander le matériel/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/MAD|prix|coût/i)
    expect(screen.queryByRole('button', { name: 'Intervention de pose' })).not.toBeInTheDocument()
  })

  it('prêt à poser : intervention de pose et son lien', async () => {
    monter('fiche_chantier', { variante: 'exemple_pret' })
    expect(screen.getByText('Prêt à poser')).toBeInTheDocument()
    expect(screen.getByText(/Hamza Idrissi · prête/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Intervention de pose' }))
    expect(ouvrir).toHaveBeenCalledWith('/interventions?id=55')
  })

  it('jumeau (pose planifiée) : la date et le technicien rendus', () => {
    monter('fiche_chantier', { jumeau: true })
    expect(screen.getByText(/à préparer/)).toBeInTheDocument()
    expect(screen.getByText('Hamza Idrissi')).toBeInTheDocument()
  })
})
