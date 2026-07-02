// QC1 — helpers d'autocomplete entreprise : mapping des hits en options,
// validation NON bloquante des identifiants marocains, deep-links « Vérifier ».
import { describe, it, expect, vi } from 'vitest'
import {
  searchCompanies, hitToOption, hitsToOptions,
  iceWarning, ifWarning, rcWarning, verifierIceUrl, verifierOmpicUrl,
} from './companyLookup'

const HIT_CLIENT = {
  source: 'client', id: 3, nom: 'Zellige SARL', ice: '001234567000089',
  if_fiscal: '12345678', rc: 'RC-99', adresse: 'Casa', telephone: '+2126', email: 'a@z.ma',
}
const HIT_LEAD = { source: 'lead', id: 7, nom: 'Zellige Prospect', ice: '' }

describe('searchCompanies (provider seam)', () => {
  it('délègue au searcher fourni et déballe {data:{results}}', async () => {
    const searcher = vi.fn().mockResolvedValue({ data: { results: [HIT_CLIENT] } })
    const out = await searchCompanies('zellige', { searcher })
    expect(searcher).toHaveBeenCalledWith('zellige')
    expect(out).toEqual([HIT_CLIENT])
  })

  it('query vide → [] sans appel réseau', async () => {
    const searcher = vi.fn()
    expect(await searchCompanies('  ', { searcher })).toEqual([])
    expect(searcher).not.toHaveBeenCalled()
  })
})

describe('hitToOption / hitsToOptions', () => {
  it('encode source+id dans value (pas de collision client/lead)', () => {
    expect(hitToOption(HIT_CLIENT).value).toBe('client:3')
    expect(hitToOption(HIT_LEAD).value).toBe('lead:7')
  })

  it('description porte l\'ICE + la source lisible', () => {
    expect(hitToOption(HIT_CLIENT).description).toBe('ICE 001234567000089 · Client')
    expect(hitToOption(HIT_LEAD).description).toBe('Lead')
  })

  it('conserve le hit complet pour le remplissage', () => {
    expect(hitToOption(HIT_CLIENT).hit).toBe(HIT_CLIENT)
    expect(hitsToOptions([HIT_CLIENT, HIT_LEAD])).toHaveLength(2)
  })
})

describe('validation NON bloquante (avertissements)', () => {
  it('ICE : 15 chiffres OK, sinon avertit', () => {
    expect(iceWarning('001234567000089')).toBeNull()
    expect(iceWarning('123')).toMatch(/15 chiffres/)
    expect(iceWarning('')).toBeNull() // vide = pas d'avertissement
  })
  it('IF : 6-9 chiffres OK', () => {
    expect(ifWarning('12345678')).toBeNull()
    expect(ifWarning('12')).toMatch(/incomplet/)
    expect(ifWarning('')).toBeNull()
  })
  it('RC : contient au moins un chiffre', () => {
    expect(rcWarning('RC-4521')).toBeNull()
    expect(rcWarning('abc')).toMatch(/incomplet/)
    expect(rcWarning('')).toBeNull()
  })
})

describe('deep-links « Vérifier »', () => {
  it('encode le nom dans l\'URL des registres officiels', () => {
    expect(verifierIceUrl('Zellige SARL')).toContain('ice.gov.ma')
    expect(verifierIceUrl('Zellige SARL')).toContain('Zellige%20SARL')
    expect(verifierOmpicUrl('Zellige SARL')).toContain('directinfo.ma')
  })
})
