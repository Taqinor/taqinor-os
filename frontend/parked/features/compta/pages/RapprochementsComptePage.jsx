import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Send, CheckCircle2, XCircle, ListPlus } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label, Combobox, toast,
} from '../../../ui'
import { formatMAD } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList, { unwrap } from '../components/useComptaList.js'

/* ============================================================================
   PACT30 — Rapprochements de comptes de bilan (contrôle à quatre yeux).
   ----------------------------------------------------------------------------
   NTFIN35-37 : justification périodique du solde d'un compte de bilan
   (fournisseurs, comptes d'attente, TVA…) — DISTINCT du rapprochement bancaire
   déjà écranté. Report N-1 à l'ouverture, recalcul de l'écart, puis séparation
   des tâches préparateur → réviseur (403 serveur si le réviseur = préparateur,
   affiché tel quel — jamais une erreur générique). Endpoints
   /compta/rapprochements-compte/, /compta/lignes-justification-compte/.
   ========================================================================== */

const comptesAsync = () => comptaApi.comptes.list()
  .then((res) => unwrap(res).map((c) => ({ value: c.id, label: `${c.numero} — ${c.intitule}` })))

const periodesAsync = () => comptaApi.periodes.list()
  .then((res) => unwrap(res).map((p) => ({ value: p.id, label: p.libelle })))

function OuvrirDialog({ onClose, onSaved }) {
  const [compte, setCompte] = useState(null)
  const [periode, setPeriode] = useState(null)
  const [soldeGl, setSoldeGl] = useState('')
  const [comptes, setComptes] = useState([])
  const [periodes, setPeriodes] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    comptesAsync().then(setComptes)
    periodesAsync().then(setPeriodes)
  // eslint-disable-next-line react-hooks/exhaustive-deps -- chargement au montage
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!compte || !periode) return
    setSaving(true)
    try {
      await comptaApi.rapprochementsCompte.ouvrir({
        compte, periode, solde_gl: soldeGl || undefined,
      })
      toast.success('Rapprochement ouvert.')
      onSaved?.()
      onClose?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Ouverture impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Ouvrir un rapprochement de compte</DialogTitle></DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="rc-compte" required>Compte</Label>
            <Combobox id="rc-compte" options={comptes} value={compte} onChange={setCompte} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="rc-periode" required>Période</Label>
            <Combobox id="rc-periode" options={periodes} value={periode} onChange={setPeriode} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="rc-solde">Solde grand livre (optionnel)</Label>
            <Input id="rc-solde" type="number" step="any" value={soldeGl}
              onChange={(e) => setSoldeGl(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving || !compte || !periode}>
              {saving ? 'Ouverture…' : 'Ouvrir'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function LignesDialog({ rapprochement, onClose, onChanged }) {
  const [lignes, setLignes] = useState(rapprochement.lignes || [])
  const [libelle, setLibelle] = useState('')
  const [montant, setMontant] = useState('')
  const [saving, setSaving] = useState(false)

  const ajouter = async (e) => {
    e.preventDefault()
    if (!montant) return
    setSaving(true)
    try {
      await comptaApi.lignesJustificationCompte.create({
        rapprochement: rapprochement.id, libelle, montant: Number(montant) || 0,
      })
      const res = await comptaApi.rapprochementsCompte.get(rapprochement.id)
      setLignes(res.data?.lignes || [])
      setLibelle('')
      setMontant('')
      toast.success('Ligne justificative ajoutée.')
      onChanged?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Ajout impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Lignes justificatives — {rapprochement.compte_numero}</DialogTitle>
        </DialogHeader>
        {lignes.length === 0 ? (
          <EmptyState title="Aucune ligne" description="Aucune ligne de justification pour ce rapprochement." />
        ) : (
          <ComptaTable
            aria-label="Lignes justificatives"
            rows={lignes}
            getRowKey={(li) => li.id}
            columns={[
              { key: 'libelle', label: 'Libellé', cell: (li) => li.libelle || '—' },
              { key: 'type_element', label: 'Type', cell: (li) => li.type_element || '—' },
              { key: 'montant', label: 'Montant', align: 'right', numeric: true,
                sortValue: (li) => Number(li.montant) || 0, cell: (li) => formatMAD(li.montant) },
            ]}
          />
        )}
        <form onSubmit={ajouter} noValidate className="flex flex-col gap-3 border-t pt-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="lj-libelle">Libellé</Label>
            <Input id="lj-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="lj-montant" required>Montant</Label>
            <Input id="lj-montant" type="number" step="any" value={montant}
              onChange={(e) => setMontant(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Ajout…' : 'Ajouter la ligne'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function RapprochementsComptePage() {
  const [ouvrir, setOuvrir] = useState(false)
  const [lignesDe, setLignesDe] = useState(null)
  const list = useComptaList(comptaApi.rapprochementsCompte.list, undefined)

  const agir = async (fn, okMsg) => {
    try {
      await fn()
      toast.success(okMsg)
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      // NTFIN37 — le refus 403 (réviseur = préparateur) est affiché TEL QUEL,
      // jamais une erreur générique.
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
    }
  }

  const columns = [
    { id: 'compte', header: 'Compte', accessor: (r) => r.compte_numero || r.compte,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'periode', header: 'Période', accessor: (r) => r.periode,
      cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'solde_gl', header: 'Solde GL', accessor: (r) => Number(r.solde_gl) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'solde_justifie', header: 'Solde justifié', accessor: (r) => Number(r.solde_justifie) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'ecart', header: 'Écart', accessor: (r) => Number(r.ecart) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
  ]

  const rowActions = (row) => {
    const acts = [
      { id: 'lignes', label: 'Lignes justificatives', icon: ListPlus, onClick: () => setLignesDe(row) },
      { id: 'recalculer', label: 'Recalculer', icon: RefreshCw,
        onClick: () => agir(() => comptaApi.rapprochementsCompte.recalculer(row.id), 'Recalculé.') },
    ]
    if (['a_rapprocher', 'en_cours'].includes(row.statut)) {
      acts.push({ id: 'soumettre', label: 'Soumettre à revue', icon: Send,
        onClick: () => agir(() => comptaApi.rapprochementsCompte.soumettre(row.id), 'Soumis à revue.') })
    }
    if (row.statut === 'soumis') {
      acts.push({ id: 'valider', label: 'Valider', icon: CheckCircle2,
        onClick: () => agir(() => comptaApi.rapprochementsCompte.valider(row.id), 'Validé.') })
      acts.push({ id: 'rejeter', label: 'Rejeter', icon: XCircle,
        onClick: () => {
          const motif = window.prompt('Motif du rejet :')
          if (motif == null) return
          agir(() => comptaApi.rapprochementsCompte.rejeter(row.id, { motif }), 'Rejeté — retour au préparateur.')
        } })
    }
    return acts
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Rapprochements de comptes de bilan</h2>
        <div className="page-header-actions">
          <Button onClick={() => setOuvrir(true)}><Plus /> Ouvrir un rapprochement</Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Rapprochements"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        onRowClick={(row) => setLignesDe(row)}
        exportName="rapprochements-compte"
        emptyTitle="Aucun rapprochement"
        emptyDescription="Aucun rapprochement de compte de bilan ouvert pour l'instant."
      />

      {ouvrir && <OuvrirDialog onClose={() => setOuvrir(false)} onSaved={list.reload} />}
      {lignesDe && (
        <LignesDialog rapprochement={lignesDe} onClose={() => setLignesDe(null)} onChanged={list.reload} />
      )}
    </div>
  )
}
