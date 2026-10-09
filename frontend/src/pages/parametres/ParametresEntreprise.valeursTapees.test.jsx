import {
  definirProfil, rendreParametresEntreprise, updateProfile,
} from '../../test/parametresEntrepriseHarness'
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* APAR39 — le profil société envoie les valeurs TAPÉES telles quelles : vider
   « SLA lead » n'envoie plus 0 (SLA désactivé) en silence, taper 0 dans le
   tarif ONEE n'est plus remplacé par 1.75. Le serveur juge (400 sous le
   champ). */

const PROFIL = {
  id: 1, nom: 'Démo', rib: 'RIB', tva_standard: 20, tva_panneaux: 10,
  lead_sla_hours: 24, onee_tarif_kwh: 1.75, productible_kwh_kwc: 1600,
  updated_at: '2026-10-08T10:00:00Z',
}

async function ouvrirOnglet(container, libelle, champ) {
  await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
  fireEvent.click(screen.getAllByRole('button', { name: libelle })[0])
  await waitFor(() => expect(container.querySelector(`input[name="${champ}"]`)).not.toBeNull())
  return container.querySelector(`input[name="${champ}"]`)
}

describe('APAR39 — valeurs tapées telles quelles', () => {
  beforeEach(() => {
    definirProfil(PROFIL)
    updateProfile.mockImplementation(() => Promise.reject({ response: { data: {
      lead_sla_hours: ['Un nombre entier valide est requis.'] } } }))
  })
  afterEach(() => { cleanup(); updateProfile.mockReset() })

  it('SLA lead vidé : part vide (jamais 0 en silence)', async () => {
    const { container } = rendreParametresEntreprise()
    const sla = await ouvrirOnglet(container, 'Leads', 'lead_sla_hours')
    fireEvent.change(sla, { target: { name: 'lead_sla_hours', value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile.mock.calls[0][0]).toEqual({ lead_sla_hours: '', updated_at: PROFIL.updated_at })
    // Le refus serveur s'affiche (bandeau qui nomme l'erreur).
    expect(await screen.findByText(/nombre entier valide/)).toBeInTheDocument()
  })

  it('SLA 1.5 : part 1.5 (le serveur juge), jamais tronqué', async () => {
    const { container } = rendreParametresEntreprise()
    const sla = await ouvrirOnglet(container, 'Leads', 'lead_sla_hours')
    fireEvent.change(sla, { target: { name: 'lead_sla_hours', value: '1.5' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile.mock.calls[0][0].lead_sla_hours).toBe(1.5)
  })

  it('tarif ONEE 0 : part 0, jamais 1.75', async () => {
    const { container } = rendreParametresEntreprise()
    const onee = await ouvrirOnglet(container, 'Avancé', 'onee_tarif_kwh')
    fireEvent.change(onee, { target: { name: 'onee_tarif_kwh', value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile.mock.calls[0][0].onee_tarif_kwh).toBe(0)
  })
})
