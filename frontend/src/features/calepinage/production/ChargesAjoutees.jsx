import { formatNumber } from '../../../lib/format'

/* ACAL781 — « Charges ajoutées : X kWh/an » avec le détail par charge, lu dans
   `consommation.charges` et `consommation.total_charges_kwh` (forme de
   `calepinage_simulation.json`). Aucune somme ici : le total est celui servi.
   ACAL1646 — une charge que le serveur IGNORE (déjà comprise dans les factures) est nommée : « Voiture électrique :
   ignorée — <motif> ». Le serveur la dit dans `consommation.avertissements` (« La charge n°2 (vehicule) est déjà
   comprise… ») : on en lit le type (libellé métier, jamais le code) et le motif servi.
   ACAL1608 — la source de la courbe de base est dite : `consommation.courbe_origine` (« facture du lead »…).
   Sans charge déclarée ni ignorée, aucune ligne de charges. */

const nombre = (v) => typeof v === 'number' && Number.isFinite(v)

// Les libellés métier des types de charge (`courbe_charge.TYPES_DE_CHARGE`).
const LIBELLE_TYPE = {
  vehicule: 'Voiture électrique',
  pac: 'Pompe à chaleur',
  chauffe_eau: 'Chauffe-eau',
  clim: 'Climatisation',
  piscine: 'Piscine',
}

// `consommation.courbe_origine` (`courbe_charge.ORIGINES`) en mots de tous les jours.
const LIBELLE_ORIGINE = {
  layout: "courbe saisie dans l'atelier",
  import_intervalle: 'relevé importé',
  profil_mensuel: 'douze mois saisis',
  profil_type: 'profil type de la société',
  facture_lead: 'facture du lead',
}

// « La charge n°2 (vehicule) est déjà comprise dans les factures : elle est ignorée pour ne pas être comptée deux fois (…). »
const AVIS_IGNOREE = /^La charge n°\d+ \(([^)]*)\) est (.+?) : elle est ignorée (.+)$/

function chargesIgnorees(avertissements) {
  const liste = Array.isArray(avertissements) ? avertissements : []
  return liste.flatMap((avis) => {
    const m = typeof avis === 'string' ? AVIS_IGNOREE.exec(avis) : null
    if (!m) return []
    const code = m[1].trim()
    return [{ code, libelle: LIBELLE_TYPE[code] ?? 'Une charge', motif: `${m[2]}, ${m[3].replace(/\.$/, '')}` }]
  })
}

export default function ChargesAjoutees({ consommation }) {
  const charges = Array.isArray(consommation?.charges) ? consommation.charges : []
  const ignorees = chargesIgnorees(consommation?.avertissements)
  const origine = LIBELLE_ORIGINE[consommation?.courbe_origine]
  const ligneOrigine = origine ? (
    <p className="text-sm text-muted-foreground" data-testid="calx-courbe-origine">{`Courbe de base : ${origine}`}</p>
  ) : null
  if (charges.length === 0 && ignorees.length === 0) return ligneOrigine
  const total = consommation.total_charges_kwh
  return (
    <>
      {ligneOrigine}
      <section className="text-sm" data-testid="calx-charges-ajoutees">
        {charges.length > 0 && (
          <p className="font-medium">
            {nombre(total)
              ? `Charges ajoutées : ${formatNumber(total, { decimals: 0 })} kWh/an`
              : 'Charges ajoutées'}
          </p>
        )}
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
          {ignorees.map((c, i) => (
            <li key={`${c.code}-${i}`} data-testid={`calx-charge-ignoree-${c.code}`}>
              {`${c.libelle} : ignorée — ${c.motif}`}
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
