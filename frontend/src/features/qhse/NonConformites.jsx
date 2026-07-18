import { useMemo, useState } from 'react'
import {
  Plus, Eye, CheckCircle2, RefreshCw, ClipboardCheck, Gavel, Sparkles,
  Wrench, ShieldAlert,
} from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { ListShell, DetailShell } from '../../ui/module'
import {
  Button, Badge, Dialog, DialogContent, DialogTitle, Input, Textarea, Label,
  toast, DefinitionList, Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { FieldSelect } from './QhseForm'
import { QhseResourceList } from './QhseResourceList'
import { formatDate } from '../../lib/format'
import { useQhseList } from './useQhseList'
import {
  NcrStatutPill, CapaStatutPill, GravitePill,
} from './qhsePills'
import { GRAVITE } from './qhseStatus'
import NcrChatter from './NcrChatter'

/* ============================================================================
   UX30 — Non-conformités (NCR) & actions correctives/préventives (CAPA).
   ----------------------------------------------------------------------------
   Trois registres sous onglets :
   • NCR : registre + création (dont depuis une réserve de chantier), clôture
     conditionnée (gate CAPA côté serveur), disposition (XQHS2) et détail avec
     chatter/historique (panneau `activity` de la DetailShell).
   • CAPA : registre, filtre « en retard », relance en masse, vérification
     d'efficacité.
   • Dérogations (XQHS2) : acceptations en l'état bornées, liées à une NCR.
   ========================================================================== */

const GRAVITE_OPTS = Object.entries(GRAVITE).map(([value, v]) => ({
  value, label: v.label,
}))

// XQHS2 — dispositions possibles (miroir de `NonConformite.Disposition`).
const DISPOSITION_OPTS = [
  { value: 'rebut', label: 'Rebut' },
  { value: 'retouche', label: 'Retouche' },
  { value: 'retour_fournisseur', label: 'Retour fournisseur' },
  { value: 'accepte_en_etat', label: "Accepté en l'état" },
  { value: 'tri_recontrole', label: 'Tri / recontrôle' },
]

function DispositionDialog({ ncr, onClose, onDone }) {
  const [disposition, setDisposition] = useState('')
  const [coutDisposition, setCoutDisposition] = useState('')
  const [fournisseur, setFournisseur] = useState('')
  const [creerCapaRetouche, setCreerCapaRetouche] = useState(false)
  const [capaDescription, setCapaDescription] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!disposition) { toast.error('La disposition est requise.'); return }
    if (disposition === 'retour_fournisseur' && !fournisseur) {
      toast.error('Le fournisseur est requis pour un retour fournisseur.')
      return
    }
    setSaving(true)
    try {
      await qhseApi.nonConformites.poserDisposition(ncr.id, {
        disposition,
        cout_disposition: coutDisposition || undefined,
        fournisseur: fournisseur ? Number(fournisseur) : undefined,
        creer_capa_retouche: disposition === 'retouche' ? creerCapaRetouche : false,
        capa_description: capaDescription,
      })
      toast.success('Disposition posée.')
      onDone()
      onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Disposition impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Poser la disposition</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Disposition</Label>
            <FieldSelect
              value={disposition}
              onValueChange={setDisposition}
              options={DISPOSITION_OPTS}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Coût interne (optionnel)</Label>
              <Input value={coutDisposition} onChange={(e) => setCoutDisposition(e.target.value)}
                inputMode="decimal" />
            </div>
            {disposition === 'retour_fournisseur' && (
              <div>
                <Label>Fournisseur (id)</Label>
                <Input value={fournisseur} onChange={(e) => setFournisseur(e.target.value)}
                  inputMode="numeric" />
              </div>
            )}
          </div>
          {disposition === 'retouche' && (
            <div className="flex flex-col gap-2 rounded-md border border-border p-3">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={creerCapaRetouche}
                  onChange={(e) => setCreerCapaRetouche(e.target.checked)}
                />
                Créer une CAPA de retouche
              </label>
              {creerCapaRetouche && (
                <Textarea rows={2} placeholder="Description de l'action de retouche"
                  value={capaDescription}
                  onChange={(e) => setCapaDescription(e.target.value)} />
              )}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Poser la disposition'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function NcrCreateDialog({ onClose, onCreated }) {
  const [form, setForm] = useState({
    titre: '', description: '', gravite: 'mineure', origine: '',
    reserve: '', chantier_id: '',
  })
  const [saving, setSaving] = useState(false)
  const [suggesting, setSuggesting] = useState(false)
  const set = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }))

  // XQHS25 — assistance IA (key-gated) : suggère la gravité depuis la
  // description. Toujours une proposition éditable, jamais auto-appliquée
  // sans passer par ce bouton explicite.
  async function suggererClassification() {
    if (!form.description.trim()) {
      toast.error('Décrivez la non-conformité pour obtenir une suggestion.')
      return
    }
    setSuggesting(true)
    try {
      const res = await qhseApi.ia.suggestionClassification({
        description: form.description,
      })
      if (!res.data?.disponible) {
        toast.error('Assistance IA indisponible (clé non configurée).')
        return
      }
      const suggestion = res.data.suggestion
      if (!suggestion) {
        toast.error(res.data.erreur || 'Aucune suggestion.')
        return
      }
      if (suggestion.gravite) {
        setForm((f) => ({ ...f, gravite: suggestion.gravite }))
      }
      toast.success(suggestion.justification || 'Suggestion appliquée.')
    } catch {
      toast.error('Assistance IA indisponible.')
    } finally {
      setSuggesting(false)
    }
  }

  async function save() {
    if (!form.titre.trim()) { toast.error('Le titre est requis.'); return }
    setSaving(true)
    try {
      // Deux modes : depuis une réserve (endpoint dédié) ou création directe.
      if (form.reserve) {
        await qhseApi.nonConformites.depuisReserve({
          reserve: Number(form.reserve),
          gravite: form.gravite,
        })
      } else {
        await qhseApi.nonConformites.create({
          titre: form.titre.trim(),
          description: form.description,
          gravite: form.gravite,
          origine: form.origine,
          chantier_id: form.chantier_id ? Number(form.chantier_id) : null,
        })
      }
      toast.success('Non-conformité créée.')
      onCreated()
      onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Nouvelle non-conformité</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Titre</Label>
            <Input value={form.titre} onChange={set('titre')} />
          </div>
          <div>
            <Label>Description</Label>
            <Textarea rows={3} value={form.description} onChange={set('description')} />
            <Button
              type="button" size="sm" variant="outline" className="mt-1.5"
              onClick={suggererClassification} disabled={suggesting}
            >
              <Sparkles size={14} />
              {suggesting ? 'Analyse…' : 'Suggérer la gravité (IA)'}
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Gravité</Label>
              <FieldSelect
                value={form.gravite}
                onValueChange={set('gravite')}
                options={GRAVITE_OPTS}
              />
            </div>
            <div>
              <Label>Origine</Label>
              <Input value={form.origine} onChange={set('origine')} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Chantier (id)</Label>
              <Input value={form.chantier_id} onChange={set('chantier_id')} inputMode="numeric" />
            </div>
            <div>
              <Label>Depuis réserve (id, optionnel)</Label>
              <Input value={form.reserve} onChange={set('reserve')} inputMode="numeric" />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Création…' : 'Créer'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// XQHS23 — taux de défaillance par produit (NCR d'origine SAV), affiché en
// onglet sur le détail NCR ; jusqu'ici exposé côté API mais sans appelant.
function TauxDefaillancePanel() {
  const { rows, loading, error } = useQhseList(
    () => qhseApi.nonConformites.tauxDefaillanceProduit(),
  )
  if (loading) return <p className="text-sm text-muted-foreground">Chargement…</p>
  if (error) return <p className="text-sm text-destructive">{error}</p>
  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucune NCR d'origine SAV rattachée à un produit pour l'instant.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r) => (
        <li key={r.produit_id ?? 'sans-produit'}
          className="flex items-center justify-between gap-2 rounded-md border border-border p-2.5 text-sm">
          <span>{r.produit_nom || 'Produit non identifié'}</span>
          <Badge tone="neutral">{r.nb_ncr} NCR</Badge>
        </li>
      ))}
    </ul>
  )
}

