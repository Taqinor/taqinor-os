import { useState } from 'react'
import { Link2, Copy, Check, FileText } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import { Button, Input, toast } from '../../ui'

/* WIR264 — liens PUBLICS d'une intervention (XFSM7 « technicien en route » et
   ZFSM2 « compte-rendu signé »). Les deux jetons existaient côté serveur sans
   aucun bouton pour les obtenir ni aucune page pour les ouvrir. Patron repris
   à l'identique de `TicketSuiviClientPanel` (FG86) : on GÉNÈRE à la demande
   (jeton lazy, idempotent côté serveur), on affiche l'URL, on la copie —
   jamais d'envoi automatique.

   Les deux pages publiques ne montrent aucune donnée interne : ni coût
   d'achat, ni marge, ni chatter (garanti côté serveur par les payloads
   `intervention_public_payload` / `intervention_rapport_public_payload`). */

function LienPublic({
  titre, aide, icone, libelleBouton, charger, testId,
}) {
  const [lien, setLien] = useState(null)
  const [busy, setBusy] = useState(false)
  const [copie, setCopie] = useState(false)

  const generer = async () => {
    setBusy(true)
    try {
      const r = await charger()
      setLien(r.data?.url ?? r.data?.path ?? null)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Lien indisponible — réessayez.')
    } finally {
      setBusy(false)
    }
  }

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
    <div className="flex flex-col gap-1.5" data-testid={testId}>
      <span className="flex items-center gap-2 text-sm font-medium">
        {icone}
        {titre}
      </span>
      <p className="text-xs text-muted-foreground">{aide}</p>
      {lien ? (
        <div className="flex items-center gap-2">
          <Input readOnly value={lien} onFocus={(e) => e.target.select()}
                 aria-label={titre} />
          <Button type="button" size="sm" variant="outline" onClick={copier}>
            {copie ? <Check /> : <Copy />} {copie ? 'Copié' : 'Copier'}
          </Button>
        </div>
      ) : (
        <div>
          <Button type="button" size="sm" variant="outline"
                  loading={busy} onClick={generer}>
            <Link2 /> {libelleBouton}
          </Button>
        </div>
      )}
    </div>
  )
}

export default function InterventionLiensPublicsPanel({ intervention }) {
  const id = intervention?.id
  if (!id) return null
  return (
    <div className="flex flex-col gap-4" data-testid="intervention-liens-publics">
      <LienPublic
        testId="lien-suivi-intervention"
        titre="Partager le suivi « en route »"
        aide="Lien public à envoyer au client — statut, technicien et heure
              d'arrivée estimée. Aucun prix, aucune note interne."
        icone={<Link2 className="size-4 text-muted-foreground" aria-hidden="true" />}
        libelleBouton="Générer le lien de suivi"
        charger={() => installationsApi.getLienClientIntervention(id)}
      />
      <LienPublic
        testId="lien-rapport-intervention"
        titre="Partager le compte-rendu signé"
        aide="Lien public du compte-rendu (photos, matériel posé, réserves,
              signature) avec son PDF. Jeton distinct du suivi."
        icone={<FileText className="size-4 text-muted-foreground" aria-hidden="true" />}
        libelleBouton="Générer le lien du compte-rendu"
        charger={() => installationsApi.getLienRapportIntervention(id)}
      />
    </div>
  )
}
