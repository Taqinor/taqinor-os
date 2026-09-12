import { useState } from 'react'
import { Coins, Undo2 } from 'lucide-react'
import { Button, Input, toast } from '../../ui'
import { formatMAD } from '../../lib/format'
import juridiqueApi from '../../api/juridiqueApi'

/* ============================================================================
   NTJUR14 / NTJUR15 — provision pour risque : PROPOSER, jamais poster tout seul.
   ----------------------------------------------------------------------------
   Deux affordances, toutes deux en « propose → confirme » :

   * « Proposer une provision » — visible uniquement au palier comptable /
     Administrateur (le parent décide, le serveur re-vérifie). Le montant est
     SAISI : rien n'est pré-rempli d'un chiffre inventé, seule l'estimation de
     risque déjà enregistrée sur le dossier sert de valeur initiale.
   * « Reprendre la provision » — bannière NTJUR15, affichée SEULEMENT quand le
     serveur dit ``reprise_provision_a_proposer`` (donc une seule fois : la
     décision, reprise OU abandon explicite, l'éteint définitivement).

   Aucune écriture n'est postée sans un clic de confirmation explicite.
   ========================================================================== */

export default function ProvisionPanel({ dossier, onChanged }) {
  const [montant, setMontant] = useState(
    dossier?.montant_risque_estime != null
      ? String(dossier.montant_risque_estime) : '')
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)
  const [ouvert, setOuvert] = useState(false)

  const dejaProvisionne = Boolean(dossier?.provision_comptable_id)
  const repriseAProposer = Boolean(dossier?.reprise_provision_a_proposer)

  const confirmerProvision = async () => {
    setBusy(true)
    try {
      await juridiqueApi.proposerProvision(dossier.id, {
        montant, motif, confirme: true,
      })
      const { data } = await juridiqueApi.get(dossier.id)
      onChanged?.(data)
      setOuvert(false)
      toast.success('Provision comptabilisée.')
    } catch (e) {
      const detail = e?.response?.data?.montant
      toast.error(
        Array.isArray(detail) ? detail.join(' ')
          : (detail || 'Provision impossible.'))
    } finally { setBusy(false) }
  }

  const reprendre = async (abandonner) => {
    setBusy(true)
    try {
      await juridiqueApi.reprendreProvision(
        dossier.id, abandonner ? { abandonner: true } : { confirme: true })
      const { data } = await juridiqueApi.get(dossier.id)
      onChanged?.(data)
      toast.success(abandonner
        ? 'Reprise écartée : aucune écriture passée.'
        : 'Provision reprise.')
    } catch (e) {
      const detail = e?.response?.data?.montant
      toast.error(detail || 'Reprise impossible.')
    } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-3">
      {repriseAProposer && (
        <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
          <p className="mb-2">
            Ce dossier est clos et porte une provision comptabilisée. Souhaitez-vous
            la reprendre&nbsp;? Aucune écriture n'est passée sans votre confirmation.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" disabled={busy}
              onClick={() => reprendre(false)}
            >
              <Undo2 /> Reprendre la provision
            </Button>
            <Button type="button" size="sm" variant="outline" disabled={busy}
              onClick={() => reprendre(true)}
            >
              Ne pas reprendre
            </Button>
          </div>
        </div>
      )}

      {dejaProvisionne ? (
        <p className="text-sm text-muted-foreground">
          <Coins className="mr-1 inline size-4" aria-hidden="true" />
          Provision comptabilisée (réf. interne {dossier.provision_comptable_id}).
        </p>
      ) : ouvert ? (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <label className="text-sm font-medium" htmlFor="provision-montant">
            Montant de la provision
          </label>
          <Input
            id="provision-montant"
            value={montant}
            inputMode="decimal"
            onChange={(e) => setMontant(e.target.value)}
            placeholder="Montant à provisionner"
          />
          <label className="text-sm font-medium" htmlFor="provision-motif">
            Motif
          </label>
          <Input
            id="provision-motif"
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            placeholder="Motif de la dotation"
          />
          <p className="text-xs text-muted-foreground">
            Estimation de risque enregistrée :{' '}
            {dossier?.montant_risque_estime != null
              ? formatMAD(dossier.montant_risque_estime)
              : 'aucune'}.
          </p>
          <div className="flex gap-2">
            <Button type="button" size="sm" disabled={busy || !montant}
              onClick={confirmerProvision}
            >
              Confirmer la dotation
            </Button>
            <Button type="button" size="sm" variant="outline" disabled={busy}
              onClick={() => setOuvert(false)}
            >
              Annuler
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <Button type="button" variant="outline" onClick={() => setOuvert(true)}>
            <Coins /> Proposer une provision
          </Button>
        </div>
      )}
    </div>
  )
}
