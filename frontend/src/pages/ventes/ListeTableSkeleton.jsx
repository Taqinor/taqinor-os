import { Card, SkeletonTableRow } from '../../ui'

/* Squelette PARTAGÉ des listes Devis / Factures : reprend les colonnes du vrai
   tableau pour que la mise en page ne saute pas à l'arrivée des données.
   `largeurSelection` = largeur de la colonne de sélection ; `entetes` = les
   en-têtes suivants ([libellé, classe optionnelle]). */
export default function ListeTableSkeleton({ largeurSelection, entetes }) {
  return (
    <Card className="mt-4 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th className={largeurSelection} />
              {entetes.map(([libelle, classe]) => (
                <th key={libelle} className={classe}>{libelle}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 6 }).map((unused, i) => (
              <SkeletonTableRow key={i} columns={8} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