// XQHS2 — création d'une dérogation (acceptation en l'état bornée) liée à
// cette NCR. `statut`/`date_creation` sont read-only côté serveur
// (DerogationSerializer) — jamais lus du corps ; `non_conformite` est validé
// (même société) par `validate_non_conformite`.
function DerogationCreateDialog({ ncr, onClose, onDone }) {
  const [justification, setJustification] = useState('')
  const [evaluationRisque, setEvaluationRisque] = useState('')
  const [quantiteMax, setQuantiteMax] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateExpiration, setDateExpiration] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.derogations.create({
        non_conformite: ncr.id,
        justification,
        evaluation_risque: evaluationRisque,
        quantite_max: quantiteMax ? Number(quantiteMax) : undefined,
        date_debut: dateDebut || undefined,
        date_expiration: dateExpiration || undefined,
      })
      toast.success('Dérogation créée.')
      onDone()
      onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création de la dérogation impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Créer une dérogation</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Justification</Label>
            <Textarea rows={2} placeholder="Justification de l'acceptation en l'état"
              value={justification}
              onChange={(e) => setJustification(e.target.value)} />
          </div>
          <div>
            <Label>Évaluation du risque</Label>
            <Textarea rows={2} placeholder="Évaluation du risque (optionnel)"
              value={evaluationRisque}
              onChange={(e) => setEvaluationRisque(e.target.value)} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label>Quantité max (optionnel)</Label>
              <Input value={quantiteMax} onChange={(e) => setQuantiteMax(e.target.value)}
                inputMode="numeric" />
            </div>
            <div>
              <Label>Date de début</Label>
              <Input type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div>
              <Label>Date d'expiration</Label>
              <Input type="date" value={dateExpiration}
                onChange={(e) => setDateExpiration(e.target.value)} />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Créer la dérogation'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function NcrDetail({ ncr, onBack, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [posingDisposition, setPosingDisposition] = useState(false)
  // WIR32 — pont NCR↔SAV + création de dérogation, jusqu'ici sans aucun
  // appelant réel côté écran (creerIntervention/tauxDefaillanceProduit dans
  // qhseApi.js, DerogationsRegister en lecture seule).
  const [creatingIntervention, setCreatingIntervention] = useState(false)
  const [derogOpen, setDerogOpen] = useState(false)

  async function creerInterventionSav() {
    setCreatingIntervention(true)
    try {
      const r = await qhseApi.nonConformites.creerIntervention(ncr.id, {})
      const ref = r.data?.ticket_reference
      toast.success(r.data?.created
        ? `Intervention SAV créée — ticket ${ref}`
        : `Intervention SAV déjà ouverte — ticket ${ref}`)
    } catch (err) {
      toast.error(err?.response?.data?.detail
        ?? "Impossible d'ouvrir une intervention SAV.")
    } finally {
      setCreatingIntervention(false)
    }
  }

  async function cloturer() {
    setBusy(true)
    try {
      await qhseApi.nonConformites.cloturer(ncr.id)
      toast.success('Non-conformité clôturée.')
      onChanged()
    } catch (err) {
      // Le serveur refuse si les CAPA ne sont pas vérifiées efficaces.
      toast.error(err?.response?.data?.detail
        ?? 'Clôture impossible (CAPA non vérifiées ?).')
    } finally {
      setBusy(false)
    }
  }

  const items = [
    { term: 'Référence', description: ncr.reference || '—' },
    { term: 'Gravité', description: <GravitePill status={ncr.gravite} /> },
    { term: 'Origine', description: ncr.origine || '—' },
    { term: 'Chantier', description: ncr.chantier_id ?? '—' },
    { term: 'Détectée le', description: formatDate(ncr.date_detection) },
    { term: 'Créée le', description: formatDate(ncr.date_creation) },
    {
      term: 'Disposition',
      description: ncr.disposition_display || ncr.disposition || '—',
    },
  ]

  return (
    <>
      <DetailShell
        title={ncr.titre || ncr.reference || `NCR #${ncr.id}`}
        status={ncr.statut}
        statusPill={NcrStatutPill}
        actions={
          <div className="flex items-center gap-2">
            {!ncr.disposition && (
              <Button size="sm" variant="outline" onClick={() => setPosingDisposition(true)}>
                <Gavel size={15} /> Poser disposition
              </Button>
            )}
            {/* WIR32 — pont NCR→SAV (XQHS23), jusqu'ici sans appelant réel. */}
            <Button size="sm" variant="outline" onClick={creerInterventionSav}
              disabled={creatingIntervention}>
              <Wrench size={15} /> Créer une intervention SAV
            </Button>
            {/* WIR32 — création de dérogation (XQHS2), DerogationsRegister
                était lecture seule alors que la création est supportée. */}
            <Button size="sm" variant="outline" onClick={() => setDerogOpen(true)}>
              <ShieldAlert size={15} /> Créer une dérogation
            </Button>
            {ncr.statut !== 'cloturee' && (
              <Button size="sm" onClick={cloturer} disabled={busy}>
                <CheckCircle2 size={15} /> Clôturer
              </Button>
            )}
          </div>
        }
        activity={<NcrChatter ncrId={ncr.id} />}
        tabs={[
          {
            value: 'infos',
            label: 'Détails',
            content: (
              <div className="flex flex-col gap-4">
                <DefinitionList items={items} />
                {ncr.description && (
                  <div>
                    <h4 className="mb-1 text-sm font-semibold">Description</h4>
                    <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                      {ncr.description}
                    </p>
                  </div>
                )}
                <button
                  type="button"
                  onClick={onBack}
                  className="self-start text-sm text-muted-foreground hover:text-foreground"
                >
                  ← Retour au registre
                </button>
              </div>
            ),
          },
          {
            // WIR32 — taux de défaillance par produit (XQHS23), jusqu'ici
            // sans appelant réel côté écran.
            value: 'taux-defaillance',
            label: 'Taux de défaillance produit',
            content: <TauxDefaillancePanel />,
          },
        ]}
      />
      {posingDisposition && (
        <DispositionDialog
          ncr={ncr}
          onClose={() => setPosingDisposition(false)}
          onDone={onChanged}
        />
      )}
      {derogOpen && (
        <DerogationCreateDialog
          ncr={ncr}
          onClose={() => setDerogOpen(false)}
          onDone={() => {}}
        />
      )}
    </>
  )
}

