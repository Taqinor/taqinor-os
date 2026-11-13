import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR210 — hors-ligne terrain : la consommation matériel (F11) et les n° de
   série (F9) partaient en direct et étaient PERDUS sans réseau, alors que les
   handlers serveur `intervention.consommation_ligne` / `intervention.serial`
   existaient depuis N91. Ce test vérifie le CÂBLAGE :
   (1) échec RÉSEAU → op enfilée avec le bon op_type et la bonne charge ;
   (2) erreur APPLICATIVE 4xx → jamais enfilée, elle reste visible ;
   (3) la photo de plaque part dans la file BINAIRE existante ;
   hors périmètre (inchangés) : `addExtra` et `validerConsommation`. */

const outbox = vi.hoisted(() => {
  const enqueue = vi.fn(() => Promise.resolve('op-1'))
  return {
    enqueue,
    queuePhoto: vi.fn(() => Promise.resolve('photo-1')),
    FIELD_OPS: {
      SERIAL: 'intervention.serial',
      CONSOMMATION_LIGNE: 'intervention.consommation_ligne',
    },
    // Reproduit fidèlement la règle du vrai helper : pas de `response` axios
    // = panne réseau (on enfile) ; sinon c'est une erreur applicative (on
    // relance, jamais d'enfilage).
    withOfflineFallback: async (onlineCall, opType, payload, meta) => {
      try {
        const data = await onlineCall()
        return { queued: false, data }
      } catch (err) {
        if (err?.response) throw err
        const clientOpId = await (meta === undefined ? enqueue(opType, payload) : enqueue(opType, payload, meta))
        return { queued: true, clientOpId }
      }
    },
  }
})

vi.mock('./offline/fieldOutbox', () => (
  import('./InterventionCapturePanels.testkit.js').then((m) => m.fieldOutboxMock(outbox))
))

const api = vi.hoisted(() => ({
  getSerials: vi.fn(),
  ajouterSerial: vi.fn(),
  supprimerSerial: vi.fn(),
  getConsommation: vi.fn(),
  modifierLigneConsommation: vi.fn(),
  ajouterLigneConsommation: vi.fn(),
  validerConsommation: vi.fn(),
  getFiche: vi.fn(),
  renseignerFiche: vi.fn(),
  getReserves: vi.fn(),
  ajouterReserve: vi.fn(),
}))
vi.mock('../../api/installationsApi', () => ({ default: api }))

vi.mock('../../pages/preferences/prefs', () => (
  import('./InterventionCapturePanels.testkit.js').then((m) => m.prefsMock())
))

const toasts = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, success: toasts.success, error: toasts.error } }
})

import { SerialsPanel, ConsommationPanel, FichePanel, ReservesPanel } from './InterventionCapturePanels'

const INTERVENTION = { id: 42 }

const CONSOMMATION = {
  valide: false,
  lignes: [
    {
      id: 5, designation: 'Panneau 450W', quantite_prevue: '10',
      quantite_utilisee: '10', variance: 0, justification: '',
      justification_requise: false, hors_nomenclature: false,
    },
  ],
}

// axios : une panne réseau n'a PAS de `response` ; un refus serveur en a une.
const erreurReseau = () => Object.assign(new Error('Network Error'), { response: undefined })
const erreur400 = () => ({ response: { status: 400, data: { detail: 'Quantité invalide.' } } })

beforeEach(() => {
  api.getSerials.mockResolvedValue({ data: [] })
  api.ajouterSerial.mockResolvedValue({ data: { id: 1 } })
  api.getConsommation.mockResolvedValue({ data: CONSOMMATION })
  api.modifierLigneConsommation.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ConsommationPanel — WIR210 hors-ligne (F11)', () => {
  it('échec réseau → op enfilée en `intervention.consommation_ligne`', async () => {
    const user = userEvent.setup()
    api.modifierLigneConsommation.mockRejectedValue(erreurReseau())
    render(<ConsommationPanel intervention={INTERVENTION} />)

    const champ = await screen.findByDisplayValue('10')
    await user.clear(champ)
    await user.type(champ, '12')
    await user.tab()

    await waitFor(() => expect(outbox.enqueue).toHaveBeenCalledWith(
      'intervention.consommation_ligne',
      { intervention: 42, ligne: 5, quantite_utilisee: '12' },
      { baseUpdatedAt: undefined },
    ))
    expect(toasts.success).toHaveBeenCalledWith(
      'Hors ligne — enregistré, synchro au retour du réseau.')
  })

  it("échec réseau → l'op enfilée porte la version lue", async () => {
    const user = userEvent.setup()
    api.getConsommation.mockResolvedValue({ data: {
      ...CONSOMMATION,
      lignes: [{ ...CONSOMMATION.lignes[0], date_modification: '2026-09-30T16:00:00Z' }],
    } })
    api.modifierLigneConsommation.mockRejectedValue(erreurReseau())
    render(<ConsommationPanel intervention={INTERVENTION} />)

    const champ = await screen.findByDisplayValue('10')
    await user.clear(champ)
    await user.type(champ, '8')
    await user.tab()

    await waitFor(() => expect(outbox.enqueue).toHaveBeenCalledWith(
      'intervention.consommation_ligne',
      { intervention: 42, ligne: 5, quantite_utilisee: '8' },
      { baseUpdatedAt: '2026-09-30T16:00:00Z' },
    ))
  })

  it('erreur applicative 4xx → JAMAIS enfilée, elle reste visible', async () => {
    const user = userEvent.setup()
    api.modifierLigneConsommation.mockRejectedValue(erreur400())
    render(<ConsommationPanel intervention={INTERVENTION} />)

    const champ = await screen.findByDisplayValue('10')
    await user.clear(champ)
    await user.type(champ, '12')
    await user.tab()

    // AERR86 — le toast global (intercepteur) dit la cause : aucun toast local en double.
    await waitFor(() => expect(api.modifierLigneConsommation).toHaveBeenCalled())
    expect(toasts.error).not.toHaveBeenCalled()
    expect(outbox.enqueue).not.toHaveBeenCalled()
  })
})

