import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmProvider } from '../../providers/ConfirmProvider'

/* APAR41 — la suppression d'un référentiel (Catégories / Fournisseurs) passe
   par la confirmation MAISON : le dialogue s'ouvre, Annuler n'appelle rien,
   Supprimer appelle `onDelete`. Oracle = dialogue rendu + appel, jamais un
   espion sur window.confirm. */

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

import { ReferentielBlock } from './peComponents'

function rendre(onDelete) {
  return render(
    <ConfirmProvider>
      <ReferentielBlock title="Catégories" icon={null}
        items={[{ id: 3, nom: 'Onduleurs' }]}
        onCreate={vi.fn()} onUpdate={vi.fn()} onDelete={onDelete} />
    </ConfirmProvider>,
  )
}

describe('APAR41 — ReferentielBlock : confirmation maison', () => {
  afterEach(cleanup)

  it('Annuler : aucune suppression', async () => {
    const onDelete = vi.fn(() => Promise.resolve())
    const user = userEvent.setup()
    rendre(onDelete)
    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    const dialogue = await screen.findByRole('alertdialog').catch(() => screen.findByRole('dialog'))
    await user.click(within(dialogue).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(onDelete).not.toHaveBeenCalled()
  })

  it('Supprimer : la suppression part', async () => {
    const onDelete = vi.fn(() => Promise.resolve())
    const user = userEvent.setup()
    rendre(onDelete)
    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    const dialogue = await screen.findByRole('alertdialog').catch(() => screen.findByRole('dialog'))
    await user.click(within(dialogue).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(3))
  })
})
