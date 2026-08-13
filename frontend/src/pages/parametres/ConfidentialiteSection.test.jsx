import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* XPLT23 — Onglet « Confidentialité » : registre des traitements CNDP (CRUD)
   + demandes de personnes concernées (soumission/suivi), réservé
   admin/responsable. */

const {
  listRegistre, createRegistre, updateRegistre, removeRegistre, exportCsv,
  listDsr, createDsr, traiterDsr,
} = vi.hoisted(() => ({
  listRegistre: vi.fn(() => Promise.resolve({
    data: [{ id: 1, code: 'leads_clients', finalite: 'Gestion des prospects', base_legale: 'Consentement', actif: true }],
  })),
  createRegistre: vi.fn(() => Promise.resolve({ data: {} })),
  updateRegistre: vi.fn(() => Promise.resolve({ data: {} })),
  removeRegistre: vi.fn(() => Promise.resolve({ data: {} })),
  exportCsv: vi.fn(() => Promise.resolve({ data: new Blob(['x']), headers: {} })),
  listDsr: vi.fn(() => Promise.resolve({
    data: [{ id: 5, subject_identifier: 'client@x.ma', kind: 'acces', statut: 'recue' }],
  })),
  createDsr: vi.fn(() => Promise.resolve({ data: {} })),
  traiterDsr: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/coreApi', () => ({
  default: {
    confidentialite: {
      registreTraitements: {
        list: listRegistre, create: createRegistre, update: updateRegistre,
        remove: removeRegistre, exportCsv,
      },
      dsrRequests: { list: listDsr, create: createDsr, traiter: traiterDsr },
    },
  },
}))

vi.mock('../../api/importApi', () => ({
  downloadBlob: vi.fn(),
  filenameFromResponse: vi.fn(() => 'registre-traitements-cndp.csv'),
}))

/* PACT119 — le bloc « Registre de consentement » consomme
   `/core/consent-records/` directement via l'instance axios. */
const { axiosGet, axiosPost, axiosPatch } = vi.hoisted(() => ({
  axiosGet: vi.fn(() => Promise.resolve({
    data: [{
      id: 3, subject_identifier: 'prospect@x.ma', purpose: 'marketing',
      granted: true, version_texte: 'v1-2026-07', ip_confirmation: '41.10.0.1',
    }],
  })),
  axiosPost: vi.fn(() => Promise.resolve({ data: {} })),
  axiosPatch: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/axios', () => ({
  default: { get: axiosGet, post: axiosPost, patch: axiosPatch },
}))

import ConfidentialiteSection from './ConfidentialiteSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderWithRole(role) {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(<Provider store={store}><ConfidentialiteSection /></Provider>)
}

describe('ConfidentialiteSection (XPLT23)', () => {
  it('un rôle non-admin/responsable voit un accès restreint', async () => {
    renderWithRole('normal')
    expect(await screen.findByText('Accès restreint')).toBeInTheDocument()
    expect(listRegistre).not.toHaveBeenCalled()
  })

  it('liste le registre des traitements et les demandes DSR pour un admin', async () => {
    renderWithRole('admin')

    expect(await screen.findByText('leads_clients')).toBeInTheDocument()
    expect(screen.getByText('Gestion des prospects')).toBeInTheDocument()
    expect(screen.getByText('client@x.ma')).toBeInTheDocument()
    expect(screen.getAllByText('Accès (export)').length).toBeGreaterThan(0)
  })

  it('soumet une nouvelle demande de personne concernée', async () => {
    const user = userEvent.setup()
    renderWithRole('responsable')
    await screen.findByText('client@x.ma')

    // Le placeholder « personne concernée » existe aussi dans le bloc
    // Registre de consentement (PACT119, plus bas dans l'écran) : on prend
    // celui du bloc DSR, rendu en premier (même convention que le test
    // « ajoute un consentement… » plus bas, qui prend le dernier des deux).
    const champsSujet = screen.getAllByPlaceholderText(
      'Email ou téléphone de la personne concernée')
    await user.type(champsSujet[0], 'nouveau@x.ma')
    await user.click(screen.getByRole('button', { name: 'Soumettre' }))

    await waitFor(() => expect(createDsr).toHaveBeenCalledWith({
      subject_identifier: 'nouveau@x.ma', kind: 'acces',
    }))
  })

  it('traite une demande reçue', async () => {
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('client@x.ma')

    await user.click(screen.getByRole('button', { name: /Traiter/ }))

    await waitFor(() => expect(traiterDsr).toHaveBeenCalledWith(5))
  })

  it('liste les consentements par sujet et finalité avec leur statut (PACT119)', async () => {
    renderWithRole('admin')

    expect(await screen.findByText('prospect@x.ma')).toBeInTheDocument()
    expect(axiosGet).toHaveBeenCalledWith('/core/consent-records/')
    const ligne = screen.getByTestId('consent-row')
    expect(ligne).toHaveTextContent('marketing')
    expect(ligne).toHaveTextContent('Donné')
    expect(ligne).toHaveTextContent('v1-2026-07')
  })

  it('ajoute un consentement sans jamais envoyer company (PACT119)', async () => {
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('prospect@x.ma')

    await user.type(
      screen.getByPlaceholderText('Finalité (ex. marketing)'), 'whatsapp')
    // Le champ « personne concernée » existe aussi dans le bloc DSR : on prend
    // celui du formulaire de consentement (le second rendu).
    const champsSujet = screen.getAllByPlaceholderText(
      'Email ou téléphone de la personne concernée')
    await user.type(champsSujet[champsSujet.length - 1], 'nouveau@x.ma')
    await user.click(screen.getByRole('button', { name: /Enregistrer le consentement/ }))

    await waitFor(() => expect(axiosPost).toHaveBeenCalledWith(
      '/core/consent-records/',
      { subject_identifier: 'nouveau@x.ma', purpose: 'whatsapp', granted: true, version_texte: '' },
    ))
    expect(Object.keys(axiosPost.mock.calls[0][1])).not.toContain('company')
  })

  it('révoque un consentement au lieu de le supprimer (PACT119)', async () => {
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('prospect@x.ma')

    await user.click(screen.getByRole('button', { name: 'Révoquer' }))

    await waitFor(() => expect(axiosPatch).toHaveBeenCalledWith(
      '/core/consent-records/3/', { granted: false }))
  })

  it('exporte le registre en CSV', async () => {
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('leads_clients')

    await user.click(screen.getByRole('button', { name: /Exporter en CSV/ }))

    await waitFor(() => expect(exportCsv).toHaveBeenCalled())
  })
})
