import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* WIR24 — le composant EcritureSourceLink affiche un lien vers l'écriture GL
   d'un document source quand une écriture existe, et RIEN sinon. Les appels
   API sont mockés (aucun réseau). */

const listMock = vi.fn()
vi.mock('../../../api/comptaApi', () => ({
  default: { ecritures: { list: (params) => listMock(params) } },
}))

import EcritureSourceLink from './EcritureSourceLink.jsx'

function mount(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('EcritureSourceLink (WIR24)', () => {
  it('rend un lien quand une écriture existe pour la facture', async () => {
    listMock.mockResolvedValueOnce({ data: [{ id: 7, numero: 'VE-2026-0003' }] })
    mount(<EcritureSourceLink sourceType="facture" sourceId={42} />)
    const link = await screen.findByTestId('ecriture-source-link')
    expect(link).toBeTruthy()
    expect(link.getAttribute('href')).toContain('source_type=facture')
    expect(link.getAttribute('href')).toContain('source_id=42')
    expect(listMock).toHaveBeenCalledWith({ source_type: 'facture', source_id: 42 })
  })

  it("n'affiche rien quand aucune écriture n'existe (auto-génération OFF)", async () => {
    listMock.mockResolvedValueOnce({ data: [] })
    const { container } = mount(
      <EcritureSourceLink sourceType="facture" sourceId={99} />,
    )
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(screen.queryByTestId('ecriture-source-link')).toBeNull()
    expect(container.textContent).toBe('')
  })
})
