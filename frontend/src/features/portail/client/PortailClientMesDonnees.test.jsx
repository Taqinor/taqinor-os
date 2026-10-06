import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

/* ADOC141 — recherche du shell client + export « Mes données »
   (contrat recherche_portail.json ; l'export est un binaire). */

vi.mock('../../../api/portailApi', () => ({
  default: {
    recherche: vi.fn(),
    exportMesDonneesUrl: () => '/api/django/portail/client/mes-donnees/export/',
  },
}))

import portailApi from '../../../api/portailApi'
import PortailClientRecherche from './PortailClientRecherche.jsx'
import PortailClientMesDonnees from './PortailClientMesDonnees.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderRecherche() {
  return render(
    <MemoryRouter><ThemeProvider><PortailClientRecherche /></ThemeProvider></MemoryRouter>,
  )
}

describe('PortailClientRecherche — ADOC141', () => {
  it('« 0012 » affiche le groupe Devis, le résultat mène à /portail/client/devis', async () => {
    portailApi.recherche.mockResolvedValue(reponseContrat('portail', 'recherche_portail'))
    renderRecherche()
    fireEvent.change(screen.getByLabelText('Rechercher dans mon espace'), { target: { value: '0012' } })
    fireEvent.click(screen.getByRole('button', { name: /Rechercher/ }))
    await waitFor(() => expect(portailApi.recherche).toHaveBeenCalledWith('0012'))
    const lien = await screen.findByRole('link', { name: 'DEV-202609-0012' })
    expect(lien.getAttribute('href')).toBe('/portail/client/devis')
    expect(screen.getByRole('region', { name: 'Devis' })).toBeTruthy()
    // les groupes vides n'affichent rien
    expect(screen.queryByRole('region', { name: 'Factures' })).toBeNull()
  })

  it('un mot vide n’appelle pas le serveur et n’affiche rien', async () => {
    portailApi.recherche.mockResolvedValue(reponseContrat('portail', 'recherche_portail', 'exemple_vide'))
    renderRecherche()
    fireEvent.click(screen.getByRole('button', { name: /Rechercher/ }))
    expect(portailApi.recherche).not.toHaveBeenCalled()
    expect(screen.queryByRole('region')).toBeNull()
  })

  it('aucun résultat : message, pas de groupe', async () => {
    portailApi.recherche.mockResolvedValue(reponseContrat('portail', 'recherche_portail', 'exemple_vide'))
    renderRecherche()
    fireEvent.change(screen.getByLabelText('Rechercher dans mon espace'), { target: { value: 'zzz' } })
    fireEvent.click(screen.getByRole('button', { name: /Rechercher/ }))
    expect(await screen.findByText('Aucun résultat.')).toBeTruthy()
  })
})

describe('PortailClientMesDonnees — ADOC141', () => {
  it('le bouton Exporter pointe sur l’export zip du serveur', () => {
    render(<MemoryRouter><ThemeProvider><PortailClientMesDonnees /></ThemeProvider></MemoryRouter>)
    const lien = screen.getByRole('link', { name: /Exporter mes données/ })
    expect(lien.getAttribute('href')).toBe('/api/django/portail/client/mes-donnees/export/')
    expect(lien.hasAttribute('download')).toBe(true)
  })
})
