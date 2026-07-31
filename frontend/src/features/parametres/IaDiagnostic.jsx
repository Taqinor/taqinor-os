// WIR153 — Paramètres → IA : panneau de diagnostic admin-only.
//
// `iaApi.getSchema()` (GET /sql-agent/schema) existait déjà côté FastAPI
// (provider/modèle LLM actif + tables autorisées de l'agent SQL) mais
// n'avait AUCUN appelant côté frontend — code mort. Ce panneau l'affiche :
// provider + modèle configurés (`SQL_AGENT_PROVIDER`/`SQL_AGENT_MODEL`) et
// la liste des tables que l'agent NL→SQL peut lire (allowlist). Lecture
// seule, aucune écriture. Réservé Administrateur (le backend n'exige que
// l'authentification ; le gating admin-only est appliqué ici côté route,
// comme les autres écrans de configuration sensibles de Paramètres).
import { useCallback, useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import iaApi from '../../api/iaApi'
import {
  Card, CardContent, Button, Spinner, EmptyState, DefinitionList, Badge,
} from '../../ui'

export default function IaDiagnostic() {
  const [schema, setSchema] = useState(null) // null = chargement
  const [loadError, setLoadError] = useState(false)

  const load = useCallback(() => {
    setLoadError(false)
    setSchema(null)
    iaApi.getSchema()
      .then((res) => setSchema(res.data || {}))
      .catch(() => setLoadError(true))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  const tables = schema?.tables || []

  return (
    <div className="mx-auto max-w-[720px] p-6">
      <div className="mb-4">
        <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
          Paramètres — IA : diagnostic de l'agent SQL
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Fournisseur/modèle LLM actif et tables que l'agent conversationnel
          (lecture seule) peut interroger.
        </p>
      </div>

      {loadError && (
        <EmptyState
          tone="error"
          icon={AlertCircle}
          title="Diagnostic indisponible"
          description="Impossible de charger l'état de l'agent IA (serveur ?)."
          action={<Button type="button" size="sm" variant="outline" onClick={load}>Réessayer</Button>}
        />
      )}

      {!loadError && schema === null && (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </p>
      )}

      {!loadError && schema !== null && (
        <div className="flex flex-col gap-4">
          <Card>
            <CardContent className="p-5">
              <DefinitionList
                items={[
                  { term: 'Fournisseur LLM', description: schema.provider || '—' },
                  { term: 'Modèle', description: schema.model || '—' },
                  {
                    term: 'Statut',
                    description: (
                      <Badge tone={schema.status === 'ok' ? 'success' : 'neutral'}>
                        {schema.status || 'inconnu'}
                      </Badge>
                    ),
                  },
                ]}
              />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <h3 className="mb-3 text-sm font-semibold text-foreground">
                Tables autorisées ({tables.length})
              </h3>
              {tables.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune table déclarée.</p>
              ) : (
                <ul className="flex flex-col gap-2 text-sm">
                  {tables.map((t) => (
                    <li key={t.table} className="flex flex-col gap-0.5 border-b border-border pb-2 last:border-b-0 last:pb-0">
                      <span className="font-mono font-medium text-foreground">{t.table}</span>
                      {t.description && (
                        <span className="text-xs text-muted-foreground">{t.description}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
