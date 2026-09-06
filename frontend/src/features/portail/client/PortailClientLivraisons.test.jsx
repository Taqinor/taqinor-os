import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   AUD147 — « Voir la preuve de livraison » ne rend plus un lien MORT.
   ----------------------------------------------------------------------------
   Défaut d'origine : l'écran rendait `pod_url` en `<a href … target="_blank">`
   dès `pod_disponible`. Ce lien pointait l'endpoint INTERNE
   `/api/django/installations/preuves-livraison/<id>/` (`IsAnyRole`, qui exclut
   explicitement `portee != 'interne'`) : le client cliquait et recevait 403 —
   sur SON PROPRE document. AUD301 a livré la route PORTAIL et y a repointé
   `pod_url`, mais celle-ci renvoie un DOCUMENT JSON, pas un fichier : ouvert
   dans un onglet, le client aurait vu du JSON brut. L'écran LIT donc la preuve
   par l'API et la RESTITUE.

   PACT10 — aucune charge utile n'est écrite ici : la liste vient de
   `apps/portail/contract_samples/mes_livraisons.json` et la preuve de
   `mes_livraisons_preuve.json`, les MÊMES fichiers que les tests backend
   (`apps/portail/tests/test_aud147_lien_preuve_portail.py` et
   `test_aud301_preuve_livraison.py`) affirment contre la réponse RÉELLE du
   serveur. Si le serveur change de forme, ces exemples changent et ce test
   casse tout seul.
   ========================================================================== */

vi.mock('../../../api/portailApi', () => ({
  default: { livraisons: { liste: vi.fn(), preuve: vi.fn() } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientLivraisons from './PortailClientLivraisons'

const LISTE = exempleContrat('portail', 'mes_livraisons')
const PREUVE = exempleContrat('portail', 'mes_livraisons_preuve')
// Repérées PAR LEUR CONTENU, jamais par un id codé en dur.
const AVEC_POD = LISTE.results.find((l) => l.pod_disponible)
const SANS_POD = LISTE.results.find((l) => !l.pod_disponible)

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider><PortailClientLivraisons /></ThemeProvider>
    </MemoryRouter>,
  )
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PortailClientLivraisons — AUD147', () => {
  beforeEach(() => {
    portailApi.livraisons.liste.mockResolvedValue({ data: LISTE })
    portailApi.livraisons.preuve.mockResolvedValue({ data: PREUVE })
  })

  it('l’exemple de contrat porte bien les deux cas dont l’écran a besoin', () => {
    // Garde-fou : sans ces deux états, les tests ci-dessous testeraient autre
    // chose que ce qu'ils annoncent.
    expect(AVEC_POD).toBeTruthy()
    expect(SANS_POD).toBeTruthy()
  })

  it('n’affiche le bouton de preuve que sur une livraison qui en a une', async () => {
    renderPage()
    await screen.findByText(AVEC_POD.reference)

    expect(screen.getByText(SANS_POD.reference)).toBeTruthy()
    expect(screen.getAllByRole('button', { name: /Voir la preuve de livraison/ }))
      .toHaveLength(1)
  })

  it('ne rend AUCUN lien vers l’endpoint interne des preuves', async () => {
    const { container } = renderPage()
    await screen.findByText(AVEC_POD.reference)

    const liens = [...container.querySelectorAll('a[href]')]
      .map((a) => a.getAttribute('href'))
    expect(liens.some((h) => h.includes('installations/preuves-livraison')))
      .toBe(false)
    // Le document JSON de la preuve n'est pas non plus offert en lien brut.
    expect(liens).not.toContain(AVEC_POD.pod_url)
  })

  it('lit la preuve par l’API portail et l’affiche dans la page', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(AVEC_POD.reference)

    await user.click(
      screen.getByRole('button', { name: /Voir la preuve de livraison/ }))

    await waitFor(() => expect(portailApi.livraisons.preuve)
      .toHaveBeenCalledWith(AVEC_POD.id))
    expect(await screen.findByText(PREUVE.signataire_nom)).toBeTruthy()
    expect(screen.getByText(PREUVE.note)).toBeTruthy()
    const signature = screen.getByAltText('Signature du client')
    expect(signature.getAttribute('src')).toBe(PREUVE.signature_image)
    const photo = screen.getByAltText('Photo de la livraison')
    expect(photo.getAttribute('src')).toBe(PREUVE.photo_url)
  })

  it('signale l’échec sans laisser un bouton qui ne fait rien', async () => {
    portailApi.livraisons.preuve.mockRejectedValue(new Error('403'))
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(AVEC_POD.reference)

    await user.click(
      screen.getByRole('button', { name: /Voir la preuve de livraison/ }))

    expect(await screen.findByText(
      /preuve de livraison n’a pas pu être affichée/)).toBeTruthy()
  })
})
