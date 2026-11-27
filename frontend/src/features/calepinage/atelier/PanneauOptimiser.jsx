import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { formatNumber } from '../../../lib/format'
import { Button, Card, Input, Label, Spinner } from '../../../ui'
import { refusDepuisErreur } from '../production/suiviSimulation'
import useSuiviJob from '../production/useSuiviJob'

/* ============================================================================
   ACAL469 — L'ONGLET « OPTIMISER » : lancer le balayage d'un pan, voir la carte
   des résultats, appliquer l'optimum en un geste.
   ----------------------------------------------------------------------------
   Contrat partagé `calepinage_balayage.json` (ACAL388) : `POST balayage/` rend
   un accusé 202, suivi par `useSuiviJob` (comme `PanneauProduction`) ; le
   résultat (`grille[]`, `optimum`, `complete`, `socle_manquant`) est AFFICHÉ tel
   que servi — aucun calcul de rendement ici. La couleur d'une case est la
   position de son `rendement_specifique_kwh_kwc` entre le plus bas et le plus
   haut de la grille.

   « Appliquer l'optimum » épingle inclinaison et azimut dans l'atelier par
   `builderApi.appliquerSection('choixConception', …)` : rien n'est enregistré
   avant « Enregistrer le calepinage ».
   ========================================================================== */
const AXES = [
  { nom: 'inclinaison_deg', libelle: 'Inclinaison (°)', defaut: { min: '10', max: '40', pas: '10' } },
  { nom: 'azimut_deg', libelle: 'Azimut (°, 180 = Sud)', defaut: { min: '150', max: '210', pas: '30' } },
]

/* ACAL1629 — un chemin de réglage société (« parametres.simulation.mode_meteo »,
   « meteo.gi_w_m2 ») n'est jamais montré : la phrase du serveur suffit. Un autre
   champ pointé (« axes.inclinaison_deg ») reste nommé. */
const CLE_TECHNIQUE = /^(parametres|meteo)\.[a-z0-9_.[\]]+$/i

const nombre = (v) => (v === '' || v === null ? NaN : Number(v))

/* ACAL813 — « Optimiser pour le mois de » : critère `{nom: 'mois', mois}` du
   balayage (ACAL812) ; la réponse est LUE de `optimum_mois`, `optimum` et
   `ecart_mois_kwh`. « Toute l'année » (défaut) ne poste aucun critère. */
const nomDuMois = (m) => new Date(2000, m - 1, 1).toLocaleDateString('fr-FR', { month: 'long' })
const MOIS = Array.from({ length: 12 }, (_, i) => i + 1)
const degres = (v) => `${formatNumber(v, { decimals: 0 })}°`

function OptimumDuMois({ resultat, mois, onAppliquer }) {
  const duMois = resultat?.optimum_mois
  const annee = resultat?.optimum
  if (!mois || !duMois || !annee) return null
  const ecart = Number(resultat.ecart_mois_kwh)
  const nom = nomDuMois(mois)
  return (
    <div className="flex flex-wrap items-center gap-3">
      <p className="text-sm" data-testid="acal813-mois">
        {degres(duMois.inclinaison_deg)} pour {nom}, {degres(annee.inclinaison_deg)} pour l’année
        {Number.isFinite(ecart) ? ` : ${ecart >= 0 ? '+' : '−'} ${formatNumber(Math.abs(ecart), { decimals: 0 })} kWh en ${nom}` : ''}
      </p>
      {onAppliquer && (
        <Button variant="outline" onClick={() => onAppliquer(duMois)} data-testid="acal813-appliquer">
          Appliquer pour ce mois
        </Button>
      )}
    </div>
  )
}

/** Fond de case : du plus bas (clair) au plus haut (vert) rendement de la grille. */
function fondDeCase(valeur, bas, haut) {
  const t = haut > bas ? (valeur - bas) / (haut - bas) : 1
  return `hsl(${Math.round(40 + 80 * t)} 60% 85%)`
}

