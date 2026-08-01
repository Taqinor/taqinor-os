import { Link } from 'react-router-dom'
import {
  Wrench, Boxes, ClipboardList, ShieldCheck, BookOpen, FileBarChart2,
  MessageCircleQuestion, CalendarClock, Bell, CheckCircle2,
} from 'lucide-react'
import { ModuleHero, ModuleDashboard } from '../../ui/module'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, Button } from '../../ui'
import useResource from '../../hooks/useResource'
import savApi from '../../api/savApi'

/* ============================================================================
   ODY19 — Cockpit Après-vente (`/sav/cockpit`).
   ----------------------------------------------------------------------------
   Porte d'entrée de l'app SAV : identité (ModuleHero VX15) + actions rapides
   + bandeau KPI. `/sav` reste la liste des tickets (TicketsPage) — de trop
   nombreux points d'entrée existants (Dashboard « Mes activités », Rapports,
   entityRoutes ROUTE.ticket, OwnerChain, RelationCounters, CalendarPage…)
   pointent déjà vers `/sav` pour ouvrir un ticket précis ; on n'y touche PAS.
   Le cockpit est donc une route additive, posée en tête de la nav SAV.

   KPI : réutilise TEL QUEL `savApi.getSavFileAction()` (`GET
   /sav/tickets/file-action/`, ZSAV6) — le même agrégat déjà éprouvé par
   `SavActionBoardPage` — aucune agrégation dupliquée, aucun nouvel endpoint.
   ========================================================================== */

const BUCKET_META = [
  { key: 'a_repondre', label: 'À répondre', icon: MessageCircleQuestion },
  { key: 'a_planifier', label: 'À planifier', icon: CalendarClock },
  { key: 'a_relancer', label: 'À relancer', icon: Bell },
  { key: 'a_cloturer', label: 'À clôturer', icon: CheckCircle2 },
]

// N'inclut PAS /sav ni /equipements : déjà les 2 actions rapides du hero
// ci-dessous — pas de doublon de destination.
const QUICK_LINKS = [
  {
    to: '/sav/contrats',
    label: 'Contrats maintenance',
    hint: 'Contrats actifs et échéances de visite',
    icon: ClipboardList,
  },
  {
    to: '/sav/warranty-claims',
    label: 'Garanties fournisseur (RMA)',
    hint: 'Réclamations garantie en cours',
    icon: ShieldCheck,
  },
  {
    to: '/sav/kb',
    label: 'Base de connaissances SAV',
    hint: 'Procédures et articles de dépannage',
    icon: BookOpen,
  },
  {
    to: '/sav/sla-rapport',
    label: 'Rapport SLA SAV',
    hint: 'Conformité des délais contractuels',
    icon: FileBarChart2,
  },
]

export default function SavCockpitPage() {
  const { data, loading, error } = useResource(
    () => savApi.getSavFileAction(),
    undefined,
    {
      initialData: null,
      select: (res) => res.data,
      errorMessage: 'Impossible de charger le tableau de bord SAV.',
    },
  )

  const buckets = data?.buckets ?? {}
  const totalCount = BUCKET_META.reduce(
    (sum, b) => sum + (buckets[b.key]?.count ?? 0), 0,
  )

  const stats = BUCKET_META.map((b) => ({
    label: b.label,
    value: buckets[b.key]?.count ?? 0,
    icon: b.icon,
    to: '/sav/action-requise',
  }))

  return (
    <div className="page flex flex-col gap-6">
      <ModuleHero
        title="Après-vente"
        subtitle={
          loading
            ? 'Tickets SAV, équipements et contrats de maintenance'
            : `${totalCount} ticket${totalCount > 1 ? 's' : ''} ouvert${totalCount > 1 ? 's' : ''} à traiter`
        }
        actions={(
          <>
            <Button asChild size="sm">
              <Link to="/sav"><Wrench size={16} aria-hidden="true" /> Tickets SAV</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to="/equipements"><Boxes size={16} aria-hidden="true" /> Équipements</Link>
            </Button>
          </>
        )}
      />

      <ModuleDashboard stats={stats} loading={loading} error={error} />

      <Card>
        <CardHeader>
          <CardTitle>Accès rapide</CardTitle>
          <CardDescription>Les écrans les plus utilisés de l’Après-vente.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2">
            {QUICK_LINKS.map((l) => {
              const Icon = l.icon
              return (
                <Link
                  key={l.to}
                  to={l.to}
                  className="flex items-start gap-3 rounded-lg border border-border p-3 transition-shadow hover:ring-2 hover:ring-ring/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Icon className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="flex flex-col">
                    <span className="font-medium">{l.label}</span>
                    <span className="text-sm text-muted-foreground">{l.hint}</span>
                  </span>
                </Link>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
