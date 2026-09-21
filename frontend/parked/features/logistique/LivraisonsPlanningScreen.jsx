import { useCallback, useEffect, useMemo, useState } from 'react'
import { Truck, MapPin, Route, Camera } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Badge, Spinner, EmptyState } from '../../ui'
import installationsApi from '../../api/installationsApi'
import { formatDate } from '../../lib/format'
import { LIVRAISON_STATUTS, tourneeToStops } from './logistique'
import PodCaptureDialog from './PodCaptureDialog'

/* ============================================================================
   XSTK2 — Planning des livraisons du jour (`/logistique/livraisons`).
   ----------------------------------------------------------------------------
   Liste les livraisons planifiées/en transit du jour choisi (FG329),
   propose une tournée (FG332, lecture seule/consultative — plus proche
   voisin), permet l'affectation d'un transporteur + le passage de statut
   (expédier/livrer/annuler), et ouvre la capture POD (FG330 — signature +
   photo) une fois livrée. `cout_transport`/`tarif_base` ne sont JAMAIS
   affichés ici — coûts internes, hors scope de cet écran opérationnel.
   ========================================================================== */

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function LivraisonsPlanningScreen() {
  const [jour, setJour] = useState(todayIso())
  const [livraisons, setLivraisons] = useState([])
  const [transporteurs, setTransporteurs] = useState([])
  const [tournee, setTournee] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [podFor, setPodFor] = useState(null)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([
      installationsApi.getLivraisons({ date_prevue: jour }),
      installationsApi.getTransporteurs({ active: true }),
      installationsApi.getTourneeLivraison(jour).catch(() => ({ data: null })),
    ])
      .then(([liv, transp, tour]) => {
        if (cancelled) return
        setLivraisons(liv.data?.results ?? liv.data ?? [])
        setTransporteurs(transp.data?.results ?? transp.data ?? [])
        setTournee(tour.data)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.response?.data?.detail || 'Chargement du planning impossible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [jour])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage/changement de jour
  useEffect(() => load(), [load])

  const stops = useMemo(() => tourneeToStops(tournee), [tournee])
  const ordreParLivraison = useMemo(() => {
    const m = new Map()
    stops.forEach((s) => { if (s.livraisonId != null) m.set(s.livraisonId, s.position) })
    return m
  }, [stops])

  const withBusy = async (id, fn) => {
    setBusyId(id)
    try { await fn(); await load() }
    catch (err) { setError(err?.response?.data?.detail || 'Action impossible.') }
    finally { setBusyId(null) }
  }

  const assignerTransporteur = (id, transporteurId) =>
    withBusy(id, () => installationsApi.updateLivraison(id, {
      transporteur: transporteurId || null,
    }))

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Planning des livraisons"
        subtitle="Livraisons du jour, tournée proposée et preuve de livraison."
        filters={(
          <input
            type="date"
            className="form-control w-auto"
            value={jour}
            onChange={(e) => setJour(e.target.value)}
            aria-label="Jour du planning"
          />
        )}
      />

      {loading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Chargement…</p>}
      {error && !loading && (
        <EmptyState title="Impossible de charger le planning" description={error} />
      )}

      {!loading && !error && (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <div className="flex flex-col gap-3">
            {livraisons.length === 0 && (
              <EmptyState
                icon={Truck}
                title="Aucune livraison planifiée"
                description={`Aucune livraison pour le ${formatDate(jour)}.`}
              />
            )}
            {livraisons.map((liv) => (
              <LivraisonCard
                key={liv.id}
                livraison={liv}
                position={ordreParLivraison.get(liv.id)}
                transporteurs={transporteurs}
                busy={busyId === liv.id}
                onAssignerTransporteur={(t) => assignerTransporteur(liv.id, t)}
                onExpedier={() => withBusy(liv.id, () => installationsApi.expedierLivraison(liv.id))}
                onLivrer={() => withBusy(liv.id, () => installationsApi.livrerLivraison(liv.id))}
                onAnnuler={() => withBusy(liv.id, () => installationsApi.annulerLivraison(liv.id))}
                onCapturerPod={() => setPodFor(liv)}
              />
            ))}
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2">
              <Route className="size-4 text-muted-foreground" aria-hidden="true" />
              <h3 className="font-display text-sm font-semibold tracking-tight">
                Tournée proposée
              </h3>
            </div>
            {stops.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Aucun itinéraire — planifiez des livraisons géolocalisées.
              </p>
            ) : (
              <ol className="flex flex-col gap-2 text-sm">
                {stops.map((s) => (
                  <li key={s.livraisonId} className="flex items-center gap-2">
                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-semibold">
                      {s.position ?? '—'}
                    </span>
                    <span className="flex-1 truncate">{s.reference}</span>
                    {!s.geolocalisee && (
                      <MapPin className="size-3.5 text-muted-foreground" aria-hidden="true" titleAccess="Sans GPS" />
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      )}

      {podFor && (
        <PodCaptureDialog
          livraison={podFor}
          onClose={() => setPodFor(null)}
          onSaved={() => { setPodFor(null); load() }}
        />
      )}
    </div>
  )
}

function LivraisonCard({
  livraison, position, transporteurs, busy,
  onAssignerTransporteur, onExpedier, onLivrer, onAnnuler, onCapturerPod,
}) {
  const statut = livraison.statut
  const tone = statut === 'livree' ? 'success'
    : statut === 'annulee' ? 'neutral'
    : statut === 'en_transit' ? 'info' : 'warning'

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        {position != null && (
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold">
            {position}
          </span>
        )}
        <span className="font-mono text-sm font-medium">{livraison.reference}</span>
        <Badge tone={tone}>{LIVRAISON_STATUTS[statut] || statut}</Badge>
        <span className="ml-auto text-sm text-muted-foreground">
          {livraison.installation_reference || '—'}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-muted-foreground" htmlFor={`transp-${livraison.id}`}>
          Transporteur
        </label>
        <select
          id={`transp-${livraison.id}`}
          className="form-control w-auto min-w-[180px]"
          value={livraison.transporteur ?? ''}
          disabled={busy || statut === 'livree' || statut === 'annulee'}
          onChange={(e) => onAssignerTransporteur(e.target.value)}
        >
          <option value="">— Non affecté —</option>
          {transporteurs.map((t) => (
            <option key={t.id} value={t.id}>{t.nom}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {statut === 'planifiee' && (
          <Button size="sm" disabled={busy} onClick={onExpedier}>Expédier</Button>
        )}
        {statut === 'en_transit' && (
          <Button size="sm" disabled={busy} onClick={onLivrer}>Marquer livrée</Button>
        )}
        {(statut === 'planifiee' || statut === 'en_transit') && (
          <Button size="sm" variant="outline" disabled={busy} onClick={onAnnuler}>Annuler</Button>
        )}
        {statut === 'livree' && (
          <Button size="sm" variant="outline" disabled={busy} onClick={onCapturerPod}>
            <Camera className="size-4" aria-hidden="true" /> Preuve de livraison
          </Button>
        )}
      </div>
    </div>
  )
}
