import { useEffect, useState } from 'react'
import { FilePlus2 } from 'lucide-react'
import statuspageApi from '../../api/statuspageApi'
import {
  Card, CardContent, Badge, Button, Spinner, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from '../../ui'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   NTOBS33 — Paramètres → Fiabilité → « Historique brut » (admin interne).
   ----------------------------------------------------------------------------
   Liste les 30 derniers changements de statut RÉELLEMENT détectés
   (`GET statuspage/historique-statut/`, `core.ComponentStatusLog`) — pas un
   flot continu par tick de 5 min. « Créer un incident depuis cet événement »
   appelle `prefill-incident/`, qui NE CRÉE RIEN : il renvoie les champs
   suggérés (titre à écrire, sévérité dérivée, région, composants, début).
   AUCUN endpoint de création d'`IncidentPublic` n'existe côté serveur
   aujourd'hui (lecture publique + postmortem seulement) — la fenêtre affiche
   donc le pré-remplissage à reporter manuellement dans l'admin Django, plutôt
   que de prétendre créer l'incident elle-même.
   ========================================================================== */

const STATUT_LABEL = {
  operational: 'Opérationnel',
  degraded: 'Dégradé',
  partial_outage: 'Panne partielle',
  major_outage: 'Panne majeure',
}
const STATUT_TONE = {
  operational: 'success',
  degraded: 'warning',
  partial_outage: 'danger',
  major_outage: 'danger',
}
const SEVERITE_LABEL = { mineure: 'Mineure', majeure: 'Majeure', critique: 'Critique' }

function libelleStatut(v) {
  return STATUT_LABEL[v] || v || '—'
}

export default function HistoriqueStatutPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [prefill, setPrefill] = useState(null)
  const [prefillLoading, setPrefillLoading] = useState(false)

  useEffect(() => {
    statuspageApi.getHistoriqueStatut()
      .then((r) => setLogs(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch(() => setError('Historique indisponible.'))
      .finally(() => setLoading(false))
  }, [])

  const creerDepuis = async (log) => {
    setPrefillLoading(true)
    try {
      const r = await statuspageApi.prefillIncident(log.id)
      setPrefill({ log, ...r.data })
    } catch {
      toast.error('Pré-remplissage impossible.')
    } finally {
      setPrefillLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
      <h1 className="text-xl font-semibold">Historique brut des statuts</h1>
      <p className="text-sm text-muted-foreground">
        Les 30 derniers changements de statut détectés par composant — vérifiez
        « ce composant a-t-il vraiment flanché » avant de publier un incident.
      </p>

      {loading && <div className="flex justify-center py-8"><Spinner /></div>}
      {!loading && error && <p className="text-sm text-destructive">{error}</p>}
      {!loading && !error && logs.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucun changement de statut détecté.</p>
      )}

      {!loading && !error && logs.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {logs.map((log) => (
                <li key={log.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {log.composant} {log.region && <span className="text-muted-foreground">({log.region})</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatDateTime(log.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {log.ancien_statut && (
                      <>
                        <Badge tone={STATUT_TONE[log.ancien_statut] || 'neutral'}>
                          {libelleStatut(log.ancien_statut)}
                        </Badge>
                        <span className="text-xs text-muted-foreground">→</span>
                      </>
                    )}
                    <Badge tone={STATUT_TONE[log.nouveau_statut] || 'neutral'}>
                      {libelleStatut(log.nouveau_statut)}
                    </Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={prefillLoading}
                      onClick={() => creerDepuis(log)}
                    >
                      <FilePlus2 size={14} aria-hidden="true" />
                      Créer un incident depuis cet événement
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Dialog open={!!prefill} onOpenChange={(o) => { if (!o) setPrefill(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Pré-remplissage de l’incident</DialogTitle>
            <DialogDescription>
              Aucune création automatique : reportez ces champs dans l’admin pour publier
              l’incident. Le titre reste à écrire — jamais un texte narratif généré seul.
            </DialogDescription>
          </DialogHeader>
          {prefill && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
              <dt className="text-muted-foreground">Sévérité suggérée</dt>
              <dd><Badge tone="warning">{SEVERITE_LABEL[prefill.severite] || prefill.severite}</Badge></dd>
              <dt className="text-muted-foreground">Région</dt>
              <dd>{prefill.region || '—'}</dd>
              <dt className="text-muted-foreground">Composant(s)</dt>
              <dd>{(prefill.composants || []).join(', ') || '—'}</dd>
              <dt className="text-muted-foreground">Début</dt>
              <dd>{prefill.debute_le ? formatDateTime(prefill.debute_le) : '—'}</dd>
            </dl>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPrefill(null)}>Fermer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
