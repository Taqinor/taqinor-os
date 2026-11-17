import { useId, useState } from 'react'
import { aujourdhuiIso, jourNomme } from '../lib/textes'

/* ============================================================================
   TCH82 — Sélecteur « Quand » (textes.md §2.4 : Aujourd'hui · Demain · Ce soir · Reporter à
   {jour} · Choisir un jour · En réserve · Sans jour) + l'heure (« 10 h »). Un seul composant,
   posé dans la feuille de saisie, la fiche (TCH84) et À trier (« Choisir un jour »).

   La valeur est celle que `planifier/` et `saisie-rapide/` lisent :
     { jour_prevu: 'AAAA-MM-JJ' | null, moment: '' | 'soir', heure_debut: 'HH:MM' | null, quelque_jour: bool }
   Rien n'est corrigé d'office : une date passée ou un jour non travaillé se pose tel quel, c'est
   le serveur qui avertit. Pas de jour = pas d'heure (« Une heure demande un jour prévu. »).
   Maquettes : composants-5.html, composants-6.html.
   ========================================================================== */

// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé (D-ENF22)
export const QUAND_VIDE = { jour_prevu: null, moment: '', heure_debut: null, quelque_jour: false }

/** `iso` + `n` jours, en ISO (calcul en UTC : jamais décalé par l'heure d'été). */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé (D-ENF22)
export function ajouterJours(iso, n) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ''))
  if (!m) return null
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + n))
  return d.toISOString().slice(0, 10)
}

function tuileCourante(valeur, { aujourdhui, demain, reporterA }) {
  if (valeur.quelque_jour) return 'reserve'
  if (!valeur.jour_prevu) return 'sans'
  if (valeur.jour_prevu === aujourdhui) return valeur.moment === 'soir' ? 'soir' : 'aujourdhui'
  if (valeur.jour_prevu === demain) return 'demain'
  if (reporterA && valeur.jour_prevu === reporterA) return 'reporter'
  return 'choisir'
}

export default function SelecteurQuand({
  valeur = QUAND_VIDE,
  onChoisir,
  aujourdhui = aujourdhuiIso(),
  reporterA = null,
}) {
  const idAide = useId()
  const [dateOuverte, setDateOuverte] = useState(false)
  const demain = ajouterJours(aujourdhui, 1)
  const courante = tuileCourante({ ...QUAND_VIDE, ...valeur }, { aujourdhui, demain, reporterA })
  const choisir = (suite) => onChoisir?.({ ...QUAND_VIDE, ...suite })
  const gardeHeure = (jour) => (jour ? valeur.heure_debut ?? null : null)

  const tuiles = [
    { cle: 'aujourdhui', titre: "Aujourd'hui", detail: jourNomme(aujourdhui, aujourdhui) || '', pose: () => choisir({ jour_prevu: aujourdhui, heure_debut: gardeHeure(aujourdhui) }) },
    { cle: 'demain', titre: 'Demain', detail: jourNomme(demain, aujourdhui), pose: () => choisir({ jour_prevu: demain, heure_debut: gardeHeure(demain) }) },
    { cle: 'soir', titre: 'Ce soir', detail: '', pose: () => choisir({ jour_prevu: aujourdhui, moment: 'soir', heure_debut: gardeHeure(aujourdhui) }) },
  ]
  if (reporterA) {
    tuiles.push({
      cle: 'reporter',
      titre: `Reporter à ${jourNomme(reporterA, aujourdhui)}`,
      detail: '',
      pose: () => choisir({ jour_prevu: reporterA, heure_debut: gardeHeure(reporterA) }),
    })
  }
  tuiles.push(
    { cle: 'choisir', titre: 'Choisir un jour', detail: courante === 'choisir' ? jourNomme(valeur.jour_prevu, aujourdhui) : '', pose: () => setDateOuverte(true) },
    { cle: 'reserve', titre: 'En réserve', detail: '', pose: () => { setDateOuverte(false); choisir({ quelque_jour: true }) } },
    { cle: 'sans', titre: 'Sans jour', detail: '', pose: () => { setDateOuverte(false); choisir({}) } },
  )

  const surTuile = (tuile) => () => {
    if (tuile.cle !== 'choisir') setDateOuverte(false)
    tuile.pose()
  }
  const surDate = (e) => {
    const jour = e.target.value
    if (jour) choisir({ jour_prevu: jour, heure_debut: valeur.heure_debut ?? null })
  }
  const surHeure = (e) => {
    if (!valeur.jour_prevu) return
    choisir({ jour_prevu: valeur.jour_prevu, moment: valeur.moment ?? '', heure_debut: e.target.value || null })
  }

  const montrerDate = dateOuverte || courante === 'choisir'
  return (
    <div className="selecteur-quand">
      <div className="quand-tuiles" role="radiogroup" aria-label="Quand je la fais">
        {tuiles.map((tuile) => (
          <button
            key={tuile.cle}
            type="button"
            role="radio"
            aria-checked={courante === tuile.cle || (tuile.cle === 'choisir' && dateOuverte)}
            className="quand-tuile"
            onClick={surTuile(tuile)}
          >
            <b>{tuile.titre}</b>
            {tuile.detail ? <span className="chiffres">{tuile.detail}</span> : null}
          </button>
        ))}
      </div>
      {montrerDate ? (
        <label className="champ-etiquette">
          <span>Jour</span>
          <input
            type="date"
            className="champ"
            aria-label="Choisir un jour"
            value={valeur.jour_prevu ?? ''}
            onChange={surDate}
          />
        </label>
      ) : null}
      <label className="champ-etiquette">
        <span>Heure</span>
        <input
          type="time"
          className="champ chiffres"
          aria-label="Heure"
          aria-describedby={valeur.jour_prevu ? undefined : idAide}
          disabled={!valeur.jour_prevu}
          value={valeur.heure_debut ?? ''}
          onChange={surHeure}
        />
      </label>
      {valeur.jour_prevu ? null : <p id={idAide} className="aide-champ">Une heure demande un jour prévu.</p>}
    </div>
  )
}
