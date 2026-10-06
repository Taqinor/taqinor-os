import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { documentContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* ADOC114 — le devis à DEUX options demande le choix au client dans le dialogue
   d'acceptation et l'envoie dans `option` (contrat mes_devis_liste.json,
   variante `exemple_deux_options` + `acceptation`). Le « serveur de test »
   reproduit le 400 du contrat quand `option` manque. */

vi.mock('../../../api/portailApi', () => ({
  default: { devis: { liste: vi.fn(), accepter: vi.fn(), pdfUrl: (id) => `/pdf/${id}` } },
}))
const toastSpy = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../../ui', async (orig) => {
  const m = await orig()
  return { ...m, toast: { ...m.toast, success: toastSpy.success, error: toastSpy.error } }
})

import portailApi from '../../../api/portailApi'
import PortailClientDevis from './PortailClientDevis.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const contrat = documentContrat('portail', 'mes_devis_liste')

function serveur() {
  let accepte = false
  portailApi.devis.liste.mockImplementation(() => {
    const r = reponseContrat('portail', 'mes_devis_liste', 'exemple_deux_options')
    if (accepte) {
      r.data.results[0] = { ...r.data.results[0], accepte: true, statut: 'accepte', statut_display: 'Accepté' }
    }
    return Promise.resolve(r)
  })
  portailApi.devis.accepter.mockImplementation((id, corps) => {
    if (!corps.option) {
      return Promise.reject({
        response: { status: 400, data: contrat.acceptation.reponses['400_option_manquante'] },
      })
    }
    accepte = true
    return Promise.resolve({ data: contrat.acceptation.reponses['200'] })
  })
}

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><PortailClientDevis /></ThemeProvider></MemoryRouter>,
  )
}

describe('PortailClientDevis — ADOC114 choix de l’option', () => {
  it('exige le choix, envoie option et recharge la liste « Accepté »', async () => {
    serveur()
    renderPage()
    await screen.findByText('DEV-202609-0012')
    fireEvent.click(screen.getByRole('button', { name: 'Accepter' }))
    fireEvent.change(screen.getByLabelText('Votre nom'), { target: { value: 'Karim Alaoui' } })
    fireEvent.click(screen.getByRole('checkbox'))
    const valider = screen.getByRole('button', { name: /Confirmer l’acceptation/ })
    expect(valider.disabled).toBe(true) // aucune option choisie
    fireEvent.click(screen.getByLabelText('Avec batterie'))
    await waitFor(() => expect(valider.disabled).toBe(false))
    fireEvent.click(valider)
    await waitFor(() => expect(portailApi.devis.accepter).toHaveBeenCalledWith(
      413, contrat.acceptation.exemple_corps_deux_options,
    ))
    await waitFor(() => expect(toastSpy.success).toHaveBeenCalledWith('Devis accepté. Merci !'))
    // rechargé : le devis 413 n'a plus de bouton d'acceptation
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Accepter' })).toBeNull())
  })

  it('un devis mono-option garde le dialogue actuel (aucun choix)', async () => {
    // Devis envoyé mono-option : la ligne à accepter du contrat, avec les
    // valeurs mono-option de la seconde ligne du même contrat (false / null).
    const r = reponseContrat('portail', 'mes_devis_liste')
    const mono = r.data.results[1]
    r.data.results = [{ ...r.data.results[0], deux_options: mono.deux_options, options: mono.options }]
    portailApi.devis.liste.mockResolvedValue(r)
    renderPage()
    await screen.findByText('DEV-202609-0012')
    fireEvent.click(screen.getByRole('button', { name: 'Accepter' }))
    expect(screen.queryByLabelText('Avec batterie')).toBeNull()
    fireEvent.change(screen.getByLabelText('Votre nom'), { target: { value: 'K A' } })
    fireEvent.click(screen.getByRole('checkbox'))
    expect(screen.getByRole('button', { name: /Confirmer l’acceptation/ }).disabled).toBe(false)
  })
})
