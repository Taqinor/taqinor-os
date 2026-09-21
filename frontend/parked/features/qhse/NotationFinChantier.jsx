import { useCallback, useEffect, useState } from 'react'
import { ClipboardCheck } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { Card, Badge, Button, Input, Spinner, EmptyState } from '../../ui'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR125 — Notation de fin de chantier (`/qhse/notations`) : rendre OPÉRABLE
   la gate advisory `NotationFinChantier`, jusqu'ici dormante (aucun appelant
   frontend ni installations).
   ----------------------------------------------------------------------------
   - Liste les notations : score / seuil / verdict / « peut clôturer » ;
   - bouton « Calculer » par notation (recalcule le score pondéré serveur) ;
   - vérificateur « Ce chantier peut-il clôturer ? » (endpoint collection
     `peut-cloturer/?chantier_id=`), advisory.
   La gate reste ADVISORY : elle informe, elle ne bloque pas (câblage services
   côté installations exposé mais non bloquant — cf. installations/services.py).
   ========================================================================== */

function verdictTone(verdict) {
  if (verdict === 'passe') return 'success'
  if (verdict === 'echec') return 'danger'
  return 'neutral'
}

function ClotureChecker() {
  const [chantierId, setChantierId] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const check = async () => {
    if (!chantierId.trim()) { setError('Indiquez un identifiant de chantier.'); return }
    setBusy(true); setError(null); setResult(null)
    try {
      const r = await qhseApi.notationsFinChantier.peutCloturer({ chantier_id: chantierId.trim() })
      setResult(r.data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Vérification impossible.')
    } finally { setBusy(false) }
  }

  return (
    <Card className="flex flex-col gap-2 p-4">
      <h3 className="font-display text-base font-semibold tracking-tight">
        Ce chantier peut-il clôturer ?
      </h3>
      <p className="text-xs text-muted-foreground">
        Gate advisory : consulte la notation la plus récente du chantier (aucune
        notation ou verdict non-échec = clôture autorisée).
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1">
          <label className="form-label" htmlFor="cloture-chantier">Identifiant du chantier</label>
          <Input id="cloture-chantier" className="w-40" value={chantierId}
            onChange={(e) => setChantierId(e.target.value)} placeholder="ex. 42" />
        </div>
        <Button type="button" loading={busy} disabled={busy} onClick={check}>Vérifier</Button>
        {result && (
          <Badge tone={result.peut_cloturer ? 'success' : 'danger'}>
            {result.peut_cloturer ? 'Peut clôturer' : 'Clôture déconseillée'}
          </Badge>
        )}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Card>
  )
}

export default function NotationFinChantier() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    qhseApi.notationsFinChantier.list()
      .then((res) => {
        if (cancelled) return
        const p = res?.data
        setRows(Array.isArray(p) ? p : (p?.results ?? []))
      })
      .catch((err) => { if (!cancelled) setError(err?.response?.data?.detail || 'Chargement impossible.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const calculer = async (notation) => {
    setBusyId(notation.id)
    try {
      await qhseApi.notationsFinChantier.calculer(notation.id)
      load()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Calcul impossible.')
    } finally { setBusyId(null) }
  }

  return (
    <div className="flex flex-col gap-4">
      <ClotureChecker />

      {loading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </p>
      )}
      {error && !loading && <EmptyState title="Impossible de charger les notations" description={error} />}

      {!loading && !error && rows.length === 0 && (
        <EmptyState icon={ClipboardCheck} title="Aucune notation de fin de chantier"
          description="Les notations créées apparaîtront ici avec leur score et leur verdict." />
      )}

      {!loading && !error && rows.map((n) => (
        <Card key={n.id} className="flex flex-col gap-2 p-4" data-testid={`notation-${n.id}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-sm">Chantier #{n.chantier_id}</span>
            <Badge tone={verdictTone(n.verdict)}>{n.verdict_display || n.verdict || 'Non calculé'}</Badge>
            <Badge tone={n.peut_cloturer ? 'success' : 'danger'}>
              {n.peut_cloturer ? 'Peut clôturer' : 'Clôture déconseillée'}
            </Badge>
            <span className="ml-auto text-xs text-muted-foreground">{formatDate(n.date_notation)}</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            <span>Score : <strong className="text-foreground tabular-nums">{n.score ?? '—'}</strong>
              {n.seuil_passage != null && <span> / seuil {n.seuil_passage}</span>}
            </span>
            <span>{n.nb_items ?? 0} item(s)</span>
          </div>
          <div>
            <Button type="button" size="sm" variant="outline" loading={busyId === n.id}
              disabled={busyId === n.id} onClick={() => calculer(n)}>
              Calculer le score
            </Button>
          </div>
        </Card>
      ))}
    </div>
  )
}
