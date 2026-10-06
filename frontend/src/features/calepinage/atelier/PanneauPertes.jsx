import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'

/* ============================================================================
   CALX18 / ACAL136 — L'ÉDITEUR DES POSTES DE PERTES, AVEC LE STATUT DE CHAQUE
   POSTE.
   ----------------------------------------------------------------------------
   CONSTAT (CALX18). `GET pertes/` et `POST enregistrer-pertes/`
   (`views/simulation.py`, CAL139) sont servis ; le catalogue de postes NOMMÉS
   (`services/pertes.py::CATALOGUE`) vient du GET, ce panneau ne connaît aucun
   nom de poste par avance. Parité PV*SOL — le bilan de pertes se détaille poste
   par poste : https://help.valentin-software.com/pvsol/en/pages/results/energy-balance/.

   ACAL136 — LE STATUT DE CHAQUE POSTE (contrat `calepinage_pertes.json`).
   `postes[]` publie, pour chaque poste saisi, `statut` ∈ applique |
   ecarte_par_etape | remplace_reglage_societe | hors_chaine | non_source |
   non_simule, avec `etape` et `raison` : l'écran DIT ce que la chaîne fait de la
   saisie, au lieu de la laisser croire appliquée. Un poste écarté par une étape
   physique est en lecture seule (« Calculé par l'étape … — votre saisie n'est
   pas appliquée ») ; le bouton « Forcer » l'applique malgré l'étape, mais
   EXIGE un motif écrit (forçage signé, ACAL135).

   ZÉRO POSTE PERDU À L'ENREGISTREMENT. Les lignes sont celles du catalogue
   servi PLUS tout poste servi hors catalogue (« neige »…). Une ligne NON
   TOUCHÉE est renvoyée TELLE QUE SERVIE (poste, libellé, pourcentage, source —
   éventuellement `null` —, référence, mois, forçage) : ouvrir puis enregistrer
   sans toucher laisse `GET pertes/` octet-identique. Seule une ligne ÉDITÉE est
   revalidée : un pourcentage tapé sans source reste REFUSÉ avant tout envoi
   réseau, le champ pointé (règle fondateur du 08/09/2026 : jamais un « non
   enregistré » générique) ; le refus 400 du serveur (qui NOMME son champ)
   atterrit au même endroit.

   LE TOTAL AFFICHÉ est la somme des SEULS postes saisis — jamais complétée
   d'une valeur de référence — et porte la mention exacte exigée : ces postes
   ne sont plus transmis à PVGIS un par un, ils entrent dans la chaîne de pertes
   séquentielle qui les applique un à un.
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

const aDouzeMois = (valeur) => Array.isArray(valeur) && valeur.length === 12

/** Les LIGNES de l'écran : le catalogue servi, puis tout poste servi qui n'y
    figure pas (jamais supprimé par l'écran). `origine` = le poste tel que
    servi, ou `null` (ligne du catalogue jamais saisie). */
function construireLignes(data) {
  const catalogue = Array.isArray(data?.catalogue) ? data.catalogue : []
  const servis = Array.isArray(data?.postes)
    ? data.postes
    : (Array.isArray(data?.pertes) ? data.pertes : [])
  const parPoste = new Map(servis.map((p) => [p.poste, p]))
  const connus = new Set(catalogue.map((c) => c.poste))
  const lignes = catalogue.map((item) => {
    const origine = parPoste.get(item.poste) || null
    return {
      poste: item.poste,
      libelle: item.libelle,
      reference: item.reference || '',
      mensuel: Boolean(item.mensuel) || aDouzeMois(origine?.mensuel),
      horsCatalogue: false,
      origine,
    }
  })
  for (const p of servis) {
    if (connus.has(p.poste)) continue
    lignes.push({
      poste: p.poste,
      libelle: p.libelle || p.poste,
      reference: '',
      mensuel: aDouzeMois(p.mensuel),
      horsCatalogue: true,
      origine: p,
    })
  }
  return lignes
}

/** Le brouillon (chaînes) d'une ligne, depuis le poste servi. */
function brouillonDe(ligne) {
  const o = ligne.origine
  return {
    pct: o && o.pct !== undefined && o.pct !== null ? String(o.pct) : '',
    source: o?.source ?? '',
    reference: o?.reference ?? '',
    mensuel: ligne.mensuel
      ? (aDouzeMois(o?.mensuel) ? o.mensuel.map(String) : Array(12).fill(''))
      : null,
    force: Boolean(o?.force),
    motif_force: o?.motif_force ?? '',
  }
}

