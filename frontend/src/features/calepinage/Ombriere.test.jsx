import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { espions } from '../../test/fixtures/calepinageApiMock'

/* ENF15 — l'onglet « Ombrière » (CALX1) est MONTÉ. Le détail (coupe, travées,
   totaux par bâtiment) vit dans `__tests__/ombriere.test.jsx` ; ici, l'onglet tel
   que le rail le monte : saisie incomplète = aucune demande au moteur, et la
   hauteur libre n'est jamais supposée. */

vi.mock('../../api/calepinageApi', async () => (await import('../../test/fixtures/calepinageApiMock')).apiDocument({ moteur: true }))

const { default: Ombriere } = await import('./Ombriere')

const monter = () => render(<MemoryRouter><Ombriere calepinageId={7} /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  espions.layout.mockResolvedValue({ data: { roof_layout: {}, empreinte_document: 'E0' } })
})
afterEach(() => { cleanup() })

describe('Ombriere — onglet monté', () => {
  it('saisie incomplète : rien n’est envoyé au moteur, le refus est dit', async () => {
    monter()
    await waitFor(() => expect(espions.layout).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    expect(espions.pose).not.toHaveBeenCalled()
    expect(await screen.findByTestId('cal-ombriere-message')).toBeInTheDocument()
  })

  it('sans hauteur libre saisie, l’écran ne suppose aucune hauteur', async () => {
    monter()
    await screen.findByTestId('cal-ombriere')
    expect(screen.getByTestId('cal-ombriere-hauteur')).not.toHaveTextContent(/\d\s*m\b/)
  })
})
