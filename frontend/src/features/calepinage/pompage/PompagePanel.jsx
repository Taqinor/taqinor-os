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
  /* AGR125 — les composantes de la HMT « comme au devis » (core/pompage
     `hmt_composantes`). AUCUN défaut : pertes singulières et pression de
     service restent vides tant qu'elles ne sont pas saisies ; le serveur
     nomme ce qui manque et retombe sur la HMT saisie. */
  ['hmt_composantes', 'La HMT calculée comme au devis', [
    ['niveau_dynamique_m', 'Niveau dynamique mesuré (m)'],
    ['denivele_m', 'Dénivelé (m)'],
    ['diametre_interieur_mm', 'Diamètre intérieur de la conduite (mm)'],
    ['materiau_conduite', 'Matériau de la conduite (PVC, PEHD…)', 'text'],
    ['c_hazen_williams', 'Coefficient de Hazen-Williams (C)'],
    ['pertes_singulieres_m', 'Pertes singulières (m)'],
    ['pression_service_bar', 'Pression de service (bar)'],
  ]],
  /* ACAL807 — le niveau d'eau saisonnier et la pose (ACAL806, ACAL1113,
     ACAL1114) ; les mois de niveau bas sont des pastilles sous ce groupe. */
  ['niveau_eau', 'Le niveau d’eau', [
    ['niveau_statique_ete_m', 'Profondeur de l’eau au repos en été (m)'],
    ['niveau_statique_hiver_m', 'Profondeur de l’eau au repos en hiver (m)'],
    ['profondeur_calage_m', 'Profondeur de pose de la pompe (m)'],
    ['diametre_tubage_mm', 'Diamètre du tubage (mm)'],
    ['debit_exploitation_m3h', 'Débit que donne le forage (m³/h)'],
  ]],
  ['besoin', 'Le besoin', [
    ['debit_souhaite_m3h', 'Débit souhaité (m³/h)'],
    ['besoin_m3_jour', 'Besoin en eau (m³/jour)'],
    ['heures_pompage', 'Heures de pompage par jour'],
    ['heures_demande_h', 'Heures par jour où l’on tire l’eau'],  // ACAL815
  ]],
  ['reservoir', 'Le réservoir', [
    ['volume_reservoir_m3', 'Volume du réservoir (m³)'],
  ]],
  /* ACAL811 — la chaîne du champ solaire, jugée par le serveur (ACAL810). */
  ['champ_solaire', 'Le champ solaire', [
    ['modules_en_serie', 'Modules en série'],
    ['chaines_paralleles', 'Chaînes en parallèle'],
  ]],
]

/* Clé technique → libellé humain, dérivé de CHAMPS : le bandeau nomme le champ
   comme l'écran l'affiche, pas comme le serveur le code. */
const LIBELLE_CHAMP = Object.fromEntries(
  CHAMPS.flatMap(([, , champs]) => champs),
)

/* ACAL807 — une phrase simple par code d'alerte du serveur (ACAL1113,
   ACAL1114), posée sous le champ que l'alerte nomme ; le texte du serveur suit. */
const PHRASE_ALERTE = {
  immersion_minimale: 'La pompe risque de tourner à sec',
  diametre_tubage: 'La pompe ne passe pas dans le tubage',
  plafond_forage: 'Le forage ne donne pas assez d\'eau pour ce besoin',
}

