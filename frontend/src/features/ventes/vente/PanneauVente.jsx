// VNT74 (Groupe VNT, D-VNT-3) — le panneau de vente d'un devis accepté, dans
// la carte devis du lead. Tout est LU de `d.vente` (GET détail du lead,
// VNT70 ; contrat `ventes/contract_samples/vente_etat.json`) : `vente` absent
// ou null ⇒ rien. Une version remplacée dit « Remplacé par … », sans bouton.
// VNT75 — « Facturer l'acompte » / « Facturer le solde » : deux boutons au
// plus, ouverts par `vente.peut` SEUL (jamais le repli `'libre'`), jamais sur
// une version remplacée ni quand le serveur dit `prochaine_action: 'aucune'`.
// VNT78 — « Prix négocié » (dialogue VNT73) suivant `vente.peut.prix_negocie` ;
// le succès relit le lead, qui sert alors la V2 acceptée.
// ATOT60 — « Confirmer l'avoir » suivant `vente.peut.confirmer_avoir_revision` ;
// le montant est dans `raison_bloquee` (serveur), jamais calculé ici.
import { useState } from 'react'
import ventesApi from '../../../api/ventesApi'
import { Button } from '../../../ui'
import { useConfirmDialog } from '../../../ui/confirm'
import BilanVente from './BilanVente'
import LigneFactureVente from './LigneFactureVente'
import FacturerVenteDialog from './FacturerVenteDialog'
import PrixNegocieDialog from '../PrixNegocieDialog'
import { peutFacturerAcompte, peutFacturerSolde, peutVente, CIBLE_TACTILE } from './venteEtat'

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

export default function PanneauVente({ devis, onRafraichir, avecFacturer = true }) {
  const vente = useVenteMemorisee(devis)
  const [facturer, setFacturer] = useState(false)
  const [prixOuvert, setPrixOuvert] = useState(false)
  const [avoir, setAvoir] = useState({ enCours: false, erreur: '' })
  const { confirm } = useConfirmDialog()
  if (!vente) return null
  const remplacee = vente.est_tete === false
  const tete = remplacee ? (vente.versions || []).find((v) => v.id === vente.tete_id) : null
  const factures = vente.factures || []
  const d = { ...devis, vente }
  // VNT79 — la liste des devis garde son bouton unique « Facturer… » sur la
  // ligne : sa sous-ligne n'en ajoute pas un second (`avecFacturer={false}`).
  const ouvert = avecFacturer && !remplacee && vente.prochaine_action !== 'aucune'
  const acompte = ouvert && peutFacturerAcompte(d)
  const solde = ouvert && peutFacturerSolde(d)
  // VNT78 (D-VNT-2) — tête acceptée active seulement (jamais une version remplacée).
  const prix = !remplacee && peutVente(d, 'prix_negocie')
  const confirmer = !remplacee && peutVente(d, 'confirmer_avoir_revision')
  const confirmerAvoir = async () => {
    // AERR17 — un avoir sera émis : confirmation qui nomme le devis.
    if (!(await confirm({ title: `Confirmer l'avoir de révision du devis ${devis.reference} ?`,
      description: 'Un avoir sera émis sur la facture de ce devis.' }))) return
    setAvoir({ enCours: true, erreur: '' })
    try {
      await ventesApi.confirmerAvoirRevision(devis.id)
      setAvoir({ enCours: false, erreur: '' })
      onRafraichir?.()
    } catch (e) {
      setAvoir({ enCours: false, erreur: e?.response?.data?.detail || "L'avoir n'a pas pu être confirmé." })
    }
  }
  return (
    <section
      // VNT81 — une colonne, aucun débordement horizontal au téléphone.
      className="grid min-w-0 max-w-full gap-2 rounded-md border p-2"
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
          {factures.map((f) => (
            <LigneFactureVente
              key={f.id} facture={f} facturesVente={factures}
              onRafraichir={onRafraichir} lectureSeule={remplacee}
            />
          ))}
        </ul>
      )}
      {(acompte || solde || prix || confirmer) && (
        <div className="flex flex-wrap gap-2">
          {acompte && (
            <Button type="button" size="sm" className={CIBLE_TACTILE} onClick={() => setFacturer(true)}>
              Facturer l&apos;acompte
            </Button>
          )}
          {solde && (
            <Button type="button" size="sm" variant="outline" className={CIBLE_TACTILE} onClick={() => setFacturer(true)}>
              {vente.prochaine_action === 'intermediaire' ? 'Facturer la tranche suivante' : 'Facturer le solde'}
            </Button>
          )}
          {prix && (
            <Button type="button" size="sm" variant="outline" className={CIBLE_TACTILE} onClick={() => setPrixOuvert(true)}>
              Prix négocié
            </Button>
          )}
          {confirmer && (
            <Button type="button" size="sm" variant="outline" className={CIBLE_TACTILE}
              disabled={avoir.enCours} onClick={confirmerAvoir}>
              Confirmer l&apos;avoir
            </Button>
          )}
        </div>
      )}
      {avoir.erreur && <p role="alert" className="text-sm text-destructive">{avoir.erreur}</p>}
      <FacturerVenteDialog
        devis={facturer ? devis : null}
        onOpenChange={(o) => { if (!o) setFacturer(false) }}
        onDone={() => onRafraichir?.()}
      />
      {/* Monté hors du bouton : après l'application, la V1 devient remplacée
          (bouton retiré) mais le dialogue reste ouvert pour l'avenant à signer. */}
      {prixOuvert && (
        <PrixNegocieDialog
          devis={devis} open onOpenChange={setPrixOuvert}
          onApplied={() => onRafraichir?.()}
        />
      )}
    </section>
  )
}
