// NTCRM13 — Écran Paramètres → Playbooks.
//
// CRUD des playbooks : sélection des 6 stages STAGES.py (jamais codés en dur
// ici — import depuis features/crm/stages.js, le MIROIR STRICT du repo),
// tâches par étape, ordre, obligatoire/bloquant.
import { useCallback, useEffect, useState } from 'react'
import api from '../../api/axios'
import { PIPELINE_STAGES, STAGE_LABELS } from '../crm/stages'
import {
  Button, Input, Spinner, EmptyState, Card, Checkbox,
} from '../../ui'
import { toast } from '../../ui/confirm'

export default function Playbooks() {
  const [playbooks, setPlaybooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [nom, setNom] = useState('')
  const [bloquant, setBloquant] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    api.get('/crm/playbooks/')
      .then((res) => setPlaybooks(res.data?.results ?? res.data ?? []))
      .catch(() => toast.error('Impossible de charger les playbooks.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!nom.trim()) {
      toast.error('Le nom du playbook est requis.')
      return
    }
    setSaving(true)
    try {
      await api.post('/crm/playbooks/', { nom: nom.trim(), bloquant, actif: true })
      toast.success('Playbook créé.')
      setNom(''); setBloquant(false)
      load()
    } catch {
      toast.error('Échec de la création du playbook.')
    } finally {
      setSaving(false)
    }
  }

  const handleAddEtape = async (playbookId, stage) => {
    try {
      await api.post('/crm/playbook-etapes/', { playbook: playbookId, stage, ordre: 1 })
      toast.success('Étape ajoutée.')
      load()
    } catch {
      toast.error("Échec de l'ajout de l'étape (déjà présente pour ce stage ?).")
    }
  }

  const handleAddTache = async (etapeId, libelle, obligatoire) => {
    if (!libelle.trim()) return
    try {
      await api.post('/crm/playbook-taches/', {
        etape: etapeId, libelle: libelle.trim(), obligatoire, ordre: 1,
      })
      toast.success('Tâche ajoutée.')
      load()
    } catch {
      toast.error("Échec de l'ajout de la tâche.")
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="space-y-6" data-testid="playbooks-screen">
      <div>
        <h2 className="text-lg font-semibold">Playbooks</h2>
        <p className="text-sm text-muted-foreground">
          Tâches guidées par étape du pipeline (STAGES.py).
        </p>
      </div>

      <Card className="p-4 space-y-3">
        <h3 className="font-medium">Nouveau playbook</h3>
        <form onSubmit={handleCreate} className="flex gap-3 items-center">
          <Input
            placeholder="Nom du playbook"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={bloquant} onCheckedChange={setBloquant} />
            Bloquant
          </label>
          <Button type="submit" disabled={saving}>
            {saving ? 'Création…' : 'Créer'}
          </Button>
        </form>
      </Card>

      {playbooks.length === 0 ? (
        <EmptyState title="Aucun playbook" description="Créez le premier playbook ci-dessus." />
      ) : (
        <div className="space-y-4">
          {playbooks.map((pb) => (
            <Card key={pb.id} className="p-4 space-y-3" data-testid={`playbook-${pb.id}`}>
              <div className="flex items-center justify-between">
                <div className="font-medium">{pb.nom}</div>
                <span className="text-xs text-muted-foreground">
                  {pb.bloquant ? 'Bloquant' : 'Avertissement seulement'}
                </span>
              </div>
              <AjoutEtape onAdd={(stage) => handleAddEtape(pb.id, stage)} etapesExistantes={pb.etapes} />
              {(pb.etapes || []).map((etape) => (
                <div key={etape.id} className="pl-3 border-l-2 space-y-2">
                  <div className="text-sm font-medium">{STAGE_LABELS[etape.stage] || etape.stage}</div>
                  <ul className="text-sm space-y-1">
                    {(etape.taches || []).map((t) => (
                      <li key={t.id} className="flex items-center gap-2">
                        <span>{t.libelle}</span>
                        {t.obligatoire && <span className="text-xs text-destructive">(obligatoire)</span>}
                      </li>
                    ))}
                  </ul>
                  <AjoutTache onAdd={(libelle, obligatoire) => handleAddTache(etape.id, libelle, obligatoire)} />
                </div>
              ))}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function AjoutEtape({ onAdd, etapesExistantes }) {
  const [stage, setStage] = useState(PIPELINE_STAGES[0])
  const dejaPresente = (etapesExistantes || []).some((e) => e.stage === stage)
  return (
    <div className="flex gap-2 items-center">
      <select className="form-select" value={stage} onChange={(e) => setStage(e.target.value)}>
        {PIPELINE_STAGES.map((s) => (
          <option key={s} value={s}>{STAGE_LABELS[s]}</option>
        ))}
      </select>
      <Button type="button" variant="outline" disabled={dejaPresente} onClick={() => onAdd(stage)}>
        Ajouter une étape
      </Button>
    </div>
  )
}

function AjoutTache({ onAdd }) {
  const [libelle, setLibelle] = useState('')
  const [obligatoire, setObligatoire] = useState(false)
  return (
    <div className="flex gap-2 items-center">
      <Input
        placeholder="Libellé de la tâche"
        value={libelle}
        onChange={(e) => setLibelle(e.target.value)}
      />
      <label className="flex items-center gap-1 text-xs">
        <Checkbox checked={obligatoire} onCheckedChange={setObligatoire} />
        Obligatoire
      </label>
      <Button
        type="button" variant="outline"
        onClick={() => { onAdd(libelle, obligatoire); setLibelle(''); setObligatoire(false) }}
      >
        Ajouter
      </Button>
    </div>
  )
}
