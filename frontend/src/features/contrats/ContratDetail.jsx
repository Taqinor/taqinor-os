import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import contratsApi from '../../api/contratsApi'
import { Button, Card, EmptyState, Skeleton, Badge, toast } from '../../ui'
import { DetailShell } from '../../ui/module'
import { formatMAD, formatDate, formatDateTime } from '../../lib/format'
import { StatutContrat, StatutResiliation } from './status'
import StateMachine from './StateMachine'
import SimpleTable from './SimpleTable'

/* ============================================================================
   UX34 (détail) — Fiche cycle de vie d'un contrat.
   ----------------------------------------------------------------------------
   DetailShell UX1 : machine d'états lisible, onglets Parties / Liens / Versions
   / Avenants / Résiliations, chatter (historique) en panneau latéral. Montants
   client-facing via formatMAD (jamais de prix d'achat/marge).
   ========================================================================== */

export default function ContratDetail() {
  const { id } = useParams()
  const [contrat, setContrat] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [parties, setParties] = useState([])
  const [liens, setLiens] = useState([])
  const [versions, setVersions] = useState([])
  const [avenants, setAvenants] = useState([])
  const [resiliations, setResiliations] = useState([])
  const [historique, setHistorique] = useState([])

  const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))

  const load = () => {
    setLoading(true)
    setError(null)
    contratsApi
      .getContrat(id)
      .then((res) => setContrat(res.data))
      .catch(() => setError('Contrat introuvable.'))
      .finally(() => setLoading(false))
    contratsApi.getParties({ contrat: id }).then((r) => setParties(listData(r))).catch(() => {})
    contratsApi.getLiens(id).then((r) => setLiens(Array.isArray(r.data) ? r.data : [])).catch(() => {})
    contratsApi.getVersions({ contrat: id }).then((r) => setVersions(listData(r))).catch(() => {})
    contratsApi.getAvenants({ contrat: id }).then((r) => setAvenants(listData(r))).catch(() => {})
    contratsApi.getResiliations({ contrat: id }).then((r) => setResiliations(listData(r))).catch(() => {})
    contratsApi.getHistorique(id).then((r) => setHistorique(Array.isArray(r.data) ? r.data : [])).catch(() => {})
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetch only when id changes
  }, [id])

  const genererPdf = async () => {
    try {
      const res = await contratsApi.getPdf(id)
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch { toast.error('PDF indisponible.') }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (error || !contrat) {
    return (
      <EmptyState
        title="Contrat introuvable"
        description={error || 'Ce contrat n’existe pas ou n’est pas accessible.'}
        action={<Button variant="outline" onClick={load}>Réessayer</Button>}
      />
    )
  }

  const partiesTab = (
    <SimpleTable
      emptyText="Aucune partie enregistrée."
      rows={parties}
      columns={[
        { header: 'Type', cell: (p) => p.type_partie_display || p.type_partie },
        { header: 'Nom', cell: (p) => <span className="font-medium">{p.nom}</span> },
        { header: 'Fonction', cell: (p) => p.fonction || '—' },
        { header: 'Email', cell: (p) => p.email || '—' },
        { header: 'Téléphone', cell: (p) => p.telephone || '—' },
      ]}
    />
  )

  const liensTab = (
    <SimpleTable
      emptyText="Aucun lien vers un devis / lead / installation."
      rows={liens}
      columns={[
        { header: 'Type', cell: (l) => l.type_cible_display || l.type_cible },
        { header: 'Cible', cell: (l) => <span className="font-medium">{l.libelle || `#${l.cible_id}`}</span> },
        { header: 'Source', cell: (l) => <Badge tone={l.source === 'live' ? 'success' : 'neutral'}>{l.source || 'stored'}</Badge> },
      ]}
    />
  )

  const versionsTab = (
    <SimpleTable
      emptyText="Aucune version figée."
      rows={versions}
      columns={[
        { header: 'Version', cell: (v) => <span className="font-mono">v{v.version}</span> },
        { header: 'Motif', cell: (v) => v.motif || '—' },
        { header: 'Auteur', cell: (v) => v.cree_par_username || '—' },
        { header: 'Créée le', cell: (v) => formatDateTime(v.cree_le), align: 'right' },
      ]}
    />
  )

  const avenantsTab = (
    <SimpleTable
      emptyText="Aucun avenant."
      rows={avenants}
      columns={[
        { header: 'N°', cell: (a) => <span className="font-mono">#{a.numero}</span> },
        { header: 'Objet', cell: (a) => <span className="font-medium">{a.objet}</span> },
        { header: 'Effet', cell: (a) => (a.date_effet ? formatDate(a.date_effet) : '—') },
        { header: 'Delta', cell: (a) => (a.montant_delta != null ? formatMAD(a.montant_delta) : '—'), align: 'right' },
      ]}
    />
  )

  const resiliationsTab = (
    <SimpleTable
      emptyText="Aucune résiliation."
      rows={resiliations}
      columns={[
        { header: 'Statut', cell: (r) => <StatutResiliation status={r.statut} /> },
        { header: 'Motif', cell: (r) => r.motif || '—' },
        { header: 'Effet', cell: (r) => (r.date_effet ? formatDate(r.date_effet) : '—') },
        { header: 'Solde', cell: (r) => (r.solde != null ? formatMAD(r.solde) : '—'), align: 'right' },
      ]}
    />
  )

  const infosTab = (
    <Card className="p-4">
      <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
        <Info label="Type" value={contrat.type_contrat_display || contrat.type_contrat} />
        <Info label="Confidentialité" value={contrat.confidentialite_display || contrat.confidentialite} />
        <Info label="Montant" value={contrat.montant != null ? formatMAD(contrat.montant) : '—'} />
        <Info label="Devise" value={contrat.devise || '—'} />
        <Info label="Début" value={contrat.date_debut ? formatDate(contrat.date_debut) : '—'} />
        <Info label="Fin" value={contrat.date_fin ? formatDate(contrat.date_fin) : '—'} />
        <Info label="Préavis (jours)" value={contrat.preavis_jours ?? '—'} />
        <Info label="Tacite reconduction" value={contrat.tacite_reconduction ? 'Oui' : 'Non'} />
        <Info label="Renouvellements" value={contrat.nb_renouvellements ?? 0} />
        <Info
          label="Jours avant échéance"
          value={contrat.jours_avant_echeance != null ? `${contrat.jours_avant_echeance} j` : '—'}
        />
      </dl>
    </Card>
  )

  const activity = (
    <Card className="p-4">
      <h3 className="mb-3 font-display text-base font-semibold">Historique</h3>
      {historique.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune activité.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {historique.map((h) => (
            <li key={h.id} className="border-l-2 border-border pl-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{h.type_display || h.type}</span>
                <span className="text-xs text-muted-foreground">{formatDateTime(h.date_creation)}</span>
              </div>
              {h.field && (
                <p className="text-xs text-muted-foreground">
                  {h.field} : {h.old_value || '∅'} → {h.new_value || '∅'}
                </p>
              )}
              {h.message && <p className="mt-0.5">{h.message}</p>}
              {h.auteur_nom && <p className="text-xs text-muted-foreground">par {h.auteur_nom}</p>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )

  return (
    <DetailShell
      title={contrat.reference || `Contrat #${contrat.id}`}
      subtitle={contrat.objet}
      status={contrat.statut}
      statusPill={StatutContrat}
      backTo="/contrats"
      backLabel="Retour aux contrats"
      actions={<Button variant="outline" onClick={genererPdf}>PDF interne</Button>}
      activity={activity}
      tabs={[
        { value: 'infos', label: 'Informations', content: (
          <div className="flex flex-col gap-4">
            <Card className="p-4">
              <h3 className="mb-3 font-display text-sm font-semibold text-muted-foreground">Cycle de vie</h3>
              <StateMachine statut={contrat.statut} />
            </Card>
            {infosTab}
          </div>
        ) },
        { value: 'parties', label: 'Parties', count: parties.length, content: partiesTab },
        { value: 'liens', label: 'Liens', count: liens.length, content: liensTab },
        { value: 'versions', label: 'Versions', count: versions.length, content: versionsTab },
        { value: 'avenants', label: 'Avenants', count: avenants.length, content: avenantsTab },
        { value: 'resiliations', label: 'Résiliations', count: resiliations.length, content: resiliationsTab },
      ]}
    />
  )
}

function Info({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}
