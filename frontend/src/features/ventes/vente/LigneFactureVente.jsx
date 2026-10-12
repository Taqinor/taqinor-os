// VNT74/VNT76 (Groupe VNT, D-VNT-3) — UNE facture de la vente dans le panneau :
// sa référence (`BROUILLON-<id>` tant qu'elle n'est pas émise), sa nature, la
// pastille « Brouillon » ≠ « Émise » ≠ « Payée », le total, le payé, les
// paiements — et ses gestes : Émettre, PDF, Envoyer (WhatsApp / e-mail),
// Encaisser (`PaiementDialog`) et, PAR PAIEMENT, Reçu. Chaque geste est ouvert
// par `facture.peut` / `paiement.peut` (le serveur dit, l'écran n'en redérive
// aucun) ; un refus s'écrit en `role=alert` SOUS cette facture, avec sa
// référence — jamais de toast (règle fondateur « erreurs → le champ fautif »).
// VNT77 (D-VNT-1) — trois gestes de plus, chacun ouvert par `facture.peut` (le
// palier est calculé serveur : le Commercial n'en voit aucun, jamais de 403
// évitable) : « Annuler la facture » (avoir automatique ; AlertDialog qui dit la
// conséquence, ou `AnnulationFactureDialog` quand la facture porte de l'argent —
// directive obligatoire), « Supprimer » (BROUILLON-<id> seulement, confirmé) et
// « Modifier le montant » d'un brouillon de tranche (champ inline → `montant-tranche`,
// refus nommé SOUS le champ ; le panneau relit la fiche, l'échéancier suit).
import { useState } from 'react'
import { MoreHorizontal } from 'lucide-react'
import {
  Button, Input, StatusPill, DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogFooter, AlertDialogTitle,
  AlertDialogDescription, AlertDialogCancel, AlertDialogAction,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import { formatMAD, formatDate } from '../../../lib/format'
import PaiementDialog from '../../../pages/ventes/PaiementDialog'
import { AnnulationFactureDialog } from '../../../pages/ventes/factureList/AnnulationFactureDialog'
import ventesApi from '../../../api/ventesApi'
import { useActionsVente } from './useActionsVente'
import { aplatirErreurs, bandeau } from './erreursVente'

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

const MONTANT_REPLI = 'Montant non enregistré : réessayez.'

export default function LigneFactureVente({ facture, factures = [], onChange }) {
  const actions = useActionsVente({ liste: false, onChange })
  const [encaisser, setEncaisser] = useState(null)
  // VNT77 — `annulation` : {directive, erreur} ; `suppression` : confirmation ;
  // `montant` : {valeur, enCours, erreur} (champ inline d'un brouillon de tranche).
  const [annulation, setAnnulation] = useState(null)
  const [suppression, setSuppression] = useState(false)
  const [montant, setMontant] = useState(null)
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
  if (peut.modifier_montant === true) {
    gestes.push({
      id: 'montant', libelle: 'Modifier le montant',
      agir: () => { actions.effacerErreur(); setMontant({ valeur: String(Number(facture.total_ttc)), enCours: false, erreur: null }) },
    })
  }
  if (peut.annuler === true) {
    gestes.push({
      id: 'annuler', libelle: 'Annuler la facture',
      agir: () => { actions.effacerErreur(); setAnnulation({ directive: Number(facture.montant_paye) > 0, erreur: null }) },
    })
  }
  if (peut.supprimer === true) {
    gestes.push({ id: 'supprimer', libelle: 'Supprimer', agir: () => { actions.effacerErreur(); setSuppression(true) } })
  }
  const recus = (facture.paiements ?? []).filter((p) => p.peut?.recu === true)
  const aReplier = mobile
    ? [...gestes, ...recus.map((p) => ({
      id: `recu-${p.id}`, libelle: `Reçu ${formatMAD(p.montant, { decimals: 0 })}`, agir: () => actions.recu(facture, p),
    }))]
    : []
  const visibles = mobile ? aReplier.slice(0, aReplier.length > 2 ? 1 : aReplier.length) : gestes
  const menu = mobile ? aReplier.slice(visibles.length) : []

  const enregistrerMontant = async () => {
    const brut = String(montant.valeur).replace(/\s/g, '').replace(',', '.')
    setMontant((m) => ({ ...m, enCours: true, erreur: null }))
    try {
      await ventesApi.modifierMontantTranche(facture.id, brut)
      setMontant(null)
      onChange?.()
    } catch (err) {
      const message = err?.response
        ? bandeau(aplatirErreurs(err.response.data))
        : 'Serveur injoignable — vérifiez la connexion puis réessayez.'
      setMontant((m) => ({ ...m, enCours: false, erreur: message || MONTANT_REPLI }))
    }
  }

  const confirmerAnnulation = async (directive) => {
    setAnnulation((a) => ({ ...a, erreur: null }))
    const r = await actions.annuler(facture, directive)
    if (r.ok) { setAnnulation(null); return }
    setAnnulation((a) => ({
      directive: a.directive || r.code === 'directive_acompte_requise', erreur: r.message,
    }))
  }

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
      {montant && (
        <div className="vente-montant grid gap-1" data-testid={`vente-montant-${facture.id}`}>
          <div className="flex flex-wrap items-end gap-2">
            <label className="grid gap-1 text-xs">
              Montant TTC
              <Input
                type="number" step="any" inputMode="decimal" value={montant.valeur}
                invalid={montant.erreur ? true : undefined}
                className="w-40"
                onChange={(e) => setMontant((m) => ({ ...m, valeur: e.target.value, erreur: null }))}
              />
            </label>
            <Button type="button" size="sm" className={cible} loading={montant.enCours} onClick={enregistrerMontant}>
              Enregistrer
            </Button>
            <Button type="button" size="sm" variant="ghost" className={cible} disabled={montant.enCours} onClick={() => setMontant(null)}>
              Retour
            </Button>
          </div>
          {montant.erreur && (
            <p role="alert" className="vente-facture-erreur" data-testid={`vente-montant-erreur-${facture.id}`}>
              {montant.erreur}
            </p>
          )}
        </div>
      )}
      {erreur && !annulation && (
        <p role="alert" className="vente-facture-erreur" data-testid={`vente-erreur-${facture.id}`}>
          {facture.reference} : {erreur.message}
        </p>
      )}
      {suppression && (
        <AlertDialog open onOpenChange={(o) => { if (!o) setSuppression(false) }}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Supprimer le brouillon {facture.reference} ?</AlertDialogTitle>
              <AlertDialogDescription>
                Ce brouillon n'a pas de numéro légal : il disparaît sans laisser de trou dans la numérotation.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Retour</AlertDialogCancel>
              <AlertDialogAction
                onClick={async () => { await actions.supprimer(facture); setSuppression(false) }}
              >
                Supprimer le brouillon
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
      {annulation && !annulation.directive && (
        <AlertDialog open onOpenChange={(o) => { if (!o) setAnnulation(null) }}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Annuler la facture {facture.reference} ?</AlertDialogTitle>
              <AlertDialogDescription>
                Un avoir de contre-passation sera créé automatiquement. La facture reste tracée
                dans la liste : elle n'est jamais supprimée.
              </AlertDialogDescription>
            </AlertDialogHeader>
            {annulation.erreur && (
              <p role="alert" className="vente-facture-erreur" data-testid={`vente-annulation-erreur-${facture.id}`}>
                {annulation.erreur}
              </p>
            )}
            <AlertDialogFooter>
              <AlertDialogCancel>Retour</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => { e.preventDefault(); confirmerAnnulation(undefined) }}
              >
                Confirmer l'annulation
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
      {annulation?.directive && (
        <AnnulationFactureDialog
          facture={facture}
          factures={factures}
          busy={actions.occupe === `annuler:${facture.id}`}
          erreur={annulation.erreur}
          directiveRequise
          onClose={() => setAnnulation(null)}
          onConfirm={confirmerAnnulation}
        />
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
