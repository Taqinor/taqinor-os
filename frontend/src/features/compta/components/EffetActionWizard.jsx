/* NTTRE26 — Assistant guidé « Endossement / protêt d'un effet » (1 écran).
   ----------------------------------------------------------------------------
   Présente LES DEUX actions possibles sur un effet (endosser à un tiers,
   constater un protêt) ; celle qui est invalide pour le statut courant est
   GRISÉE avec l'explication du blocage, ce qui rend impossible l'enchaînement
   illégal (un protêt sur un effet déjà encaissé, par exemple).

   Les champs affichés dépendent de l'action choisie. Aucun nouveau modèle ni
   endpoint : l'assistant appelle les routes NTTRE7 existantes
   (`effets/{id}/endosser/` et `effets/{id}/constater-protet/`). */
import { useMemo, useState } from 'react'
import { ArrowRightLeft, Scale } from 'lucide-react'
import {
  Button, Input, Label, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import comptaApi from '../../../api/comptaApi'
import { actionsEffet } from './effetActions'

function messageErreur(err, repli) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  if (d?.detail) return d.detail
  if (d && typeof d === 'object') {
    const [champ, valeur] = Object.entries(d)[0] || []
    if (champ) return `${champ} : ${Array.isArray(valeur) ? valeur[0] : valeur}`
  }
  return repli
}

export default function EffetActionWizard({ effet, onClose, onDone }) {
  const dispo = useMemo(() => actionsEffet(effet), [effet])
  const [action, setAction] = useState(
    dispo.endosser.possible ? 'endosser'
      : (dispo.protet.possible ? 'protet' : ''))
  const [beneficiaire, setBeneficiaire] = useState('')
  const [dateEndossement, setDateEndossement] = useState('')
  const [fraisProtet, setFraisProtet] = useState('')
  const [dateProtet, setDateProtet] = useState('')
  const [erreurChamp, setErreurChamp] = useState('')
  const [busy, setBusy] = useState(false)

  const valider = async () => {
    if (!action) return
    setBusy(true)
    try {
      if (action === 'endosser') {
        if (!beneficiaire.trim()) {
          setErreurChamp('beneficiaire')
          toast.error('Bénéficiaire de l’endossement : champ obligatoire.')
          return
        }
        setErreurChamp('')
        await comptaApi.effets.endosser(effet.id, {
          beneficiaire: beneficiaire.trim(),
          date_endossement: dateEndossement || undefined,
        })
        toast.success('Effet endossé.')
      } else {
        const frais = fraisProtet === '' ? 0 : Number(fraisProtet)
        if (!Number.isFinite(frais) || frais < 0) {
          setErreurChamp('frais_protet')
          toast.error('Frais de protêt : saisissez un montant positif.')
          return
        }
        setErreurChamp('')
        await comptaApi.effets.constaterProtet(effet.id, {
          frais_protet: frais,
          date_protet: dateProtet || undefined,
        })
        toast.success('Protêt constaté.')
      }
      onDone?.()
      onClose()
    } catch (err) {
      toast.error(messageErreur(err, 'Action impossible sur cet effet.'))
    } finally {
      setBusy(false)
    }
  }

  const carte = (cle, titre, Icone, etat) => (
    <button
      type="button"
      key={cle}
      disabled={!etat.possible}
      aria-pressed={action === cle}
      onClick={() => setAction(cle)}
      className={`flex flex-col gap-1 rounded-lg border p-3 text-left text-sm transition ${
        !etat.possible
          ? 'cursor-not-allowed border-border bg-muted/40 text-muted-foreground opacity-60'
          : action === cle
            ? 'border-primary bg-primary/10'
            : 'border-border hover:border-primary/50'
      }`}
    >
      <span className="flex items-center gap-2 font-medium">
        <Icone className="size-4" aria-hidden="true" /> {titre}
      </span>
      {!etat.possible && (
        <span className="text-xs">{etat.raison}</span>
      )}
    </button>
  )

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            Endossement / protêt — effet {effet?.numero || `#${effet?.id}`}
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {carte('endosser', 'Endosser à un tiers', ArrowRightLeft, dispo.endosser)}
          {carte('protet', 'Constater un protêt', Scale, dispo.protet)}
        </div>

        {!action && (
          <p className="mt-3 text-sm text-muted-foreground">
            Aucune de ces deux actions n’est possible dans l’état actuel de cet
            effet.
          </p>
        )}

        {action === 'endosser' && (
          <div className="mt-3 flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="ea-beneficiaire">Bénéficiaire de l’endossement</Label>
              <Input
                id="ea-beneficiaire" value={beneficiaire}
                onChange={(e) => setBeneficiaire(e.target.value)}
              />
              {erreurChamp === 'beneficiaire' && (
                <span className="text-xs text-destructive">
                  Bénéficiaire de l’endossement : champ obligatoire.
                </span>
              )}
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="ea-date-endos">Date de l’endossement</Label>
              <Input
                id="ea-date-endos" type="date" value={dateEndossement}
                onChange={(e) => setDateEndossement(e.target.value)}
              />
            </div>
          </div>
        )}

        {action === 'protet' && (
          <div className="mt-3 flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="ea-frais">Frais de protêt</Label>
              <Input
                id="ea-frais" type="number" step="any" value={fraisProtet}
                onChange={(e) => setFraisProtet(e.target.value)}
              />
              {erreurChamp === 'frais_protet' && (
                <span className="text-xs text-destructive">
                  Frais de protêt : saisissez un montant positif.
                </span>
              )}
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="ea-date-protet">Date du protêt</Label>
              <Input
                id="ea-date-protet" type="date" value={dateProtet}
                onChange={(e) => setDateProtet(e.target.value)}
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
          <Button onClick={valider} disabled={busy || !action}>
            Valider
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
