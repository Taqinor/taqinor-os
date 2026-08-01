import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* AOF181 — l'analyse du cahier des charges devient un écran.
   Trois garanties prouvées ici :
     1. le jeu de clauses FRDISI se saisit INTÉGRALEMENT (ratio DC/AC 0,75-1,
        plafond 60 kWc/onduleur, caution provisoire en montant ABSOLU, validité
        75 jours) — avec sa source (pièce du DCE + page) et son caractère
        bloquant, et sans qu'aucun nombre tapé ne soit normalisé ;
     2. une clause bloquante non satisfaite s'affiche en rouge et EMPÊCHE
        `pret_a_deposer`, motif écrit sur le bouton ;
     3. aucun chiffre de conformité n'est calculé côté front : une clause que le
        serveur n'a pas évaluée reste « Non évalué », même quand la valeur
        constatée est là et qu'une comparaison serait « évidente ». */

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), update: vi.fn() }))
const toastMocks = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '7' }) }
})

vi.mock('../../../api/aoApi', () => ({
  default: {
    exigencesCps: { list: mocks.list, create: mocks.create },
    affaires: { update: mocks.update },
  },
}))

vi.mock('../../../ui', async () => {
  const actual = await vi.importActual('../../../ui')
  return { ...actual, toast: { success: toastMocks.success, error: toastMocks.error } }
})

// L'aperçu réel (AOF175) charge pdfjs : on prouve seulement qu'il est BRANCHÉ.
vi.mock('../dossier/PiecePreview', () => ({
  default: ({ piece }) => <div data-testid="apercu-cps">{piece ? piece.libelle : 'aucune pièce'}</div>,
}))

import ExigencesPage, { payloadClause, estIntervalle } from './ExigencesPage'
import {
  statutConformite, severiteAffichee, exigencesBloquantes, motifBlocageDepot, valeurExigee,
} from './ConformiteTable'

// Le jeu de clauses FRDISI, tel qu'il sera saisi par l'écran.
const RATIO = {
  id: 1, code: 'ratio_dc_ac', libelle: 'Ratio DC/AC admissible', type: 'intervalle',
  valeur_min: '0,75', valeur_max: '1', bloquant: true,
  source_piece: 'CPS — article 12', source_page: '34',
  conformite: {
    statut: 'conforme', valeur_constatee: '0,92',
    origine_label: 'Chaîne électrique', message: null,
  },
}
const PLAFOND = {
  id: 2, code: 'plafond_onduleur', libelle: 'Puissance maximale par onduleur',
  type: 'plafond', valeur: '60', unite: 'kWc/onduleur', bloquant: true,
  source_piece: 'CPS — article 12', source_page: '35',
  conformite: {
    statut: 'non_conforme', valeur_constatee: '66 kWc',
    origine_label: 'Chaîne électrique',
    message: 'Un onduleur du bâtiment C dépasse le plafond : 66 kWc pour 60 admis.',
  },
}
const CAUTION = {
  id: 3, code: 'caution_provisoire', libelle: 'Caution provisoire',
  type: 'montant', valeur: '40000', unite: 'MAD', bloquant: true,
  source_piece: "Règlement de consultation", source_page: '8',
  conformite: { statut: 'conforme', valeur_constatee: '40 000 MAD', origine_label: 'Contrôleur avant dépôt' },
}
const VALIDITE = {
  id: 4, code: 'validite_offre', libelle: 'Validité des offres', type: 'duree',
  valeur: '75', unite: 'jours', bloquant: false,
  source_piece: 'Règlement de consultation', source_page: '9',
  a_reverifier: true, erratum_ref: 'n° 2/2026',
  conformite: { statut: 'non_conforme', message: 'La lettre de soumission annonce 60 jours.' },
}
// Clause NON évaluée par le serveur : le front ne doit RIEN en conclure.
const NON_EVALUEE = {
  id: 5, code: 'garantie_decennale', libelle: 'Garantie décennale', type: 'texte',
  valeur_texte: 'Exigée', bloquant: true, source_piece: 'CPS — article 30',
  conformite: { valeur_constatee: 'Fournie' },
}

const liste = (items) => ({ data: { results: items } })

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue(liste([RATIO, PLAFOND, CAUTION, VALIDITE]))
  mocks.create.mockResolvedValue({ data: { id: 99 } })
  mocks.update.mockResolvedValue({ data: {} })
})

