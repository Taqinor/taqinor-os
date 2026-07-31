import { useEffect, useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import { Plus, CheckCircle2, PlayCircle, Sparkles } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Segmented, Card, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   WIR107 / NTFIN26-34 — Cockpit de clôture.
   ----------------------------------------------------------------------------
   Les endpoints de close management existaient (`/compta/modeles-cloture/`,
   `/instances-cloture/`, `/taches-cloture/`, `/accruals-cloture/`,
   `/justifications-variation/`) sans AUCUN écran ni client API : la clôture
   n'était donc pilotable que par curl. Cet écran matérialise le parcours
   réel : choisir la période → instancier la checklist depuis un modèle →
   cocher les tâches → poster les accruals → justifier les variations.
   ========================================================================== */

const StatutTache = statusPill({
  a_faire: { label: 'À faire', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'info' },
  fait: { label: 'Fait', tone: 'success' },
  na: { label: 'N/A', tone: 'neutral' },
})

const StatutInstance = statusPill({
  ouvert: { label: 'Ouverte', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'info' },
  valide: { label: 'Validée', tone: 'success' },
})

const StatutVariation = statusPill({
  expliquee: { label: 'Expliquée', tone: 'success' },
  non_expliquee: { label: 'Non expliquée', tone: 'warning' },
})

// Message d'erreur serveur lisible (DRF renvoie une string, {detail} ou un
// dict de champs) — même repli que les autres écrans compta.
function messageErreur(err, repli) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  const premier = d?.detail || Object.values(d || {})?.[0]
  return (Array.isArray(premier) ? premier[0] : premier) || repli
}

// Sélecteur de période comptable — partagé par les onglets qui en dépendent.
function usePeriodes() {
  const [periodes, setPeriodes] = useState([])
  useEffect(() => {
    let alive = true
    comptaApi.periodes.list({ page_size: 200 })
      .then((res) => {
        if (!alive) return
        const data = res?.data
        setPeriodes(Array.isArray(data) ? data : (data?.results || []))
      })
      .catch(() => { if (alive) setPeriodes([]) })
    return () => { alive = false }
  }, [])
  return periodes
}

function SelecteurPeriode({ periodes, value, onChange }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">Période</span>
      <select
        aria-label="Période comptable"
        className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Toutes</option>
        {periodes.map((p) => (
          <option key={p.id} value={p.id}>
            {p.libelle || `${p.date_debut} → ${p.date_fin}`}
          </option>
        ))}
      </select>
    </label>
  )
}

