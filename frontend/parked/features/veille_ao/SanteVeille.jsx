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
import { ageLabel } from './veilleAoShared'

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


const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

/* ── WIR269 — « D'où vient le chiffre d'affaires » (VAO31) ─────────────────
   Le constat CENTRAL de l'étude était illisible : l'endpoint agrégé existait
   (`GET /veille_ao/attribution/`), personne ne l'appelait, et la question
   « la veille automatique rapporte-t-elle vraiment ? » n'avait aucune réponse
   à l'écran.

   RÈGLE ABSOLUE DE CE BLOC : **aucun agrégat n'est recalculé ici.** Chaque
   nombre affiché — y compris la ligne « Total » — est lu TEL QUEL dans la
   réponse serveur (`kpis.attribution`, qui lit l'issue des affaires par le
   `selectors.py` d'`apps.ao`). Une somme faite ici finirait, un jour, par
   afficher un chiffre différent de celui du serveur sur le même écran.

   Les DEUX axes sont à ÉGALITÉ (par source automatique ET par informateur
   humain) : c'est tout l'intérêt de la mesure — rendre visible ce que la
   veille automatique ne voit pas, jamais en note de bas de page. */
const COLONNES_ATTRIBUTION = [
  { cle: 'avis', libelle: 'Avis' },
  { cle: 'retenus', libelle: 'Retenus' },
  { cle: 'affaires', libelle: 'Affaires' },
  { cle: 'gagnes', libelle: 'Gagnés' },
  { cle: 'perdus', libelle: 'Perdus' },
  { cle: 'en_cours', libelle: 'En cours' },
]

// Un nombre ABSENT n'est pas un zéro : « — » dit qu'on ne sait pas, un 0
// affirmerait qu'il n'y en a eu aucun.
const nb = (v) => (Number.isFinite(v) ? v : '—')

function TableauAttribution({ titre, lignes, total, axe }) {
  if (!lignes?.length) {
    return (
      <div data-veille-attribution-vide={axe}>
        <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{titre}</h4>
        <p className="text-sm text-muted-foreground">Aucun canal mesuré pour l’instant.</p>
      </div>
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="data-table w-full text-sm" data-veille-attribution={axe}>
        <caption className="text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {titre}
        </caption>
        <thead>
          <tr>
            <th scope="col">Canal</th>
            {COLONNES_ATTRIBUTION.map((c) => (
              <th key={c.cle} scope="col" className="text-right">{c.libelle}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lignes.map((ligne) => (
            <tr key={ligne.cle} data-veille-canal={ligne.cle}>
              <th scope="row" className="font-normal">{ligne.libelle}</th>
              {COLONNES_ATTRIBUTION.map((c) => (
                <td key={c.cle} className="text-right tabular-nums">{nb(ligne[c.cle])}</td>
              ))}
            </tr>
          ))}
        </tbody>
        {total && axe === 'source' && (
          /* Le total est celui du SERVEUR (`attribution.total`), jamais une
             somme des lignes ci-dessus. Il n'est rendu qu'UNE fois (sous l'axe
             « source ») : les deux axes décrivent les MÊMES avis, les
             additionner les compterait deux fois. */
          <tfoot>
            <tr data-veille-attribution-total="">
              <th scope="row">Total</th>
              {COLONNES_ATTRIBUTION.map((c) => (
                <td key={c.cle} className="text-right font-medium tabular-nums">{nb(total[c.cle])}</td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}

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

  // WIR269 — un SECOND appel agrégé, distinct de `sante()` : deux mesures
  // différentes, deux endpoints, aucun croisement côté écran.
  const { data: attribution, loading: chargementAttribution } = useResource(
    () => veilleAoApi.attribution(), undefined,
    { select: (res) => res.data, errorMessage: 'Attribution du chiffre d’affaires indisponible.' },
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

      {/* Bloc 1bis — D'OÙ VIENT LE CHIFFRE D'AFFAIRES (VAO31/WIR269). Le
          constat central de l'étude, servi par UN appel agrégé : rien n'est
          recalculé ici, total compris. */}
      <Card className="flex flex-col gap-3 p-4" data-veille-attribution-bloc="">
        <h3 className="font-display text-sm font-semibold">D’où vient le chiffre d’affaires</h3>
        <p className="text-xs text-muted-foreground">
          Canal → avis → affaires → gagnés, sur tout l’historique. Les deux axes
          décrivent les mêmes avis&nbsp;: la source automatique qui les a
          ramenés, et l’informateur humain qui les a signalés.
        </p>
        {chargementAttribution && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {!chargementAttribution && (
          <>
            <TableauAttribution
              axe="source"
              titre="Par source (collecte automatique)"
              lignes={attribution?.par_source}
              total={attribution?.total}
            />
            <TableauAttribution
              axe="informateur"
              titre="Par informateur (signalé par un humain)"
              lignes={attribution?.par_informateur}
              total={attribution?.total}
            />
          </>
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
