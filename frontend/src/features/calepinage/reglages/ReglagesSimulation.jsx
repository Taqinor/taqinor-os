import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Badge, Button, Card, Spinner } from '../../../ui'
import ReglagesSite from './ReglagesSite'

/* ============================================================================
   CALX69 / ACAL133 — LES RÉGLAGES DE SIMULATION ET D'ÉLECTRIQUE, AVEC
   PROVENANCE OBLIGATOIRE, TYPÉS PAR LE REGISTRE SERVI.
   ----------------------------------------------------------------------------
   `GET /api/django/calepinage/parametres/` publie la clé DÉRIVÉE `registre`
   — `{simulation: [{cle, libelle, unite, reference, type, valeurs?, minimum?,
   maximum?}, …], electrique_societe: [...]}`, lue de
   `services/parametres_cles.py` (contrat `parametres_calepinage.json`).
   ACAL133 : ce registre est la SEULE source des lignes. L'ancienne copie
   locale (`REGISTRE_SIMULATION`/`REGISTRE_ELECTRIQUE_SOCIETE`) et son repli
   sont SUPPRIMÉS : sans registre servi, l'écran dit qu'il est indisponible
   plutôt que d'afficher des lignes qui ne sont plus celles du serveur. Le
   type de chaque clé commande son champ (liste fermée pour un enum, oui/non
   pour un booléen, saisie libre sinon — jamais de bornes HTML qui feraient
   « sauter » ce que l'on tape : le serveur normalise « 2,5 » et refuse en
   nommant la clé).

   LA DISCIPLINE DE SAISIE, IDENTIQUE À CELLE DU SERVEUR
   (`services/parametres.py::_normaliser_section_a_registre`) :
     * une clé JAMAIS entamée (valeur, source ET référence toutes vides) est
       OMISE de l'envoi — rien n'est inventé ;
     * une clé STOCKÉE puis vidée part à `null` (le PUT fusionne par clé) ;
     * une clé ENTAMÉE sans valeur, ou sans provenance choisie, est REFUSÉE
       avant tout envoi réseau — l'erreur se pose SOUS la clé fautive et le
       bandeau la NOMME ;
     * le refus 400 du serveur (nommé DANS sa section) atterrit au même endroit ;
     * UN SEUL PUT `{simulation, electrique_societe}` : jamais d'écriture
       partielle entre les deux sections ;
     * une ligne NON TOUCHÉE est renvoyée avec sa valeur d'origine telle que
       servie (aller-retour sans geste = sections identiques côté serveur).
   Les valeurs CITÉES des logiciels concurrents (la référence doctrinale du
   registre) restent un simple REPÈRE sous chaque ligne — jamais copiées dans
   « valeur ».
   ========================================================================== */

//: `services/parametres_cles.py::SOURCES_ADMISES` — les QUATRE provenances
//: admises par le serveur ; toute autre chaîne est refusée en la nommant.
const SOURCES = [
  ['societe', 'Réglage société'],
  ['mesure', 'Mesure'],
  ['saisie', 'Saisie'],
  ['texte', 'Texte cité'],
]

const TITRES = { simulation: 'Simulation', electrique_societe: 'Électrique — société' }

const LIGNE_VIDE = { valeurTexte: '', source: '', reference: '' }

/** Le libellé français d'une clé, cherché dans le registre SERVI. */
function libelleDe(cle, registres) {
  for (const registre of Object.values(registres)) {
    const trouve = registre.find((r) => r.cle === cle)
    if (trouve) return trouve.libelle
  }
  return cle
}

/** `registre.<section>` servi par le GET — une LISTE d'objets — normalisée.
 *  Rend `null` si la clé est absente ou mal formée : l'écran dit alors que le
 *  registre est indisponible, jamais un registre à moitié reconstruit. */
