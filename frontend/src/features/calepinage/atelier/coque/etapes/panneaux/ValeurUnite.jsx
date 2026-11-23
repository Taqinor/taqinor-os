import { scinderUnite } from './formats'

/* ACAL1445 / ACAL1829 — « un chiffre dessiné » (LANGAGE.md, changement 3) : l'unité d'une valeur lue (« 6,96 kWc »,
   « 107 m² », « 11 480 kWh / an », « 82 % ») est écrite plus petite et en gris, sur la même ligne de base. Le TEXTE reste
   celui de la lecture : seule la forme change, jamais le contenu. Pas d'unité lue → la valeur est rendue telle quelle. */
export default function ValeurUnite({ texte }) {
  const { valeur, unite } = scinderUnite(texte)
  if (!unite) return valeur
  return <>{valeur} <span className="cal-unite">{unite}</span></>
}
