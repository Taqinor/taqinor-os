/* ACAL1028 — le CROQUIS DE PRINCIPE grisé de l'onglet Schéma unifilaire, montré seulement quand la fiche
   technique est incomplète (le serveur refuse alors le schéma). Dessin STATIQUE de la chaîne générique
   (modules → coffret DC → onduleur → protections AC → réseau) : aucune donnée lue, aucune valeur, aucun
   nombre, aucun libellé de produit ; jamais présenté comme le schéma de la conception. */
const ETAGES = ['Modules', 'Coffret DC', 'Onduleur', 'Protections AC', 'Réseau']
const LARGEUR = 112
const ECART = 28
const HAUTEUR = 56

export default function CroquisSchemaGrise() {
  const largeurTotale = ETAGES.length * LARGEUR + (ETAGES.length - 1) * ECART
  return (
    <figure className="m-0 flex flex-col gap-2" data-testid="acal1028-croquis">
      <svg
        viewBox={`0 0 ${largeurTotale} ${HAUTEUR + 8}`}
        role="img"
        aria-label="Croquis de principe d’une installation, sans valeur"
        className="w-full max-w-3xl text-muted-foreground opacity-60"
      >
        {ETAGES.map((nom, rang) => {
          const x = rang * (LARGEUR + ECART)
          return (
            <g key={nom}>
              <rect x={x} y="4" width={LARGEUR} height={HAUTEUR} rx="4" fill="none"
                stroke="currentColor" strokeWidth="1.5" strokeDasharray="5 4" />
              <text x={x + LARGEUR / 2} y={4 + HAUTEUR / 2 + 4} textAnchor="middle" fontSize="12" fill="currentColor">
                {nom}
              </text>
              {rang < ETAGES.length - 1
                ? <line x1={x + LARGEUR} y1={4 + HAUTEUR / 2} x2={x + LARGEUR + ECART} y2={4 + HAUTEUR / 2}
                  stroke="currentColor" strokeWidth="1.5" />
                : null}
            </g>
          )
        })}
      </svg>
      <figcaption className="text-sm text-muted-foreground" data-testid="acal1028-legende">
        Croquis de principe, sans valeur : votre schéma s’affichera quand les champs ci-dessous seront remplis.
      </figcaption>
    </figure>
  )
}
