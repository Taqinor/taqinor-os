import { useCallback, useEffect, useState } from 'react'
import { Plus, FileCheck2 } from 'lucide-react'
import {
  Button, Spinner, EmptyState, Badge, DataTable, toast,
} from '../../../ui'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { formatMAD, formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'
import { TextField } from './fields'

/* XPRJ4 — Situations de travaux (décomptes progressifs BTP) : une situation
   par période, lignes ajoutées via l'action serveur (montants calculés),
   validation → génère la facture d'acompte une seule fois. */

const STATUT_TONE = { brouillon: 'neutral', validee: 'success', facturee: 'info' }

function AjouterLigneDialog({ situationId, onClose, onSaved }) {
  const [libelle, setLibelle] = useState('')
  const [montant, setMontant] = useState('')
  const [avancement, setAvancement] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!libelle.trim() || montant === '' || avancement === '') {
      toast.error('Libellé, montant marché HT et avancement cumulé sont obligatoires.')
      return
    }
    setSaving(true)
    try {
      const res = await gestionProjetApi.ajouterLigneSituation(situationId, {
        libelle,
        montant_marche_ht: montant,
        avancement_cumule_pct: avancement,
      })
      onSaved?.(res.data)
    } catch (err) {
      toast.error(errMessage(err, "Ajout de la ligne impossible."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose?.() }}
      title="Ajouter une ligne à la situation"
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <TextField id="ls-libelle" label="Libellé" required value={libelle} onChange={(e) => setLibelle(e.target.value)} />
        <TextField id="ls-montant" label="Montant marché HT (MAD)" inputMode="decimal" required value={montant} onChange={(e) => setMontant(e.target.value)} />
        <TextField id="ls-avancement" label="Avancement cumulé (%)" inputMode="decimal" required value={avancement} onChange={(e) => setAvancement(e.target.value)} />
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Ajout…' : 'Ajouter'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function NouvelleSituationDialog({ projetId, onClose, onSaved }) {
  const [periode, setPeriode] = useState('')
  const [retenue, setRetenue] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!periode) {
      toast.error('La période est obligatoire.')
      return
    }
    setSaving(true)
    try {
      const res = await gestionProjetApi.createSituation({
        projet: projetId,
        periode,
        retenue_garantie_pct: retenue || 0,
      })
      onSaved?.(res.data)
    } catch (err) {
      toast.error(errMessage(err, 'Création de la situation impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose?.() }}
      title="Nouvelle situation de travaux"
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <TextField id="sit-periode" label="Période" type="date" required value={periode} onChange={(e) => setPeriode(e.target.value)} />
        <TextField id="sit-retenue" label="Retenue de garantie (%)" inputMode="decimal" value={retenue} onChange={(e) => setRetenue(e.target.value)} />
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

export default function SituationsTab({ projetId }) {
  const [situations, setSituations] = useState([])
  const [lignesBySituation, setLignesBySituation] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const [ligneTarget, setLigneTarget] = useState(null)
  const [validating, setValidating] = useState(null)

  const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await gestionProjetApi.getSituations({ projet: projetId })
      const rows = asList(res)
      setSituations(rows)
      const entries = await Promise.all(rows.map(async (s) => {
        const l = await gestionProjetApi.getLignesSituation({ situation: s.id }).catch(() => ({ data: [] }))
        return [s.id, asList(l)]
      }))
      setLignesBySituation(Object.fromEntries(entries))
    } catch (err) {
      setError(errMessage(err, 'Chargement des situations impossible.'))
    } finally {
      setLoading(false)
    }
  }, [projetId])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load() })()
    return () => { alive = false }
  }, [load])

  const validerSituation = async (s) => {
    setValidating(s.id)
    try {
      const res = await gestionProjetApi.validerSituation(s.id)
      setSituations((rows) => rows.map((r) => (r.id === s.id ? res.data : r)))
      toast.success('Situation validée — facture d\'acompte générée.')
      if (res.data.avertissement_politique) {
        toast.warning(res.data.avertissement_politique)
      }
    } catch (err) {
      toast.error(errMessage(err, 'Validation impossible.'))
    } finally {
      setValidating(null)
    }
  }

  if (loading) return <div className="flex justify-center p-6"><Spinner /></div>
  if (error) return <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={load}>Réessayer</Button>} />

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" onClick={() => setShowNew(true)}>
          <Plus /> Nouvelle situation
        </Button>
      </div>
      {situations.length === 0 ? (
        <EmptyState title="Aucune situation" description="Créez un décompte progressif (situation de travaux) pour ce projet BTP." />
      ) : (
        <div className="flex flex-col gap-4">
          {situations.map((s) => (
            <div key={s.id} className="rounded-lg border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">Situation n°{s.numero}</span>
                <Badge tone={STATUT_TONE[s.statut] ?? 'neutral'}>{s.statut_display || s.statut}</Badge>
                <span className="text-xs text-muted-foreground">{s.periode ? formatDate(s.periode) : ''}</span>
                <div className="ml-auto flex gap-2">
                  {s.statut === 'brouillon' && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => setLigneTarget(s.id)}>
                        <Plus /> Ligne
                      </Button>
                      <Button size="sm" disabled={validating === s.id} onClick={() => validerSituation(s)}>
                        <FileCheck2 /> Valider
                      </Button>
                    </>
                  )}
                </div>
              </div>
              <DataTable
                className="mt-2"
                data={lignesBySituation[s.id] ?? []}
                getRowId={(l) => l.id}
                searchable={false}
                columns={[
                  { id: 'libelle', header: 'Libellé', accessor: (l) => l.libelle },
                  { id: 'marche', header: 'Marché HT', align: 'right', numeric: true, accessor: (l) => Number(l.montant_marche_ht ?? 0), cell: (v) => formatMAD(v) },
                  { id: 'avancement', header: 'Avancement cumulé', align: 'right', numeric: true, accessor: (l) => Number(l.avancement_cumule_pct ?? 0), cell: (v) => `${v} %` },
                  { id: 'periode', header: 'Montant période', align: 'right', numeric: true, accessor: (l) => Number(l.montant_periode ?? 0), cell: (v) => formatMAD(v) },
                  { id: 'cumule', header: 'Montant cumulé', align: 'right', numeric: true, accessor: (l) => Number(l.montant_cumule ?? 0), cell: (v) => formatMAD(v) },
                ]}
                emptyTitle="Aucune ligne"
                emptyDescription="Ajoutez une ligne à cette situation."
              />
            </div>
          ))}
        </div>
      )}
      {showNew && (
        <NouvelleSituationDialog
          projetId={projetId}
          onClose={() => setShowNew(false)}
          onSaved={(s) => { setShowNew(false); setSituations((r) => [...r, s]); setLignesBySituation((m) => ({ ...m, [s.id]: [] })); toast.success('Situation créée.') }}
        />
      )}
      {ligneTarget && (
        <AjouterLigneDialog
          situationId={ligneTarget}
          onClose={() => setLigneTarget(null)}
          onSaved={(l) => {
            setLigneTarget(null)
            setLignesBySituation((m) => ({ ...m, [l.situation]: [...(m[l.situation] ?? []), l] }))
            toast.success('Ligne ajoutée.')
          }}
        />
      )}
    </div>
  )
}
