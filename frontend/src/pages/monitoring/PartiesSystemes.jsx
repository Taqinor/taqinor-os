import { DataTable } from '../../ui'
import { ModuleDashboard } from '../../ui/module'
import { BarArrondie, ChartEmpty } from '../../ui/charts'

/* Éléments PARTAGÉS des écrans de supervision par système (Parc, CO₂) : tableau
   de bord à un graphique en barres pleine largeur, puis tableau des systèmes.
   Un seul endroit — jamais recopiés écran par écran. */

/** KPI + graphique en barres « par système » (rien tant que chargement/erreur). */
export function TableauDeBordSystemes({
  stats, loading, error, titre, chartData, nom, tone, tooltipFormat,
}) {
  return (
    <ModuleDashboard
      stats={stats}
      loading={loading}
      error={error}
      charts={!loading && !error ? [{
        title: titre,
        span: 'full',
        node: chartData.length > 0
          ? <BarArrondie data={chartData} height={220} {...(tone ? { tone } : {})} name={nom} tooltipFormat={tooltipFormat} />
          : <ChartEmpty />,
      }] : []}
    />
  )
}

/** Tableau paginé des systèmes supervisés. */
export function TableSystemes({ systems, columns, label }) {
  return (
    <div className="mt-6">
      <DataTable
        data={systems}
        columns={columns}
        getRowId={(row) => row.installation}
        searchable={false}
        pageSize={25}
        aria-label={label}
      />
    </div>
  )
}
