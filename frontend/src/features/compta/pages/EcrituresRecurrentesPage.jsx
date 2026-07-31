import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import { Plus, PlayCircle, RefreshCw } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Segmented, Card, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   WIR107 / XACC8 — Modèles d'écriture & écritures récurrentes.
   ----------------------------------------------------------------------------
   `ModeleEcriture` / `LigneModeleEcriture` / `AbonnementEcriture` existaient en
   base et n'étaient pilotés QUE par la commande planifiée
   `generer_ecritures_recurrentes` (aucune route REST, aucun écran) : impossible
   de créer un loyer récurrent depuis l'ERP. WIR107 ajoute les routes
   (`/compta/modeles-ecriture/`, `/lignes-modele-ecriture/`,
   `/abonnements-ecriture/`) et cet écran.

   Garde-fou métier repris tel quel du service : toute génération naît en
   BROUILLON (relecture humaine avant validation) et la génération des
   échéances dues est IDEMPOTENTE par période — rejouer le bouton ne crée
   jamais de doublon.
   ========================================================================== */

const StatutAbonnement = statusPill({
  actif: { label: 'Actif', tone: 'success' },
  inactif: { label: 'Inactif', tone: 'neutral' },
})

function messageErreur(err, repli) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  const premier = d?.detail || Object.values(d || {})?.[0]
  return (Array.isArray(premier) ? premier[0] : premier) || repli
}

function unwrapList(res) {
  const data = res?.data
  return Array.isArray(data) ? data : (data?.results || [])
}

// Options « modèle d'écriture » (partagées par les onglets Lignes/Abonnements).
function useModeles() {
  const [modeles, setModeles] = useState([])
  const charger = useCallback(() => {
    let alive = true
    comptaApi.modelesEcriture.list({ page_size: 200 })
      .then((res) => { if (alive) setModeles(unwrapList(res)) })
      .catch(() => { if (alive) setModeles([]) })
    return () => { alive = false }
  }, [])
  useEffect(() => charger(), [charger])
  return { modeles, recharger: charger }
}

const journauxAsync = () => comptaApi.journaux.list({ page_size: 200 })
  .then((res) => unwrapList(res).map((j) => ({
    value: j.id, label: `${j.code || j.type || ''} — ${j.libelle}`.trim(),
  })))

const comptesAsync = () => comptaApi.comptes.list({ page_size: 500 })
  .then((res) => unwrapList(res).map((c) => ({
    value: c.id, label: `${c.numero} — ${c.libelle}`,
  })))

