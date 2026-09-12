import { describe, it, expect } from 'vitest'
import {
  detecterFormatReleve, extensionDe, normaliserDate, normaliserMontant,
  parserReleveCsv,
} from './bankFormatDetect'

/* NTTRE24 — la détection de format de l'assistant « Nouveau rapprochement ».
   Fonctions PURES (aucun DOM, aucun réseau) : testées isolément. */

describe('extensionDe', () => {
  it('rend l’extension en minuscules, vide si absente', () => {
    expect(extensionDe('releve.CSV')).toBe('csv')
    expect(extensionDe('releve')).toBe('')
    expect(extensionDe('')).toBe('')
  })
})

describe('detecterFormatReleve', () => {
  it('reconnaît camt.053 par son en-tête XML', () => {
    const xml = '<?xml version="1.0"?><Document xmlns="urn:iso:std:iso:20022:'
      + 'tech:xsd:camt.053.001.02"><BkToCstmrStmt/></Document>'
    expect(detecterFormatReleve('quelconque.dat', xml)).toBe('camt053')
  })

  it('reconnaît MT940 par ses tags SWIFT', () => {
    const mt = ':20:REL001\n:25:011780000012345678901234\n:61:2601050105D250,00NTRF'
    expect(detecterFormatReleve('releve.txt', mt)).toBe('mt940')
  })

  it('reconnaît CFONB120 à la largeur fixe de 120 caractères', () => {
    const ligne = 'X'.repeat(120)
    expect(detecterFormatReleve('releve.txt', `${ligne}\n${ligne}`))
      .toBe('cfonb120')
  })

  it('retombe sur l’extension quand l’en-tête n’est pas concluant', () => {
    expect(detecterFormatReleve('releve.csv', 'date;libelle;montant'))
      .toBe('csv')
    expect(detecterFormatReleve('releve.sta', 'contenu opaque')).toBe('mt940')
    expect(detecterFormatReleve('releve.xml', 'contenu opaque')).toBe('camt053')
  })

  it('rend null quand rien n’est concluant (jamais de devinette)', () => {
    expect(detecterFormatReleve('releve.bin', 'contenu opaque')).toBeNull()
  })
})

describe('normaliserMontant / normaliserDate', () => {
  it('accepte les écritures française et anglo-saxonne', () => {
    expect(normaliserMontant('1 234,56')).toBe(1234.56)
    expect(normaliserMontant('1,234.56')).toBe(1234.56)
    expect(normaliserMontant('-250')).toBe(-250)
    expect(normaliserMontant('illisible')).toBeNull()
  })

  it('accepte AAAA-MM-JJ et JJ/MM/AAAA', () => {
    expect(normaliserDate('2026-03-10')).toBe('2026-03-10')
    expect(normaliserDate('10/03/2026')).toBe('2026-03-10')
    expect(normaliserDate('mars 2026')).toBeNull()
  })
})

describe('parserReleveCsv', () => {
  it('lit un CSV à en-tête, quel que soit le séparateur', () => {
    const csv = [
      'date;libelle;montant;reference',
      '10/03/2026;Virement client;1 500,00;VIR-1',
      '12/03/2026;Frais bancaires;-120,50;COM-9',
    ].join('\n')
    const { lignes, ignorees } = parserReleveCsv(csv)
    expect(ignorees).toBe(0)
    expect(lignes).toHaveLength(2)
    expect(lignes[0]).toEqual({
      date_operation: '2026-03-10',
      libelle: 'Virement client',
      montant: 1500,
      reference: 'VIR-1',
    })
    expect(lignes[1].montant).toBe(-120.5)
  })

  it('lit un CSV sans en-tête et ignore les lignes illisibles', () => {
    const csv = [
      '10/03/2026,Virement,900,REF',
      'total,,,',
    ].join('\n')
    const { lignes, ignorees } = parserReleveCsv(csv)
    expect(lignes).toHaveLength(1)
    expect(ignorees).toBe(1)
  })

  it('rend une liste vide sur un contenu vide', () => {
    expect(parserReleveCsv('')).toEqual({ lignes: [], ignorees: 0 })
  })
})
