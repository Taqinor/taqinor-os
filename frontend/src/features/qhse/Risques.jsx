import { useMemo, useState } from 'react'
import {
  ShieldAlert, ListChecks, CheckCircle2, QrCode, Plus, Wrench, AlertOctagon,
  Lock, LockOpen, XCircle,
} from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Badge, Dialog, DialogContent,
  DialogTitle, Button, Input, Label, Textarea, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { formatDate } from '../../lib/format'
import { QhseResourceList } from './QhseResourceList'
import { useQhseList, rowsFrom } from './useQhseList'
import {
  EvalRisqueStatutPill, PermisStatutPill, LotoStatutPill,
  IncidentStatutPill, IncidentTypePill, GravitePill, CnssStatutPill,
} from './qhsePills'
import { INCIDENT_TYPES, GRAVITE } from './qhseStatus'

// WIR126 — miroir de `PermisTravail.TypePermis` (backend, apps/qhse/models.py).
// source-choix: qhse.PermisTravail.type_permis
const TYPE_PERMIS_OPTIONS = [
  { value: 'hauteur', label: 'Travail en hauteur' },
  { value: 'consignation_elec', label: 'Consignation électrique' },
  { value: 'point_chaud', label: 'Point chaud (soudure / flamme)' },
  { value: 'espace_confine', label: 'Espace confiné' },
  { value: 'autre', label: 'Autre' },
]

