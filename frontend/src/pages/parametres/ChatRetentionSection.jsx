// WIR157 / XKB32 — onglet « Rétention (Discuter) » : politique de rétention
// des conversations chat (loi 09-08 / conformité CNDP employés) + historique
// des purges (traçabilité). Admin uniquement — le backend gate déjà l'écriture
// (`IsAdminRole` sur `RetentionPolicyViewSet`) ; cette section n'est de toute
// façon montée que derrière `useIsAdmin()` côté appelant (comme les autres
// onglets N96/N94/XPLT23 ajoutés localement dans ParametresEntreprise.jsx).
//
// DÉFAUT : aucune politique posée pour un type de conversation = aucune purge
// (comportement inchangé, cf. `apps/chat/models.py RetentionPolicy`). Poser un
// nombre de mois active la purge pour CE type UNIQUEMENT.
import { useEffect, useState } from 'react'
import { Card, CardContent, Input, Button } from '../../ui'
import { SectionTitle, Field } from './peComponents'
import { formatDateTime } from '../../lib/format'
import messagesApi from '../../api/messagesApi'
import { toastError, toastSuccess } from '../../lib/toast'

const KINDS = [
  { value: 'dm', label: 'Messages directs (DM)' },
  { value: 'channel', label: 'Canaux' },
]

export default function ChatRetentionSection() {
  const [policies, setPolicies] = useState({}) // { dm: {id, retention_months}, channel: {...} }
  const [drafts, setDrafts] = useState({ dm: '', channel: '' })
  const [saving, setSaving] = useState(null) // conversation_kind en cours d'enregistrement, ou null
  const [history, setHistory] = useState(null) // null = chargement, [] = vide
  const [loading, setLoading] = useState(true)

  // Chargement au montage : `loading` démarre déjà à `true` (état initial
  // ci-dessus), donc aucun setState synchrone n'est nécessaire avant le
  // premier `.then` (react-hooks/set-state-in-effect — même motif que
  // PatrimoineTree.jsx/RentabiliteActif.jsx, pages/immobilier).
  useEffect(() => {
    Promise.all([
      messagesApi.retention.list(),
      messagesApi.retention.historique().catch(() => ({ data: [] })),
    ])
      .then(([pRes, hRes]) => {
        const rows = pRes.data?.results ?? pRes.data ?? []
        const byKind = {}
        for (const row of rows) byKind[row.conversation_kind] = row
        setPolicies(byKind)
        setDrafts({
          dm: byKind.dm?.retention_months ?? '',
          channel: byKind.channel?.retention_months ?? '',
        })
        setHistory(hRes.data?.results ?? hRes.data ?? [])
      })
      .catch(() => setHistory([]))
      .finally(() => setLoading(false))
  }, [])

  const save = async (kind) => {
    setSaving(kind)
    try {
      const raw = drafts[kind]
      const months = raw === '' ? null : Number(raw)
      const existing = policies[kind]
      const res = existing
        ? await messagesApi.retention.update(existing.id, { retention_months: months })
        : await messagesApi.retention.create({ conversation_kind: kind, retention_months: months })
      setPolicies((p) => ({ ...p, [kind]: res.data }))
      toastSuccess(months
        ? `Rétention posée : ${months} mois pour ${KINDS.find((k) => k.value === kind)?.label}.`
        : `Politique levée — aucune purge pour ${KINDS.find((k) => k.value === kind)?.label}.`)
    } catch (err) {
      toastError(err.response?.data?.detail || 'Enregistrement impossible')
    } finally {
      setSaving(null)
    }
  }

  return (
    <>
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle
            label="Politique de rétention"
            icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="M9 12l2 2 4-4" /></>}
          />
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Nombre de mois au-delà duquel les messages sont purgés automatiquement
            (loi 09-08 / conformité CNDP). Laisser vide = aucune politique active,
            aucune purge pour ce type de conversation. Le sweep quotidien
            journalise TOUJOURS son passage (voir l’historique ci-dessous), même
            à 0 purge.
          </p>
          {loading ? (
            <p className="text-xs text-muted-foreground">Chargement…</p>
          ) : (
            <div className="flex flex-col gap-3">
              {KINDS.map((k) => (
                <div key={k.value} className="flex items-end gap-2">
                  <div className="flex-1">
                    <Field label={k.label} htmlFor={`chat-retention-${k.value}`}>
                      <Input
                        id={`chat-retention-${k.value}`}
                        type="number" min="0" step="1"
                        placeholder="Aucune politique"
                        value={drafts[k.value]}
                        onChange={(e) => setDrafts((d) => ({ ...d, [k.value]: e.target.value }))}
                      />
                    </Field>
                  </div>
                  <Button size="sm" onClick={() => save(k.value)} loading={saving === k.value}>
                    Enregistrer
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle
            label="Historique des purges"
            icon={<><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>}
          />
          {history === null ? (
            <p className="text-xs text-muted-foreground">Chargement…</p>
          ) : history.length === 0 ? (
            <p className="text-xs text-muted-foreground">Aucune exécution enregistrée pour l’instant.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {history.map((run) => (
                <li key={run.id} className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-xs">
                  <span className="text-muted-foreground">{formatDateTime(run.ran_at)}</span>
                  <span className="font-medium text-foreground">
                    {run.messages_purged} message{run.messages_purged > 1 ? 's' : ''} purgé{run.messages_purged > 1 ? 's' : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </>
  )
}
