import { useState } from 'react'
import { Sparkles, X } from 'lucide-react'
import { Button, Badge, EmptyState, toast, confirmLeaveIfDirty } from '../../../ui'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage, TYPES_INSTALLATION } from '../constants'
import { TextField, SelectField } from './fields'

/* XPRJ29 — Plan de tâches IA : propose (GET plan JSON depuis un devis lié,
   AUCUNE écriture — key-gated LLM) puis confirme (matérialise après relecture
   utilisateur, l'utilisateur peut retirer une tâche proposée avant validation).
   Jamais automatique : deux clics distincts, l'un affiche, l'autre écrit. */

export default function PlanIaDialog({ projetId, onClose, onConfirmed }) {
  const [devisId, setDevisId] = useState('')
  const [typeInstallation, setTypeInstallation] = useState('residentiel')
  const [proposition, setProposition] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [confirming, setConfirming] = useState(false)
  // VX168 — garde de fermeture : une proposition générée (non confirmée) ne
  // doit pas être perdue sur un clic malheureux, pas plus qu'une saisie.
  const dirty = Boolean(devisId || typeInstallation !== 'residentiel' || proposition)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const genererPlan = async (e) => {
    e.preventDefault()
    if (!devisId) {
      toast.error('L\'identifiant du devis est obligatoire.')
      return
    }
    setGenerating(true)
    try {
      const res = await gestionProjetApi.genererPlanIa(projetId, {
        devis_id: devisId,
        type_installation: typeInstallation,
      })
      setProposition(res.data.taches ?? [])
    } catch (err) {
      toast.error(errMessage(err, 'Génération du plan IA impossible.'))
    } finally {
      setGenerating(false)
    }
  }

  const retirerTache = (index) => {
    setProposition((rows) => rows.filter((unused, i) => i !== index))
  }

  const confirmerPlan = async () => {
    if (!proposition || proposition.length === 0) {
      toast.error('Aucune tâche à confirmer.')
      return
    }
    setConfirming(true)
    try {
      const res = await gestionProjetApi.confirmerPlanIa(projetId, { taches: proposition })
      toast.success(`${res.data.length} tâche(s) créée(s).`)
      onConfirmed?.(res.data)
    } catch (err) {
      toast.error(errMessage(err, 'Confirmation du plan impossible.'))
    } finally {
      setConfirming(false)
    }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) closeIfConfirmed() }}
      title="Générer un plan de tâches par IA"
      description="Propose un brouillon de WBS depuis un devis lié — rien n'est créé tant que vous n'avez pas confirmé."
    >
      <div className="flex flex-col gap-4">
        {!proposition ? (
          <form onSubmit={genererPlan} noValidate className="flex flex-col gap-3">
            <TextField id="pia-devis" label="ID du devis lié" inputMode="numeric" required autoFocus value={devisId} onChange={(e) => setDevisId(e.target.value)} />
            <SelectField id="pia-type" label="Type d'installation" options={TYPES_INSTALLATION} value={typeInstallation} onChange={(e) => setTypeInstallation(e.target.value)} />
            <div className="mt-2 flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
              <Button type="submit" disabled={generating}>
                <Sparkles className="size-4" aria-hidden="true" /> {generating ? 'Génération…' : 'Proposer un plan'}
              </Button>
            </div>
          </form>
        ) : proposition.length === 0 ? (
          <EmptyState title="Plan vide" description="Toutes les tâches proposées ont été retirées." />
        ) : (
          <>
            <ul className="flex max-h-80 flex-col gap-2 overflow-y-auto">
              {proposition.map((t, i) => (
                <li key={`${t.code}-${i}`} className="flex items-start gap-2 rounded-md border border-border p-2 text-sm">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {t.code && <span className="font-mono text-xs text-muted-foreground">{t.code}</span>}
                      <span className="font-medium">{t.libelle}</span>
                      {t.phase && <Badge tone="info">{t.phase}</Badge>}
                      {t.duree_jours != null && <span className="text-xs text-muted-foreground">{t.duree_jours} j</span>}
                    </div>
                    {t.dependances_fs?.length > 0 && (
                      <p className="mt-0.5 text-xs text-muted-foreground">Dépend de : {t.dependances_fs.join(', ')}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
                    onClick={() => retirerTache(i)}
                    aria-label={`Retirer ${t.libelle}`}
                  >
                    <X className="size-3.5" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setProposition(null)}>Recommencer</Button>
              <Button type="button" disabled={confirming} onClick={confirmerPlan}>
                {confirming ? 'Création…' : `Confirmer et créer ${proposition.length} tâche(s)`}
              </Button>
            </div>
          </>
        )}
      </div>
    </ResponsiveDialog>
  )
}
