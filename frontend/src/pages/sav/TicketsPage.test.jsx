import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'

// PACT142 — le panneau « mémo vocal » appelle `POST /ai/cr-intervention/` via
// l'instance axios partagée : elle est mockée pour tout ce fichier (les autres
// suites ne rendent que des briques de présentation, sans réseau).
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../api/axios'
import {
  StatutPill,
  PrioriteBadge,
  TicketSlaBadge,
  TicketSlaEcheanceChip,
  TicketPremiereReponseChip,
  KanbanColumn,
  CrVocalMemo,
  crEnTexte,
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

/* ===========================================================================
   PACT142 — Compte rendu d'intervention depuis un MÉMO VOCAL (NTAI12)
   ===========================================================================
   Ce que la tâche exige et que ces tests verrouillent :
     • un mémo vocal PRÉ-REMPLIT le formulaire de rapport, ÉDITABLE avant
       sauvegarde ;
     • le statut du ticket n'est JAMAIS changé et l'audio n'est JAMAIS conservé
       (aucune écriture n'est émise depuis ce panneau : un seul POST, vers
       l'endpoint de génération) ;
     • sans clé de transcription, un message EXPLICITE remplace le sélecteur de
       fichier — jamais un téléversement qui échoue en silence, et jamais une
       erreur brute pour les autres échecs. */

// Un vrai conteneur OGG en tête (le serveur reconnaît le format aux octets
// magiques, jamais au Content-Type déclaré) : le fichier de test lui ressemble.
const memoOgg = () => new File(
  [new Uint8Array([0x4f, 0x67, 0x67, 0x53])], 'memo.ogg', { type: 'audio/ogg' })

const REPONSE_CR = {
  ticket_id: 42,
  transcript: "Onduleur en défaut 14, j'ai repris les connecteurs.",
  cr: {
    diagnostic: 'Défaut 14 — isolement DC faible côté string 2.',
    travaux: 'Connecteurs MC4 refaits, bornier resserré.',
    pieces: '2 connecteurs MC4.',
    recommandations: 'Recontrôler l’isolement sous 3 mois.',
  },
  structure: true,
  applique: false,
  source: 'zhipu',
}

/* Le formulaire d'intervention réduit à son câblage RÉEL (une seule ligne dans
   TicketDetail) : le panneau pré-remplit « Compte rendu », qui reste éditable
   tant que « Ajouter une intervention » n'a pas été cliqué. */
function FormulaireCr({ ticketId = 42 }) {
  const [compteRendu, setCompteRendu] = useState('')
  return (
    <div>
      <CrVocalMemo ticketId={ticketId} onPrefill={(texte) => setCompteRendu(texte)} />
      <label>
        Compte rendu
        <textarea value={compteRendu} onChange={(e) => setCompteRendu(e.target.value)} />
      </label>
    </div>
  )
}

describe('crEnTexte (PACT142 — aplatissement du CR structuré)', () => {
  it('respecte l’ordre des sections du serveur et omet les sections vides', () => {
    expect(crEnTexte({
      diagnostic: 'A', travaux: '', pieces: 'C', recommandations: 'D',
    })).toBe('Diagnostic : A\nPièces : C\nRecommandations : D')
  })

  it('rend une chaîne vide quand le serveur n’a rien structuré', () => {
    expect(crEnTexte({})).toBe('')
    expect(crEnTexte(null)).toBe('')
  })
})

describe('CrVocalMemo (PACT142 — mémo vocal → rapport pré-rempli)', () => {
  beforeEach(() => {
    api.post.mockReset()
    api.patch.mockReset()
  })

  it('pré-remplit le compte rendu avec les 4 sections, sans toucher au ticket', async () => {
    api.post.mockResolvedValue({ data: REPONSE_CR })
    render(<FormulaireCr />)

    await userEvent.upload(
      screen.getByLabelText("Mémo vocal de l'intervention"), memoOgg())

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    const [url, corps] = api.post.mock.calls[0]
    expect(url).toBe('/ai/cr-intervention/')
    expect(corps).toBeInstanceOf(FormData)
    expect(corps.get('file').name).toBe('memo.ogg')
    expect(corps.get('ticket_id')).toBe('42')

    // Le rapport est pré-rempli, sections dans l'ordre du serveur.
    await waitFor(() => expect(screen.getByLabelText('Compte rendu')).toHaveValue(
      'Diagnostic : Défaut 14 — isolement DC faible côté string 2.\n'
      + 'Travaux : Connecteurs MC4 refaits, bornier resserré.\n'
      + 'Pièces : 2 connecteurs MC4.\n'
      + 'Recommandations : Recontrôler l’isolement sous 3 mois.'))

    // Aucune écriture sur le ticket : le seul appel est la génération.
    expect(api.patch).not.toHaveBeenCalled()
    expect(api.post).toHaveBeenCalledTimes(1)

    // Le contrat (audio non conservé, statut inchangé) est DIT à l'écran.
    expect(screen.getByText(/l’audio n’est pas conservé/i)).toBeInTheDocument()
    expect(screen.getByText(/statut du ticket n’est jamais modifié/i)).toBeInTheDocument()
  })

  it('le compte rendu reste ÉDITABLE avant enregistrement', async () => {
    api.post.mockResolvedValue({
      data: {
        ...REPONSE_CR,
        cr: { diagnostic: 'Défaut 14.', travaux: '', pieces: '', recommandations: '' },
      },
    })
    render(<FormulaireCr />)
    await userEvent.upload(
      screen.getByLabelText("Mémo vocal de l'intervention"), memoOgg())

    const zone = screen.getByLabelText('Compte rendu')
    await waitFor(() => expect(zone).toHaveValue('Diagnostic : Défaut 14.'))
    await userEvent.type(zone, ' Repris par le technicien.')
    expect(zone).toHaveValue('Diagnostic : Défaut 14. Repris par le technicien.')
  })

  it('sans clé de transcription (503), le message serveur REMPLACE le sélecteur', async () => {
    api.post.mockRejectedValue({
      response: {
        status: 503,
        data: {
          detail: "Aucun fournisseur de transcription n'est configuré (clé "
            + 'absente) — saisie manuelle requise.',
        },
      },
    })
    render(<FormulaireCr />)
    await userEvent.upload(
      screen.getByLabelText("Mémo vocal de l'intervention"), memoOgg())

    expect(await screen.findByText(
      "Aucun fournisseur de transcription n'est configuré (clé absente) — "
      + 'saisie manuelle requise.',
    )).toBeInTheDocument()
    expect(screen.queryByLabelText("Mémo vocal de l'intervention")).toBeNull()
  })

  it('tout autre échec est AFFICHÉ en clair, le sélecteur reste disponible', async () => {
    api.post.mockRejectedValue({
      response: {
        status: 400,
        data: { detail: 'Format audio non reconnu (OGG, WAV, MP3, M4A, FLAC ou WebM).' },
      },
    })
    render(<FormulaireCr />)
    await userEvent.upload(
      screen.getByLabelText("Mémo vocal de l'intervention"), memoOgg())

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(
      'Format audio non reconnu (OGG, WAV, MP3, M4A, FLAC ou WebM).')
    // Un échec récupérable ne condamne pas le panneau (≠ clé absente).
    expect(screen.getByLabelText("Mémo vocal de l'intervention")).toBeInTheDocument()
    expect(screen.getByLabelText('Compte rendu')).toHaveValue('')
  })

  it('sans structuration, la dictée transcrite est proposée telle quelle et DITE comme telle', async () => {
    api.post.mockResolvedValue({
      data: {
        ticket_id: 42,
        transcript: 'Onduleur redémarré, tout est rentré dans l’ordre.',
        cr: { diagnostic: '', travaux: '', pieces: '', recommandations: '' },
        structure: false, applique: false, source: 'zhipu',
      },
    })
    render(<FormulaireCr />)
    await userEvent.upload(
      screen.getByLabelText("Mémo vocal de l'intervention"), memoOgg())

    await waitFor(() => expect(screen.getByLabelText('Compte rendu')).toHaveValue(
      'Onduleur redémarré, tout est rentré dans l’ordre.'))
    expect(screen.getByText(/non structuré/i)).toBeInTheDocument()
  })

  it('sans ticket lié, aucun ticket_id n’est envoyé', async () => {
    api.post.mockResolvedValue({ data: REPONSE_CR })
    render(<FormulaireCr ticketId={null} />)
    await userEvent.upload(
      screen.getByLabelText("Mémo vocal de l'intervention"), memoOgg())

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    expect(api.post.mock.calls[0][1].get('ticket_id')).toBeNull()
  })
})
