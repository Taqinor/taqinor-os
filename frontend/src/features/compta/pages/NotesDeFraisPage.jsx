import { useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import { Plus, Pencil, Check, X, Send, Download, BarChart3 } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Segmented, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import rhApi from '../../../api/rhApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

// VX229 — options employé chargées une fois à l'ouverture du dialog (au lieu
// d'un champ « Employé (ID) » tapé à la main), « Nom Prénom » comme EmployeList.
const employeAsync = () => rhApi.getEmployes({ page_size: 500 }).then((res) => {
  const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
  return list.map((e) => ({
    value: e.id,
    label: `${e.nom || ''} ${e.prenom || ''}`.trim() || `Employé #${e.id}`,
  }))
})

/* ============================================================================
   FG135/FG136 — Notes de frais (écran VALIDATION / COMPTABLE).
   ----------------------------------------------------------------------------
   DISTINCT de l'écran RH self-service (saisie employé) : cet écran est réservé
   à la comptabilité/direction pour piloter le cycle complet — notes isolées,
   rapports (regroupement de notes), plafonds par catégorie, barèmes
   indemnités km/per-diem chantier, indemnités chantier — avec les actions de
   service soumettre/valider/rejeter/rembourser/reçu PDF/analyse. Endpoints :
   /compta/notes-frais/, /rapports-notes-frais/, /plafonds-notes-frais/,
   /baremes-indemnite/, /indemnites-chantier/.
   ========================================================================== */

const TABS = [
  { value: 'notesFrais', label: 'Notes de frais' },
  { value: 'rapportsNotesFrais', label: 'Rapports' },
  { value: 'plafondsNotesFrais', label: 'Plafonds' },
  { value: 'baremesIndemnite', label: 'Barèmes indemnité' },
  { value: 'indemnitesChantier', label: 'Indemnités chantier' },
]

const RESOURCE = {
  notesFrais: comptaApi.notesFrais,
  rapportsNotesFrais: comptaApi.rapportsNotesFrais,
  plafondsNotesFrais: comptaApi.plafondsNotesFrais,
  baremesIndemnite: comptaApi.baremesIndemnite,
  indemnitesChantier: comptaApi.indemnitesChantier,
}

const StatutFrais = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  soumise: { label: 'Soumise', tone: 'info' },
  soumis: { label: 'Soumis', tone: 'info' },
  validee: { label: 'Validée', tone: 'success' },
  valide: { label: 'Validé', tone: 'success' },
  rejetee: { label: 'Rejetée', tone: 'danger' },
  rejete: { label: 'Rejeté', tone: 'danger' },
  remboursee: { label: 'Remboursée', tone: 'success' },
  rembourse: { label: 'Remboursé', tone: 'success' },
})

const money = (v) => formatMAD(v)

const COLUMNS = {
  notesFrais: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'employe', header: 'Employé', accessor: (r) => r.employe_nom || r.employe || '—' },
    { id: 'date', header: 'Date', accessor: (r) => r.date_frais, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'motif', header: 'Motif', accessor: (r) => r.motif || '—' },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFrais status={v} /> },
  ],
  rapportsNotesFrais: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'employe', header: 'Employé', accessor: (r) => r.employe_nom || r.employe || '—' },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'total', header: 'Total', accessor: (r) => Number(r.total) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFrais status={v} /> },
  ],
  plafondsNotesFrais: [
    { id: 'categorie', header: 'Catégorie', accessor: (r) => r.categorie_display || r.categorie },
    { id: 'montant_max', header: 'Plafond', accessor: (r) => Number(r.montant_max) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  baremesIndemnite: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'taux_km', header: 'Taux/km', accessor: (r) => Number(r.taux_km) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'per_diem', header: 'Per diem', accessor: (r) => Number(r.per_diem) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'defaut', header: 'Par défaut', accessor: (r) => (r.par_defaut ? 'Oui' : 'Non'), searchable: false },
  ],
  indemnitesChantier: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'employe', header: 'Employé', accessor: (r) => r.employe_nom || r.employe || '—' },
    { id: 'chantier', header: 'Chantier', accessor: (r) => r.libelle_chantier || '—' },
    { id: 'date', header: 'Date', accessor: (r) => r.date_deplacement, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'montant', header: 'Montant total', accessor: (r) => Number(r.montant_total) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFrais status={v} /> },
  ],
}

const FIELDS = {
  notesFrais: [
    { name: 'employe', label: 'Employé', async: employeAsync, required: true },
    { name: 'date_frais', label: 'Date', type: 'date', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'motif', label: 'Motif' },
  ],
  rapportsNotesFrais: [
    { name: 'employe', label: 'Employé', async: employeAsync, required: true },
    { name: 'libelle', label: 'Libellé' },
  ],
  plafondsNotesFrais: [
    { name: 'categorie', label: 'Catégorie', required: true },
    { name: 'montant_max', label: 'Plafond', type: 'number', required: true },
  ],
  baremesIndemnite: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'taux_km', label: 'Taux/km', type: 'number' },
    { name: 'per_diem', label: 'Per diem', type: 'number' },
  ],
  indemnitesChantier: [
    { name: 'employe', label: 'Employé', async: employeAsync, required: true },
    { name: 'date_deplacement', label: 'Date', type: 'date', required: true },
    { name: 'libelle_chantier', label: 'Chantier' },
    { name: 'nombre_jours', label: 'Nombre de jours', type: 'number' },
  ],
}

const TRESO_ID_HINT = 'ID du compte de trésorerie payeur'

