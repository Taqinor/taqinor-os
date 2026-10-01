import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import { formatDate } from '../../../lib/format'

/* QJR565 — un devis corrigé après envoi dit « Document mis à jour le … » sur
   le portail client, comme la page proposition. La liste vient du contrat
   COMMITTÉ `apps/portail/contract_samples/mes_devis_liste.json` (QJR514) —
   jamais un mock écrit à la main. Le contrat porte DEUX devis : un envoyé
   corrigé (mis_a_jour_le daté) et un accepté jamais corrigé (null). */

vi.mock('../../../api/portailApi', () => ({
  default: { devis: { liste: vi.fn(), accepter: vi.fn(), pdfUrl: (id) => `/pdf/${id}` } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientDevis from './PortailClientDevis.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider><PortailClientDevis /></ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PortailClientDevis — QJR565 « Document mis à jour le »', () => {
  it('le devis corrigé affiche sa date de mise à jour, l’autre non', async () => {
    portailApi.devis.liste.mockResolvedValue(reponseContrat('portail', 'mes_devis_liste'))
    const [corrige, intact] = exempleContrat('portail', 'mes_devis_liste').results
    renderPage()
    await screen.findByText(corrige.reference)
    expect(screen.getByTestId(`devis-mis-a-jour-${corrige.id}`).textContent)
      .toBe(`Document mis à jour le ${formatDate(corrige.mis_a_jour_le)}`)
    expect(screen.queryByTestId(`devis-mis-a-jour-${intact.id}`)).toBeNull()
  })
})
