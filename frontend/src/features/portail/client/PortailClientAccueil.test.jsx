import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   NTPRT9 — Tableau de bord du portail client authentifié.
   ----------------------------------------------------------------------------
   PACT10 — aucune charge utile n'est écrite ici : les 4 cartes viennent du
   contrat COMMITTÉ (`apps/portail/contract_samples/client_tableau_de_bord.json`),
   le MÊME fichier que le test backend
   (`apps/portail/tests/test_ntprt9_tableau_de_bord_client.py`) affirme contre
   la réponse RÉELLE du serveur. Si le serveur change de forme, cet exemple
   change et ce test casse tout seul.
   ========================================================================== */

vi.mock('../../../api/portailApi', () => ({
  default: {
    tableauDeBord: vi.fn(),
    satisfaction: { enAttente: vi.fn(), repondre: vi.fn() },
  },
}))

import portailApi from '../../../api/portailApi'
import PortailClientAccueil from './PortailClientAccueil.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage() {
  portailApi.satisfaction.enAttente.mockResolvedValue({ data: { enquete: null } })
  const store = configureStore({
    reducer: { auth: (s = { user: { first_name: 'Sami' } }) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><PortailClientAccueil /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

// Le libellé de la carte et sa valeur partagent le même conteneur Card —
// on lit la carte PAR SON TITRE plutôt qu'un chiffre nu (deux cartes du
// contrat committé partagent la même valeur « 1 », un `getByText('1')`
// global serait ambigu).
function texteDeLaCarte(titre) {
  return screen.getByText(titre).closest('div').textContent
}

describe('PortailClientAccueil — NTPRT9', () => {
  it('affiche les 4 cartes résumé du contrat committé', async () => {
    const RESUME = reponseContrat('portail', 'client_tableau_de_bord')
    portailApi.tableauDeBord.mockResolvedValue(RESUME)
    renderPage()

    await screen.findByText('Devis en attente')
    expect(texteDeLaCarte('Devis en attente'))
      .toContain(String(RESUME.data.devis_en_attente))
    expect(texteDeLaCarte('Factures impayées'))
      .toContain(String(RESUME.data.factures_impayees))
    expect(texteDeLaCarte('Tickets SAV ouverts'))
      .toContain(String(RESUME.data.tickets_ouverts))
  })

  it('affiche le libellé du prochain jalon quand il existe', async () => {
    const RESUME = reponseContrat('portail', 'client_tableau_de_bord')
    portailApi.tableauDeBord.mockResolvedValue(RESUME)
    renderPage()

    expect(await screen.findByText(
      RESUME.data.prochain_jalon.libelle)).toBeInTheDocument()
    expect(screen.getByText(
      RESUME.data.prochain_jalon.chantier_reference)).toBeInTheDocument()
  })

  it('sans prochain jalon (compte vide), affiche un état explicite jamais un chiffre inventé', async () => {
    const VIDE = reponseContrat('portail', 'client_tableau_de_bord', 'exemple_vide')
    portailApi.tableauDeBord.mockResolvedValue(VIDE)
    renderPage()

    expect(await screen.findByText('Prochain jalon chantier')).toBeInTheDocument()
    expect(screen.getByText('Aucun jalon à venir')).toBeInTheDocument()
  })

  it('signale l’indisponibilité sans planter si l’API échoue', async () => {
    portailApi.tableauDeBord.mockRejectedValue(new Error('500'))
    renderPage()

    expect(await screen.findByText('Tableau de bord indisponible')).toBeInTheDocument()
  })

  it('propose un lien vers « Mes chantiers »', async () => {
    portailApi.tableauDeBord.mockResolvedValue(
      reponseContrat('portail', 'client_tableau_de_bord', 'exemple_vide'))
    renderPage()

    await screen.findByText('Prochain jalon chantier')
    expect(screen.getByRole('link', { name: /Mes chantiers/i }))
      .toHaveAttribute('href', '/portail/client/chantiers')
  })
})