// WIR126 — création d'un permis de travail (QHSE23). Le `statut` est en
// lecture seule au CRUD (brouillon par défaut côté serveur) : piloté ensuite
// par les actions `valider`/`cloturer`.
function CreerPermisDialog({ onClose, onCreated }) {
  const [titre, setTitre] = useState('')
  const [typePermis, setTypePermis] = useState('hauteur')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [mesures, setMesures] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!titre.trim()) { toast.error('Le titre est requis.'); return }
    setSaving(true)
    try {
      await qhseApi.permisTravail.create({
        titre: titre.trim(),
        type_permis: typePermis,
        date_debut: dateDebut || null,
        date_fin: dateFin || null,
        mesures_prevention: mesures.trim(),
      })
      toast.success('Permis de travail créé (brouillon).')
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
        <DialogTitle>Nouveau permis de travail</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Titre</Label>
            <Input aria-label="Titre" value={titre} onChange={(e) => setTitre(e.target.value)} />
          </div>
          <div>
            <Label>Type de permis</Label>
            <Select value={typePermis} onValueChange={setTypePermis}>
              <SelectTrigger aria-label="Type de permis"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPE_PERMIS_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Début de validité</Label>
              <Input aria-label="Début de validité" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div>
              <Label>Fin de validité</Label>
              <Input aria-label="Fin de validité" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
            </div>
          </div>
          <div>
            <Label>Mesures de prévention</Label>
            <Textarea aria-label="Mesures de prévention" value={mesures} onChange={(e) => setMesures(e.target.value)} rows={3} />
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

// WIR126 — création d'une consignation LOTO (QHSE24), rattachée à un permis
// existant (typiquement `consignation_elec`). Le statut initial `consignee`
// est posé côté serveur.
function CreerLotoDialog({ permis, onClose, onCreated }) {
  const [permisId, setPermisId] = useState(permis[0]?.id ? String(permis[0].id) : '')
  const [equipement, setEquipement] = useState('')
  const [pointConsignation, setPointConsignation] = useState('')
  const [consignateur, setConsignateur] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!permisId) { toast.error('Un permis de travail est requis.'); return }
    setSaving(true)
    try {
      await qhseApi.consignationsLoto.create({
        permis: Number(permisId),
        equipement: equipement.trim(),
        point_consignation: pointConsignation.trim(),
        consignateur: consignateur.trim(),
      })
      toast.success('Consignation LOTO enregistrée.')
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
        <DialogTitle>Nouvelle consignation LOTO</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Permis de travail</Label>
            <Select value={permisId} onValueChange={setPermisId}>
              <SelectTrigger aria-label="Permis de travail"><SelectValue placeholder="Choisir un permis…" /></SelectTrigger>
              <SelectContent>
                {permis.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.reference || `PT-${p.id}`} — {p.titre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Équipement</Label>
            <Input aria-label="Équipement" value={equipement} onChange={(e) => setEquipement(e.target.value)} />
          </div>
          <div>
            <Label>Point de consignation</Label>
            <Input aria-label="Point de consignation" value={pointConsignation} onChange={(e) => setPointConsignation(e.target.value)} />
          </div>
          <div>
            <Label>Consignateur</Label>
            <Input aria-label="Consignateur" value={consignateur} onChange={(e) => setConsignateur(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving || permis.length === 0}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// WIR126 — création d'un incident HSE (QHSE29). La création à elle seule
// déclenche la chaîne d'escalade chatter/notification déjà testée côté
// serveur (aucune action serveur supplémentaire à câbler ici).
function CreerIncidentDialog({ onClose, onCreated }) {
  const [titre, setTitre] = useState('')
  const [typeIncident, setTypeIncident] = useState('incident')
  const [gravite, setGravite] = useState('mineure')
  const [dateIncident, setDateIncident] = useState('')
  const [description, setDescription] = useState('')
  // XQHS19 — champs environnement (déversement/rejet), affichés seulement
  // quand l'événement est de type « Environnement ». Tous optionnels.
  const [substance, setSubstance] = useState('')
  const [quantite, setQuantite] = useState('')
  const [unite, setUnite] = useState('')
  const [milieu, setMilieu] = useState('')
  const [notificationRequise, setNotificationRequise] = useState(false)
  const [saving, setSaving] = useState(false)
  const estEnvironnemental = typeIncident === 'environnement'

  async function save() {
    if (!titre.trim()) { toast.error('Le titre est requis.'); return }
    setSaving(true)
    try {
      await qhseApi.incidents.create({
        titre: titre.trim(),
        type_incident: typeIncident,
        gravite,
        date_incident: dateIncident || null,
        description: description.trim(),
        ...(estEnvironnemental ? {
          substance: substance.trim(),
          quantite_estimee: quantite === '' ? null : Number(quantite),
          quantite_unite: unite.trim(),
          milieu_touche: milieu,
          notification_requise: notificationRequise,
        } : {}),
      })
      toast.success('Incident déclaré.')
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
        <DialogTitle>Déclarer un incident</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Titre</Label>
            <Input aria-label="Titre" value={titre} onChange={(e) => setTitre(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Type d’événement</Label>
              <Select value={typeIncident} onValueChange={setTypeIncident}>
                <SelectTrigger aria-label="Type d’événement"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(INCIDENT_TYPES).map(([value, { label }]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Gravité</Label>
              <Select value={gravite} onValueChange={setGravite}>
                <SelectTrigger aria-label="Gravité"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(GRAVITE).map(([value, { label }]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>Date de l’événement</Label>
            <Input aria-label="Date de l’événement" type="date" value={dateIncident} onChange={(e) => setDateIncident(e.target.value)} />
          </div>
          <div>
            <Label>Description</Label>
            <Textarea aria-label="Description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </div>
          {estEnvironnemental && (
            <div className="flex flex-col gap-3 rounded-md border border-border p-3">
              <p className="text-sm text-muted-foreground">
                Déversement / rejet — renseigner ce qui a été relâché et où.
              </p>
              <div>
                <Label>Substance</Label>
                <Input
                  aria-label="Substance" value={substance}
                  onChange={(e) => setSubstance(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Quantité estimée</Label>
                  <Input
                    aria-label="Quantité estimée" inputMode="decimal" step="any"
                    value={quantite} onChange={(e) => setQuantite(e.target.value)}
                  />
                </div>
                <div>
                  <Label>Unité</Label>
                  <Input
                    aria-label="Unité" value={unite}
                    onChange={(e) => setUnite(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <Label>Milieu touché</Label>
                <Select value={milieu} onValueChange={setMilieu}>
                  <SelectTrigger aria-label="Milieu touché"><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sol">Sol</SelectItem>
                    <SelectItem value="eau">Eau</SelectItem>
                    <SelectItem value="air">Air</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox" checked={notificationRequise}
                  onChange={(e) => setNotificationRequise(e.target.checked)}
                />
                Notification à l’autorité requise
              </label>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Déclaration…' : 'Déclarer'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// XQHS14 — échelle 1–5 partagée avec le document unique (`RisqueOpportunite`,
// backend). Les criticités sont calculées côté serveur — jamais postées d'ici.
const ECHELLE_1_5 = [1, 2, 3, 4, 5]

// XQHS14 — création d'un risque/opportunité niveau SMQ (ISO 6.1), distinct du
// document unique opérationnel chantier.
function CreerRisqueOpportuniteDialog({ onClose, onCreated }) {
  const [typeRo, setTypeRo] = useState('risque')
  const [processus, setProcessus] = useState('')
  const [description, setDescription] = useState('')
  const [probabilite, setProbabilite] = useState('1')
  const [gravite, setGravite] = useState('1')
  const [actions, setActions] = useState('')
  const [dateRevue, setDateRevue] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!description.trim()) { toast.error('La description est requise.'); return }
    setSaving(true)
    try {
      await qhseApi.risquesOpportunites.create({
        type_ro: typeRo,
        processus: processus.trim(),
        description: description.trim(),
        probabilite_inherente: Number(probabilite),
        gravite_inherente: Number(gravite),
        actions_traitement: actions.trim(),
        date_revue: dateRevue || null,
      })
      toast.success('Risque / opportunité enregistré.')
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
        <DialogTitle>Nouveau risque / opportunité (SMQ)</DialogTitle>
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Type</Label>
              <Select value={typeRo} onValueChange={setTypeRo}>
                <SelectTrigger aria-label="Type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="risque">Risque</SelectItem>
                  <SelectItem value="opportunite">Opportunité</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Processus concerné</Label>
              <Input
                aria-label="Processus concerné" value={processus}
                onChange={(e) => setProcessus(e.target.value)}
              />
            </div>
          </div>
          <div>
            <Label>Description</Label>
            <Textarea
              aria-label="Description" rows={3} value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Probabilité inhérente (1–5)</Label>
              <Select value={probabilite} onValueChange={setProbabilite}>
                <SelectTrigger aria-label="Probabilité inhérente (1–5)"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ECHELLE_1_5.map((n) => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Gravité inhérente (1–5)</Label>
              <Select value={gravite} onValueChange={setGravite}>
                <SelectTrigger aria-label="Gravité inhérente (1–5)"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ECHELLE_1_5.map((n) => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>Actions de traitement</Label>
            <Textarea
              aria-label="Actions de traitement" rows={2} value={actions}
              onChange={(e) => setActions(e.target.value)}
            />
          </div>
          <div>
            <Label>Date de revue</Label>
            <Input
              aria-label="Date de revue" type="date" value={dateRevue}
              onChange={(e) => setDateRevue(e.target.value)}
            />
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

// XQHS17 — saisie TERRAIN volontairement minimale.
// source-choix: qhse.ObservationSecurite.categorie
const OBSERVATION_CATEGORIES = [
  { value: 'epi', label: 'EPI' },
  { value: 'hauteur', label: 'Travail en hauteur' },
  { value: 'electrique', label: 'Électrique' },
  { value: 'manutention', label: 'Manutention' },
  { value: 'environnement', label: 'Environnement' },
  { value: 'autre', label: 'Autre' },
]
// source-choix: qhse.ObservationSecurite.type_observation
const OBSERVATION_TYPES = [
  { value: 'sur', label: 'Sûr' },
  { value: 'a_risque', label: 'À risque' },
]

// XQHS17 — capture rapide d'une observation BBS depuis le terrain. Le
// formulaire tient sur un écran mobile (champs empilés, une seule colonne),
// n'exige qu'une description et pose la date du jour par défaut. `company` et
// `observateur` sont posés côté serveur — jamais envoyés d'ici.
function CaptureObservationDialog({ onClose, onCreated }) {
  const [typeObservation, setTypeObservation] = useState('a_risque')
  const [categorie, setCategorie] = useState('autre')
  const [description, setDescription] = useState('')
  const [chantierId, setChantierId] = useState('')
  const [feedbackDonne, setFeedbackDonne] = useState(false)
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!description.trim()) { toast.error('La description est requise.'); return }
    setSaving(true)
    try {
      await qhseApi.observationsSecurite.create({
        type_observation: typeObservation,
        categorie,
        description: description.trim(),
        chantier_id: chantierId ? Number(chantierId) : null,
        feedback_donne: feedbackDonne,
        date_observation: new Date().toISOString().slice(0, 10),
      })
      toast.success('Observation enregistrée.')
      onCreated()
      onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Observation sécurité (capture rapide)</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Type d’observation</Label>
            <Select value={typeObservation} onValueChange={setTypeObservation}>
              <SelectTrigger aria-label="Type d’observation"><SelectValue /></SelectTrigger>
              <SelectContent>
                {OBSERVATION_TYPES.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Catégorie</Label>
            <Select value={categorie} onValueChange={setCategorie}>
              <SelectTrigger aria-label="Catégorie"><SelectValue /></SelectTrigger>
              <SelectContent>
                {OBSERVATION_CATEGORIES.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Ce que j’ai vu</Label>
            <Textarea
              aria-label="Ce que j’ai vu" rows={3} value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div>
            <Label>Chantier (id, optionnel)</Label>
            <Input
              aria-label="Chantier (id, optionnel)" inputMode="numeric"
              value={chantierId} onChange={(e) => setChantierId(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox" checked={feedbackDonne}
              onChange={(e) => setFeedbackDonne(e.target.checked)}
            />
            Feedback donné sur place
          </label>
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

// XQHS16 — création d'un lien de signalement QR public par chantier.
function CreerLienSignalementDialog({ onClose, onCreated }) {
  const [libelle, setLibelle] = useState('')
  const [chantierId, setChantierId] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!libelle.trim()) { toast.error('Le libellé est requis.'); return }
    setSaving(true)
    try {
      await qhseApi.liensSignalement.create({
        libelle: libelle.trim(),
        chantier_id: chantierId ? Number(chantierId) : null,
      })
      toast.success('Lien de signalement créé.')
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
        <DialogTitle>Nouveau lien de signalement QR</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Libellé</Label>
            <Input value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>
          <div>
            <Label>Chantier (id, optionnel)</Label>
            <Input value={chantierId} onChange={(e) => setChantierId(e.target.value)} inputMode="numeric" />
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

async function telechargerQr(lien) {
  const pending = downloadBlobInGesture()
  try {
    const res = await qhseApi.liensSignalement.qr(lien.id)
    pending.deliver(new Blob([res.data]), `signalement-qr-${lien.token?.slice(0, 8) || lien.id}.png`)
  } catch {
    toast.error('Génération QR indisponible.')
  }
}

// XQHS1 — checklist des étapes légales AT/MP (loi 18-12), dialog rattaché à
// une déclaration CNSS.
function EtapesDeclarationDialog({ declaration, onClose }) {
  const { rows, loading, reload } = useQhseList(
    () => qhseApi.etapesDeclarationAt.list({ declaration: declaration.id }),
    [declaration.id],
  )

  async function marquerFait(etape) {
    try {
      await qhseApi.etapesDeclarationAt.marquerFait(etape.id)
      toast.success('Étape marquée faite.')
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Enregistrement impossible.')
    }
  }

  const STATUT_TONE = { a_faire: 'warning', fait: 'success', hors_delai: 'danger' }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>
          Checklist légale AT/MP — {declaration.numero_declaration || `#${declaration.id}`}
        </DialogTitle>
        <div className="flex flex-col gap-2">
          {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {!loading && rows.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucune étape instanciée.</p>
          )}
          <ul className="flex flex-col gap-2">
            {rows.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-2 rounded-md border border-border p-2.5">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium">{e.type_etape_display || e.type_etape}</span>
                  <span className="text-xs text-muted-foreground">
                    Échéance {formatDate(e.echeance)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={STATUT_TONE[e.statut] ?? 'neutral'}>{e.statut_display || e.statut}</Badge>
                  {e.statut === 'a_faire' && (
                    <Button size="sm" variant="outline" onClick={() => marquerFait(e)}>
                      <CheckCircle2 size={14} /> Fait
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <div className="flex justify-end pt-1">
            <Button variant="outline" onClick={onClose}>Fermer</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/* ============================================================================
   UX32 — Risques, permis & incidents.
   ----------------------------------------------------------------------------
   Onglets :
   • Document unique : évaluations des risques (matrice criticité) + lignes.
   • Permis & consignation : permis de travail + LOTO.
   • Préparation site : inductions sécurité + plans d'urgence + secouristes.
   • Incidents : registre incidents + déclarations CNSS + analyses de cause.
   ========================================================================== */

const critTone = (c) => (c >= 15 ? 'danger' : c >= 8 ? 'warning' : 'info')

export default function Risques() {
  const [tab, setTab] = useState('document-unique')
  const [cnssChecklist, setCnssChecklist] = useState(null)
  const [creatingLien, setCreatingLien] = useState(false)
  const [liensReload, setLiensReload] = useState(0)

  // WIR126 — Permis & LOTO, Incidents : création + actions de cycle de vie.
  const [creatingPermis, setCreatingPermis] = useState(false)
  const [permisReload, setPermisReload] = useState(0)
  const [creatingLoto, setCreatingLoto] = useState(false)
  const [lotoPermisOptions, setLotoPermisOptions] = useState([])
  const [lotoReload, setLotoReload] = useState(0)
  const [creatingIncident, setCreatingIncident] = useState(false)
  const [incidentsReload, setIncidentsReload] = useState(0)

  // XQHS17 — capture rapide d'une observation BBS (le registre n'était
  // jusqu'ici qu'en lecture + conversion).
  const [creatingObservation, setCreatingObservation] = useState(false)
  const [observationsReload, setObservationsReload] = useState(0)

  // XQHS19 — incidents environnementaux : filtre « notifications en retard »,
  // relance en masse et clôture gatée (le serveur refuse si la notification
  // requise n'est pas faite).
  const [incidentsRetardOnly, setIncidentsRetardOnly] = useState(false)

  // XQHS14 — registre risques & opportunités niveau SMQ (ISO 6.1).
  const [creatingRo, setCreatingRo] = useState(false)
  const [roReload, setRoReload] = useState(0)
  const [roRevuesDues, setRoRevuesDues] = useState(false)

  // XQHS19 — la clôture est GATÉE côté serveur (400 si une notification
  // requise n'a pas été faite) : on remonte tel quel le motif du refus.
  async function cloturerIncident(incident) {
    try {
      await qhseApi.incidents.cloturer(incident.id)
      toast.success('Incident clôturé.')
      setIncidentsReload((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Clôture impossible.')
    }
  }

  async function relancerNotifications() {
    try {
      const res = await qhseApi.incidents.relancerNotifications()
      const nb = res?.data?.relances ?? 0
      toast.success(`${nb} relance(s) de notification envoyée(s).`)
      setIncidentsReload((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Relance impossible.')
    }
  }

  async function ouvrirCreationLoto() {
    try {
      const res = await qhseApi.permisTravail.list()
      setLotoPermisOptions(rowsFrom(res))
    } catch {
      setLotoPermisOptions([])
    }
    setCreatingLoto(true)
  }

  async function validerPermis(p) {
    try {
      await qhseApi.permisTravail.valider(p.id)
      toast.success('Permis validé.')
      setPermisReload((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    }
  }

  async function cloturerPermis(p) {
    try {
      await qhseApi.permisTravail.cloturer(p.id)
      toast.success('Permis clôturé.')
      setPermisReload((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Clôture impossible.')
    }
  }

  async function deconsignerLoto(l) {
    try {
      await qhseApi.consignationsLoto.deconsigner(l.id)
      toast.success('Consignation déconsignée.')
      setLotoReload((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Déconsignation impossible.')
    }
  }

  const evalCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 130, accessor: (r) => r.reference },
    { id: 'titre', header: 'Évaluation', accessor: (r) => r.titre },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'criticite_max', header: 'Criticité max', width: 130, align: 'center',
      accessor: (r) => r.criticite_max ?? 0,
      cell: (v) => <Badge tone={critTone(v)}>{v}</Badge>,
    },
    { id: 'nb_lignes', header: 'Lignes', width: 90, align: 'right', accessor: (r) => r.nb_lignes ?? 0 },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <EvalRisqueStatutPill status={v} />,
    },
  ], [])

  // XQHS14 — registre SMQ : criticité INHÉRENTE (avant traitement) et
  // RÉSIDUELLE (après), toutes deux calculées côté serveur.
  const roCols = useMemo(() => [
    { id: 'type', header: 'Type', width: 120, accessor: (r) => r.type_ro_display || r.type_ro },
    { id: 'processus', header: 'Processus', width: 170, accessor: (r) => r.processus || '—' },
    { id: 'description', header: 'Description', accessor: (r) => r.description },
    {
      id: 'criticite_inherente', header: 'Criticité inhérente', width: 160, align: 'center',
      accessor: (r) => r.criticite_inherente ?? 0,
      cell: (v) => <Badge tone={critTone(v)}>{v}</Badge>,
    },
    {
      id: 'criticite_residuelle', header: 'Criticité résiduelle', width: 160, align: 'center',
      accessor: (r) => r.criticite_residuelle,
      cell: (v) => (v == null ? '—' : <Badge tone={critTone(v)}>{v}</Badge>),
    },
    {
      id: 'date_revue', header: 'Revue', width: 120, align: 'right',
      accessor: (r) => r.date_revue, cell: (v) => formatDate(v),
    },
  ], [])

  const permisCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 120, accessor: (r) => r.reference },
    { id: 'titre', header: 'Permis', accessor: (r) => r.titre },
    { id: 'type', header: 'Type', width: 160, accessor: (r) => r.type_permis_display || r.type_permis },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => r.statut, cell: (v) => <PermisStatutPill status={v} />,
    },
    {
      id: 'date_fin', header: 'Fin validité', width: 130, align: 'right',
      accessor: (r) => r.date_fin, cell: (v) => formatDate(v),
    },
  ], [])

  const lotoCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 120, accessor: (r) => r.reference },
    { id: 'equipement', header: 'Équipement', accessor: (r) => r.equipement || '—' },
    { id: 'point', header: 'Point de consignation', accessor: (r) => r.point_consignation || '—' },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <LotoStatutPill status={v} />,
    },
  ], [])

  const inductionsCols = useMemo(() => [
    { id: 'personne', header: 'Personne', accessor: (r) => r.personne_nom || '—' },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'acquittement', header: 'Acquittée', width: 110, align: 'center',
      accessor: (r) => r.acquittement,
      cell: (v) => <Badge tone={v ? 'success' : 'warning'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
    {
      id: 'date_induction', header: 'Le', width: 120, align: 'right',
      accessor: (r) => r.date_induction, cell: (v) => formatDate(v),
    },
  ], [])

  const plansUrgenceCols = useMemo(() => [
    { id: 'titre', header: 'Plan d’urgence', accessor: (r) => r.titre },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    { id: 'point_rassemblement', header: 'Point de rassemblement', accessor: (r) => r.point_rassemblement || '—' },
    { id: 'nb_secouristes', header: 'Secouristes', width: 110, align: 'right', accessor: (r) => r.nb_secouristes ?? 0 },
  ], [])

  const secouristesCols = useMemo(() => [
    { id: 'nom', header: 'Secouriste', accessor: (r) => r.secouriste_nom || r.nom || '—' },
    { id: 'certification', header: 'Certification', accessor: (r) => r.certification || '—' },
    { id: 'telephone', header: 'Téléphone', width: 150, accessor: (r) => r.telephone || '—' },
    {
      id: 'validite', header: 'Validité', width: 120, align: 'right',
      accessor: (r) => r.validite, cell: (v) => formatDate(v),
    },
  ], [])

  const incidentsCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 120, accessor: (r) => r.reference },
    { id: 'titre', header: 'Incident', accessor: (r) => r.titre },
    {
      id: 'type', header: 'Type', width: 150,
      accessor: (r) => r.type_incident, cell: (v) => <IncidentTypePill status={v} />,
    },
    {
      id: 'gravite', header: 'Gravité', width: 120,
      accessor: (r) => r.gravite, cell: (v) => <GravitePill status={v} />,
    },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => r.statut, cell: (v) => <IncidentStatutPill status={v} />,
    },
    {
      id: 'date_incident', header: 'Date', width: 120, align: 'right',
      accessor: (r) => r.date_incident, cell: (v) => formatDate(v),
    },
    // XQHS19 — `notification_en_retard` est calculé côté serveur : une
    // notification requise et non faite dans le délai légal bloque la clôture.
    {
      id: 'notification', header: 'Notification', width: 150, align: 'center',
      accessor: (r) => (r.notification_requise
        ? (r.notification_en_retard ? 'retard' : 'ok')
        : ''),
      cell: (v) => {
        if (!v) return '—'
        return v === 'retard'
          ? <Badge tone="danger">En retard</Badge>
          : <Badge tone="success">À jour</Badge>
      },
    },
  ], [])

  const cnssCols = useMemo(() => [
    { id: 'numero', header: 'N° déclaration', accessor: (r) => r.numero_declaration || '—' },
    {
      id: 'date_accident', header: 'Accident', width: 120, align: 'right',
      accessor: (r) => r.date_accident, cell: (v) => formatDate(v),
    },
    {
      id: 'date_limite', header: 'Échéance légale', width: 150, align: 'right',
      accessor: (r) => r.date_limite, cell: (v) => formatDate(v),
    },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <CnssStatutPill status={v} />,
    },
  ], [])

  const analysesCols = useMemo(() => [
    { id: 'incident', header: 'Incident', accessor: (r) => r.incident_reference || r.incident },
    { id: 'methode', header: 'Méthode', width: 180, accessor: (r) => r.methode_display || r.methode },
    { id: 'nb_causes', header: 'Causes', width: 90, align: 'right', accessor: (r) => r.nb_causes ?? 0 },
    { id: 'nb_capa', header: 'CAPA', width: 80, align: 'right', accessor: (r) => r.nb_capa ?? 0 },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut_display || r.statut },
  ], [])

  // XQHS18 — exercices d'urgence (drills) rattachés aux plans d'urgence.
  const exercicesUrgenceCols = useMemo(() => [
    { id: 'plan', header: 'Plan d’urgence', accessor: (r) => r.plan_titre || r.plan },
    { id: 'type', header: 'Type', width: 150, accessor: (r) => r.type_exercice_display || r.type_exercice },
    {
      id: 'date_prevue', header: 'Prévu le', width: 120, align: 'right',
      accessor: (r) => r.date_prevue, cell: (v) => formatDate(v),
    },
    {
      id: 'date_realisee', header: 'Réalisé le', width: 120, align: 'right',
      accessor: (r) => r.date_realisee, cell: (v) => (v ? formatDate(v) : '—'),
    },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut_display || r.statut },
  ], [])

  // XQHS16 — liens de signalement QR public + signalements reçus.
  const liensCols = useMemo(() => [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'actif', header: 'Actif', width: 90, align: 'center',
      accessor: (r) => r.actif,
      cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
    { id: 'token', header: 'Jeton', width: 130, accessor: (r) => `${(r.token || '').slice(0, 8)}…` },
  ], [])

  const signalementsCols = useMemo(() => [
    {
      id: 'date', header: 'Reçu le', width: 130, align: 'right',
      accessor: (r) => r.date_creation, cell: (v) => formatDate(v),
    },
    { id: 'type', header: 'Type', width: 120, accessor: (r) => r.type_signalement_display || r.type_signalement },
    { id: 'description', header: 'Description', accessor: (r) => r.description },
    {
      id: 'anonyme', header: 'Anonyme', width: 100, align: 'center',
      accessor: (r) => r.anonyme,
      cell: (v) => <Badge tone={v ? 'neutral' : 'info'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  // XQHS17 — observations sécurité comportementales (BBS).
  const observationsCols = useMemo(() => [
    {
      id: 'date_observation', header: 'Date', width: 120, align: 'right',
      accessor: (r) => r.date_observation, cell: (v) => formatDate(v),
    },
    { id: 'categorie', header: 'Catégorie', width: 130, accessor: (r) => r.categorie_display || r.categorie },
    { id: 'type', header: 'Type', width: 130, accessor: (r) => r.type_observation_display || r.type_observation },
    { id: 'description', header: 'Description', accessor: (r) => r.description },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'feedback_donne', header: 'Feedback donné', width: 130, align: 'center',
      accessor: (r) => r.feedback_donne,
      cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2 className="flex items-center gap-2">
          <ShieldAlert size={20} strokeWidth={1.75} aria-hidden="true" />
          Risques, permis & incidents
        </h2>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="document-unique">Document unique</TabsTrigger>
          <TabsTrigger value="risques-opportunites">Risques & opportunités</TabsTrigger>
          <TabsTrigger value="permis">Permis & LOTO</TabsTrigger>
          <TabsTrigger value="preparation">Préparation site</TabsTrigger>
          <TabsTrigger value="incidents">Incidents</TabsTrigger>
          <TabsTrigger value="observations">Observations BBS</TabsTrigger>
          <TabsTrigger value="signalement-qr">Signalement QR</TabsTrigger>
        </TabsList>

        <TabsContent value="document-unique" className="mt-4">
          <QhseResourceList
            title="Évaluations des risques (document unique)"
            subtitle="Matrice de criticité gravité × probabilité"
            fetcher={() => qhseApi.evaluationsRisque.list()}
            columns={evalCols}
            exportName="qhse-evaluations-risque"
          />
        </TabsContent>

        <TabsContent value="risques-opportunites" className="mt-4">
          <QhseResourceList
            title="Risques & opportunités (SMQ)"
            subtitle="Niveau entreprise/processus (ISO 6.1) — distinct du document unique chantier"
            fetcher={() => (roRevuesDues
              ? qhseApi.risquesOpportunites.revuesDues()
              : qhseApi.risquesOpportunites.list())}
            columns={roCols}
            exportName="qhse-risques-opportunites"
            deps={[roReload, roRevuesDues]}
            actions={(
              <>
                <Button
                  variant={roRevuesDues ? 'default' : 'outline'}
                  onClick={() => setRoRevuesDues((v) => !v)}
                >
                  <ListChecks size={16} /> Revues dues
                </Button>
                <Button onClick={() => setCreatingRo(true)}>
                  <Plus size={16} /> Nouveau risque / opportunité
                </Button>
              </>
            )}
          />
        </TabsContent>

        <TabsContent value="permis" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Permis de travail"
            subtitle="Hauteur, point chaud, espace confiné…"
            fetcher={() => qhseApi.permisTravail.list()}
            columns={permisCols}
            exportName="qhse-permis-travail"
            deps={[permisReload]}
            actions={
              <Button onClick={() => setCreatingPermis(true)}>
                <Plus size={16} /> Nouveau permis
              </Button>
            }
            rowActions={(r) => [
              ...(r.statut === 'brouillon'
                ? [{ id: 'valider', label: 'Valider', icon: CheckCircle2, onClick: () => validerPermis(r) }]
                : []),
              ...(r.statut === 'brouillon' || r.statut === 'valide'
                ? [{ id: 'cloturer', label: 'Clôturer', icon: XCircle, onClick: () => cloturerPermis(r) }]
                : []),
            ]}
          />
          <QhseResourceList
            title="Consignations LOTO"
            fetcher={() => qhseApi.consignationsLoto.list()}
            columns={lotoCols}
            exportName="qhse-loto"
            deps={[lotoReload]}
            actions={
              <Button onClick={ouvrirCreationLoto}>
                <Lock size={16} /> Nouvelle consignation
              </Button>
            }
            rowActions={(r) => (
              r.statut === 'consignee'
                ? [{ id: 'deconsigner', label: 'Déconsigner', icon: LockOpen, onClick: () => deconsignerLoto(r) }]
                : []
            )}
          />
        </TabsContent>

        <TabsContent value="preparation" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Inductions sécurité"
            subtitle="Accueils sécurité (internes & sous-traitants)"
            fetcher={() => qhseApi.inductionsSecurite.list()}
            columns={inductionsCols}
            exportName="qhse-inductions"
          />
          <QhseResourceList
            title="Plans d’urgence"
            fetcher={() => qhseApi.plansUrgence.list()}
            columns={plansUrgenceCols}
            exportName="qhse-plans-urgence"
          />
          <QhseResourceList
            title="Secouristes"
            fetcher={() => qhseApi.secouristes.list()}
            columns={secouristesCols}
            exportName="qhse-secouristes"
          />
          <QhseResourceList
            title="Exercices d'urgence (drills)"
            subtitle="Exigence ISO 45001 8.2 — exercices rattachés aux plans d'urgence"
            fetcher={() => qhseApi.exercicesUrgence.list()}
            columns={exercicesUrgenceCols}
            exportName="qhse-exercices-urgence"
          />
        </TabsContent>

        <TabsContent value="incidents" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Registre des incidents HSE"
            subtitle="Accidents, presqu’accidents, incidents"
            fetcher={() => (incidentsRetardOnly
              ? qhseApi.incidents.notificationsEnRetard()
              : qhseApi.incidents.list())}
            columns={incidentsCols}
            exportName="qhse-incidents"
            deps={[incidentsReload, incidentsRetardOnly]}
            actions={(
              <>
                <Button
                  variant={incidentsRetardOnly ? 'default' : 'outline'}
                  onClick={() => setIncidentsRetardOnly((v) => !v)}
                >
                  <AlertOctagon size={16} /> Notifications en retard
                </Button>
                <Button variant="outline" onClick={relancerNotifications}>
                  <ListChecks size={16} /> Relancer
                </Button>
                <Button onClick={() => setCreatingIncident(true)}>
                  <Plus size={16} /> Déclarer un incident
                </Button>
              </>
            )}
            rowActions={(r) => (
              r.statut === 'clos'
                ? []
                : [{
                  id: 'cloturer', label: 'Clôturer', icon: XCircle,
                  onClick: () => cloturerIncident(r),
                }]
            )}
          />
          <QhseResourceList
            title="Déclarations CNSS"
            subtitle="Accidents du travail — échéance légale"
            fetcher={() => qhseApi.declarationsCnss.list()}
            columns={cnssCols}
            exportName="qhse-cnss"
            rowActions={(r) => [
              {
                id: 'checklist', label: 'Checklist légale AT/MP', icon: ListChecks,
                onClick: () => setCnssChecklist(r),
              },
            ]}
          />
          <QhseResourceList
            title="Analyses d’incident"
            subtitle="Arbre des causes → CAPA"
            fetcher={() => qhseApi.analysesIncident.list()}
            columns={analysesCols}
            exportName="qhse-analyses-incident"
            rowActions={(r) => [
              {
                id: 'capa', label: 'Générer CAPA', icon: Wrench,
                onClick: async () => {
                  try {
                    await qhseApi.analysesIncident.genererCapa(r.id)
                    toast.success('CAPA générée depuis l’analyse.')
                  } catch (err) {
                    toast.error(err?.response?.data?.detail ?? 'Génération impossible.')
                  }
                },
              },
            ]}
          />
        </TabsContent>

        <TabsContent value="observations" className="mt-4">
          <QhseResourceList
            title="Observations sécurité comportementales (BBS)"
            subtitle="Capture terrain rapide — conversion en un clic vers CAPA/NCR"
            fetcher={() => qhseApi.observationsSecurite.list()}
            columns={observationsCols}
            exportName="qhse-observations-securite"
            deps={[observationsReload]}
            actions={
              <Button onClick={() => setCreatingObservation(true)}>
                <Plus size={16} /> Nouvelle observation
              </Button>
            }
            rowActions={(r) => [
              {
                id: 'capa', label: 'Convertir en CAPA', icon: Wrench,
                onClick: async () => {
                  try {
                    await qhseApi.observationsSecurite.convertirCapa(r.id, {})
                    toast.success('CAPA créée depuis l’observation.')
                  } catch (err) {
                    toast.error(err?.response?.data?.detail ?? 'Conversion impossible.')
                  }
                },
              },
              {
                id: 'ncr', label: 'Convertir en NCR', icon: AlertOctagon,
                onClick: async () => {
                  try {
                    await qhseApi.observationsSecurite.convertirNcr(r.id, {})
                    toast.success('NCR créée depuis l’observation.')
                  } catch (err) {
                    toast.error(err?.response?.data?.detail ?? 'Conversion impossible.')
                  }
                },
              },
            ]}
          />
        </TabsContent>

        <TabsContent value="signalement-qr" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Liens de signalement QR"
            subtitle="Signalement danger/incident chantier sans compte — imprimer le QR sur site"
            fetcher={() => qhseApi.liensSignalement.list()}
            columns={liensCols}
            exportName="qhse-liens-signalement"
            deps={[liensReload]}
            actions={
              <Button onClick={() => setCreatingLien(true)}>
                <Plus size={16} /> Nouveau lien
              </Button>
            }
            rowActions={(r) => [
              { id: 'qr', label: 'Générer QR', icon: QrCode, onClick: () => telechargerQr(r) },
            ]}
          />
          <QhseResourceList
            title="Signalements reçus"
            subtitle="Danger/incident signalés via QR chantier (lecture interne)"
            fetcher={() => qhseApi.signalementsPublics.list()}
            columns={signalementsCols}
            exportName="qhse-signalements-publics"
          />
        </TabsContent>
      </Tabs>

      {creatingLien && (
        <CreerLienSignalementDialog
          onClose={() => setCreatingLien(false)}
          onCreated={() => setLiensReload((n) => n + 1)}
        />
      )}

      {cnssChecklist && (
        <EtapesDeclarationDialog
          declaration={cnssChecklist}
          onClose={() => setCnssChecklist(null)}
        />
      )}

      {creatingPermis && (
        <CreerPermisDialog
          onClose={() => setCreatingPermis(false)}
          onCreated={() => setPermisReload((n) => n + 1)}
        />
      )}

      {creatingLoto && (
        <CreerLotoDialog
          permis={lotoPermisOptions}
          onClose={() => setCreatingLoto(false)}
          onCreated={() => setLotoReload((n) => n + 1)}
        />
      )}

      {creatingIncident && (
        <CreerIncidentDialog
          onClose={() => setCreatingIncident(false)}
          onCreated={() => setIncidentsReload((n) => n + 1)}
        />
      )}

      {creatingRo && (
        <CreerRisqueOpportuniteDialog
          onClose={() => setCreatingRo(false)}
          onCreated={() => setRoReload((n) => n + 1)}
        />
      )}

      {creatingObservation && (
        <CaptureObservationDialog
          onClose={() => setCreatingObservation(false)}
          onCreated={() => setObservationsReload((n) => n + 1)}
        />
      )}
    </div>
  )
}
