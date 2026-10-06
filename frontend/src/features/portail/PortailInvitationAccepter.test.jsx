import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* ADOC117 — page publique /portail/invitation/accepter : l'invité choisit son
   mot de passe. Le « serveur de test » rejoue le contrat committé
   invitation_accepter.json : 400 {mot_de_passe:[…]} puis 200 {detail}. */

vi.mock('../../api/portailApi', () => ({
  default: { invitation: { accepter: vi.fn() } },
}))

import portailApi from '../../api/portailApi'
import PortailInvitationAccepter from './PortailInvitationAccepter.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const contrat = documentContrat('portail', 'invitation_accepter')

function renderPage(url = '/portail/invitation/accepter?token=abc') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <ThemeProvider>
        <Routes>
          <Route path="/portail/invitation/accepter" element={<PortailInvitationAccepter />} />
          <Route path="/login" element={<div>PAGE LOGIN</div>} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

function saisir(mdp) {
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: mdp } })
  fireEvent.change(screen.getByLabelText('Confirmez le mot de passe'), { target: { value: mdp } })
  fireEvent.click(screen.getByRole('button', { name: /Créer mon compte/ }))
}

describe('PortailInvitationAccepter — ADOC117', () => {
  it('affiche le refus de la politique puis envoie vers /login au succès', async () => {
    portailApi.invitation.accepter
      .mockRejectedValueOnce({
        response: { status: 400, data: contrat.exemple_mot_de_passe_refuse },
      })
      .mockResolvedValueOnce({ data: contrat.exemple })
    renderPage()
    saisir('1')
    for (const m of contrat.exemple_mot_de_passe_refuse.mot_de_passe) {
      expect(await screen.findByText(m)).toBeTruthy()
    }
    expect(portailApi.invitation.accepter).toHaveBeenCalledWith({
      token: 'abc', mot_de_passe: '1',
    })
    saisir(contrat.exemple_corps.mot_de_passe)
    expect(await screen.findByText(contrat.exemple.detail)).toBeTruthy()
    expect(portailApi.invitation.accepter).toHaveBeenLastCalledWith({
      token: 'abc', mot_de_passe: contrat.exemple_corps.mot_de_passe,
    })
    fireEvent.click(screen.getByRole('link', { name: /Se connecter/ }))
    await waitFor(() => expect(screen.getByText('PAGE LOGIN')).toBeTruthy())
  })

  it('un jeton invalide affiche le detail du serveur', async () => {
    portailApi.invitation.accepter.mockRejectedValue({
      response: { status: 400, data: contrat.exemple_jeton_invalide },
    })
    renderPage()
    saisir('Un-mot-de-passe-solide-2026')
    expect(await screen.findByText(contrat.exemple_jeton_invalide.detail)).toBeTruthy()
  })

  it('sans jeton dans le lien, rien n’est envoyé', async () => {
    renderPage('/portail/invitation/accepter')
    expect(await screen.findByText(/lien d’invitation/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Créer mon compte/ })).toBeNull()
  })
})
