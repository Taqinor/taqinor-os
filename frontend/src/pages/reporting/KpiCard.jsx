// ENF28 (ENF19) — tuile KPI partagée des rapports (analytics terrain, SLA SAV,
// quote-to-cash, pilotage chantiers) : icône, libellé, valeur et, en option,
// une ligne d'aide. Un seul exemplaire au lieu de quatre copies.
import { Card, CardContent } from '../../ui'

export default function KpiCard({ icon, label, value, hint, className = 'flex-1 min-w-[160px]' }) {
  return (
    <Card className={className}>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="text-muted-foreground">{icon}</div>
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="text-lg font-semibold">{value}</div>
          {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
        </div>
      </CardContent>
    </Card>
  )
}
