import {
  definirProfil, rendreParametresEntreprise, updateProfile,
} from '../../test/parametresEntrepriseHarness'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import crmApi from '../../api/crmApi'
import { diffProfilePayload } from './peConstants'

/* APAR16 — l'écran Paramètres (profil société) n'envoie que le SEUL diff des
   champs modifiés + l'`updated_at` lu au chargement (verrou optimiste). Avant :
   `{...form}` complet → l'enregistrement de A réécrivait le RIB que B venait
   de changer. */

const PROFIL = {
  id: 1, nom: 'Démo', rib: 'RIB-B', tva_standard: 20, tva_panneaux: 10,
  ice: '', email: '', telephone: '', updated_at: '2026-10-08T10:00:00.123456Z',
}

describe('APAR16 — diffProfilePayload', () => {
  it('ne garde que les clés modifiées + updated_at', () => {
    const base = { rib: 'B', tva_standard: 20, payment_terms: { r: [1, 2] } }
    const next = { rib: 'B', tva_standard: 14, payment_terms: { r: [1, 2] } }
    expect(diffProfilePayload(base, next, 'T0')).toEqual({ tva_standard: 14, updated_at: 'T0' })
  })
  it('objets imbriqués comparés par valeur', () => {
    const base = { payment_terms: { r: [1, 2] } }
    const next = { payment_terms: { r: [1, 3] } }
    expect(diffProfilePayload(base, next, 'T')).toEqual({ payment_terms: { r: [1, 3] }, updated_at: 'T' })
  })
})

