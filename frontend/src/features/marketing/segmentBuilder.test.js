import { describe, it, expect } from 'vitest'
import { emptyRuleForm, ruleFormFromRegles, buildRegles, reglesKey } from './segmentBuilder'

describe('emptyRuleForm / ruleFormFromRegles', () => {
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
