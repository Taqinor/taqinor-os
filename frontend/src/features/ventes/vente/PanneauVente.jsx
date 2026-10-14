// VNT74 (Groupe VNT, D-VNT-3) — le panneau de vente d'un devis accepté, dans
// la carte devis du lead. Tout est LU de `d.vente` (GET détail du lead,
// VNT70 ; contrat `ventes/contract_samples/vente_etat.json`) : `vente` absent
// ou null ⇒ rien. Une version remplacée dit « Remplacé par … », sans bouton.
import { useState } from 'react'
import BilanVente from './BilanVente'
import LigneFactureVente from './LigneFactureVente'

/**
 * La `vente` du DERNIER GET détail : une réponse qui ne porte pas la clé
 * (PATCH du lead, rafraîchissement partiel) garde l'état connu — le panneau
 * et ses boutons ne disparaissent jamais sur un rechargement partiel. Une clé
 * présente (même `null`) fait foi.
 */
function useVenteMemorisee(devis) {
  const presente = !!devis && Object.prototype.hasOwnProperty.call(devis, 'vente')
  const [memo, setMemo] = useState(presente ? devis.vente : null)
  if (presente && devis.vente !== memo) setMemo(devis.vente)
  return presente ? devis.vente : memo
}

export default function PanneauVente({ devis }) {
  const vente = useVenteMemorisee(devis)
  if (!vente) return null
  const remplacee = vente.est_tete === false
  const tete = remplacee ? (vente.versions || []).find((v) => v.id === vente.tete_id) : null
  const factures = vente.factures || []
  return (
    <section
      className="grid gap-2 rounded-md border p-2"
      aria-label={`Vente du devis ${devis.reference}`}
      data-testid="panneau-vente"
    >
      {remplacee ? (
        <p className="gen-hint" role="note">Remplacé par {tete?.reference ?? 'la version en cours'}</p>
      ) : (
        vente.raison_bloquee && <p className="gen-hint">{vente.raison_bloquee}</p>
      )}
      <BilanVente vente={vente} />
      {factures.length > 0 && (
        <ul className="grid gap-2" aria-label="Factures de la vente">
          {factures.map((f) => <LigneFactureVente key={f.id} facture={f} />)}
        </ul>
      )}
    </section>
  )
}
