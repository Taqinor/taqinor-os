// QJR637 — le bloc étude réseau (conso, injection 82-21, raccordement BT/MT,
// bloc MT) était recopié octet pour octet dans PanneauIndustriel.jsx et
// PanneauCommercial.jsx : un correctif d'un côté oubliait l'autre. Il vit
// désormais UNE fois, dans BlocEtudeReseau.jsx, monté par les deux panneaux.
//
// Run : npx vitest run src/pages/ventes/generator/BlocEtudeReseau.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import BlocEtudeReseau from './BlocEtudeReseau'
import PanneauIndustriel from './PanneauIndustriel'
import PanneauCommercial from './PanneauCommercial'

const HERE = dirname(fileURLToPath(import.meta.url))

const propsBloc = (extra = {}) => ({
  consoMensuelle: '12000', setConsoMensuelle: vi.fn(),
  injectionEnabled: false, setInjectionEnabled: vi.fn(),
  tensionRaccordement: 'mt', dispatchSizing: vi.fn(),
  estMt: true, repartitionMt: { pointe: '', pleines: '', creuses: '' },
  setPartMt: vi.fn(), tarifMtApplique: null,
  ...extra,
})

const propsPanneau = (marche, extra = {}) => ({
  marche,
  fHiver: '', setFHiver: vi.fn(), fEte: '', setFEte: vi.fn(),
  syncBillEstimator: vi.fn(), onHiverPaste: vi.fn(), onEtePaste: vi.fn(),
  handleEstimerMois: vi.fn(), errors: {}, monthly: Array(12).fill(''),
  setMonth: vi.fn(), distributeur: 'onee', setDistributeur: vi.fn(),
  realBillMode: 'mad', setRealBillMode: vi.fn(),
  realBillMad: '', setRealBillMad: vi.fn(), realBillKwh: '', setRealBillKwh: vi.fn(),
  onRealBillPaste: vi.fn(), consoAnnuelleReelle: null,
  categorieCommerciale: 'non_precisee', setCategorieCommerciale: vi.fn(),
  commercialAnswers: {}, setCommercialAnswer: vi.fn(),
  ...propsBloc(),
  ...extra,
})

describe('QJR637 — BlocEtudeReseau', () => {
  it('rend gen-conso, gen-tension et gen-mt-block ; chaque input number porte step="any"', () => {
    const { container } = render(<BlocEtudeReseau {...propsBloc()} />)
    expect(container.querySelector('#gen-conso')).not.toBeNull()
    expect(screen.getByTestId('gen-tension')).toBeInTheDocument()
    expect(screen.getByTestId('gen-mt-block')).toBeInTheDocument()
    const nombres = container.querySelectorAll('input[type=number]')
    expect(nombres.length).toBe(4)
    for (const input of nombres) {
      expect(input.getAttribute('step')).toBe('any')
      expect(input.getAttribute('min')).toBe('0')
    }
  })

  it('site BT : aucun bloc MT', () => {
    render(<BlocEtudeReseau {...propsBloc({ estMt: false, tensionRaccordement: 'bt' })} />)
    expect(screen.queryByTestId('gen-mt-block')).toBeNull()
  })

  it.each(['industriel', 'commercial'])('le panneau %s monte le bloc partagé (mêmes ids)', (marche) => {
    const Panneau = marche === 'industriel' ? PanneauIndustriel : PanneauCommercial
    const { container } = render(<Panneau {...propsPanneau(marche)} />)
    expect(container.querySelectorAll('#gen-conso').length).toBe(1)
    expect(screen.getByTestId('gen-tension')).toBeInTheDocument()
    expect(screen.getByTestId('gen-mt-block')).toBeInTheDocument()
  })

  it('garde de source : plus aucune copie du bloc dans les deux panneaux', () => {
    for (const fichier of ['PanneauIndustriel.jsx', 'PanneauCommercial.jsx']) {
      const src = readFileSync(join(HERE, fichier), 'utf8')
      expect(src.includes('id="gen-conso"')).toBe(false)
      expect(src.includes('BlocEtudeReseau')).toBe(true)
    }
  })
})
