/* ACAL1028 — le CROQUIS DE PRINCIPE grisé de l'onglet Schéma unifilaire, montré seulement quand la fiche
   technique est incomplète (le serveur refuse alors le schéma). Dessin STATIQUE de la chaîne générique
   (modules → coffret DC → onduleur → protections AC → réseau) : aucune donnée lue, aucune valeur, aucun
   nombre, aucun libellé de produit ; jamais présenté comme le schéma de la conception. */
const ETAGES = ['Modules', 'Coffret DC', 'Onduleur', 'Protections AC', 'Réseau']

/* ACAL1427 — les étages sont des boîtes HTML empilées (texte 14 px, jamais un SVG mis à l'échelle du rail : ses libellés
   tombaient à ~3 px dans le panneau latéral d'Avancé) ; une colonne tient à toutes les largeurs. */
export default function CroquisSchemaGrise() {
  return (
    <figure className="m-0 flex flex-col gap-2" data-testid="acal1028-croquis">
      <ol aria-label="Croquis de principe d’une installation, sans valeur"
        className="m-0 flex max-w-xs list-none flex-col items-stretch p-0 text-muted-foreground">
        {ETAGES.map((nom, rang) => (
          <li key={nom} className="flex flex-col items-center">
            {rang > 0 ? <span aria-hidden="true" className="h-3 w-px bg-border" /> : null}
            <span className="w-full rounded border border-dashed border-border px-3 py-2 text-center text-sm">{nom}</span>
          </li>
        ))}
      </ol>
      <figcaption className="text-sm text-muted-foreground" data-testid="acal1028-legende">
        Croquis de principe, sans valeur : votre schéma s’affichera quand les champs ci-dessous seront remplis.
      </figcaption>
    </figure>
  )
}