function NcrRegister() {
  const [selected, setSelected] = useState(null)
  const [creating, setCreating] = useState(false)
  const { rows, loading, error, reload } = useQhseList(
    () => qhseApi.nonConformites.list(),
  )

  const columns = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 110, accessor: (r) => r.reference || '—' },
    { id: 'titre', header: 'Titre', accessor: (r) => r.titre },
    {
      id: 'gravite', header: 'Gravité', width: 120,
      accessor: (r) => r.gravite,
      cell: (v) => <GravitePill status={v} />,
    },
    {
      id: 'statut', header: 'Statut', width: 140,
      accessor: (r) => r.statut,
      cell: (v) => <NcrStatutPill status={v} />,
    },
    {
      id: 'date_detection', header: 'Détectée', width: 120, align: 'right',
      accessor: (r) => r.date_detection,
      cell: (v) => formatDate(v),
    },
  ], [])

  if (selected) {
    return (
      <NcrDetail
        ncr={selected}
        onBack={() => setSelected(null)}
        onChanged={() => { reload(); setSelected(null) }}
      />
    )
  }

  return (
    <>
      <ListShell
        title="Non-conformités"
        subtitle="Registre NCR — création, chatter et clôture conditionnée"
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        searchable
        exportName="qhse-non-conformites"
        onRowClick={(r) => setSelected(r)}
        rowActions={(r) => [
          { id: 'view', label: 'Ouvrir', icon: Eye, onClick: () => setSelected(r) },
        ]}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus size={16} /> Nouvelle NCR
          </Button>
        }
        emptyTitle="Aucune non-conformité"
        emptyDescription="Aucune NCR ne correspond à ces filtres."
        emptyAction={<Button size="sm" onClick={() => setCreating(true)}><Plus size={16} /> Nouvelle NCR</Button>}
      />
      {creating && (
        <NcrCreateDialog onClose={() => setCreating(false)} onCreated={reload} />
      )}
    </>
  )
}