// ── Onglet 1 — Modèles d'écriture ──
function ModelesPanel({ modelesHook }) {
  const [dialog, setDialog] = useState(null)
  const [generer, setGenerer] = useState(null)
  const [derniere, setDerniere] = useState(null)
  const list = useComptaList(comptaApi.modelesEcriture.list, undefined)

  const recharger = () => { list.reload(); modelesHook.recharger() }

  const colonnes = [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'journal', header: 'Journal', accessor: (r) => r.journal_libelle || r.journal },
    { id: 'lignes', header: 'Lignes', searchable: false,
      accessor: (r) => (r.lignes || []).length },
    { id: 'defaut', header: 'Total par défaut (débit)', align: 'right', numeric: true,
      searchable: false,
      accessor: (r) => (r.lignes || [])
        .filter((l) => l.sens === 'debit')
        .reduce((acc, l) => acc + (Number(l.montant_defaut) || 0), 0),
      cell: (v) => formatMAD(v) },
    { id: 'extourne', header: 'Extourne auto', searchable: false,
      accessor: (r) => (r.extourne_auto ? 'Oui' : 'Non') },
    { id: 'cloture', header: 'Clôture', searchable: false,
      accessor: (r) => (r.cloture ? 'Oui' : 'Non') },
    { id: 'actif', header: 'Actif', searchable: false,
      accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => [
    { id: 'generer', label: 'Générer une écriture', icon: PlayCircle,
      onClick: () => setGenerer(row) },
    { id: 'editer', label: 'Modifier', onClick: () => setDialog({ row }) },
  ]

  const champs = [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'journal', label: 'Journal', required: true, async: journauxAsync },
    { name: 'extourne_auto', label: 'Extourne automatique', options: [
      { value: 'true', label: 'Oui' }, { value: 'false', label: 'Non' }] },
    { name: 'cloture', label: 'Modèle de clôture', options: [
      { value: 'true', label: 'Oui' }, { value: 'false', label: 'Non' }] },
    { name: 'categorie_cloture', label: 'Catégorie de clôture' },
    { name: 'actif', label: 'Actif', options: [
      { value: 'true', label: 'Oui' }, { value: 'false', label: 'Non' }] },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}>
          <Plus /> Nouveau modèle
        </Button>
      </div>
      {derniere && (
        <Card className="p-3 text-sm">
          Écriture <span className="font-mono">{derniere.reference || `#${derniere.ecriture_id}`}</span>
          {' '}créée en <strong>brouillon</strong> — à relire puis valider depuis l’écran Écritures.
        </Card>
      )}
      <ListShell
        title="Modèles d’écriture"
        columns={colonnes}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="modeles-ecriture"
        emptyTitle="Aucun modèle"
        emptyDescription="Créez un modèle (loyer, dotation…) puis ajoutez-lui ses lignes."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier le modèle' : 'Nouveau modèle d’écriture'}
          fields={champs}
          initial={dialog.row}
          onSubmit={(payload) => (dialog.row
            ? comptaApi.modelesEcriture.update(dialog.row.id, payload)
            : comptaApi.modelesEcriture.create(payload))}
          onSaved={recharger}
        />
      )}
      {generer && (
        <CrudDialog
          open
          onClose={() => setGenerer(null)}
          title={`Générer une écriture — ${generer.libelle}`}
          fields={[
            { name: 'date_ecriture', label: 'Date d’écriture', type: 'date', required: true },
            { name: 'libelle', label: 'Libellé (facultatif)' },
          ]}
          onSubmit={(payload) => comptaApi.modelesEcriture.generer(generer.id, payload)
            .then((res) => { setDerniere(res?.data || null); return res })}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── Onglet 2 — Lignes pré-codées d'un modèle ──
function LignesPanel({ modelesHook }) {
  const { modeles } = modelesHook
  const [modele, setModele] = useState('')
  const [dialog, setDialog] = useState(null)
  const params = useMemo(() => (modele ? { modele } : undefined), [modele])
  const list = useComptaList(comptaApi.lignesModeleEcriture.list, params)

  const totaux = useMemo(() => {
    const debit = list.rows.filter((l) => l.sens === 'debit')
      .reduce((acc, l) => acc + (Number(l.montant_defaut) || 0), 0)
    const credit = list.rows.filter((l) => l.sens === 'credit')
      .reduce((acc, l) => acc + (Number(l.montant_defaut) || 0), 0)
    return { debit, credit, ecart: debit - credit }
  }, [list.rows])

  const colonnes = [
    { id: 'ordre', header: 'Ordre', accessor: (r) => r.ordre, searchable: false, width: 80 },
    { id: 'compte', header: 'Compte',
      accessor: (r) => `${r.compte_numero || ''} ${r.compte_libelle || ''}`.trim() || r.compte },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'sens', header: 'Sens', accessor: (r) => r.sens_display || r.sens, searchable: false },
    { id: 'montant', header: 'Montant par défaut', align: 'right', numeric: true,
      searchable: false,
      accessor: (r) => (r.montant_defaut === null || r.montant_defaut === undefined
        ? null : Number(r.montant_defaut)),
      cell: (v) => (v === null ? 'à saisir' : formatMAD(v)) },
  ]

  const champs = [
    { name: 'modele', label: 'Modèle', required: true,
      options: modeles.map((m) => ({ value: m.id, label: m.libelle })) },
    { name: 'compte', label: 'Compte', required: true, async: comptesAsync },
    { name: 'sens', label: 'Sens', required: true, options: [
      { value: 'debit', label: 'Débit' }, { value: 'credit', label: 'Crédit' }] },
    { name: 'libelle', label: 'Libellé' },
    { name: 'montant_defaut', label: 'Montant par défaut', type: 'number' },
    { name: 'ordre', label: 'Ordre', type: 'number' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Modèle</span>
          <select
            aria-label="Modèle d’écriture"
            className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
            value={modele}
            onChange={(e) => setModele(e.target.value)}
          >
            <option value="">Tous</option>
            {modeles.map((m) => (
              <option key={m.id} value={m.id}>{m.libelle}</option>
            ))}
          </select>
        </label>
        <Button size="sm" onClick={() => setDialog({ row: null })}>
          <Plus /> Nouvelle ligne
        </Button>
      </div>
      {modele && (
        <Card className={`p-3 text-sm ${totaux.ecart === 0 ? 'border-success/40 bg-success/5' : 'border-destructive/40 bg-destructive/5'}`}>
          {totaux.ecart === 0
            ? `Modèle équilibré sur les montants par défaut — ${formatMAD(totaux.debit)} au débit comme au crédit.`
            : `Écart de ${formatMAD(Math.abs(totaux.ecart))} entre débit (${formatMAD(totaux.debit)}) et crédit (${formatMAD(totaux.credit)}) : les montants seront à saisir à la génération.`}
        </Card>
      )}
      <ListShell
        title="Lignes pré-codées"
        columns={colonnes}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={(row) => [
          { id: 'editer', label: 'Modifier', onClick: () => setDialog({ row }) },
        ]}
        exportName="lignes-modele-ecriture"
        emptyTitle="Aucune ligne"
        emptyDescription="Ajoutez les lignes (compte / sens / montant par défaut) du modèle."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier la ligne' : 'Nouvelle ligne de modèle'}
          fields={champs}
          initial={dialog.row || (modele ? { modele } : null)}
          onSubmit={(payload) => (dialog.row
            ? comptaApi.lignesModeleEcriture.update(dialog.row.id, payload)
            : comptaApi.lignesModeleEcriture.create(payload))}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── Onglet 3 — Abonnements (écritures récurrentes) ──
function AbonnementsPanel({ modelesHook }) {
  const { modeles } = modelesHook
  const [dialog, setDialog] = useState(null)
  const [resultat, setResultat] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const list = useComptaList(comptaApi.abonnementsEcriture.list, undefined)

  const genererDues = async () => {
    setEnCours(true)
    try {
      const res = await comptaApi.abonnementsEcriture.genererDues()
      setResultat(res?.data || { generees: [], ignorees: [] })
      const n = (res?.data?.generees || []).length
      toast.success(n
        ? `${n} écriture(s) générée(s) en brouillon.`
        : 'Aucune échéance due — rien à générer.')
      list.reload()
    } catch (err) {
      toast.error(messageErreur(err, 'Génération impossible.'))
    } finally {
      setEnCours(false)
    }
  }

  const colonnes = [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || r.modele_libelle || '—' },
    { id: 'modele', header: 'Modèle', accessor: (r) => r.modele_libelle || r.modele },
    { id: 'frequence', header: 'Fréquence',
      accessor: (r) => r.frequence_display || r.frequence, searchable: false },
    { id: 'echeance', header: 'Prochaine échéance', searchable: false,
      accessor: (r) => r.prochaine_echeance, cell: (v) => formatDate(v) },
    { id: 'fin', header: 'Fin', searchable: false,
      accessor: (r) => r.date_fin, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'derniere', header: 'Dernière génération', searchable: false,
      accessor: (r) => r.derniere_generation, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'statut', header: 'Statut', searchable: false,
      accessor: (r) => (r.actif ? 'actif' : 'inactif'),
      cell: (v) => <StatutAbonnement status={v} /> },
  ]

  const champs = [
    { name: 'modele', label: 'Modèle d’écriture', required: true,
      options: modeles.map((m) => ({ value: m.id, label: m.libelle })) },
    { name: 'libelle', label: 'Libellé' },
    { name: 'frequence', label: 'Fréquence', required: true, options: [
      { value: 'mensuelle', label: 'Mensuelle' },
      { value: 'trimestrielle', label: 'Trimestrielle' }] },
    { name: 'prochaine_echeance', label: 'Prochaine échéance', type: 'date', required: true },
    { name: 'date_fin', label: 'Date de fin', type: 'date' },
    { name: 'actif', label: 'Actif', options: [
      { value: 'true', label: 'Oui' }, { value: 'false', label: 'Non' }] },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="outline" size="sm" onClick={genererDues} disabled={enCours}>
          <RefreshCw className="size-4" />
          {enCours ? 'Génération…' : 'Générer les échéances dues'}
        </Button>
        <Button size="sm" onClick={() => setDialog({ row: null })}>
          <Plus /> Nouvel abonnement
        </Button>
      </div>
      {resultat && (
        <Card className="p-3 text-sm">
          <p>
            {(resultat.generees || []).length} écriture(s) générée(s) en brouillon,
            {' '}{(resultat.ignorees || []).length} ignorée(s).
          </p>
          {(resultat.ignorees || []).length > 0 && (
            <ul className="mt-1 list-inside list-disc text-muted-foreground">
              {resultat.ignorees.map((i, idx) => (
                <li key={`${i.abonnement_id}-${i.periode}-${idx}`}>
                  Abonnement {i.abonnement_id} ({i.periode}) : {i.raison}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      <ListShell
        title="Écritures récurrentes"
        columns={colonnes}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={(row) => [
          { id: 'editer', label: 'Modifier', onClick: () => setDialog({ row }) },
        ]}
        exportName="abonnements-ecriture"
        emptyTitle="Aucun abonnement"
        emptyDescription="Adossez un abonnement à un modèle pour générer l’écriture à chaque échéance."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier l’abonnement' : 'Nouvel abonnement'}
          fields={champs}
          initial={dialog.row}
          onSubmit={(payload) => (dialog.row
            ? comptaApi.abonnementsEcriture.update(dialog.row.id, payload)
            : comptaApi.abonnementsEcriture.create(payload))}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

const TABS = [
  { value: 'modeles', label: 'Modèles' },
  { value: 'lignes', label: 'Lignes' },
  { value: 'abonnements', label: 'Abonnements' },
]

export default function EcrituresRecurrentesPage() {
  const [tab, setTab] = useTabParam('modeles')
  const modelesHook = useModeles()

  return (
    <div className="page">
      <div className="page-header">
        <h2>Écritures récurrentes</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab}
          aria-label="Onglet écritures récurrentes" />
      </div>

      {tab === 'modeles' && <ModelesPanel modelesHook={modelesHook} />}
      {tab === 'lignes' && <LignesPanel modelesHook={modelesHook} />}
      {tab === 'abonnements' && <AbonnementsPanel modelesHook={modelesHook} />}
    </div>
  )
}
