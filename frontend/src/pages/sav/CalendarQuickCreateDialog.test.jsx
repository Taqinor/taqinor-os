import { Children, isValidElement } from 'react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR178 — Création rapide de ticket SAV depuis le « + » du calendrier
   (CalendarQuickCreateDialog, TicketsPage.jsx) : `client` est un FK REQUIS
   côté serveur (aucun `null=True` sur `sav.Ticket.client`) — le payload
   minimal type+description renvoyait un 400 garanti. Un sélecteur Client
   OBLIGATOIRE bloque la soumission et le corps réel du POST est vérifié. */

vi.mock('../../api/savApi', () => ({
  default: {
    replanifierTicket: vi.fn(() => Promise.resolve({ data: {} })),
    createTicket: vi.fn(() => Promise.resolve({ data: { id: 99, reference: 'SAV-2026-0099' } })),
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({
      data: [{ id: 21, nom: 'Bennani', prenom: 'Omar' }],
    })),
  },
}))

/* Même pattern établi que TicketQuickCreateModal.test.jsx : un <select>
   natif pilote le seul Select de cette modale (le type de ticket reste un
   deuxième Select, sans aria-label — non testé ici). */
vi.mock('../../ui', async (importActual) => {
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

import savApi from '../../api/savApi'
import { TicketCalendarView } from './TicketsPage.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

async function ouvrirDialogueDuJour(user) {
  const today = new Date()
  const todayIso = today.toISOString().slice(0, 10)
  render(<TicketCalendarView tickets={[]} onSelect={() => {}} onReload={() => {}} />)
  // Le bouton « + » d'un jour est masqué (`hidden ... group-hover:flex`) mais
  // reste accessible par son titre en test (pas de survol simulé en jsdom).
  const boutons = screen.getAllByTitle('Créer un ticket ce jour')
  await user.click(boutons[0])
  return todayIso
}

describe('CalendarQuickCreateDialog (WIR178)', () => {
  it('affiche un sélecteur Client obligatoire', async () => {
    const user = userEvent.setup()
    await ouvrirDialogueDuJour(user)
    expect(await screen.findByLabelText('Client')).toBeInTheDocument()
  })

  it('crée le ticket avec le client au corps réel (objectContaining({client}))', async () => {
    const user = userEvent.setup()
    await ouvrirDialogueDuJour(user)

    await user.selectOptions(await screen.findByLabelText('Client'), '21')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(savApi.createTicket).toHaveBeenCalledWith(expect.objectContaining({
      client: '21',
    })))
    // La date proposée est posée ensuite sur le ticket fraîchement créé.
    await waitFor(() => expect(savApi.replanifierTicket).toHaveBeenCalledWith(99, expect.any(String)))
  })

  it('le bouton Créer reste désactivé tant que le client n\'est pas choisi', async () => {
    const user = userEvent.setup()
    await ouvrirDialogueDuJour(user)
    await screen.findByLabelText('Client')

    expect(screen.getByRole('button', { name: 'Créer' })).toBeDisabled()
  })
})