function VerifierDialog({ capa, onClose, onDone }) {
  const [efficace, setEfficace] = useState('true')
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.capa.verifierEfficacite(capa.id, {
        efficace: efficace === 'true',
        commentaire,
      })
      toast.success('Efficacité enregistrée.')
      onDone()
      onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Vérification impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Vérifier l’efficacité de la CAPA</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Efficace ?</Label>
            <FieldSelect
              value={efficace}
              onValueChange={setEfficace}
              options={[
                { value: 'true', label: 'Oui — action efficace' },
                { value: 'false', label: 'Non — à repasser en cours' },
              ]}
            />
          </div>
          <div>
            <Label>Commentaire</Label>
            <Textarea rows={3} value={commentaire}
              onChange={(e) => setCommentaire(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function CapaRegister() {
  const [onlyLate, setOnlyLate] = useState(false)
  const [verifying, setVerifying] = useState(null)
  const { rows, loading, error, reload } = useQhseList(
    () => (onlyLate ? qhseApi.capa.enRetard() : qhseApi.capa.list()),
    [onlyLate],
  )

  async function relancer() {
    try {
      const res = await qhseApi.capa.relancerRetards()
      const n = res.data?.total ?? res.data?.notifiees ?? 0
      toast.success(`Relance envoyée (${n} CAPA en retard).`)
      reload()
    } catch {
      toast.error('Relance impossible.')
    }
  }

  const columns = useMemo(() => [
    { id: 'description', header: 'Action', accessor: (r) => r.description },
    {
      id: 'type_action', header: 'Type', width: 120,
      accessor: (r) => r.type_action_display || r.type_action,
    },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut,
      cell: (v) => <CapaStatutPill status={v} />,
    },
    {
      id: 'echeance', header: 'Échéance', width: 120, align: 'right',
      accessor: (r) => r.echeance,
      cell: (v) => formatDate(v),
    },
    {
      id: 'efficace', header: 'Efficace', width: 100, align: 'center',
      accessor: (r) => r.efficace,
      cell: (v) =>
        v == null
          ? <span className="text-muted-foreground">—</span>
          : <Badge tone={v ? 'success' : 'danger'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  return (
    <>
      <ListShell
        title="Actions correctives / préventives (CAPA)"
        subtitle="Suivi, relance des retards et vérification d’efficacité"
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        searchable
        exportName="qhse-capa"
        rowActions={(r) => [
          {
            id: 'verifier',
            label: 'Vérifier l’efficacité',
            icon: ClipboardCheck,
            onClick: () => setVerifying(r),
          },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant={onlyLate ? 'default' : 'outline'}
              onClick={() => setOnlyLate((v) => !v)}
            >
              {onlyLate ? 'Voir toutes' : 'En retard'}
            </Button>
            <Button variant="outline" onClick={relancer}>
              <RefreshCw size={16} /> Relancer les retards
            </Button>
          </div>
        }
      />
      {verifying && (
        <VerifierDialog
          capa={verifying}
          onClose={() => setVerifying(null)}
          onDone={reload}
        />
      )}
    </>
  )
}

// XQHS2 — Dérogations (acceptations en l'état bornées) liées à une NCR.
function DerogationsRegister() {
  const columns = useMemo(() => [
    { id: 'non_conformite', header: 'NCR', accessor: (r) => r.non_conformite_reference || r.non_conformite },
    { id: 'motif', header: 'Motif', accessor: (r) => r.motif || '—' },
    {
      id: 'date_expiration', header: 'Expire le', width: 130, align: 'right',
      accessor: (r) => r.date_expiration, cell: (v) => formatDate(v),
    },
  ], [])
  return (
    <QhseResourceList
      title="Dérogations"
      subtitle="Acceptations en l'état bornées, liées à une NCR"
      fetcher={() => qhseApi.derogations.list()}
      columns={columns}
      exportName="qhse-derogations"
    />
  )
}

export default function NonConformites() {
  const [tab, setTab] = useState('ncr')
  return (
    <div className="page flex flex-col gap-4">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="ncr">Non-conformités</TabsTrigger>
          <TabsTrigger value="capa">CAPA</TabsTrigger>
          <TabsTrigger value="derogations">Dérogations</TabsTrigger>
        </TabsList>
        <TabsContent value="ncr" className="mt-4">
          <NcrRegister />
        </TabsContent>
        <TabsContent value="capa" className="mt-4">
          <CapaRegister />
        </TabsContent>
        <TabsContent value="derogations" className="mt-4">
          <DerogationsRegister />
        </TabsContent>
      </Tabs>
    </div>
  )
}