// ── NTFIN26-27 — Checklist de clôture (instances + tâches) ──
function ChecklistPanel({ periodes }) {
  const [periode, setPeriode] = useState('')
  const [dialog, setDialog] = useState(false)
  const params = useMemo(() => (periode ? { periode } : undefined), [periode])
  const instances = useComptaList(comptaApi.instancesCloture.list, params)

  const modelesAsync = () => comptaApi.modelesCloture.list({ page_size: 200 })
    .then((res) => {
      const data = res?.data
      const list = Array.isArray(data) ? data : (data?.results || [])
      return list.map((m) => ({ value: m.id, label: m.libelle }))
    })

  const cocher = async (tache, statut) => {
    try {
      await comptaApi.tachesCloture.cocher(tache.id, { statut })
      toast.success('Tâche mise à jour.')
      instances.reload()
    } catch (err) {
      toast.error(messageErreur(err, 'Mise à jour impossible.'))
    }
  }

  const colonnes = [
    { id: 'periode', header: 'Période', accessor: (r) => r.periode_libelle || r.periode },
    { id: 'modele', header: 'Modèle', accessor: (r) => r.modele || '—' },
    { id: 'cible', header: 'Date cible', accessor: (r) => r.date_cible, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'avancement', header: 'Avancement', searchable: false,
      accessor: (r) => {
        const taches = r.taches || []
        const faites = taches.filter((t) => t.statut === 'fait' || t.statut === 'na').length
        return `${faites}/${taches.length}`
      } },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutInstance status={v} /> },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SelecteurPeriode periodes={periodes} value={periode} onChange={setPeriode} />
        <Button size="sm" onClick={() => setDialog(true)}>
          <Plus /> Instancier une clôture
        </Button>
      </div>
      <ListShell
        title="Instances de clôture"
        columns={colonnes}
        rows={instances.rows}
        loading={instances.loading}
        error={instances.error}
        exportName="instances-cloture"
        emptyTitle="Aucune clôture ouverte"
        emptyDescription="Instanciez une checklist sur une période pour démarrer la clôture."
      />

      {instances.rows.map((inst) => (
        <Card key={inst.id} className="flex flex-col gap-2 p-3">
          <h3 className="font-display text-sm font-semibold">
            Tâches — {inst.periode_libelle || `période ${inst.periode}`}
          </h3>
          {(inst.taches || []).length === 0 && (
            <p className="text-sm text-muted-foreground">Aucune tâche sur cette instance.</p>
          )}
          <ul className="flex flex-col gap-1">
            {(inst.taches || []).map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-2 text-sm">
                <StatutTache status={t.statut} />
                <span className="grow">
                  {t.libelle}
                  {t.obligatoire ? <span className="text-destructive"> *</span> : null}
                </span>
                <span className="text-xs text-muted-foreground">
                  {t.categorie || '—'}
                </span>
                {t.statut !== 'fait' && (
                  <Button variant="outline" size="sm"
                    onClick={() => cocher(t, 'fait')}>
                    <CheckCircle2 className="size-4" /> Fait
                  </Button>
                )}
                {t.statut !== 'na' && (
                  <Button variant="ghost" size="sm"
                    onClick={() => cocher(t, 'na')}>
                    N/A
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </Card>
      ))}

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(false)}
          title="Instancier une clôture"
          fields={[
            { name: 'periode', label: 'Période', required: true,
              options: periodes.map((p) => ({
                value: p.id, label: p.libelle || `${p.date_debut} → ${p.date_fin}` })) },
            { name: 'modele', label: 'Modèle de clôture', required: true, async: modelesAsync },
            { name: 'date_cible', label: 'Date cible', type: 'date' },
          ]}
          onSubmit={(payload) => comptaApi.instancesCloture.instancier(payload)}
          onSaved={instances.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN29 — Accruals de clôture (charges à payer / produits à recevoir) ──
function AccrualsPanel({ periodes }) {
  const [periode, setPeriode] = useState('')
  const [dialog, setDialog] = useState(false)
  const params = useMemo(() => (periode ? { periode } : undefined), [periode])
  const list = useComptaList(comptaApi.accrualsCloture.list, params)

  const poster = async (row) => {
    try {
      await comptaApi.accrualsCloture.poster(row.id)
      toast.success('Accrual posté (avec son extourne).')
      list.reload()
    } catch (err) {
      toast.error(messageErreur(err, 'Postage impossible.'))
    }
  }

  const colonnes = [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'type', header: 'Type', accessor: (r) => r.type_display || r.type_accrual },
    { id: 'charge', header: 'Compte charge/produit', accessor: (r) => r.compte_charge_produit,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'contrepartie', header: 'Contrepartie', accessor: (r) => r.compte_contrepartie,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'ecriture', header: 'Écriture', accessor: (r) => r.ecriture || '—', searchable: false },
  ]

  const rowActions = (row) => (row.ecriture
    ? []
    : [{ id: 'poster', label: 'Poster', icon: PlayCircle, onClick: () => poster(row) }])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SelecteurPeriode periodes={periodes} value={periode} onChange={setPeriode} />
        <Button size="sm" onClick={() => setDialog(true)}><Plus /> Nouvel accrual</Button>
      </div>
      <ListShell
        title="Accruals de clôture"
        columns={colonnes}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="accruals-cloture"
        emptyTitle="Aucun accrual"
        emptyDescription="Aucune charge à payer / produit à recevoir sur cette période."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(false)}
          title="Nouvel accrual de clôture"
          fields={[
            { name: 'periode', label: 'Période', required: true,
              options: periodes.map((p) => ({
                value: p.id, label: p.libelle || `${p.date_debut} → ${p.date_fin}` })) },
            { name: 'type_accrual', label: 'Type', required: true, options: [
              { value: 'charge_a_payer', label: 'Charge à payer' },
              { value: 'produit_a_recevoir', label: 'Produit à recevoir' },
              { value: 'fnp', label: 'Facture non parvenue' },
            ] },
            { name: 'libelle', label: 'Libellé', required: true },
            { name: 'compte_charge_produit', label: 'Compte charge / produit', required: true },
            { name: 'compte_contrepartie', label: 'Compte de contrepartie', required: true },
            { name: 'montant', label: 'Montant', type: 'number', required: true },
          ]}
          onSubmit={(payload) => comptaApi.accrualsCloture.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN31 — Justifications de variations matérielles ──
function VariationsPanel({ periodes }) {
  const [periode, setPeriode] = useState('')
  const params = useMemo(() => (periode ? { periode } : undefined), [periode])
  const list = useComptaList(comptaApi.justificationsVariation.list, params)

  const colonnes = [
    { id: 'compte', header: 'Compte', accessor: (r) => r.compte || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'variation', header: 'Variation', accessor: (r) => Number(r.montant_variation) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'commentaire', header: 'Commentaire', accessor: (r) => r.commentaire || '—' },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutVariation status={v} /> },
  ]

  return (
    <div className="flex flex-col gap-3">
      <SelecteurPeriode periodes={periodes} value={periode} onChange={setPeriode} />
      <ListShell
        title="Justifications de variations"
        columns={colonnes}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="justifications-variation"
        emptyTitle="Aucune variation à justifier"
        emptyDescription="Aucune variation matérielle relevée sur cette période."
      />
    </div>
  )
}

// ── NTFIN26 — Modèles de checklist ──
function ModelesPanel() {
  const list = useComptaList(comptaApi.modelesCloture.list, undefined)

  const seed = async () => {
    try {
      await comptaApi.modelesCloture.seed()
      toast.success('Modèle de clôture mensuelle amorcé.')
      list.reload()
    } catch (err) {
      toast.error(messageErreur(err, 'Amorçage impossible.'))
    }
  }

  const colonnes = [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'periodicite', header: 'Périodicité',
      accessor: (r) => r.periodicite_display || r.periodicite },
    { id: 'taches', header: 'Tâches', searchable: false,
      accessor: (r) => (r.taches || []).length },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non'), searchable: false },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={seed}>
          <Sparkles className="size-4" /> Amorcer le modèle mensuel
        </Button>
      </div>
      <ListShell
        title="Modèles de checklist"
        columns={colonnes}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="modeles-cloture"
        emptyTitle="Aucun modèle"
        emptyDescription="Amorcez le modèle de clôture mensuelle standard pour démarrer."
      />
    </div>
  )
}

const TABS = [
  { value: 'checklist', label: 'Checklist' },
  { value: 'accruals', label: 'Accruals' },
  { value: 'variations', label: 'Variations' },
  { value: 'modeles', label: 'Modèles' },
]

export default function CloturePage() {
  const [tab, setTab] = useTabParam('checklist')
  const periodes = usePeriodes()

  return (
    <div className="page">
      <div className="page-header">
        <h2>Cockpit de clôture</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet clôture" />
      </div>

      {tab === 'checklist' && <ChecklistPanel periodes={periodes} />}
      {tab === 'accruals' && <AccrualsPanel periodes={periodes} />}
      {tab === 'variations' && <VariationsPanel periodes={periodes} />}
      {tab === 'modeles' && <ModelesPanel />}
    </div>
  )
}
