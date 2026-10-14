// VNT46 (D-VNT-1) — dialogue d'annulation d'une facture, extrait de
// FactureRow.jsx (ré-export nommé conservé là). Il dit CE QUI SE PASSE : un avoir
// de contre-passation est créé automatiquement et la facture reste tracée
// (jamais supprimée) ; un brouillon `BROUILLON-<id>` est annulé sans avoir.
// AFAC13 — une facture qui porte de l'argent ne s'annule jamais sans dire où il
// va : le choix « transférer » (autre facture ouverte du même client),
// « rembourser » ou « garder en avance client » est OBLIGATOIRE et NON
// pré-coché ; le refus serveur s'affiche SOUS le choix. Aucune règle d'argent
// recalculée ici : le dialogue s'ouvre sur `montant_paye > 0` servi par le
// serveur (ou `directiveRequise` après son refus `directive_acompte_requise`),
// qui reste seul juge (AFAC12).
import { useState } from 'react'
import { Button } from '../../../ui'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { formatMAD, toNumber } from '../../../lib/format'

const estProvisoire = (reference) => String(reference || '').startsWith('BROUILLON-')

function Corps({ facture, factures, busy, erreur, directiveRequise, onConfirm, onClose }) {
  const [action, setAction] = useState('')
  const [cible, setCible] = useState('')
  const porteArgent = directiveRequise || toNumber(facture.montant_paye) > 0
  const cibles = factures.filter(x => x.id !== facture.id
    && String(x.client) === String(facture.client)
    && ['emise', 'en_retard'].includes(x.statut))
  const manque = porteArgent && (!action || (action === 'transferer' && !cible))
  const valider = () => {
    if (!porteArgent) { onConfirm(undefined); return }
    onConfirm(action === 'transferer'
      ? { action, facture_cible: Number(cible) }
      : { action })
  }
  return (
    <>
      <p className="text-sm" data-testid="annulation-avoir">
        {estProvisoire(facture.reference)
          ? "Ce brouillon n'a pas encore de numéro légal : il sera annulé sans avoir."
          : "Un avoir de contre-passation sera créé automatiquement. La facture reste tracée dans la liste : elle n'est jamais supprimée."}
      </p>
      {porteArgent && (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">
            {toNumber(facture.montant_paye) > 0
              ? `Cette facture porte ${formatMAD(toNumber(facture.montant_paye))} encaissés : où va cet argent ?`
              : 'Cette facture porte de l’argent : où va-t-il ?'}
          </legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="annulation-acompte" value="transferer"
                   checked={action === 'transferer'}
                   onChange={() => setAction('transferer')} />
            Transférer sur une autre facture
          </label>
          {action === 'transferer' && (
            <select aria-label="Facture cible" value={cible}
                    onChange={(e) => setCible(e.target.value)}
                    className="w-full rounded-md border px-2 py-1 text-sm">
              <option value="">Choisir une facture ouverte…</option>
              {cibles.map(x => (
                <option key={x.id} value={x.id}>{x.reference}</option>
              ))}
            </select>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="annulation-acompte" value="rembourser"
                   checked={action === 'rembourser'}
                   onChange={() => setAction('rembourser')} />
            Rembourser
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="annulation-acompte" value="garder_en_avance"
                   checked={action === 'garder_en_avance'}
                   onChange={() => setAction('garder_en_avance')} />
            Garder en avance client
          </label>
        </fieldset>
      )}
      {erreur && (
        <p role="alert" data-testid="annulation-erreur"
           className="text-sm text-destructive">{erreur}</p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose}>Retour</Button>
        <Button type="button" variant="destructive" loading={busy}
                disabled={manque} onClick={valider}>
          Annuler la facture
        </Button>
      </div>
    </>
  )
}

export function AnnulationFactureDialog({
  facture, factures = [], busy = false, erreur = null, directiveRequise = false, onConfirm, onClose,
}) {
  if (!facture) return null
  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      title={`Annuler la facture ${facture.reference}`}
    >
      <Corps facture={facture} factures={factures} busy={busy} erreur={erreur}
             directiveRequise={directiveRequise} onConfirm={onConfirm} onClose={onClose} />
    </ResponsiveDialog>
  )
}

// VNT77 — confirmation de suppression d'un `BROUILLON-<id>`, partagée par la
// liste des factures (FactureRow) et le panneau de vente du lead.
export function SuppressionBrouillonDialog({ facture, busy = false, onConfirm, onClose }) {
  if (!facture) return null
  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      title={`Supprimer le brouillon ${facture.reference} ?`}
      description="Ce brouillon n'a pas de numéro légal : il disparaît sans laisser de trou dans la numérotation."
      footer={(
        <>
          <Button type="button" variant="ghost" onClick={onClose}>Retour</Button>
          <Button type="button" variant="destructive" loading={busy}
                  data-testid="supprimer-brouillon-confirmer" onClick={onConfirm}>
            Supprimer
          </Button>
        </>
      )}>
      <span className="sr-only">{facture.reference}</span>
    </ResponsiveDialog>
  )
}

export default AnnulationFactureDialog
