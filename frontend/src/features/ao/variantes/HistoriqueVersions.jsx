import { useCallback, useEffect, useMemo, useState } from 'react'
import { History, AlertTriangle, Undo2 } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { Card, Button, EmptyState, Skeleton, toast } from '../../../ui'
import { useConfirmDialog } from '../../../ui/confirm'
import { formatDateTime, formatNumber } from '../../../lib/format'
import DiffPlan from './DiffPlan'

/* ============================================================================
   AOF105 (1/2) — Historique des calepinages + comparaison A/B.
   ----------------------------------------------------------------------------
   Liste les versions d'un calepinage (auteur, date, paramètres, compte),
   laisse en choisir DEUX (A = référence, B = comparée) et les superpose via
   `DiffPlan`.

   ── RETOUR À UNE VERSION ANTÉRIEURE ───────────────────────────────────────
   Le retour est un PATCH sur le calepinage (`{ restaurer_version: <id> }`) :
   c'est le SERVICE SERVEUR qui restaure ET qui écrit la trace dans le chatter
   `records` de l'affaire. Ce composant n'écrit JAMAIS lui-même une entrée de
   chatter (le chatter est une primitive plateforme — ne jamais en recoder une
   locale) et ne pose aucun `window.confirm` : la confirmation passe par
   `useConfirmDialog()` (gate a11y AOF188 : aucun `alert/confirm/prompt`
   natif dans les écrans AO).
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

function ParametresResume({ parametres }) {
  const entrees = Object.entries(parametres ?? {})
  if (!entrees.length) return <span className="text-muted-foreground">—</span>
  return (
    <span className="text-muted-foreground">
      {entrees.map(([k, v]) => `${k} : ${v}`).join(' · ')}
    </span>
  )
}

export function HistoriqueVersions({ calepinageId, onRestaure }) {
  const [aId, setAId] = useState(null)
  const [bId, setBId] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const { confirm } = useConfirmDialog()

  const params = useMemo(() => ({ versions_de: calepinageId }), [calepinageId])
  const { data: versions, loading, error, refetch } = useResource(
    () => aoApi.calepinages.list(params), params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger l’historique.' },
  )

  // Par défaut : la plus ancienne en A, la plus récente en B (ordre serveur
  // conservé — le front ne retrie pas un historique).
  useEffect(() => {
    if (versions.length < 2) return
    setAId((prev) => (versions.some((v) => v.id === prev) ? prev : versions[versions.length - 1].id))
    setBId((prev) => (versions.some((v) => v.id === prev) ? prev : versions[0].id))
  }, [versions])

  const versionA = useMemo(() => versions.find((v) => v.id === aId) ?? null, [versions, aId])
  const versionB = useMemo(() => versions.find((v) => v.id === bId) ?? null, [versions, bId])

  const restaurer = useCallback(async (version) => {
    const ok = await confirm({
      title: `Revenir à la version « ${version.libelle} » ?`,
      description: 'Le calepinage courant sera remplacé. L’opération est tracée dans le fil de l’affaire.',
      confirmLabel: 'Revenir à cette version',
      cancelLabel: 'Annuler',
    })
    if (!ok) return
    setEnCours(true)
    try {
      // Le SERVEUR restaure et trace dans le chatter `records` de l'affaire.
      await aoApi.calepinages.update(calepinageId, { restaurer_version: version.id })
      toast.success(`Retour à « ${version.libelle} » — tracé dans le fil de l’affaire.`)
      await refetch()
      onRestaure?.(version)
    } catch (e) {
      toast.error(errMsg(e, 'Retour à cette version impossible.'))
    } finally {
      setEnCours(false)
    }
  }, [calepinageId, confirm, refetch, onRestaure])

  if (loading) {
    return <Card className="p-4"><Skeleton className="h-5 w-1/3" /><Skeleton className="mt-3 h-24 w-full" /></Card>
  }
  if (error) {
    return <EmptyState icon={AlertTriangle} title="Impossible de charger l’historique" description={error} />
  }
  if (!versions.length) {
    return (
      <EmptyState
        icon={History}
        title="Aucune version enregistrée"
        description="Chaque calcul de calepinage crée une version : l’historique se remplit au premier lancement."
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-2 p-4">
        <h2 className="font-display text-lg font-semibold tracking-tight">Historique des calepinages</h2>
        <div className="-mx-1 overflow-x-auto px-1">
          <table className="w-full min-w-[38rem] border-collapse text-sm">
            <caption className="sr-only">
              Versions du calepinage : auteur, date, paramètres, compte de modules.
            </caption>
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="py-2 pr-3 font-medium">A</th>
                <th scope="col" className="py-2 pr-3 font-medium">B</th>
                <th scope="col" className="py-2 pr-3 font-medium">Version</th>
                <th scope="col" className="py-2 pr-3 font-medium">Auteur</th>
                <th scope="col" className="py-2 pr-3 font-medium">Date</th>
                <th scope="col" className="py-2 pr-3 font-medium">Paramètres</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Modules</th>
                <th scope="col" className="py-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.id} className="border-b border-border/60">
                  <td className="py-2 pr-3">
                    <Button
                      size="sm"
                      variant={v.id === aId ? 'default' : 'outline'}
                      aria-pressed={v.id === aId}
                      onClick={() => setAId(v.id)}
                      aria-label={`Référence A : ${v.libelle}`}
                    >
                      A
                    </Button>
                  </td>
                  <td className="py-2 pr-3">
                    <Button
                      size="sm"
                      variant={v.id === bId ? 'default' : 'outline'}
                      aria-pressed={v.id === bId}
                      onClick={() => setBId(v.id)}
                      aria-label={`Comparée B : ${v.libelle}`}
                    >
                      B
                    </Button>
                  </td>
                  <th scope="row" className="py-2 pr-3 text-left font-normal">{v.libelle}</th>
                  <td className="py-2 pr-3">{v.auteur ?? '—'}</td>
                  <td className="py-2 pr-3">{formatDateTime(v.cree_le)}</td>
                  <td className="py-2 pr-3"><ParametresResume parametres={v.parametres} /></td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {formatNumber(v.plan?.compte_modules, { decimals: 0 })}
                  </td>
                  <td className="py-2">
                    {v.courante ? (
                      <span className="text-xs text-muted-foreground">Version courante</span>
                    ) : (
                      <Button size="sm" variant="outline" disabled={enCours} onClick={() => restaurer(v)}>
                        <Undo2 size={14} aria-hidden="true" /> Revenir à cette version
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted-foreground">
          Un retour à une version antérieure est tracé dans le fil de l’affaire (auteur, date, version restaurée).
        </p>
      </Card>

      {versionA && versionB && versionA.id !== versionB.id ? (
        <DiffPlan versionA={versionA} versionB={versionB} />
      ) : (
        <Card className="p-4 text-sm text-muted-foreground">
          Choisissez deux versions différentes (A et B) pour superposer leurs plans.
        </Card>
      )}
    </div>
  )
}

export default HistoriqueVersions
