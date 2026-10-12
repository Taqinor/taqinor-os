// VNT74/VNT76 (Groupe VNT, D-VNT-3) — UNE facture de la vente dans le panneau :
// sa référence (`BROUILLON-<id>` tant qu'elle n'est pas émise), sa nature, la
// pastille « Brouillon » ≠ « Émise » ≠ « Payée », le total, le payé, les
// paiements — et ses gestes : Émettre, PDF, Envoyer (WhatsApp / e-mail),
// Encaisser (`PaiementDialog`) et, PAR PAIEMENT, Reçu. Chaque geste est ouvert
// par `facture.peut` / `paiement.peut` (le serveur dit, l'écran n'en redérive
// aucun) ; un refus s'écrit en `role=alert` SOUS cette facture, avec sa
// référence — jamais de toast (règle fondateur « erreurs → le champ fautif »).
import { useState } from 'react'
import { Button, StatusPill } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import PaiementDialog from '../../../pages/ventes/PaiementDialog'
import { useActionsVente } from './useActionsVente'

const NATURES = {
  acompte: 'Acompte',
  intermediaire: 'Livraison du matériel',
  solde: 'Solde',
  complete: 'Facture complète',
  bc: 'Facture du bon de commande',
  consolidee: 'Facture consolidée',
}

const STATUTS_FACTURE = {
  brouillon: 'Brouillon',
  emise: 'Émise',
  partiellement_payee: 'Partiellement payée',
  payee: 'Payée',
  en_retard: 'En retard',
  annulee: 'Annulée',
}

const TONS = {
  brouillon: 'neutral', emise: 'info', partiellement_payee: 'warning',
  payee: 'success', en_retard: 'danger', annulee: 'danger',
}

export default function LigneFactureVente({ facture, onChange }) {
  const actions = useActionsVente({ liste: false, onChange })
  const [encaisser, setEncaisser] = useState(null)
  const statut = facture.statut
  const peut = facture.peut ?? {}
  const occupe = actions.occupe !== null
  const erreur = actions.erreur?.factureId === facture.id ? actions.erreur : null

  const bouton = (cle, libelle, onClick, variante = 'outline') => (
    <Button
      type="button" size="sm" variant={variante} disabled={occupe}
      data-testid={`vente-${cle}-${facture.id}`} onClick={onClick}
    >
      {libelle}
    </Button>
  )

  return (
    <li className="vente-facture" data-testid={`vente-facture-${facture.id}`}>
      <div className="vente-facture-tete">
        <span className="vente-facture-ref">{facture.reference}</span>
        <span className="gen-hint">{NATURES[facture.nature] ?? facture.nature}</span>
        <StatusPill status={statut} tone={TONS[statut]} label={STATUTS_FACTURE[statut] ?? statut} />
        <span className="num">{formatMAD(facture.total_ttc, { decimals: 0 })}</span>
        {Number(facture.montant_paye) > 0 && (
          <span className="gen-hint">payé {formatMAD(facture.montant_paye, { decimals: 0 })}</span>
        )}
      </div>
      {(facture.paiements ?? []).length > 0 && (
        <ul className="vente-paiements">
          {facture.paiements.map((p) => (
            <li key={p.id} data-testid={`vente-paiement-${p.id}`} className="gen-hint">
              {formatMAD(p.montant, { decimals: 0 })} · {formatDate(p.date_paiement)} · {p.mode_paiement}
              {p.peut?.recu === true && (
                <Button
                  type="button" size="sm" variant="ghost" disabled={occupe}
                  onClick={() => actions.recu(facture, p)}
                >
                  Reçu
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="vente-facture-gestes">
        {peut.emettre === true && bouton('emettre', 'Émettre', () => actions.emettre(facture), 'default')}
        {peut.encaisser === true && bouton('encaisser', 'Encaisser', () => setEncaisser(facture), 'default')}
        {peut.pdf === true && bouton('pdf', 'PDF', () => actions.pdf(facture))}
        {peut.envoyer === true && bouton('whatsapp', 'WhatsApp', () => actions.whatsapp(facture))}
        {peut.envoyer === true && bouton('email', 'E-mail', () => actions.envoyerEmail(facture))}
      </div>
      {erreur && (
        <p role="alert" className="vente-facture-erreur" data-testid={`vente-erreur-${facture.id}`}>
          {facture.reference} : {erreur.message}
        </p>
      )}
      {encaisser && (
        <PaiementDialog
          facture={{
            id: facture.id, reference: facture.reference,
            total_ttc: facture.total_ttc, montant_paye: facture.montant_paye,
          }}
          onOpenChange={(o) => { if (!o) { setEncaisser(null); onChange?.() } }}
          onSaved={onChange}
        />
      )}
    </li>
  )
}
