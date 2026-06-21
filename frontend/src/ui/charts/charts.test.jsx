import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import { ChartTooltip } from './ChartTooltip.jsx'
import { ChartEmpty } from './ChartEmpty.jsx'
import { ChartFrame } from './ChartFrame.jsx'

/* K147 / N161 — Tests des primitives graphiques rendant du DOM réel.
   (Les graphes recharts eux-mêmes n'ont pas de taille en jsdom ; on teste donc
   l'infobulle, l'état vide et le cadre accessible.) */

describe('ChartTooltip (K147)', () => {
  const payload = [{ name: 'CA HT', value: 1000, color: 'var(--info)' }]

  it('ne rend rien quand inactif', () => {
    const { container } = render(<ChartTooltip active={false} payload={payload} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('rend le label et la valeur formatée', () => {
    render(
      <ChartTooltip
        active
        label="Jan 2026"
        payload={payload}
        format={(v) => `${v} MAD`}
      />,
    )
    expect(screen.getByText('Jan 2026')).toBeInTheDocument()
    expect(screen.getByText('CA HT')).toBeInTheDocument()
    expect(screen.getByText('1000 MAD')).toBeInTheDocument()
  })
})

describe('ChartEmpty (K147)', () => {
  it('affiche un état vide en contexte', () => {
    render(<ChartEmpty title="Aucune vente" description="Rien à afficher." />)
    expect(screen.getByText('Aucune vente')).toBeInTheDocument()
    expect(screen.getByText('Rien à afficher.')).toBeInTheDocument()
  })
})

describe('ChartFrame (N161 — accessibilité)', () => {
  const columns = [
    { key: 'mois', header: 'Mois' },
    { key: 'ca', header: 'CA', align: 'right', format: (v) => `${v} MAD` },
  ]
  const rows = [
    { mois: 'Jan', ca: 1000 },
    { mois: 'Fév', ca: 2000 },
  ]

  it('expose role="img" + aria-label (résumé)', () => {
    render(
      <ChartFrame label="Évolution du CA" columns={columns} rows={rows}>
        <div data-testid="graph">graph</div>
      </ChartFrame>,
    )
    expect(screen.getByRole('img', { name: 'Évolution du CA' })).toBeInTheDocument()
  })

  it('rend la table de repli (présente dès le départ pour les lecteurs d\'écran)', () => {
    render(
      <ChartFrame label="Évolution du CA" columns={columns} rows={rows}>
        <div>graph</div>
      </ChartFrame>,
    )
    // Données chiffrées accessibles via la table même repliée.
    expect(screen.getByText('1000 MAD')).toBeInTheDocument()
    expect(screen.getByText('2000 MAD')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Mois' })).toBeInTheDocument()
  })

  it('le bouton « Voir le tableau » bascule l\'affichage', async () => {
    render(
      <ChartFrame label="CA" columns={columns} rows={rows}>
        <div>graph</div>
      </ChartFrame>,
    )
    const btn = screen.getByRole('button', { name: /Voir le tableau/ })
    expect(btn).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(btn)
    expect(screen.getByRole('button', { name: /Masquer le tableau/ }))
      .toHaveAttribute('aria-expanded', 'true')
  })

  it("n'a aucune violation d'accessibilité détectable", async () => {
    const { container } = render(
      <ChartFrame label="Évolution du CA" columns={columns} rows={rows}>
        <svg width="10" height="10" />
      </ChartFrame>,
    )
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })

  it('sans données tabulaires : pas de bouton ni de table', () => {
    render(
      <ChartFrame label="CA">
        <div>graph</div>
      </ChartFrame>,
    )
    expect(screen.queryByRole('button', { name: /tableau/ })).not.toBeInTheDocument()
  })
})
