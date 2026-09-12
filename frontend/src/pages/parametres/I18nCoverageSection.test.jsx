import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* NTI18N28 — smoke de l'écran de couverture i18n : il se monte, lit le
   rapport JSON déjà committé (`../../i18n/coverage-report.json`, produit par
   NTI18N1) et affiche le pourcentage global + un bouton d'export CSV, sans
   aucun appel réseau (écran 100% lecture seule côté client). */

import I18nCoverageSection from './I18nCoverageSection'
import coverageReport from '../../i18n/coverage-report.json'

afterEach(() => cleanup())

describe('NTI18N28 I18nCoverageSection', () => {
  it('affiche le pourcentage de couverture global du rapport', () => {
    render(<I18nCoverageSection />)
    expect(screen.getByText(`${coverageReport.coverage_pct}%`)).toBeInTheDocument()
  })

  it('propose un export CSV', () => {
    render(<I18nCoverageSection />)
    expect(screen.getByRole('button', { name: /exporter en csv/i })).toBeInTheDocument()
  })

  it('liste au moins un domaine du rapport dans le tableau', () => {
    render(<I18nCoverageSection />)
    const [firstDomain] = Object.keys(coverageReport.domains || {}).sort()
    if (firstDomain) {
      expect(screen.getByText(firstDomain)).toBeInTheDocument()
    }
  })
})
