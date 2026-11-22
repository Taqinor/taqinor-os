import PretAEnvoyer from '../commun/PretAEnvoyer'
import PanneauDocuments from './PanneauDocuments'

/* ACAL867 — l'étape Documents GUIDÉE, écran de FIN de parcours (maquette `Documents.dc.html`) :
   « Prêt à envoyer ? » en tête, « Générer le devis » juste dessous, puis les documents du projet.
   Rien n'est recalculé ici : `PretAEnvoyer`, `BoutonDevis` (reçu du rail dans `actionDevis`, une seule
   instance visible) et `PanneauDocuments` sont montés tels quels. */
export default function EtapeDocuments({ actionDevis = null, ...propsDuRail }) {
  return (
    <div data-testid="cal-etape-documents-ecran" className="mt-3 flex flex-col gap-4">
      <PretAEnvoyer calepinageId={propsDuRail.calepinageId} testIdCompte="cal-documents-synthese" />
      {actionDevis ? <div data-testid="cal-etape-documents-devis">{actionDevis}</div> : null}
      <PanneauDocuments
        calepinageId={propsDuRail.calepinageId}
        builderApi={propsDuRail.builderApi}
        onRecharger={propsDuRail.onRecharger}
      />
    </div>
  )
}
