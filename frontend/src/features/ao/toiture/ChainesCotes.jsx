/* AOF85 — Chaînes de cotes : création, édition inline, rendu type plan.
   ----------------------------------------------------------------------------
   Une CHAÎNE est une suite de segments cumulés le long d'un axe, avec sa cote
   mesurée TOTALE et SA tolérance propre. C'est le différenciateur de l'atelier :
   le tracé from scratch est un outil de TOPOGRAPHE, pas un outil de dessin. On
   ne saisit pas « un rectangle » — on saisit 4,10 + 8,82 + 12,70 le long d'une
   façade, et un total mesuré de 25,62 qui doit refermer.

   Chaque segment porte SA provenance (mesuré / à confirmer / plan-déduit /
   deviné) et la cote se colore en conséquence (AOF9) : un plan où l'on ne
   distingue pas ce qui a été mesuré de ce qui a été supposé est un plan qui
   ment. L'arbitrage des écarts (fermeture, prorata) est l'affaire du panneau
   Fermetures (AOF86) — ici on saisit, on édite, on rend. */
import { useCallback, useMemo, useState } from 'react'
import Cote from './Cote'

const PROVENANCES = [
  { cle: 'mesure', libelle: 'Mesuré' },
  { cle: 'confirmer', libelle: 'À confirmer' },
  { cle: 'deduit', libelle: 'Déduit du plan' },
  { cle: 'devine', libelle: 'Deviné' },
]

// Tolérances usuelles d'un relevé de toiture, reprises telles quelles du relevé
// de référence : 2 cm pour une file courte, 5 cm pour une façade, 25 cm pour un
// développé d'arc. La chaîne porte SA tolérance — jamais une constante globale.
const TOLERANCES = [0.02, 0.05, 0.25]

let compteur = 0
function nouvelId(prefixe) {
  compteur += 1
  return `${prefixe}-${compteur}`
}

// Taille d'une liste, sans savoir ce qu'elle contient : sert au numéro d'ordre
// d'une nouvelle file et au hook de test. Volontairement anonyme (même parti
// pris que `echelle()` dans AlleeGratuiteChart) — une chaîne de COTES n'a rien
// à voir avec les chaînes électriques du moteur, et rien n'est dérivé ici d'un
// chiffre métier (garde AOF94).
const combien = (liste) => liste.length

