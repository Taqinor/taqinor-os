import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Printer } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import {
  Button, Card, EmptyState, Skeleton, Badge, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea,
} from '../../ui'
import { RecordShell } from '../../ui/module'
import { formatMAD, formatDate, formatDateTime } from '../../lib/format'
import { StatutContrat, StatutResiliation, CONTRAT_STATUS } from './status'
import StateMachine from './StateMachine'
import SimpleTable from './SimpleTable'
import { openPdfInGesture } from '../../utils/pdfBlob'

/* ============================================================================
   UX34 (détail) — Fiche cycle de vie d'un contrat + actions du cycle de vie.
   ----------------------------------------------------------------------------
   DetailShell UX1 : machine d'états lisible + barre d'actions gardées
   (changer-statut — CONTRAT12), onglets Parties / Liens / Signatures
   (CONTRAT16-17) / Approbation (CONTRAT13-14) / Versions / Avenants (CONTRAT24)
   / Résiliations (CONTRAT25), chatter (historique + note — CONTRAT15) en
   panneau latéral. Renouveler (CONTRAT23). Montants client-facing via formatMAD
   (jamais de prix d'achat/marge).
   ========================================================================== */

const ROLES_SIGNATURE = [
  { value: 'client', label: 'Client' },
  { value: 'prestataire', label: 'Prestataire' },
  { value: 'temoin', label: 'Témoin' },
]

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

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
  const [signatures, setSignatures] = useState([])
  const [etapes, setEtapes] = useState([])
  const [suivants, setSuivants] = useState([])

  const [note, setNote] = useState('')
  const [notePending, setNotePending] = useState(false)
  const [dialog, setDialog] = useState(null) // 'signer' | 'renouveler' | 'avenant' | 'resilier'
  const [busy, setBusy] = useState(false)

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
    contratsApi.getSignatures(id).then((r) => setSignatures(Array.isArray(r.data) ? r.data : [])).catch(() => {})
    contratsApi.getEtapesApprobation(id).then((r) => setEtapes(Array.isArray(r.data) ? r.data : [])).catch(() => {})
    contratsApi.getStatutsSuivants(id)
      .then((r) => setSuivants(r.data?.suivants ?? []))
      .catch(() => setSuivants([]))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetch only when id changes
  }, [id])

  // VX48 — onglet pré-ouvert SYNCHRONE avant l'await (Safari iOS bloque
  // silencieusement un window.open() post-await).
  const genererPdf = async () => {
    const pending = openPdfInGesture()
    try {
      const res = await contratsApi.getPdf(id)
      const blob = new Blob([res.data], { type: 'application/pdf' })
      if (!pending.deliver(blob, `contrat-${id}.pdf`)) {
        toast.error('Ouverture bloquée par le navigateur.')
      }
    } catch { toast.error('PDF indisponible.') }
  }

  // CONTRAT12 — transition de statut gardée.
  const changerStatut = async (statut) => {
    setBusy(true)
    try {
      await contratsApi.changerStatut(id, statut)
      toast.success(`Statut : ${CONTRAT_STATUS[statut]?.label || statut}`)
      load()
    } catch (e) {
      toast.error(errMsg(e, 'Transition refusée.'))
    } finally {
      setBusy(false)
    }
  }

  // CONTRAT15 — note manuelle sur le chatter.
  const ajouterNote = async () => {
    const msg = note.trim()
    if (!msg) return
    setNotePending(true)
    try {
      await contratsApi.noter(id, msg)
      setNote('')
      contratsApi.getHistorique(id).then((r) => setHistorique(Array.isArray(r.data) ? r.data : [])).catch(() => {})
    } catch (e) {
      toast.error(errMsg(e, 'Note non enregistrée.'))
    } finally {
      setNotePending(false)
    }
  }

  // CONTRAT13-14 — approbation interne.
  const lancerApprobation = async () => {
    setBusy(true)
    try {
      const r = await contratsApi.lancerApprobation(id)
      const n = Array.isArray(r.data) ? r.data.length : 0
      toast.success(n ? `Workflow lancé (${n} étape(s)).` : 'Aucune règle ne couvre ce contrat.')
      load()
    } catch (e) {
      toast.error(errMsg(e, 'Impossible de lancer l’approbation.'))
    } finally {
      setBusy(false)
    }
  }

  const deciderEtape = async (etapeId, approuver) => {
    setBusy(true)
    try {
      if (approuver) await contratsApi.approuverEtape(id, etapeId)
      else await contratsApi.rejeterEtape(id, etapeId)
      toast.success(approuver ? 'Étape approuvée.' : 'Étape rejetée.')
      load()
    } catch (e) {
      toast.error(errMsg(e, 'Décision refusée.'))
    } finally {
      setBusy(false)
    }
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
        // WIR98 — contact canonique lié (référentiel contacts) quand la
        // partie provient d'un contact plutôt que de texte libre.
        { header: 'Contact lié', cell: (p) => p.contact_nom || '—' },
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

  // CONTRAT16-17 — signatures électroniques in-app.
  const signaturesTab = (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Signature électronique dactylographiée (loi 53-05). Quand le client ET
          le prestataire ont signé, le contrat bascule en « Signé » puis « Actif ».
        </p>
        <Button size="sm" onClick={() => setDialog('signer')}>Signer</Button>
      </div>
      <SimpleTable
        emptyText="Aucune signature."
        rows={signatures}
        columns={[
          { header: 'Signataire', cell: (s) => <span className="font-medium">{s.signataire_nom}</span> },
          { header: 'Rôle', cell: (s) => s.role_signataire_display || s.role_signataire },
          { header: 'Méthode', cell: (s) => s.methode_display || s.methode },
          { header: 'Signé le', cell: (s) => formatDateTime(s.date_signature), align: 'right' },
        ]}
      />
    </div>
  )

  // CONTRAT13-14 — workflow d'approbation interne.
  const approbationTab = (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Approbation interne selon la règle la plus spécifique (montant + type).
          Ne change aucun statut du contrat.
        </p>
        {etapes.length === 0 && (
          <Button size="sm" onClick={lancerApprobation} disabled={busy}>
            Lancer l’approbation
          </Button>
        )}
      </div>
      <SimpleTable
        emptyText="Aucune étape d’approbation. Lancez le workflow."
        rows={etapes}
        columns={[
          { header: 'Niveau', cell: (e) => <span className="font-mono">N{e.niveau}</span> },
          { header: 'Palier', cell: (e) => e.niveau_approbation_display || e.niveau_approbation },
          { header: 'Statut', cell: (e) => <Badge tone={e.statut === 'approuve' ? 'success' : e.statut === 'rejete' ? 'danger' : 'neutral'}>{e.statut_display || e.statut}</Badge> },
          { header: 'Décidée le', cell: (e) => (e.decision_le ? formatDateTime(e.decision_le) : '—') },
          {
            header: 'Action',
            align: 'right',
            cell: (e) => (e.statut === 'en_attente' ? (
              <span className="flex justify-end gap-1.5">
                <Button size="sm" variant="outline" disabled={busy} onClick={() => deciderEtape(e.id, true)}>Approuver</Button>
                <Button size="sm" variant="outline" disabled={busy} onClick={() => deciderEtape(e.id, false)}>Rejeter</Button>
              </span>
            ) : '—'),
          },
        ]}
      />
    </div>
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
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" onClick={() => setDialog('avenant')}>Créer un avenant</Button>
      </div>
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
    </div>
  )

  const resiliationsTab = (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" onClick={() => setDialog('resilier')}>Résilier le contrat</Button>
      </div>
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
    </div>
  )

  const infosTab = (
    <Card className="p-4">
      <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
        {/* WIR77 — nom du client lié (résolu cross-app côté serveur). */}
        <Info label="Client" value={contrat.client_nom || '—'} />
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
      {/* CONTRAT15 — composeur de note. */}
      <div className="mb-4 flex flex-col gap-2">
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ajouter une note…"
          rows={2}
          aria-label="Nouvelle note"
        />
        <Button size="sm" className="self-end" disabled={notePending || !note.trim()} onClick={ajouterNote}>
          {notePending ? 'Envoi…' : 'Noter'}
        </Button>
      </div>
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

  // Barre d'actions du cycle de vie (CONTRAT12/23) + PDF.
  const actions = (
    <>
      {suivants.map((s) => (
        <Button key={s} size="sm" variant="outline" disabled={busy} onClick={() => changerStatut(s)}>
          → {CONTRAT_STATUS[s]?.label || s}
        </Button>
      ))}
      <Button size="sm" variant="outline" onClick={() => setDialog('renouveler')}>Renouveler</Button>
      {/* VX246(b) — impression navigateur (print.css). Distincte du « PDF interne »
          WeasyPrint ci-dessous, qu'elle ne remplace pas. */}
      <Button size="sm" variant="outline" onClick={() => window.print()}>
        <Printer size={15} strokeWidth={1.75} aria-hidden="true" /> Imprimer
      </Button>
      <Button variant="outline" onClick={genererPdf}>PDF interne</Button>
    </>
  )

  return (
    <>
      {/* ARC46 — RecordShell (pendant détail de ListShell) ; drop-in de
          DetailShell : mêmes props (dont le slot chatter via `activity`),
          aucune refonte visuelle. */}
      <RecordShell
        title={contrat.reference || `Contrat #${contrat.id}`}
        subtitle={contrat.objet}
        status={contrat.statut}
        statusPill={StatutContrat}
        backTo="/contrats"
        backLabel="Retour aux contrats"
        actions={actions}
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
          { value: 'signatures', label: 'Signatures', count: signatures.length, content: signaturesTab },
          { value: 'approbation', label: 'Approbation', count: etapes.length, content: approbationTab },
          { value: 'liens', label: 'Liens', count: liens.length, content: liensTab },
          { value: 'versions', label: 'Versions', count: versions.length, content: versionsTab },
          { value: 'avenants', label: 'Avenants', count: avenants.length, content: avenantsTab },
          { value: 'resiliations', label: 'Résiliations', count: resiliations.length, content: resiliationsTab },
        ]}
      />

      {dialog === 'signer' && (
        <SignerDialog id={id} onClose={() => setDialog(null)} onDone={() => { setDialog(null); load() }} />
      )}
      {dialog === 'renouveler' && (
        <RenouvelerDialog id={id} onClose={() => setDialog(null)} onDone={() => { setDialog(null); load() }} />
      )}
      {dialog === 'avenant' && (
        <AvenantDialog id={id} onClose={() => setDialog(null)} onDone={() => { setDialog(null); load() }} />
      )}
      {dialog === 'resilier' && (
        <ResilierDialog id={id} onClose={() => setDialog(null)} onDone={() => { setDialog(null); load() }} />
      )}
    </>
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

/* -------------------- Dialogues d'action -------------------- */

function SignerDialog({ id, onClose, onDone }) {
  const [nom, setNom] = useState('')
  const [role, setRole] = useState('client')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!nom.trim()) { setErr('Le nom du signataire est requis (loi 53-05).'); return }
    setSaving(true)
    setErr(null)
    try {
      const r = await contratsApi.signer(id, { signataire_nom: nom.trim(), role_signataire: role })
      if (r.data?.contrat_actif) toast.success('Signé — contrat activé.')
      else if (r.data?.contrat_signe) toast.success('Signé par toutes les parties.')
      else toast.success('Signature enregistrée.')
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Signature refusée.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Signer le contrat</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sig-nom">Nom du signataire</Label>
            <Input id="sig-nom" value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Nom dactylographié" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sig-role">Rôle</Label>
            <select
              id="sig-role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {ROLES_SIGNATURE.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Signature…' : 'Signer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function RenouvelerDialog({ id, onClose, onDone }) {
  const [dureeMois, setDureeMois] = useState('')
  const [nouvelleDateFin, setNouvelleDateFin] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErr(null)
    const data = {}
    if (nouvelleDateFin) data.nouvelle_date_fin = nouvelleDateFin
    if (dureeMois) data.duree_mois = Number(dureeMois)
    try {
      await contratsApi.renouveler(id, data)
      toast.success('Contrat renouvelé.')
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Renouvellement refusé.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Renouveler le contrat</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <p className="text-sm text-muted-foreground">
            Renseignez une nouvelle date de fin OU un nombre de mois à ajouter à la fin courante.
          </p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ren-fin">Nouvelle date de fin</Label>
            <Input id="ren-fin" type="date" value={nouvelleDateFin} onChange={(e) => setNouvelleDateFin(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ren-duree">Durée (mois)</Label>
            <Input id="ren-duree" type="number" min="1" step="any" value={dureeMois} onChange={(e) => setDureeMois(e.target.value)} placeholder="ex. 12" />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Renouvellement…' : 'Renouveler'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AvenantDialog({ id, onClose, onDone }) {
  const [objet, setObjet] = useState('')
  const [description, setDescription] = useState('')
  const [dateEffet, setDateEffet] = useState('')
  const [montantDelta, setMontantDelta] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!objet.trim()) { setErr("L'objet de l'avenant est requis."); return }
    setSaving(true)
    setErr(null)
    const data = { objet: objet.trim() }
    if (description.trim()) data.description = description.trim()
    if (dateEffet) data.date_effet = dateEffet
    if (montantDelta !== '') data.montant_delta = Number(montantDelta)
    try {
      await contratsApi.creerAvenant(id, data)
      toast.success('Avenant créé.')
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, "Avenant refusé."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Créer un avenant</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="av-objet">Objet</Label>
            <Input id="av-objet" value={objet} onChange={(e) => setObjet(e.target.value)} placeholder="Titre court de l'amendement" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="av-desc">Description</Label>
            <Textarea id="av-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="av-effet">Date d’effet</Label>
              <Input id="av-effet" type="date" value={dateEffet} onChange={(e) => setDateEffet(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="av-delta">Variation du montant</Label>
              <Input id="av-delta" type="number" step="any" value={montantDelta} onChange={(e) => setMontantDelta(e.target.value)} placeholder="ex. 5000" />
            </div>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer l’avenant'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ResilierDialog({ id, onClose, onDone }) {
  const [motif, setMotif] = useState('')
  const [dateEffet, setDateEffet] = useState('')
  const [preavisJours, setPreavisJours] = useState('')
  const [solde, setSolde] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErr(null)
    const data = {}
    if (motif.trim()) data.motif = motif.trim()
    if (dateEffet) data.date_effet = dateEffet
    if (preavisJours !== '') data.preavis_jours = Number(preavisJours)
    if (solde !== '') data.solde = Number(solde)
    try {
      await contratsApi.resilier(id, data)
      toast.success('Contrat résilié.')
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Résiliation refusée.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Résilier le contrat</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="res-motif">Motif</Label>
            <Textarea id="res-motif" rows={2} value={motif} onChange={(e) => setMotif(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="res-effet">Date d’effet</Label>
              <Input id="res-effet" type="date" value={dateEffet} onChange={(e) => setDateEffet(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="res-preavis">Préavis (jours)</Label>
              <Input id="res-preavis" type="number" step="any" value={preavisJours} onChange={(e) => setPreavisJours(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="res-solde">Solde de tout compte</Label>
            <Input id="res-solde" type="number" step="any" value={solde} onChange={(e) => setSolde(e.target.value)} placeholder="Optionnel" />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" variant="destructive" disabled={saving}>{saving ? 'Résiliation…' : 'Résilier'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
