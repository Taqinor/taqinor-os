import { useMemo, useState } from 'react'
import { Plus, Wrench } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Dialog, DialogContent,
  DialogTitle, Button, Input, Label, Textarea, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { FieldSelect } from './QhseForm'
import { formatDate } from '../../lib/format'
import { QhseResourceList } from './QhseResourceList'
import { rowsFrom } from './useQhseList'

/* ============================================================================
   WIR276 — Écrans des 5 registres ISO QHSE exposés côté serveur par WIR275
   (services testés, aucun écran jusqu'ici) : campagnes de rappel produit,
   certifications (ISO/NM), programme d'audit interne, revues de direction
   (+ décisions), objectifs QHSE/ESG (ISO 6.2). Chaque onglet expose au
   minimum la création + la consultation ; les workflows de cycle de vie
   complets (peupler/notifier/cloturer, lever-ncr, instancier, creer-capa…)
   sont déjà testés côté API (WIR275) et restent accessibles via ces mêmes
   wrappers pour un futur enrichissement d'écran.
   ========================================================================== */

// ── Rappels produit (XQHS5) ────────────────────────────────────────────────
const GRAVITE_RAPPEL_OPTS = [
  { value: 'mineure', label: 'Mineure' },
  { value: 'majeure', label: 'Majeure' },
  { value: 'critique', label: 'Critique' },
]

