import { useCallback, useEffect, useState } from 'react'
import { Plus, Landmark } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import { useHasPermission } from '../../../hooks/useHasPermission'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   WIR280 / WIR279 (XACC14) — Emprunts & crédits-bails contractés par la
   société.
   ----------------------------------------------------------------------------
   Le modèle, le tableau d'amortissement (annuité constante) et le posting au
   grand livre existaient depuis WIR279 côté services/ViewSet, sans AUCUN
   écran : rien n'était atteignable hors admin Django. À ne pas confondre avec
   `ComparateursPage`/`comparateurFinancement` (le financement proposé au
   CLIENT sur un devis) : ici la société elle-même est l'emprunteuse.

   Le tableau d'amortissement (`AmortissementDialog`) est généré côté SERVEUR
   (`generer-tableau/`, idempotent tant qu'aucune échéance n'est postée,
   refusé 400 sinon) ; les montants affichés sont ceux renvoyés par le
   serveur, jamais recalculés ici. « Comptabiliser l'échéance » (poster au
   grand livre : 1481/1671 débit, 6311 débit, 5141 crédit) est gardé par la
   permission `compta_saisir` — même code que `HasPermissionOrLegacy
   ('compta_saisir')` côté serveur (`EcheanceEmpruntViewSet.get_permissions`).
   ========================================================================== */

const compteCapitalAsync = () => comptaApi.comptes.list({ page_size: 500 }).then((res) => {
  const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
  return list
    .filter((c) => String(c.numero || '').startsWith('1'))
    .map((c) => ({ value: c.id, label: `${c.numero} — ${c.intitule || c.libelle || ''}` }))
})
const compteInteretsAsync = () => comptaApi.comptes.list({ page_size: 500 }).then((res) => {
  const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
  return list
    .filter((c) => String(c.numero || '').startsWith('6'))
    .map((c) => ({ value: c.id, label: `${c.numero} — ${c.intitule || c.libelle || ''}` }))
})
const compteTresorerieAsync = () => comptaApi.tresorerie.list().then((res) => {
  const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
  return list.map((c) => ({ value: c.id, label: c.libelle || c.intitule || `Compte #${c.id}` }))
})

const FIELDS = [
  { name: 'reference', label: 'Référence' },
  // `Emprunt.banque` est `blank=True` côté modèle (pas obligatoire au sens
  // serveur) — l'astérisque `required` reste réservé aux champs réellement
  // exigés (capital, durée, date de départ).
  { name: 'banque', label: 'Banque / bailleur' },
  { name: 'type_financement', label: 'Type', options: [
    { value: 'emprunt', label: 'Emprunt bancaire' },
    { value: 'leasing', label: 'Crédit-bail / leasing' },
  ] },
  { name: 'capital', label: 'Capital emprunté (MAD)', type: 'number', required: true },
  { name: 'taux_annuel', label: 'Taux annuel (%)', type: 'number' },
  { name: 'duree_mois', label: 'Durée (mois)', type: 'number', required: true },
  { name: 'date_debut', label: 'Date de départ', type: 'date', required: true },
  { name: 'compte_capital', label: 'Compte de capital restant dû (classe 1)', async: compteCapitalAsync },
  { name: 'compte_interets', label: 'Compte de charges financières (classe 6)', async: compteInteretsAsync },
  { name: 'compte_tresorerie', label: 'Compte de trésorerie (payeur)', async: compteTresorerieAsync },
]

function messageErreur(err, repli) {
  const d = err?.response?.data
  return typeof d === 'string' ? d : (d?.detail || repli)
}

