import { useMemo, useState } from 'react'
import {
  Plus, Eye, CheckCircle2, RefreshCw, ClipboardCheck,
} from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { ListShell, DetailShell } from '../../ui/module'
import {
  Button, Badge, Dialog, DialogContent, DialogTitle, Input, Textarea, Label,
  toast, DefinitionList,
} from '../../ui'
import { FieldSelect } from './QhseForm'
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
   Deux registres sous onglets :
   • NCR : registre + création (dont depuis une réserve de chantier), clôture
     conditionnée (gate CAPA côté serveur), et détail avec chatter/historique
     (panneau `activity` de la DetailShell).
   • CAPA : registre, filtre « en retard », relance en masse, vérification
     d'efficacité.
   ========================================================================== */

const GRAVITE_OPTS = Object.entries(GRAVITE).map(([value, v]) => ({
  value, label: v.label,
}))

function NcrCreateDialog({ onClose, onCreated }) {
  const [form, setForm] = useState({
    titre: '', description: '', gravite: 'mineure', origine: '',
    reserve: '', chantier_id: '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }))

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

function NcrDetail({ ncr, onBack, onChanged }) {
  const [busy, setBusy] = useState(false)
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
  ]

  return (
    <DetailShell
      title={ncr.titre || ncr.reference || `NCR #${ncr.id}`}
      status={ncr.statut}
      statusPill={NcrStatutPill}
      actions={
        ncr.statut !== 'cloturee' ? (
          <Button size="sm" onClick={cloturer} disabled={busy}>
            <CheckCircle2 size={15} /> Clôturer
          </Button>
        ) : null
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
      ]}
    />
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

export default function NonConformites() {
  const [tab, setTab] = useState('ncr')
  return (
    <div className="page flex flex-col gap-4">
      <div className="flex gap-2">
        <Button
          variant={tab === 'ncr' ? 'default' : 'ghost'}
          onClick={() => setTab('ncr')}
        >
          Non-conformités
        </Button>
        <Button
          variant={tab === 'capa' ? 'default' : 'ghost'}
          onClick={() => setTab('capa')}
        >
          CAPA
        </Button>
      </div>
      {tab === 'ncr' ? <NcrRegister /> : <CapaRegister />}
    </div>
  )
}
