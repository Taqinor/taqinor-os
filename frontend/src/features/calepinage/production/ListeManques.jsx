import { Link } from 'react-router-dom'
import { destinationManque } from './lienManque'

/* ACAL397 — « Ce qui manque encore » en liste d'ACTIONS. Une ligne par entrée
   de `parcours.manque` (déjà dédupliquée par code + cible côté serveur,
   ACAL392 ; contrat `calepinage_parcours_guide.json`), triée par gravité ;
   chaque ligne mène au champ exact : onglet + `champ`, ou l'écran des
   réglages (`cible.onglet === 'reglages'`). Rien n'est deviné ici. */
const ORDRE_GRAVITE = { bloquant: 0, a_regler: 1, info: 2 }
const rang = (g) => ORDRE_GRAVITE[g] ?? ORDRE_GRAVITE.info

export default function ListeManques({ calepinageId, manque = [] }) {
  const lignes = manque
    .map((m, i) => ({ m, i }))
    .sort((a, b) => rang(a.m.gravite) - rang(b.m.gravite) || a.i - b.i)
  return (
    <ul className="list-disc pl-5 text-xs" data-testid="calx48-manques-liste">
      {lignes.map(({ m, i }) => {
        // R5B-N5 — LA destination des lignes de manque (`lienManque.js::destinationManque`), la même qu'aux Résultats :
        // la ligne des ombres ouvre l'étape Panneaux, jamais l'onglet Production où elle se lit déjà.
        const vers = destinationManque(calepinageId, m)
        return (
          <li key={`${m.code}-${m.cible?.onglet}-${m.cible?.champ}-${i}`}
            data-gravite={m.gravite}>
            <Link to={vers.to} state={vers.state} className="text-primary underline"
              data-testid="calx48-manque-ligne">
              {m.message}
            </Link>
            {m.nombre > 1 && <span className="ml-1 tabular-nums">{`× ${m.nombre}`}</span>}
          </li>
        )
      })}
    </ul>
  )
}
