import { useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import RetourAtelier from '../atelier/RetourAtelier'

/* ============================================================================
   CAL159 — L'ÉCRAN POMPAGE DU MODULE : puits, besoin, réservoir, volumes.
   ----------------------------------------------------------------------------
   L'atelier (`pages/ventes/ToitureDesign`) est un atelier de TOITURE : il n'a
   aucune surface pompage. Lorentz COMPASS montre dans un même écran la courbe
   de pompe, le point de fonctionnement et la plage de travail ; c'est cet écran
   qui manquait au module.

   AUCUNE INTERPOLATION ICI. La règle de la tâche est explicite : « toutes les
   valeurs viennent du backend, aucune interpolation de courbe côté écran ». Ce
   composant N'A DONC AUCUN CALCUL : il POSTe la saisie sur
   `/calepinage/calepinages/<pk>/pompage/` (CAL159 moitié serveur, contrat
   `calepinage_pompage.json`) et DESSINE ce que le serveur rend — la courbe
   telle qu'elle est servie, le point de fonctionnement tel qu'il est calculé.
   Deux implémentations d'une seule formule finissent toujours par diverger :
   c'est la raison d'être de la porte HTTP.

   ERREUR SOUS LE CHAMP FAUTIF (règle fondateur) : le serveur rend
   `erreurs: {champ: message}` ; chaque message se pose SOUS son champ, et un
   bandeau NOMME les champs concernés — jamais un « Non enregistré » générique.

   ZÉRO CHIFFRE INVENTÉ : une valeur absente rend « — », jamais 0. Un volume
   non calculable (pompe sans courbe, donc aucune pompe retenue) rend
   « non calculé — pompe sans courbe » : jamais un m³/jour fabriqué.
   ========================================================================== */

const MOIS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']

/** Une grandeur du serveur, ou le tiret de l'inconnu. Jamais un zéro. */
function valeur(brut, suffixe = '') {
  if (brut === null || brut === undefined || brut === '') return '—'
  return `${brut}${suffixe}`
}

/* Les champs de saisie, dans l'ordre du geste réel : le puits d'abord (ce
   qu'on mesure sur site), puis le besoin, puis le réservoir. `cle` est EXACTEMENT
   la clé que le serveur relit et celle qu'il nomme dans `erreurs` — c'est ce
   qui permet de poser le message SOUS le bon champ sans table de correspondance
   à tenir à la main. */
const CHAMPS = [
  ['puits', 'Le puits', [
    ['niveau_statique_m', 'Niveau statique (m)'],
    ['coefficient_rabattement_m_par_m3h', 'Rabattement spécifique (m par m³/h)'],
    ['longueur_tuyauterie_m', 'Longueur de tuyauterie (m)'],
    ['coefficient_frottement', 'Coefficient de frottement'],
    ['hauteur_refoulement_m', 'Hauteur de refoulement (m)'],
    ['hmt_saisie', 'HMT saisie (m) — si le puits n’est pas mesuré'],
  ]],
  ['besoin', 'Le besoin', [
    ['debit_souhaite_m3h', 'Débit souhaité (m³/h)'],
    ['besoin_m3_jour', 'Besoin en eau (m³/jour)'],
    ['heures_pompage', 'Heures de pompage par jour'],
  ]],
  ['reservoir', 'Le réservoir', [
    ['volume_reservoir_m3', 'Volume du réservoir (m³)'],
  ]],
]

/* Clé technique → libellé humain, dérivé de CHAMPS : le bandeau nomme le champ
   comme l'écran l'affiche, pas comme le serveur le code. */
const LIBELLE_CHAMP = Object.fromEntries(
  CHAMPS.flatMap(([, , champs]) => champs),
)

function Champ({ cle, label, valeurSaisie, erreur, onChange }) {
  return (
    <label className="block" data-testid={`cal-pompage-champ-${cle}`}>
      <span className="tech-label text-lune-faint">{label}</span>
      <input
        type="number"
        /* Règle fondateur : l'écran ne SNAPPE ni ne REFUSE jamais une saisie. */
        step="any"
        name={cle}
        id={`cal-pompage-${cle}`}
        value={valeurSaisie ?? ''}
        onChange={(e) => onChange(cle, e.target.value)}
        aria-invalid={erreur ? 'true' : undefined}
        aria-describedby={erreur ? `cal-pompage-erreur-${cle}` : undefined}
        className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
      />
      {erreur && (
        <span
          id={`cal-pompage-erreur-${cle}`}
          data-testid={`cal-pompage-erreur-${cle}`}
          role="alert"
          className="mt-1 block text-xs text-red-300"
        >
          {erreur}
        </span>
      )}
    </label>
  )
}

/* ── LA COURBE, TELLE QUE LE SERVEUR LA SERT ───────────────────────────────
   Un tracé SVG : l'écran met les points servis à l'échelle de la boîte, il
   n'en INTERPOLE aucun et n'en invente aucun. Le point de fonctionnement est
   celui que le serveur a calculé (`point_fonctionnement`), jamais un point
   cherché sur la courbe côté navigateur. */
function CourbePompe({ pompe }) {
  const debits = pompe?.courbe?.debits_m3h
  const hauteurs = pompe?.courbe?.hmt_m
  if (!Array.isArray(debits) || !Array.isArray(hauteurs)
    || debits.length < 2 || debits.length !== hauteurs.length) {
    return (
      <p className="mt-2 text-sm text-lune-soft" data-testid="cal-pompage-courbe-absente">
        Courbe non publiée par la fiche de cette pompe : aucun tracé n’est
        dessiné, et aucun point de fonctionnement n’est deviné.
      </p>
    )
  }

  const L = 320
  const H = 180
  const maxD = Math.max(...debits)
  const maxH = Math.max(...hauteurs)
  const x = (d) => (maxD ? (d / maxD) * (L - 40) + 30 : 30)
  const y = (h) => (maxH ? H - 25 - (h / maxH) * (H - 45) : H - 25)
  const trace = debits.map((d, i) => `${x(d)},${y(hauteurs[i])}`).join(' ')
  const point = pompe.point_fonctionnement ?? {}
  const tracable = point.debit_m3h != null && point.hmt_m != null

  return (
    <svg
      viewBox={`0 0 ${L} ${H}`}
      className="mt-2 w-full max-w-md"
      role="img"
      aria-label="Courbe de la pompe retenue et son point de fonctionnement"
      data-testid="cal-pompage-courbe"
    >
      <polyline points={trace} fill="none" stroke="currentColor"
        className="text-brass-300" strokeWidth="2" />
      {tracable && (
        <circle
          cx={x(point.debit_m3h)} cy={y(point.hmt_m)} r="5"
          className="fill-white" data-testid="cal-pompage-point"
        />
      )}
      <text x="30" y={H - 6} className="fill-current text-lune-faint" fontSize="10">
        Débit (m³/h)
      </text>
      <text x="4" y="12" className="fill-current text-lune-faint" fontSize="10">
        HMT (m)
      </text>
    </svg>
  )
}

/** Les 12 volumes mensuels — ou la phrase qui dit pourquoi il n'y en a pas. */
function VolumesMensuels({ volumes, besoin }) {
  if (!volumes) {
    return (
      <p className="mt-2 text-sm text-lune-soft" data-testid="cal-pompage-volumes-absents">
        non calculé — pompe sans courbe
      </p>
    )
  }
  const pvgis = volumes.m3_mois_pvgis
  const plat = volumes.m3_mois_plat
  const couverture = besoin?.couverture_pct_mois ?? null

  return (
    <table className="mt-2 w-full text-sm" data-testid="cal-pompage-volumes">
      <thead>
        <tr className="tech-label text-lune-faint">
          <th className="text-left">Mois</th>
          <th className="text-right">m³ (plat)</th>
          <th className="text-right">m³ (PVGIS)</th>
          <th className="text-right">Couverture</th>
        </tr>
      </thead>
      <tbody>
        {MOIS.map((mois, i) => (
          <tr key={mois} data-testid={`cal-pompage-mois-${i}`}>
            <td className="text-left text-lune-soft">{mois}</td>
            <td className="fig text-right text-white">{valeur(plat?.[i])}</td>
            <td className="fig text-right text-white">{valeur(pvgis?.[i])}</td>
            <td className="fig text-right text-white">
              {couverture?.[i] == null ? '—' : `${couverture[i]} %`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function PompagePanel({ calepinageId: idPropose }) {
  /* Montable en panneau (le parent passe `calepinageId`) ou en écran à part
     entière sous `/calepinage/:id/pompage` — le routeur monte le composant
     SANS props. Sans ce repli, la route serait déclarée et l'écran vide. */
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [saisie, setSaisie] = useState({})
  const [resultat, setResultat] = useState(null)
  const [refus, setRefus] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const majChamp = (cle, brut) => setSaisie((s) => ({ ...s, [cle]: brut }))

  const calculer = (evenement) => {
    evenement.preventDefault()
    if (!calepinageId) return
    setEnCours(true)
    setRefus(null)
    Promise.resolve(calepinageApi.calepinages.pompage(calepinageId, saisie))
      .then((res) => setResultat(res?.data ?? null))
      .catch((e) => {
        setResultat(null)
        setRefus(e?.response?.data?.detail
          || 'Le dimensionnement n’a pas pu être calculé.')
      })
      .finally(() => setEnCours(false))
  }

  const erreurs = resultat?.erreurs ?? {}
  const champsFautifs = Object.keys(erreurs)
  const pompe = resultat?.pompe ?? null
  const variateur = resultat?.variateur ?? null

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="cine-card mt-6 p-6" data-testid="cal-pompage-panel">
      <p className="tech-label rule-brass text-brass-300">Pompage solaire</p>

      {/* LE BANDEAU NOMME LES CHAMPS FAUTIFS — jamais un refus générique. */}
      {champsFautifs.length > 0 && (
        <p
          role="alert"
          data-testid="cal-pompage-bandeau"
          className="mt-3 rounded border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          Dimensionnement incomplet — à renseigner :{' '}
          {champsFautifs.map((cle, i) => (
            <span key={cle}>
              {i > 0 && ', '}
              {/* Le clic emmène AU champ fautif (règle fondateur) : jamais un
                  refus générique qu'il faut aller chercher soi-même. */}
              <a href={`#cal-pompage-${cle}`} className="underline">
                {LIBELLE_CHAMP[cle] ?? cle}
              </a>
            </span>
          ))}
        </p>
      )}
      {refus && (
        <p role="alert" data-testid="cal-pompage-refus"
          className="mt-3 text-sm text-red-300">{refus}</p>
      )}

      <form onSubmit={calculer} noValidate data-testid="cal-pompage-form">
        {CHAMPS.map(([groupe, titre, champs]) => (
          <fieldset key={groupe} className="mt-4" data-testid={`cal-pompage-groupe-${groupe}`}>
            <legend className="tech-label text-lune-faint">{titre}</legend>
            <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
              {champs.map(([cle, label]) => (
                <Champ
                  key={cle}
                  cle={cle}
                  label={label}
                  valeurSaisie={saisie[cle]}
                  erreur={erreurs[cle]}
                  onChange={majChamp}
                />
              ))}
            </div>
          </fieldset>
        ))}
        <button
          type="submit"
          disabled={enCours}
          data-testid="cal-pompage-calculer"
          className="mt-4 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200"
        >
          {enCours ? 'Calcul en cours…' : 'Calculer le dimensionnement'}
        </button>
      </form>

      {resultat && (
        <div className="mt-6 border-t border-white/10 pt-5">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
            <div data-testid="cal-pompage-hmt">
              <dd className="fig text-lg text-white">
                {valeur(resultat.hmt?.hmt_m, ' m')}
              </dd>
              <dt className="tech-label mt-0.5 text-lune-faint">
                HMT — {valeur(resultat.hmt?.source)}
              </dt>
            </div>
            <div data-testid="cal-pompage-debit">
              <dd className="fig text-lg text-white">
                {valeur(pompe?.debit_hmt_m3h, ' m³/h')}
              </dd>
              <dt className="tech-label mt-0.5 text-lune-faint">Débit à cette HMT</dt>
            </div>
            <div data-testid="cal-pompage-pompe">
              <dd className="text-sm text-white">{valeur(pompe?.nom)}</dd>
              <dt className="tech-label mt-0.5 text-lune-faint">
                Pompe retenue{pompe?.pompe_kw != null ? ` · ${pompe.pompe_kw} kW` : ''}
              </dt>
            </div>
            <div data-testid="cal-pompage-variateur">
              <dd className="text-sm text-white">{valeur(variateur?.nom)}</dd>
              <dt className="tech-label mt-0.5 text-lune-faint">Variateur assorti</dt>
            </div>
            <div data-testid="cal-pompage-autonomie">
              <dd className="fig text-lg text-white">
                {valeur(resultat.besoin?.autonomie_jours, ' j')}
              </dd>
              <dt className="tech-label mt-0.5 text-lune-faint">
                Autonomie du réservoir
              </dt>
            </div>
            <div data-testid="cal-pompage-irradiation">
              <dd className="text-sm text-white">
                {valeur(resultat.volumes?.source_irradiation)}
              </dd>
              <dt className="tech-label mt-0.5 text-lune-faint">Source d’irradiation</dt>
            </div>
          </dl>

          <h3 className="tech-label mt-5 text-lune-faint">Courbe de la pompe</h3>
          <CourbePompe pompe={pompe} />

          <h3 className="tech-label mt-5 text-lune-faint">Volumes mensuels</h3>
          <VolumesMensuels volumes={resultat.volumes} besoin={resultat.besoin} />

          {(resultat.avertissements ?? []).length > 0 && (
            <ul className="mt-4 space-y-1" data-testid="cal-pompage-avertissements">
              {resultat.avertissements.map((texte) => (
                <li key={texte} className="text-xs text-amber-200">{texte}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
    </>
  )
}
