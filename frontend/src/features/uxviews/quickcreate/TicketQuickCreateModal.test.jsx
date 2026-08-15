import { Children, isValidElement } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR178 — Création rapide de ticket SAV (⌘K) : `client` est un FK REQUIS
   côté serveur (aucun `null=True` sur `sav.Ticket.client`) — le payload
   minimal type+description renvoyait un 400 garanti. Un sélecteur Client
   OBLIGATOIRE est ajouté, la soumission est bloquée sans client, et le
   corps réel du POST est vérifié (pas seulement l'appel). */

const createTicket = vi.fn()
const getClients = vi.fn()

vi.mock('../../../api/savApi', () => ({ default: { createTicket: (...a) => createTicket(...a) } }))
vi.mock('../../../api/crmApi', () => ({ default: { getClients: (...a) => getClients(...a) } }))

/* Pattern établi du dépôt (sav/TicketWorksheetPanel.test.jsx,
   paie/PaieDeclarations.test.jsx) : jsdom n'ouvre pas fiablement un Radix
   Select (portail + pointer events) — un <select> natif pilote le choix
   pendant que tout le reste de `../../../ui` reste RÉEL. Cet écran a DEUX
   Select (Client + Type) : le mock lit `aria-label` sur le SelectTrigger
   RÉEL (élément JSX non-rendu, juste inspecté) pour les distinguer. */
vi.mock('../../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>

  function extractItems(node) {
    const out = []
    Children.forEach(node, (child) => {
      if (!isValidElement(child)) return
      if (child.props && child.props.value !== undefined) out.push(child)
      else if (child.props && child.props.children) out.push(...extractItems(child.props.children))
    })
    return out
  }

  function MockSelect({ value, onValueChange, children }) {
    const kids = Children.toArray(children)
    const trigger = kids.find((k) => isValidElement(k) && k.type === Passthrough && 'aria-label' in (k.props || {}))
    const content = kids.find((k) => isValidElement(k) && k.type === Passthrough && !('aria-label' in (k.props || {})))
    const label = trigger?.props?.['aria-label']
    const items = extractItems(content?.props?.children)
    return (
      <select role="combobox" aria-label={label} value={value}
        onChange={(e) => onValueChange(e.target.value)}>
        <option value="" />
        {items.map((it) => <option key={it.props.value} value={it.props.value}>{it.props.children}</option>)}
      </select>
    )
  }

  return {
    ...actual,
    Select: MockSelect,
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

import TicketQuickCreateModal from './TicketQuickCreateModal'

beforeEach(() => {
  vi.clearAllMocks()
  getClients.mockResolvedValue({ data: [{ id: 11, nom: 'Alaoui', prenom: 'Youssef' }] })
  createTicket.mockResolvedValue({ data: { id: 5, reference: 'SAV-2026-0005' } })
})

describe('TicketQuickCreateModal (WIR178)', () => {
  it('bloque la soumission sans client sélectionné', async () => {
    const user = userEvent.setup()
    render(<TicketQuickCreateModal open onClose={() => {}} onCreated={() => {}} />)
    await screen.findByLabelText('Client')

    await user.type(screen.getByLabelText('Description'), 'Onduleur en panne')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    expect(createTicket).not.toHaveBeenCalled()
    expect(await screen.findByRole('alert')).toHaveTextContent('client')
  })

  it('crée le ticket avec le client au corps réel (objectContaining({client}))', async () => {
    const onCreated = vi.fn()
    const user = userEvent.setup()
    render(<TicketQuickCreateModal open onClose={() => {}} onCreated={onCreated} />)
    await screen.findByLabelText('Client')

    await user.selectOptions(screen.getByLabelText('Client'), '11')
    await user.type(screen.getByLabelText('Description'), 'Onduleur en panne')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(createTicket).toHaveBeenCalledWith(expect.objectContaining({
      client: '11', description: 'Onduleur en panne',
    })))
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith({ id: 5, reference: 'SAV-2026-0005' }))
  })
})
