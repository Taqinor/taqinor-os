import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useIsAdmin } from '../../hooks/useHasPermission'
import { FileX2, FileText, Search } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner, Input,
  Tabs, TabsList, TabsTrigger,
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import { Table } from '../reporting/Table'
import { formatMAD } from '../../lib/format'

const STATUT_TABS = [
  { key: 'tous', label: 'Tous' },
  { key: 'emise', label: 'Émis' },
  { key: 'annulee', label: 'Annulés' },
]

export default function AvoirsPage() {
  const isAdmin = useIsAdmin()
  const navigate = useNavigate()
  const [avoirs, setAvoirs] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statutFilter, setStatutFilter] = useState('tous')
  const [actionError, setActionError] = useState('')

  const load = () => {
    setLoading(true)
    ventesApi.getAvoirs()
      .then(r => setAvoirs(r.data.results ?? r.data)).catch(() => {})
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const download = async (a) => {
    setActionError('')
    try {
      const res = await ventesApi.telechargerAvoirPdf(a.id)
      openPdfBlob(res.data, `${a.reference}.pdf`)
    } catch {
      setActionError(`Téléchargement du PDF de l'avoir ${a.reference} impossible. Réessayez.`)
    }
  }
  const annuler = async (a) => {
    setActionError('')
    try {
      await ventesApi.annulerAvoir(a.id)
      load()
    } catch {
      setActionError(`Annulation de l'avoir ${a.reference} impossible. Réessayez.`)
    }
  }

  const filtered = useMemo(() => {
    let list = avoirs
    if (statutFilter !== 'tous') list = list.filter(a => a.statut === statutFilter)
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(a =>
        (a.reference ?? '').toLowerCase().includes(q) ||
        (a.facture_reference ?? '').toLowerCase().includes(q) ||
        (a.client_nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [avoirs, search, statutFilter])

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Avoirs (notes de crédit)
          {avoirs.length > 0 && <Badge tone="primary" className="ml-2 align-middle">{avoirs.length}</Badge>}
        </h2>
        {avoirs.length > 0 && (
          <Input
            type="search"
            className="w-full sm:w-64"
            leading={<Search />}
            placeholder="Référence, facture, client…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        )}
      </div>

      {actionError && (
        <div className="mt-2 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {avoirs.length > 0 && (
        <Tabs value={statutFilter} onValueChange={setStatutFilter} className="mt-3">
          <TabsList className="flex-wrap">
            {STATUT_TABS.map(t => (
              <TabsTrigger key={t.key} value={t.key}>{t.label}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={FileX2}
          title={avoirs.length === 0 ? 'Aucun avoir' : 'Aucun résultat'}
          description={avoirs.length === 0
            ? "Créez-en un depuis une facture émise (bouton « Avoir » de la liste des factures)."
            : 'Aucun avoir ne correspond à cette recherche ou ce filtre.'}
          action={avoirs.length === 0
            ? <Button onClick={() => navigate('/ventes/factures')}>Aller aux factures</Button>
            : undefined}
          className="mt-4"
        />
      ) : (
        <Card className="mt-4 overflow-hidden">
          {/* P167 — migré vers le moteur de tableau partagé. */}
          <Table
            aria-label="Avoirs"
            getRowKey={(a) => a.id}
            columns={[
              { key: 'reference', header: 'Référence', cell: (a) => <strong>{a.reference}</strong> },
              { key: 'facture', header: 'Facture', cell: (a) => a.facture_reference },
              { key: 'client', header: 'Client', cell: (a) => a.client_nom },
              { key: 'total_ttc', header: 'Total TTC', align: 'right', cell: (a) => formatMAD(a.total_ttc) },
              { key: 'motif', header: 'Motif', cell: (a) => a.motif || '—' },
              { key: 'statut', header: 'Statut', cell: (a) => <StatusPill status={a.statut} label={a.statut_display} /> },
              {
                key: 'actions',
                header: '',
                align: 'right',
                cell: (a) => (
                  <div className="flex items-center justify-end gap-2">
                    <Button size="sm" variant="outline" onClick={() => download(a)}>
                      <FileText /> PDF
                    </Button>
                    {isAdmin && a.statut !== 'annulee' && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="sm" variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10">
                            Annuler
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Annuler l'avoir {a.reference} ?</AlertDialogTitle>
                            <AlertDialogDescription>
                              Cette action marque l'avoir comme annulé.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Retour</AlertDialogCancel>
                            <AlertDialogAction onClick={() => annuler(a)}>Annuler l'avoir</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>
                ),
              },
            ]}
            rows={filtered}
          />
        </Card>
      )}
    </div>
  )
}
