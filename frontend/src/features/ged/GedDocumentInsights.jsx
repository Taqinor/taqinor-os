import { useEffect, useState } from 'react'
import { Clock, ShieldCheck, Download, Star } from 'lucide-react'
import gedApi from '../../api/gedApi'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
  Button, Badge, Spinner, EmptyState, Tabs, TabsList, TabsTrigger, TabsContent,
  toast,
} from '../../ui'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR70 — Panneau « Détails » d'un document GED : timeline + rapport ACL.
   ----------------------------------------------------------------------------
   Surface deux backends déjà exposés mais sans écran :
   • Timeline (XGED15) — journal chronologique du document.
   • « Qui voit ce document et pourquoi » (XGED22) — niveau effectif par
     utilisateur/rôle + la source de résolution, exportable en CSV.
   Inclut aussi l'étoile favori personnel (ZGED7).
   ========================================================================== */

export default function GedDocumentInsights({ document, onClose }) {
  const [timeline, setTimeline] = useState(null)
  const [acl, setAcl] = useState(null)
  const [favori, setFavori] = useState(!!document?.favori)

  useEffect(() => {
    if (!document) return
    gedApi.getTimeline(document.id)
      .then((r) => setTimeline(r.data?.results ?? r.data ?? []))
      .catch(() => setTimeline([]))
    gedApi.getPermissionsEffectives(document.id)
      .then((r) => setAcl(r.data?.results ?? r.data ?? []))
      .catch(() => setAcl([]))
  }, [document])

  const exportCsv = async () => {
    try {
      const res = await gedApi.exportPermissionsEffectivesCsv(document.id)
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }))
      const a = window.document.createElement('a')
      a.href = url
      a.download = `acl-document-${document.id}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('Export impossible.') }
  }

  const toggleFavori = async () => {
    try {
      const r = await gedApi.toggleFavoriDocument(document.id, !favori)
      setFavori(!!r.data?.favori)
    } catch { toast.error('Action impossible.') }
  }

  if (!document) return null
  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <SheetContent side="right" className="w-full max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {document.nom}
            <Button size="sm" variant="ghost" onClick={toggleFavori}
              aria-label={favori ? 'Retirer des favoris' : 'Ajouter aux favoris'}>
              <Star size={16} className={favori ? 'fill-amber-400 text-amber-400' : ''} />
            </Button>
          </SheetTitle>
        </SheetHeader>
        <Tabs defaultValue="timeline" className="mt-3">
          <TabsList>
            <TabsTrigger value="timeline"><Clock size={14} /> Timeline</TabsTrigger>
            <TabsTrigger value="acl"><ShieldCheck size={14} /> Accès</TabsTrigger>
          </TabsList>

          <TabsContent value="timeline">
            {timeline === null ? <Spinner /> : timeline.length === 0 ? (
              <EmptyState title="Aucune activité" className="py-6" />
            ) : (
              <ul className="flex flex-col gap-2" data-testid="ged-timeline">
                {timeline.map((e, i) => (
                  <li key={i} className="rounded-md border px-3 py-2 text-sm">
                    <div className="flex items-center gap-1.5">
                      <Badge tone="info">{e.evenement || e.type}</Badge>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {formatDate(e.created_at)}
                      </span>
                    </div>
                    <div className="mt-1 text-muted-foreground">{e.message}</div>
                    {e.utilisateur && (
                      <div className="text-xs text-muted-foreground">par {e.utilisateur}</div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>

          <TabsContent value="acl">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Qui voit ce document et pourquoi.</p>
              <Button size="sm" variant="secondary" onClick={exportCsv}>
                <Download size={14} /> CSV
              </Button>
            </div>
            {acl === null ? <Spinner /> : acl.length === 0 ? (
              <EmptyState title="Aucune règle d'accès" className="py-6" />
            ) : (
              <ul className="flex flex-col gap-1.5" data-testid="ged-acl">
                {acl.map((l, i) => (
                  <li key={i} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="font-medium">{l.label}</span>
                    <Badge tone={l.niveau && l.niveau !== 'aucune' ? 'success' : 'neutral'}>
                      {l.niveau || 'aucune'}
                    </Badge>
                    <span className="ml-auto text-xs text-muted-foreground">{l.source}</span>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}
