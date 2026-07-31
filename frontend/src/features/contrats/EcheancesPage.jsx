import { useEffect, useMemo, useState } from 'react'
import { BellRing, Plus } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import {
  Card, Badge, Button, Tabs, TabsList, TabsTrigger, TabsContent, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea,
} from '../../ui'
import { EcheanceCenter } from '../../ui/module'
import { formatDate } from '../../lib/format'
import SimpleTable from './SimpleTable'
import {
  StatutAlerte, StatutJalon, StatutObligation, CONTRAT_TYPES,
} from './status'

/* ============================================================================
   UX36 — Échéances & alertes.
   ----------------------------------------------------------------------------
   Centre d'échéances (préavis CONTRAT20 + à renouveler CONTRAT21) via
   EcheanceCenter, plus onglets : alertes planifiées (CONTRAT22), jalons
   (CONTRAT26), obligations à faire (CONTRAT26), SLA (CONTRAT27) et règles
   d'approbation (CONTRAT13). Lecture + quelques actions déclencheur.

   WIR74 — les 4 onglets Règles d'approbation / Jalons / Obligations / SLA
   étaient lecture seule alors que `createRegleApprobation`/`createJalon`/
   `createObligation`/`createSla` (+`penaliteSla`) sont exposés par
   contratsApi.js : sans règle d'approbation, « Lancer l'approbation »
   (ContratDetail.jsx) échoue systématiquement sur une société neuve. Ajoute un
   bouton « Nouveau » + un dialogue de création par onglet — même patron que
   `ContratDetail.jsx` (Dialog + `errMsg`), aucune donnée interne (prix
   d'achat/marge) jamais demandée.
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const NIVEAUX_APPROBATION = [
  { value: 'responsable', label: 'Responsable' },
  { value: 'administrateur', label: 'Administrateur' },
  { value: 'direction', label: 'Direction' },
]

const REDEVABLES = [
  { value: 'prestataire', label: 'Prestataire' },
  { value: 'client', label: 'Client' },
  { value: 'autre', label: 'Autre' },
]

const MODES_PENALITE = [
  { value: 'fixe', label: 'Montant fixe' },
  { value: 'pourcentage', label: 'Pourcentage du montant du contrat' },
]

export default function EcheancesPage() {
  const [preavis, setPreavis] = useState([])
  const [renouveler, setRenouveler] = useState([])
  const [alertes, setAlertes] = useState([])
  const [jalons, setJalons] = useState([])
  const [obligations, setObligations] = useState([])
  const [sla, setSla] = useState([])
  const [regles, setRegles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // WIR74 — liste des contrats pour le sélecteur des dialogues de création
  // (Jalon/Obligation/SLA sont rattachés à UN contrat ; Règle d'approbation
  // est globale à la société, aucun sélecteur nécessaire).
  const [contrats, setContrats] = useState([])
  const [dialog, setDialog] = useState(null) // 'regle' | 'jalon' | 'obligation' | 'sla'

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([
      contratsApi.getPreavis().then((r) => setPreavis(Array.isArray(r.data) ? r.data : listData(r))),
      contratsApi.getARenouveler().then((r) => setRenouveler(Array.isArray(r.data) ? r.data : listData(r))),
      contratsApi.getAlertes().then((r) => setAlertes(listData(r))),
      contratsApi.getJalons().then((r) => setJalons(listData(r))),
      contratsApi.getObligations().then((r) => setObligations(listData(r))),
      contratsApi.getSla().then((r) => setSla(listData(r))),
      contratsApi.getReglesApprobation().then((r) => setRegles(listData(r))),
      contratsApi.getContrats({ page_size: 200 }).then((r) => setContrats(listData(r))),
    ])
      .catch(() => setError('Impossible de charger les échéances.'))
      .finally(() => setLoading(false))
  }

  const onCreated = (message) => {
    setDialog(null)
    toast.success(message)
    load()
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  // Fusionne préavis + échéances en items du centre d'échéances.
  const echeanceItems = useMemo(() => {
    const items = []
    for (const c of preavis) {
      items.push({
        id: `preavis-${c.id}`,
        label: c.reference || c.objet || `Contrat #${c.id}`,
        meta: 'Préavis à traiter',
        daysLeft: c.jours_avant_preavis,
        to: `/contrats/${c.id}`,
      })
    }
    for (const c of renouveler) {
      items.push({
        id: `renew-${c.id}`,
        label: c.reference || c.objet || `Contrat #${c.id}`,
        meta: 'À renouveler / clôturer',
        daysLeft: c.jours_avant_echeance,
        to: `/contrats/${c.id}`,
      })
    }
    return items
  }, [preavis, renouveler])

  const declencher = async () => {
    try {
      const res = await contratsApi.declencherAlertes()
      toast.success(`${res.data?.nb_envoyees ?? 0} alerte(s) envoyée(s).`)
      load()
    } catch { toast.error('Déclenchement impossible.') }
  }

  const semer = async () => {
    try {
      const res = await contratsApi.semerAlertes(30)
      toast.success(`${res.data?.nb_creees ?? 0} alerte(s) créée(s).`)
      load()
    } catch { toast.error('Génération impossible.') }
  }

  const marquerJalon = async (jalonId) => {
    try {
      await contratsApi.marquerJalonAtteint(jalonId)
      toast.success('Jalon marqué atteint.')
      load()
    } catch { toast.error('Action impossible.') }
  }

  const marquerObligation = async (oblId) => {
    try {
      await contratsApi.marquerObligationFaite(oblId)
      toast.success('Obligation marquée réalisée.')
      load()
    } catch { toast.error('Action impossible.') }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BellRing className="size-5 text-muted-foreground" aria-hidden="true" />
          <h1 className="font-display text-xl font-semibold tracking-tight">Échéances &amp; alertes</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={semer}>Générer les alertes</Button>
          <Button size="sm" onClick={declencher}>Déclencher les alertes dues</Button>
        </div>
      </div>

      <EcheanceCenter
        title="Contrats à échéance (préavis + renouvellement)"
        items={echeanceItems}
        loading={loading}
        error={error}
        emptyText="Aucune échéance dans la fenêtre à venir."
      />

      <Tabs defaultValue="alertes">
        <TabsList className="flex-wrap">
          <TabsTrigger value="alertes">Alertes ({alertes.length})</TabsTrigger>
          <TabsTrigger value="jalons">Jalons ({jalons.length})</TabsTrigger>
          <TabsTrigger value="obligations">Obligations ({obligations.length})</TabsTrigger>
          <TabsTrigger value="sla">SLA ({sla.length})</TabsTrigger>
          <TabsTrigger value="regles">Approbation ({regles.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="alertes">
          <SimpleTable
            emptyText="Aucune alerte planifiée."
            rows={alertes}
            columns={[
              { header: 'Contrat', cell: (a) => <span className="font-mono text-xs">#{a.contrat}</span> },
              { header: 'Type', cell: (a) => a.type_alerte_display || a.type_alerte },
              { header: 'Déclenchement', cell: (a) => (a.date_declenchement ? formatDate(a.date_declenchement) : '—') },
              { header: 'Statut', cell: (a) => <StatutAlerte status={a.statut} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="jalons">
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setDialog('jalon')}><Plus /> Nouveau jalon</Button>
          </div>
          <SimpleTable
            emptyText="Aucun jalon."
            rows={jalons}
            columns={[
              { header: 'N°', cell: (j) => <span className="font-mono">#{j.numero}</span> },
              { header: 'Intitulé', cell: (j) => <span className="font-medium">{j.intitule}</span> },
              { header: 'Cible', cell: (j) => (j.date_cible ? formatDate(j.date_cible) : '—') },
              { header: 'Statut', cell: (j) => <StatutJalon status={j.statut} /> },
              { header: '', cell: (j) => (j.statut !== 'atteint' ? (
                <Button variant="outline" size="sm" onClick={() => marquerJalon(j.id)}>Marquer atteint</Button>
              ) : <span className="text-xs text-muted-foreground">✓</span>), align: 'right' },
            ]}
          />
        </TabsContent>

        <TabsContent value="obligations">
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setDialog('obligation')}><Plus /> Nouvelle obligation</Button>
          </div>
          <SimpleTable
            emptyText="Aucune obligation."
            rows={obligations}
            columns={[
              { header: 'Intitulé', cell: (o) => <span className="font-medium">{o.intitule}</span> },
              { header: 'Redevable', cell: (o) => o.redevable_display || o.redevable },
              { header: 'Échéance', cell: (o) => (o.date_echeance ? formatDate(o.date_echeance) : '—') },
              { header: 'Statut', cell: (o) => <StatutObligation status={o.statut} /> },
              { header: '', cell: (o) => (o.statut !== 'faite' ? (
                <Button variant="outline" size="sm" onClick={() => marquerObligation(o.id)}>Marquer faite</Button>
              ) : <span className="text-xs text-muted-foreground">✓</span>), align: 'right' },
            ]}
          />
        </TabsContent>

        <TabsContent value="sla">
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setDialog('sla')}><Plus /> Nouvel engagement SLA</Button>
          </div>
          <SimpleTable
            emptyText="Aucun engagement SLA."
            rows={sla}
            columns={[
              { header: 'Libellé', cell: (s) => <span className="font-medium">{s.libelle}</span> },
              { header: 'Taux cible', cell: (s) => (s.taux_cible != null ? `${s.taux_cible} %` : '—') },
              { header: 'Pénalité', cell: (s) => s.mode_penalite_display || s.mode_penalite },
              { header: 'Actif', cell: (s) => <Badge tone={s.actif ? 'success' : 'neutral'}>{s.actif ? 'Actif' : 'Inactif'}</Badge> },
            ]}
          />
        </TabsContent>

        <TabsContent value="regles">
          <Card className="mb-3 border-info/40 bg-info/5 p-3 text-sm text-muted-foreground">
            Workflow d’approbation interne : la règle ACTIVE la plus spécifique (montant + type) instancie les étapes du contrat.
          </Card>
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setDialog('regle')}><Plus /> Nouvelle règle d’approbation</Button>
          </div>
          <SimpleTable
            emptyText="Aucune règle d’approbation."
            rows={regles}
            columns={[
              { header: 'Libellé', cell: (r) => <span className="font-medium">{r.libelle}</span> },
              { header: 'Type', cell: (r) => r.type_contrat_display || r.type_contrat || 'Tous' },
              { header: 'Bornes', cell: (r) => `${r.montant_min ?? '—'} → ${r.montant_max ?? '∞'}` },
              { header: 'Niveau', cell: (r) => r.niveau_approbation_display || r.niveau_approbation },
              { header: 'Actif', cell: (r) => <Badge tone={r.actif ? 'success' : 'neutral'}>{r.actif ? 'Actif' : 'Inactif'}</Badge> },
            ]}
          />
        </TabsContent>
      </Tabs>

      {dialog === 'regle' && (
        <RegleApprobationDialog
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Règle d’approbation créée.')}
        />
      )}
      {dialog === 'jalon' && (
        <JalonDialog
          contrats={contrats}
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Jalon créé.')}
        />
      )}
      {dialog === 'obligation' && (
        <ObligationDialog
          contrats={contrats}
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Obligation créée.')}
        />
      )}
      {dialog === 'sla' && (
        <SlaDialog
          contrats={contrats}
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Engagement SLA créé.')}
        />
      )}
    </div>
  )
}

// WIR74 — sélecteur de contrat commun aux 3 dialogues rattachés (Jalon,
// Obligation, SLA) : un <select> natif (pas de Radix Select) — même patron
// que ContratsList.jsx::CreateContratDialog (léger, sans portail, testable).
function ContratSelect({ id, contrats, value, onChange }) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border border-border bg-card px-3 text-sm"
    >
      <option value="">Choisir un contrat…</option>
      {contrats.map((c) => (
        <option key={c.id} value={c.id}>{c.reference || c.objet || `Contrat #${c.id}`}</option>
      ))}
    </select>
  )
}

// WIR74 — règle d'approbation (CONTRAT13). Aucun contrat rattaché (règle
// globale à la société) : seul `libelle` est requis côté backend
// (`RegleApprobationSerializer`), tout le reste a un défaut serveur.
function RegleApprobationDialog({ onClose, onDone }) {
  const [libelle, setLibelle] = useState('')
  const [typeContrat, setTypeContrat] = useState('')
  const [montantMin, setMontantMin] = useState('')
  const [montantMax, setMontantMax] = useState('')
  const [niveau, setNiveau] = useState('responsable')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!libelle.trim()) { setErr('Le libellé est requis.'); return }
    setSaving(true)
    setErr(null)
    const data = { libelle: libelle.trim(), niveau_approbation: niveau }
    if (typeContrat) data.type_contrat = typeContrat
    if (montantMin !== '') data.montant_min = Number(montantMin)
    if (montantMax !== '') data.montant_max = Number(montantMax)
    try {
      await contratsApi.createRegleApprobation(data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvelle règle d’approbation</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ra-libelle" required>Libellé</Label>
            <Input id="ra-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="ex. Approbation grands montants" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ra-type">Type de contrat ciblé</Label>
            <select
              id="ra-type"
              value={typeContrat}
              onChange={(e) => setTypeContrat(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">Tous types</option>
              {CONTRAT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ra-min">Montant min</Label>
              <Input id="ra-min" type="number" step="any" value={montantMin} onChange={(e) => setMontantMin(e.target.value)} placeholder="Optionnel" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ra-max">Montant max</Label>
              <Input id="ra-max" type="number" step="any" value={montantMax} onChange={(e) => setMontantMax(e.target.value)} placeholder="Optionnel" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ra-niveau">Niveau d’approbation requis</Label>
            <select
              id="ra-niveau"
              value={niveau}
              onChange={(e) => setNiveau(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {NIVEAUX_APPROBATION.map((n) => (
                <option key={n.value} value={n.value}>{n.label}</option>
              ))}
            </select>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer la règle'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR74 — jalon (CONTRAT26). `contrat` + `intitule` requis ; `numero` est
// calculé côté serveur (services.creer_jalon, max+1 sous verrou de ligne).
function JalonDialog({ contrats, onClose, onDone }) {
  const [contrat, setContrat] = useState('')
  const [intitule, setIntitule] = useState('')
  const [description, setDescription] = useState('')
  const [dateCible, setDateCible] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!contrat) { setErr('Le contrat est requis.'); return }
    if (!intitule.trim()) { setErr("L'intitulé est requis."); return }
    setSaving(true)
    setErr(null)
    const data = { contrat: Number(contrat), intitule: intitule.trim() }
    if (description.trim()) data.description = description.trim()
    if (dateCible) data.date_cible = dateCible
    try {
      await contratsApi.createJalon(data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau jalon</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-contrat" required>Contrat</Label>
            <ContratSelect id="ja-contrat" contrats={contrats} value={contrat} onChange={setContrat} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-intitule" required>Intitulé</Label>
            <Input id="ja-intitule" value={intitule} onChange={(e) => setIntitule(e.target.value)} placeholder="ex. Mise en service" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-desc">Description</Label>
            <Textarea id="ja-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-cible">Date cible</Label>
            <Input id="ja-cible" type="date" value={dateCible} onChange={(e) => setDateCible(e.target.value)} />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le jalon'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR74 — obligation / livrable (CONTRAT26). `contrat` + `intitule` requis ;
// le rattachement optionnel à un jalon reste possible plus tard côté détail
// contrat (non demandé ici — seul `Done =` : créer l'obligation).
function ObligationDialog({ contrats, onClose, onDone }) {
  const [contrat, setContrat] = useState('')
  const [intitule, setIntitule] = useState('')
  const [description, setDescription] = useState('')
  const [redevable, setRedevable] = useState('prestataire')
  const [dateEcheance, setDateEcheance] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!contrat) { setErr('Le contrat est requis.'); return }
    if (!intitule.trim()) { setErr("L'intitulé est requis."); return }
    setSaving(true)
    setErr(null)
    const data = { contrat: Number(contrat), intitule: intitule.trim(), redevable }
    if (description.trim()) data.description = description.trim()
    if (dateEcheance) data.date_echeance = dateEcheance
    try {
      await contratsApi.createObligation(data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvelle obligation</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ob-contrat" required>Contrat</Label>
            <ContratSelect id="ob-contrat" contrats={contrats} value={contrat} onChange={setContrat} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ob-intitule" required>Intitulé</Label>
            <Input id="ob-intitule" value={intitule} onChange={(e) => setIntitule(e.target.value)} placeholder="ex. Remise du dossier ONEE" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ob-desc">Description</Label>
            <Textarea id="ob-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ob-redevable">Redevable</Label>
              <select
                id="ob-redevable"
                value={redevable}
                onChange={(e) => setRedevable(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {REDEVABLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ob-echeance">Échéance</Label>
              <Input id="ob-echeance" type="date" value={dateEcheance} onChange={(e) => setDateEcheance(e.target.value)} />
            </div>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : "Créer l'obligation"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR74 — engagement SLA (CONTRAT27). `contrat` + `libelle` requis ; le
// reste (taux/pénalité) a un défaut serveur — `penaliteSla` (calcul déclaratif
// de la pénalité encourue) reste une action du détail contrat, hors scope ici.
function SlaDialog({ contrats, onClose, onDone }) {
  const [contrat, setContrat] = useState('')
  const [libelle, setLibelle] = useState('')
  const [tauxCible, setTauxCible] = useState('')
  const [unite, setUnite] = useState('')
  const [modePenalite, setModePenalite] = useState('fixe')
  const [valeurPenalite, setValeurPenalite] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!contrat) { setErr('Le contrat est requis.'); return }
    if (!libelle.trim()) { setErr('Le libellé est requis.'); return }
    setSaving(true)
    setErr(null)
    const data = { contrat: Number(contrat), libelle: libelle.trim(), mode_penalite: modePenalite }
    if (tauxCible !== '') data.taux_cible = Number(tauxCible)
    if (unite.trim()) data.unite = unite.trim()
    if (valeurPenalite !== '') data.valeur_penalite = Number(valeurPenalite)
    try {
      await contratsApi.createSla(data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvel engagement SLA</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sl-contrat" required>Contrat</Label>
            <ContratSelect id="sl-contrat" contrats={contrats} value={contrat} onChange={setContrat} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sl-libelle" required>Libellé</Label>
            <Input id="sl-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="ex. Disponibilité ≥ 98 %" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sl-taux">Taux cible (%)</Label>
              <Input id="sl-taux" type="number" step="any" value={tauxCible} onChange={(e) => setTauxCible(e.target.value)} placeholder="ex. 98" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sl-unite">Unité / métrique</Label>
              <Input id="sl-unite" value={unite} onChange={(e) => setUnite(e.target.value)} placeholder="ex. disponibilité" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sl-mode">Mode de pénalité</Label>
              <select
                id="sl-mode"
                value={modePenalite}
                onChange={(e) => setModePenalite(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {MODES_PENALITE.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sl-valeur">Valeur de la pénalité</Label>
              <Input id="sl-valeur" type="number" step="any" value={valeurPenalite} onChange={(e) => setValeurPenalite(e.target.value)} placeholder="Optionnel" />
            </div>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : "Créer l'engagement"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