function registreDepuisServeur(liste) {
  if (!Array.isArray(liste) || liste.length === 0) return null
  const lignes = []
  for (const ligne of liste) {
    if (!ligne || typeof ligne !== 'object' || typeof ligne.cle !== 'string') return null
    lignes.push({
      cle: ligne.cle,
      libelle: typeof ligne.libelle === 'string' ? ligne.libelle : ligne.cle,
      unite: typeof ligne.unite === 'string' ? ligne.unite : '',
      reference: typeof ligne.reference === 'string' ? ligne.reference : '',
      type: typeof ligne.type === 'string' ? ligne.type : '',
      valeurs: Array.isArray(ligne.valeurs) ? ligne.valeurs.map(String) : null,
      minimum: typeof ligne.minimum === 'number' ? ligne.minimum : null,
      maximum: typeof ligne.maximum === 'number' ? ligne.maximum : null,
    })
  }
  return lignes
}

/** Le texte affiché dans le champ « valeur », depuis ce que le serveur sert. */
function texteDeValeur(valeur) {
  if (valeur === undefined || valeur === null) return ''
  if (typeof valeur === 'string') return valeur
  return JSON.stringify(valeur)
}

/** La valeur ENVOYÉE, depuis le texte tapé — nombre, table (JSON) ou texte
 *  brut selon ce que l'utilisateur a tapé ; « 2,5 » part tel quel (texte) et
 *  c'est le serveur qui normalise. */
function valeurDepuisTexte(texte) {
  try {
    return JSON.parse(texte)
  } catch {
    return texte
  }
}

/** Les brouillons `{clé: {valeurTexte, source, reference}}` d'une section,
 *  une entrée par clé du REGISTRE — une clé non saisie reste VIDE, jamais
 *  complétée d'une valeur par défaut. */
function lignesDepuis(registre, section) {
  const servi = section && typeof section === 'object' ? section : {}
  const lignes = {}
  for (const { cle } of registre) {
    const existant = servi[cle]
    if (existant && typeof existant === 'object') {
      const texte = texteDeValeur(existant.valeur)
      lignes[cle] = {
        valeurTexte: texte,
        source: typeof existant.source === 'string' ? existant.source : '',
        reference: typeof existant.reference === 'string' ? existant.reference : '',
        stockee: true,
        valeurOrigine: existant.valeur,
        texteOrigine: texte,
      }
    } else {
      lignes[cle] = { ...LIGNE_VIDE }
    }
  }
  return lignes
}

/** La section ENVOYABLE au serveur + les erreurs de saisie, AVANT tout envoi
 *  réseau. Une clé jamais entamée est OMISE ; une clé entamée sans valeur ou
 *  sans source est REFUSÉE, jamais envoyée à moitié remplie. */
function validerSection(registre, lignes) {
  const section = {}
  const erreurs = {}
  for (const { cle, libelle } of registre) {
    const ligne = lignes[cle] || LIGNE_VIDE
    const valeurTexte = (ligne.valeurTexte || '').trim()
    const source = (ligne.source || '').trim()
    const reference = (ligne.reference || '').trim()
    // ACAL132 — le PUT FUSIONNE clé par clé : une clé STOCKÉE puis vidée à
    // l'écran est envoyée à `null` pour être RETIRÉE (l'omettre la garderait
    // stockée) ; une clé jamais saisie reste omise.
    if (!valeurTexte && !source && !reference) {
      if (ligne.stockee) section[cle] = null
      continue
    }
    if (!valeurTexte) {
      erreurs[cle] = `« ${libelle} » doit porter une valeur : une clé `
        + 'entamée sans valeur ne règle rien. Videz aussi sa source pour '
        + 'revenir au comportement d’aujourd’hui.'
      continue
    }
    if (!source) {
      erreurs[cle] = `« ${libelle} » doit porter sa provenance « source » : `
        + 'aucune valeur n’est admise sans elle. Provenances admises : '
        + 'societe, mesure, saisie, texte.'
      continue
    }
    // Ligne NON TOUCHÉE : la valeur d'origine telle que servie (un texte
    // « 60 » ne devient pas le nombre 60 par un aller-retour sans geste).
    const intacte = ligne.stockee && valeurTexte === (ligne.texteOrigine || '').trim()
    section[cle] = {
      valeur: intacte ? ligne.valeurOrigine : valeurDepuisTexte(valeurTexte),
      source,
      reference,
    }
  }
  return { section, erreurs }
}

const CLASSE_CHAMP = 'mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground'

