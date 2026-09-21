import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'

/* ============================================================================
   CALX18 — L'ÉDITEUR DES POSTES DE PERTES.
   ----------------------------------------------------------------------------
   CONSTAT. `GET pertes/` et `POST enregistrer-pertes/` (`views/simulation.py`,
   CAL139) sont servis, testés, et n'avaient AUCUN consommateur : le catalogue
   de 14 postes NOMMÉS (`services/pertes.py::CATALOGUE`) restait invisible.
   Parité PV*SOL — le bilan de pertes se détaille poste par poste, de l'albédo
   au standby de l'onduleur :
   https://help.valentin-software.com/pvsol/en/pages/results/energy-balance/.

   UNE LIGNE PAR POSTE DU CATALOGUE SERVI — jamais une liste écrite en dur ici :
   le catalogue vient de `GET pertes/`, ce panneau ne connaît aucun nom de
   poste par avance. Chaque poste porte SON pourcentage et SA source, parmi
   `pvgis|fiche|societe|saisie|mesure|hypothese` (CAL238) ; le poste
   `salissure` se saisit en DOUZE valeurs mensuelles (un toit marocain se salit
   l'été et se rince en novembre), jamais une valeur annuelle unique.

   ZÉRO CHIFFRE INVENTÉ. Un poste vide n'est PAS envoyé (il reste simplement
   absent, publié « non sourcé » par CAL139) — mais un poste dont on a TAPÉ un
   pourcentage sans choisir de source est REFUSÉ avant tout envoi réseau, le
   champ fautif pointé (règle fondateur du 08/09/2026 : jamais un « non
   enregistré » générique, l'erreur se pose SOUS le poste et le bandeau le
   NOMME). Le refus 400 du serveur (qui NOMME lui aussi son champ,
   `services/pertes.py`) atterrit exactement au même endroit.

   LE TOTAL AFFICHÉ est la somme des SEULS postes saisis — jamais complétée
   d'une valeur de référence — et porte la mention exacte exigée par la tâche :
   ces postes ne sont plus transmis à PVGIS un par un tels quels, ils entrent
   dans la chaîne de pertes séquentielle (lot 3, CALX141) qui les applique un à
   un ; un poste devenu calculable par cette chaîne en sera écarté et le dira.
   ========================================================================== */

const SOURCES = [
  ['pvgis', 'PVGIS'],
  ['fiche', 'Fiche produit'],
  ['societe', 'Réglage société'],
  ['saisie', 'Saisie'],
  ['mesure', 'Mesure'],
  ['hypothese', 'Hypothèse'],
]

const MOIS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']

/* Le libellé exact exigé par la tâche — jamais reformulé, jamais raccourci :
   c'est la phrase que `PanneauPertes.test.jsx` (et un lecteur humain) doivent
   retrouver mot pour mot. */
const MENTION_TOTAL = 'ces postes ne sont plus transmis à PVGIS : la chaîne '
  + 'de pertes les applique un à un (lot 3) ; un poste devenu calculable par '
  + 'la chaîne y sera écarté et le dira'

