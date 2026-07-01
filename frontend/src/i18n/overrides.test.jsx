import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup } from '@testing-library/react'

/* N94 — la couche de surcharges de traduction fusionne PAR-DESSUS les
   catalogues statiques N93. On vérifie :
   - resolveValue : override(locale) → statique(locale) → statique(FR) → clé ;
   - le provider adopte les surcharges via setOverrides (effet immédiat) ;
   - sans surcharge, le comportement est EXACTEMENT celui du catalogue statique
     (aucune régression) ;
   - un échec du fetch au montage retombe silencieusement sur le statique. */

// Le provider charge les surcharges au montage via ce module — on le mocke pour
// contrôler le scénario (données / échec) sans réseau.
vi.mock('./overridesApi', () => ({
  fetchTranslationOverrides: vi.fn(async () => ({})),
}))

import { fetchTranslationOverrides } from './overridesApi'
import { I18nProvider, useI18n, resolveValue } from './index'

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute('dir')
  document.documentElement.removeAttribute('lang')
  fetchTranslationOverrides.mockReset()
  fetchTranslationOverrides.mockResolvedValue({})
})
afterEach(() => cleanup())

describe('N94 resolveValue — chaîne de repli', () => {
  it('préfère une surcharge à la valeur statique', () => {
    const ov = { fr: { 'common.save': 'Sauvegarder' } }
    expect(resolveValue('common.save', 'fr', ov)).toBe('Sauvegarder')
  })

  it('retombe sur le catalogue de la locale sans surcharge', () => {
    // 'common.save' existe en EN = 'Save'.
    expect(resolveValue('common.save', 'en', {})).toBe('Save')
    expect(resolveValue('common.save', 'en', null)).toBe('Save')
  })

  it('retombe sur le FR quand la locale n’a pas la clé', () => {
    // Clé présente en FR mais supposée absente d’une locale → repli FR.
    const v = resolveValue('common.save', 'fr', {})
    expect(v).toBe('Enregistrer')
  })

  it('retombe sur la clé quand elle n’existe nulle part', () => {
    expect(resolveValue('nope.nope', 'fr', {})).toBe('nope.nope')
    expect(resolveValue('nope.nope', 'en', { fr: {} })).toBe('nope.nope')
  })

  it('n’applique la surcharge qu’à la locale visée', () => {
    const ov = { en: { 'common.save': 'SAVE!' } }
    // EN surchargé, FR intact (statique).
    expect(resolveValue('common.save', 'en', ov)).toBe('SAVE!')
    expect(resolveValue('common.save', 'fr', ov)).toBe('Enregistrer')
  })
})

function Probe() {
  const { t, setOverrides } = useI18n()
  return (
    <div>
      <span data-testid="save">{t('common.save')}</span>
      <button data-testid="apply" onClick={() =>
        setOverrides({ fr: { 'common.save': 'Sauver !' } })}>apply</button>
      <button data-testid="clear" onClick={() => setOverrides({})}>clear</button>
    </div>
  )
}

describe('N94 provider — fusion des surcharges', () => {
  it('sans surcharge : t() = catalogue statique (aucune régression)', async () => {
    await act(async () => {
      render(<I18nProvider><Probe /></I18nProvider>)
    })
    expect(screen.getByTestId('save').textContent).toBe('Enregistrer')
  })

  it('adopte une surcharge via setOverrides, puis revient au statique', async () => {
    await act(async () => {
      render(<I18nProvider><Probe /></I18nProvider>)
    })
    expect(screen.getByTestId('save').textContent).toBe('Enregistrer')
    act(() => { screen.getByTestId('apply').click() })
    expect(screen.getByTestId('save').textContent).toBe('Sauver !')
    act(() => { screen.getByTestId('clear').click() })
    expect(screen.getByTestId('save').textContent).toBe('Enregistrer')
  })

  it('charge les surcharges au montage (fetch réussi)', async () => {
    fetchTranslationOverrides.mockResolvedValue({ fr: { 'common.save': 'Garder' } })
    await act(async () => {
      render(<I18nProvider><Probe /></I18nProvider>)
    })
    expect(screen.getByTestId('save').textContent).toBe('Garder')
  })

  it('un échec de fetch retombe silencieusement sur le statique', async () => {
    fetchTranslationOverrides.mockRejectedValue(new Error('offline'))
    await act(async () => {
      render(<I18nProvider><Probe /></I18nProvider>)
    })
    expect(screen.getByTestId('save').textContent).toBe('Enregistrer')
  })
})