const memeBrouillon = (a, b) => a.pct === b.pct && a.source === b.source
  && a.reference === b.reference && a.force === b.force && a.motif_force === b.motif_force
  && JSON.stringify(a.mensuel) === JSON.stringify(b.mensuel)

/** Le poste TEL QUE SERVI, renvoyé inchangé (clés de la forme persistée). */
function posteInchange(origine) {
  const poste = {
    poste: origine.poste,
    libelle: origine.libelle ?? '',
    pct: origine.pct ?? null,
    source: origine.source ?? null,
    reference: origine.reference ?? '',
    mensuel: origine.mensuel ?? null,
  }
  if (origine.force) {
    poste.force = true
    poste.motif_force = origine.motif_force ?? ''
  }
  return poste
}

/**
 * Les postes à envoyer, et les erreurs de saisie (avant tout réseau). Une
 * ligne NON TOUCHÉE repart telle que servie ; une ligne vide jamais saisie est
 * OMISE ; une ligne ÉDITÉE sans source, un mensuel incomplet ou un forçage sans
 * motif sont REFUSÉS — jamais envoyés à moitié remplis.
 */
function construireEnvoi(lignes, saisie, initial) {
  const erreurs = {}
  const aEnvoyer = []
  for (const ligne of lignes) {
    const s = saisie[ligne.poste]
    if (!s) continue
    if (ligne.origine && initial[ligne.poste] && memeBrouillon(s, initial[ligne.poste])) {
      aEnvoyer.push(posteInchange(ligne.origine))
      continue
    }
    const corps = {
      poste: ligne.poste,
      libelle: ligne.libelle,
      source: s.source || null,
      reference: s.reference || '',
    }
    if (ligne.mensuel) {
      const remplis = moisRenseignes(s.mensuel)
      if (remplis.length === 0) continue
      if (remplis.length < 12) {
        erreurs[ligne.poste] = 'Les douze mois doivent être renseignés : '
          + `il en manque ${12 - remplis.length}.`
        continue
      }
      corps.mensuel = s.mensuel.map(Number)
    } else {
      if (s.pct === '' || s.pct === undefined || s.pct === null) continue
      corps.pct = Number(s.pct)
    }
    if (!s.source) {
      erreurs[ligne.poste] = 'Une source est requise pour ce poste : sans '
        + 'elle, la valeur ne peut pas être publiée comme fiable.'
      continue
    }
    if (s.force) {
      if (!(s.motif_force || '').trim()) {
        erreurs[ligne.poste] = 'Un forçage exige un motif : écrivez pourquoi '
          + 'ce poste remplace l’étape calculée, ou retirez le forçage.'
        continue
      }
      corps.force = true
      corps.motif_force = s.motif_force.trim()
    }
    aEnvoyer.push(corps)
  }
  return { erreurs, aEnvoyer }
}

