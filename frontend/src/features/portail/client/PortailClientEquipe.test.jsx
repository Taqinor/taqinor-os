import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { documentContrat, exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* ADOC138 — « Mon équipe » : l'administrateur invite et révoque, le membre
   (peut_gerer:false) ne voit aucun bouton. Charges = contrat mon_equipe.json. */

vi.mock('../../../api/portailApi', () => ({
  default: { equipe: { liste: vi.fn(), inviter: vi.fn(), revoquer: vi.fn() } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientEquipe from './PortailClientEquipe.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const contrat = documentContrat('portail', 'mon_equipe')

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><PortailClientEquipe /></ThemeProvider></MemoryRouter>,
  )
}

describe('PortailClientEquipe — ADOC138', () => {
  it('l’admin invite (corps du contrat) puis la liste rechargée est relue', async () => {
    portailApi.equipe.liste.mockResolvedValue(reponseContrat('portail', 'mon_equipe'))
    portailApi.equipe.inviter.mockResolvedValue({ data: contrat.invitation.reponses['201'] })
    renderPage()
    await screen.findByText('collegue@exemple.ma')
    fireEvent.change(screen.getByLabelText('E-mail'),
      { target: { value: contrat.invitation.exemple_corps.email } })
    fireEvent.click(screen.getByRole('button', { name: 'Inviter' }))
    await waitFor(() => expect(portailApi.equipe.inviter)
      .toHaveBeenCalledWith(contrat.invitation.exemple_corps))
    await waitFor(() => expect(portailApi.equipe.liste).toHaveBeenCalledTimes(2))
    expect(screen.getByText('En attente')).toBeTruthy()
  })

  it('l’admin révoque un membre : POST puis relecture', async () => {
    portailApi.equipe.liste.mockResolvedValue(reponseContrat('portail', 'mon_equipe'))
    portailApi.equipe.revoquer.mockResolvedValue({ data: contrat.revocation.reponses['200'] })
    renderPage()
    await screen.findByText('collegue@exemple.ma')
    const boutons = screen.getAllByRole('button', { name: 'Révoquer' })
    expect(boutons).toHaveLength(2)
    fireEvent.click(boutons[0])
    await waitFor(() => expect(portailApi.equipe.revoquer).toHaveBeenCalledWith(5))
    await waitFor(() => expect(portailApi.equipe.liste).toHaveBeenCalledTimes(2))
  })

  it('le membre (peut_gerer:false) voit la liste sans aucun bouton', async () => {
    portailApi.equipe.liste.mockResolvedValue(
      reponseContrat('portail', 'mon_equipe', 'exemple_membre_non_admin'))
    renderPage()
    await screen.findByText(
      exempleContrat('portail', 'mon_equipe', 'exemple_membre_non_admin').results[0].email)
    expect(screen.queryByRole('button', { name: 'Inviter' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Révoquer' })).toBeNull()
  })

  it('le refus 403 du serveur est affiché', async () => {
    portailApi.equipe.liste.mockResolvedValue(reponseContrat('portail', 'mon_equipe'))
    portailApi.equipe.inviter.mockRejectedValue({
      response: { status: 403, data: contrat.invitation.reponses['403'] },
    })
    renderPage()
    await screen.findByText('collegue@exemple.ma')
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'a@b.ma' } })
    fireEvent.click(screen.getByRole('button', { name: 'Inviter' }))
    expect(await screen.findByText(contrat.invitation.reponses['403'].detail)).toBeTruthy()
  })
})