export default function NotesDeFraisPage() {
  const [tab, setTab] = useTabParam('notesFrais')  // VX231(c) — onglet persisté (?onglet=)
  const [dialog, setDialog] = useState(null)

  const list = useComptaList(RESOURCE[tab].list, undefined)

  const act = async (fn, okMsg) => {
    try {
      await fn()
      toast.success(okMsg)
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
    }
  }

  const download = async (fn, filename) => {
    try {
      const res = await fn()
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, filename)
    } catch {
      toast.error('Téléchargement indisponible.')
    }
  }

  const rembourserPrompt = (fn) => {
    const compte = window.prompt(TRESO_ID_HINT)
    if (!compte) return
    act(() => fn({ compte_tresorerie: compte }), 'Remboursement enregistré.')
  }

  const rowActions = (row) => {
    if (tab === 'notesFrais') {
      const acts = []
      if (row.statut === 'brouillon' || row.statut === 'rejetee') {
        acts.push({ id: 'soumettre', label: 'Soumettre', icon: Send,
          onClick: () => act(() => comptaApi.notesFrais.soumettre(row.id), 'Note soumise.') })
      }
      if (row.statut === 'soumise') {
        acts.push({ id: 'valider', label: 'Valider', icon: Check,
          onClick: () => act(() => comptaApi.notesFrais.valider(row.id, {}), 'Note validée.') })
        acts.push({ id: 'rejeter', label: 'Rejeter', icon: X,
          onClick: () => act(() => comptaApi.notesFrais.rejeter(row.id, {}), 'Note rejetée.') })
      }
      if (row.statut === 'validee') {
        acts.push({ id: 'rembourser', label: 'Rembourser', icon: Send,
          onClick: () => rembourserPrompt((data) => comptaApi.notesFrais.rembourser(row.id, data)) })
      }
      if (row.statut === 'remboursee') {
        acts.push({ id: 'recu', label: 'Reçu PDF', icon: Download,
          onClick: () => download(() => comptaApi.notesFrais.recuPdf(row.id),
            `recu_note_frais_${row.reference || row.id}.pdf`) })
      }
      acts.push({ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) })
      return acts
    }
    if (tab === 'rapportsNotesFrais') {
      const acts = []
      if (row.statut === 'brouillon') {
        acts.push({ id: 'soumettre', label: 'Soumettre', icon: Send,
          onClick: () => act(() => comptaApi.rapportsNotesFrais.soumettre(row.id), 'Rapport soumis.') })
      }
      if (row.statut === 'soumis') {
        acts.push({ id: 'valider', label: 'Valider', icon: Check,
          onClick: () => act(() => comptaApi.rapportsNotesFrais.valider(row.id), 'Rapport validé.') })
      }
      if (row.statut === 'valide') {
        acts.push({ id: 'rembourser', label: 'Rembourser', icon: Send,
          onClick: () => rembourserPrompt((data) => comptaApi.rapportsNotesFrais.rembourser(row.id, data)) })
      }
      if (row.statut === 'rembourse') {
        acts.push({ id: 'recu', label: 'Reçu PDF', icon: Download,
          onClick: () => download(() => comptaApi.rapportsNotesFrais.recuPdf(row.id),
            `recu_rapport_note_frais_${row.reference || row.id}.pdf`) })
      }
      return acts
    }
    if (tab === 'indemnitesChantier') {
      const acts = []
      if (row.statut === 'brouillon' || row.statut === 'rejetee') {
        acts.push({ id: 'soumettre', label: 'Soumettre', icon: Send,
          onClick: () => act(() => comptaApi.indemnitesChantier.soumettre(row.id), 'Indemnité soumise.') })
      }
      if (row.statut === 'soumise') {
        acts.push({ id: 'valider', label: 'Valider', icon: Check,
          onClick: () => act(() => comptaApi.indemnitesChantier.valider(row.id, {}), 'Indemnité validée.') })
        acts.push({ id: 'rejeter', label: 'Rejeter', icon: X,
          onClick: () => act(() => comptaApi.indemnitesChantier.rejeter(row.id, {}), 'Indemnité rejetée.') })
      }
      if (row.statut === 'validee') {
        acts.push({ id: 'rembourser', label: 'Rembourser', icon: Send,
          onClick: () => rembourserPrompt((data) => comptaApi.indemnitesChantier.rembourser(row.id, data)) })
      }
      return acts
    }
    return [{ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) }]
  }

  const submit = (payload) => {
    const api = RESOURCE[tab]
    return dialog?.row ? api.update(dialog.row.id, payload) : api.create(payload)
  }

  const analyse = async () => {
    try {
      const res = await comptaApi.notesFrais.analyse({ export: 'xlsx' })
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, 'analyse-notes-frais.xlsx')
    } catch {
      toast.error('Analyse indisponible.')
    }
  }

  const singular = useMemo(() => ({
    notesFrais: 'note de frais', rapportsNotesFrais: 'rapport',
    plafondsNotesFrais: 'plafond', baremesIndemnite: 'barème',
    indemnitesChantier: 'indemnité',
  }[tab]), [tab])

  return (
    <div className="page">
      <div className="page-header">
        <h2>Notes de frais & indemnités</h2>
        <div className="page-header-actions">
          {tab === 'notesFrais' && (
            <Button variant="outline" onClick={analyse}>
              <BarChart3 className="size-4" /> Analyse (xlsx)
            </Button>
          )}
          <Button onClick={() => setDialog({ row: null })}>
            <Plus /> Nouveau {singular}
          </Button>
        </div>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet notes de frais" />
      </div>

      <ListShell
        title={TABS.find((t) => t.value === tab).label}
        columns={COLUMNS[tab]}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName={tab}
        emptyTitle="Aucun élément"
        emptyDescription="Rien à afficher pour cet onglet."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? `Modifier le ${singular}` : `Nouveau ${singular}`}
          fields={FIELDS[tab]}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