/** Le total des postes SAISIS uniquement — jamais complété par le catalogue. */
function totalSaisi(lignes, saisie) {
  let total = 0
  let compte = 0
  for (const ligne of lignes) {
    const s = saisie[ligne.poste] || {}
    if (ligne.mensuel) {
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

/** « thermique » → « Thermique », « ohmique_dc » → « Ohmique dc ». */
function nomEtape(etape) {
  const texte = String(etape || '').replace(/_/g, ' ').trim()
  return texte ? texte.charAt(0).toUpperCase() + texte.slice(1) : 'de la chaîne'
}

/** La phrase de STATUT d'un poste servi (jamais devinée côté écran). */
function phraseStatut(origine) {
  if (!origine?.statut) return ''
  const raison = origine.raison ? ` ${origine.raison}` : ''
  switch (origine.statut) {
    case 'applique':
      return 'Appliqué dans la chaîne de pertes.'
    case 'ecarte_par_etape':
      return `Calculé par l'étape ${nomEtape(origine.etape)} — votre saisie n'est pas appliquée.`
    case 'remplace_reglage_societe':
      return `Remplace le réglage société (${origine.pct ?? '—'} %).${raison}`
    case 'hors_chaine':
      return `Hors chaîne :${raison || ' n’agit pas sur la production.'}`
    case 'non_source':
      return `Sans source :${raison || ' le poste n’entre pas dans la chaîne.'}`
    case 'non_simule':
      return `Pas encore simulé.${raison}`
    default:
      return `${origine.statut}${raison}`
  }
}

function SelectSource({ poste, saisie, disabled, onChangeSource }) {
  return (
    <label className="block" data-testid={`cal-pertes-source-${poste}`}>
      <span className="tech-label text-lune-faint">Source</span>
      <select
        id={`cal-pertes-source-select-${poste}`}
        value={saisie.source ?? ''}
        disabled={disabled}
        onChange={(e) => onChangeSource(poste, e.target.value)}
        className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
      >
        <option value="">— aucune —</option>
        {SOURCES.map(([cle, label]) => <option key={cle} value={cle}>{label}</option>)}
      </select>
    </label>
  )
}

function LignePourcentage({ poste, saisie, erreur, disabled, onChangePct, onChangeSource }) {
  return (
    <>
      <label className="block" data-testid={`cal-pertes-champ-${poste}`}>
        <span className="tech-label text-lune-faint">Pourcentage (%)</span>
        <input
          type="number"
          step="any"
          id={`cal-pertes-${poste}`}
          value={saisie.pct ?? ''}
          disabled={disabled}
          onChange={(e) => onChangePct(poste, e.target.value)}
          aria-invalid={erreur ? 'true' : undefined}
          aria-describedby={erreur ? `cal-pertes-erreur-${poste}` : undefined}
          className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
        />
      </label>
      <SelectSource poste={poste} saisie={saisie} disabled={disabled} onChangeSource={onChangeSource} />
    </>
  )
}

function LigneMensuelle({ poste, saisie, erreur, disabled, onChangeMois, onChangeSource }) {
  const mois = saisie.mensuel ?? Array(12).fill('')
  return (
    <>
      <div className="sm:col-span-2" data-testid={`cal-pertes-champ-${poste}`}>
        <span className="tech-label text-lune-faint">
          Douze valeurs mensuelles (%)
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
                disabled={disabled}
                onChange={(e) => onChangeMois(poste, i, e.target.value)}
                aria-invalid={erreur ? 'true' : undefined}
                aria-describedby={erreur ? `cal-pertes-erreur-${poste}` : undefined}
                className="mt-1 w-full rounded border border-white/15 bg-black/30 px-1 py-1 text-xs text-white"
              />
            </label>
          ))}
        </div>
      </div>
      <SelectSource poste={poste} saisie={saisie} disabled={disabled} onChangeSource={onChangeSource} />
    </>
  )
}

