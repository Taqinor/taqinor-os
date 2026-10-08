import { definirProfil, rendreParametresEntreprise } from '../../test/parametresEntrepriseHarness'
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'

/* APAR38 — l'écran Paramètres reflète le droit `parametres_modifier` (garde
   serveur ASEC31) : un Admin RH (palier responsable, sans le droit) voit la
   page en LECTURE SEULE (« Enregistrer » inerte) ; un Directeur écrit. */

const PROFIL = {
  id: 1, nom: 'Démo', rib: 'RIB', tva_standard: 20, tva_panneaux: 10,
  updated_at: '2026-10-08T10:00:00Z',
}

describe('APAR38 — droit parametres_modifier', () => {
  beforeEach(() => definirProfil(PROFIL))
  afterEach(cleanup)

  it('Admin RH : lecture seule, Enregistrer désactivé, champs inertes', async () => {
    const { container } = rendreParametresEntreprise({
      role: 'responsable', role_nom: 'Admin RH', permissions: ['rh_voir'],
    })
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    expect(screen.getByTestId('parametres-lecture-seule')).toHaveTextContent(/Lecture seule/)
    expect(screen.getByRole('button', { name: /Enregistrer/ })).toBeDisabled()
    expect(container.querySelector('input[name="nom"]')).toBeDisabled()
  })

  it('Directeur : écriture inchangée', async () => {
    const { container } = rendreParametresEntreprise({
      role: 'admin', role_nom: 'Directeur', permissions: ['parametres_modifier'],
    })
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    expect(screen.queryByTestId('parametres-lecture-seule')).toBeNull()
    expect(screen.getByRole('button', { name: /Enregistrer/ })).not.toBeDisabled()
    expect(container.querySelector('input[name="nom"]')).not.toBeDisabled()
  })

  it('compte hérité sans rôle fin (palier responsable) : comportement historique du serveur', async () => {
    const { container } = rendreParametresEntreprise({ role: 'responsable', role_nom: null, permissions: [] })
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    expect(screen.queryByTestId('parametres-lecture-seule')).toBeNull()
  })
})
