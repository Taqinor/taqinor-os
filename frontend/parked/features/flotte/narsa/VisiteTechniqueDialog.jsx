import { useEffect, useRef, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, confirmLeaveIfDirty,
} from '../../../ui'
import flotteApi from '../../../api/flotteApi'

/* ============================================================================
   AUDV21/XFLT10 — Formulaire de création d'une visite technique NARSA.
   ----------------------------------------------------------------------------
   Quand l'actif choisi est un VÉHICULE avec une carte grise renseignée, la
   prochaine date NARSA est PROPOSÉE (`GET .../visites-techniques/
   proposer-date-narsa/?actif_flotte=<id>`) selon la périodicité légale par
   type fiscal (`services.prochaine_visite_narsa`) et pré-remplit
   `date_prochaine` — UNIQUEMENT tant que l'utilisateur ne l'a pas modifiée
   lui-même : jamais un écrasement d'une saisie manuelle. Sans carte grise
   (engin, ou véhicule sans date de mise en circulation connue), le champ
   reste vide et se calcule normalement côté serveur depuis
   ``date_visite + validite_mois`` à l'enregistrement.
   ========================================================================== */

export default function VisiteTechniqueDialog({ actifs = [], onClose, onSaved }) {
  const [actifFlotteId, setActifFlotteId] = useState('')
  const [centre, setCentre] = useState('')
  const [dateVisite, setDateVisite] = useState('')
  const [resultat, setResultat] = useState('favorable')
  const [validiteMois, setValiditeMois] = useState('12')
  const [dateProchaine, setDateProchaine] = useState('')
  const [proposition, setProposition] = useState(null)
  const [proposing, setProposing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)
  // AUDV21 — ``ref`` (pas un ``useState``) : une proposition réseau peut
  // résoudre APRÈS que l'utilisateur ait déjà tapé sa propre date (course) ;
  // seule une ref est lue à sa valeur COURANTE dans le ``.then`` déjà en vol,
  // un ``useState`` capturé resterait figé sur sa valeur au lancement de
  // l'effet (closure obsolète) et écraserait quand même la saisie manuelle.
  const dateProchaineToucheeRef = useRef(false)

  const peutEnregistrer = Boolean(actifFlotteId && centre.trim() && dateVisite)
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(actifFlotteId || centre || dateVisite || dateProchaine)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  // AUDV21 — à chaque changement d'actif, propose la prochaine date NARSA
  // (silencieux — `null` — si l'actif est un engin ou si la date de mise en
  // circulation est inconnue) ; ne remplace jamais une date déjà saisie à la
  // main sur CE formulaire (``dateProchaineToucheeRef``, lue à jour même si
  // la saisie manuelle survient pendant que l'appel réseau est en vol).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialise la proposition à la désélection
    if (!actifFlotteId) { setProposition(null); return undefined }
    let cancelled = false
    setProposing(true)
    flotteApi.visitesTechniques.proposerDateNarsa(actifFlotteId)
      .then((res) => {
        if (cancelled) return
        const proposee = res?.data?.date_proposee || null
        setProposition(proposee)
        if (proposee && !dateProchaineToucheeRef.current) setDateProchaine(proposee)
      })
      .catch(() => { if (!cancelled) setProposition(null) })
      .finally(() => { if (!cancelled) setProposing(false) })
    return () => { cancelled = true }
  }, [actifFlotteId])

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.visitesTechniques.create({
        actif_flotte: Number(actifFlotteId),
        centre: centre.trim(),
        date_visite: dateVisite,
        resultat,
        validite_mois: validiteMois === '' ? undefined : Number(validiteMois),
        date_prochaine: dateProchaine || undefined,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.actif_flotte
        || data?.validite_mois
        || data?.date_prochaine
        || data?.centre
        || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle visite technique</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="vt-actif">Actif (véhicule ou engin)</Label>
            <select
              id="vt-actif"
              autoFocus
              value={actifFlotteId}
              onChange={(e) => {
                setActifFlotteId(e.target.value)
                dateProchaineToucheeRef.current = false
              }}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {actifs.map((a) => (
                <option key={a.id} value={a.id}>{a.label}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="vt-centre">Centre de visite</Label>
            <Input id="vt-centre" value={centre} onChange={(e) => setCentre(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vt-date-visite">Date de la visite</Label>
              <Input
                id="vt-date-visite" type="date" value={dateVisite}
                onChange={(e) => setDateVisite(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vt-resultat">Résultat</Label>
              <select
                id="vt-resultat"
                value={resultat}
                onChange={(e) => setResultat(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="favorable">Favorable</option>
                <option value="defavorable">Défavorable</option>
                <option value="contre_visite">Contre-visite</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vt-validite">Validité (mois)</Label>
              <Input
                id="vt-validite" type="number" step="1" value={validiteMois}
                onChange={(e) => setValiditeMois(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vt-prochaine">Prochaine visite</Label>
              <Input
                id="vt-prochaine"
                type="date"
                value={dateProchaine}
                onChange={(e) => {
                  setDateProchaine(e.target.value)
                  dateProchaineToucheeRef.current = true
                }}
              />
            </div>
          </div>

          {proposing && (
            <p className="text-xs text-muted-foreground">Calcul de la date NARSA proposée…</p>
          )}
          {!proposing && proposition && (
            <p className="text-xs text-muted-foreground">
              Date NARSA proposée (périodicité légale) : {proposition} — modifiable.
            </p>
          )}

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
