import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { LogOut, FileDown, CheckCircle2 } from 'lucide-react'
import { RecordShell } from '../../ui/module'
import {
  DefinitionList, EmptyState, Skeleton, Badge, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, Textarea,
} from '../../ui'
import { formatMAD, formatDate, formatPhoneMA, formatPercent } from '../../lib/format'
import { useSelector } from 'react-redux'
import rhApi from '../../api/rhApi'
import { openPdfInGesture } from '../../utils/pdfBlob'
import { peutVoirSalaires } from './permissions.js'
import ExternalLink from '../../ui/ExternalLink'
import { StatutEmploye, TYPE_CONTRAT_LABELS } from './constants.jsx'

/* ============================================================================
   UX22 + XRH1/4/5/6/15/16 + YHIRE2/ZRH12 — Dossier employé (détail).
   ----------------------------------------------------------------------------
   Onglets : Identité, Contrat, Documents, Rémunération (gated salaires_voir),
   Habilitations, Formations, Intégration (checklist XRH4), Chatter (XRH6).
   En-tête : bouton Sortie (YHIRE2 — désactive le compte + checklist offboarding)
   et téléchargement du certificat de travail (ZRH12) une fois l'employé sorti.
   Rémunération inclut le compa-ratio (XRH16) — donnée paie, gatée par permission.
   ========================================================================== */

function Liste({ rows, loading, empty, renderRow }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((unused, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }
  if (!rows.length) {
    return <EmptyState title="Rien à afficher" description={empty} />
  }
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r, i) => (
        <li key={r.id ?? i} className="rounded-lg border border-border bg-card px-3 py-2 text-sm">
          {renderRow(r)}
        </li>
      ))}
    </ul>
  )
}

