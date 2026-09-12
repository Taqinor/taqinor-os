import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   NTPRT14 — « Mes chantiers » (portail client authentifié).
   ----------------------------------------------------------------------------
   PACT10 — aucune charge utile n'est écrite ici : la liste vient de
   `apps/portail/contract_samples/mes_chantiers_liste.json`, le détail
   (jalons) de `mes_chantiers_detail.json` et les photos de
   `mes_chantiers_photos.json` — les MÊMES fichiers que les tests backend
   (`apps/portail/tests/test_ntprt14_mes_chantiers.py`) affirment contre la
   réponse RÉELLE du serveur.
   ========================================================================== */

vi.mock('../../../api/portailApi', () => ({
  default: { chantiers: { liste: vi.fn(), detail: vi.fn(), photos: vi.fn() } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientChantiers from './PortailClientChantiers.jsx'

const LISTE = exempleContrat('portail', 'mes_chantiers_liste')
const DETAIL = exempleContrat('portail', 'mes_chantiers_detail')
const PHOTOS = exempleContrat('portail', 'mes_chantiers_photos')
const CHANTIER = LISTE.results[0]

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider><PortailClientChantiers /></ThemeProvider>
    </MemoryRouter>,
  )
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PortailClientChantiers — NTPRT14', () => {
  it('affiche tous les chantiers du contrat committé', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    renderPage()

    for (const c of LISTE.results) {
      expect(await screen.findByText(c.reference)).toBeInTheDocument()
      expect(screen.getByText(c.statut_display)).toBeInTheDocument()
    }
  })

  it('affiche un état vide explicite quand le client n’a aucun chantier', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: { results: [] } })
    renderPage()

    expect(await screen.findByText('Aucun chantier')).toBeInTheDocument()
  })

  it('signale l’indisponibilité sans planter si la liste échoue', async () => {
    portailApi.chantiers.liste.mockRejectedValue(new Error('500'))
    renderPage()

    expect(await screen.findByText('Chantiers indisponibles')).toBeInTheDocument()
  })

  it('« Voir le suivi » charge et affiche la timeline + la galerie', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: DETAIL })
    portailApi.chantiers.photos.mockResolvedValue({ data: PHOTOS })
    const user = userEvent.setup()
    renderPage()

    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])

    await waitFor(() => expect(portailApi.chantiers.detail)
      .toHaveBeenCalledWith(CHANTIER.id))
    expect(portailApi.chantiers.photos).toHaveBeenCalledWith(CHANTIER.id)

    for (const j of DETAIL.jalons) {
      expect(await screen.findByText(j.libelle)).toBeInTheDocument()
    }
    for (const p of PHOTOS.results) {
      const img = screen.getByAltText(p.filename)
      expect(img).toHaveAttribute('src', p.url)
    }
  })

  it('sans photo, affiche une note plutôt qu’une galerie vide silencieuse', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: DETAIL })
    portailApi.chantiers.photos.mockResolvedValue({ data: { results: [] } })
    const user = userEvent.setup()
    renderPage()

    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])

    expect(await screen.findByText(
      /Aucune photo pour ce chantier/i)).toBeInTheDocument()
  })

  it('n’expose jamais un lien vers l’endpoint interne des pièces jointes', async () => {
    portailApi.chantiers.liste.mockResolvedValue({ data: LISTE })
    portailApi.chantiers.detail.mockResolvedValue({ data: DETAIL })
    portailApi.chantiers.photos.mockResolvedValue({ data: PHOTOS })
    const user = userEvent.setup()
    const { container } = renderPage()

    await screen.findByText(CHANTIER.reference)
    await user.click(screen.getAllByRole('button', { name: /Voir le suivi/i })[0])
    await screen.findByAltText(PHOTOS.results[0].filename)

    const sources = [...container.querySelectorAll('img[src]')]
      .map((img) => img.getAttribute('src'))
    expect(sources.some((s) => s.includes('records/attachments'))).toBe(false)
  })
})
