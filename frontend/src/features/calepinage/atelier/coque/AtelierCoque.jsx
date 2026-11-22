import AtelierPanneaux from '../../AtelierPanneaux'
import BuilderCarte from '../BuilderCarte'
import BuilderOutils from '../BuilderOutils'
import BuilderPose, { BuilderStatut } from '../BuilderPose'
import BuilderToit from '../BuilderToit'
import CoqueAtelier from './CoqueAtelier'
import { sousTitreProjet, titreProjet } from './projet'

/* ============================================================================
   COQUE — LE BRANCHEMENT de l'écran de conception (pages/ventes/ToitureDesign,
   mode calepinage) sur la coque plein écran. Ce fichier ne tient AUCUN état :
   il compose les nœuds (groupes du constructeur, panneau de l'atelier) et les
   textes du bandeau à partir de ce que le serveur a servi (design-context).
   ========================================================================== */

export default function AtelierCoque({
  calepinageId, contexte, devisId, devisReference, devisLabel, calepinageTitre, lectureSeule,
  enregistrement, proprietesBuilder, enregistreLe, onEtape, ecranProps, alertes, avance, atelierPanneaux,
}) {
  const devisLie = contexte?.calepinage?.devis_lie ?? null
  return (
    <CoqueAtelier
      calepinageId={calepinageId}
      retour={devisId ? { to: `/ventes/devis/${devisId}`, libelle: 'Devis' } : { to: '/calepinage', libelle: 'Calepinages' }}
      titre={titreProjet({ devisId, devisReference, calepinageTitre, calepinageId, contexte })}
      sousTitre={sousTitreProjet({ devisId, devisLabel, contexte })}
      enregistrement={enregistrement}
      libelleDevis={devisLie ? 'Resynchroniser le devis' : 'Générer le devis'}
      devisPossible={!lectureSeule}
      carte={<BuilderCarte {...proprietesBuilder} />}
      statut={<div className="cal-coque-statut"><BuilderStatut /></div>}
      groupes={{
        outils: <BuilderOutils {...proprietesBuilder} />,
        toit: <BuilderToit {...proprietesBuilder} />,
        pose: <BuilderPose {...proprietesBuilder} />,
      }}
      alertes={alertes}
      avance={avance}
      ecranProps={ecranProps}
      enregistreLe={enregistreLe}
      onEtape={onEtape}
      renderAtelierPanneaux={atelierPanneaux ? (coque) => (
        <AtelierPanneaux calepinageId={calepinageId} contexte={contexte} {...atelierPanneaux}
          dansCoque expert={coque.expert} onBasculerExpert={coque.onBasculerExpert}
          parcours={coque.parcours} portailDevis={coque.portailDevis} />
      ) : null}
    />
  )
}
