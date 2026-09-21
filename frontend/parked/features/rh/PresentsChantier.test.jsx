import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import PresentsChantier from './PresentsChantier.jsx'

/* AUDV20 — écran « Présents chantier ». PACT10 : la charge utile n'est PAS
   retapée ici, elle vient de l'exemple committé
   `apps/rh/contract_samples/effectif_chantier.json` — le même fichier que
   `scripts/check_api_shapes.py` compare au dictionnaire réellement renvoyé par
   `PresenceChantierViewSet.effectif`. Si le serveur change de forme, ce test
   casse tout seul. */

const CONTRAT = exempleContrat('rh', 'effectif_chantier')

vi.mock('../../api/rhApi', () => ({
  default: { getEffectifChantier: vi.fn() },
}))

function renderEcran() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <PresentsChantier />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PresentsChantier (AUDV20)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('n’interroge pas le serveur tant qu’aucun chantier n’est choisi', async () => {
    renderEcran()
    await screen.findByText('Présents chantier')
    expect(rhApi.getEffectifChantier).not.toHaveBeenCalled()
  })

  it('affiche l’effectif et les employés comptés pour un chantier/jour', async () => {
    rhApi.getEffectifChantier.mockResolvedValue(
      reponseContrat('rh', 'effectif_chantier'))
    renderEcran()
    fireEvent.change(screen.getByLabelText('Chantier (ID installation)'),
      { target: { value: String(CONTRAT.installation_id) } })

    expect(await screen.findByText(String(CONTRAT.effectif))).toBeTruthy()
    for (const present of CONTRAT.presents) {
      expect(screen.getAllByText(present.employe_nom).length).toBeGreaterThan(0)
    }
    expect(rhApi.getEffectifChantier).toHaveBeenCalledWith(
      expect.objectContaining({
        installation_id: String(CONTRAT.installation_id),
      }),
    )
  })

  it('rend l’état vide du contrat sans planter', async () => {
    rhApi.getEffectifChantier.mockResolvedValue(
      reponseContrat('rh', 'effectif_chantier', 'exemple_vide'))
    renderEcran()
    fireEvent.change(screen.getByLabelText('Chantier (ID installation)'),
      { target: { value: '42' } })

    // `ListShell` rend deux variantes (bureau + mobile) : findAllByText.
    expect((await screen.findAllByText('Aucun présent')).length)
      .toBeGreaterThan(0)
  })
})