describe('SerialsPanel — WIR210 hors-ligne (F9)', () => {
  it('échec réseau → op enfilée en `intervention.serial`', async () => {
    const user = userEvent.setup()
    api.ajouterSerial.mockRejectedValue(erreurReseau())
    render(<SerialsPanel intervention={INTERVENTION} />)

    await user.type(
      await screen.findByPlaceholderText('Composant (onduleur, panneau…)'), 'Onduleur')
    await user.type(screen.getByPlaceholderText('N° de série (optionnel)'), 'SN-1234')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))

    await waitFor(() => expect(outbox.enqueue).toHaveBeenCalledWith(
      'intervention.serial',
      // Revue chantier 26/10/2026 — la source de capture voyage aussi.
      { intervention: 42, designation: 'Onduleur', numero_serie: 'SN-1234',
        capture_source: 'saisie' },
    ))
    expect(toasts.success).toHaveBeenCalledWith(
      'Hors ligne — enregistré, synchro au retour du réseau.')
    // Aucune photo choisie : la file binaire n'est pas sollicitée.
    expect(outbox.queuePhoto).not.toHaveBeenCalled()
  })

  it('erreur applicative 4xx → JAMAIS enfilée, le détail serveur reste visible', async () => {
    const user = userEvent.setup()
    api.ajouterSerial.mockRejectedValue({
      response: { status: 400, data: { detail: 'N° déjà relevé.' } },
    })
    render(<SerialsPanel intervention={INTERVENTION} />)

    await user.type(
      await screen.findByPlaceholderText('Composant (onduleur, panneau…)'), 'Onduleur')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))

    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith('N° déjà relevé.'))
    expect(outbox.enqueue).not.toHaveBeenCalled()
  })
})

// ACSV91 — panneau « Fiche d'intervention » (relevé du gabarit).
describe('FichePanel', () => {
  const RELEVE = {
    id: 1,
    valeurs: [
      { id: 11, champ_libelle: 'Disjoncteur testé', champ_type: 'case', champ_obligatoire: true, valeur: '' },
      { id: 12, champ_libelle: 'Tension DC', champ_type: 'mesure', champ_unite: 'V', champ_obligatoire: false, valeur: '' },
    ],
  }
  beforeEach(() => {
    api.getFiche.mockResolvedValue({ data: RELEVE })
    api.renseignerFiche.mockResolvedValue({ data: RELEVE })
  })

  it('cocher la case obligatoire envoie « true »', async () => {
    const user = userEvent.setup()
    render(<FichePanel intervention={INTERVENTION} />)
    await user.click(await screen.findByRole('checkbox'))
    await waitFor(() => expect(api.renseignerFiche).toHaveBeenCalledWith(42, 11, 'true'))
  })

  it('la mesure saisie part telle quelle à la sortie du champ, le refus serveur s\'affiche', async () => {
    const user = userEvent.setup()
    api.renseignerFiche.mockRejectedValue({ response: { status: 400, data: { valeur: ['« Tension DC » attend un nombre.'] } } })
    render(<FichePanel intervention={INTERVENTION} />)
    await user.type(await screen.findByLabelText(/Tension DC/), '235,4')
    await user.tab()
    await waitFor(() => expect(api.renseignerFiche).toHaveBeenCalledWith(42, 12, '235,4'))
    expect(await screen.findByRole('alert')).toBeTruthy()
  })

  it('aucun gabarit : panneau masqué', async () => {
    api.getFiche.mockResolvedValue({ data: null })
    const { container } = render(<FichePanel intervention={INTERVENTION} />)
    await waitFor(() => expect(api.getFiche).toHaveBeenCalled())
    expect(container.textContent).toBe('')
  })
})

