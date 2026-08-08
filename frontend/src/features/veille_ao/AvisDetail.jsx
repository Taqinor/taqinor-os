import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import veilleAoApi from '../../api/veilleAoApi'
import useResource from '../../hooks/useResource'
import ChatterWidget from '../../components/ChatterWidget'
import {
  Button, Card, Skeleton, EmptyState, toast, Badge,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Textarea, Checkbox, Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Input,
} from '../../ui'
import { RecordShell, daysUntil, urgencyLevel, urgencyTone, urgencyLabel } from '../../ui/module'
import { formatDate, formatDateTime, formatMAD } from '../../lib/format'
import { StatutAvis } from './veilleAoShared'

/* ============================================================================
   VAO34 — Fiche avis + les deux gestes qui comptent : « Retenir » et « Ignorer ».
   ----------------------------------------------------------------------------
   `RecordShell` (ARC46) : en-tête + statut + actions, chatter `records`
   (`ChatterWidget`, FG7 — model `veille_ao.avismarche`, JAMAIS une timeline
   maison). « Retenir » et « Ignorer » appellent chacun un service serveur RÉEL
   (VAO30/VAO14) — aucune mutation de façade. « Charger le détail » (VAO18)
   n'appelle le portail QU'À LA DEMANDE (deux délais de 110 s observés côté
   portail) : un échec laisse l'avis INTACT et affiche un message FR, jamais un
   écran vide.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const PORTEES_REGLE = [
  { value: 'acheteur', label: 'Cet acheteur' },
  { value: 'mot_libelle', label: 'Un mot du libellé' },
  { value: 'categorie', label: 'Cette catégorie' },
  { value: 'region', label: 'Cette région' },
]

function valeurParDefaut(avis, portee) {
  if (!avis) return ''
  if (portee === 'acheteur') return avis.acheteur || ''
  if (portee === 'categorie') return avis.categorie || ''
  if (portee === 'region') return avis.region || avis.lieu || ''
  return ''
}

function Info({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value ?? <span className="text-muted-foreground">—</span>}</dd>
    </div>
  )
}

// VAO34 — « Ignorer » demande le motif et PROPOSE la règle d'exclusion sans
// jamais la créer en douce (opt-in explicite, décoché par défaut, VAO10).
function IgnorerDialog({ avis, onClose, onDone }) {
  const [motif, setMotif] = useState('')
  const [creerRegle, setCreerRegle] = useState(false)
  const [portee, setPortee] = useState('acheteur')
  const [valeur, setValeur] = useState(() => valeurParDefaut(avis, 'acheteur'))
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const choisirPortee = (p) => {
    setPortee(p)
    setValeur(valeurParDefaut(avis, p))
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErr(null)
    try {
      await veilleAoApi.avis.ignorer(avis.id, { motif: motif.trim() || undefined })
      if (creerRegle) {
        await veilleAoApi.reglesExclusion.create({
          portee, motif: motif.trim() || undefined, valeur: valeur.trim() || undefined,
        })
      }
      toast.success(creerRegle ? 'Avis ignoré — règle d’exclusion créée.' : 'Avis ignoré.')
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Impossible d’ignorer cet avis.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Ignorer cet avis</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ign-motif">Motif</Label>
            <Textarea id="ign-motif" rows={2} value={motif} onChange={(e) => setMotif(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="flex items-start gap-2">
            <Checkbox id="ign-regle" checked={creerRegle} onCheckedChange={(v) => setCreerRegle(Boolean(v))} />
            <Label htmlFor="ign-regle" className="font-normal">
              Créer aussi une règle d’exclusion — les prochains avis correspondants seront auto-ignorés
            </Label>
          </div>
          {creerRegle && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ign-portee">Portée</Label>
                <Select value={portee} onValueChange={choisirPortee}>
                  <SelectTrigger id="ign-portee" aria-label="Portée"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PORTEES_REGLE.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ign-valeur">Valeur</Label>
                <Input id="ign-valeur" value={valeur} onChange={(e) => setValeur(e.target.value)} />
              </div>
            </div>
          )}
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Envoi…' : 'Ignorer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function AvisDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [dialog, setDialog] = useState(null)
  const [busy, setBusy] = useState(false)

  const { data: avis, loading, error, refetch } = useResource(
    () => veilleAoApi.avis.get(id),
    id,
    { select: (res) => res.data, errorMessage: 'Avis introuvable.' },
  )

  const retenir = async () => {
    setBusy(true)
    try {
      const res = await veilleAoApi.avis.retenir(id)
      toast.success('Avis retenu — affaire créée.')
      const appelOffreId = res?.data?.appel_offre_id
      if (appelOffreId) navigate(`/ao/affaires/${appelOffreId}`)
      else refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Impossible de retenir cet avis.'))
    } finally { setBusy(false) }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (error || !avis) {
    return (
      <EmptyState
        title="Avis introuvable"
        description={error || 'Cet avis n’existe pas ou n’est pas accessible.'}
        action={<Button variant="outline" onClick={refetch}>Réessayer</Button>}
      />
    )
  }

  const days = avis.date_limite ? daysUntil(avis.date_limite) : null
  const level = urgencyLevel(days)

  const actions = (
    <>
      {(avis.statut === 'nouveau' || avis.statut === 'ignore') && (
        <Button size="sm" onClick={retenir} disabled={busy}>
          {busy ? 'Retenue…' : 'Retenir'}
        </Button>
      )}
      {avis.statut === 'nouveau' && (
        <Button size="sm" variant="outline" onClick={() => setDialog('ignorer')} disabled={busy}>
          Ignorer
        </Button>
      )}
      {/* Pas de bouton « Charger le détail » : l'enrichissement à la demande
          (VAO18) appartient au COLLECTEUR PORTAIL (VAO15-VAO20), gaté derrière
          l'action fondateur VAO2 — ouvrir le compte entreprise du portail et
          vérifier si le flux RSS authentifié existe (auquel cas le collecteur
          n'est même jamais construit). Le bouton revient AVEC le collecteur.
          En attendant, « Voir l'avis d'origine » ouvre la page publique. */}
      {avis.url_detail && (
        <Button size="sm" variant="outline" asChild>
          <a href={avis.url_detail} target="_blank" rel="noopener noreferrer">
            <ExternalLink aria-hidden="true" /> Voir l’avis d’origine
          </a>
        </Button>
      )}
    </>
  )

  return (
    <>
      <RecordShell
        title={avis.objet || avis.reference_avis || `Avis #${avis.id}`}
        subtitle={avis.acheteur}
        status={avis.statut}
        statusPill={StatutAvis}
        backTo="/veille-ao/avis"
        backLabel="Retour aux avis"
        actions={actions}
        activity={<ChatterWidget model="veille_ao.avismarche" id={avis.id} />}
      >
        <div className="flex flex-col gap-4">
          {/* VAO10/VAO34 — un avis auto-ignoré affiche la règle qui l'a filtré. */}
          {avis.statut === 'ignore' && avis.regle_exclusion_motif && (
            <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
              Ignoré automatiquement par la règle : {avis.regle_exclusion_motif}
            </div>
          )}
          <Card className="p-4">
            <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
              <Info label="Référence" value={avis.reference_avis || avis.ref_consultation} />
              <Info label="Acheteur" value={avis.acheteur} />
              <Info label="Acronyme" value={avis.org_acronyme} />
              <Info label="Lieu / région" value={avis.lieu || avis.region} />
              <Info label="Procédure" value={avis.procedure} />
              {/* Le serveur publie `<champ>_libelle` (convention du module :
                  statut_libelle, type_source_libelle…), jamais `_display`. */}
              <Info label="Catégorie" value={avis.categorie_libelle || avis.categorie} />
              <Info label="Publié le" value={avis.date_publication ? formatDate(avis.date_publication) : null} />
              <Info
                label="Date limite"
                value={avis.date_limite ? (
                  <span className="inline-flex items-center gap-1.5">
                    {formatDateTime(avis.date_limite)}
                    <Badge tone={urgencyTone(level)}>{urgencyLabel(days)}</Badge>
                  </span>
                ) : null}
              />
              <Info label="Ouverture des plis" value={avis.date_ouverture ? formatDateTime(avis.date_ouverture) : null} />
              <Info label="Montant estimé" value={avis.montant_estime ? formatMAD(avis.montant_estime) : null} />
              <Info label="Caution provisoire" value={avis.caution_provisoire ? formatMAD(avis.caution_provisoire) : null} />
              <Info label="Lot" value={avis.lot} />
              <Info label="Score" value={avis.score} />
              <Info label="Source" value={avis.source_libelle} />
              <Info label="Informateur" value={avis.informateur_libelle || avis.informateur} />
            </dl>
            {Array.isArray(avis.mots_cles_declenches) && avis.mots_cles_declenches.length > 0 && (
              <div className="mt-3">
                <dt className="text-xs text-muted-foreground">Mots déclencheurs</dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {avis.mots_cles_declenches.map((m) => (
                    <span key={m} className="rounded-full bg-muted px-2 py-0.5 text-xs">{m}</span>
                  ))}
                </dd>
              </div>
            )}
          </Card>
        </div>
      </RecordShell>

      {dialog === 'ignorer' && (
        <IgnorerDialog
          avis={avis}
          onClose={() => setDialog(null)}
          onDone={() => { setDialog(null); refetch() }}
        />
      )}
    </>
  )
}
