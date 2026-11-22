import PretAEnvoyer from '../commun/PretAEnvoyer'
import PanneauDocuments from './PanneauDocuments'

/* ACAL867 / ACAL1193 — l'étape Documents GUIDÉE, écran de FIN de parcours (maquette `Documents.dc.html`),
   sur TOUTE la largeur du centre : à gauche « Prêt à envoyer ? » rangé par étape, avec « Générer le devis »
   en pied de carte ; à droite « Documents du projet » (cinq cartes). Rien n'est recalculé ici :
   `PretAEnvoyer` (contrôles servis), `BoutonDevis` (reçu du rail dans `actionDevis`, une seule instance
   visible, toutes ses gardes) et `PanneauDocuments` (mêmes téléchargements) sont montés tels quels ;
   le panneau d'origine reste la vue Expert, sous la colonne de droite.
   `enregistreLe` (ISO) : l'heure de la version enregistrée, quand l'atelier la relaie — sinon la ligne
   « Faits à partir de la version enregistrée à … » n'est pas écrite. */
export default function EtapeDocuments({ actionDevis = null, enregistreLe = null, ...propsDuRail }) {
  return (
    <div data-testid="cal-etape-documents-ecran" className="cdoc-ecran">
      <div data-testid="cal-docs-controles" className="cdoc-colonne">
        <PretAEnvoyer
          calepinageId={propsDuRail.calepinageId}
          testIdCompte="cal-documents-synthese"
          groupes
          pied={actionDevis
            ? <div data-testid="cal-etape-documents-devis" className="cdoc-devis">{actionDevis}</div> : null}
        />
      </div>
      <div className="cdoc-colonne">
        <PanneauDocuments
          guide
          calepinageId={propsDuRail.calepinageId}
          builderApi={propsDuRail.builderApi}
          onRecharger={propsDuRail.onRecharger}
          enregistreLe={enregistreLe}
        />
      </div>
    </div>
  )
}