/** L'aide de TYPE d'une clé, depuis le registre servi (type, bornes). */
function aideDeType(r) {
  const bornes = r.minimum !== null && r.maximum !== null
    ? ` entre ${r.minimum} et ${r.maximum}`
    : (r.minimum !== null ? ` au moins ${r.minimum}` : (r.maximum !== null ? ` au plus ${r.maximum}` : ''))
  switch (r.type) {
    case 'pourcentage': return `Pourcentage${bornes}`
    case 'nombre': return `Nombre${bornes}`
    case 'entier': return `Nombre entier${bornes}`
    case 'enum': return 'Une valeur de la liste'
    case 'booleen': return 'Oui ou non'
    case 'table_mensuelle': return `Douze valeurs mensuelles (liste), ou une seule pour les douze${bornes}`
    case 'intervalle_annees': return 'Intervalle d’années [début, fin]'
    case 'table': return 'Table structurée (JSON)'
    default: return ''
  }
}

function ChampValeur({ r, ligne, disabled, erreur, onChange }) {
  const commun = {
    id: `calx69-${r.cle}`,
    value: ligne.valeurTexte,
    disabled,
    'aria-invalid': erreur ? 'true' : undefined,
    'aria-describedby': erreur ? `calx69-erreur-${r.cle}` : undefined,
    onChange: (e) => onChange('valeurTexte', e.target.value),
    className: CLASSE_CHAMP,
  }
  if (r.type === 'enum' && r.valeurs) {
    const options = r.valeurs.includes(ligne.valeurTexte) || !ligne.valeurTexte
      ? r.valeurs : [ligne.valeurTexte, ...r.valeurs]
    return (
      <select {...commun}>
        <option value="">— aucune —</option>
        {options.map((v) => <option key={v} value={v}>{v}</option>)}
      </select>
    )
  }
  if (r.type === 'booleen') {
    return (
      <select {...commun}>
        <option value="">— aucune —</option>
        <option value="true">Oui</option>
        <option value="false">Non</option>
      </select>
    )
  }
  return <input type="text" inputMode="text" {...commun} />
}

