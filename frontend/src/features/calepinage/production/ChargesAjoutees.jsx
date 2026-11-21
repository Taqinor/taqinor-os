import { formatNumber } from '../../../lib/format'

/* ACAL781 — « Charges ajoutées : X kWh/an » avec le détail par charge, lu dans
   `consommation.charges` et `consommation.total_charges_kwh` (forme de
   `calepinage_simulation.json`). Aucune somme ici : le total est celui servi.
   Sans charge déclarée, rien ne s'affiche. */

const nombre = (v) => typeof v === 'number' && Number.isFinite(v)

export default function ChargesAjoutees({ consommation }) {
  const charges = Array.isArray(consommation?.charges) ? consommation.charges : []
  if (charges.length === 0) return null
  const total = consommation.total_charges_kwh
  return (
    <section className="text-sm" data-testid="calx-charges-ajoutees">
      <p className="font-medium">
        {nombre(total)
          ? `Charges ajoutées : ${formatNumber(total, { decimals: 0 })} kWh/an`
          : 'Charges ajoutées'}
      </p>
      <ul className="mt-1 list-disc pl-5">
        {charges.map((c) => (
          <li key={c.code} data-testid={`calx-charge-${c.code}`}>
            <span>{c.libelle}</span>
            {nombre(c.kwh_an) && <span className="tabular-nums">{` — ${formatNumber(c.kwh_an, { decimals: 0 })} kWh/an`}</span>}
            {c.methode && <span>{` · ${String(c.methode).replace(/_/g, ' ')}`}</span>}
            {c.planifie === true && <span>{' · prévue'}</span>}
            {c.plafonnee === true && <span>{' · plafonnée par la borne'}</span>}
          </li>
        ))}
      </ul>
    </section>
  )
}