describe('ExigencesPage (AOF181)', () => {
  it('affiche le tableau de conformité avec la source DCE et l’origine du constat', async () => {
    render(<ExigencesPage />)
    expect(await screen.findByText('Ratio DC/AC admissible')).toBeInTheDocument()
    expect(screen.getByText('0,75 – 1')).toBeInTheDocument()
    expect(screen.getByText('≤ 60 kWc/onduleur')).toBeInTheDocument()
    expect(screen.getAllByText(/CPS — article 12, p\. 3[45]/)).toHaveLength(2)
    expect(screen.getAllByText('Chaîne électrique')).toHaveLength(2)
    expect(document.querySelectorAll('[data-ao-controle]')).toHaveLength(4)
  })

  it('une clause bloquante non satisfaite est rouge et EMPÊCHE « prêt à déposer », motif écrit sur le bouton', async () => {
    render(<ExigencesPage />)
    const bouton = await screen.findByRole('button', { name: /^Dépôt bloqué —/ })
    expect(bouton).toBeDisabled()
    expect(bouton).toHaveAccessibleName(/66 kWc pour 60 admis/)
    // La ligne fautive porte la pastille « Bloquant » du socle partagé.
    expect(screen.getByText('Bloquant')).toBeInTheDocument()
    expect(mocks.update).not.toHaveBeenCalled()
  })

  it('sans clause bloquante non satisfaite, le dépôt redevient possible', async () => {
    mocks.list.mockResolvedValue(liste([RATIO, CAUTION, VALIDITE]))
    const onPretADeposer = vi.fn().mockResolvedValue({})
    render(<ExigencesPage onPretADeposer={onPretADeposer} />)
    const bouton = await screen.findByRole('button', { name: 'Marquer « prêt à déposer »' })
    expect(bouton).toBeEnabled()
    fireEvent.click(bouton)
    await waitFor(() => expect(onPretADeposer).toHaveBeenCalled())
  })

  it('aucun chiffre de conformité côté front : une clause non évaluée reste « Non évalué »', async () => {
    mocks.list.mockResolvedValue(liste([NON_EVALUEE]))
    render(<ExigencesPage />)
    expect(await screen.findByText('Non évalué')).toBeInTheDocument()
    // Une valeur constatée présente ne suffit JAMAIS à conclure « conforme ».
    expect(screen.queryByText('OK')).not.toBeInTheDocument()
    // …et une clause bloquante non évaluée ne bloque pas non plus (le verdict
    // appartient au serveur, dans les deux sens).
    expect(await screen.findByRole('button', { name: 'Marquer « prêt à déposer »' })).toBeEnabled()
  })

  it('signale les exigences à revérifier après erratum', async () => {
    render(<ExigencesPage />)
    expect(await screen.findByText('Exigences à revérifier après erratum')).toBeInTheDocument()
    expect(screen.getAllByText(/erratum n° 2\/2026/).length).toBeGreaterThan(0)
  })

  it('le jeu de clauses FRDISI se saisit intégralement, valeurs NON normalisées', async () => {
    render(<ExigencesPage />)
    await screen.findByText('Ratio DC/AC admissible')

    const saisir = async (champs, { intervalle = false, bloquant = true } = {}) => {
      fireEvent.change(screen.getByLabelText(/^Type$/), { target: { value: champs.type } })
      fireEvent.change(screen.getByLabelText(/Intitulé de la clause/), { target: { value: champs.libelle } })
      fireEvent.change(
        screen.getByLabelText(intervalle ? /^Valeur minimale$/ : /^Valeur$/),
        { target: { value: champs.valeur } },
      )
      if (intervalle) {
        fireEvent.change(screen.getByLabelText(/^Valeur maximale$/), { target: { value: champs.valeurMax } })
      }
      fireEvent.change(screen.getByLabelText(/^Unité$/), { target: { value: champs.unite ?? '' } })
      fireEvent.change(screen.getByLabelText(/Pièce du DCE/), { target: { value: champs.source } })
      fireEvent.change(screen.getByLabelText(/^Page$/), { target: { value: champs.page } })
      if (!bloquant) fireEvent.click(screen.getByRole('checkbox', { name: 'Clause bloquante' }))
      fireEvent.click(screen.getByRole('button', { name: 'Ajouter la clause' }))
      // Le formulaire se vide APRÈS la réponse serveur : attendre la remise à
      // zéro évite que la clause suivante soit tapée dans un champ encore plein.
      await waitFor(() => expect(screen.getByLabelText(/Intitulé de la clause/)).toHaveValue(''))
    }

    // 1. Ratio DC/AC 0,75-1 — un intervalle, virgule décimale intacte.
    await saisir({
      type: 'intervalle', libelle: 'Ratio DC/AC admissible',
      valeur: '0,75', valeurMax: '1', source: 'CPS — article 12', page: '34',
    }, { intervalle: true })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1))
    expect(mocks.create.mock.calls[0][0]).toEqual({
      affaire: '7', libelle: 'Ratio DC/AC admissible', type: 'intervalle', bloquant: true,
      source_piece: 'CPS — article 12', source_page: '34', unite: null,
      valeur_min: '0,75', valeur_max: '1',
    })

    // 2. Plafond 60 kWc par onduleur.
    await saisir({
      type: 'plafond', libelle: 'Puissance maximale par onduleur',
      valeur: '60', unite: 'kWc/onduleur', source: 'CPS — article 12', page: '35',
    })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(2))
    expect(mocks.create.mock.calls[1][0]).toMatchObject({
      type: 'plafond', valeur: '60', unite: 'kWc/onduleur', bloquant: true,
    })

    // 3. Caution provisoire en MONTANT ABSOLU (jamais un pourcentage déduit).
    await saisir({
      type: 'montant', libelle: 'Caution provisoire',
      valeur: '40000', unite: 'MAD', source: 'Règlement de consultation', page: '8',
    })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(3))
    expect(mocks.create.mock.calls[2][0]).toMatchObject({
      type: 'montant', valeur: '40000', unite: 'MAD',
    })

    // 4. Validité des offres 75 jours, clause NON bloquante.
    await saisir({
      type: 'duree', libelle: 'Validité des offres',
      valeur: '75', unite: 'jours', source: 'Règlement de consultation', page: '9',
    }, { bloquant: false })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(4))
    expect(mocks.create.mock.calls[3][0]).toMatchObject({
      type: 'duree', valeur: '75', unite: 'jours', bloquant: false,
    })
  })

  it('l’aperçu du CPS est branché sur le composant partagé (AOF175), pas réécrit', async () => {
    render(<ExigencesPage pieceCps={{ id: 3, libelle: 'CPS — lot 2' }} />)
    expect(await screen.findByTestId('apercu-cps')).toHaveTextContent('CPS — lot 2')
  })
})