describe('APAR16 — Enregistrer envoie le seul champ modifié', () => {
  beforeEach(() => {
    definirProfil(PROFIL)
    updateProfile.mockImplementation((data) => Promise.resolve({ data: { ...PROFIL, ...data } }))
  })
  afterEach(() => { cleanup(); updateProfile.mockReset() })

  it('seul le champ modifié part (avec updated_at), jamais le RIB', async () => {
    const { container } = rendreParametresEntreprise()
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    const nom = container.querySelector('input[name="nom"]')
    fireEvent.change(nom, { target: { name: 'nom', value: 'Démo SARL' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    const envoye = updateProfile.mock.calls[0][0]
    expect(envoye).toEqual({ nom: 'Démo SARL', updated_at: PROFIL.updated_at })
    expect(envoye).not.toHaveProperty('rib')
  })
})

describe('APAR73 — le verrou suit les écritures instantanées du profil', () => {
  const T1 = '2026-10-08T10:05:00.654321Z'
  const T2 = '2026-10-08T10:06:00.111111Z'
  const UTILISATEURS = [{ id: 7, username: 'sami', poste: 'Commercial' }]

  async function ouvrirOnglet(container, libelle, champ) {
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    fireEvent.click(screen.getAllByRole('button', { name: libelle })[0])
    await waitFor(() => expect(container.querySelector(`input[name="${champ}"]`)).not.toBeNull())
    return container.querySelector(`input[name="${champ}"]`)
  }

  // Le premier PATCH (écriture instantanée) rend T1, le suivant (Enregistrer) T2.
  function repondreAvecHorodatages() {
    updateProfile.mockImplementation((data) => Promise.resolve({
      data: { ...PROFIL, ...data, updated_at: updateProfile.mock.calls.length === 1 ? T1 : T2 },
    }))
  }

  beforeEach(() => {
    definirProfil({ ...PROFIL, lead_sla_hours: 24 })
    repondreAvecHorodatages()
  })
  afterEach(() => {
    cleanup(); updateProfile.mockReset()
    delete crmApi.getAssignableUsers
  })

  it('Enregistrer après le choix du responsable pro porte le nouvel updated_at', async () => {
    // Le double de `crmApi` (harnais) est un Proxy : on pose la méthode, on la retire après.
    crmApi.getAssignableUsers = vi.fn(() => Promise.resolve({ data: UTILISATEURS }))
    const user = userEvent.setup()
    const { container } = rendreParametresEntreprise()
    const sla = await ouvrirOnglet(container, 'Leads', 'lead_sla_hours')
    fireEvent.change(sla, { target: { name: 'lead_sla_hours', value: '48' } })
    await user.click(screen.getByRole('combobox', {
      name: /Responsable des leads commerciaux et industriels/i }))
    await user.click(await screen.findByRole('option', { name: /sami/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile.mock.calls[0][0]).toEqual({ responsable_leads_pro: 7 })
    // La saisie d'avant le choix n'a pas été resynchronisée par le serveur.
    expect(container.querySelector('input[name="lead_sla_hours"]')).toHaveValue(48)
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(2))
    expect(updateProfile.mock.calls[1][0]).toEqual({ lead_sla_hours: 48, updated_at: T1 })
    expect(await screen.findByText(/Profil enregistré avec succès/)).toBeInTheDocument()
  })

  it('Enregistrer après le consentement benchmarking porte le nouvel updated_at', async () => {
    const user = userEvent.setup()
    const { container } = rendreParametresEntreprise()
    const sla = await ouvrirOnglet(container, 'Leads', 'lead_sla_hours')
    fireEvent.change(sla, { target: { name: 'lead_sla_hours', value: '48' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Confidentialité' })[0])
    const consentement = await screen.findByRole('checkbox', { name: /benchmarking anonymisé/i })
    await waitFor(() => expect(consentement).not.toBeDisabled())
    await user.click(consentement)
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile.mock.calls[0][0]).toEqual({ benchmarking_opt_in: true })
    fireEvent.click(screen.getAllByRole('button', { name: 'Leads' })[0])
    await waitFor(() => expect(container.querySelector('input[name="lead_sla_hours"]')).toHaveValue(48))
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(2))
    expect(updateProfile.mock.calls[1][0]).toEqual({ lead_sla_hours: 48, updated_at: T1 })
  })
})

describe('APAR16 — 409 : Recharger garde la saisie de A', () => {
  const T1 = '2026-10-08T10:07:00.222222Z'
  const CONFLIT = {
    response: {
      status: 409,
      data: {
        detail: 'Le profil a été modifié par Bob entre-temps : recharger la page avant d\'enregistrer.',
        code: 'profil_modifie',
        updated_at: T1,
      },
    },
  }
  beforeEach(() => { definirProfil(PROFIL) })
  afterEach(() => { cleanup(); updateProfile.mockReset() })

  it('Recharger relit le serveur, garde le nom de A et renvoie le nouvel updated_at', async () => {
    updateProfile.mockRejectedValueOnce(CONFLIT)
    updateProfile.mockImplementation((data) => Promise.resolve({ data: { ...PROFIL, ...data } }))
    const { container } = rendreParametresEntreprise()
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    fireEvent.change(container.querySelector('input[name="nom"]'),
      { target: { name: 'nom', value: 'Démo A' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    // B a écrit entre-temps : le serveur sert désormais le RIB de B et T1.
    definirProfil({ ...PROFIL, rib: 'RIB-B2', updated_at: T1 })
    const recharger = await screen.findByRole('button', { name: 'Recharger les valeurs du serveur' })
    expect(screen.getByText(/modifié par Bob/)).toBeInTheDocument()
    fireEvent.click(recharger)
    await waitFor(() => expect(container.querySelector('input[name="rib"]')).toHaveValue('RIB-B2'))
    expect(container.querySelector('input[name="nom"]')).toHaveValue('Démo A')
    expect(screen.queryByText(/modifié par Bob/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(2))
    expect(updateProfile.mock.calls[1][0]).toEqual({ nom: 'Démo A', updated_at: T1 })
    expect(await screen.findByText(/Profil enregistré avec succès/)).toBeInTheDocument()
  })

  it('sans conflit de verrou, aucun bouton Recharger', async () => {
    updateProfile.mockRejectedValueOnce({ response: { status: 400, data: { nom: ['Nom invalide.'] } } })
    const { container } = rendreParametresEntreprise()
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    fireEvent.change(container.querySelector('input[name="nom"]'),
      { target: { name: 'nom', value: 'X' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('button', { name: 'Recharger les valeurs du serveur' })).toBeNull()
  })
})