function Champ({ cle, label, type = 'number', valeurSaisie, erreur, alertes = [], onChange }) {
  return (
    <label className="block" data-testid={`cal-pompage-champ-${cle}`}>
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      <input
        type={type}
        /* Règle fondateur : l'écran ne SNAPPE ni ne REFUSE jamais une saisie. */
        step="any"
        name={cle}
        id={`cal-pompage-${cle}`}
        value={valeurSaisie ?? ''}
        onChange={(e) => onChange(cle, e.target.value)}
        aria-invalid={erreur ? 'true' : undefined}
        aria-describedby={erreur ? `cal-pompage-erreur-${cle}` : undefined}
        className="mt-1 min-h-[44px] w-full rounded border border-border bg-background px-2 py-1 text-sm text-foreground"
      />
      {alertes.map((a) => (
        <span key={a.code} data-testid={`cal-pompage-alerte-${a.code}`} role="alert"
          className="mt-1 block text-xs text-amber-200">
          {PHRASE_ALERTE[a.code] ? `${PHRASE_ALERTE[a.code]}. ` : ''}{a.message}
        </span>
      ))}
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
      <p className="mt-2 text-sm text-foreground" data-testid="cal-pompage-courbe-absente">
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
        className="text-primary-text" strokeWidth="2" />
      {tracable && (
        <circle
          cx={x(point.debit_m3h)} cy={y(point.hmt_m)} r="5"
          className="fill-foreground" data-testid="cal-pompage-point"
        />
      )}
      <text x="30" y={H - 6} className="fill-current text-muted-foreground" fontSize="10">
        Débit (m³/h)
      </text>
      <text x="4" y="12" className="fill-current text-muted-foreground" fontSize="10">
        HMT (m)
      </text>
    </svg>
  )
}

