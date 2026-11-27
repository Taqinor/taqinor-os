import { formatNumber } from '../../lib/format'

/* ACAL450 — « Conseils du moteur » : chaque suggestion servie par
   `moteur/calculer` (`suggestions[]`) en phrase simple. Lecture seule : titre,
   gain, confiance et question sont ceux que le moteur sert, aucun gain n'est
   recalculé ici. Seule l'allée gratuite a un bouton d'application existant
   (« Reprendre », panneau Allées) : la carte y renvoie. */

const modules = (n) => `+${formatNumber(n, { maxDecimals: 0 })} module${Math.abs(n) > 1 ? 's' : ''}`

function phraseGain(s) {
  if (!Number.isFinite(s?.gain_modules)) return null
  const kwc = Number.isFinite(s?.gain_kwc)
    ? ` (+${formatNumber(s.gain_kwc, { maxDecimals: 2 })} kWc)` : ''
  return `${modules(s.gain_modules)}${kwc}`
}

export default function CarteConseils({ suggestions = null }) {
  const liste = Array.isArray(suggestions) ? suggestions.filter((s) => s?.code) : []
  if (!liste.length) return null
  return (
    <div className="mt-4 border-t border-border pt-4" data-testid="acal450-conseils">
      <p className="text-sm font-semibold text-foreground">Conseils du moteur</p>
      <ul className="mt-2 space-y-3">
        {liste.map((s, i) => (
          <li key={`${s.code}-${i}`} className="text-sm text-foreground" data-testid="acal450-conseil">
            <p className="font-medium">{s.titre ?? s.code}</p>
            {phraseGain(s) && <p className="text-xs text-muted-foreground">{phraseGain(s)}</p>}
            {s.confiance && (
              <p className="text-xs text-muted-foreground">Confiance : {s.confiance}</p>
            )}
            {s.question_a_poser && <p className="text-xs italic">{s.question_a_poser}</p>}
            {s.code === 'ALLEE_GRATUITE' && (
              <p className="text-xs text-primary-text">
                Appliquer : bouton « Reprendre » du panneau Allées.
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
