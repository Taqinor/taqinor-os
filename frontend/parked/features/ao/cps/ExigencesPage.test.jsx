import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* AOF181 — l'analyse du cahier des charges devient un écran.

   ── RÉPARATION 03/08/2026 : ces tests ÉPINGLAIENT un contrat inventé ───────
   Les fixtures étaient bâties sur `type: 'intervalle' | 'plafond' | 'montant'
   | 'duree' | 'texte'` et sur `valeur` / `valeur_min` / `valeur_max` — un
   vocabulaire et des champs qu'`ExigenceCPSSerializer` n'a JAMAIS servis. Le
   code de l'écran lisait les mêmes noms fantômes : test et code étaient donc
   d'accord entre eux et faux tous les deux, ce qui est exactement pourquoi la
   panne (aucune valeur chiffrée affichée, aucun préfixe « ≤ ») a survécu à la
   relecture. Les fixtures ci-dessous ne portent plus QUE des clés réellement
   servies, listées dans `CHAMPS_SERIALISEUR`.

   Quatre garanties prouvées ici :
     1. le jeu de clauses FRDISI se saisit INTÉGRALEMENT, avec sa source (pièce
        du DCE + page) et son caractère bloquant, sans qu'aucun nombre tapé ne
        soit normalisé ;
     2. `payloadClause` n'émet AUCUNE clé absente du sérialiseur — la garde qui
        manquait, et sans laquelle cinq clés inconnues sont parties en silence ;
     3. sur des données RÉELLES (clés du sérialiseur seules), l'écran affiche
        les valeurs chiffrées et « Non évalué », et ne bloque pas le dépôt ;
     4. les verdicts restent des fonctions PURES : aucun chiffre de conformité
        n'est calculé côté front. */

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

import ExigencesPage from './ExigencesPage'
import { payloadClause, estIntervalle, estTexte, TYPES_CLAUSE } from './ExigencesPage.utils'
import {
  statutConformite, severiteAffichee, exigencesBloquantes, motifBlocageDepot, valeurExigee,
} from './ConformiteTable.utils'

/* La liste EXACTE des champs déclarés par `ExigenceCPSSerializer`
   (`backend/django_core/apps/ao/serializers.py`). Toute clé hors de cette
   liste est un champ fantôme : le serveur ne la lit pas en écriture (DRF
   l'ignore en silence) et ne la sert pas en lecture. */
const CHAMPS_SERIALISEUR = [
  'id', 'appel_offre', 'code', 'libelle', 'type_exigence', 'type_exigence_display',
  'valeur_num', 'valeur_max_num', 'est_intervalle', 'unite', 'valeur_texte',
  'source_piece', 'source_page', 'piece_consultation', 'a_reverifier', 'bloquant',
  'commentaire',
]

/* Le jeu de clauses FRDISI, aux noms de champs RÉELS. `est_intervalle` est
   DÉRIVÉ côté serveur (`valeur_max_num is not None`) : il est servi en
   lecture, jamais envoyé. */