function LignePoste({
  ligne, saisie, erreur, onChangePct, onChangeSource, onChangeMois, onChangeChamp,
}) {
  const { poste, origine } = ligne
  // Un poste ÉCARTÉ par une étape calculée est en lecture seule tant qu'il
  // n'est pas forcé (ACAL136).
  const ecarte = origine?.statut === 'ecarte_par_etape'
  const lectureSeule = ecarte && !saisie.force
  const statut = phraseStatut(origine)
  return (
    <fieldset className="mt-4 border-t border-white/10 pt-4" data-testid={`cal-pertes-poste-${poste}`}>
      <legend className="tech-label text-lune-faint">
        {ligne.libelle}{ligne.horsCatalogue ? ' (hors catalogue)' : ''}
      </legend>
      {ligne.reference && (
        <p className="text-xs text-lune-soft">{ligne.reference}</p>
      )}
      {statut && (
        <p
          className="mt-1 text-xs text-amber-200"
          data-testid={`acal136-statut-${poste}`}
          data-statut={origine.statut}
        >
          {statut}
        </p>
      )}
      <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {ligne.mensuel
          ? (
            <LigneMensuelle
              poste={poste} saisie={saisie} erreur={erreur} disabled={lectureSeule}
              onChangeMois={onChangeMois} onChangeSource={onChangeSource}
            />
          )
          : (
            <LignePourcentage
              poste={poste} saisie={saisie} erreur={erreur} disabled={lectureSeule}
              onChangePct={onChangePct} onChangeSource={onChangeSource}
            />
          )}
        <label className="block sm:col-span-2" data-testid={`acal136-reference-${poste}`}>
          <span className="tech-label text-lune-faint">Référence</span>
          <input
            type="text"
            value={saisie.reference ?? ''}
            disabled={lectureSeule}
            onChange={(e) => onChangeChamp(poste, 'reference', e.target.value)}
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
          />
        </label>
      </div>
      {ecarte && !saisie.force && (
        <button
          type="button"
          onClick={() => onChangeChamp(poste, 'force', true)}
          data-testid={`acal136-forcer-${poste}`}
          className="mt-2 rounded border border-white/15 px-3 py-1 text-xs font-semibold text-white"
        >
          Forcer
        </button>
      )}
      {saisie.force && (
        <label className="mt-2 block" data-testid={`acal136-motif-${poste}`}>
          <span className="tech-label text-lune-faint">
            Motif du forçage (obligatoire)
          </span>
          <input
            type="text"
            value={saisie.motif_force ?? ''}
            onChange={(e) => onChangeChamp(poste, 'motif_force', e.target.value)}
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
          />
        </label>
      )}
      {erreur && (
        <span
          id={`cal-pertes-erreur-${poste}`}
          data-testid={`cal-pertes-erreur-${poste}`}
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

  const [lignes, setLignes] = useState([])
  const [saisie, setSaisie] = useState({})
  const [initial, setInitial] = useState({})
  // Sans identifiant, il n'y a rien à charger : on ne reste pas bloqué sur
  // l'écran d'attente (l'état initial le dit, jamais une mise à jour
  // synchrone dans l'effet — voir `react-hooks/set-state-in-effect`).
  const [chargement, setChargement] = useState(() => Boolean(calepinageId))
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [motifNonSimulable, setMotifNonSimulable] = useState('')

  const charger = (data) => {
    const construites = construireLignes(data)
    const brouillons = Object.fromEntries(construites.map((l) => [l.poste, brouillonDe(l)]))
    setLignes(construites)
    setSaisie(brouillons)
    setInitial(structuredClone(brouillons))
    setMotifNonSimulable(data?.motif_non_simulable ?? '')
  }

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.pertes(calepinageId))
      .then((res) => {
        if (annule) return
        charger(res?.data ?? {})
      })
      .catch(() => { if (!annule) setLignes([]) })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [calepinageId])

  const changerChamp = (poste, champ, valeur) => setSaisie((s) => (
    { ...s, [poste]: { ...(s[poste] || {}), [champ]: valeur } }
  ))
  const changerPct = (poste, brut) => changerChamp(poste, 'pct', brut)
  const changerSource = (poste, brut) => changerChamp(poste, 'source', brut)
  const changerMois = (poste, rang, brut) => setSaisie((s) => {
    const precedent = s[poste] || {}
    const mois = [...(precedent.mensuel ?? Array(12).fill(''))]
    mois[rang] = brut
    return { ...s, [poste]: { ...precedent, mensuel: mois } }
  })

  const total = totalSaisi(lignes, saisie)

  const enregistrer = () => {
    const { erreurs: erreursSaisie, aEnvoyer } = construireEnvoi(lignes, saisie, initial)
    setErreurs(erreursSaisie)
    setMessage(null)
    if (Object.keys(erreursSaisie).length > 0) return
    if (!calepinageId) return
    setEnCours(true)
    Promise.resolve(calepinageApi.calepinages.enregistrerPertes(calepinageId, { postes: aEnvoyer }))
      .then((res) => {
        setMessage('Postes de pertes enregistrés.')
        const data = res?.data ?? {}
        // Relecture des statuts servis après l'écriture.
        if (Array.isArray(data.postes) || Array.isArray(data.pertes)) {
          charger({ ...data, catalogue: Array.isArray(data.catalogue) ? data.catalogue : lignes
            .filter((l) => !l.horsCatalogue)
            .map((l) => ({ poste: l.poste, libelle: l.libelle, reference: l.reference, mensuel: l.mensuel })) })
        } else {
          setMotifNonSimulable(data.motif_non_simulable ?? '')
        }
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
  const libelleDe = (cle) => lignes.find((l) => l.poste === cle)?.libelle ?? cle

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
                {libelleDe(cle)}
              </a>
            </span>
          ))}
        </p>
      )}

      {lignes.map((ligne) => (
        <LignePoste
          key={ligne.poste}
          ligne={ligne}
          saisie={saisie[ligne.poste] || {}}
          erreur={erreurs[ligne.poste]}
          onChangePct={changerPct}
          onChangeSource={changerSource}
          onChangeMois={changerMois}
          onChangeChamp={changerChamp}
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