describe('ConformiteTable — verdicts purs (AOF181)', () => {
  it('le statut vient du serveur, jamais d’une comparaison locale', () => {
    expect(statutConformite(PLAFOND)).toBe('non_conforme')
    expect(statutConformite({ statut_conformite: 'conforme' })).toBe('conforme')
    expect(statutConformite(NON_EVALUEE)).toBe('non_evalue')
    expect(statutConformite({})).toBe('non_evalue')
  })

  it('sévérité affichée : bloquante non satisfaite = bloquant, non bloquante = avertissement', () => {
    expect(severiteAffichee(RATIO)).toBe('ok')
    expect(severiteAffichee(PLAFOND)).toBe('bloquant')
    expect(severiteAffichee(VALIDITE)).toBe('avertissement')
    expect(severiteAffichee(NON_EVALUEE)).toBeNull()
  })

  it('motifBlocageDepot ne retient que les bloquantes non satisfaites', () => {
    expect(exigencesBloquantes([RATIO, PLAFOND, VALIDITE])).toEqual([PLAFOND])
    expect(motifBlocageDepot([RATIO, PLAFOND])).toBe(PLAFOND.conformite.message)
    expect(motifBlocageDepot([RATIO, CAUTION, VALIDITE])).toBeNull()
    expect(motifBlocageDepot([NON_EVALUEE])).toBeNull()
  })

  it('valeurExigee assemble du TEXTE, sans arithmétique', () => {
    expect(valeurExigee(RATIO)).toBe('0,75 – 1')
    expect(valeurExigee(PLAFOND)).toBe('≤ 60 kWc/onduleur')
    expect(valeurExigee({ type: 'plancher', valeur: '3', unite: 'ans' })).toBe('≥ 3 ans')
    expect(valeurExigee(NON_EVALUEE)).toBe('Exigée')
    expect(valeurExigee({})).toBe('—')
  })

  it('estIntervalle / payloadClause : le corps envoyé ne retouche aucun nombre', () => {
    expect(estIntervalle('intervalle')).toBe(true)
    expect(estIntervalle('plafond')).toBe(false)
    expect(payloadClause({
      libelle: ' Ratio ', type: 'intervalle', valeur: '0,75', valeurMax: '1',
      unite: '', sourcePiece: ' CPS ', sourcePage: '', bloquant: true,
    }, 12)).toEqual({
      affaire: 12, libelle: 'Ratio', type: 'intervalle', bloquant: true,
      source_piece: 'CPS', source_page: null, unite: null,
      valeur_min: '0,75', valeur_max: '1',
    })
  })
})