const RATIO = {
  id: 1, appel_offre: 7, code: 'RATIO_DC_AC', libelle: 'Ratio DC/AC admissible',
  type_exigence: 'ratio_dc_ac', type_exigence_display: 'Ratio DC/AC (min–max)',
  valeur_num: '0,75', valeur_max_num: '1', est_intervalle: true, unite: '',
  bloquant: true, source_piece: 'CPS — article 12', source_page: 34,
}
const PLAFOND = {
  id: 2, appel_offre: 7, code: 'ONDULEUR_KWC_MAX',
  libelle: 'Puissance maximale par onduleur',
  type_exigence: 'puissance_onduleur_max',
  type_exigence_display: "Puissance unitaire max d'onduleur",
  valeur_num: '60', est_intervalle: false, unite: 'kWc/onduleur', bloquant: true,
  source_piece: 'CPS — article 12', source_page: 35,
}
const CAUTION = {
  id: 3, appel_offre: 7, code: 'CAUTION_PROVISOIRE', libelle: 'Caution provisoire',
  type_exigence: 'caution_provisoire',
  type_exigence_display: 'Caution provisoire (montant absolu)',
  valeur_num: '40000', est_intervalle: false, unite: 'MAD', bloquant: true,
  source_piece: 'Règlement de consultation', source_page: 8,
}
const VALIDITE = {
  id: 4, appel_offre: 7, code: 'VALIDITE_OFFRE', libelle: 'Validité des offres',
  type_exigence: 'validite_offre', type_exigence_display: "Validité de l'offre",
  valeur_num: '75', est_intervalle: false, unite: 'jours', bloquant: false,
  source_piece: 'Règlement de consultation', source_page: 9, a_reverifier: true,
}
// Clause non chiffrable : sa valeur vit dans `valeur_texte`.
const TEXTUELLE = {
  id: 5, appel_offre: 7, code: 'GARANTIE_DECENNALE', libelle: 'Garantie décennale',
  type_exigence: 'piece_administrative',
  type_exigence_display: 'Pièce administrative exigée',
  valeur_texte: 'Exigée', est_intervalle: false, bloquant: true,
  source_piece: 'CPS — article 30',
}

/* Le verdict de conformité n'est PAS servi à ce jour (cf. la note sur
   `statutConformite`) : les tests de verdict ci-dessous SIMULENT l'annotation
   qu'AOF99/AOF146 produiront, pour prouver que la logique de porte est juste
   le jour où elle arrivera. Aucun test de RENDU ne s'en sert : les tests
   d'écran n'utilisent que des données réellement servies. */
const avecVerdict = (clause, conformite) => ({ ...clause, conformite })

const liste = (items) => ({ data: { results: items } })

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue(liste([RATIO, PLAFOND, CAUTION, VALIDITE]))
  mocks.create.mockResolvedValue({ data: { id: 99 } })
  mocks.update.mockResolvedValue({ data: {} })
})

