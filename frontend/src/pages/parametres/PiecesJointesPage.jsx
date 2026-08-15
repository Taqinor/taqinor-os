import { useCallback, useEffect, useState } from 'react'
import { Paperclip } from 'lucide-react'
import recordsApi from '../../api/recordsApi'
import { frenchError } from '../../lib/frenchError'
import {
  Card, CardContent, Button, Input, Label, EmptyState, Skeleton, Badge,
} from '../../ui'
import { Table } from '../reporting/Table'
import { PageHeader } from '../../ui/PageHeader'

/* ============================================================================
   WIR270/FG10 — Centre de pièces jointes de la société.

   L'endpoint `records/attachments/all/` était complet (scopé société,
   filtrable mime / mime_like / phase / model / since, paginé à 50) et
   `getAllAttachments` l'exposait déjà côté client — mais AUCUN écran ne
   l'appelait. Arbitrage de la tâche : l'endpoint est réel et utile, donc on
   construit l'écran plutôt que de supprimer l'export.

   L'isolation par société est garantie SERVEUR (`_scoped`) : cet écran ne
   filtre rien lui-même sur la société et n'a aucun moyen d'en sortir.
   ========================================================================== */

const PHASES = [
  { value: '', label: 'Toutes' },
  { value: 'avant', label: 'Avant' },
  { value: 'pendant', label: 'Pendant' },
  { value: 'apres', label: 'Après' },
]

const octets = (n) => {
  const v = Number(n)
  if (!Number.isFinite(v) || v <= 0) return '—'
  if (v < 1024) return `${v} o`
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} ko`
  return `${(v / (1024 * 1024)).toFixed(1)} Mo`
}

const dateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

export default function PiecesJointesPage() {
  const [filtres, setFiltres] = useState({
    mime: '', mime_like: '', phase: '', model: '', since: '',
  })
  const [lignes, setLignes] = useState([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [aSuivante, setASuivante] = useState(false)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)

  const charger = useCallback((numPage, f) => {
    setLoading(true)
    setErreur(null)
    // Un filtre vide n'est PAS envoyé : `phase=''` est un filtre légitime
    // côté serveur (« sans phase »), on ne le confond pas avec « pas de
    // filtre » — d'où le traitement à part de `phase`.
    const params = { page: numPage }
    if (f.mime) params.mime = f.mime
    if (f.mime_like) params.mime_like = f.mime_like
    if (f.phase) params.phase = f.phase
    if (f.model) params.model = f.model
    if (f.since) params.since = f.since
    recordsApi.getAllAttachments(params)
      .then((r) => {
        const d = r.data ?? {}
        setLignes(Array.isArray(d.results) ? d.results : (Array.isArray(d) ? d : []))
        setCount(d.count ?? 0)
        setASuivante(!!d.next)
      })
      .catch((err) => {
        setLignes([])
        setErreur(frenchError(err, 'Chargement des pièces jointes impossible.'))
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { charger(page, filtres) }, [charger, page]) // eslint-disable-line react-hooks/exhaustive-deps

  const appliquer = (e) => {
    e.preventDefault()
    setPage(1)
    charger(1, filtres)
  }

  const set = (k, v) => setFiltres((f) => ({ ...f, [k]: v }))

  return (
    <div className="ui-root page">
      <PageHeader
        icon={Paperclip}
        title="Pièces jointes"
        subtitle="Toutes les pièces jointes de la société, filtrables"
      />

      {erreur && (
        <div role="alert" className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erreur}
        </div>
      )}

      <Card className="mb-4">
        <CardContent className="pt-5">
          <form onSubmit={appliquer} noValidate className="flex flex-wrap items-end gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="pj-mime-like">Type (contient)</Label>
              <Input id="pj-mime-like" value={filtres.mime_like}
                     placeholder="ex : image, pdf"
                     onChange={(e) => set('mime_like', e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="pj-mime">Type exact</Label>
              <Input id="pj-mime" value={filtres.mime}
                     placeholder="ex : application/pdf"
                     onChange={(e) => set('mime', e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="pj-phase">Phase</Label>
              <select id="pj-phase" className="form-control h-9"
                      value={filtres.phase}
                      onChange={(e) => set('phase', e.target.value)}>
                {PHASES.map((p) => (
                  <option key={p.value || 'toutes'} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="pj-model">Enregistrement</Label>
              <Input id="pj-model" value={filtres.model}
                     placeholder="ex : crm.lead"
                     onChange={(e) => set('model', e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="pj-since">Depuis le</Label>
              <Input id="pj-since" type="date" value={filtres.since}
                     onChange={(e) => set('since', e.target.value)} />
            </div>
            <Button type="submit" size="sm">Filtrer</Button>
          </form>
        </CardContent>
      </Card>

      {loading ? (
        <Card><CardContent className="space-y-2 pt-5">
          {Array.from({ length: 5 }).map((unused, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </CardContent></Card>
      ) : (
        <Card>
          <CardContent className="p-0 sm:p-0">
            <Table
              aria-label="Pièces jointes"
              getRowKey={(a) => a.id}
              columns={[
                { key: 'filename', header: 'Fichier', cell: (a) => (
                  <a href={a.url} target="_blank" rel="noreferrer"
                     className="text-info hover:underline">{a.filename}</a>
                ) },
                { key: 'mime', header: 'Type', cell: (a) => a.mime || '—' },
                { key: 'phase', header: 'Phase', cell: (a) => (
                  a.phase ? <Badge tone="neutral">{a.phase}</Badge> : '—'
                ) },
                { key: 'size', header: 'Taille', align: 'right', cell: (a) => octets(a.size) },
                { key: 'uploaded_by_nom', header: 'Déposé par', cell: (a) => a.uploaded_by_nom || '—' },
                { key: 'created_at', header: 'Le', cell: (a) => dateFR(a.created_at) },
              ]}
              rows={lignes}
              empty={(
                <EmptyState
                  icon={Paperclip}
                  title="Aucune pièce jointe"
                  description="Aucune pièce jointe ne correspond à ces filtres."
                  className="border-0 py-6"
                />
              )}
            />
          </CardContent>
        </Card>
      )}

      {/* Pagination serveur (50 par page) — jamais de tri/filtre refait ici. */}
      <div className="mt-3 flex items-center gap-3 text-sm">
        <Button type="button" size="sm" variant="outline"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}>
          Précédent
        </Button>
        <span className="text-muted-foreground">
          Page {page}{count ? ` · ${count} pièce(s) au total` : ''}
        </span>
        <Button type="button" size="sm" variant="outline"
                disabled={!aSuivante || loading}
                onClick={() => setPage((p) => p + 1)}>
          Suivant
        </Button>
      </div>
    </div>
  )
}
