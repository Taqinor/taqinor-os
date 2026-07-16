import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { emptyRuleForm, ruleFormFromRegles, buildRegles, reglesKey } from './segmentBuilder'

// ── Vitest ne ramasse que `*.test.jsx` (voir vitest.config.js) — la logique
// pure de `segmentBuilder.js` est donc testée ICI plutôt que dans un fichier
// `.test.js` séparé (qui ne serait exécuté par aucun des deux runners).
describe('emptyRuleForm / ruleFormFromRegles (logique pure)', () => {
  it('emptyRuleForm renvoie tous les champs vides', () => {
    const f = emptyRuleForm()
    expect(f.ville).toBe('')
    expect(f.score_gte).toBe('')
    expect(f.activite).toBe('')
  })

  it('ruleFormFromRegles reprend les bornes score/facture_energie séparément', () => {
    const form = ruleFormFromRegles({
      ville: 'Casablanca', score: { gte: 50, lte: 90 },
      facture_energie: { gte: 800 }, activite: 'a_ouvert',
    })
    expect(form.ville).toBe('Casablanca')
    expect(form.score_gte).toBe(50)
    expect(form.score_lte).toBe(90)
    expect(form.facture_gte).toBe(800)
    expect(form.facture_lte).toBe('')
    expect(form.activite).toBe('a_ouvert')
  })

  it('ruleFormFromRegles tolère un regles vide/null', () => {
    expect(ruleFormFromRegles(null).ville).toBe('')
    expect(ruleFormFromRegles(undefined).canal).toBe('')
  })
})

describe('buildRegles — omet toute clé vide (jamais de règle fantôme)', () => {
  it('un formulaire vide produit un objet vide', () => {
    expect(buildRegles(emptyRuleForm())).toEqual({})
  })

  it('recompose score/facture_energie en {gte, lte}', () => {
    const form = { ...emptyRuleForm(), score_gte: '10', score_lte: '80' }
    expect(buildRegles(form)).toEqual({ score: { gte: 10, lte: 80 } })
  })

  it('une seule borne renseignée ne pose que cette clé', () => {
    const form = { ...emptyRuleForm(), facture_gte: '500' }
    expect(buildRegles(form)).toEqual({ facture_energie: { gte: 500 } })
  })

  it('combine tous les champs whitelistés + activité + événement', () => {
    const form = {
      ...emptyRuleForm(), ville: 'Agadir', type_installation: 'agricole',
      tags: 'vip', canal: 'reference', activite: 'jamais_ouvert',
      evenement_present: '12',
    }
    expect(buildRegles(form)).toEqual({
      ville: 'Agadir', type_installation: 'agricole', tags: 'vip',
      canal: 'reference', activite: 'jamais_ouvert', evenement_present: 12,
    })
  })
})

describe('reglesKey — stable pour détecter un vrai changement', () => {
  it('deux formulaires équivalents donnent la même clé', () => {
    const a = { ...emptyRuleForm(), ville: 'Rabat' }
    const b = { ...emptyRuleForm(), ville: 'Rabat' }
    expect(reglesKey(a)).toBe(reglesKey(b))
  })

  it('un changement de règle change la clé', () => {
    const a = { ...emptyRuleForm(), ville: 'Rabat' }
    const b = { ...emptyRuleForm(), ville: 'Fès' }
    expect(reglesKey(a)).not.toBe(reglesKey(b))
  })
})

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
  previsualiser: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    segments: {
      create: mocks.create, update: mocks.update, previsualiser: mocks.previsualiser,
    },
  },
}))

import SegmentBuilder from './SegmentBuilder'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.update.mockResolvedValue({ data: {} })
  mocks.previsualiser.mockResolvedValue({ data: { count: 0, echantillon: [] } })
})

describe('SegmentBuilder (NTMKT4)', () => {
  it("sans segment créé, la prévisualisation n'apparaît pas encore", () => {
    render(<SegmentBuilder initial={null} onSaved={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByTestId('segment-preview-compte')).toBeNull()
    expect(screen.getByTestId('segment-creer')).toBeInTheDocument()
  })

  it('« Créer » pose le nom, crée le brouillon puis prévisualise', async () => {
    mocks.create.mockResolvedValue({ data: { id: 5 } })
    mocks.previsualiser.mockResolvedValue({ data: { count: 3, echantillon: [1, 2, 3] } })
    render(<SegmentBuilder initial={null} onSaved={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByTestId('segment-nom'), { target: { value: 'Leads froids' } })
    fireEvent.click(screen.getByTestId('segment-creer'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      { nom: 'Leads froids', regles: {} }))
    expect(await screen.findByTestId('segment-preview-compte'))
      .toHaveTextContent('3 lead(s)')
  })

  it("ajouter une règle sur un segment existant re-persiste puis re-prévisualise", async () => {
    mocks.update.mockResolvedValue({ data: {} })
    mocks.previsualiser.mockResolvedValue({ data: { count: 7, echantillon: [] } })
    render(<SegmentBuilder
      initial={{ id: 9, nom: 'Segment X', regles: {} }}
      onSaved={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByTestId('segment-ville'), { target: { value: 'Marrakech' } })
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(
      9, { regles: { ville: 'Marrakech' } }))
    await waitFor(() => expect(mocks.previsualiser).toHaveBeenCalledWith(9))
    expect(await screen.findByTestId('segment-preview-compte'))
      .toHaveTextContent('7 lead(s)')
  })

  it('un échec réseau affiche une erreur plutôt que de rester bloqué', async () => {
    mocks.update.mockRejectedValue(new Error('500'))
    render(<SegmentBuilder
      initial={{ id: 9, nom: 'Segment X', regles: {} }}
      onSaved={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByTestId('segment-ville'), { target: { value: 'Fès' } })
    await waitFor(() => expect(screen.getByText(/impossible/i)).toBeInTheDocument())
  })
})
