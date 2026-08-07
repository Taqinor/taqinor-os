import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock, Info, Plus } from 'lucide-react'
import veilleAoApi from '../../api/veilleAoApi'
import useResource from '../../hooks/useResource'
import {
  Card, Badge, Button, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   VAO37 — Bandeau de santé de la collecte + la carte d'honnêteté.
   ----------------------------------------------------------------------------
   Deux blocs INDISSOCIABLES (texte de tâche) : (1) santé — dernière collecte
   réussie et son ÂGE, alarme de silence (VAO24) EN ÉVIDENCE, avis examinés
   hier ; (2) honnêteté — la veille ne promet JAMAIS l'exhaustivité (c'est
   l'erreur qui a coûté l'AO FRDISI, préambule du Groupe VAO). Données via
   `veilleAoApi.sante()` (appel agrégé unique) — zéro calcul de KPI côté front.
   ========================================================================== */

const INFORMATEURS = [
  { value: 'partenaire', label: 'Partenaire' },
  { value: 'client', label: 'Client' },
  { value: 'employe', label: 'Employé' },
  { value: 'presse', label: 'Presse' },
  { value: 'autre', label: 'Autre' },
]

// VAO37 (Done=) — logique PURE, testable hors React : « l'âge de la dernière
// collecte est visible sans clic » exige un libellé, pas une date brute.
export function ageLabel(iso, now = new Date()) {
  if (!iso) return null
  const d = new Date(iso)
  const base = now instanceof Date ? now : new Date(now)
  if (Number.isNaN(d.getTime()) || Number.isNaN(base.getTime())) return null
  const ms = base.getTime() - d.getTime()
  if (ms < 0) return 'à l’instant'
  const heures = Math.floor(ms / (1000 * 60 * 60))
  if (heures < 1) return 'à l’instant'
  if (heures < 24) return `il y a ${heures} h`
  const jours = Math.floor(heures / 24)
  return `il y a ${jours} j`
}

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

// VAO27 — capter en 30 s un AO reçu par WhatsApp/SMS/appel, AVEC sa source.
// Seul `informateur` bloque (VAO27 Done= : « 400 FR sinon ») — tout le reste
// est facultatif, aucune validation qui bloque une saisie faite du chantier.
function AjouterAvisDialog({ onClose, onDone }) {
  const [objet, setObjet] = useState('')
  const [acheteur, setAcheteur] = useState('')
  const [dateLimite, setDateLimite] = useState('')
  const [informateur, setInformateur] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!informateur) { setErr('Qui vous l’a signalé ? (informateur requis)'); return }
    setSaving(true)
    setErr(null)
    try {
      await veilleAoApi.avis.create({
        objet: objet.trim() || undefined,
        acheteur: acheteur.trim() || undefined,
        date_limite: dateLimite || undefined,
        informateur,
        source: 'tuyau_partenaire',
      })
      toast.success('Avis ajouté au sas.')
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Impossible d’ajouter cet avis.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Ajouter un avis reçu par WhatsApp, SMS ou appel</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="aa-objet">Objet</Label>
            <Input id="aa-objet" value={objet} onChange={(e) => setObjet(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="aa-acheteur">Acheteur</Label>
            <Input id="aa-acheteur" value={acheteur} onChange={(e) => setAcheteur(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="aa-date-limite">Date limite</Label>
            <Input id="aa-date-limite" type="date" value={dateLimite} onChange={(e) => setDateLimite(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="aa-informateur">Qui vous l’a signalé ?</Label>
            <Select value={informateur} onValueChange={setInformateur}>
              <SelectTrigger id="aa-informateur" aria-label="Informateur"><SelectValue placeholder="Choisir…" /></SelectTrigger>
              <SelectContent>
                {INFORMATEURS.map((i) => <SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Ajout…' : 'Ajouter'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function SanteVeille({ onAvisAjoute }) {
  const [ajout, setAjout] = useState(false)
  const { data: sante, loading, refetch } = useResource(
    () => veilleAoApi.sante(), undefined,
    { select: (res) => res.data, errorMessage: 'État de la veille indisponible.' },
  )

  const alarme = Boolean(sante?.alarme_active)
  const age = ageLabel(sante?.derniere_collecte_reussie)

  return (
    <div className="flex flex-col gap-3">
      {/* Bloc 1 — SANTÉ. L'âge est visible SANS clic (VAO37 Done=). */}
      <Card className={`flex flex-wrap items-center gap-4 p-4 ${alarme ? 'border-destructive/50 bg-destructive/10' : ''}`}>
        <div className="flex items-center gap-2">
          <Clock className="size-4 text-muted-foreground" aria-hidden="true" />
          <div>
            <p className="text-xs text-muted-foreground">Dernière collecte réussie</p>
            <p className="font-medium">
              {loading ? '…' : (sante?.derniere_collecte_reussie
                ? <>{formatDateTime(sante.derniere_collecte_reussie)} <span className="text-muted-foreground">({age})</span></>
                : 'Jamais')}
            </p>
          </div>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Avis examinés hier</p>
          <p className="font-medium tabular-nums">{sante?.avis_examines_hier ?? '—'}</p>
        </div>
        {alarme && (
          <div role="alert" className="flex flex-1 items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/15 px-3 py-2 text-sm font-medium text-destructive">
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            {sante?.alarme_message || 'La veille ne ramène plus rien — vérifiez.'}
          </div>
        )}
        {!alarme && !loading && (
          <Badge tone="success" className="ml-auto">
            <CheckCircle2 className="size-3.5" aria-hidden="true" /> Collecte silencieuse : aucune alarme
          </Badge>
        )}
      </Card>

      {/* Bloc 2 — HONNÊTETÉ. Carte permanente, jamais retirée : promettre
          l'exhaustivité serait faux dès le premier jour (préambule Groupe
          VAO — c'est exactement l'erreur qui a coûté l'AO FRDISI). */}
      <Card className="flex flex-col gap-2 p-4">
        <div className="flex items-center gap-2">
          <Info className="size-4 text-muted-foreground" aria-hidden="true" />
          <h3 className="font-display text-sm font-semibold">Ce que la veille automatique ne voit pas</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          La collecte automatique couvre le portail public marchespublics.gov.ma —
          <strong className="text-foreground"> environ 65 à 75 % des opportunités adressables</strong>.
          Elle ne voit <strong className="text-foreground">PAS</strong> les consultations privées et
          restreintes type FRDISI (<strong className="text-foreground">environ 15 à 25 % du flux réel,
          0 % détectable</strong>), ni les portails sectoriels ONEE-Électricité / MASEN / OCP
          (<strong className="text-foreground">environ 10 % du nombre mais la majorité de la valeur</strong>).
        </p>
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted/40 p-2.5 text-sm">
          <span>Un AO reçu par WhatsApp, SMS ou appel ?</span>
          <Button size="sm" onClick={() => setAjout(true)}>
            <Plus className="size-4" /> Ajouter un avis
          </Button>
        </div>
      </Card>

      {ajout && (
        <AjouterAvisDialog
          onClose={() => setAjout(false)}
          onDone={() => { setAjout(false); refetch(); onAvisAjoute?.() }}
        />
      )}
    </div>
  )
}
