import { useMemo, useState } from 'react'
import { BadgeCheck, PlusCircle } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Badge,
  Dialog, DialogContent, DialogTitle, Button, Label, Input, Textarea, toast,
} from '../../ui'
import { FieldSelect } from './QhseForm'
import { formatDate } from '../../lib/format'
import { QhseResourceList } from './QhseResourceList'

/* ============================================================================
   WIR276 — Écrans des registres ISO exposés par WIR275 (jusqu'ici sans
   écran) : campagnes de rappel produit, certifications + audits externes,
   programme d'audit interne, réunions/revues de direction, objectifs 6.2.
   Même patron que Environnement.jsx (UX33) : `QhseResourceList` par onglet,
   dialogue de création générique piloté par une spec de champs. Les statuts
   dérivés (`statut_calcule`, `independance_ok`, `checklist_9_3_complete`,
   `atteint`) sont AFFICHÉS, jamais recalculés côté client.
   ========================================================================== */

const CREATE_SPECS = {
  campagnesRappel: {
    title: 'Nouvelle campagne de rappel', create: (d) => qhseApi.campagnesRappel.create(d),
    fields: [
      { name: 'titre', label: 'Titre', type: 'text', required: true },
      { name: 'produit', label: 'Produit (id)', type: 'number', required: true },
      { name: 'serie_debut', label: 'Série début', type: 'text' },
      { name: 'serie_fin', label: 'Série fin', type: 'text' },
      { name: 'lot', label: 'Lot', type: 'text' },
      { name: 'motif', label: 'Motif', type: 'textarea', required: true },
      {
        name: 'gravite', label: 'Gravité', type: 'select', default: 'majeure',
        options: [
          { value: 'mineure', label: 'Mineure' },
          { value: 'majeure', label: 'Majeure' },
          { value: 'critique', label: 'Critique' },
        ],
      },
    ],
  },
  certifications: {
    title: 'Nouvelle certification', create: (d) => qhseApi.certifications.create(d),
    fields: [
      {
        name: 'referentiel', label: 'Référentiel', type: 'select', default: 'iso_9001',
        options: [
          { value: 'iso_9001', label: 'ISO 9001' },
          { value: 'iso_14001', label: 'ISO 14001' },
          { value: 'iso_45001', label: 'ISO 45001' },
          { value: 'nm', label: 'NM' },
        ],
      },
      { name: 'organisme', label: 'Organisme', type: 'text', required: true },
      { name: 'numero_certificat', label: 'N° certificat', type: 'text' },
      { name: 'perimetre', label: 'Périmètre', type: 'textarea' },
      { name: 'date_emission', label: "Date d'émission", type: 'date', required: true },
      { name: 'date_expiration', label: "Date d'expiration", type: 'date', required: true },
      { name: 'prealerte_jours', label: 'Préalerte (jours)', type: 'number', default: '60' },
    ],
  },
  programmesAudit: {
    title: "Nouveau programme d'audit", create: (d) => qhseApi.programmesAudit.create(d),
    fields: [
      { name: 'annee', label: 'Année', type: 'number', required: true, default: String(new Date().getFullYear()) },
      { name: 'objectifs', label: 'Objectifs', type: 'textarea' },
    ],
  },
  reunionsQhse: {
    title: 'Nouvelle réunion', create: (d) => qhseApi.reunionsQhse.create(d),
    fields: [
      {
        name: 'type_reunion', label: 'Type', type: 'select', default: 'revue_direction',
        options: [
          { value: 'revue_direction', label: 'Revue de direction' },
          { value: 'comite_hygiene_securite', label: "Comité d'hygiène et de sécurité" },
          { value: 'hse', label: 'Réunion HSE' },
        ],
      },
      { name: 'date_reunion', label: 'Date', type: 'date', required: true },
      { name: 'ordre_du_jour', label: 'Ordre du jour', type: 'textarea' },
      { name: 'pv', label: 'Procès-verbal', type: 'textarea' },
    ],
  },
  objectifsQhse: {
    title: 'Nouvel objectif QHSE', create: (d) => qhseApi.objectifsQhse.create(d),
    fields: [
      {
        name: 'domaine', label: 'Domaine', type: 'select', default: 'securite',
        options: [
          { value: 'qualite', label: 'Qualité' },
          { value: 'securite', label: 'Sécurité' },
          { value: 'environnement', label: 'Environnement' },
          { value: 'esg', label: 'ESG' },
        ],
      },
      { name: 'intitule', label: 'Intitulé', type: 'text', required: true },
      { name: 'indicateur_libre', label: 'Indicateur', type: 'text' },
      { name: 'valeur_baseline', label: 'Baseline', type: 'number' },
      { name: 'annee_baseline', label: 'Année baseline', type: 'number', default: String(new Date().getFullYear()) },
      { name: 'valeur_cible', label: 'Cible', type: 'number', required: true },
      { name: 'echeance', label: 'Échéance', type: 'date', required: true },
      {
        name: 'sens_amelioration', label: "Sens d'amélioration", type: 'select', default: 'baisse',
        options: [
          { value: 'baisse', label: 'Baisse souhaitée' },
          { value: 'hausse', label: 'Hausse souhaitée' },
        ],
      },
    ],
  },
}