function LigneReglage({ r, ligne, erreur, disabled, onChange }) {
  const majer = (champ, valeur) => onChange(r.cle, champ, valeur)
  const aide = aideDeType(r)
  return (
    <fieldset className="mt-4 border-t border-border/60 pt-4" data-testid={`calx69-ligne-${r.cle}`}>
      <legend className="text-sm font-semibold text-foreground">
        {r.libelle}{r.unite ? ` (${r.unite})` : ''}
      </legend>
      {r.reference && (
        <p className="text-xs text-muted-foreground" data-testid={`calx69-aide-${r.cle}`}>
          {r.reference}
        </p>
      )}
      {aide && (
        <p className="text-xs text-muted-foreground" data-testid={`acal133-type-${r.cle}`}>
          {aide}
        </p>
      )}
      <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="block" data-testid={`calx69-valeur-${r.cle}`}>
          <span className="text-xs text-muted-foreground">Valeur</span>
          <ChampValeur r={r} ligne={ligne} disabled={disabled} erreur={erreur} onChange={majer} />
        </label>
        <label className="block" data-testid={`calx69-source-${r.cle}`}>
          <span className="text-xs text-muted-foreground">Source</span>
          <select
            value={ligne.source}
            disabled={disabled}
            onChange={(e) => majer('source', e.target.value)}
            className={CLASSE_CHAMP}
          >
            <option value="">— aucune —</option>
            {SOURCES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
        <label className="block" data-testid={`calx69-reference-${r.cle}`}>
          <span className="text-xs text-muted-foreground">Référence (facultatif)</span>
          <input
            type="text"
            value={ligne.reference}
            disabled={disabled}
            onChange={(e) => majer('reference', e.target.value)}
            className={CLASSE_CHAMP}
          />
        </label>
      </div>
      {erreur && (
        <p
          id={`calx69-erreur-${r.cle}`}
          data-testid={`calx69-erreur-${r.cle}`}
          role="alert"
          className="mt-2 text-xs text-destructive"
        >
          {erreur}
        </p>
      )}
    </fieldset>
  )
}

/** « N simulations relancées » — l'accord du pluriel est celui du serveur
 *  (`soumis`), jamais un chiffre recalculé ici. */
function phraseRecalcul(rendu) {
  const n = Number.isFinite(rendu?.soumis) ? rendu.soumis : 0
  const base = n === 1 ? '1 simulation relancée' : `${n} simulations relancées`
  const reste = Number.isFinite(rendu?.reste) ? rendu.reste : 0
  return reste > 0
    ? `${base} — il en reste ${reste} : relancez « Tout recalculer » pour la suite.`
    : `${base}.`
}

export default function ReglagesSimulation() {
  const peutGerer = useHasPermission('calepinage_gerer')

  const [lignesParSection, setLignesParSection] = useState({
    simulation: {}, electrique_societe: {},
  })
  // Le registre ACTIF : UNIQUEMENT celui servi par le GET (ACAL133).
  const [registres, setRegistres] = useState(null)
  // ACAL130 — la section « imagerie » servie, pour « Site & imagerie ».
  const [imagerie, setImagerie] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [erreurChargement, setErreurChargement] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [enregistrement, setEnregistrement] = useState(false)
  const [recalcul, setRecalcul] = useState(false)

  useEffect(() => {
    let annule = false
    Promise.resolve(calepinageApi.parametres.get())
      .then((res) => {
        if (annule) return
        const data = res?.data ?? {}
        const servi = data.registre && typeof data.registre === 'object' ? data.registre : {}
        const simulation = registreDepuisServeur(servi.simulation)
        const electrique = registreDepuisServeur(servi.electrique_societe)
        if (!simulation || !electrique) {
          setErreurChargement(
            'Registre des réglages indisponible : le serveur n’a pas servi la liste '
            + 'des réglages, la page ne peut pas afficher de lignes.',
          )
          return
        }
        setRegistres({ simulation, electrique_societe: electrique })
        setImagerie(data.imagerie && typeof data.imagerie === 'object' ? data.imagerie : null)
        setLignesParSection({
          simulation: lignesDepuis(simulation, data.simulation),
          electrique_societe: lignesDepuis(electrique, data.electrique_societe),
        })
      })
      .catch(() => {
        if (!annule) {
          setErreurChargement('Réglages indisponibles : la page n’a pas pu être chargée.')
        }
      })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [])

  const changer = (section) => (cle, champ, valeur) => setLignesParSection((courant) => ({
    ...courant,
    [section]: {
      ...courant[section],
      [cle]: { ...(courant[section][cle] || LIGNE_VIDE), [champ]: valeur },
    },
  }))

  const enregistrer = async () => {
    const simulation = validerSection(registres.simulation, lignesParSection.simulation)
    const electrique = validerSection(
      registres.electrique_societe, lignesParSection.electrique_societe,
    )
    const toutesErreurs = { ...simulation.erreurs, ...electrique.erreurs }
    setMessage(null)
    if (Object.keys(toutesErreurs).length > 0) {
      setErreurs(toutesErreurs)
      return
    }
    setErreurs({})
    setEnregistrement(true)
    try {
      // UN SEUL PUT pour les deux sections (ACAL133) : le serveur l'écrit
      // dans une seule transaction, jamais une moitié.
      const res = await calepinageApi.parametres.update({
        simulation: simulation.section,
        electrique_societe: electrique.section,
      })
      const data = res?.data ?? {}
      setLignesParSection({
        simulation: lignesDepuis(registres.simulation, data.simulation),
        electrique_societe: lignesDepuis(registres.electrique_societe, data.electrique_societe),
      })
      setMessage('Réglages enregistrés.')
    } catch (e) {
      const corps = e?.response?.data
      if (corps && typeof corps === 'object') {
        const mappees = {}
        for (const [champ, valeur] of Object.entries(corps)) {
          // ACAL132 — une clé d'une section à registre est nommée DANS sa
          // section : `{simulation: {sigma_modele_pct: motif}}`.
          if (valeur && typeof valeur === 'object' && !Array.isArray(valeur)) {
            for (const [cle, motif] of Object.entries(valeur)) {
              mappees[cle] = Array.isArray(motif) ? motif.join(' ') : String(motif)
            }
            continue
          }
          mappees[champ] = Array.isArray(valeur) ? valeur.join(' ') : String(valeur)
        }
        setErreurs(mappees)
      } else {
        setErreurs({ _general: 'Le serveur n’a rendu aucun motif : rien n’a été enregistré.' })
      }
    } finally {
      setEnregistrement(false)
    }
  }

  const toutRecalculer = async () => {
    setMessage(null)
    setRecalcul(true)
    try {
      const res = await calepinageApi.parametres.recalculerSimulations()
      setMessage(phraseRecalcul(res?.data))
    } catch (e) {
      const detail = e?.response?.data?.detail
      setErreurs({
        _general: typeof detail === 'string' && detail
          ? detail : 'Le recalcul n’a pas pu être lancé : aucune simulation relancée.',
      })
    } finally {
      setRecalcul(false)
    }
  }

  if (chargement) {
    return <div className="page" data-testid="calx69-ecran"><Spinner /></div>
  }
  if (erreurChargement) {
    return (
      <div className="page" data-testid="calx69-ecran">
        <p role="alert" className="text-sm text-destructive" data-testid="calx69-erreur-chargement">
          {erreurChargement}
        </p>
      </div>
    )
  }

  const champsFautifs = Object.keys(erreurs).filter((cle) => cle !== '_general')

  return (
    <div className="page" data-testid="calx69-ecran">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-lg font-semibold text-foreground">
          Réglages de simulation et d’électrique
        </h1>
        {!peutGerer && (
          <Badge variant="outline" data-testid="calx69-lecture-seule">Lecture seule</Badge>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Chaque valeur saisie porte sa provenance : sans elle, elle n’est pas
        enregistrée. Une clé non saisie reste omise — chaque étape de
        simulation ou contrôle électrique qui en dépend l’affiche comme telle,
        jamais un forfait. Les repères sous chaque ligne sont ceux publiés par
        les logiciels du marché, cités à titre d’aide : ils ne sont jamais
        recopiés dans la valeur.
      </p>
      <p className="mt-1 text-sm text-muted-foreground" data-testid="acal133-priorite">
        Un poste saisi sur un calepinage prime sur ce réglage société.
      </p>

      {champsFautifs.length > 0 && (
        <p
          role="alert"
          data-testid="calx69-bandeau"
          className="mt-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          Réglages incomplets — à corriger :{' '}
          {champsFautifs.map((cle, i) => (
            <span key={cle}>
              {i > 0 && ', '}
              <a href={`#calx69-${cle}`} className="underline">{libelleDe(cle, registres)}</a>
            </span>
          ))}
        </p>
      )}

      <ReglagesSite imagerie={imagerie} />

      {Object.keys(registres).map((section) => (
        <Card key={section} className="mt-5 p-4" data-testid={`calx69-section-${section}`}>
          <h2 className="text-base font-semibold text-foreground">{TITRES[section] || section}</h2>
          {registres[section].map((r) => (
            <LigneReglage
              key={r.cle}
              r={r}
              ligne={lignesParSection[section][r.cle] || LIGNE_VIDE}
              erreur={erreurs[r.cle]}
              disabled={!peutGerer || enregistrement}
              onChange={changer(section)}
            />
          ))}
        </Card>
      ))}

      {peutGerer ? (
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button
            type="button"
            disabled={enregistrement}
            data-testid="calx69-enregistrer"
            className="text-sm font-semibold underline"
            onClick={enregistrer}
          >
            {enregistrement ? 'Enregistrement…' : 'Enregistrer les réglages'}
          </button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={recalcul || enregistrement}
            data-testid="acal133-tout-recalculer"
            onClick={toutRecalculer}
          >
            {recalcul ? 'Recalcul en cours…' : 'Tout recalculer'}
          </Button>
        </div>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">
          Sans le droit « gérer le calepinage », la saisie n’est pas proposée
          ici.
        </p>
      )}

      {erreurs._general && (
        <p role="alert" className="mt-2 text-xs text-destructive" data-testid="calx69-erreur-generale">
          {erreurs._general}
        </p>
      )}
      {message && (
        <p role="status" className="mt-3 text-sm text-muted-foreground" data-testid="calx69-message">
          {message}
        </p>
      )}
    </div>
  )
}
