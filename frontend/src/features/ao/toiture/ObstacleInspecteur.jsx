/* AOF88 — Inspecteur de l'obstacle sélectionné.
   ----------------------------------------------------------------------------
   Nature (13 types), provenance, et le point qui compte : le DÉGAGEMENT est
   dérivé de la provenance (0,30 m mesuré / 0,50 m sinon) et se recalcule
   INSTANTANÉMENT quand la provenance change. Une valeur saisie à la main reste
   possible mais porte un badge « surchargé » — un dégagement réduit à la main,
   qui décide silencieusement du nombre de panneaux posables, ne doit jamais
   passer inaperçu. */
import { useCallback } from 'react'
import {
  NATURES_OBSTACLE,
  degagementEffectif,
  estLineaire,
} from './repereLettre'

const PROVENANCES = [
  { cle: 'mesure', libelle: 'Mesuré' },
  { cle: 'confirmer', libelle: 'À confirmer' },
  { cle: 'deduit', libelle: 'Déduit du plan' },
  { cle: 'devine', libelle: 'Deviné' },
]

export default function ObstacleInspecteur({ obstacle, onChange }) {
  const majField = useCallback(
    (patch) => onChange?.({ ...obstacle, ...patch }),
    [obstacle, onChange],
  )

  if (!obstacle) {
    return (
      <aside className="ao-inspecteur" data-ao-inspecteur="vide">
        <p>Sélectionnez un obstacle pour l&apos;inspecter.</p>
      </aside>
    )
  }

  const degagement = degagementEffectif(obstacle)

  return (
    <aside className="ao-inspecteur" data-ao-inspecteur={obstacle.repere}>
      <h4>
        Obstacle {obstacle.repere}
        {obstacle.verrouille ? ' (verrouillé)' : ''}
      </h4>

      <label className="ao-champ" htmlFor="ao-obstacle-nature">
        <span>Nature</span>
        <select
          id="ao-obstacle-nature"
          className="form-select"
          value={obstacle.nature}
          onChange={(e) => majField({ nature: e.target.value })}
          disabled={obstacle.verrouille}
        >
          {NATURES_OBSTACLE.map((n) => (
            <option key={n.cle} value={n.cle}>
              {n.libelle}
            </option>
          ))}
        </select>
      </label>

      <label className="ao-champ" htmlFor="ao-obstacle-provenance">
        <span>Provenance</span>
        <select
          id="ao-obstacle-provenance"
          className="form-select"
          value={obstacle.provenance}
          onChange={(e) => majField({ provenance: e.target.value })}
          disabled={obstacle.verrouille}
        >
          {PROVENANCES.map((p) => (
            <option key={p.cle} value={p.cle}>
              {p.libelle}
            </option>
          ))}
        </select>
      </label>

      <label className="ao-champ" htmlFor="ao-obstacle-degagement">
        <span>Dégagement (m)</span>
        <input
          id="ao-obstacle-degagement"
          className="form-control"
          type="text"
          inputMode="decimal"
          placeholder={degagement.derive.toFixed(2)}
          value={obstacle.degagementM ?? ''}
          onChange={(e) => majField({ degagementM: e.target.value })}
          disabled={obstacle.verrouille}
        />
      </label>

      <p data-ao-obstacle-degagement={obstacle.repere}>
        Dégagement appliqué&nbsp;: {degagement.valeur.toFixed(2)} m
        {degagement.surcharge ? (
          <span className="ao-badge-surcharge" data-ao-obstacle-surcharge>
            {' '}
            surchargé (dérivé&nbsp;: {degagement.derive.toFixed(2)} m)
          </span>
        ) : (
          <span className="ao-badge-derive"> dérivé de la provenance</span>
        )}
      </p>

      {degagement.surcharge && (
        <button
          type="button"
          onClick={() => majField({ degagementM: null })}
          data-ao-obstacle-rendre-derive
        >
          Revenir au dégagement dérivé
        </button>
      )}

      {estLineaire(obstacle.nature) && (
        <label className="ao-champ" htmlFor="ao-obstacle-epaisseur">
          <span>Épaisseur (m)</span>
          <input
            id="ao-obstacle-epaisseur"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={obstacle.epaisseurM ?? ''}
            onChange={(e) => majField({ epaisseurM: e.target.value })}
            disabled={obstacle.verrouille}
          />
        </label>
      )}

      <label className="ao-champ" htmlFor="ao-obstacle-verrou">
        <input
          id="ao-obstacle-verrou"
          type="checkbox"
          checked={Boolean(obstacle.verrouille)}
          onChange={(e) => majField({ verrouille: e.target.checked })}
        />
        <span>Verrouiller cet obstacle</span>
      </label>
    </aside>
  )
}