export default function PanneauOptimiser({ calepinageId, builderApi = null, lectureSeule = false }) {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [pan, setPan] = useState('1')
  const [bornes, setBornes] = useState(() => Object.fromEntries(AXES.map((a) => [a.nom, a.defaut])))
  const [resultat, setResultat] = useState(null)
  const [refus, setRefus] = useState(null)
  const [message, setMessage] = useState(null)
  const [mois, setMois] = useState('')
  const [moisLance, setMoisLance] = useState(null)
  const suivi = useSuiviJob({
    intervalleMs: 2000,
    surIssue: (issue, job) => {
      if (issue.etat === 'succes') setResultat(job?.resultat ?? null)
      else setRefus(issue.refus)
    },
    surInterruption: () => setRefus({ champ: '', motif: 'Le suivi du balayage a été interrompu.' }),
  })

  const modifier = (axe, cle, valeur) => setBornes((b) => ({ ...b, [axe]: { ...b[axe], [cle]: valeur } }))

  const lancer = () => {
    setRefus(null)
    setMessage(null)
    setResultat(null)
    const axes = AXES.map((a) => ({
      nom: a.nom,
      min: nombre(bornes[a.nom].min), max: nombre(bornes[a.nom].max), pas: nombre(bornes[a.nom].pas),
    }))
    const corps = { pan: nombre(pan), axes }
    if (mois) corps.critere = { nom: 'mois', mois: Number(mois) }
    setMoisLance(mois ? Number(mois) : null)
    suivi.lancer(calepinageApi.calepinages.balayer(calepinageId, corps), {
      surSynchrone: () => setRefus({ champ: '', motif: 'Réponse inattendue du serveur : le balayage n’a pas démarré.' }),
      surErreur: (e) => setRefus(refusDepuisErreur(e)),
    })
  }

  const grille = Array.isArray(resultat?.grille) ? resultat.grille : []
  const optimum = resultat?.optimum ?? null
  const rendements = grille.map((l) => l.rendement_specifique_kwh_kwc)
  const bas = Math.min(...rendements)
  const haut = Math.max(...rendements)
  const colonnes = AXES.filter((a) => grille.some((l) => l[a.nom] !== undefined))
  const appliquable = !!optimum && !!builderApi?.appliquerSection && !lectureSeule
    && colonnes.length > 0

  const appliquer = (point = optimum) => {
    const corps = { epingles: [] }
    if (point.inclinaison_deg !== undefined) { corps.tilt = point.inclinaison_deg; corps.epingles.push('tilt') }
    if (point.azimut_deg !== undefined) { corps.azimuth = point.azimut_deg; corps.epingles.push('azimuth') }
    builderApi.appliquerSection('choixConception', corps)
    setMessage('Optimum appliqué à l’atelier : enregistrez le calepinage pour le conserver.')
  }

  return (
    <Card className="space-y-3 p-4" data-testid="acal469-panneau">
      <p className="text-sm text-muted-foreground">
        Balayage d’un pan à orientation libre (champ au sol, ombrière, toit plat à châssis).
        Rien n’est enregistré avant « Enregistrer le calepinage ».
      </p>
      <p className="text-sm text-muted-foreground" data-testid="acal1629-meteo">
        L’optimisation demande une année type ou une série horaire : si la météo de la
        société est réglée sur plusieurs années, passez la fenêtre météo à un an
        (Réglages simulation) avant de lancer.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <Label htmlFor="acal469-pan">Pan n°</Label>
          <Input id="acal469-pan" type="number" step="any" value={pan} onChange={(e) => setPan(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="acal813-critere">Optimiser pour le mois de</Label>
          <select id="acal813-critere" value={mois} onChange={(e) => setMois(e.target.value)}
            className="min-h-11 w-full rounded-md border border-input bg-card px-2 text-sm text-foreground">
            <option value="">Toute l’année</option>
            {MOIS.map((m) => <option key={m} value={m}>{nomDuMois(m)}</option>)}
          </select>
        </div>
        {AXES.map((a) => (
          <fieldset key={a.nom} className="flex items-end gap-2">
            <legend className="text-xs text-muted-foreground">{a.libelle}</legend>
            {['min', 'max', 'pas'].map((cle) => (
              <div key={cle}>
                <Label htmlFor={`acal469-${a.nom}-${cle}`}>{cle}</Label>
                <Input
                  id={`acal469-${a.nom}-${cle}`} type="number" step="any"
                  value={bornes[a.nom][cle]} onChange={(e) => modifier(a.nom, cle, e.target.value)}
                />
              </div>
            ))}
          </fieldset>
        ))}
        {peutGerer && !lectureSeule && (
          <Button onClick={lancer} disabled={suivi.enCours} data-testid="acal469-lancer">
            {suivi.enCours ? 'Balayage en cours…' : 'Lancer'}
          </Button>
        )}
        {suivi.enCours && <Spinner />}
      </div>

      {refus && (
        <p className="text-sm text-danger" role="alert" data-testid="acal469-refus">
          {refus.champ && !CLE_TECHNIQUE.test(refus.champ) ? `${refus.champ} : ` : ''}{refus.motif}
        </p>
      )}

      {resultat && resultat.complete === false && (
        <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm" data-testid="acal469-incomplet">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
          <span>
            Balayage incomplet : certaines cases n’ont pas pu être calculées
            {Array.isArray(resultat.socle_manquant) && resultat.socle_manquant.length
              ? ` (${resultat.socle_manquant.join(', ')})` : ''}.
          </span>
        </div>
      )}

      {grille.length > 0 && (
        <table className="w-full text-sm" data-testid="acal469-grille">
          <thead>
            <tr>
              {colonnes.map((a) => <th key={a.nom} className="text-left">{a.libelle}</th>)}
              <th className="text-right">P50 (kWh)</th>
              <th className="text-right">kWh/kWc</th>
            </tr>
          </thead>
          <tbody>
            {grille.map((l, i) => (
              <tr key={i}>
                {colonnes.map((a) => <td key={a.nom}>{formatNumber(l[a.nom], { decimals: 0 })}</td>)}
                <td className="text-right">{formatNumber(l.p50_kwh, { decimals: 0 })}</td>
                <td
                  className="text-right" data-testid="acal469-case"
                  style={{ background: fondDeCase(l.rendement_specifique_kwh_kwc, bas, haut) }}
                >
                  {formatNumber(l.rendement_specifique_kwh_kwc, { decimals: 1 })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {optimum && (
        <p className="text-sm" data-testid="acal469-optimum">
          Optimum : {colonnes.map((a) => `${a.libelle} ${formatNumber(optimum[a.nom], { decimals: 0 })}`).join(' · ')}
          {' — '}{formatNumber(optimum.rendement_specifique_kwh_kwc, { decimals: 1 })} kWh/kWc
        </p>
      )}
      <OptimumDuMois resultat={resultat} mois={moisLance} onAppliquer={appliquable ? appliquer : null} />
      {appliquable && (
        <Button onClick={() => appliquer()} data-testid="acal469-appliquer">Appliquer l’optimum</Button>
      )}
      {message && <p className="text-sm" role="status" data-testid="acal469-message">{message}</p>}
    </Card>
  )
}
