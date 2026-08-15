import { useState } from 'react'
import { Link2, Copy, Check } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import { Button, Input, toast } from '../../ui'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   WIR264/XFSM7+ZFSM2 — Partage client d'une intervention.

   Les deux actions serveur (`lien-client`, `lien-rapport`) exposaient un jeton
   sans qu'aucun bouton ne les appelle ni qu'aucune page ne les reçoive. Ce
   panneau est le pendant de `TicketSuiviClientPanel` (FG86) côté intervention :
   il génère le lien (idempotent côté serveur : un second clic renvoie le même
   jeton), l'affiche en clair et le copie.

   Les deux jetons sont DISTINCTS : le suivi « en route » ne donne pas accès au
   compte-rendu, et réciproquement.
   ========================================================================== */

// Le serveur renvoie un CHEMIN de page ; on l'absolutise sur l'origine
// courante pour donner au technicien un lien collable tel quel.
const versUrlAbsolue = (path) => {
  if (!path) return null
  if (/^https?:\/\//i.test(path)) return path
  if (typeof window === 'undefined') return path
  return `${window.location.origin}${path}`
}

function LigneLien({ libelle, description, lien, busy, onGenerer }) {
  const [copie, setCopie] = useState(false)

  const copier = async () => {
    if (!lien) return
    try {
      await navigator.clipboard.writeText(lien)
      setCopie(true)
      toast.success('Lien copié')
      setTimeout(() => setCopie(false), 2500)
    } catch {
      toast.error('Copie impossible — sélectionnez le lien manuellement.')
    }
  }

  return (
    <div className="flex flex-col gap-1.5 rounded border border-border p-2">
      <span className="text-sm font-medium">{libelle}</span>
      <span className="text-[12px] text-muted-foreground">{description}</span>
      {lien ? (
        <div className="flex items-center gap-2">
          <Input readOnly value={lien} aria-label={`Lien : ${libelle}`} />
          <Button type="button" size="sm" variant="outline" onClick={copier}>
            {copie ? <Check className="size-4" /> : <Copy className="size-4" />}
            Copier
          </Button>
        </div>
      ) : (
        <Button type="button" size="sm" variant="outline"
                onClick={onGenerer} disabled={busy}>
          <Link2 className="size-4" /> Partager
        </Button>
      )}
    </div>
  )
}

export default function InterventionPartagePanel({ intervention }) {
  const [suivi, setSuivi] = useState(null)
  const [rapport, setRapport] = useState(null)
  const [busy, setBusy] = useState(false)

  const generer = async (appel, poser, libelle) => {
    setBusy(true)
    try {
      const r = await appel(intervention.id)
      poser(versUrlAbsolue(r.data?.path))
    } catch (err) {
      toast.error(frenchError(err, `${libelle} indisponible — réessayez.`))
    } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-semibold">Partager avec le client</span>
      <LigneLien
        libelle="Suivi « technicien en route »"
        description="Statut, créneau et heure d'arrivée estimée. Aucun coût, aucune position GPS live."
        lien={suivi}
        busy={busy}
        onGenerer={() => generer(
          installationsApi.getLienClientIntervention, setSuivi, 'Lien de suivi')}
      />
      <LigneLien
        libelle="Compte-rendu signé"
        description="Photos, matériel utilisé (quantités seules), réserves et signature, avec le PDF."
        lien={rapport}
        busy={busy}
        onGenerer={() => generer(
          installationsApi.getLienRapportIntervention, setRapport, 'Lien du compte-rendu')}
      />
    </div>
  )
}
