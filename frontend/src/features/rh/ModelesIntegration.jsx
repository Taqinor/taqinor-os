import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Card, Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Checkbox, confirmLeaveIfDirty,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT85 — Modèles d'intégration (onboarding).
   ----------------------------------------------------------------------------
   `ModeleIntegration`/`ElementIntegration` (XRH4, models.py:663-739) sont le
   GABARIT de checklist d'onboarding ciblé par poste/département ; la fiche
   employé coche déjà les items PAR employé — cet écran crée/édite le MODÈLE
   lui-même. Un modèle nouvellement créé est proposé à la prochaine embauche
   correspondante SANS redéploiement (`services.embaucher` lit le modèle le
   plus spécifique applicable à l'instant de l'embauche).
   ========================================================================== */

export default function ModelesIntegration() {
  const { confirmDelete } = useConfirmDialog()
  const [modeles, setModeles] = useState([])
  const [postes, setPostes] = useState([])
  const [departements, setDepartements] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [selected, setSelected] = useState(null)
  const [modeleOpen, setModeleOpen] = useState(false)
  const [elementOpen, setElementOpen] = useState(false)

  const recharger = () => setReloadTick((t) => t + 1)

  useEffect(() => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getModelesIntegration(),
      rhApi.getPostes(),
      rhApi.getDepartements(),
    ])
      .then(([m, p, d]) => {
        if (!vivant) return
        const list = unwrapList(m)
        setModeles(list)
        setPostes(unwrapList(p))
        setDepartements(unwrapList(d))
        setSelected((cur) => (cur ? list.find((x) => x.id === cur.id) ?? null : null))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les modèles d’intégration.')
        toast.error('Impossible de charger les modèles d’intégration.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadTick])

  const supprimerElement = async (el) => {
    const ok = await confirmDelete({
      title: 'Supprimer cette étape ?',
      description: `« ${el.libelle} » sera retirée du gabarit.`,
      confirmLabel: 'Supprimer',
    })
    if (!ok) return
    try {
      await rhApi.deleteElementIntegration(el.id)
      toast.success('Étape supprimée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Suppression impossible.')
    }
  }

  const columns = useMemo(() => [
    { id: 'nom', header: 'Nom du modèle', width: 220, accessor: (m) => m.nom || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'poste', header: 'Poste ciblé', width: 160, accessor: (m) => postes.find((p) => p.id === m.poste_ref)?.intitule || '', cell: (v) => v || 'Tous' },
    { id: 'departement', header: 'Département ciblé', width: 160, accessor: (m) => departements.find((d) => d.id === m.departement)?.nom || '', cell: (v) => v || 'Tous' },
    { id: 'elements', header: 'Étapes', width: 90, align: 'right', numeric: true, searchable: false, accessor: (m) => (m.elements || []).length, cell: (v) => v },
    { id: 'actif', header: 'Actif', width: 90, accessor: (m) => (m.actif ? 'oui' : 'non'), cell: (_v, m) => <Badge tone={m.actif ? 'success' : 'neutral'}>{m.actif ? 'Actif' : 'Inactif'}</Badge> },
  ], [postes, departements])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Modèles d’intégration</h2>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <ListShell
          title="Modèles"
          columns={columns}
          rows={modeles}
          loading={loading}
          error={error}
          searchable
          exportName="modeles-integration"
          onRowClick={(m) => setSelected(m)}
          actions={<Button onClick={() => setModeleOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouveau modèle</Button>}
          emptyTitle="Aucun modèle"
          emptyDescription="Aucun modèle d’intégration configuré."
        />

        <Card className="flex flex-col gap-3 p-4">
          {!selected ? (
            <p className="text-sm text-muted-foreground">Sélectionnez un modèle pour éditer ses étapes.</p>
          ) : (
            <>
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-medium">{selected.nom}</h3>
                <Button size="sm" variant="outline" onClick={() => setElementOpen(true)}>
                  <Plus size={14} strokeWidth={1.75} aria-hidden="true" />Étape
                </Button>
              </div>
              {(selected.elements || []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune étape.</p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {(selected.elements || []).map((el) => (
                    <li key={el.id} className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-sm">
                      <span>{el.ordre}. {el.libelle}</span>
                      <button type="button" aria-label={`Supprimer ${el.libelle}`} onClick={() => supprimerElement(el)} className="text-muted-foreground hover:text-destructive">
                        <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Card>
      </div>

      {modeleOpen && (
        <ModeleDialog
          postes={postes}
          departements={departements}
          onClose={() => setModeleOpen(false)}
          onSaved={() => { setModeleOpen(false); recharger() }}
        />
      )}
      {elementOpen && selected && (
        <ElementDialog
          modele={selected}
          onClose={() => setElementOpen(false)}
          onSaved={() => { setElementOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function ModeleDialog({ postes, departements, onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [posteRef, setPosteRef] = useState('')
  const [departement, setDepartement] = useState('')
  const [actif, setActif] = useState(true)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(nom || posteRef || departement)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(nom.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createModeleIntegration({
        nom: nom.trim(),
        poste_ref: posteRef || null,
        departement: departement || null,
        actif,
      })
      toast.success('Modèle créé.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.nom?.[0] || 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouveau modèle d’intégration</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mi-nom">Nom</Label>
            <Input id="mi-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mi-poste">Poste (optionnel)</Label>
              <select id="mi-poste" value={posteRef} onChange={(e) => setPosteRef(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">Tous les postes</option>
                {postes.map((p) => <option key={p.id} value={p.id}>{p.intitule}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mi-departement">Département (optionnel)</Label>
              <select id="mi-departement" value={departement} onChange={(e) => setDepartement(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">Tous les départements</option>
                {departements.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
              </select>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="mi-actif" checked={actif} onCheckedChange={setActif} />
            <Label htmlFor="mi-actif">Actif</Label>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ElementDialog({ modele, onClose, onSaved }) {
  const [libelle, setLibelle] = useState('')
  const [ordre, setOrdre] = useState(String((modele.elements || []).length))
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(libelle)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(libelle.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createElementIntegration({
        modele: modele.id, libelle: libelle.trim(), ordre: Number(ordre) || 0,
      })
      toast.success('Étape ajoutée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.libelle?.[0] || 'Ajout impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvelle étape — {modele.nom}</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ei-libelle">Libellé</Label>
            <Input id="ei-libelle" autoFocus value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="Ex. Contrat signé" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ei-ordre">Ordre</Label>
            <Input id="ei-ordre" type="number" step="any" value={ordre} onChange={(e) => setOrdre(e.target.value)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Ajout…' : 'Ajouter'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
