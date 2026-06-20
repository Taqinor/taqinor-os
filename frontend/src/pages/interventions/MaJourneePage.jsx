// F22 — « Ma journée » : l'écran unique du technicien sur le terrain. Affiche
// les interventions du jour qui lui sont assignées, dans l'ordre, chacune
// s'ouvrant directement sur son flux préparation → capture sur site →
// complétion (les mêmes panneaux F5–F19 que le volet détail). Pensé
// thumb-reachable et 100 % en français. La portée « seulement les miennes » est
// garantie côté serveur par le rôle Technicien (scope_queryset) ; aucun prix
// d'achat ni marge n'est exposé.
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CalendarDays, MapPin, ChevronRight, ClipboardList, Navigation, Camera,
  Tag, ListChecks, Mic, ShieldCheck, Wrench, AlertOctagon,
} from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Card, Spinner, EmptyState, Badge, StatusPill,
  Sheet, SheetContent, SheetHeader, SheetTitle,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import {
  PreparationPanel, TrajetPanel, PhotosPanel,
} from '../../features/installations/InterventionFieldExecution'
import {
  SerialsPanel, ConsommationPanel, MemosPanel, ReservesPanel,
  ToolReturnPanel, SafetyPanel, CompteRenduButton, CodePanel,
} from '../../features/installations/InterventionCapturePanels'
import {
  interventionStatusLabel, INTERVENTION_TYPES,
} from '../../features/installations/statuses'
import { formatDate } from '../../lib/format'

const TYPE_LABELS = Object.fromEntries(
  INTERVENTION_TYPES.map((t) => [t.value, t.label]))
const typeLabel = (k) => TYPE_LABELS[k] ?? k ?? '—'

function todayISO() {
  const d = new Date()
  const tz = d.getTimezoneOffset() * 60000
  return new Date(d - tz).toISOString().slice(0, 10)
}

export default function MaJourneePage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState(null)
  const today = useMemo(() => todayISO(), [])

  // Le rôle Technicien ne reçoit déjà que SES interventions (scope serveur).
  const load = useCallback(() => installationsApi
    .getInterventions({ date_prevue: today })
    .then((r) => {
      const all = r.data?.results ?? r.data ?? []
      // Filtre défensif : aujourd'hui uniquement (l'API peut ignorer le filtre).
      setRows(all.filter((i) => (i.date_prevue || '').slice(0, 10) === today))
    })
    .catch(() => setRows([]))
    .finally(() => setLoading(false)), [today])
  useEffect(() => { load() }, [load])

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-3 p-3 sm:p-4">
      <header className="flex items-center gap-2">
        <CalendarDays className="size-5 text-primary" aria-hidden="true" />
        <h1 className="text-lg font-semibold">Ma journée</h1>
        <span className="text-sm text-muted-foreground">{formatDate(today, { long: true })}</span>
      </header>

      {loading ? (
        <p className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement de vos interventions…
        </p>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<ClipboardList className="size-8" aria-hidden="true" />}
          title="Aucune intervention aujourd'hui"
          description="Vos interventions du jour apparaîtront ici." />
      ) : (
        <ol className="flex flex-col gap-2">
          {rows.map((interv, i) => (
            <li key={interv.id}>
              <Card className="overflow-hidden p-0">
                <button type="button" onClick={() => setActive(interv)}
                  className="flex w-full items-center gap-3 p-3 text-left active:bg-accent">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{interv.client_nom || interv.installation_reference || '—'}</span>
                      <StatusPill status={interv.statut} label={interventionStatusLabel(interv.statut)} dot={false} />
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] text-muted-foreground">
                      <span>{typeLabel(interv.type_intervention)}</span>
                      {interv.site_ville && (
                        <span className="flex items-center gap-1"><MapPin className="size-3.5" aria-hidden="true" />{interv.site_ville}</span>)}
                      {interv.photos_obligatoires_manquantes > 0 && (
                        <span className="flex items-center gap-1 text-destructive">
                          <AlertOctagon className="size-3.5" aria-hidden="true" />
                          {interv.photos_obligatoires_manquantes} photo(s) requise(s)
                        </span>)}
                    </div>
                  </div>
                  <ChevronRight className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                </button>
              </Card>
            </li>
          ))}
        </ol>
      )}

      {/* ERR103 — dériver la fiche de l'état VIVANT (rows), pas du snapshot
          capturé au tap : les changements de statut/photos faits dans la fiche
          se reflètent sans avoir à la rouvrir. */}
      <InterventionFlowSheet
        interv={active ? (rows.find((r) => r.id === active.id) ?? active) : null}
        onClose={() => setActive(null)}
        onChanged={load} />
    </div>
  )
}

function InterventionFlowSheet({ interv, onClose, onChanged }) {
  if (!interv) return null
  return (
    <Sheet open={!!interv} onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" className="w-full max-w-md overflow-y-auto p-0">
        <SheetHeader className="border-b border-border p-4">
          <SheetTitle className="flex items-center gap-2">
            {interv.client_nom || interv.installation_reference}
          </SheetTitle>
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
            <Badge>{typeLabel(interv.type_intervention)}</Badge>
            <StatusPill status={interv.statut} label={interventionStatusLabel(interv.statut)} dot={false} />
            {interv.site_ville && <span>{interv.site_ville}</span>}
          </div>
          <div className="pt-1"><CompteRenduButton intervention={interv} /></div>
        </SheetHeader>

        <Tabs defaultValue="prep" className="p-3">
          <TabsList className="flex w-full flex-wrap gap-1">
            <TabsTrigger value="prep" className="text-[12px]"><ClipboardList className="size-4" aria-hidden="true" /></TabsTrigger>
            <TabsTrigger value="trajet" className="text-[12px]"><Navigation className="size-4" aria-hidden="true" /></TabsTrigger>
            <TabsTrigger value="safety" className="text-[12px]"><ShieldCheck className="size-4" aria-hidden="true" /></TabsTrigger>
            <TabsTrigger value="photos" className="text-[12px]"><Camera className="size-4" aria-hidden="true" /></TabsTrigger>
            <TabsTrigger value="serials" className="text-[12px]"><Tag className="size-4" aria-hidden="true" /></TabsTrigger>
            <TabsTrigger value="conso" className="text-[12px]"><ListChecks className="size-4" aria-hidden="true" /></TabsTrigger>
            <TabsTrigger value="memos" className="text-[12px]"><Mic className="size-4" aria-hidden="true" /></TabsTrigger>
            <TabsTrigger value="reserves" className="text-[12px]"><AlertOctagon className="size-4" aria-hidden="true" /></TabsTrigger>
            <TabsTrigger value="outils" className="text-[12px]"><Wrench className="size-4" aria-hidden="true" /></TabsTrigger>
          </TabsList>
          <TabsContent value="prep"><PreparationPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="trajet"><TrajetPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="safety"><SafetyPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="photos"><PhotosPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="serials"><SerialsPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="conso"><ConsommationPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="memos"><MemosPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="reserves"><ReservesPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="outils">
            <ToolReturnPanel intervention={interv} onChanged={onChanged} />
            <CodePanel intervention={interv} />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}