describe('ExigencesPage (AOF181)', () => {
  it('affiche les valeurs chiffrées et la source DCE à partir des champs RÉELS', async () => {
    render(<ExigencesPage />)
    expect(await screen.findByText('Ratio DC/AC admissible')).toBeInTheDocument()
    // `valeur_num` + `valeur_max_num` → intervalle, virgule décimale intacte.
    expect(screen.getByText('0,75 – 1')).toBeInTheDocument()
    // Préfixe « ≤ » : la direction est portée par le modèle pour ce type seul.
    expect(screen.getByText('≤ 60 kWc/onduleur')).toBeInTheDocument()
    // Aucune direction dans le modèle pour `validite_offre` → aucun préfixe.
    expect(screen.getByText('75 jours')).toBeInTheDocument()
    expect(screen.getByText('40000 MAD')).toBeInTheDocument()
    expect(screen.getAllByText(/CPS — article 12, p\. 3[45]/)).toHaveLength(2)
    expect(document.querySelectorAll('[data-ao-controle]')).toHaveLength(4)
  })

  it('l’écran filtre par `appel_offre` — le nom que le serveur honore', async () => {
    render(<ExigencesPage />)
    await screen.findByText('Ratio DC/AC admissible')
    expect(mocks.list).toHaveBeenCalledWith({ appel_offre: '7' })
  })

  it('sur des données réelles, tout est « Non évalué » et le dépôt n’est pas bloqué', async () => {
    // Le serveur ne sert AUCUN verdict de conformité aujourd'hui : l'écran doit
    // le dire honnêtement, et surtout ne rien conclure — ni « conforme », ni
    // « bloquant ». C'est le serveur qui reste la porte (AOF146).
    render(<ExigencesPage />)
    expect(await screen.findByRole('button', { name: 'Marquer « prêt à déposer »' })).toBeEnabled()
    expect(screen.getAllByText('Non évalué')).toHaveLength(4)
    expect(screen.queryByText('OK')).not.toBeInTheDocument()
    expect(screen.queryByText('Bloquant')).not.toBeInTheDocument()
  })

  it('aucune colonne ne peut afficher un tiret perpétuel', async () => {
    // Les colonnes « Constaté » et « Origine du constat » lisaient une
    // annotation jamais servie : elles affichaient « — » sur chaque ligne.
    render(<ExigencesPage />)
    await screen.findByText('Ratio DC/AC admissible')
    expect(screen.queryByRole('columnheader', { name: 'Constaté' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Origine du constat' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('columnheader').map((c) => c.textContent))
      .toEqual(['Clause', 'Exigé', 'Source (DCE)', 'Conformité'])
  })

  it('signale les exigences à revérifier après erratum', async () => {
    render(<ExigencesPage />)
    expect(await screen.findByText('Exigences à revérifier après erratum')).toBeInTheDocument()
    // `a_reverifier` est le SEUL signal servi : la référence de l'additif
    // (`erratum_ref`) n'existe pas au contrat et n'est plus prétendue.
    expect(screen.getAllByText('Validité des offres').length).toBeGreaterThan(0)
    expect(screen.queryByText(/erratum n°/)).not.toBeInTheDocument()
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

    // 1. Ratio DC/AC 0,75-1 — le seul intervalle, virgule décimale intacte.
    await saisir({
      type: 'ratio_dc_ac', libelle: 'Ratio DC/AC admissible',
      valeur: '0,75', valeurMax: '1', source: 'CPS — article 12', page: '34',
    }, { intervalle: true })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1))
    expect(mocks.create.mock.calls[0][0]).toEqual({
      appel_offre: '7', code: 'Ratio DC/AC admissible', libelle: 'Ratio DC/AC admissible',
      type_exigence: 'ratio_dc_ac', bloquant: true,
      source_piece: 'CPS — article 12', source_page: '34', unite: '',
      valeur_num: '0,75', valeur_max_num: '1',
    })

    // 2. Plafond 60 kWc par onduleur.
    await saisir({
      type: 'puissance_onduleur_max', libelle: 'Puissance maximale par onduleur',
      valeur: '60', unite: 'kWc/onduleur', source: 'CPS — article 12', page: '35',
    })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(2))
    expect(mocks.create.mock.calls[1][0]).toMatchObject({
      type_exigence: 'puissance_onduleur_max', valeur_num: '60', unite: 'kWc/onduleur',
      bloquant: true,
    })

    // 3. Caution provisoire en MONTANT ABSOLU (jamais un pourcentage déduit).
    await saisir({
      type: 'caution_provisoire', libelle: 'Caution provisoire',
      valeur: '40000', unite: 'MAD', source: 'Règlement de consultation', page: '8',
    })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(3))
    expect(mocks.create.mock.calls[2][0]).toMatchObject({
      type_exigence: 'caution_provisoire', valeur_num: '40000', unite: 'MAD',
    })

    // 4. Validité des offres 75 jours, clause NON bloquante.
    await saisir({
      type: 'validite_offre', libelle: 'Validité des offres',
      valeur: '75', unite: 'jours', source: 'Règlement de consultation', page: '9',
    }, { bloquant: false })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(4))
    expect(mocks.create.mock.calls[3][0]).toMatchObject({
      type_exigence: 'validite_offre', valeur_num: '75', unite: 'jours', bloquant: false,
    })

    // 5. Clause non chiffrable : la valeur part en `valeur_texte`.
    await saisir({
      type: 'piece_administrative', libelle: 'Attestation fiscale',
      valeur: 'Exigée, moins d’un an', source: 'Règlement de consultation', page: '4',
    })
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(5))
    expect(mocks.create.mock.calls[4][0]).toMatchObject({
      type_exigence: 'piece_administrative', valeur_texte: 'Exigée, moins d’un an',
    })
    expect(mocks.create.mock.calls[4][0]).not.toHaveProperty('valeur_num')
  })

  it('un refus serveur s’affiche tel quel', async () => {
    mocks.create.mockRejectedValue({ response: { data: { detail: 'Code déjà utilisé.' } } })
    render(<ExigencesPage />)
    await screen.findByText('Ratio DC/AC admissible')
    fireEvent.change(screen.getByLabelText(/Intitulé de la clause/), { target: { value: 'X' } })
    fireEvent.change(screen.getByLabelText(/Pièce du DCE/), { target: { value: 'CPS' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter la clause' }))
    await waitFor(() => expect(toastMocks.error).toHaveBeenCalledWith('Code déjà utilisé.'))
  })

  it('l’aperçu du CPS est branché sur le composant partagé (AOF175), pas réécrit', async () => {
    render(<ExigencesPage pieceCps={{ id: 3, libelle: 'CPS — lot 2' }} />)
    expect(await screen.findByTestId('apercu-cps')).toHaveTextContent('CPS — lot 2')
  })
})

describe('payloadClause — garde de contrat (la garde qui manquait)', () => {
  const formulaire = (type) => ({
    libelle: ' Clause de test ', type, valeur: '0,75', valeurMax: '1',
    unite: ' kWc ', sourcePiece: ' CPS ', sourcePage: ' 12 ', bloquant: true,
  })

  it('n’émet AUCUNE clé absente du sérialiseur, pour CHAQUE type du modèle', () => {
    for (const { value } of TYPES_CLAUSE) {
      const corps = payloadClause(formulaire(value), 12)
      const intrus = Object.keys(corps).filter((k) => !CHAMPS_SERIALISEUR.includes(k))
      expect(intrus, `type « ${value} » : clés inconnues du sérialiseur`).toEqual([])
    }
  })

  it('n’envoie JAMAIS `company` ni `est_intervalle` (dérivé, lecture seule)', () => {
    for (const { value } of TYPES_CLAUSE) {
      const corps = payloadClause(formulaire(value), 12)
      expect(corps).not.toHaveProperty('company')
      expect(corps).not.toHaveProperty('est_intervalle')
    }
  })

  it('n’envoie plus aucune des cinq clés fantômes de l’ancien contrat', () => {
    for (const { value } of TYPES_CLAUSE) {
      const corps = payloadClause(formulaire(value), 12)
      for (const fantome of ['affaire', 'type', 'valeur', 'valeur_min', 'valeur_max']) {
        expect(corps, `type « ${value} »`).not.toHaveProperty(fantome)
      }
    }
  })

  it('porte toujours `appel_offre` — la clé obligatoire qui manquait', () => {
    for (const { value } of TYPES_CLAUSE) {
      expect(payloadClause(formulaire(value), 12).appel_offre).toBe(12)
    }
  })

  it('le corps envoyé ne retouche aucun nombre', () => {
    expect(payloadClause({
      libelle: ' Ratio ', type: 'ratio_dc_ac', valeur: '0,75', valeurMax: '1',
      unite: '', sourcePiece: ' CPS ', sourcePage: '', bloquant: true,
    }, 12)).toEqual({
      appel_offre: 12, code: 'Ratio', libelle: 'Ratio', type_exigence: 'ratio_dc_ac',
      bloquant: true, source_piece: 'CPS', source_page: null, unite: '',
      valeur_num: '0,75', valeur_max_num: '1',
    })
  })

  it('estIntervalle / estTexte suivent les types RÉELS du modèle', () => {
    expect(estIntervalle('ratio_dc_ac')).toBe(true)
    expect(estIntervalle('puissance_onduleur_max')).toBe(false)
    // Les types inventés ne sont plus reconnus par rien.
    expect(estIntervalle('intervalle')).toBe(false)
    expect(estTexte('autre')).toBe(true)
    expect(estTexte('piece_administrative')).toBe(true)
    expect(estTexte('caution_provisoire')).toBe(false)
  })

  it('les types proposés sont EXACTEMENT ceux de `ExigenceCPS.TypeExigence`', () => {
    expect(TYPES_CLAUSE.map((t) => t.value)).toEqual([
      'ratio_dc_ac', 'puissance_onduleur_max', 'caution_provisoire',
      'caution_definitive_taux', 'validite_offre', 'penalite_retard',
      'piece_administrative', 'reference_normative', 'autre',
    ])
  })
})

describe('ConformiteTable — verdicts purs (AOF181)', () => {
  it('le statut vient du serveur, jamais d’une comparaison locale', () => {
    expect(statutConformite(avecVerdict(PLAFOND, { statut: 'non_conforme' }))).toBe('non_conforme')
    expect(statutConformite({ statut_conformite: 'conforme' })).toBe('conforme')
    // Une clause RÉELLE (clés du sérialiseur seules) n'est jamais évaluée.
    expect(statutConformite(PLAFOND)).toBe('non_evalue')
    expect(statutConformite(TEXTUELLE)).toBe('non_evalue')
    expect(statutConformite({})).toBe('non_evalue')
  })

  it('sévérité affichée : bloquante non satisfaite = bloquant, non bloquante = avertissement', () => {
    expect(severiteAffichee(avecVerdict(RATIO, { statut: 'conforme' }))).toBe('ok')
    expect(severiteAffichee(avecVerdict(PLAFOND, { statut: 'non_conforme' }))).toBe('bloquant')
    expect(severiteAffichee(avecVerdict(VALIDITE, { statut: 'non_conforme' }))).toBe('avertissement')
    expect(severiteAffichee(PLAFOND)).toBeNull()
  })

  it('motifBlocageDepot ne retient que les bloquantes non satisfaites', () => {
    const faute = avecVerdict(PLAFOND, {
      statut: 'non_conforme',
      message: 'Un onduleur du bâtiment C dépasse le plafond : 66 kWc pour 60 admis.',
    })
    expect(exigencesBloquantes([RATIO, faute, VALIDITE])).toEqual([faute])
    expect(motifBlocageDepot([RATIO, faute])).toBe(faute.conformite.message)
    expect(motifBlocageDepot([RATIO, CAUTION, VALIDITE])).toBeNull()
    // Une clause bloquante NON évaluée ne bloque pas : le verdict appartient au
    // serveur, dans les deux sens.
    expect(motifBlocageDepot([TEXTUELLE])).toBeNull()
  })

  it('valeurExigee lit les champs RÉELS et assemble du TEXTE, sans arithmétique', () => {
    expect(valeurExigee(RATIO)).toBe('0,75 – 1')
    expect(valeurExigee(PLAFOND)).toBe('≤ 60 kWc/onduleur')
    expect(valeurExigee(CAUTION)).toBe('40000 MAD')
    expect(valeurExigee(TEXTUELLE)).toBe('Exigée')
    expect(valeurExigee({})).toBe('—')
    expect(valeurExigee(null)).toBe('—')
  })

  it('aucun préfixe inventé : seul le type dont le modèle porte la direction en reçoit un', () => {
    // `validite_offre` : le modèle n'écrit AUCUNE direction — pas de « ≥ ».
    expect(valeurExigee(VALIDITE)).toBe('75 jours')
    // Les types inventés d'hier ne produisent plus rien de spécial.
    expect(valeurExigee({ type_exigence: 'plancher', valeur_num: '3', unite: 'ans' })).toBe('3 ans')
    expect(valeurExigee({ type_exigence: 'plafond', valeur_num: '3' })).toBe('3')
    // Et l'ancien champ `type` ne décide plus de rien.
    expect(valeurExigee({ type: 'puissance_onduleur_max', valeur_num: '60' })).toBe('60')
  })

  it('une valeur seule sur `valeur_num` s’affiche — c’était le défaut silencieux', () => {
    // Avant réparation : `valeur_num` n'était pas lu, donc « — » perpétuel sur
    // TOUTE clause chiffrée.
    expect(valeurExigee({ type_exigence: 'autre', valeur_num: '0' })).toBe('0')
    expect(valeurExigee({ type_exigence: 'autre', valeur_num: '', unite: 'MAD' })).toBe('—')
  })
})
