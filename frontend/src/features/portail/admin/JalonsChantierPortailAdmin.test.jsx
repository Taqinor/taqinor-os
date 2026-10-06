import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT100 — Jalons de chantier (portail) : marquer_atteint (date posée côté
   serveur uniquement si absente). ADOC129 — plus de création manuelle :
   correction en ligne (libellé, date, atteint), « Marquer non atteint »,
   suppression des seuls jalons hérités (sans clé de phase). portailApi mocké. */

vi.mock('../../../api/portailApi', () => ({
  default: {
    admin: {
      jalonsChantier: {
        liste: vi.fn(), patch: vi.fn(), supprimer: vi.fn(),
        marquerAtteint: vi.fn(), marquerNonAtteint: vi.fn(),
      },
    },
  },
}))

import portailApi from '../../../api/portailApi'
import JalonsChantierPortailAdmin from './JalonsChantierPortailAdmin'

// ADOC32 — l'API sert l'enveloppe DRF réelle {count, next, results} (jamais un
// tableau nu) ; `pagine` simule une liste de `total` lignes servie par pages de 50.
const enveloppe = (results) => ({ count: results.length, next: null, previous: null, results })
const pagine = (total, ligne, taille = 50) => (params) => {
  const page = params?.page ?? 1
  const debut = (page - 1) * taille
  const fin = Math.min(total, debut + taille)
  return Promise.resolve({
    data: {
      count: total,
      next: fin < total ? `/api/django/portail/x/?page=${page + 1}` : null,
      previous: page > 1 ? `/api/django/portail/x/?page=${page - 1}` : null,
      results: Array.from({ length: Math.max(0, fin - debut) }, (_, i) => ligne(debut + i + 1)),
    },
  })
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('JalonsChantierPortailAdmin — PACT100', () => {
  it('affiche la timeline avec statut atteint/non atteint', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: enveloppe([{ id: 1, chantier_id: 21, libelle: 'Étude', ordre: 1, atteint: true, date_jalon: '2026-07-01', cle_phase: 'etude' }]),
    })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Étude').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Atteint').length).toBeGreaterThan(0)
    expect(screen.getAllByText('#21').length).toBeGreaterThan(0)
  })

  it('marque un jalon non atteint comme atteint', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: enveloppe([{ id: 4, chantier_id: 21, libelle: 'Installation', ordre: 4, atteint: false, date_jalon: null, cle_phase: 'pose' }]),
    })
    portailApi.admin.jalonsChantier.marquerAtteint.mockResolvedValue({ data: {} })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Installation').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: /Marquer atteint/ })[0])
    await waitFor(() => expect(portailApi.admin.jalonsChantier.marquerAtteint).toHaveBeenCalledWith(4))
  })
})

describe('ADOC129 — corriger un jalon (plus de création manuelle)', () => {
  it("n'offre plus aucun formulaire de création", async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({ data: enveloppe([]) })
    renderPage(<JalonsChantierPortailAdmin />)
    expect((await screen.findAllByText('Aucun jalon')).length).toBeGreaterThan(0)
    expect(screen.queryAllByRole('button', { name: /Créer le jalon/ })).toHaveLength(0)
    expect(screen.queryAllByRole('combobox', { name: 'Chantier' })).toHaveLength(0)
  })

  it('corriger un jalon', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: enveloppe([{ id: 7, chantier_id: 21, libelle: 'Pose', ordre: 5, atteint: true, date_jalon: '2026-10-01', cle_phase: 'pose' }]),
    })
    portailApi.admin.jalonsChantier.patch.mockResolvedValue({ data: {} })
    renderPage(<JalonsChantierPortailAdmin />)
    fireEvent.click((await screen.findAllByRole('button', { name: /Corriger/ }))[0])
    fireEvent.change(screen.getAllByLabelText('Libellé du jalon Pose')[0],
      { target: { value: 'Pose des panneaux' } })
    fireEvent.change(screen.getAllByLabelText('Date du jalon Pose')[0],
      { target: { value: '2026-10-02' } })
    fireEvent.click(screen.getAllByRole('button', { name: /Enregistrer/ })[0])
    await waitFor(() => expect(portailApi.admin.jalonsChantier.patch).toHaveBeenCalledWith(7, {
      libelle: 'Pose des panneaux', date_jalon: '2026-10-02', atteint: true,
    }))
    // Rechargement après la correction (persistance relue au serveur).
    await waitFor(() => expect(portailApi.admin.jalonsChantier.liste).toHaveBeenCalledTimes(2))
  })

  it('marque un jalon atteint par erreur comme non atteint', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: enveloppe([{ id: 6, chantier_id: 21, libelle: 'Réception', ordre: 6, atteint: true, date_jalon: '2026-07-20', cle_phase: 'reception' }]),
    })
    portailApi.admin.jalonsChantier.marquerNonAtteint.mockResolvedValue({ data: {} })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Réception').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Marquer atteint/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: /Marquer non atteint/ })[0])
    await waitFor(() => expect(portailApi.admin.jalonsChantier.marquerNonAtteint).toHaveBeenCalledWith(6))
  })

  it('ne propose la suppression que pour un jalon hérité (sans clé de phase)', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: enveloppe([
        { id: 1, chantier_id: 21, libelle: 'Pose', ordre: 5, atteint: false, date_jalon: null, cle_phase: 'pose' },
        { id: 2, chantier_id: 21, libelle: 'Installation', ordre: 4, atteint: false, date_jalon: null, cle_phase: null },
      ]),
    })
    portailApi.admin.jalonsChantier.supprimer.mockResolvedValue({ data: {} })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Installation').length).toBeGreaterThan(0))
    // Chaque bouton « Supprimer » rendu (table ET carte mobile) vise le seul
    // jalon hérité : le jalon synchronisé (id 1) n'en a aucun.
    for (const bouton of screen.getAllByRole('button', { name: /Supprimer/ })) {
      fireEvent.click(bouton)
    }
    await waitFor(() => expect(portailApi.admin.jalonsChantier.supprimer).toHaveBeenCalledWith(2))
    expect(portailApi.admin.jalonsChantier.supprimer).not.toHaveBeenCalledWith(1)
  })
})

describe('ADOC32 — toutes les pages (jalons)', () => {
  it('60 lignes sur deux pages', async () => {
    portailApi.admin.jalonsChantier.liste.mockImplementation(pagine(60, (n) => ({ id: n, chantier_id: 21, libelle: `Jalon ${n}`, ordre: n, atteint: false, date_jalon: null, cle_phase: `p${n}` })))
    renderPage(<JalonsChantierPortailAdmin />)
    expect((await screen.findAllByText('1–25 sur 60')).length).toBeGreaterThan(0)
    expect(portailApi.admin.jalonsChantier.liste).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })
})
