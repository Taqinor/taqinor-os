import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ClipboardList } from 'lucide-react'
import {
  Button, Card, EmptyState, Skeleton, Textarea, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import { formatMAD } from '../../../lib/format'
import LigneRow from './LigneRow'

/* ============================================================================
   AOF179 — Écran « Bordereau » : édition des lignes et des sections.
   ----------------------------------------------------------------------------
   AOF120-AOF123 livrent les sections, la TVA par ligne, les quantités
   TRAÇABLES et la renumérotation à total invariant ; sans écran, les 30 items
   du cas réel continueraient de se saisir dans Excel — c'est-à-dire hors de
   tout contrôle.

   **AUCUN CHIFFRE N'EST DÉRIVÉ ICI** (garde AOF94). Sous-total HT, remise,
   total HT, TVA, total TTC, total de ligne et montants en lettres viennent
   TOUS du payload serveur ; l'écran n'additionne rien, ne multiplie rien,
   n'arrondit rien. C'est ce qui rend l'écran et le PDF structurellement
   incapables de se contredire.

   **Déplacer une ligne = appeler le service de renumérotation** (AOF123), pas
   réordonner un tableau en mémoire : le serveur renumérote 1..N de façon
   contiguë ET PROUVE que le total est inchangé. L'écran affiche le bordereau
   qu'il reçoit en retour — total compris.

   **Rien de verrouillé ne s'édite en douce.** Une quantité issue du calepinage
   ou une ligne du cadre acheteur exige un déverrouillage EXPLICITE avec motif
   obligatoire, tracé côté serveur.

   Les services serveur sont INJECTÉS (`onDeplacerLigne`, `onModifierLigne`,
   `onDeverrouiller`, `onAppliquerPrix`) : `api/aoApi.js` (AOF11, lane
   `frontend/ao-socle`) n'expose pas encore de ressource bordereau et n'est
   jamais retouché ici — aucun endpoint n'est inventé, aucun `axios` direct.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

// Une réponse de service peut être le bordereau lui-même ou une réponse axios.
function lireBordereau(reponse) {
  if (!reponse) return null
  if (reponse.data && (reponse.data.lignes || reponse.data.sections)) return reponse.data
  if (reponse.lignes || reponse.sections) return reponse
  return null
}

function TotauxServeur({ bordereau }) {
  const ligne = (label, valeur, fort = false) => (
    <div className="flex items-center justify-between gap-6 text-sm">
      <span className={fort ? 'font-medium' : 'text-muted-foreground'}>{label}</span>
      <span className={`tabular-nums ${fort ? 'font-display text-base font-semibold' : ''}`}>
        {valeur != null ? formatMAD(valeur) : '—'}
      </span>
    </div>
  )
  return (
    <Card className="ml-auto flex w-full max-w-sm flex-col gap-1 p-4">
      {ligne('Sous-total HT', bordereau.sous_total_ht)}
      {ligne('Remise globale', bordereau.remise_globale)}
      {ligne('Total HT', bordereau.total_ht, true)}
      {ligne('TVA', bordereau.tva_montant)}
      {ligne('Total TTC', bordereau.total_ttc, true)}
      {bordereau.total_ttc_lettres && (
        <p className="mt-1 text-xs italic text-muted-foreground">
          Arrêté à la somme de : {bordereau.total_ttc_lettres}
        </p>
      )}
    </Card>
  )
}

function DeverrouillageDialog({ ligne, onClose, onConfirmer }) {
  const [motif, setMotif] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    const m = motif.trim()
    if (!m) return
    setEnvoi(true)
    try {
      await onConfirmer(ligne, m)
      onClose()
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Déverrouiller « {ligne.designation || ligne.libelle} »</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
          <p className="rounded-md border border-warning/40 bg-warning/5 p-2.5 text-xs text-warning">
            Cette quantité est verrouillée par sa provenance. Le déverrouillage est TRACÉ côté
            serveur : le motif est obligatoire.
          </p>
          <Textarea
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            rows={3}
            aria-label="Motif du déverrouillage"
            placeholder="Ex. quantité corrigée après relevé contradictoire du 27/07."
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={!motif.trim() || envoi}>
              {envoi ? 'Déverrouillage…' : 'Déverrouiller'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function BordereauPage({
  bordereau: bordereauInitial,
  loading = false,
  error = null,
  propositionsPrix = {},
  onModifierLigne,
  onDeplacerLigne,
  onDeverrouiller,
  onAppliquerPrix,
}) {
  const [bordereau, setBordereau] = useState(bordereauInitial ?? null)
  const [occupe, setOccupe] = useState(false)
  const [aDeverrouiller, setADeverrouiller] = useState(null)

  useEffect(() => { setBordereau(bordereauInitial ?? null) }, [bordereauInitial])

  // Tout service renvoie le bordereau RECALCULÉ : on le remplace en bloc, on
  // ne « patche » jamais une ligne localement (sinon les totaux divergent).
  const appliquerReponse = useCallback((reponse) => {
    const frais = lireBordereau(reponse)
    if (frais) setBordereau(frais)
  }, [])

  const executer = useCallback(async (fn, echec) => {
    if (!fn) return
    setOccupe(true)
    try {
      appliquerReponse(await fn())
    } catch (e) {
      toast.error(errMsg(e, echec))
    } finally {
      setOccupe(false)
    }
  }, [appliquerReponse])

  const deplacer = useCallback((ligne, sectionId) => executer(
    () => onDeplacerLigne(ligne, sectionId),
    'Déplacement impossible — le bordereau est inchangé.',
  ), [executer, onDeplacerLigne])

  const modifier = useCallback((ligne, patch) => executer(
    () => onModifierLigne(ligne, patch),
    'Modification impossible.',
  ), [executer, onModifierLigne])

  const appliquerPrix = useCallback((ligne, proposition) => executer(
    () => onAppliquerPrix(ligne, proposition),
    'Application du prix impossible.',
  ), [executer, onAppliquerPrix])

  const deverrouiller = useCallback(async (ligne, motif) => {
    await executer(
      () => onDeverrouiller(ligne, motif),
      'Déverrouillage refusé.',
    )
  }, [executer, onDeverrouiller])

  const sections = bordereau?.sections ?? []
  const lignesParSection = useMemo(() => {
    const carte = new Map(sections.map((s) => [s.id, []]))
    for (const l of bordereau?.lignes ?? []) {
      if (!carte.has(l.section)) carte.set(l.section, [])
      carte.get(l.section).push(l)
    }
    return carte
  }, [bordereau, sections])

  if (loading && !bordereau) {
    return <div className="flex flex-col gap-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>
  }
  if (error || !bordereau) {
    return (
      <EmptyState
        icon={ClipboardList}
        title="Bordereau indisponible"
        description={error || "Cette affaire n'a pas encore de bordereau des prix."}
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Bordereau des prix</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {bordereau.indice_revision ? `Indice de révision ${bordereau.indice_revision} — ` : ''}
            prix unitaires et montants en lettres calculés par le serveur.
          </p>
        </div>
      </div>

      {sections.map((section) => (
        <Card key={section.id} className="overflow-x-auto p-0">
          <h2 className="px-3 py-2 font-display text-base font-semibold">
            {section.numero ? `${section.numero} — ` : ''}{section.libelle}
            {section.batiment_label ? ` (${section.batiment_label})` : ''}
          </h2>
          <table className="w-full min-w-[64rem] border-t border-border text-left">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th scope="col" className="px-2 py-2 font-medium">N°</th>
                <th scope="col" className="px-2 py-2 font-medium">Désignation</th>
                <th scope="col" className="px-2 py-2 font-medium">Unité</th>
                <th scope="col" className="px-2 py-2 font-medium">Quantité</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">P.U. HT</th>
                <th scope="col" className="px-2 py-2 font-medium">P.U. en lettres</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">TVA</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Total HT</th>
                <th scope="col" className="px-2 py-2 font-medium">Section</th>
              </tr>
            </thead>
            <tbody>
              {(lignesParSection.get(section.id) ?? []).map((ligne) => (
                <LigneRow
                  key={ligne.id}
                  ligne={ligne}
                  sections={sections}
                  proposition={propositionsPrix[ligne.id]}
                  occupe={occupe}
                  onModifier={onModifierLigne ? modifier : undefined}
                  onDeplacer={onDeplacerLigne ? deplacer : undefined}
                  onAppliquerPrix={onAppliquerPrix ? appliquerPrix : undefined}
                  onDemanderDeverrouillage={onDeverrouiller ? setADeverrouiller : undefined}
                />
              ))}
            </tbody>
          </table>
        </Card>
      ))}

      <TotauxServeur bordereau={bordereau} />

      {/* Clause de réserve : obligatoire pour un marché à prix unitaires, et
          NON ÉDITABLE ici (texte normalisé — il se modifie dans la
          bibliothèque, avec sa liste de dossiers impactés). */}
      <Card className="flex items-start gap-2 p-4">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div>
          <p className="text-xs font-medium text-muted-foreground">Clause de réserve (non éditable)</p>
          <p className="text-sm">{bordereau.clause_reserve || '—'}</p>
        </div>
      </Card>

      {aDeverrouiller && (
        <DeverrouillageDialog
          ligne={aDeverrouiller}
          onClose={() => setADeverrouiller(null)}
          onConfirmer={deverrouiller}
        />
      )}
    </div>
  )
}
