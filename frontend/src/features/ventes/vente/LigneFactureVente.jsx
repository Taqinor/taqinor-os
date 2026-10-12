// VNT74/VNT76 (Groupe VNT, D-VNT-3) — UNE facture de la vente dans le panneau :
// sa référence (`BROUILLON-<id>` tant qu'elle n'est pas émise), sa nature, la
// pastille « Brouillon » ≠ « Émise » ≠ « Payée », le total, le payé, les
// paiements — et ses gestes : Émettre, PDF, Envoyer (WhatsApp / e-mail),
// Encaisser (`PaiementDialog`) et, PAR PAIEMENT, Reçu. Chaque geste est ouvert
// par `facture.peut` / `paiement.peut` (le serveur dit, l'écran n'en redérive
// aucun) ; un refus s'écrit en `role=alert` SOUS cette facture, avec sa
// référence — jamais de toast (règle fondateur « erreurs → le champ fautif »).
import { useState } from 'react'
import { MoreHorizontal } from 'lucide-react'
import {
  Button, StatusPill, DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
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
  // VNT81 — au téléphone (< 768 px) : cibles ≥ 44 px et AU PLUS deux boutons
  // visibles par facture (le geste principal + « Plus d'actions »), le reste —
  // Reçu compris — passe dans le menu. Au bureau : tout reste visible.
  const mobile = useIsMobile()
  const cible = mobile ? 'min-h-11 min-w-11' : undefined

  const gestes = []
  if (peut.emettre === true) gestes.push({ id: 'emettre', libelle: 'Émettre', variante: 'default', agir: () => actions.emettre(facture) })
  if (peut.encaisser === true) gestes.push({ id: 'encaisser', libelle: 'Encaisser', variante: 'default', agir: () => setEncaisser(facture) })
  if (peut.pdf === true) gestes.push({ id: 'pdf', libelle: 'PDF', agir: () => actions.pdf(facture) })
  if (peut.envoyer === true) {
    gestes.push({ id: 'whatsapp', libelle: 'WhatsApp', agir: () => actions.whatsapp(facture) })
    gestes.push({ id: 'email', libelle: 'E-mail', agir: () => actions.envoyerEmail(facture) })
  }
  const recus = (facture.paiements ?? []).filter((p) => p.peut?.recu === true)
  const aReplier = mobile
    ? [...gestes, ...recus.map((p) => ({
      id: `recu-${p.id}`, libelle: `Reçu ${formatMAD(p.montant, { decimals: 0 })}`, agir: () => actions.recu(facture, p),
    }))]
    : []
  const visibles = mobile ? aReplier.slice(0, aReplier.length > 2 ? 1 : aReplier.length) : gestes
  const menu = mobile ? aReplier.slice(visibles.length) : []

  const bouton = (g) => (
    <Button
      key={g.id} type="button" size="sm" variant={g.variante ?? 'outline'} disabled={occupe}
      className={cible} data-testid={`vente-${g.id}-${facture.id}`} onClick={g.agir}
    >
      {g.libelle}
    </Button>
  )

  return (
    <li className="vente-facture grid gap-1 border-t py-2" data-testid={`vente-facture-${facture.id}`}>
      <div className="vente-facture-tete flex flex-wrap items-center gap-x-2 gap-y-1">
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
              {!mobile && p.peut?.recu === true && (
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
      <div className="vente-facture-gestes flex flex-wrap items-center gap-2">
        {visibles.map(bouton)}
        {menu.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button" size="sm" variant="outline" disabled={occupe} className={cible}
                aria-label={`Plus d'actions — ${facture.reference}`}
              >
                <MoreHorizontal className="size-4" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {menu.map((g) => (
                <DropdownMenuItem key={g.id} className="min-h-11" onSelect={g.agir}>{g.libelle}</DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
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
