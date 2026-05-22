/**
 * Page Reporting & Analytics.
 * TODO Phase 4 Sem. 7-8 : graphiques recharts, filtres date, export PDF/Excel.
 */
export function Component() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-gray-800 mb-6">Reporting & Analytics</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-gray-700 mb-3">CA par période</h3>
          <p className="text-gray-400 text-sm">📊 TODO Sem. 7 : AreaChart recharts</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-gray-700 mb-3">Top produits vendus</h3>
          <p className="text-gray-400 text-sm">📊 TODO Sem. 7 : BarChart recharts</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-gray-700 mb-3">Taux de conversion Devis → BC</h3>
          <p className="text-gray-400 text-sm">📊 TODO Sem. 7 : FunnelChart</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-gray-700 mb-3">Créances clients</h3>
          <p className="text-gray-400 text-sm">📊 TODO Sem. 7 : tableau + aging report</p>
        </div>
      </div>
    </div>
  )
}