function nombre(valeur) {
  const n = Number(String(valeur ?? '').replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

export default function ChainesCotes({
  chainesInitiales = [],
  pixelsParMetre = 1,
  onChange,
}) {
  const [chaines, setChaines] = useState(chainesInitiales)

  const publier = useCallback(
    (suivantes) => {
      setChaines(suivantes)
      onChange?.(suivantes)
    },
    [onChange],
  )

  const ajouterChaine = useCallback(
    (axe) => {
      publier([
        ...chaines,
        {
          id: nouvelId('chaine'),
          axe,
          nom: axe === 'x'
            ? `File horizontale ${combien(chaines) + 1}`
            : `File verticale ${combien(chaines) + 1}`,
          origine: { x: 0, y: 0 },
          tolerance: 0.05,
          coteMesuree: 0,
          segments: [],
        },
      ])
    },
    [chaines, publier],
  )

  const majChaine = useCallback(
    (id, patch) => {
      publier(chaines.map((c) => (c.id === id ? { ...c, ...patch } : c)))
    },
    [chaines, publier],
  )

  const ajouterSegment = useCallback(
    (id) => {
      publier(
        chaines.map((c) =>
          c.id === id
            ? {
                ...c,
                segments: [
                  ...c.segments,
                  {
                    id: nouvelId('seg'),
                    libelle: `S${c.segments.length + 1}`,
                    valeur: 0,
                    provenance: 'mesure',
                  },
                ],
              }
            : c,
        ),
      )
    },
    [chaines, publier],
  )

  const majSegment = useCallback(
    (idChaine, idSegment, patch) => {
      publier(
        chaines.map((c) =>
          c.id === idChaine
            ? {
                ...c,
                segments: c.segments.map((s) => (s.id === idSegment ? { ...s, ...patch } : s)),
              }
            : c,
        ),
      )
    },
    [chaines, publier],
  )

  const supprimerSegment = useCallback(
    (idChaine, idSegment) => {
      publier(
        chaines.map((c) =>
          c.id === idChaine
            ? { ...c, segments: c.segments.filter((s) => s.id !== idSegment) }
            : c,
        ),
      )
    },
    [chaines, publier],
  )

  // Positions cumulées : chaque segment démarre là où le précédent s'arrête.
  const rendus = useMemo(
    () =>
      chaines.map((chaine, indexChaine) => {
        let curseur = 0
        const cotes = chaine.segments.map((segment) => {
          const debut = curseur
          curseur += nombre(segment.valeur)
          return { segment, debut, fin: curseur }
        })
        return { chaine, cotes, somme: curseur, decalage: (indexChaine + 1) * 1.2 }
      }),
    [chaines],
  )

  return (
    <section className="ao-chaines" data-ao-chaines={combien(chaines)}>
      <div className="ao-chaines-actions">
        <button type="button" onClick={() => ajouterChaine('x')} data-ao-chaine-nouvelle="x">
          Nouvelle chaîne horizontale
        </button>
        <button type="button" onClick={() => ajouterChaine('y')} data-ao-chaine-nouvelle="y">
          Nouvelle chaîne verticale
        </button>
      </div>

      {/* Rendu type plan. Le groupe est mis à l'échelle : les cotes compensent
          pour rester lisibles à tous les zooms (voir Cote.jsx). */}
      <svg
        className="ao-chaines-planche"
        viewBox="-4 -4 80 80"
        role="img"
        aria-label="Planche des chaînes de cotes"
        data-ao-chaines-planche
      >
        <g transform={`scale(${pixelsParMetre})`}>
          {rendus.map(({ chaine, cotes, somme, decalage }) => (
            <g key={chaine.id} data-ao-chaine={chaine.id} data-ao-chaine-axe={chaine.axe}>
              {cotes.map(({ segment, debut, fin }) => (
                <Cote
                  key={segment.id}
                  axe={chaine.axe}
                  x1={chaine.axe === 'x' ? debut : chaine.origine.x}
                  y1={chaine.axe === 'x' ? chaine.origine.y : debut}
                  x2={chaine.axe === 'x' ? fin : chaine.origine.x}
                  y2={chaine.axe === 'x' ? chaine.origine.y : fin}
                  valeur={nombre(segment.valeur)}
                  provenance={segment.provenance}
                  decalage={decalage}
                  pixelsParMetre={pixelsParMetre}
                />
              ))}
              {/* La cote TOTALE de la chaîne, en dessous des segments. */}
              {cotes.length > 0 && (
                <Cote
                  axe={chaine.axe}
                  x1={chaine.axe === 'x' ? 0 : chaine.origine.x}
                  y1={chaine.axe === 'x' ? chaine.origine.y : 0}
                  x2={chaine.axe === 'x' ? somme : chaine.origine.x}
                  y2={chaine.axe === 'x' ? chaine.origine.y : somme}
                  valeur={nombre(chaine.coteMesuree) || somme}
                  provenance={nombre(chaine.coteMesuree) ? 'mesure' : 'deduit'}
                  decalage={decalage + 1.2}
                  pixelsParMetre={pixelsParMetre}
                />
              )}
            </g>
          ))}
        </g>
      </svg>

      {rendus.map(({ chaine, somme }) => (
        <fieldset className="ao-chaine" key={chaine.id} data-ao-chaine-edition={chaine.id}>
          <legend>
            {chaine.nom} — axe {chaine.axe === 'x' ? 'horizontal' : 'vertical'}
          </legend>

          <label className="ao-champ" htmlFor={`${chaine.id}-mesuree`}>
            <span>Cote mesurée totale (m)</span>
            <input
              id={`${chaine.id}-mesuree`}
              className="form-control"
              type="text"
              inputMode="decimal"
              value={chaine.coteMesuree}
              onChange={(e) => majChaine(chaine.id, { coteMesuree: e.target.value })}
            />
          </label>

          <label className="ao-champ" htmlFor={`${chaine.id}-tolerance`}>
            <span>Tolérance (m)</span>
            <select
              id={`${chaine.id}-tolerance`}
              className="form-select"
              value={chaine.tolerance}
              onChange={(e) => majChaine(chaine.id, { tolerance: Number(e.target.value) })}
            >
              {TOLERANCES.map((t) => (
                <option key={t} value={t}>
                  {t.toFixed(2)}
                </option>
              ))}
            </select>
          </label>

          <table className="data-table ao-chaine-segments">
            <caption>Segments cumulés</caption>
            <thead>
              <tr>
                <th scope="col">Repère</th>
                <th scope="col">Longueur (m)</th>
                <th scope="col">Provenance</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {chaine.segments.map((s) => (
                <tr key={s.id}>
                  <td>
                    <input
                      className="form-control"
                      value={s.libelle}
                      aria-label={`Repère du segment ${s.libelle}`}
                      onChange={(e) => majSegment(chaine.id, s.id, { libelle: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="form-control"
                      type="text"
                      inputMode="decimal"
                      value={s.valeur}
                      aria-label={`Longueur du segment ${s.libelle}`}
                      onChange={(e) => majSegment(chaine.id, s.id, { valeur: e.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      className="form-select"
                      value={s.provenance}
                      aria-label={`Provenance du segment ${s.libelle}`}
                      onChange={(e) => majSegment(chaine.id, s.id, { provenance: e.target.value })}
                    >
                      {PROVENANCES.map((p) => (
                        <option key={p.cle} value={p.cle}>
                          {p.libelle}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button type="button" onClick={() => supprimerSegment(chaine.id, s.id)}>
                      Supprimer {s.libelle}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <button type="button" onClick={() => ajouterSegment(chaine.id)}>
            Ajouter un segment à {chaine.nom}
          </button>

          <p data-ao-chaine-somme={chaine.id}>
            Somme des segments&nbsp;: {somme.toFixed(2)} m — cote mesurée&nbsp;:{' '}
            {nombre(chaine.coteMesuree).toFixed(2)} m
          </p>
        </fieldset>
      ))}
    </section>
  )
}
