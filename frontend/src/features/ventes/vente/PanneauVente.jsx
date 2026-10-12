// VNT74 (Groupe VNT, D-VNT-3) — le PANNEAU DE VENTE de la carte d'un devis
// accepté : prix convenu, acompte, factures (brouillon ≠ émise), payé, reste.
// Il ne lit que `devis.vente` (GET détail, VNT70) ; absent (ancien serveur) ⇒
// rien. Une réponse de PATCH / refresh SANS `vente` ne le fait pas disparaître :
// on garde l'état du dernier GET détail (jamais de disparition des boutons).
// Une version remplacée n'a AUCUN bouton : « Remplacé par <réf> ».
// VNT75 — « Facturer l'acompte » / « Facturer le solde » : 2 boutons au plus,
// ouverts par `vente.peut` (venteEtat.js), jamais sur une version remplacée ni
// quand la prochaine action est « aucune » ; ils ouvrent FacturerVenteDialog.
import { useState } from 'react'
import { Button } from '../../../ui'
import BilanVente from './BilanVente'
import LigneFactureVente from './LigneFactureVente'
import FacturerVenteDialog from './FacturerVenteDialog'
import { peutFacturerAcompte, peutFacturerSolde } from './venteEtat'

export default function PanneauVente({ devis, onAction }) {
  const [facturerCible, setFacturerCible] = useState(null)
  // Dernier état servi par un GET détail (état dérivé pendant le rendu).
  const [dernier, setDernier] = useState(devis?.vente ?? null)
  if (devis?.vente && devis.vente !== dernier) setDernier(devis.vente)
  const vente = devis?.vente ?? dernier
  if (!vente) return null

  const remplacee = vente.est_tete === false
  const tete = (vente.versions ?? []).find((v) => v.id === vente.tete_id)
  const factures = vente.factures ?? []
  const rafraichir = () => onAction?.('refresh')
  const actif = { ...devis, vente }
  const ouvert = !remplacee && vente.prochaine_action !== 'aucune'
  const acompte = ouvert && peutFacturerAcompte(actif)
  const solde = ouvert && peutFacturerSolde(actif)

  return (
    <section className="vente-panneau" data-testid={`panneau-vente-${devis.id}`} aria-label="Vente">
      {remplacee && (
        <p className="gen-hint" data-testid={`vente-remplacee-${devis.id}`}>
          {tete?.reference ? `Remplacé par ${tete.reference}` : 'Version remplacée'}
        </p>
      )}
      <BilanVente vente={vente} />
      {factures.length > 0 && (
        <ul className="vente-factures">
          {factures.map((f) => <LigneFactureVente key={f.id} facture={f} onChange={rafraichir} />)}
        </ul>
      )}
      {(acompte || solde) && (
        <div className="vente-actions">
          {acompte && (
            <Button
              type="button" size="sm" data-testid={`vente-facturer-acompte-${devis.id}`}
              onClick={() => setFacturerCible(devis)}
            >
              🧾 Facturer l'acompte
            </Button>
          )}
          {solde && (
            <Button
              type="button" size="sm" data-testid={`vente-facturer-solde-${devis.id}`}
              onClick={() => setFacturerCible(devis)}
            >
              🧾 Facturer le solde
            </Button>
          )}
        </div>
      )}
      {vente.revision_en_cours?.reference && (
        <p className="gen-hint">Révision en cours : {vente.revision_en_cours.reference}</p>
      )}
      {!remplacee && vente.raison_bloquee && (
        <p className="gen-hint" data-testid={`vente-raison-${devis.id}`}>{vente.raison_bloquee}</p>
      )}
      <FacturerVenteDialog
        devis={facturerCible}
        onOpenChange={(o) => { if (!o) setFacturerCible(null) }}
        onDone={() => onAction?.('refresh')}
      />
    </section>
  )
}
