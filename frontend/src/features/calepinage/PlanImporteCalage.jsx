import { useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import useDocumentCalepinage, { MESSAGE_ILLISIBLE } from './useDocumentCalepinage'
import { lireConflit } from './conflitEcriture'
import { refusServeur } from './commun/refusServeur'
import RetourAtelier from './atelier/RetourAtelier'
import { echelleDepuisDeuxPoints, phraseControleEchelle } from './PlanImporteCalage.helpers'

/* ============================================================================
   CAL63 — CALER UN PLAN IMPORTÉ : rotation, ÉCHELLE SAISIE.
   ----------------------------------------------------------------------------
   Constat de la tâche : l'atelier n'a aucune manipulation de plan importé
   (aucun `rotate`/`scale` de calque dans `roofPro11/`). Un plan déposé reste
   donc un dessin muet, dans l'unité DU FICHIER — et `services/import_plan.py`
   (CAL62) le dit noir sur blanc : « un DXF qui ne déclare pas $INSUNITS et un
   PDF (points typographiques) rendent `unite='inconnu'`, et c'est la
   calibration de l'atelier qui donne l'échelle. Une conversion supposée
   produirait un plan faux qui a l'air juste. » Cet écran EST cette calibration.

   L'ÉCHELLE VIENT D'UNE DISTANCE SAISIE, JAMAIS D'UNE ESTIMATION. On ne déduit
   l'échelle ni du cartouche, ni de l'unité déclarée, ni d'une hypothèse de
   format : l'utilisateur DÉSIGNE DEUX POINTS du plan et TAPE la distance
   RÉELLE qui les sépare. Sans cette saisie, `echelleDepuisDeuxPoints` rend
   `null` et l’écran refuse de poser le pan — il n’invente pas un facteur 1.

   LE SERVEUR POSE LE CONTOUR SUR LE TOIT (ACAL70). Le calage (deux sommets de
   référence A et B, la distance RÉELLE saisie, la rotation) part à
   `importer-plan/` avec le fichier : le serveur rend `contour_lnglat`, le
   contour calé en [lng, lat] autour de l'épingle du calepinage (un seul repère
   local, `services/zones.py`). « Poser comme pan du toit » le passe à
   `builderApi.ajouterPanDepuisContour` : un VRAI pan apparaît dans l'atelier,
   à enregistrer avec la conception. Cet écran n'écrit donc plus RIEN dans le
   document : plus de clé `planImporte` (sans lecteur, effacée par l'atelier),
   plus de « Convertir en tracé de toit » (il écrivait des unités de plan dans
   `outline`), plus d'aimantation (elle comparait des unités de plan à des
   degrés) — l'aimantation se fait dans l'atelier, une fois le pan posé.

   D'OÙ VIENT LE CONTOUR (CALX39). L'analyseur de CAL62 a désormais sa porte
   HTTP : `POST calepinages/<pk>/importer-plan/` (contrat
   `apps/calepinage/contract_samples/calepinage_import_plan.json`). Le fichier
   déposé ici est ANALYSÉ par le serveur, qui rend ses calques ; le calque
   choisi rend le contour. Cette porte n'écrit RIEN — ni `roof_layout`, ni
   document. Sans plan analysé, l'écran le DIT au lieu d'afficher un calque
   vide qui aurait l'air cassé.

   LE SERVEUR NE DEVINE AUCUNE ÉCHELLE, ET CET ÉCRAN NON PLUS : la réponse
   porte l'unité DÉCLARÉE par le fichier (ou « inconnu ») et le motif qui dit
   pourquoi l'échelle vient d'ici. Un refus est rendu SOUS le champ fautif
   (`fichier` ou `calque`), avec le bandeau qui le nomme.
   ========================================================================== */

const RAD = Math.PI / 180

/** ACAL1443 — UNE classe de champ pour tout l'écran : celle de l'atelier (bordure, fond de champ, 44 px), jamais le
 *  fond noir translucide du thème sombre qui rendait les champs gris pleins en thème clair. */
const CLASSE_CHAMP = 'mt-1 w-full min-h-11 border border-border bg-muted px-3 py-2 text-base text-foreground outline-none focus:border-brass-400'

/** ACAL1443 — le sélecteur de fichier en français : un bouton relié à l'`input` masqué (qui garde son `data-testid`),
 *  suivi du nom choisi ou de « Aucun fichier choisi » — jamais le « Choose File » natif. */
function SelecteurPlan({ id, testId, accept, ariaLabel, invalide, fichier, onChange }) {
  return (
    <div className="mt-1 flex flex-wrap items-center gap-2">
      <input
        type="file"
        id={id}
        data-testid={testId}
        accept={accept}
        aria-label={ariaLabel}
        aria-invalid={invalide ? 'true' : undefined}
        onChange={onChange}
        className="peer sr-only"
      />
      <label htmlFor={id}
        className="inline-flex min-h-11 cursor-pointer items-center rounded border border-border px-3 text-sm font-medium peer-focus-visible:ring-2">
        Choisir un fichier
      </label>
      <span className="text-sm text-muted-foreground">{fichier ? fichier.name : 'Aucun fichier choisi'}</span>
    </div>
  )
}

/** Une valeur servie, ou le tiret de l'inconnu — jamais un zéro de repli. */
function texte(brut, suffixe = '') {
  if (brut === null || brut === undefined || brut === '') return '—'
  return `${brut}${suffixe}`
}

function ChampNombre({ cle, label, valeur, erreur, onChange }) {
  return (
    <label className="block" data-testid={`cal-calage-champ-${cle}`}>
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      <input
        type="number"
        step="any"
        id={`cal-calage-${cle}`}
        value={valeur ?? ''}
        onChange={(e) => onChange(cle, e.target.value)}
        aria-invalid={erreur ? 'true' : undefined}
        className={CLASSE_CHAMP}
      />
      {erreur && (
        <span role="alert" data-testid={`cal-calage-erreur-${cle}`}
          className="mt-1 block text-xs text-red-300">{erreur}</span>
      )}
    </label>
  )
}

/** ACAL280 — `{champ, message}` d'un refus : le champ NOMMÉ par le serveur
 *  (sinon `fichier`), le motif du décodeur commun, sinon `repli`. */
function refusDuPlan(e, repli) {
  const { message, champs } = refusServeur(e)
  return { champ: Object.keys(champs)[0] ?? 'fichier', message: message || repli }
}

export default function PlanImporteCalage({
  calepinageId: idPropose, builderApi = null, documentVivant = null,
}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [saisie, setSaisie] = useState({
    rotationDeg: '', indexA: '0', indexB: '1', distanceReelleM: '',
  })
  // ACAL73 — le document (jeton d'écriture) ne sert QU'au fond « image de plan » :
  // l'UNIQUE lecture (hook), jamais un document vide sur lequel on écrirait.
  const doc = useDocumentCalepinage(calepinageId)
  const [imageFond, setImageFond] = useState(null)
  const [refusFond, setRefusFond] = useState(null)
  const [messageFond, setMessageFond] = useState(null)
  const [message, setMessage] = useState(null)
  const [refus, setRefus] = useState(null)
  // CALX39 — le plan déposé, l'analyse rendue par le serveur, le calque choisi
  // et le contour qu'il propose. Rien de tout cela n'est persisté par la porte.
  const [fichierDepose, setFichierDepose] = useState(null)
  const [analyse, setAnalyse] = useState(null)
  const [calqueChoisi, setCalqueChoisi] = useState('')
  // ACAL213 — le rang (1, 2, …) de l'entité choisie dans le calque ('' = défaut serveur).
  const [entiteChoisie, setEntiteChoisie] = useState('')
  const [contourImporte, setContourImporte] = useState(null)
  const [controleEchelle, setControleEchelle] = useState(null) // ACAL513
  const [refusImport, setRefusImport] = useState(null)

  const sommets = Array.isArray(contourImporte) ? contourImporte : []

  const pointA = sommets[Number(saisie.indexA)] ?? null
  const pointB = sommets[Number(saisie.indexB)] ?? null
  const mesure = echelleDepuisDeuxPoints(pointA, pointB, saisie.distanceReelleM)

  const majChamp = (cle, brutSaisi) => setSaisie((s) => ({ ...s, [cle]: brutSaisi }))

  /* CALX39 — dépose le plan et lit ce que le SERVEUR en dit. `calque` vide =
     première analyse (la liste des calques) ; `calque` renseigné = le contour
     de ce calque. Le fichier n'est pas conservé côté serveur : il repart avec
     le choix du calque. Un refus atterrit SOUS son champ. */
  const envoyerPlan = (calque, entite = '') => {
    if (!fichierDepose) {
      setRefusImport({
        champ: 'fichier',
        message: 'Déposez un plan (DXF ou PDF vectoriel) avant de lancer l’analyse.',
      })
      return
    }
    const corps = new FormData()
    corps.append('fichier', fichierDepose)
    if (calque) corps.append('calque', calque)
    if (calque && entite) corps.append('entite', String(entite))
    setRefusImport(null)
    Promise.resolve(calepinageApi.calepinages.importerPlan(calepinageId, corps))
      .then((res) => {
        const donnees = res?.data ?? null
        setAnalyse(donnees)
        if (donnees?.contour) setContourImporte(donnees.contour)
        setMessage(donnees?.message ?? null)
      })
      .catch((e) => {
        // Le motif vient du SERVEUR, et il NOMME son champ (`fichier` ou
        // `calque`) : on ne réécrit ni l'un ni l'autre (ACAL280 : décodeur commun).
        setRefusImport(refusDuPlan(e, 'Le plan n’a pas pu être analysé.'))
      })
  }

  /* ACAL70 — « Poser comme pan du toit » : le calage part au SERVEUR avec le
     fichier (`importer-plan/`), qui rend le contour en [lng, lat] autour de
     l'épingle ; l'atelier le pose comme un vrai pan (refusé, motif nommé, s'il
     se croise ou sort de l'amplitude GPS). Aucun POST du document : le pan est
     à enregistrer avec la conception. */
  const poserCommePan = () => {
    if (!builderApi?.ajouterPanDepuisContour) {
      setRefusImport({
        champ: 'atelier',
        message: 'Ouvrez cet onglet depuis l’atelier : le pan se pose dans la scène vivante.',
      })
      return
    }
    if (!fichierDepose) {
      setRefusImport({
        champ: 'fichier',
        message: 'Déposez un plan (DXF ou PDF vectoriel) avant de le poser.',
      })
      return
    }
    if (!mesure) {
      setRefus('distanceReelleM')
      return
    }
    setRefus(null)
    setRefusImport(null)
    setMessage(null)
    setControleEchelle(null)
    const corps = new FormData()
    corps.append('fichier', fichierDepose)
    corps.append('calque', calqueChoisi)
    if (entiteChoisie) corps.append('entite', String(entiteChoisie))
    corps.append('calage', JSON.stringify({
      pointA, pointB,
      distanceM: Number(saisie.distanceReelleM),
      rotationDeg: Number(saisie.rotationDeg) || 0,
    }))
    Promise.resolve(calepinageApi.calepinages.importerPlan(calepinageId, corps))
      .then((res) => {
        setControleEchelle(res?.data?.controle_echelle ?? null)
        const contourGeo = res?.data?.contour_lnglat
        if (!Array.isArray(contourGeo) || !contourGeo.length) {
          setRefusImport({
            champ: 'contour',
            message: 'Le serveur n’a rendu aucun contour calé : le pan n’est pas posé.',
          })
          return
        }
        const verdict = builderApi.ajouterPanDepuisContour(contourGeo)
        if (verdict?.ok) {
          setMessage('Pan posé dans l’atelier : enregistrez le calepinage pour le conserver.')
        } else {
          setRefusImport({
            champ: 'contour',
            message: verdict?.motif || 'Le contour n’a pas pu être posé comme pan.',
          })
        }
      })
      .catch((e) => {
        setRefusImport(refusDuPlan(e, 'Le plan n’a pas pu être calé.'))
      })
  }

  /* ACAL73 — « Poser comme fond de l'atelier » : une IMAGE de plan (PNG/JPEG) est
     rangée par le serveur (`fond-plan/`, ACAL72) qui écrit `underlay` par section ;
     la réponse est poussée dans l'atelier vivant, qui l'affiche et la cale par
     l'outil deux points existant. Un DXF/PDF ne passe pas ici : il passe par
     l'analyse et « Poser comme pan du toit ». */
  const poserCommeFond = async () => {
    setMessageFond(null)
    if (!imageFond) {
      setRefusFond('Choisissez une image de plan (PNG ou JPEG) avant de la poser en fond.')
      return
    }
    const base = documentVivant?.empreinte || doc.empreinte
    if (doc.etat !== 'ok' || !base) {
      setRefusFond(MESSAGE_ILLISIBLE)
      return
    }
    setRefusFond(null)
    const corps = new FormData()
    corps.append('fichier', imageFond)
    corps.append('base_empreinte', base)
    try {
      const res = await calepinageApi.calepinages.envoyerFondPlan(calepinageId, corps)
      const fond = res?.data?.underlay ?? null
      const empreinte = res?.data?.empreinte_document ?? null
      doc.appliquerSection('underlay', fond, empreinte)
      documentVivant?.appliquerSection?.('underlay', fond, empreinte)
      setMessageFond('Image posée comme fond de l’atelier : calez-la avec l’outil deux points, '
        + 'puis enregistrez le calepinage.')
    } catch (e) {
      // ACAL280 — jeton périmé (relire) ≠ verrou (SON motif) ; sinon le motif serveur.
      const conflit = lireConflit(e)
      if (conflit?.documentModifie) {
        setRefusFond('La conception a changé ailleurs : elle est relue, recommencez.')
        doc.recharger()
        return
      }
      setRefusFond(conflit?.motif
        || refusDuPlan(e, 'L’image n’a pas pu être posée en fond.').message)
    }
  }

  const blocFond = (
    <div className="mt-4" role="group" aria-label="Image de plan en fond de l’atelier">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Poser une image de plan (PNG ou JPEG) en fond de l’atelier
      </p>
      <SelecteurPlan
        id="cal-calage-fond-fichier"
        accept="image/png,image/jpeg"
        ariaLabel="Image de plan (PNG ou JPEG)"
        fichier={imageFond}
        onChange={(e) => {
          setImageFond(e.target.files?.[0] ?? null)
          setRefusFond(null)
        }}
      />
      <button type="button" onClick={poserCommeFond}
        className="mt-2 rounded border border-border px-3 py-1 text-sm text-foreground">
        Poser comme fond de l’atelier
      </button>
      {refusFond && (
        <span role="alert" className="mt-1 block text-xs text-red-300">{refusFond}</span>
      )}
      {messageFond && (
        <p className="mt-2 text-sm text-foreground" role="status">{messageFond}</p>
      )}
    </div>
  )

  const entitesDuCalque = (analyse?.calques ?? [])
    .find((calque) => calque.nom === calqueChoisi)?.entites_detail ?? []

  const blocDepot = (
    <div className="mt-4" data-testid="cal-calage-import">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Déposer un plan (DXF ou PDF vectoriel)
      </p>
      <SelecteurPlan
        id="cal-calage-fichier"
        testId="cal-calage-fichier"
        accept=".dxf,.pdf"
        invalide={refusImport?.champ === 'fichier'}
        fichier={fichierDepose}
        onChange={(e) => {
          setFichierDepose(e.target.files?.[0] ?? null)
          setRefusImport(null)
        }}
      />
      <button type="button" onClick={() => envoyerPlan('')}
        data-testid="cal-calage-analyser"
        className="mt-2 rounded border border-border px-3 py-1 text-sm text-foreground">
        Analyser le plan
      </button>
      {refusImport?.champ === 'fichier' && (
        <span role="alert" data-testid="cal-calage-erreur-fichier"
          className="mt-1 block text-xs text-red-300">{refusImport.message}</span>
      )}

      {analyse && (
        <div className="mt-3" data-testid="cal-calage-analyse">
          <p className="text-xs text-foreground" data-testid="cal-calage-unite">
            Format : {texte(analyse.format)} — unité déclarée par le fichier :{' '}
            {texte(analyse.unite)}
          </p>
          <p className="text-xs text-muted-foreground" data-testid="cal-calage-motif-echelle">
            {analyse.motif_echelle}
          </p>
          <label className="mt-2 block" data-testid="cal-calage-champ-calque">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Calque d’enveloppe</span>
            <select
              data-testid="cal-calage-calque"
              value={calqueChoisi}
              aria-invalid={refusImport?.champ === 'calque' ? 'true' : undefined}
              onChange={(e) => { setCalqueChoisi(e.target.value); setEntiteChoisie('') }}
              className={CLASSE_CHAMP}
            >
              <option value="">— choisir un calque —</option>
              {(analyse.calques ?? []).map((calque) => (
                <option key={calque.nom} value={calque.nom}>
                  {calque.nom} — {calque.entites} tracé(s), {calque.sommets} sommet(s)
                </option>
              ))}
            </select>
          </label>
          {entitesDuCalque.length > 0 && (
            <fieldset className="mt-2" data-testid="cal-calage-entites">
              <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Entité du calque (le serveur propose la plus grande aire fermée)
              </legend>
              {entitesDuCalque.map((entite) => (
                <label key={entite.rang} className="mt-1 flex items-center gap-2 text-xs text-foreground">
                  <input
                    type="radio"
                    name="cal-calage-entite"
                    data-testid={`cal-calage-entite-${entite.rang}`}
                    checked={String(entiteChoisie) === String(entite.rang)}
                    onChange={() => setEntiteChoisie(String(entite.rang))}
                  />
                  {`Entité ${entite.rang} — ${entite.sommets} sommet(s), `
                    + `aire ${Number(entite.aire).toFixed(2)} (${texte(analyse.unite)}²), `
                    + `emprise ${Number(entite.emprise?.largeur).toFixed(2)} × `
                    + `${Number(entite.emprise?.hauteur).toFixed(2)}`
                    + (entite.fermee ? '' : ' — tracé non fermé')}
                </label>
              ))}
            </fieldset>
          )}
          <button type="button" onClick={() => envoyerPlan(calqueChoisi, entiteChoisie)}
            data-testid="cal-calage-proposer"
            className="mt-2 rounded bg-brass-500/20 px-3 py-1 text-sm font-semibold text-primary-text">
            Proposer ce contour
          </button>
          {refusImport?.champ === 'calque' && (
            <span role="alert" data-testid="cal-calage-erreur-calque"
              className="mt-1 block text-xs text-red-300">{refusImport.message}</span>
          )}
        </div>
      )}

      {refusImport && (
        <p role="alert" data-testid="cal-calage-bandeau-import"
          className="mt-2 text-xs text-red-300">
          Le champ « {refusImport.champ} » doit être corrigé : {refusImport.message}
        </p>
      )}
    </div>
  )

  if (!sommets.length) {
    return (
      <>
        <RetourAtelier calepinageId={calepinageId} />
        <div className="rounded-xl border border-border bg-card mt-6 p-6" data-testid="cal-calage-plan">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Plan importé</p>
          <p className="mt-2 text-sm text-foreground" data-testid="cal-calage-sans-plan">
            Aucun plan importé n’est rattaché à ce calepinage : il n’y a donc rien
            à caler. Déposez un plan (DXF ou PDF vectoriel) ci-dessous : le serveur
            l’analyse et propose le contour du calque choisi, sans rien enregistrer.
          </p>
          {blocDepot}
          {blocFond}
        </div>
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="rounded-xl border border-border bg-card mt-6 p-6" data-testid="cal-calage-plan">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">
          Caler le plan importé
        </p>

      {blocDepot}
      {blocFond}

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <ChampNombre cle="rotationDeg" label="Rotation (°)"
          valeur={saisie.rotationDeg} onChange={majChamp} />
      </div>

      <fieldset className="mt-4" data-testid="cal-calage-echelle">
        <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          L’échelle — deux points de référence et la distance RÉELLE entre eux
        </legend>
        <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <ChampNombre cle="indexA" label="Sommet de référence A"
            valeur={saisie.indexA} onChange={majChamp} />
          <ChampNombre cle="indexB" label="Sommet de référence B"
            valeur={saisie.indexB} onChange={majChamp} />
          <ChampNombre
            cle="distanceReelleM"
            label="Distance réelle A→B (m)"
            valeur={saisie.distanceReelleM}
            erreur={refus === 'distanceReelleM'
              ? 'Mesurez la distance réelle entre les deux points de référence : '
                + 'sans elle, l’échelle serait une estimation, et le plan calé serait faux.'
              : null}
            onChange={majChamp}
          />
        </div>
        <p className="mt-2 text-sm text-foreground" data-testid="cal-calage-facteur">
          Échelle :{' '}
          {mesure
            ? `${mesure.echelle} m par unité de plan (source : ${mesure.source})`
            : 'non calculée — aucune échelle n’est estimée à votre place'}
        </p>
        {phraseControleEchelle(controleEchelle) && (
          <p className="mt-1 text-sm text-foreground" role="status" data-testid="cal-calage-controle">
            {phraseControleEchelle(controleEchelle)}
          </p>
        )}
      </fieldset>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        <div data-testid="cal-calage-sommets">
          <dd className="fig text-lg text-foreground">{sommets.length}</dd>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sommets du plan</dt>
        </div>
        <div data-testid="cal-calage-source">
          <dd className="text-sm text-foreground">{texte(mesure?.source)}</dd>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Source de l’échelle</dt>
        </div>
        <div data-testid="cal-calage-distance-plan">
          <dd className="fig text-lg text-foreground">{texte(mesure?.distancePlan)}</dd>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Distance A→B sur le plan</dt>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={poserCommePan}
          className="rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-primary-text">
          Poser comme pan du toit
        </button>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Le contour calé devient un vrai pan de l’atelier (posé autour de l’épingle) :
        enregistrez ensuite le calepinage pour le conserver.
      </p>

      {message && (
        <p className="mt-3 text-sm text-foreground" role="status"
          data-testid="cal-calage-message">{message}</p>
      )}
    </div>
    </>
  )
}
