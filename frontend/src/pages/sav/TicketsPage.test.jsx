import { describe, it, expect, vi } from 'vitest'
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { mockMatchMedia } from '../../test/matchMedia'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import savApi from '../../api/savApi'

// ADRG22 — doublures réseau de la fiche et de la liste (aucun effet sur les
// briques de présentation testées plus bas, qui n'appellent aucune API).
vi.mock('../../features/sav/store/ticketsSlice', async (io) => ({
  ...(await import('./__tests__/ticketDetailMocks.js')).ticketsSliceMock(await io()),
  fetchTickets: () => ({ type: 'sav/fetchTickets/noop' }),
}))
vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailMocks.js')).savApiMock())
vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailMocks.js')).axiosMock())
vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailMocks.js')).installationsApiMock())

import TicketsPage, {
  TicketDetail,
  StatutPill,
  PrioriteBadge,
  TicketSlaBadge,
  TicketSlaEcheanceChip,
  TicketPremiereReponseChip,
  KanbanColumn,
} from './TicketsPage.jsx'
import {
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
  TICKET_PRIORITE_LABELS,
} from '../../features/sav/ticketStatuses'

/* J144 — refonte SAV : les écrans tickets passent à StatusPill + DataTable, avec
   états vide / chargement et passe mobile. Ces tests verrouillent les briques de
   présentation (ton de statut, badge SLA, colonne Kanban) qui encodent cette
   refonte — la couleur n'est jamais le seul signal : le LIBELLÉ reste toujours. */

// Le point coloré du StatusPill encode le ton (bg-success/bg-warning/…) : on
// l'utilise pour vérifier le mapping statut → ton sans dépendre du thème.
const DOT_CLASS = {
  neutral: 'bg-muted-foreground', info: 'bg-info', success: 'bg-success',
  warning: 'bg-warning', danger: 'bg-destructive',
}

describe('StatutPill (J144 — statut ticket → ton + libellé FR)', () => {
  it('chaque statut canonique rend un libellé FR et un point coloré défini', () => {
    for (const k of TICKET_STATUSES) {
      const { container, unmount } = render(<StatutPill statut={k} />)
      // Libellé FR visible (jamais la clé brute).
      expect(screen.getByText(TICKET_STATUS_LABELS[k])).toBeInTheDocument()
      // Un point coloré d'un ton CONNU est rendu (la couleur n'est jamais seule).
      const hasKnownDot = Object.values(DOT_CLASS)
        .some((cls) => container.querySelector(`.${cls}`))
      expect(hasKnownDot).toBe(true)
      unmount()
    }
  })

  it('affiche le libellé FR du statut (jamais la clé brute)', () => {
    render(<StatutPill statut="en_cours" />)
    expect(screen.getByText(TICKET_STATUS_LABELS.en_cours)).toBeInTheDocument()
  })

  it('résolu → point coloré succès', () => {
    const { container } = render(<StatutPill statut="resolu" />)
    expect(container.querySelector(`.${DOT_CLASS.success}`)).toBeTruthy()
  })

  it('statut inconnu → ton neutre (jamais une erreur)', () => {
    const { container } = render(<StatutPill statut="zzz" />)
    expect(container.querySelector(`.${DOT_CLASS.neutral}`)).toBeTruthy()
  })
})

describe('PrioriteBadge (J144)', () => {
  it('affiche le libellé FR de la priorité', () => {
    render(<PrioriteBadge value="urgente" />)
    expect(screen.getByText(TICKET_PRIORITE_LABELS.urgente)).toBeInTheDocument()
  })

  it('chaque priorité connue rend son libellé FR', () => {
    for (const k of Object.keys(TICKET_PRIORITE_LABELS)) {
      const { unmount } = render(<PrioriteBadge value={k} />)
      expect(screen.getByText(TICKET_PRIORITE_LABELS[k])).toBeInTheDocument()
      unmount()
    }
  })
})