function nombre(brut) {
  if (brut === null || brut === undefined || brut === '') return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

/** Un poste MENSUEL est « saisi » dès qu'au moins un de ses 12 mois l'est. */
function moisRenseignes(mensuel) {
  return (mensuel || []).filter((v) => v !== '' && v !== null && v !== undefined)
}

/**
 * Les postes VALIDES à envoyer, et les erreurs de saisie (avant tout réseau).
 * Un poste vide (rien de tapé) est simplement OMIS. Un poste entamé (une
 * valeur, ou un mois) mais sans source, ou un poste mensuel incomplet, est
 * REFUSÉ — jamais envoyé à moitié rempli.
 */
function validerSaisie(catalogue, saisie) {
  const erreurs = {}
  const aEnvoyer = []
  for (const item of catalogue) {
    const s = saisie[item.poste] || {}
    if (item.mensuel) {
      const remplis = moisRenseignes(s.mensuel)
      if (remplis.length === 0) continue
      if (remplis.length < 12) {
        erreurs[item.poste] = 'Les douze mois doivent être renseignés : '
          + `il en manque ${12 - remplis.length}.`
        continue
      }
      if (!s.source) {
        erreurs[item.poste] = 'Une source est requise pour ce poste : sans '
          + 'elle, la valeur ne peut pas être publiée comme fiable.'
        continue
      }
      aEnvoyer.push({
        poste: item.poste, libelle: item.libelle, source: s.source,
        mensuel: s.mensuel.map(Number),
      })
    } else {
      if (s.pct === '' || s.pct === undefined || s.pct === null) continue
      if (!s.source) {
        erreurs[item.poste] = 'Une source est requise pour ce poste : sans '
          + 'elle, la valeur ne peut pas être publiée comme fiable.'
        continue
      }
      aEnvoyer.push({
        poste: item.poste, libelle: item.libelle, source: s.source,
        pct: Number(s.pct),
      })
    }
  }
  return { erreurs, aEnvoyer }
}

/** Le total des postes SAISIS uniquement — jamais complété par le catalogue. */
function totalSaisi(catalogue, saisie) {
  let total = 0
  let compte = 0
  for (const item of catalogue) {
    const s = saisie[item.poste] || {}
    if (item.mensuel) {
      const mois = (s.mensuel || []).map(nombre)
      if (mois.length === 12 && mois.every((v) => v !== null)) {
        total += mois.reduce((a, b) => a + b, 0) / 12
        compte += 1
      }
    } else {
      const v = nombre(s.pct)
      if (v !== null) { total += v; compte += 1 }
    }
  }
  return compte > 0 ? total : null
}

function LignePourcentage({ poste, saisie, erreur, onChangePct, onChangeSource }) {
  return (
    <>
      <label className="block" data-testid={`cal-pertes-champ-${poste}`}>
        <span className="tech-label text-lune-faint">Pourcentage (%)</span>
        <input
          type="number"
          step="any"
          id={`cal-pertes-${poste}`}
          value={saisie.pct ?? ''}
          onChange={(e) => onChangePct(poste, e.target.value)}
          aria-invalid={erreur ? 'true' : undefined}
          aria-describedby={erreur ? `cal-pertes-erreur-${poste}` : undefined}
          className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
        />
      </label>
      <label className="block" data-testid={`cal-pertes-source-${poste}`}>
        <span className="tech-label text-lune-faint">Source</span>
        <select
          id={`cal-pertes-source-select-${poste}`}
          value={saisie.source ?? ''}
          onChange={(e) => onChangeSource(poste, e.target.value)}
          className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
        >
          <option value="">— aucune —</option>
          {SOURCES.map(([cle, label]) => <option key={cle} value={cle}>{label}</option>)}
        </select>
      </label>
    </>
  )
}

function LigneMensuelle({ poste, saisie, erreur, onChangeMois, onChangeSource }) {
  const mois = saisie.mensuel ?? Array(12).fill('')
  return (
    <>
      <div className="sm:col-span-2" data-testid={`cal-pertes-champ-${poste}`}>
        <span className="tech-label text-lune-faint">
          Salissure — douze valeurs mensuelles (%)
        </span>
        <div className="mt-1 grid grid-cols-4 gap-2 sm:grid-cols-6">
          {MOIS.map((libelleMois, i) => (
            <label key={libelleMois} className="block">
              <span className="text-xs text-lune-faint">{libelleMois}</span>
              <input
                type="number"
                step="any"
                id={`cal-pertes-${poste}-mois-${i}`}
                data-testid={`cal-pertes-${poste}-mois-${i}`}
                value={mois[i] ?? ''}
                onChange={(e) => onChangeMois(poste, i, e.target.value)}
                aria-invalid={erreur ? 'true' : undefined}
                aria-describedby={erreur ? `cal-pertes-erreur-${poste}` : undefined}
                className="mt-1 w-full rounded border border-white/15 bg-black/30 px-1 py-1 text-xs text-white"
              />
            </label>
          ))}
        </div>
      </div>
      <label className="block" data-testid={`cal-pertes-source-${poste}`}>
        <span className="tech-label text-lune-faint">Source</span>
        <select
          id={`cal-pertes-source-select-${poste}`}
          value={saisie.source ?? ''}
          onChange={(e) => onChangeSource(poste, e.target.value)}
          className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
        >
          <option value="">— aucune —</option>
          {SOURCES.map(([cle, label]) => <option key={cle} value={cle}>{label}</option>)}
        </select>
      </label>
    </>
  )
}

function LignePoste({ item, saisie, erreur, onChangePct, onChangeSource, onChangeMois }) {
  return (
    <fieldset className="mt-4 border-t border-white/10 pt-4" data-testid={`cal-pertes-poste-${item.poste}`}>
      <legend className="tech-label text-lune-faint">{item.libelle}</legend>
      {item.reference && (
        <p className="text-xs text-lune-soft">{item.reference}</p>
      )}
      <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {item.mensuel
          ? (
            <LigneMensuelle
              poste={item.poste} saisie={saisie} erreur={erreur}
              onChangeMois={onChangeMois} onChangeSource={onChangeSource}
            />
          )
          : (
            <LignePourcentage
              poste={item.poste} saisie={saisie} erreur={erreur}
              onChangePct={onChangePct} onChangeSource={onChangeSource}
            />
          )}
      </div>
      {erreur && (
        <span
          id={`cal-pertes-erreur-${item.poste}`}
          data-testid={`cal-pertes-erreur-${item.poste}`}
          role="alert"
          className="mt-1 block text-xs text-red-300"
        >
          {erreur}
        </span>
      )}
    </fieldset>
  )
}

export default function PanneauPertes({ calepinageId: idPropose }) {
  /* Montable en panneau de l'atelier (le rail passe `calepinageId`) ou en
     écran à part entière — même repli que les autres panneaux du module. */
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [catalogue, setCatalogue] = useState([])
  const [libelleParPoste, setLibelleParPoste] = useState({})
  const [saisie, setSaisie] = useState({})
  // Sans identifiant, il n'y a rien à charger : on ne reste pas bloqué sur
  // l'écran d'attente (l'état initial le dit, jamais une mise à jour
  // synchrone dans l'effet — voir `react-hooks/set-state-in-effect`).
  const [chargement, setChargement] = useState(() => Boolean(calepinageId))
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [motifNonSimulable, setMotifNonSimulable] = useState('')

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.pertes(calepinageId))
      .then((res) => {
        if (annule) return
        const data = res?.data ?? {}
        const cat = Array.isArray(data.catalogue) ? data.catalogue : []
        setCatalogue(cat)
        setLibelleParPoste(Object.fromEntries(cat.map((c) => [c.poste, c.libelle])))
        const parPoste = {}
        for (const p of (data.pertes || [])) parPoste[p.poste] = p
        const init = {}
        for (const item of cat) {
          const existant = parPoste[item.poste]
          if (item.mensuel) {
            init[item.poste] = {
              source: existant?.source ?? '',
              mensuel: Array.isArray(existant?.mensuel) && existant.mensuel.length === 12
                ? existant.mensuel.map(String)
                : Array(12).fill(''),
            }
          } else {
            init[item.poste] = {
              source: existant?.source ?? '',
              pct: existant?.pct !== undefined && existant?.pct !== null
                ? String(existant.pct) : '',
            }
          }
        }
        setSaisie(init)
        setMotifNonSimulable(data.motif_non_simulable ?? '')
      })
      .catch(() => { if (!annule) setCatalogue([]) })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [calepinageId])

  const changerPct = (poste, brut) => setSaisie((s) => (
    { ...s, [poste]: { ...(s[poste] || {}), pct: brut } }
  ))
  const changerSource = (poste, brut) => setSaisie((s) => (
    { ...s, [poste]: { ...(s[poste] || {}), source: brut } }
  ))
  const changerMois = (poste, rang, brut) => setSaisie((s) => {
    const precedent = s[poste] || {}
    const mois = [...(precedent.mensuel ?? Array(12).fill(''))]
    mois[rang] = brut
    return { ...s, [poste]: { ...precedent, mensuel: mois } }
  })

  const total = totalSaisi(catalogue, saisie)

  const enregistrer = () => {
    const { erreurs: erreursSaisie, aEnvoyer } = validerSaisie(catalogue, saisie)
    setErreurs(erreursSaisie)
    setMessage(null)
    if (Object.keys(erreursSaisie).length > 0) return
    if (!calepinageId) return
    setEnCours(true)
    Promise.resolve(calepinageApi.calepinages.enregistrerPertes(calepinageId, { pertes: aEnvoyer }))
      .then((res) => {
        setMessage('Postes de pertes enregistrés.')
        const data = res?.data ?? {}
        setMotifNonSimulable(data.motif_non_simulable ?? '')
      })
      .catch((err) => {
        const corps = err?.response?.data
        if (corps && typeof corps === 'object') {
          const mappees = {}
          for (const [champ, valeur] of Object.entries(corps)) {
            mappees[champ] = Array.isArray(valeur) ? valeur[0] : valeur
          }
          setErreurs(mappees)
        } else {
          setErreurs({ pertes: 'Enregistrement refusé par le serveur.' })
        }
      })
      .finally(() => setEnCours(false))
  }

  const champsFautifs = Object.keys(erreurs)

  if (chargement) {
    return (
      <p className="mt-3 text-sm text-lune-faint" data-testid="cal-pertes-chargement">
        Chargement des postes de pertes…
      </p>
    )
  }

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-pertes-panel">
      <p className="tech-label rule-brass text-brass-300">Postes de pertes</p>

      {champsFautifs.length > 0 && (
        <p
          role="alert"
          data-testid="cal-pertes-bandeau"
          className="mt-3 rounded border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          Postes incomplets — à corriger :{' '}
          {champsFautifs.map((cle, i) => (
            <span key={cle}>
              {i > 0 && ', '}
              <a href={`#cal-pertes-${cle}`} className="underline">
                {libelleParPoste[cle] ?? cle}
              </a>
            </span>
          ))}
        </p>
      )}

      {catalogue.map((item) => (
        <LignePoste
          key={item.poste}
          item={item}
          saisie={saisie[item.poste] || {}}
          erreur={erreurs[item.poste]}
          onChangePct={changerPct}
          onChangeSource={changerSource}
          onChangeMois={changerMois}
        />
      ))}

      <div className="mt-6 border-t border-white/10 pt-4" data-testid="cal-pertes-total">
        <p className="tech-label text-lune-faint">Total des postes saisis</p>
        <p className="fig text-lg text-white">
          {total === null ? '—' : `${total.toFixed(2)} %`}
        </p>
        <p className="mt-1 text-xs text-lune-soft" data-testid="cal-pertes-mention">
          {MENTION_TOTAL}
        </p>
      </div>

      {motifNonSimulable && (
        <p className="mt-3 text-xs text-amber-200" data-testid="cal-pertes-motif-non-simulable">
          {motifNonSimulable}
        </p>
      )}

      <button
        type="button"
        onClick={enregistrer}
        disabled={enCours}
        data-testid="cal-pertes-enregistrer"
        className="mt-4 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200"
      >
        {enCours ? 'Enregistrement…' : 'Enregistrer les postes de pertes'}
      </button>

      {message && (
        <p className="mt-3 text-sm text-lune-soft" role="status" data-testid="cal-pertes-message">
          {message}
        </p>
      )}
    </div>
  )
}