/** Les 12 volumes mensuels — ou la phrase qui dit pourquoi il n'y en a pas. */
function VolumesMensuels({ volumes, besoin }) {
  if (!volumes) {
    return (
      <p className="mt-2 text-sm text-foreground" data-testid="cal-pompage-volumes-absents">
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
        <tr className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <th className="text-left">Mois</th>
          <th className="text-right">m³ (plat)</th>
          <th className="text-right">m³ (PVGIS)</th>
          <th className="text-right">Couverture</th>
        </tr>
      </thead>
      <tbody>
        {MOIS.map((mois, i) => (
          <tr key={mois} data-testid={`cal-pompage-mois-${i}`}>
            <td className="text-left text-foreground">{mois}</td>
            <td className="fig text-right text-foreground">{valeur(plat?.[i])}</td>
            <td className="fig text-right text-foreground">{valeur(pvgis?.[i])}</td>
            <td className="fig text-right text-foreground">
              {couverture?.[i] == null ? '—' : `${couverture[i]} %`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/* ACAL807 — les 12 pastilles des mois où le niveau d'eau est bas (été). */
function MoisNiveauBas({ choisis = [], onChange }) {
  const basculer = (m) => onChange('mois_niveau_bas', choisis.includes(m)
    ? choisis.filter((x) => x !== m) : [...choisis, m].sort((a, b) => a - b))
  return (
    <div className="mt-3" role="group" aria-label="Mois où le niveau d’eau est bas">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Mois où le niveau d’eau est bas
      </span>
      <div className="mt-1 flex flex-wrap gap-2">
        {MOIS.map((nom, i) => (
          <button key={nom} type="button" data-testid={`cal-pompage-mois-bas-${i + 1}`}
            aria-pressed={choisis.includes(i + 1) ? 'true' : 'false'} onClick={() => basculer(i + 1)}
            className={`min-h-[44px] min-w-[44px] rounded border border-border px-2 text-xs ${
              choisis.includes(i + 1) ? 'bg-brass-500/20 text-primary-text' : 'text-foreground'}`}>
            {nom}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ACAL807 — la carte « Réservoir jour par jour » (bilan servi par ACAL806),
   ou la phrase qui dit pourquoi elle est absente. Aucun chiffre recalculé. */
function BilanReservoir({ bilan }) {
  if (!bilan?.calcule) {
    return (
      <p className="mt-2 text-sm text-foreground" data-testid="cal-pompage-bilan-motif">
        {`Bilan du réservoir non calculé : ${bilan?.motif ?? 'le serveur n’a rendu aucun bilan'}`}
      </p>
    )
  }
  const parMois = bilan.jours_manque_mois ?? []
  return (
    <div className="mt-2 rounded border border-border p-3 text-sm text-foreground" data-testid="cal-pompage-bilan">
      <p>{`Jours où l'eau manque : ${valeur(bilan.jours_manque)} sur 365`}</p>
      <p>{`Jours où le réservoir est plein (la pompe s'arrête) : ${valeur(bilan.jours_plein)}`}</p>
      <p>{`Besoin couvert : ${valeur(bilan.besoin_couvert_pct, ' %')}`}</p>
      <div className="mt-2 flex h-16 items-end gap-1" aria-label="Jours où l’eau manque, mois par mois">
        {MOIS.map((nom, i) => (
          <div key={nom} className="flex flex-1 flex-col items-center" data-mois-manque={parMois[i] ?? ''}
            title={`${nom} : ${valeur(parMois[i])} jour(s) de manque`}>
            <div className="w-full rounded-t bg-red-400/70" style={{ height: `${((parMois[i] ?? 0) / 31) * 48}px` }} />
            <span className="text-xs text-muted-foreground">{nom}</span>
          </div>
        ))}
      </div>
      {bilan.mention && <p className="mt-2 text-xs text-muted-foreground">{bilan.mention}</p>}
    </div>
  )
}

/* ACAL815 — deux cartes côte à côte (une sous l'autre sur téléphone) :
   `comparaison_reservoir` servi tel quel ; carte absente ⇒ le motif du serveur. */
const OPTIONS_COMPARAISON = [['direct', 'Pompage direct'], ['avec_reservoir', 'Avec le réservoir']]
const uneDecimale = (x) => (x == null ? '—' : Number(x).toFixed(1).replace('.', ','))

function ComparaisonReservoir({ comparaison }) {
  if (!comparaison) return null
  return (
    <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="cal-pompage-comparaison">
      {OPTIONS_COMPARAISON.map(([cle, titre]) => {
        const option = comparaison[cle]
        return (
          <div key={cle} data-option={cle} className="rounded border border-border p-3 text-sm text-foreground">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{titre}</p>
            {option ? (
              <p className="mt-1">
                {`Débit de conception : ${uneDecimale(option.debit_conception_m3h)} m³/h · Mois critique : `}
                {`${MOIS[option.mois_critique - 1] ?? '—'} · Jours où l'eau manque : ${valeur(option.jours_manque)}`}
                {option.motif_bilan && <span className="block text-xs">{option.motif_bilan}</span>}
              </p>
            ) : (
              <p className="mt-1">
                {`Non calculé : ${comparaison.motif ?? 'motif non servi'}`}
                {cle === 'direct' && comparaison.motif?.includes('fenêtre de demande') && (
                  <> — à remplir : <a href="#cal-pompage-heures_demande_h" className="underline">
                    {LIBELLE_CHAMP.heures_demande_h}</a></>
                )}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ACAL821 — plusieurs pompes sur le variateur retenu : kW de PLAQUE saisis,
   mode de marche choisi ; le serveur juge (`controle_pompes_par_variateur`). */
const MODES_POMPES = [['ensemble', 'Ensemble'], ['a_tour_de_role', 'À tour de rôle']]
const BOUTON = 'min-h-[44px] rounded border border-border px-3 text-sm'

function PompesParVariateur({ pompes = [], mode, onChange }) {
  const maj = (liste) => onChange('pompes_variateur', liste)
  return (
    <fieldset className="mt-4">
      <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Plusieurs pompes sur ce variateur
      </legend>
      {pompes.map((p, i) => (
        <div key={i /* lignes sans identifiant : l'ordre de saisie fait la clé */} className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
          {[['nom', `Nom de la pompe ${i + 1}`, 'text'], ['kw', `kW de plaque de la pompe ${i + 1}`, 'number']]
            .map(([cle, libelle, type]) => (
              <input key={cle} type={type} step="any" aria-label={libelle} placeholder={libelle}
                value={p[cle] ?? ''} className="min-h-[44px] rounded border border-border bg-background px-2 text-sm"
                onChange={(e) => maj(pompes.map((x, j) => (j === i ? { ...x, [cle]: e.target.value } : x)))} />
            ))}
          <button type="button" className={BOUTON} onClick={() => maj(pompes.filter((_, j) => j !== i))}>
            Retirer
          </button>
        </div>
      ))}
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" className={BOUTON} onClick={() => maj([...pompes, {}])}>Ajouter une pompe</button>
        {MODES_POMPES.map(([cle, libelle]) => (
          <button key={cle} type="button" aria-pressed={mode === cle ? 'true' : 'false'}
            className={`${BOUTON} ${mode === cle ? 'bg-brass-500/20 text-primary-text' : ''}`}
            onClick={() => onChange('mode_pompes', cle)}>{libelle}</button>
        ))}
      </div>
    </fieldset>
  )
}

function LignePompes({ bloc }) {
  if (!bloc) return null
  const demande = `${uneDecimale(bloc.kw_demande)} kW demandés sur ${uneDecimale(bloc.kw_variateur)} kW`
  const [texte, couleur] = {
    conforme: [`${demande} : conforme (marge ${uneDecimale(bloc.marge_kw)} kW)`, 'text-emerald-300'],
    depasse: [`${demande} : le variateur est trop petit`, 'text-red-300'],
  }[bloc.verdict] ?? ['À vérifier : kW de plaque ou mode non saisi', 'text-amber-200']
  return (
    <div className={`mt-2 text-sm ${couleur}`} data-testid="cal-pompage-pompes">
      <p>{texte}</p>
      {bloc.motif && <p className="text-xs">{bloc.motif}</p>}
    </div>
  )
}

/* ACAL811 — le verdict de la chaîne servi (`chaines_variateur`) : icône ET
   mot, jamais un vert par défaut ; le motif chiffré du serveur suit. */
const ETAT_CHAINE = {
  conforme: ['✔ Conforme', 'text-emerald-300'],
  hors_fenetre: ['✖ Hors fenêtre', 'text-red-300'],
}

function phraseChaine(motif) {
  if (motif?.startsWith('trop longue')) {
    return 'Trop de modules en série : la tension à froid dépasse ce que le variateur accepte'
  }
  if (motif?.startsWith('trop courte')) {
    return 'Pas assez de modules en série : le variateur ne démarre pas par temps chaud'
  }
  return null
}

function VerdictChaines({ chaines }) {
  if (!chaines) return null
  const [etat, couleur] = ETAT_CHAINE[chaines.verdict] ?? ['⚠ À vérifier', 'text-amber-200']
  const t = chaines.temperatures ?? {}
  const fenetre = chaines.fenetre
  return (
    <div className={`mt-2 text-sm ${couleur}`} data-testid="cal-pompage-chaines">
      <p>
        {`${valeur(chaines.serie)} modules en série : Voc à froid ${valeur(chaines.voc_froid_v, ' V')}, `}
        {fenetre ? `le variateur accepte ${fenetre.longueur_min} à ${fenetre.longueur_max} modules`
          : 'fenêtre du variateur inconnue'}
        {` : ${etat}`}
      </p>
      {phraseChaine(chaines.motif) && <p>{phraseChaine(chaines.motif)}</p>}
      {chaines.motif && <p className="text-xs">{chaines.motif}</p>}
      <p className="text-xs text-muted-foreground">
        {`Températures du site : ${valeur(t.froid_c, ' °C')} à froid, ${valeur(t.chaud_c, ' °C')} à chaud — `}
        {t.source ? `source : ${t.source}` : (t.mention ?? 'source non servie')}
      </p>
      {(chaines.alertes ?? []).map((a) => <p key={a.code} className="text-xs">{a.message}</p>)}
    </div>
  )
}

/* ACAL820 — appoint réseau ou groupe : le choix (vide = « Pas d'appoint »,
   jamais envoyé) et la ligne du verdict servi (`appoint_variateur`). */
const APPOINTS = [['', 'Pas d’appoint'], ['reseau', 'Réseau'], ['groupe', 'Groupe']]
const ETAT_APPOINT = {
  conforme: ['Conforme', 'text-emerald-300'],
  vmp_sous_bus: ['Le champ ne passe pas au-dessus du bus : l’appoint fait tout le travail', 'text-red-300'],
  voc_au_dessus_limite: ['Tension trop haute à froid', 'text-red-300'],
}

function ChoixAppoint({ choisi = '', onChange }) {
  return (
    <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Appoint">
      {APPOINTS.map(([cle, libelle]) => (
        <button key={cle || 'aucun'} type="button" aria-pressed={choisi === cle ? 'true' : 'false'}
          className={`${BOUTON} ${choisi === cle ? 'bg-brass-500/20 text-primary-text' : ''}`}
          onClick={() => onChange('appoint', cle)}>{libelle}</button>
      ))}
    </div>
  )
}

function VerdictAppoint({ bloc }) {
  if (!bloc) return null
  const bus = bloc.motif?.includes('var_bus_dc_redresse_v')
  const [texte, couleur] = ETAT_APPOINT[bloc.verdict] ?? [bus
    ? 'À vérifier : tension redressée du bus non publiée sur la fiche du variateur'
    : `À vérifier : ${bloc.motif ?? 'donnée manquante'}`, 'text-amber-200']
  return (
    <div className={`mt-2 text-sm ${couleur}`} data-testid="cal-pompage-appoint">
      <p>Appoint : le variateur est alimenté par le réseau ou un groupe en plus des panneaux</p>
      <p>{texte}</p>
      {bloc.motif && bloc.verdict !== 'non_verifiable' && <p className="text-xs">{bloc.motif}</p>}
    </div>
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
    // Un champ vide n'est JAMAIS envoyé : l'absence reste une absence.
    // ACAL821 — une pompe ne garde que ses valeurs saisies ; une ligne vide disparaît.
    const pompes = (saisie.pompes_variateur ?? []).map((p) => Object.fromEntries(
      Object.entries(p).filter(([, v]) => v !== '' && v != null))).filter((p) => Object.keys(p).length)
    const corps = Object.fromEntries(
      Object.entries({ ...saisie, pompes_variateur: pompes }).filter(([, v]) => v !== '' && v != null
        && !(Array.isArray(v) && v.length === 0)),
    )
    Promise.resolve(calepinageApi.calepinages.pompage(calepinageId, corps))
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
  const chaines = resultat?.chaines_variateur ?? null
  // ACAL811 — `non_verifiable` nomme le champ à saisir : le motif se pose SOUS lui.
  const alertes = [...(resultat?.alertes ?? []), ...(chaines?.champ ? [{
    code: 'chaine_a_saisir', champ: chaines.champ,
    message: `À saisir pour vérifier la chaîne : ${chaines.motif ?? chaines.champ}`,
  }] : [])]

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="rounded-xl border border-border bg-card mt-6 p-6" data-testid="cal-pompage-panel">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Pompage solaire</p>

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
            <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{titre}</legend>
            <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
              {champs.map(([cle, label, type]) => (
                <Champ
                  key={cle}
                  cle={cle}
                  label={label}
                  type={type}
                  valeurSaisie={saisie[cle]}
                  erreur={erreurs[cle]}
                  alertes={alertes.filter((a) => a.champ === cle)}
                  onChange={majChamp}
                />
              ))}
            </div>
            {groupe === 'niveau_eau' && (
              <MoisNiveauBas choisis={saisie.mois_niveau_bas} onChange={majChamp} />
            )}
            {groupe === 'champ_solaire' && (
              <>
                <p className="mt-2 text-sm text-foreground">{`Modules posés : ${valeur(chaines?.modules_poses)}`}</p>
                <ChoixAppoint choisi={saisie.appoint} onChange={majChamp} />
                <VerdictAppoint bloc={resultat?.appoint_variateur} />
              </>
            )}
          </fieldset>
        ))}
        <PompesParVariateur pompes={saisie.pompes_variateur} mode={saisie.mode_pompes} onChange={majChamp} />
        <button
          type="submit"
          disabled={enCours}
          data-testid="cal-pompage-calculer"
          className="mt-4 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-primary-text"
        >
          {enCours ? 'Calcul en cours…' : 'Calculer le dimensionnement'}
        </button>
      </form>

      {resultat && (
        <div className="mt-6 border-t border-border pt-5">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
            <div data-testid="cal-pompage-hmt">
              <dd className="fig text-lg text-foreground">
                {valeur(resultat.hmt?.hmt_m, ' m')}
              </dd>
              <dt className="text-xs font-semibold uppercase tracking-wide mt-0.5 text-muted-foreground">
                HMT — {valeur(resultat.hmt?.source)}
              </dt>
            </div>
            <div data-testid="cal-pompage-debit">
              <dd className="fig text-lg text-foreground">
                {valeur(pompe?.debit_hmt_m3h, ' m³/h')}
              </dd>
              <dt className="text-xs font-semibold uppercase tracking-wide mt-0.5 text-muted-foreground">Débit à cette HMT</dt>
            </div>
            <div data-testid="cal-pompage-pompe">
              <dd className="text-sm text-foreground">{valeur(pompe?.nom)}</dd>
              <dt className="text-xs font-semibold uppercase tracking-wide mt-0.5 text-muted-foreground">
                Pompe retenue{pompe?.pompe_kw != null ? ` · ${pompe.pompe_kw} kW` : ''}
              </dt>
            </div>
            <div data-testid="cal-pompage-variateur">
              <dd className="text-sm text-foreground">{valeur(variateur?.nom)}</dd>
              <dt className="text-xs font-semibold uppercase tracking-wide mt-0.5 text-muted-foreground">Variateur assorti</dt>
            </div>
            <div data-testid="cal-pompage-autonomie">
              <dd className="fig text-lg text-foreground">
                {valeur(resultat.besoin?.autonomie_jours, ' j')}
              </dd>
              <dt className="text-xs font-semibold uppercase tracking-wide mt-0.5 text-muted-foreground">
                Autonomie du réservoir
              </dt>
            </div>
            <div data-testid="cal-pompage-irradiation">
              <dd className="text-sm text-foreground">
                {valeur(resultat.volumes?.source_irradiation)}
              </dd>
              <dt className="text-xs font-semibold uppercase tracking-wide mt-0.5 text-muted-foreground">Source d’irradiation</dt>
            </div>
          </dl>

          <h3 className="text-xs font-semibold uppercase tracking-wide mt-5 text-muted-foreground">Courbe de la pompe</h3>
          <CourbePompe pompe={pompe} />

          <h3 className="text-xs font-semibold uppercase tracking-wide mt-5 text-muted-foreground">Volumes mensuels</h3>
          <VolumesMensuels volumes={resultat.volumes} besoin={resultat.besoin} />

          <h3 className="text-xs font-semibold uppercase tracking-wide mt-5 text-muted-foreground">
            Réservoir jour par jour
          </h3>
          <BilanReservoir bilan={resultat.bilan_reservoir} />
          <ComparaisonReservoir comparaison={resultat.comparaison_reservoir} />

          <h3 className="text-xs font-semibold uppercase tracking-wide mt-5 text-muted-foreground">
            Modules en série et variateur
          </h3>
          <VerdictChaines chaines={chaines} />
          <LignePompes bloc={resultat.pompes_variateur} />

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
