import { useEffect, useMemo, useState } from 'react'
import { Inbox, Link2, Plus } from 'lucide-react'
import innovationApi from '../../api/innovationApi'
import {
  Badge, Button, Card, DataTable, EmptyState, IconButton,
  Input, Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Spinner, Textarea, toast,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR150 — Écran admin « Retours produit » (canal founder, NTIDE36-39).
   ----------------------------------------------------------------------------
   `FeedbackProduitViewSet`/`FeedbackResumeView`/`AnnonceProduitViewSet`
   n'avaient aucun consommateur admin : seul `.feedback.create` était appelé
   (bouton discret côté utilisateur) et le digest email quotidien était la
   seule visibilité — `AnnonceProduit` n'apparaissait même pas dans le client
   API. Palier admin (`IdeasSeeAll`, même gate que la boîte à idées) : liste,
   résumé par thème, création d'annonce, clôture par annonce liée.
   ========================================================================== */

const STATUT_TONE = { envoye: 'warning', lu: 'neutral', adresse: 'success' }

export default function RetoursProduitPage() {
  const [feedbacks, setFeedbacks] = useState([])
  const [resume, setResume] = useState([])
  const [annonces, setAnnonces] = useState([])
  const [loading, setLoading] = useState(true)

  const [annonceDialogOpen, setAnnonceDialogOpen] = useState(false)
  const [annonceForm, setAnnonceForm] = useState({ titre: '', description: '', lien: '' })
  const [savingAnnonce, setSavingAnnonce] = useState(false)

  const [lierTarget, setLierTarget] = useState(null) // feedback en cours de clôture
  const [mode, setMode] = useState('existante') // 'existante' | 'nouvelle'
  const [annonceId, setAnnonceId] = useState('')
  const [nouvelleAnnonce, setNouvelleAnnonce] = useState({ titre: '', description: '', lien: '' })
  const [message, setMessage] = useState('')
  const [busyId, setBusyId] = useState(null)

  const reload = () => {
    innovationApi.feedback.list().then((r) => setFeedbacks(r.data?.results ?? r.data ?? [])).catch(() => {})
    innovationApi.feedback.resume().then((r) => setResume(r.data?.results ?? [])).catch(() => {})
    innovationApi.annonces.list().then((r) => setAnnonces(r.data?.results ?? r.data ?? [])).catch(() => {})
  }

  useEffect(() => {
    let active = true
    Promise.all([
      innovationApi.feedback.list(),
      innovationApi.feedback.resume(),
      innovationApi.annonces.list(),
    ])
      .then(([f, r, a]) => {
        if (!active) return
        setFeedbacks(f.data?.results ?? f.data ?? [])
        setResume(r.data?.results ?? [])
        setAnnonces(a.data?.results ?? a.data ?? [])
      })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const creerAnnonce = (e) => {
    e.preventDefault()
    setSavingAnnonce(true)
    innovationApi.annonces.create(annonceForm)
      .then(() => {
        toast.success('Annonce créée.')
        setAnnonceDialogOpen(false)
        setAnnonceForm({ titre: '', description: '', lien: '' })
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail ?? 'Création impossible.'))
      .finally(() => setSavingAnnonce(false))
  }

  const openLier = (feedback) => {
    setLierTarget(feedback)
    setMode('existante')
    setAnnonceId('')
    setNouvelleAnnonce({ titre: '', description: '', lien: '' })
    setMessage('')
  }

  const confirmerLiaison = () => {
    if (!lierTarget) return
    const body = { message }
    if (mode === 'existante') {
      if (!annonceId) return
      body.annonce_id = Number(annonceId)
    } else {
      if (!nouvelleAnnonce.titre.trim()) return
      body.annonce = nouvelleAnnonce
    }
    setBusyId(lierTarget.id)
    innovationApi.feedback.lierAnnonce(lierTarget.id, body)
      .then(() => {
        toast.success('Retour clôturé — annonce liée.')
        setLierTarget(null)
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail ?? 'Liaison impossible.'))
      .finally(() => setBusyId(null))
  }

  const columns = useMemo(() => [
    { id: 'titre', header: 'Titre', accessor: (r) => r.titre },
    {
      id: 'theme', header: 'Thème', width: 130,
      accessor: (r) => r.theme_display || r.theme,
    },
    {
      id: 'auteur', header: 'Auteur', width: 150,
      accessor: (r) => r.auteur_nom || '—',
    },
    {
      id: 'statut', header: 'Statut', width: 110,
      accessor: (r) => r.statut,
      cell: (v, r) => <Badge tone={STATUT_TONE[v] ?? 'neutral'}>{r.statut_display || v}</Badge>,
    },
    {
      id: 'date', header: 'Reçu le', width: 160,
      accessor: (r) => r.date_creation ?? '',
      cell: (v) => (v ? formatDateTime(v) : '—'),
    },
    {
      id: 'actions', header: '', width: 120, align: 'right',
      accessor: () => '',
      cell: (v, r) => (r.statut !== 'adresse' ? (
        <IconButton variant="ghost" label="Lier une annonce" disabled={busyId === r.id} onClick={() => openLier(r)}>
          <Link2 />
        </IconButton>
      ) : (r.annonce_titre ? <span className="text-xs text-muted-foreground">{r.annonce_titre}</span> : null)),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- openLier recréé à chaque rendu
  ], [busyId])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title inline-flex items-center gap-2">
          <Inbox className="size-5" aria-hidden="true" />
          Retours produit
        </h1>
        <div className="page-subtitle">
          Canal de suggestions envoyées au founder — clôturez un retour en le liant à une annonce produit.
        </div>
      </div>

      {resume.length > 0 && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {resume.map((t) => (
            <Card key={t.theme} className="p-3">
              <div className="text-xs text-muted-foreground">{t.theme_display}</div>
              <div className="text-lg font-semibold tabular-nums">{t.total}</div>
              {t.non_lus > 0 && <Badge tone="warning">{t.non_lus} non lu(s)</Badge>}
            </Card>
          ))}
        </div>
      )}

      <div className="mb-4 flex justify-end">
        <Button variant="outline" onClick={() => setAnnonceDialogOpen(true)}><Plus /> Nouvelle annonce</Button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : feedbacks.length === 0 ? (
        <EmptyState
          title="Aucun retour produit"
          description="Aucune suggestion n'a encore été envoyée."
          className="my-6"
        />
      ) : (
        <DataTable
          data={feedbacks}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Retours produit"
        />
      )}

      {/* ── Dialogue nouvelle annonce (standalone) ── */}
      <ResponsiveDialog open={annonceDialogOpen} onOpenChange={setAnnonceDialogOpen} title="Nouvelle annonce produit">
        <form onSubmit={creerAnnonce} noValidate className="flex flex-col gap-3">
          <div>
            <Label htmlFor="ann-titre">Titre</Label>
            <Input id="ann-titre" value={annonceForm.titre} onChange={(e) => setAnnonceForm((f) => ({ ...f, titre: e.target.value }))} />
          </div>
          <div>
            <Label htmlFor="ann-desc">Description</Label>
            <Textarea id="ann-desc" rows={2} value={annonceForm.description} onChange={(e) => setAnnonceForm((f) => ({ ...f, description: e.target.value }))} />
          </div>
          <div>
            <Label htmlFor="ann-lien">Lien</Label>
            <Input id="ann-lien" type="url" value={annonceForm.lien} onChange={(e) => setAnnonceForm((f) => ({ ...f, lien: e.target.value }))} placeholder="Optionnel" />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setAnnonceDialogOpen(false)}>Annuler</Button>
            <Button type="submit" loading={savingAnnonce} disabled={!annonceForm.titre.trim()}>Créer</Button>
          </div>
        </form>
      </ResponsiveDialog>

      {/* ── Dialogue lier un retour à une annonce (« vous l'aviez demandé, c'est livré ») ── */}
      <ResponsiveDialog
        open={!!lierTarget}
        onOpenChange={(o) => { if (!o) setLierTarget(null) }}
        title={lierTarget ? `Lier « ${lierTarget.titre} » à une annonce` : 'Lier une annonce'}
      >
        <div className="flex flex-col gap-3">
          <div className="flex gap-2">
            <Button type="button" size="sm" variant={mode === 'existante' ? 'default' : 'outline'} onClick={() => setMode('existante')}>
              Annonce existante
            </Button>
            <Button type="button" size="sm" variant={mode === 'nouvelle' ? 'default' : 'outline'} onClick={() => setMode('nouvelle')}>
              Nouvelle annonce
            </Button>
          </div>

          {mode === 'existante' ? (
            <div>
              <Label htmlFor="lier-annonce">Annonce</Label>
              <Select value={annonceId} onValueChange={setAnnonceId}>
                <SelectTrigger id="lier-annonce" aria-label="Annonce"><SelectValue placeholder="Choisir une annonce…" /></SelectTrigger>
                <SelectContent>
                  {annonces.map((a) => <SelectItem key={a.id} value={String(a.id)}>{a.titre}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <>
              <div>
                <Label htmlFor="lier-titre">Titre</Label>
                <Input id="lier-titre" value={nouvelleAnnonce.titre} onChange={(e) => setNouvelleAnnonce((f) => ({ ...f, titre: e.target.value }))} />
              </div>
              <div>
                <Label htmlFor="lier-desc">Description</Label>
                <Textarea id="lier-desc" rows={2} value={nouvelleAnnonce.description} onChange={(e) => setNouvelleAnnonce((f) => ({ ...f, description: e.target.value }))} />
              </div>
            </>
          )}

          <div>
            <Label htmlFor="lier-message">Message à l'auteur</Label>
            <Textarea id="lier-message" rows={2} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Optionnel" />
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setLierTarget(null)}>Annuler</Button>
            <Button
              type="button"
              loading={busyId === lierTarget?.id}
              disabled={mode === 'existante' ? !annonceId : !nouvelleAnnonce.titre.trim()}
              onClick={confirmerLiaison}
            >
              Clôturer
            </Button>
          </div>
        </div>
      </ResponsiveDialog>
    </div>
  )
}
