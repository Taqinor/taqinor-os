import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { espions, REPONSE_POSE } from '../../test/fixtures/calepinageApiMock'
import { SAISIE_SOL } from '../../test/fixtures/saisiesSurfacePose'

/* ENF15 — l'onglet « Terrain » (CALX1) est MONTÉ. Le détail (pas mesuré, dessin du
   champ, enregistrement) vit dans `__tests__/mode_terrain.test.jsx` ; ici, l'onglet
   tel que le rail le monte : saisie incomplète = aucune demande au moteur ; saisie
   complète = le compte de modules affiché est celui du moteur. */

vi.mock('../../api/calepinageApi', async () => (await import('../../test/fixtures/calepinageApiMock')).apiDocument({ moteur: true }))

const { default: ModeTerrain } = await import('./ModeTerrain')

const monter = () => render(<MemoryRouter><ModeTerrain calepinageId={7} /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  espions.layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'PAN-A' }] }, empreinte_document: 'E0' } })
  espions.pose.mockResolvedValue({ data: REPONSE_POSE })
})
afterEach(() => { cleanup() })

describe('ModeTerrain — onglet monté', () => {
  it('saisie incomplète : rien n’est envoyé au moteur, le refus est dit', async () => {
    monter()
    await waitFor(() => expect(espions.layout).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    expect(espions.pose).not.toHaveBeenCalled()
    expect(await screen.findByTestId('cal-terrain-message')).toHaveTextContent(/incomplètes/)
  })

  it('saisie complète : le compte de modules affiché est celui du moteur', async () => {
    monter()
    await waitFor(() => expect(espions.layout).toHaveBeenCalled())
    for (const [cle, valeur] of Object.entries(SAISIE_SOL)) {
      const champ = screen.queryByTestId(`cal-terrain-${cle}`)
      if (champ) fireEvent.change(champ, { target: { value: valeur } })
    }
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => expect(espions.pose).toHaveBeenCalledTimes(1))
    const modules = await screen.findByTestId('cal-terrain-modules')
    expect(modules).toHaveTextContent(String(REPONSE_POSE.plans[0].modules))
  })
})