function CreerCampagneRappelDialog({ onClose, onCreated }) {
  const [titre, setTitre] = useState('')
  const [produit, setProduit] = useState('')
  const [gravite, setGravite] = useState('majeure')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!titre.trim() || !produit) { toast.error('Titre et produit sont requis.'); return }
    setSaving(true)
    try {
      await qhseApi.campagnesRappel.create({
        titre: titre.trim(), produit: Number(produit), gravite,
      })
      toast.success('Campagne de rappel créée.')
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
        <DialogTitle>Nouvelle campagne de rappel</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Titre</Label>
            <Input aria-label="Titre" value={titre} onChange={(e) => setTitre(e.target.value)} />
          </div>
          <div>
            <Label>Produit (id)</Label>
            <Input aria-label="Produit (id)" inputMode="numeric" value={produit}
              onChange={(e) => setProduit(e.target.value)} />
          </div>
          <div>
            <Label>Gravité</Label>
            <FieldSelect value={gravite} onValueChange={setGravite} options={GRAVITE_RAPPEL_OPTS} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Certifications (XQHS9) ─────────────────────────────────────────────────
const REFERENTIEL_OPTS = [
  { value: 'iso_9001', label: 'ISO 9001' },
  { value: 'iso_14001', label: 'ISO 14001' },
  { value: 'iso_45001', label: 'ISO 45001' },
  { value: 'nm', label: 'NM (norme marocaine)' },
  { value: 'autre', label: 'Autre' },
]

function CreerCertificationDialog({ onClose, onCreated }) {
  const [referentiel, setReferentiel] = useState('iso_9001')
  const [organisme, setOrganisme] = useState('')
  const [numero, setNumero] = useState('')
  const [dateExpiration, setDateExpiration] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.certifications.create({
        referentiel, organisme, numero_certificat: numero,
        date_expiration: dateExpiration || undefined,
      })
      toast.success('Certification créée.')
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
        <DialogTitle>Nouvelle certification</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Référentiel</Label>
            <FieldSelect value={referentiel} onValueChange={setReferentiel} options={REFERENTIEL_OPTS} />
          </div>
          <div>
            <Label>Organisme</Label>
            <Input aria-label="Organisme" value={organisme} onChange={(e) => setOrganisme(e.target.value)} />
          </div>
          <div>
            <Label>Numéro de certificat</Label>
            <Input aria-label="Numéro de certificat" value={numero} onChange={(e) => setNumero(e.target.value)} />
          </div>
          <div>
            <Label>Date d’expiration</Label>
            <Input aria-label="Date d’expiration" type="date" value={dateExpiration}
              onChange={(e) => setDateExpiration(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Programme d'audit interne (XQHS10) ─────────────────────────────────────
function CreerProgrammeAuditDialog({ onClose, onCreated }) {
  const [annee, setAnnee] = useState(String(new Date().getFullYear()))
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.programmesAudit.create({ annee: Number(annee) })
      toast.success('Programme d’audit créé.')
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
        <DialogTitle>Nouveau programme d’audit</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Année</Label>
            <Input aria-label="Année" type="number" value={annee}
              onChange={(e) => setAnnee(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Revues de direction + décisions (XQHS12) ───────────────────────────────
const TYPE_REUNION_OPTS = [
  { value: 'revue_direction', label: 'Revue de direction' },
  { value: 'comite_hygiene_securite', label: "Comité d'hygiène et de sécurité" },
  { value: 'reunion_hse', label: 'Réunion HSE' },
]

function CreerReunionDialog({ onClose, onCreated }) {
  const [typeReunion, setTypeReunion] = useState('reunion_hse')
  const [dateReunion, setDateReunion] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.reunionsQhse.create({
        type_reunion: typeReunion, date_reunion: dateReunion || undefined,
      })
      toast.success('Réunion QHSE créée.')
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
        <DialogTitle>Nouvelle réunion QHSE</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Type de réunion</Label>
            <Select value={typeReunion} onValueChange={setTypeReunion}>
              <SelectTrigger aria-label="Type de réunion"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPE_REUNION_OPTS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Date</Label>
            <Input aria-label="Date" type="date" value={dateReunion}
              onChange={(e) => setDateReunion(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function CreerDecisionDialog({ reunions, onClose, onCreated }) {
  const [reunionId, setReunionId] = useState(reunions[0]?.id ? String(reunions[0].id) : '')
  const [texte, setTexte] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!reunionId || !texte.trim()) { toast.error('Réunion et texte sont requis.'); return }
    setSaving(true)
    try {
      await qhseApi.decisionsReunion.create({
        reunion: Number(reunionId), texte: texte.trim(),
      })
      toast.success('Décision enregistrée.')
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
        <DialogTitle>Nouvelle décision de réunion</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Réunion</Label>
            <Select value={reunionId} onValueChange={setReunionId}>
              <SelectTrigger aria-label="Réunion"><SelectValue placeholder="Choisir une réunion…" /></SelectTrigger>
              <SelectContent>
                {reunions.map((r) => (
                  <SelectItem key={r.id} value={String(r.id)}>
                    {r.type_reunion_display || r.type_reunion} — {r.date_reunion || 'sans date'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Décision</Label>
            <Textarea aria-label="Décision" rows={3} value={texte}
              onChange={(e) => setTexte(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving || reunions.length === 0}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Objectifs QHSE/ESG (XQHS13, ISO 6.2) ───────────────────────────────────
const DOMAINE_OPTS = [
  { value: 'qualite', label: 'Qualité' },
  { value: 'securite', label: 'Sécurité' },
  { value: 'environnement', label: 'Environnement' },
  { value: 'esg', label: 'ESG' },
]

function CreerObjectifDialog({ onClose, onCreated }) {
  const [intitule, setIntitule] = useState('')
  const [domaine, setDomaine] = useState('qualite')
  const [valeurCible, setValeurCible] = useState('')
  const [echeance, setEcheance] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!intitule.trim()) { toast.error('L’intitulé est requis.'); return }
    setSaving(true)
    try {
      await qhseApi.objectifsQhse.create({
        intitule: intitule.trim(), domaine,
        valeur_cible: valeurCible || undefined,
        echeance: echeance || undefined,
      })
      toast.success('Objectif créé.')
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
        <DialogTitle>Nouvel objectif QHSE</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Intitulé</Label>
            <Input aria-label="Intitulé" value={intitule} onChange={(e) => setIntitule(e.target.value)} />
          </div>
          <div>
            <Label>Domaine</Label>
            <FieldSelect value={domaine} onValueChange={setDomaine} options={DOMAINE_OPTS} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Valeur cible</Label>
              <Input aria-label="Valeur cible" inputMode="decimal" value={valeurCible}
                onChange={(e) => setValeurCible(e.target.value)} />
            </div>
            <div>
              <Label>Échéance</Label>
              <Input aria-label="Échéance" type="date" value={echeance}
                onChange={(e) => setEcheance(e.target.value)} />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function CreerRevueObjectifDialog({ objectifs, onClose, onCreated }) {
  const [objectifId, setObjectifId] = useState(objectifs[0]?.id ? String(objectifs[0].id) : '')
  const [valeurConstatee, setValeurConstatee] = useState('')
  const [dateRevue, setDateRevue] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!objectifId) { toast.error('Un objectif est requis.'); return }
    setSaving(true)
    try {
      await qhseApi.revuesObjectif.create({
        objectif: Number(objectifId),
        valeur_constatee: valeurConstatee || undefined,
        date_revue: dateRevue || undefined,
      })
      toast.success('Revue enregistrée.')
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
        <DialogTitle>Nouvelle revue d’objectif</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Objectif</Label>
            <Select value={objectifId} onValueChange={setObjectifId}>
              <SelectTrigger aria-label="Objectif"><SelectValue placeholder="Choisir un objectif…" /></SelectTrigger>
              <SelectContent>
                {objectifs.map((o) => (
                  <SelectItem key={o.id} value={String(o.id)}>{o.intitule}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Valeur constatée</Label>
              <Input aria-label="Valeur constatée" inputMode="decimal" value={valeurConstatee}
                onChange={(e) => setValeurConstatee(e.target.value)} />
            </div>
            <div>
              <Label>Date de revue</Label>
              <Input aria-label="Date de revue" type="date" value={dateRevue}
                onChange={(e) => setDateRevue(e.target.value)} />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving || objectifs.length === 0}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function IsoQhse() {
  const [createKey, setCreateKey] = useState(null)
  const [reloadNonce, setReloadNonce] = useState(0)
  const bump = () => setReloadNonce((n) => n + 1)

  // WIR275 (XQHS12) — réunions disponibles pour rattacher une nouvelle
  // décision (même patron que `ouvrirCreationLoto`, Risques.jsx).
  const [reunionOptions, setReunionOptions] = useState([])
  const [objectifOptions, setObjectifOptions] = useState([])

  async function ouvrirCreationDecision() {
    try {
      const res = await qhseApi.reunionsQhse.list()
      setReunionOptions(rowsFrom(res))
    } catch {
      setReunionOptions([])
    }
    setCreateKey('decision')
  }

  async function creerCapaDecision(decision) {
    try {
      await qhseApi.decisionsReunion.creerCapaDepuisDecision(decision.id)
      toast.success('CAPA créée depuis la décision.')
      bump()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création de la CAPA impossible.')
    }
  }

  async function ouvrirCreationRevueObjectif() {
    try {
      const res = await qhseApi.objectifsQhse.list()
      setObjectifOptions(rowsFrom(res))
    } catch {
      setObjectifOptions([])
    }
    setCreateKey('revue-objectif')
  }

  const campagnesCols = useMemo(() => [
    { id: 'titre', header: 'Campagne', accessor: (r) => r.titre },
    { id: 'produit', header: 'Produit', accessor: (r) => r.produit },
    { id: 'gravite', header: 'Gravité', width: 120, accessor: (r) => r.gravite_display || r.gravite },
    { id: 'nb_elements', header: 'Éléments', width: 100, align: 'right', accessor: (r) => r.nb_elements ?? 0 },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_display || r.statut },
  ], [])

  const certificationsCols = useMemo(() => [
    { id: 'referentiel', header: 'Référentiel', width: 130, accessor: (r) => r.referentiel_display || r.referentiel },
    { id: 'organisme', header: 'Organisme', accessor: (r) => r.organisme || '—' },
    { id: 'numero', header: 'N° certificat', accessor: (r) => r.numero_certificat || '—' },
    {
      id: 'expiration', header: 'Expiration', width: 130, align: 'right',
      accessor: (r) => r.date_expiration, cell: (v) => formatDate(v),
    },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_calcule || r.statut },
  ], [])

  const programmesCols = useMemo(() => [
    { id: 'annee', header: 'Année', width: 100, accessor: (r) => r.annee },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_display || r.statut },
    {
      id: 'nb_audits', header: 'Audits planifiés', width: 150, align: 'right',
      accessor: (r) => r.nb_audits_planifies ?? 0,
    },
  ], [])

  const reunionsCols = useMemo(() => [
    { id: 'type', header: 'Type', accessor: (r) => r.type_reunion_display || r.type_reunion },
    {
      id: 'date', header: 'Date', width: 120, align: 'right',
      accessor: (r) => r.date_reunion, cell: (v) => formatDate(v),
    },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_display || r.statut },
  ], [])

  const decisionsCols = useMemo(() => [
    { id: 'texte', header: 'Décision', accessor: (r) => r.texte },
    {
      id: 'capa', header: 'CAPA liée', width: 110, align: 'center',
      accessor: (r) => r.capa_id, cell: (v) => (v ? `#${v}` : '—'),
    },
  ], [])

  const objectifsCols = useMemo(() => [
    { id: 'intitule', header: 'Objectif', accessor: (r) => r.intitule },
    { id: 'domaine', header: 'Domaine', width: 130, accessor: (r) => r.domaine_display || r.domaine },
    { id: 'cible', header: 'Cible', width: 100, align: 'right', accessor: (r) => r.valeur_cible ?? '—' },
    {
      id: 'echeance', header: 'Échéance', width: 120, align: 'right',
      accessor: (r) => r.echeance, cell: (v) => formatDate(v),
    },
  ], [])

  const revuesCols = useMemo(() => [
    { id: 'objectif', header: 'Objectif', accessor: (r) => r.objectif },
    { id: 'periode', header: 'Période', width: 120, accessor: (r) => r.periode || '—' },
    { id: 'valeur', header: 'Valeur constatée', width: 140, align: 'right', accessor: (r) => r.valeur_constatee ?? '—' },
    {
      id: 'atteint', header: 'Atteint', width: 100, align: 'center',
      accessor: (r) => r.atteint,
      cell: (v) => (v == null ? '—' : (v ? 'Oui' : 'Non')),
    },
  ], [])

  return (
    <>
      <Tabs defaultValue="rappels">
        <TabsList>
          <TabsTrigger value="rappels">Rappels produit</TabsTrigger>
          <TabsTrigger value="certifications">Certifications</TabsTrigger>
          <TabsTrigger value="programme-audit">Programme d’audit</TabsTrigger>
          <TabsTrigger value="revues-direction">Revues de direction</TabsTrigger>
          <TabsTrigger value="objectifs">Objectifs QHSE</TabsTrigger>
        </TabsList>

        <TabsContent value="rappels" className="mt-4">
          <QhseResourceList
            title="Campagnes de rappel produit"
            subtitle="Défaut fournisseur produit-lot-série (XQHS5)"
            fetcher={() => qhseApi.campagnesRappel.list()}
            columns={campagnesCols}
            exportName="qhse-campagnes-rappel"
            deps={[reloadNonce]}
            actions={
              <Button onClick={() => setCreateKey('campagne')}>
                <Plus size={16} /> Nouvelle campagne
              </Button>
            }
          />
        </TabsContent>

        <TabsContent value="certifications" className="mt-4">
          <QhseResourceList
            title="Certifications (ISO / NM)"
            subtitle="Registre des certificats détenus (XQHS9)"
            fetcher={() => qhseApi.certifications.list()}
            columns={certificationsCols}
            exportName="qhse-certifications"
            deps={[reloadNonce]}
            actions={
              <Button onClick={() => setCreateKey('certification')}>
                <Plus size={16} /> Nouvelle certification
              </Button>
            }
          />
        </TabsContent>

        <TabsContent value="programme-audit" className="mt-4">
          <QhseResourceList
            title="Programme d’audit interne"
            subtitle="Programme annuel (XQHS10)"
            fetcher={() => qhseApi.programmesAudit.list()}
            columns={programmesCols}
            exportName="qhse-programmes-audit"
            deps={[reloadNonce]}
            actions={
              <Button onClick={() => setCreateKey('programme')}>
                <Plus size={16} /> Nouveau programme
              </Button>
            }
          />
        </TabsContent>

        <TabsContent value="revues-direction" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Réunions QHSE"
            subtitle="Revue de direction, CSH, réunion HSE (XQHS12)"
            fetcher={() => qhseApi.reunionsQhse.list()}
            columns={reunionsCols}
            exportName="qhse-reunions"
            deps={[reloadNonce]}
            actions={
              <Button onClick={() => setCreateKey('reunion')}>
                <Plus size={16} /> Nouvelle réunion
              </Button>
            }
          />
          <QhseResourceList
            title="Décisions de réunion"
            subtitle="Une décision peut faire « spawner » une CAPA liée"
            fetcher={() => qhseApi.decisionsReunion.list()}
            columns={decisionsCols}
            exportName="qhse-decisions-reunion"
            deps={[reloadNonce]}
            actions={
              <Button onClick={ouvrirCreationDecision}>
                <Plus size={16} /> Nouvelle décision
              </Button>
            }
            rowActions={(r) => (!r.capa_id
              ? [{ id: 'capa', label: 'Créer CAPA', icon: Wrench, onClick: () => creerCapaDecision(r) }]
              : [])}
          />
        </TabsContent>

        <TabsContent value="objectifs" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Objectifs QHSE/ESG"
            subtitle="Baseline, cible, échéance (ISO 6.2)"
            fetcher={() => qhseApi.objectifsQhse.list()}
            columns={objectifsCols}
            exportName="qhse-objectifs"
            deps={[reloadNonce]}
            actions={
              <Button onClick={() => setCreateKey('objectif')}>
                <Plus size={16} /> Nouvel objectif
              </Button>
            }
          />
          <QhseResourceList
            title="Revues d’objectif"
            subtitle="Valeur constatée périodique — atteinte dérivée côté serveur"
            fetcher={() => qhseApi.revuesObjectif.list()}
            columns={revuesCols}
            exportName="qhse-revues-objectif"
            deps={[reloadNonce]}
            actions={
              <Button onClick={ouvrirCreationRevueObjectif}>
                <Plus size={16} /> Nouvelle revue
              </Button>
            }
          />
        </TabsContent>
      </Tabs>

      {createKey === 'campagne' && (
        <CreerCampagneRappelDialog onClose={() => setCreateKey(null)} onCreated={bump} />
      )}
      {createKey === 'certification' && (
        <CreerCertificationDialog onClose={() => setCreateKey(null)} onCreated={bump} />
      )}
      {createKey === 'programme' && (
        <CreerProgrammeAuditDialog onClose={() => setCreateKey(null)} onCreated={bump} />
      )}
      {createKey === 'reunion' && (
        <CreerReunionDialog onClose={() => setCreateKey(null)} onCreated={bump} />
      )}
      {createKey === 'decision' && (
        <CreerDecisionDialog
          reunions={reunionOptions}
          onClose={() => setCreateKey(null)}
          onCreated={bump}
        />
      )}
      {createKey === 'objectif' && (
        <CreerObjectifDialog onClose={() => setCreateKey(null)} onCreated={bump} />
      )}
      {createKey === 'revue-objectif' && (
        <CreerRevueObjectifDialog
          objectifs={objectifOptions}
          onClose={() => setCreateKey(null)}
          onCreated={bump}
        />
      )}
    </>
  )
}
