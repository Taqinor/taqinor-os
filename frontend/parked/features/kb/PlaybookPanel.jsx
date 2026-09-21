import { useCallback, useEffect, useState } from 'react'
import { Plus } from 'lucide-react'

import { Badge, Button, Checkbox, EmptyState, Input, Label, Progress, Spinner, toast } from '../../ui'
import migrationApi from '../../api/migrationApi'

/* ============================================================================
   NTMIG25 — Panneau playbook interactif dans le détail d'un article `kb` de
   type ``playbook`` : phases/étapes cochables (consomme les instances
   NTMIG22), progression globale, et le bouton « Instancier pour un
   déploiement » qui lie optionnellement un ``ProjetMigration``.
   ----------------------------------------------------------------------------
   Le modèle (article kb) affiche ses phases ; l'exécution COCHABLE se fait
   toujours sur une INSTANCE (``PlaybookInstance``, NTMIG22) — jamais sur
   l'article lui-même, qui reste un contenu versionné partagé par tous les
   déploiements. Sans instance active, ce panneau ne propose que de la créer.
   ========================================================================== */

function groupeParPhase(etapes) {
  const parPhase = new Map()
  for (const etape of etapes || []) {
    const cle = etape.phase || ''
    if (!parPhase.has(cle)) {
      parPhase.set(cle, { cle, titre: etape.phase_titre || cle, etapes: [] })
    }
    parPhase.get(cle).etapes.push(etape)
  }
  return [...parPhase.values()]
}

export default function PlaybookPanel({ articleId }) {
  const [instances, setInstances] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [clientFinal, setClientFinal] = useState('')
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await migrationApi.listPlaybookInstances({ playbook: articleId })
      const data = res?.data
      const rows = Array.isArray(data) ? data : (data?.results ?? [])
      setInstances(rows)
      setSelectedId((prev) => (rows.some((r) => r.id === prev) ? prev : rows[0]?.id ?? null))
    } catch {
      toast.error('Impossible de charger les déploiements de ce playbook.')
    } finally {
      setLoading(false)
    }
  }, [articleId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [load])

  const instancier = async () => {
    setCreating(true)
    try {
      const res = await migrationApi.instancierPlaybook({
        playbook_article: articleId,
        client_final: clientFinal.trim(),
      })
      toast.success('Playbook instancié pour un déploiement.')
      setClientFinal('')
      setInstances((prev) => [res.data, ...prev])
      setSelectedId(res.data.id)
    } catch {
      toast.error('Instanciation impossible.')
    } finally {
      setCreating(false)
    }
  }

  const cocher = async (instance, cle, fait) => {
    try {
      const res = await migrationApi.cocherEtapePlaybook(instance.id, cle, fait)
      setInstances((prev) => prev.map((i) => (i.id === instance.id ? res.data : i)))
    } catch {
      toast.error('Action impossible.')
    }
  }

  const terminer = async (instance) => {
    try {
      const res = await migrationApi.terminerPlaybookInstance(instance.id)
      setInstances((prev) => prev.map((i) => (i.id === instance.id ? res.data : i)))
      toast.success('Déploiement clôturé.')
    } catch (err) {
      const restantes = err?.response?.data?.etapes_restantes
      if (Array.isArray(restantes) && restantes.length) {
        toast.error(`${restantes.length} étape(s) restante(s).`)
      } else {
        toast.error('Clôture impossible.')
      }
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }

  const instance = instances.find((i) => i.id === selectedId) || null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-2 rounded-lg border border-border p-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pb-client-final">Client final (optionnel)</Label>
          <Input
            id="pb-client-final"
            value={clientFinal}
            onChange={(e) => setClientFinal(e.target.value)}
            placeholder="Nom du client déployé"
          />
        </div>
        <Button type="button" onClick={instancier} disabled={creating}>
          <Plus /> Instancier pour un déploiement
        </Button>
      </div>

      {instances.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {instances.map((i) => (
            <Button
              key={i.id}
              type="button"
              variant={i.id === selectedId ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedId(i.id)}
            >
              {i.client_final || `Déploiement #${i.id}`}
            </Button>
          ))}
        </div>
      )}

      {!instance ? (
        <EmptyState
          title="Aucun déploiement instancié"
          description="Instanciez ce playbook pour un déploiement afin de cocher ses étapes."
        />
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Progress value={instance.progression} className="max-w-xs" />
            <span className="text-sm text-muted-foreground">
              {instance.nb_faites} / {instance.nb_etapes} étapes ({instance.progression} %)
            </span>
            <Badge tone={instance.statut === 'termine' ? 'success' : 'neutral'}>
              {instance.statut === 'termine' ? 'Terminé' : 'En cours'}
            </Badge>
          </div>

          {groupeParPhase(instance.etapes).map((phase) => (
            <div key={phase.cle} className="rounded-lg border border-border p-3">
              <h4 className="mb-2 text-sm font-semibold">{phase.titre}</h4>
              <ul className="flex flex-col gap-2">
                {phase.etapes.map((etape) => {
                  const fait = Boolean(instance.avancement?.[etape.cle])
                  return (
                    <li key={etape.cle} className="flex items-center gap-2">
                      <Checkbox
                        checked={fait}
                        aria-label={etape.libelle}
                        disabled={instance.statut === 'termine'}
                        onCheckedChange={(val) => cocher(instance, etape.cle, val === true)}
                      />
                      <span className={fait ? 'text-muted-foreground line-through' : 'text-sm'}>
                        {etape.libelle}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}

          {instance.statut !== 'termine' && (
            <Button type="button" variant="outline" onClick={() => terminer(instance)} className="w-fit">
              Clôturer ce déploiement
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