export default function EmployeDetail() {
  const { id } = useParams()
  const permissions = useSelector((s) => s.auth.permissions)
  const canSalaires = peutVoirSalaires(permissions)

  const [emp, setEmp] = useState(null)
  const [documents, setDocuments] = useState([])
  const [remunerations, setRemunerations] = useState([])
  const [compaRatio, setCompaRatio] = useState(null)
  const [habilitations, setHabilitations] = useState([])
  const [formation, setFormation] = useState(null)
  const [integration, setIntegration] = useState(null)
  const [chatter, setChatter] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [subLoading, setSubLoading] = useState(true)
  const [sortieOpen, setSortieOpen] = useState(false)
  const [reloadTick, setReloadTick] = useState(0)

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    setError(null)
    rhApi.getEmploye(id)
      .then((res) => { if (vivant) setEmp(res.data) })
      .catch(() => {
        if (!vivant) return
        setError('Employé introuvable.')
        toast.error('Employé introuvable.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [id, reloadTick])

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setSubLoading(true)
    const calls = [
      rhApi.getDocuments({ employe: id }),
      rhApi.getHabilitations({ employe: id }),
      rhApi.getRegistreFormation(id),
      rhApi.getIntegration(id),
      rhApi.getHistoriqueEmploye(id),
    ]
    if (canSalaires) {
      calls.push(rhApi.getRemunerations({ employe: id }))
      calls.push(rhApi.getCompaRatio(id))
    }
    Promise.allSettled(calls).then((results) => {
      if (!vivant) return
      const [docRes, habRes, formRes, intRes, chatRes, remRes, compaRes] = results
      if (docRes.status === 'fulfilled') setDocuments(unwrap(docRes.value.data))
      if (habRes.status === 'fulfilled') setHabilitations(unwrap(habRes.value.data))
      if (formRes.status === 'fulfilled') setFormation(formRes.value.data)
      if (intRes.status === 'fulfilled') setIntegration(intRes.value.data)
      if (chatRes.status === 'fulfilled') setChatter(unwrap(chatRes.value.data))
      if (canSalaires && remRes?.status === 'fulfilled') {
        setRemunerations(unwrap(remRes.value.data))
      }
      // compa-ratio : 404 attendu si poste/bande/salaire manquant → silencieux.
      if (canSalaires && compaRes?.status === 'fulfilled') {
        setCompaRatio(compaRes.value.data)
      }
      setSubLoading(false)
    })
    return () => { vivant = false }
  }, [id, canSalaires, reloadTick])

  const recharger = () => setReloadTick((t) => t + 1)

  // VX48 — onglet pré-ouvert SYNCHRONE avant l'await (Safari iOS bloque
  // silencieusement un window.open() post-await).
  const telechargerCertificat = async () => {
    const pending = openPdfInGesture()
    try {
      const res = await rhApi.getCertificatTravail(id)
      const blob = new Blob([res.data], { type: 'application/pdf' })
      if (!pending.deliver(blob, `certificat-travail-${id}.pdf`)) {
        toast.error('Ouverture bloquée par le navigateur.')
      }
    } catch (err) {
      if (err?.response?.status === 404) {
        toast.error('Certificat indisponible : l’employé n’est pas sorti.')
      } else {
        toast.error('Téléchargement du certificat impossible.')
      }
    }
  }

  const confirmerEssai = async () => {
    try {
      await rhApi.confirmerEssai(id)
      toast.success('Période d’essai confirmée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Confirmation impossible.')
    }
  }

  const marquerDeclare = async () => {
    try {
      await rhApi.marquerDeclare(id)
      toast.success('Déclaration d’entrée CNSS/AMO marquée faite.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Opération impossible.')
    }
  }

  if (loading) {
    return (
      <div className="page flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (error || !emp) {
    return (
      <div className="page">
        <EmptyState title="Employé introuvable" description="Ce dossier n'existe pas ou n'est pas accessible." />
      </div>
    )
  }

  const nomComplet = `${emp.nom} ${emp.prenom}`.trim()
  const estSorti = emp.statut === 'sorti'

  const identiteTab = (
    <DefinitionList
      items={[
        { term: 'Matricule', description: emp.matricule || '—' },
        { term: 'Nom complet', description: nomComplet || '—' },
        { term: 'CIN', description: emp.cin || '—' },
        { term: 'CNSS', description: emp.cnss || '—' },
        { term: 'Situation familiale', description: emp.situation_familiale_display || '—' },
        { term: 'Enfants', description: emp.nombre_enfants ?? '—' },
        { term: 'Téléphone', description: emp.telephone ? formatPhoneMA(emp.telephone) : '—' },
        { term: 'Email', description: emp.email || '—' },
        { term: 'Contact d’urgence', description: emp.urgence_nom
          ? `${emp.urgence_nom}${emp.urgence_lien ? ` (${emp.urgence_lien})` : ''}${emp.urgence_telephone ? ` — ${formatPhoneMA(emp.urgence_telephone)}` : ''}`
          : '—' },
      ]}
    />
  )

  // XRH1 (essai) + XRH5 (déclaration d'entrée CNSS/AMO) — encarts d'action.
  const essaiEnCours = Boolean(emp.essai_date_fin)
  const declarationAFaire = emp.declaration_entree_statut === 'a_faire'
  const contratTab = (
    <div className="flex flex-col gap-4">
      <DefinitionList
        items={[
          { term: 'Poste', description: emp.poste || '—' },
          { term: 'Département', description: emp.departement ? String(emp.departement) : '—' },
          { term: 'Type de contrat', description: emp.type_contrat_display || TYPE_CONTRAT_LABELS[emp.type_contrat] || '—' },
          { term: 'Date d’embauche', description: formatDate(emp.date_embauche) },
          { term: 'Début de contrat', description: formatDate(emp.contrat_date_debut) },
          { term: 'Fin de contrat', description: emp.contrat_date_fin ? formatDate(emp.contrat_date_fin) : '—' },
          { term: 'Fin de période d’essai', description: emp.essai_date_fin ? formatDate(emp.essai_date_fin) : '—' },
          { term: 'Statut', description: emp.statut_display || emp.statut || '—' },
          { term: 'Date de sortie', description: emp.date_sortie ? formatDate(emp.date_sortie) : '—' },
          { term: 'Motif de sortie', description: emp.motif_sortie_display || emp.motif_sortie || '—' },
        ]}
      />
      {essaiEnCours && !estSorti && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
          <span>Période d’essai en cours (fin le {formatDate(emp.essai_date_fin)}).</span>
          <Button size="sm" variant="outline" onClick={confirmerEssai}>Confirmer l’essai</Button>
        </div>
      )}
      {declarationAFaire && !estSorti && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-info/40 bg-info/10 px-3 py-2 text-sm">
          <span>Déclaration d’entrée CNSS/AMO à faire.</span>
          <Button size="sm" variant="outline" onClick={marquerDeclare}>Marquer déclaré</Button>
        </div>
      )}
    </div>
  )

  const documentsTab = (
    <Liste
      rows={documents}
      loading={subLoading}
      empty="Aucune pièce au dossier."
      renderRow={(d) => (
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium">{d.type_document_display || d.type_document}</p>
            <p className="truncate text-xs text-muted-foreground">
              {d.filename || '—'}
              {d.date_expiration ? ` · expire le ${formatDate(d.date_expiration)}` : ''}
            </p>
          </div>
          {d.url && (
            <ExternalLink className="link-blue text-xs" href={d.url}>
              Ouvrir
            </ExternalLink>
          )}
        </div>
      )}
    />
  )

  const habilitationsTab = (
    <Liste
      rows={habilitations}
      loading={subLoading}
      empty="Aucune habilitation enregistrée."
      renderRow={(h) => (
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium">{h.type_habilitation_display || h.type_habilitation}</p>
            <p className="truncate text-xs text-muted-foreground">
              {h.organisme || '—'}
              {h.date_validite ? ` · valide jusqu’au ${formatDate(h.date_validite)}` : ''}
            </p>
          </div>
          <Badge tone={h.valide ? 'success' : 'danger'}>
            {h.valide ? 'Valide' : 'Expirée'}
          </Badge>
        </div>
      )}
    />
  )

  const formationsRows = formation?.lignes ?? []
  const formationsTab = (
    <Liste
      rows={formationsRows}
      loading={subLoading}
      empty="Aucune formation au registre."
      renderRow={(f) => (
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium">{f.intitule || f.session_intitule || '—'}</p>
            <p className="truncate text-xs text-muted-foreground">
              {f.organisme || '—'}
              {f.date_debut ? ` · ${formatDate(f.date_debut)}` : ''}
            </p>
          </div>
          {f.statut_display && <Badge tone="neutral">{f.statut_display}</Badge>}
        </div>
      )}
    />
  )

  // XRH4 — checklist d'intégration (onboarding) + progression.
  const integrationLignes = integration?.lignes ?? []
  const integrationTab = (
    <div className="flex flex-col gap-3">
      {integration && (
        <p className="text-sm text-muted-foreground">
          Progression : {integration.faits ?? 0}/{integration.total ?? 0} ({integration.progression_pct ?? 0}%)
        </p>
      )}
      <Liste
        rows={integrationLignes}
        loading={subLoading}
        empty="Aucune checklist d’intégration. Instanciez un modèle pour la générer."
        renderRow={(l) => (
          <div className="flex items-center justify-between gap-3">
            <span className={l.fait ? 'text-muted-foreground line-through' : ''}>{l.libelle}</span>
            <Badge tone={l.fait ? 'success' : 'neutral'}>{l.fait ? 'Fait' : 'À faire'}</Badge>
          </div>
        )}
      />
    </div>
  )

  // XRH6 — chatter (timeline d'activité : logs automatiques + notes).
  const chatterTab = (
    <Liste
      rows={chatter}
      loading={subLoading}
      empty="Aucune activité enregistrée."
      renderRow={(a) => (
        <div className="min-w-0">
          <p className="text-sm">
            {a.type === 'note' || a.type === 'NOTE'
              ? (a.message || '—')
              : `${a.field || 'Champ'} : ${a.old_value ?? '—'} → ${a.new_value ?? '—'}`}
          </p>
          <p className="text-xs text-muted-foreground">
            {a.auteur_nom || a.auteur || 'Système'}
            {a.date_creation ? ` · ${formatDate(a.date_creation)}` : ''}
          </p>
        </div>
      )}
    />
  )

  const remunerationTab = (
    <div className="flex flex-col gap-4">
      {/* XRH16 — compa-ratio (salaire vs bande du poste), donnée paie gatée. */}
      {compaRatio && (
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm">
          <p className="font-medium">Compa-ratio : {compaRatio.compa_ratio != null ? formatPercent(compaRatio.compa_ratio * 100, { decimals: 0 }) : '—'}</p>
          <p className="text-xs text-muted-foreground">
            Salaire {compaRatio.salaire != null ? formatMAD(compaRatio.salaire) : '—'}
            {' · '}bande {compaRatio.mediane != null ? formatMAD(compaRatio.mediane) : '—'} (médiane)
          </p>
        </div>
      )}
      <Liste
        rows={remunerations}
        loading={subLoading}
        empty="Aucune rémunération enregistrée."
        renderRow={(r) => (
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="font-medium">{formatMAD(r.montant)}</p>
              <p className="truncate text-xs text-muted-foreground">
                {r.periodicite_display || r.periodicite || ''}
                {r.date_effet ? ` · effet le ${formatDate(r.date_effet)}` : ''}
                {r.motif ? ` · ${r.motif}` : ''}
              </p>
            </div>
          </div>
        )}
      />
    </div>
  )

  const tabs = [
    { value: 'identite', label: 'Identité', content: identiteTab },
    { value: 'contrat', label: 'Contrat', content: contratTab },
    { value: 'documents', label: 'Documents', content: documentsTab, count: documents.length },
    // Rémunération masquée sans la permission salaires_voir (UX22).
    ...(canSalaires
      ? [{ value: 'remuneration', label: 'Rémunération', content: remunerationTab, count: remunerations.length }]
      : []),
    { value: 'habilitations', label: 'Habilitations', content: habilitationsTab, count: habilitations.length },
    { value: 'formations', label: 'Formations', content: formationsTab, count: formationsRows.length },
    { value: 'integration', label: 'Intégration', content: integrationTab, count: integrationLignes.length },
    { value: 'chatter', label: 'Activité', content: chatterTab, count: chatter.length },
  ]

  const headerActions = (
    <>
      {estSorti ? (
        <Button variant="outline" size="sm" onClick={telechargerCertificat}>
          <FileDown size={15} strokeWidth={1.75} aria-hidden="true" />
          Certificat de travail
        </Button>
      ) : (
        <Button variant="outline" size="sm" onClick={() => setSortieOpen(true)}>
          <LogOut size={15} strokeWidth={1.75} aria-hidden="true" />
          Sortie
        </Button>
      )}
    </>
  )

  return (
    <div className="page">
      {/* ARC46 — RecordShell (pendant détail de ListShell) ; drop-in de
          DetailShell : mêmes props, aucune refonte visuelle, save-bar non
          activée (édition via dialogue). */}
      <RecordShell
        title={nomComplet || 'Employé'}
        subtitle={emp.matricule ? `Matricule ${emp.matricule}` : undefined}
        status={emp.statut}
        statusPill={StatutEmploye}
        backTo="/rh/employes"
        backLabel="Retour aux employés"
        actions={headerActions}
        tabs={tabs}
      />
      {sortieOpen && (
        <SortieDialog
          employe={emp}
          onClose={() => setSortieOpen(false)}
          onSaved={() => { setSortieOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

/* ── YHIRE2 — Sortie de l'employé (offboarding) ── */
function SortieDialog({ employe, onClose, onSaved }) {
  const [dateSortie, setDateSortie] = useState('')
  const [motif, setMotif] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  // Motifs alignés sur DossierEmploye.MotifSortie (côté serveur).
  const MOTIFS = [
    { value: 'demission', label: 'Démission' },
    { value: 'licenciement', label: 'Licenciement' },
    { value: 'fin_cdd', label: 'Fin de CDD' },
    { value: 'retraite', label: 'Retraite' },
    { value: 'rupture_conventionnelle', label: 'Rupture conventionnelle' },
    { value: 'deces', label: 'Décès' },
    { value: 'autre', label: 'Autre' },
  ]

  const submit = async (e) => {
    e.preventDefault()
    if (!dateSortie || !motif) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.sortirEmploye(employe.id, {
        date_sortie: dateSortie,
        motif,
        notes_avances: notes || '',
      })
      toast.success('Sortie enregistrée — compte désactivé, checklist générée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.date_sortie || data?.motif
        || 'Enregistrement de la sortie impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Sortie de {employe.nom} {employe.prenom}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="so-date">Date de sortie</Label>
              <Input id="so-date" type="date" value={dateSortie} onChange={(e) => setDateSortie(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="so-motif">Motif</Label>
              <select
                id="so-motif"
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Choisir —</option>
                {MOTIFS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="so-notes">Notes (avances, solde…)</Label>
            <Textarea id="so-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Optionnel" />
          </div>
          <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-foreground">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            La sortie désactive le compte utilisateur et génère la checklist de
            restitution (EPI, matériel, accès). Action irréversible.
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={!dateSortie || !motif || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer la sortie'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// Les listes DRF peuvent être paginées ({results:[…]}) ou brutes ([…]).
function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