function AmortissementDialog({ emprunt, onClose, onChanged }) {
  const [echeances, setEcheances] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [posting, setPosting] = useState(null)
  const canSaisir = useHasPermission('compta_saisir')

  const charger = useCallback(() => {
    setLoading(true)
    comptaApi.echeancesEmprunt.list({ emprunt: emprunt.id })
      .then((res) => setEcheances(Array.isArray(res.data) ? res.data : (res.data?.results || [])))
      .catch(() => setEcheances([]))
      .finally(() => setLoading(false))
  }, [emprunt.id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture
  useEffect(() => { charger() }, [charger])

  const genererTableau = async () => {
    setGenerating(true)
    try {
      const res = await comptaApi.emprunts.genererTableau(emprunt.id)
      setEcheances(res.data?.echeances || [])
      toast.success(`Tableau d'amortissement généré (${res.data?.nb_echeances ?? 0} échéance(s)).`)
      onChanged?.()
    } catch (err) {
      toast.error(messageErreur(err, "Génération du tableau impossible."))
    } finally {
      setGenerating(false)
    }
  }

  const comptabiliser = async (echeance) => {
    setPosting(echeance.id)
    try {
      await comptaApi.echeancesEmprunt.poster(echeance.id)
      toast.success(`Échéance ${echeance.numero} comptabilisée.`)
      charger()
      onChanged?.()
    } catch (err) {
      toast.error(messageErreur(err, "Comptabilisation de l'échéance impossible."))
    } finally {
      setPosting(null)
    }
  }

  const colonnes = [
    { key: 'numero', label: 'Rang', sortValue: (e) => Number(e.numero) || 0, cell: (e) => e.numero },
    { key: 'date_echeance', label: 'Date', cell: (e) => formatDate(e.date_echeance) },
    { key: 'principal', label: 'Principal', align: 'right', numeric: true,
      sortValue: (e) => Number(e.principal) || 0, cell: (e) => formatMAD(e.principal) },
    { key: 'interets', label: 'Intérêts', align: 'right', numeric: true,
      sortValue: (e) => Number(e.interets) || 0, cell: (e) => formatMAD(e.interets) },
    { key: 'mensualite', label: 'Mensualité', align: 'right', numeric: true,
      sortValue: (e) => Number(e.mensualite) || 0, cell: (e) => formatMAD(e.mensualite) },
    { key: 'capital_restant_du', label: 'Capital restant dû', align: 'right', numeric: true,
      sortValue: (e) => Number(e.capital_restant_du) || 0, cell: (e) => formatMAD(e.capital_restant_du) },
    { key: 'statut', label: 'Statut', sortValue: (e) => (e.posted ? 1 : 0),
      cell: (e) => (e.posted ? 'Comptabilisée' : 'À comptabiliser') },
  ]
  if (canSaisir) {
    colonnes.push({
      key: 'actions',
      label: 'Actions',
      cell: (e) => (e.posted ? '—' : (
        <Button
          size="sm" variant="outline" disabled={posting === e.id}
          onClick={() => comptabiliser(e)}
        >
          {posting === e.id ? 'Comptabilisation…' : "Comptabiliser l'échéance"}
        </Button>
      )),
    })
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Tableau d'amortissement — {emprunt.reference || emprunt.banque}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Chargement…</p>
        ) : echeances.length === 0 ? (
          <EmptyState
            icon={Landmark}
            title="Aucun tableau généré"
            description="Générez le tableau d'amortissement complet pour cet emprunt."
            action={(
              <Button onClick={genererTableau} disabled={generating}>
                {generating ? 'Génération…' : "Générer le tableau d'amortissement"}
              </Button>
            )}
          />
        ) : (
          <>
            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={genererTableau} disabled={generating}>
                {generating ? 'Régénération…' : 'Régénérer le tableau'}
              </Button>
            </div>
            <ComptaTable
              aria-label="Tableau d'amortissement"
              exportName={`amortissement-${emprunt.reference || emprunt.id}`}
              rows={echeances}
              getRowKey={(e) => e.id}
              columns={colonnes}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default function EmpruntsPage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [detail, setDetail] = useState(null)
  const list = useComptaList(comptaApi.emprunts.list, undefined)

  const submit = useCallback((payload) => comptaApi.emprunts.create(payload), [])

  const onSaved = () => {
    toast.success('Emprunt / crédit-bail enregistré.')
    list.reload()
  }

  const columns = [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'banque', header: 'Banque / bailleur', accessor: (r) => r.banque || '—' },
    { id: 'type', header: 'Type', accessor: (r) => r.type_financement_display || r.type_financement || '—' },
    { id: 'capital', header: 'Capital', accessor: (r) => Number(r.capital) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'taux', header: 'Taux annuel', accessor: (r) => `${r.taux_annuel ?? '—'} %`, searchable: false },
    { id: 'encours', header: 'Encours restant dû', accessor: (r) => Number(r.encours_restant_du) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'echeances', header: 'Échéances postées', searchable: false,
      accessor: (r) => `${r.nb_echeances_postees ?? 0}/${r.nb_echeances ?? 0}` },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Emprunts et crédits-bails</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialogOpen(true)}>
            <Plus /> Nouvel emprunt / crédit-bail
          </Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Emprunts et crédits-bails"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        onRowClick={(row) => setDetail(row)}
        exportName="emprunts-credits-bails"
        emptyTitle="Aucun emprunt ni crédit-bail"
        emptyDescription="Un financement contracté par la société (banque ou leasing)."
      />

      {dialogOpen && (
        <CrudDialog
          open
          onClose={() => setDialogOpen(false)}
          title="Nouvel emprunt / crédit-bail"
          fields={FIELDS}
          onSubmit={submit}
          onSaved={onSaved}
        />
      )}

      {detail && (
        <AmortissementDialog
          emprunt={detail}
          onClose={() => setDetail(null)}
          onChanged={list.reload}
        />
      )}
    </div>
  )
}