describe('TicketSlaBadge (J144 — âge SLA, calculé à la lecture)', () => {
  const openTicket = {
    statut: 'nouveau',
    priorite: 'normale',
    annule: false,
    date_ouverture: '2000-01-01', // très ancien → forcément ouvert depuis N j
  }

  it('affiche « ouvert depuis X j » pour un ticket ouvert', () => {
    render(<TicketSlaBadge ticket={openTicket} />)
    expect(screen.getByText(/ouvert depuis/i)).toBeInTheDocument()
  })

  it('ne rend rien pour un ticket clôturé', () => {
    const { container } = render(
      <TicketSlaBadge ticket={{ ...openTicket, statut: 'cloture' }} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('ne rend rien pour un ticket annulé', () => {
    const { container } = render(
      <TicketSlaBadge ticket={{ ...openTicket, annule: true }} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('ne rend rien sans date exploitable', () => {
    const { container } = render(
      <TicketSlaBadge ticket={{ statut: 'nouveau', priorite: 'normale', annule: false }} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})

/* APX30 — les DEUX horloges SLA rendues. Les dates sont calculées à partir
   d'un « aujourd'hui » lu au moment du test (jamais une date figée dans le
   futur qui périmerait) : c'est l'écart en jours qui est vérifié, pas une
   chaîne de date absolue. */
describe('TicketSlaEcheanceChip (APX30 — échéance de résolution)', () => {
  const dansNJours = (n) => {
    const d = new Date()
    d.setDate(d.getDate() + n)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }
  const ouvert = { statut: 'en_cours', priorite: 'normale', annule: false }

  it('ne rend rien quand la société n’a pas activé le SLA (aucune échéance)', () => {
    const { container } = render(<TicketSlaEcheanceChip ticket={ouvert} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('annonce le délai restant sur un ticket ouvert dans les temps', () => {
    render(<TicketSlaEcheanceChip ticket={{ ...ouvert, sla_due_at: dansNJours(3) }} />)
    expect(screen.getByText(/à résoudre sous 3 j/i)).toBeInTheDocument()
  })

  it('dit « aujourd’hui » le jour de l’échéance', () => {
    render(<TicketSlaEcheanceChip ticket={{ ...ouvert, sla_due_at: dansNJours(0) }} />)
    expect(screen.getByText(/à résoudre aujourd'hui/i)).toBeInTheDocument()
  })

  it('passe en dépassement avec le nombre de jours de retard', () => {
    render(<TicketSlaEcheanceChip ticket={{ ...ouvert, sla_due_at: dansNJours(-2) }} />)
    expect(screen.getByText(/SLA dépassé — 2 j/i)).toBeInTheDocument()
  })

  it('GARDE la marque « SLA dépassé » après résolution (traçabilité)', () => {
    render(
      <TicketSlaEcheanceChip
        ticket={{ ...ouvert, statut: 'resolu', sla_due_at: dansNJours(-9), sla_breach: true }}
      />,
    )
    expect(screen.getByText(/SLA dépassé/i)).toBeInTheDocument()
  })

  it('ne marque JAMAIS un ticket résolu dans les temps', () => {
    const { container } = render(
      <TicketSlaEcheanceChip
        ticket={{ ...ouvert, statut: 'resolu', sla_due_at: dansNJours(-9), sla_breach: false }}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('une pause client (XSAV5) décale l’échéance au lieu de compter un retard', () => {
    render(
      <TicketSlaEcheanceChip
        ticket={{
          ...ouvert,
          sla_due_at: dansNJours(-4),
          sla_due_at_effectif: dansNJours(3),
          en_attente_client: true,
        }}
      />,
    )
    expect(screen.getByText(/en pause/i)).toBeInTheDocument()
    expect(screen.queryByText(/SLA dépassé/i)).toBeNull()
  })
})

describe('TicketPremiereReponseChip (APX30 — l’autre horloge)', () => {
  const ouvert = { statut: 'nouveau', priorite: 'normale', annule: false }

  it('réclame la 1ʳᵉ réponse tant qu’elle n’est pas posée', () => {
    render(<TicketPremiereReponseChip ticket={ouvert} />)
    expect(screen.getByText(/1ʳᵉ réponse à faire/i)).toBeInTheDocument()
  })

  it('disparaît dès que la 1ʳᵉ réponse est enregistrée', () => {
    const { container } = render(
      <TicketPremiereReponseChip
        ticket={{ ...ouvert, date_premiere_reponse: '2026-07-31T09:00:00Z' }}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('ne réclame rien sur un ticket fermé ou annulé', () => {
    for (const t of [{ ...ouvert, statut: 'cloture' }, { ...ouvert, annule: true }]) {
      const { container } = render(<TicketPremiereReponseChip ticket={t} />)
      expect(container).toBeEmptyDOMElement()
    }
  })
})

describe('KanbanColumn (J144 — vue Kanban par statut)', () => {
  const tickets = [
    { id: 1, reference: 'SAV-001', client_nom: 'ACME', priorite: 'haute', statut: 'nouveau' },
    { id: 2, reference: 'SAV-002', client_nom: 'Globex', priorite: 'basse', statut: 'nouveau' },
  ]

  it('rend le libellé FR du statut en en-tête et le compte des cartes', () => {
    render(<KanbanColumn statut="nouveau" tickets={tickets} onSelect={() => {}} />)
    expect(screen.getByText(TICKET_STATUS_LABELS.nouveau)).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('SAV-001')).toBeInTheDocument()
    expect(screen.getByText('SAV-002')).toBeInTheDocument()
  })

  it('affiche un « — » quand la colonne est vide (état vide)', () => {
    render(<KanbanColumn statut="resolu" tickets={[]} onSelect={() => {}} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('appelle onSelect avec le ticket cliqué', async () => {
    const onSelect = vi.fn()
    render(<KanbanColumn statut="nouveau" tickets={tickets} onSelect={onSelect} />)
    await userEvent.click(screen.getByText('SAV-001'))
    expect(onSelect).toHaveBeenCalledWith(tickets[0])
  })
})

/* ADRG22 (C-ADRG-047) — l'écran n'offre que les gestes que la route accepte :
   écriture du ticket = `sav_gerer` ; réaffectation (« Technicien responsable »,
   « Assigner à … » en masse) = `sav_reassign`. Codes recopiés du registre
   (`apps/roles/permissions_registre.py`, rôles LIVRÉS Technicien / Commercial). */
const TECHNICIEN = ['equipement_voir', 'sav_voir', 'sav_gerer', 'sav_repondre_client_externe']
const COMMERCIAL = ['equipement_voir', 'sav_voir', 'ventes_creer']
const T1 = {
  id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif', priorite: 'normale',
  sous_garantie: 'non', sous_garantie_effectif: 'non', couverture: 'a_determiner',
  devis_id_ext: null, facture_id_ext: null, instructions: '', annule: false,
  technicien_responsable: 7, technicien_nom: 'Karim', client_nom: 'ACME',
}
const T2 = { ...T1, id: 2, reference: 'SAV-2', technicien_responsable: 8, technicien_nom: 'Yassine' }

function storeAdrg22(permissions, role = 'normal') {
  return configureStore({
    reducer: {
      tickets: (state = { items: [T1, T2], loading: false, error: null }) => state,
      auth: (state = { role, permissions }) => state,
    },
  })
}

function renderFiche(permissions) {
  return render(<Provider store={storeAdrg22(permissions)}><MemoryRouter>
    <TicketDetail ticket={T1} onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

const comboTechnicien = () => screen.getAllByRole('combobox')
  .find((c) => c.textContent === '— Non assigné —' || c.textContent === 'Karim')

describe("TicketDetail — ADRG22 gestes d'écriture selon les droits de la route", () => {
  it('Technicien (sav_gerer sans sav_reassign) : technicien en lecture, transitions et enregistrement présents', async () => {
    renderFiche(TECHNICIEN)
    await screen.findByText('SAV-1', { exact: false })
    expect(comboTechnicien()).toBeDisabled()
    expect(screen.getAllByRole('combobox').find((c) => c.textContent === 'En cours')).not.toBeDisabled()
    expect(screen.getByRole('button', { name: /Mettre à jour/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Annuler le ticket/ })).toBeInTheDocument()
  }, 60000)

  it("Commercial (sav_voir sans sav_gerer) : aucun geste d'écriture du ticket", async () => {
    renderFiche(COMMERCIAL)
    await screen.findByText('SAV-1', { exact: false })
    for (const nom of [/Mettre à jour/, /Annuler le ticket/, /^Noter$/, /Ajouter la pièce/,
      /Retirer une pièce/, /Ajouter une intervention/, /Planifier une intervention/,
      /Créer un devis/, /^Facturer$/, /Mettre en attente client/]) {
      expect(screen.queryByRole('button', { name: nom })).toBeNull()
    }
    expect(screen.getAllByRole('combobox').find((c) => c.textContent === 'En cours')).toBeDisabled()
    expect(comboTechnicien()).toBeDisabled()
  }, 60000)
})

async function actionsGroupees(permissions, role) {
  const user = userEvent.setup()
  render(<ThemeProvider><Provider store={storeAdrg22(permissions, role)}><MemoryRouter>
    <TicketsPage />
  </MemoryRouter></Provider></ThemeProvider>)
  const cases = await screen.findAllByRole('checkbox', { name: /^Sélectionner la ligne/ })
  await user.click(cases[0])
  await user.click(cases[1])
  const barre = await screen.findByRole('region', { name: /ligne\(s\) sélectionnée\(s\)/ })
  const plus = within(barre).queryByRole('button', { name: /Plus/ })
  if (plus) await user.click(plus)
  return document.body.textContent
}

describe('TicketsPage — ADRG22 « Assigner à … » en masse', () => {
  it('responsable (palier) : « Assigner à » proposé', async () => {
    expect(await actionsGroupees([], 'responsable')).toContain('Assigner à Karim')
  }, 60000)

  it('sans sav_reassign : aucun « Assigner à »', async () => {
    const texte = await actionsGroupees(TECHNICIEN)
    expect(texte).not.toContain('Assigner à')
  }, 60000)
})

/* AERR27 — J/K/Entrée/Échap de l'écran se taisent quand une boîte est posée
   par-dessus ou qu'une liste déroulante est ouverte. */
describe('TicketsPage — AERR27 raccourcis clavier gardés', () => {
  async function ouvrirFiche() {
    mockMatchMedia(true)
    render(<ThemeProvider><Provider store={storeAdrg22([], 'admin')}><MemoryRouter>
      <TicketsPage />
    </MemoryRouter></Provider></ThemeProvider>)
    await screen.findAllByText('SAV-1', { exact: false })
    fireEvent.keyDown(document.body, { key: 'j' })
    await waitFor(() => expect(document.querySelector('aside')?.getAttribute('aria-label')).toMatch(/SAV-1/))
  }

  it("Échap sur la boîte d'annulation : la fiche reste ouverte", async () => {
    await ouvrirFiche()
    fireEvent.click(screen.getByRole('button', { name: /Annuler le ticket/ }))
    const boite = await screen.findByRole('alertdialog')
    fireEvent.keyDown(boite, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(document.querySelector('aside')?.getAttribute('aria-label')).toMatch(/SAV-1/)
  }, 60000)

  it('k dans une listbox ouverte : sélection inchangée', async () => {
    await ouvrirFiche()
    fireEvent.keyDown(document.body, { key: 'j' })
    await waitFor(() => expect(document.querySelector('aside')?.getAttribute('aria-label')).toMatch(/SAV-2/))
    // Liste déroulante ouverte (contenu Radix porté dans <body>).
    const liste = document.createElement('div')
    liste.setAttribute('role', 'listbox')
    liste.tabIndex = 0
    document.body.appendChild(liste)
    fireEvent.keyDown(liste, { key: 'k' })
    expect(document.querySelector('aside')?.getAttribute('aria-label')).toMatch(/SAV-2/)
    liste.remove()
  }, 60000)
})

/* AERR32 — une relecture ratée (store `error`) garde les lignes déjà chargées
   et offre « Réessayer » ; l'écran d'erreur seul n'existe que sans ticket. */
describe('TicketsPage — AERR32 liste gardée pendant/après une relecture', () => {
  function rendre(etat) {
    const store = configureStore({
      reducer: {
        tickets: (state = etat) => state,
        auth: (state = { role: 'admin', permissions: [] }) => state,
      },
    })
    render(<ThemeProvider><Provider store={store}><MemoryRouter>
      <TicketsPage />
    </MemoryRouter></Provider></ThemeProvider>)
  }

  it('store error avec 2 tickets chargés : lignes visibles + Réessayer', async () => {
    rendre({ items: [T1, T2], loading: false, error: 'Erreur réseau' })
    expect(await screen.findAllByText('SAV-1', { exact: false })).not.toHaveLength(0)
    expect(screen.getAllByText('SAV-2', { exact: false })).not.toHaveLength(0)
    expect(screen.getByText(/Liste pas à jour/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Réessayer/ })).toBeInTheDocument()
  }, 60000)

  it('relecture en cours avec tickets chargés : pas de squelette, lignes visibles', async () => {
    rendre({ items: [T1, T2], loading: true, error: null })
    expect(await screen.findAllByText('SAV-1', { exact: false })).not.toHaveLength(0)
  }, 60000)
})

/* AERR82 — retirer une pièce (déjà sortie du stock) d'un ticket passe par une
   confirmation qui nomme la pièce et sa quantité. */
describe('TicketDetail — AERR82 retrait de pièce confirmé', () => {
  it('Retirer puis Annuler : aucun retrait ; Retirer confirmé : un appel', async () => {
    savApi.getTicketPieces.mockResolvedValue({
      data: [{ id: 31, produit_nom: 'Fusible 15 A', quantite: 2, stock_decremente: true }],
    })
    savApi.removeTicketPiece = vi.fn(() => Promise.resolve({ data: {} }))
    render(<Provider store={storeAdrg22([], 'admin')}><MemoryRouter><ConfirmProvider>
      <TicketDetail ticket={T1} onClose={() => {}} onSaved={() => {}} />
    </ConfirmProvider></MemoryRouter></Provider>)
    const ligne = (await screen.findByText(/Fusible 15 A/)).closest('li')
    fireEvent.click(within(ligne).getByRole('button', { name: /Retirer/ }))
    const boite = await screen.findByRole('alertdialog')
    expect(boite.textContent).toContain('Fusible 15 A × 2')
    fireEvent.click(within(boite).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(savApi.removeTicketPiece).not.toHaveBeenCalled()

    fireEvent.click(within(ligne).getByRole('button', { name: /Retirer/ }))
    const boite2 = await screen.findByRole('alertdialog')
    fireEvent.click(within(boite2).getByRole('button', { name: 'Retirer' }))
    await waitFor(() => expect(savApi.removeTicketPiece).toHaveBeenCalledWith(1, 31))
    savApi.getTicketPieces.mockReset()
    savApi.getTicketPieces.mockImplementation(() => Promise.resolve({ data: [] }))
  }, 60000)
})

/* ACNC26 — « Retirer » d'une pièce est désactivé pendant l'envoi (un double
   clic ne lance jamais deux retraits de la même pièce). */
describe('TicketDetail — ACNC26 retrait de pièce non doublé', () => {
  it('« Retirer » désactivé pendant l'envoi', async () => {
    savApi.getTicketPieces.mockResolvedValue({
      data: [{ id: 31, produit_nom: 'Fusible 15 A', quantite: 2, stock_decremente: true }],
    })
    let finir
    savApi.removeTicketPiece = vi.fn(() => new Promise((ok) => { finir = ok }))
    render(<Provider store={storeAdrg22([], 'admin')}><MemoryRouter><ConfirmProvider>
      <TicketDetail ticket={T1} onClose={() => {}} onSaved={() => {}} />
    </ConfirmProvider></MemoryRouter></Provider>)
    const ligne = (await screen.findByText(/Fusible 15 A/)).closest('li')
    fireEvent.click(within(ligne).getByRole('button', { name: /Retirer/ }))
    const boite = await screen.findByRole('alertdialog')
    fireEvent.click(within(boite).getByRole('button', { name: 'Retirer' }))
    await waitFor(() => expect(savApi.removeTicketPiece).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(within(ligne).getByRole('button', { name: /Retirer/ })).toBeDisabled())
    finir({ data: {} })
    savApi.getTicketPieces.mockReset()
    savApi.getTicketPieces.mockImplementation(() => Promise.resolve({ data: [] }))
  }, 60000)
})