function CreateDialog({ spec, onClose, onDone }) {
  const initial = useMemo(() => {
    const o = {}
    for (const f of spec.fields) o[f.name] = f.default ?? ''
    return o
  }, [spec])
  const [form, setForm] = useState(initial)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setForm((prev) => ({ ...prev, [k]: v }))

  async function save() {
    for (const f of spec.fields) {
      if (f.required && (form[f.name] === '' || form[f.name] == null)) {
        toast.error(`${f.label} est requis.`); return
      }
    }
    const payload = {}
    for (const f of spec.fields) {
      const v = form[f.name]
      if (v === '' || v == null) continue
      payload[f.name] = f.type === 'number' ? Number(v) : v
    }
    setSaving(true)
    try {
      await spec.create(payload)
      toast.success('Enregistrement créé.')
      onDone(); onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogTitle>{spec.title}</DialogTitle>
        <div className="flex flex-col gap-3">
          {spec.fields.map((f) => (
            <div key={f.name}>
              <Label>{f.label}{f.required ? ' *' : ''}</Label>
              {f.type === 'select' ? (
                <FieldSelect
                  value={String(form[f.name] ?? '')}
                  onValueChange={(v) => setField(f.name, v)}
                  options={f.options}
                />
              ) : f.type === 'textarea' ? (
                <Textarea rows={2} aria-label={f.label}
                  value={form[f.name]} onChange={(e) => setField(f.name, e.target.value)} />
              ) : (
                <Input aria-label={f.label}
                  type={f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
                  value={form[f.name]} onChange={(e) => setField(f.name, e.target.value)} />
              )}
            </div>
          ))}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function CreerButton({ onClick, label = 'Nouveau' }) {
  return (
    <Button size="sm" onClick={onClick}>
      <PlusCircle size={15} aria-hidden="true" /> {label}
    </Button>
  )
}

export default function RegistresIso() {
  const [tab, setTab] = useState('rappels')
  const [createKey, setCreateKey] = useState(null)
  const [reloadNonce, setReloadNonce] = useState(0)
  const bumpReload = () => setReloadNonce((n) => n + 1)

  const rappelsCols = useMemo(() => [
    { id: 'titre', header: 'Campagne', accessor: (r) => r.titre },
    { id: 'lot', header: 'Lot', width: 130, accessor: (r) => r.lot || '—' },
    {
      id: 'gravite', header: 'Gravité', width: 120,
      accessor: (r) => r.gravite_display || r.gravite,
    },
    {
      id: 'nb_elements', header: 'Éléments', width: 100, align: 'right',
      accessor: (r) => r.nb_elements ?? 0,
    },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut,
      cell: (v, r) => <Badge tone={v === 'cloturee' ? 'success' : 'warning'}>{r.statut_display || v}</Badge>,
    },
  ], [])

  const certifCols = useMemo(() => [
    { id: 'referentiel', header: 'Référentiel', width: 130, accessor: (r) => r.referentiel_display || r.referentiel },
    { id: 'organisme', header: 'Organisme', accessor: (r) => r.organisme },
    { id: 'numero', header: 'N° certificat', width: 170, accessor: (r) => r.numero_certificat || '—' },
    {
      id: 'expiration', header: 'Expiration', width: 130, align: 'right',
      accessor: (r) => r.date_expiration, cell: (v) => formatDate(v),
    },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut_calcule,
      cell: (v, r) => (
        <Badge tone={v === 'valide' ? 'success' : v === 'a_renouveler' ? 'warning' : 'danger'}>
          {r.statut_display || v}
        </Badge>
      ),
    },
  ], [])

  const programmesCols = useMemo(() => [
    { id: 'annee', header: 'Année', width: 100, accessor: (r) => r.annee },
    { id: 'objectifs', header: 'Objectifs', accessor: (r) => r.objectifs || '—' },
  ], [])

  const auditsPlanifiesCols = useMemo(() => [
    { id: 'processus', header: 'Processus / domaine', accessor: (r) => r.processus_domaine },
    {
      id: 'date_cible', header: 'Date cible', width: 130, align: 'right',
      accessor: (r) => r.date_cible, cell: (v) => formatDate(v),
    },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_display || r.statut },
    {
      id: 'independance', header: 'Indépendance', width: 140, align: 'center',
      accessor: (r) => r.independance_ok,
      cell: (v) => <Badge tone={v ? 'success' : 'warning'}>{v ? 'OK' : 'À vérifier'}</Badge>,
    },
  ], [])

  const reunionsCols = useMemo(() => [
    { id: 'type', header: 'Type', width: 190, accessor: (r) => r.type_reunion_display || r.type_reunion },
    {
      id: 'date', header: 'Date', width: 120, align: 'right',
      accessor: (r) => r.date_reunion, cell: (v) => formatDate(v),
    },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut_display || r.statut },
    {
      id: 'checklist', header: 'Checklist 9.3', width: 130, align: 'center',
      accessor: (r) => r.checklist_9_3_complete,
      cell: (v, r) => (r.type_reunion !== 'revue_direction'
        ? <span className="text-muted-foreground">—</span>
        : <Badge tone={v ? 'success' : 'warning'}>{v ? 'Complète' : 'Incomplète'}</Badge>),
    },
  ], [])

  const objectifsCols = useMemo(() => [
    { id: 'intitule', header: 'Objectif', accessor: (r) => r.intitule },
    { id: 'domaine', header: 'Domaine', width: 130, accessor: (r) => r.domaine_display || r.domaine },
    { id: 'cible', header: 'Cible', width: 110, align: 'right', accessor: (r) => r.valeur_cible ?? '—' },
    {
      id: 'echeance', header: 'Échéance', width: 130, align: 'right',
      accessor: (r) => r.echeance, cell: (v) => formatDate(v),
    },
    {
      id: 'atteint', header: 'Dernière revue', width: 140, align: 'center',
      accessor: (r) => r.derniere_revue?.atteint,
      cell: (v, r) => (!r.derniere_revue
        ? <span className="text-muted-foreground">Aucune</span>
        : <Badge tone={v ? 'success' : 'warning'}>{v ? 'Atteint' : 'Non atteint'}</Badge>),
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2 className="flex items-center gap-2">
          <BadgeCheck size={20} strokeWidth={1.75} aria-hidden="true" />
          Registres ISO
        </h2>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="rappels">Rappels produit</TabsTrigger>
          <TabsTrigger value="certifications">Certifications</TabsTrigger>
          <TabsTrigger value="programme-audit">Programme d'audit</TabsTrigger>
          <TabsTrigger value="reunions">Revues de direction</TabsTrigger>
          <TabsTrigger value="objectifs">Objectifs QHSE</TabsTrigger>
        </TabsList>

        <TabsContent value="rappels" className="mt-4">
          <QhseResourceList
            title="Campagnes de rappel produit"
            subtitle="Containment — peuplement/notification/clôture pilotés côté serveur"
            fetcher={() => qhseApi.campagnesRappel.list()}
            columns={rappelsCols}
            exportName="qhse-campagnes-rappel"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('campagnesRappel')} label="Nouvelle campagne" />}
          />
        </TabsContent>

        <TabsContent value="certifications" className="mt-4">
          <QhseResourceList
            title="Certifications (ISO / NM)"
            subtitle="Statut calculé serveur selon la préalerte"
            fetcher={() => qhseApi.certifications.list()}
            columns={certifCols}
            exportName="qhse-certifications"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('certifications')} label="Nouvelle certification" />}
          />
        </TabsContent>

        <TabsContent value="programme-audit" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Programme d'audit interne annuel"
            subtitle="ISO 4.2 / 9.2"
            fetcher={() => qhseApi.programmesAudit.list()}
            columns={programmesCols}
            exportName="qhse-programmes-audit"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('programmesAudit')} label="Nouveau programme" />}
          />
          <QhseResourceList
            title="Audits planifiés"
            subtitle="Indépendance auditeur/domaine ADVISORY (jamais bloquante)"
            fetcher={() => qhseApi.auditsPlanifies.list()}
            columns={auditsPlanifiesCols}
            exportName="qhse-audits-planifies"
            deps={[reloadNonce]}
          />
        </TabsContent>

        <TabsContent value="reunions" className="mt-4">
          <QhseResourceList
            title="Réunions & revues de direction"
            subtitle="Une revue de direction ne se clôture qu'avec la checklist ISO 9.3 complète"
            fetcher={() => qhseApi.reunionsQhse.list()}
            columns={reunionsCols}
            exportName="qhse-reunions"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('reunionsQhse')} label="Nouvelle réunion" />}
          />
        </TabsContent>

        <TabsContent value="objectifs" className="mt-4">
          <QhseResourceList
            title="Objectifs QHSE / ESG (ISO 6.2)"
            subtitle="« Atteint » dérivé serveur à chaque revue"
            fetcher={() => qhseApi.objectifsQhse.list()}
            columns={objectifsCols}
            exportName="qhse-objectifs"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('objectifsQhse')} label="Nouvel objectif" />}
          />
        </TabsContent>
      </Tabs>

      {createKey && (
        <CreateDialog
          spec={CREATE_SPECS[createKey]}
          onClose={() => setCreateKey(null)}
          onDone={bumpReload}
        />
      )}
    </div>
  )
}