describe('FichePanel — saisie pendant un envoi', () => {
  it('une saisie faite pendant un envoi survit à la relecture', async () => {
    const user = userEvent.setup()
    const releve = {
      id: 1,
      valeurs: [
        { id: 21, champ_libelle: 'Tension', champ_type: 'mesure', champ_unite: 'V', champ_obligatoire: false, valeur: '' },
        { id: 22, champ_libelle: 'Courant', champ_type: 'mesure', champ_unite: 'A', champ_obligatoire: false, valeur: '' },
      ],
    }
    api.getFiche.mockResolvedValue({ data: releve })
    let fin
    api.renseignerFiche.mockImplementationOnce(() => new Promise((res) => { fin = () => res({ data: releve }) }))
    api.renseignerFiche.mockResolvedValue({ data: releve })
    render(<FichePanel intervention={INTERVENTION} />)
    await user.type(await screen.findByLabelText(/Tension/), '230')
    await user.tab()
    await waitFor(() => expect(api.renseignerFiche).toHaveBeenCalledWith(42, 21, '230'))
    const b = screen.getByLabelText(/Courant/)
    await user.type(b, '12')
    fin()
    await waitFor(() => expect(api.getFiche.mock.calls.length).toBeGreaterThan(1))
    expect(screen.getByLabelText(/Courant/).value).toBe('12')
    await user.tab()
    await waitFor(() => expect(api.renseignerFiche).toHaveBeenCalledWith(42, 22, '12'))
  })
})

// AERR77 — valider la consommation sort le stock pour de bon : boîte nommée d'abord.
describe('ConsommationPanel — AERR77 confirmation de validation', () => {
  it('Valider puis Annuler : aucun appel ; boîte nommée', async () => {
    const { ConfirmProvider } = await import('../../providers/ConfirmProvider')
    api.getConsommation.mockResolvedValue({ data: { valide: false, lignes: [
      { ...CONSOMMATION.lignes[0], id: 5, designation: 'Panneau 450W', quantite_utilisee: '12' },
      { ...CONSOMMATION.lignes[0], id: 6, designation: 'Onduleur 5 kW', quantite_utilisee: '1' },
    ] } })
    api.validerConsommation.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    render(<ConfirmProvider><ConsommationPanel intervention={{ id: 42, reference: 'INT-0042' }} /></ConfirmProvider>)
    await user.click(await screen.findByRole('button', { name: /Valider la consommation/ }))
    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent('INT-0042')
    expect(boite).toHaveTextContent('12 × Panneau 450W')
    expect(boite).toHaveTextContent('1 × Onduleur 5 kW')
    expect(boite).toHaveTextContent('définitive')
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(api.validerConsommation).not.toHaveBeenCalled()

    // CAD177 — le verrou anti-double-clic du Button tombe après 400 ms sans
    // rendu du bouton (Annuler ne le re-rend pas).
    await new Promise((r) => setTimeout(r, 450))
    await user.click(screen.getByRole('button', { name: /Valider la consommation/ }))
    await screen.findByRole('alertdialog')
    await user.click(screen.getByRole('button', { name: 'Valider' }))
    await waitFor(() => expect(api.validerConsommation).toHaveBeenCalledTimes(1))
    expect(api.validerConsommation).toHaveBeenCalledWith(42)
  })
})

// AERR86 — un refus serveur n'ajoute pas de toast local générique au toast global.
describe('ReservesPanel — AERR86 pas de toast local en double', () => {
  it('ajout de réserve refusé : aucun toast local, la saisie reste', async () => {
    api.getReserves.mockResolvedValue({ data: [] })
    api.ajouterReserve.mockRejectedValue({ response: { status: 400, data: { detail: 'Réserve déjà levée.' } } })
    const user = userEvent.setup()
    render(<ReservesPanel intervention={INTERVENTION} />)
    const saisie = await screen.findByPlaceholderText(/Réserve à reprendre/)
    await user.type(saisie, 'Câble manquant')
    await user.click(screen.getByRole('button', { name: 'Ajouter la réserve' }))
    await waitFor(() => expect(api.ajouterReserve).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByRole('button', { name: 'Ajouter la réserve' })).not.toBeDisabled())
    expect(toasts.error).not.toHaveBeenCalled()
    expect(outbox.enqueue).not.toHaveBeenCalled()
    expect(saisie).toHaveValue('Câble manquant')
  })
})
