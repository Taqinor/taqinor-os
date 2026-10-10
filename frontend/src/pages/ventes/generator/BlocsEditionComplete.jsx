// SPL49 — LE PIED DE L'ÉDITION COMPLÈTE DU GÉNÉRATEUR, déplacé tel quel de
// DevisGenerator.jsx : modèles de devis (VX18/APX16), historique des
// versions (QJR553) et blocs repris du modal DevisForm (QJR540 : badge
// calepinage périmé, calepinage, BOQ électrique, lots multi-sites, pièces
// jointes). Les composants calepinage sont importés, jamais édités. Props
// nommées une par une, jamais de spread.
import DevisPresetPanel from '../DevisPresetPanel'
import HistoriqueConfiguration from '../../../features/ventes/HistoriqueConfiguration'
import { peutEditerDevis } from '../../../features/ventes/devisStatuts'
import { Card, CardContent } from '../../../ui'
import BadgePerime from '../../../features/calepinage/BadgePerime'
import BlocCalepinageDevis from '../../../features/ventes/BlocCalepinageDevis'
import AjouterBoqElectrique from '../../../features/ventes/AjouterBoqElectrique'
import LotsMultiSites from '../../../features/ventes/LotsMultiSites'
import AttachmentsPanel from '../../../components/AttachmentsPanel'

export default function BlocsEditionComplete({
  editDevis, rechargerDevisRecompose, handlePresetApplied, enregistrerAvantModele,
  versionHistorique, revenirAVersion,
}) {
  return (
    <>
      {/* VX18 — modèles de devis : appliquer un modèle remplace les lignes.
          APX16 — le panneau n'apparaissait QU'EN ÉDITION : on ne pouvait pas
          partir d'un modèle pour créer un devis, ce qui est pourtant le
          besoin le plus fréquent. Il est désormais là DÈS LA CRÉATION
          (replié) ; sans devisId, l'application se fait localement depuis
          l'instantané de lignes du modèle (aucun endpoint nouveau) et la
          section « Enregistrer comme modèle » dit honnêtement qu'elle
          attend que le devis existe. */}
      <DevisPresetPanel devisId={editDevis?.id} onApplied={handlePresetApplied}
                        avantEnregistrement={enregistrerAvantModele} />

      {/* QJR553 (D-QJR5-7) — historique des versions, avec « Revenir à
          cette version » seulement si le devis est modifiable (QJR516). */}
      {editDevis?.id && (
        <HistoriqueConfiguration devisId={editDevis.id}
                                 peutRevenir={peutEditerDevis(editDevis)}
                                 onRevenir={revenirAVersion}
                                 rafraichir={versionHistorique} />
      )}

      {/* QJR540 — blocs repris du modal DevisForm (supprimé) : badge
          « calepinage périmé » (CAL188, lu de `layout_stale`), le calepinage
          qui pilote ce devis (CAL40, silencieux sans calepinage) et les
          pièces jointes du devis. N'existent que sur un devis enregistré. */}
      {editDevis?.id && (
        <Card data-testid="devis-edition-blocs">
          <CardContent className="pt-4 space-y-3">
            <BadgePerime layoutStale={editDevis.layout_stale}
              layoutNbPanneaux={editDevis.layout_nb_panneaux} />
            <BlocCalepinageDevis devisId={editDevis.id} />
            <AjouterBoqElectrique devisId={editDevis.id} modifiable={peutEditerDevis(editDevis)} onAjoute={rechargerDevisRecompose} />
            <LotsMultiSites devisId={editDevis.id} modifiable={peutEditerDevis(editDevis)} onChange={rechargerDevisRecompose} />
            <div>
              <p className="mb-2 text-sm font-semibold text-foreground">Pièces jointes</p>
              <AttachmentsPanel model="ventes.devis" id={editDevis.id} />
            </div>
          </CardContent>
        </Card>
      )}
    </>
  )
}
