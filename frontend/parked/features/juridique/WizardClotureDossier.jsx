import { useState } from 'react'
import { Undo2 } from 'lucide-react'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label, toast,
} from '../../ui'
import { formatMAD } from '../../lib/format'
import juridiqueApi from '../../api/juridiqueApi'
import { STATUT_MAP } from './juridiqueStatus'

/* ============================================================================
   NTJUR32 — Wizard « Clôture de dossier » (une seule modale, plusieurs étapes).
   ----------------------------------------------------------------------------
   1. Statut final (gagné / perdu / transaction / désistement) + motif ;
   2. Montant final — SEULEMENT pour une transaction ;
   3. Récapitulatif → c'est le SEUL bouton qui écrit ;
   4. (si le dossier porte une provision) proposition de reprise — NTJUR15,
      jamais automatique, et l'utilisateur peut l'écarter sans écriture.

   RÈGLE CENTRALE — aucun effet de bord avant l'étape 3. Les étapes 1 et 2 ne
   vivent que dans l'état local : fermer la modale à n'importe quel moment
   avant « Confirmer la clôture » laisse le dossier EXACTEMENT dans son statut
   précédent (aucun appel serveur n'a été émis). C'est la garantie testée par
   le critère d'acceptation.

   PÉRIMÈTRE ASSUMÉ : l'étape « politique de rétention » (NTJUR18) n'est pas
   proposée — ce mécanisme n'est pas encore construit côté serveur ; une étape
   qui n'appellerait rien serait un faux bouton.
   ========================================================================== */

const STATUTS_FINAUX = [
  'clos_gagne', 'clos_perdu', 'clos_transaction', 'clos_desistement',
]

export default function WizardClotureDossier({ dossier, onAnnuler, onClos }) {
  const [etape, setEtape] = useState(1)
  const [statutFinal, setStatutFinal] = useState('')
  const [motif, setMotif] = useState('')
  const [montantFinal, setMontantFinal] = useState('')
  const [busy, setBusy] = useState(false)
  const [closDossier, setClosDossier] = useState(null)

  const estTransaction = statutFinal === 'clos_transaction'

  const suivant = () => {
    if (etape === 1) {
      if (!statutFinal) {
        toast.error('Choisissez le statut final du dossier.')
        return
      }
      setEtape(estTransaction ? 2 : 3)
      return
    }
    if (etape === 2) setEtape(3)
  }

  const precedent = () => {
    if (etape === 3) setEtape(estTransaction ? 2 : 1)
    else if (etape === 2) setEtape(1)
  }

  // SEUL point d'écriture du wizard.
  const confirmer = async () => {
    setBusy(true)
    try {
      if (estTransaction && montantFinal) {
        await juridiqueApi.update(dossier.id, {
          montant_en_jeu: montantFinal,
        })
      }
      const { data } = await juridiqueApi.clore(dossier.id, statutFinal, motif)
      setClosDossier(data)
      toast.success('Dossier clôturé.')
      if (data?.reprise_provision_a_proposer) {
        setEtape(4)
      } else {
        onClos?.(data)
      }
    } catch (e) {
      const detail = e?.response?.data?.statut_final
      toast.error(detail || 'Clôture impossible.')
    } finally { setBusy(false) }
  }

  const deciderReprise = async (abandonner) => {
    setBusy(true)
    try {
      await juridiqueApi.reprendreProvision(
        dossier.id, abandonner ? { abandonner: true } : { confirme: true })
      const { data } = await juridiqueApi.get(dossier.id)
      toast.success(abandonner
        ? 'Reprise écartée : aucune écriture passée.'
        : 'Provision reprise.')
      onClos?.(data)
    } catch (e) {
      const detail = e?.response?.data?.montant
      toast.error(detail || 'Reprise impossible.')
    } finally { setBusy(false) }
  }

  const fermer = () => {
    // Après la clôture, refermer rend la main sur le dossier RÉELLEMENT clos ;
    // avant, c'est une simple annulation sans effet de bord.
    if (closDossier) onClos?.(closDossier)
    else onAnnuler?.()
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) fermer() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            Clôturer le dossier {dossier?.reference || ''}
          </DialogTitle>
        </DialogHeader>

        {etape === 1 && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">
              Rien n'est enregistré tant que la clôture n'est pas confirmée.
            </p>
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1 text-sm font-medium">Statut final</legend>
              {STATUTS_FINAUX.map((valeur) => (
                <label key={valeur} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="statut-final"
                    value={valeur}
                    checked={statutFinal === valeur}
                    onChange={() => setStatutFinal(valeur)}
                  />
                  {STATUT_MAP[valeur]?.label || valeur}
                </label>
              ))}
            </fieldset>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cloture-motif">Motif</Label>
              <Input
                id="cloture-motif"
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                placeholder="Motif de la clôture (facultatif)"
              />
            </div>
          </div>
        )}

        {etape === 2 && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cloture-montant">Montant final de la transaction</Label>
              <Input
                id="cloture-montant"
                value={montantFinal}
                inputMode="decimal"
                onChange={(e) => setMontantFinal(e.target.value)}
                placeholder="Montant réellement convenu"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Laissé vide, le montant en jeu du dossier reste inchangé
              ({formatMAD(dossier?.montant_en_jeu)}).
            </p>
          </div>
        )}

        {etape === 3 && (
          <div className="flex flex-col gap-2 text-sm">
            <p>
              <span className="text-muted-foreground">Statut final : </span>
              <span className="font-medium">
                {STATUT_MAP[statutFinal]?.label || statutFinal}
              </span>
            </p>
            {estTransaction && montantFinal && (
              <p>
                <span className="text-muted-foreground">Montant final : </span>
                <span className="font-medium">{formatMAD(montantFinal)}</span>
              </p>
            )}
            {motif && (
              <p>
                <span className="text-muted-foreground">Motif : </span>{motif}
              </p>
            )}
            <p className="text-muted-foreground">
              La clôture ne poste AUCUNE écriture comptable. Si ce dossier porte
              une provision, sa reprise vous sera proposée juste après —
              vous resterez libre de l'écarter.
            </p>
          </div>
        )}

        {etape === 4 && (
          <div className="flex flex-col gap-2 text-sm">
            <p>
              Ce dossier porte une provision comptabilisée. Souhaitez-vous la
              reprendre&nbsp;? Aucune écriture n'est passée sans votre
              confirmation.
            </p>
          </div>
        )}

        <DialogFooter>
          {etape === 4 ? (
            <>
              <Button type="button" variant="outline" disabled={busy}
                onClick={() => deciderReprise(true)}
              >
                Ne pas reprendre
              </Button>
              <Button type="button" disabled={busy}
                onClick={() => deciderReprise(false)}
              >
                <Undo2 /> Reprendre la provision
              </Button>
            </>
          ) : (
            <>
              <Button type="button" variant="outline" disabled={busy}
                onClick={etape === 1 ? onAnnuler : precedent}
              >
                {etape === 1 ? 'Annuler' : 'Précédent'}
              </Button>
              {etape === 3 ? (
                <Button type="button" disabled={busy} onClick={confirmer}>
                  Confirmer la clôture
                </Button>
              ) : (
                <Button type="button" disabled={busy} onClick={suivant}>
                  Suivant
                </Button>
              )}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
