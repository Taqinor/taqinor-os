/* eslint-disable react-refresh/only-export-components --
   `chargeParPointDeFixation` et `provenanceEntree` sont des fonctions PURES
   (aucun état, aucun React) que le test unitaire de la tâche doit pouvoir
   appeler sans monter le panneau. Les sortir dans un `.js` voisin séparerait
   la règle de son unique lecteur ; même dérogation que `PlanImporteCalage.jsx`
   et `module.config.jsx` du même module. */
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber } from '../../../lib/format'
import { Card, Spinner } from '../../../ui'

/* ============================================================================
   CALX17 — LE PANNEAU « MASSE & LESTAGE » DE L'ATELIER.
   ----------------------------------------------------------------------------
   LE TROU QU'IL BOUCHE. `services/lestage.py` compose la masse posée (par pan
   et par m² de pan) et la feuille de lestage depuis le poids de FICHE et les
   saisies de la société — et n'avait, jusqu'à CALX17, AUCUN appelant hors de
   ses tests : un calcul construit, testé, invisible. Ce panneau est son
   lecteur, par la porte `GET calepinages/<pk>/masse-lestage/`.

   AUCUN CALCUL NORMATIF CÔTÉ ÉCRAN. Les sept lignes de la feuille, leurs
   valeurs, leurs formules, leurs entrées et les champs manquants sont RECOPIÉS
   tels que servis (contrat `apps/calepinage/contract_samples/
   calepinage_masse_lestage.json`, que le test jumeau lit). Le seul calcul fait
   ici est la division `effort ÷ points de fixation`, et il n'a lieu QUE si le
   serveur sert les deux nombres.

   ZÉRO CHIFFRE INVENTÉ (décision D-CALX 7), DANS LES DEUX SENS :
   * un paramètre non saisi ⇒ la ligne est OMISE et le panneau NOMME le champ
     manquant, avec la mention du serveur — jamais une valeur par défaut ;
   * sans poids de fiche produit, AUCUNE masse n'est affichée : le bloc porte à
     la place le champ fautif et le message du serveur ;
   * la charge par point de fixation n'est publiée que si le nombre de points
     par module est SAISI ; il ne l'est nulle part aujourd'hui, donc la ligne
     est omise en nommant ce champ — l'inventer reviendrait à publier une
     charge de fixation fausse sur une toiture réelle.
   ========================================================================== */

/** La clé du paramètre société qui porterait le nombre de points de fixation.
    Elle n'est servie par AUCUN réglage à ce jour : c'est précisément ce que la
    ligne correspondante dit, en la nommant. */
export const CLE_POINTS_FIXATION = 'points_fixation_par_module'

/** Le code de la ligne de feuille dont la charge par point est déduite. */
const CODE_EFFORT = 'effort_soulevement_module'

/** Les entrées qui viennent du CALEPINAGE (jamais des réglages société) :
    libellé français et provenance, telles que `services/lestage.py` les lit
    (fiche produit, CAL164). Aucun chiffre ici — seulement d'où il vient. */
const ENTREES_DU_CALEPINAGE = {
  surface_module_m2: {
    libelle: 'Surface d’un module posé',
    provenance: 'fiche produit (cotes de pose)',
  },
  masse_module_kg: {
    libelle: 'Masse d’un module posé',
    provenance: 'fiche produit (poids)',
  },
  masse_resistante_kg: {
    libelle: 'Masse résistante (module + structure)',
    provenance: 'fiche produit (poids) + masse de structure saisie',
  },
}

/**
 * CALX17 — la PROVENANCE d'une entrée de ligne : la source SAISIE quand le
 * serveur la publie, la fiche produit quand l'entrée vient du calepinage, et
 * « non saisi » sinon. Jamais une provenance devinée.
 */
export function provenanceEntree(cle, parametres) {
  const saisi = (Array.isArray(parametres) ? parametres : [])
    .find((parametre) => parametre?.cle === cle)
  if (saisi) {
    return {
      libelle: saisi.libelle || cle,
      valeur: saisi.valeur,
      unite: saisi.unite || '',
      provenance: saisi.source,
    }
  }
  const connue = ENTREES_DU_CALEPINAGE[cle]
  if (connue) {
    return { libelle: connue.libelle, valeur: null, unite: '', provenance: connue.provenance }
  }
  return { libelle: cle, valeur: null, unite: '', provenance: null }
}

/**
 * CALX17 — la CHARGE PAR POINT DE FIXATION : l'effort de soulèvement d'un
 * module divisé par le nombre de points qui le tiennent.
 *
 * Elle n'est publiée que si les DEUX nombres sont servis. Le nombre de points
 * par module n'appartient à aucun réglage servi aujourd'hui : la ligne est
 * donc omise, en NOMMANT le champ attendu (`points_fixation_par_module`).
 * Une valeur par défaut (« 4 points, comme d'habitude ») produirait une charge
 * de fixation fausse sur une toiture réelle.
 */
export function chargeParPointDeFixation(donnees) {
  const lestage = donnees?.lestage ?? {}
  const parametres = Array.isArray(lestage.parametres) ? lestage.parametres : []
  const lignes = Array.isArray(lestage.lignes) ? lestage.lignes : []

  const points = parametres.find((parametre) => parametre?.cle === CLE_POINTS_FIXATION)
  const nombreDePoints = Number(points?.valeur)
  const effort = lignes.find((ligne) => ligne?.code === CODE_EFFORT)
  const effortValeur = effort?.valeur

  const manquants = []
  if (!points || !Number.isFinite(nombreDePoints) || nombreDePoints <= 0) {
    manquants.push(CLE_POINTS_FIXATION)
  }
  if (effortValeur === null || effortValeur === undefined) manquants.push(CODE_EFFORT)

  const commun = {
    libelle: 'Charge par point de fixation',
    unite: 'N',
    formule: 'F_point = F_soulèvement ÷ n_points',
    entrees: [CODE_EFFORT, CLE_POINTS_FIXATION],
  }
  if (manquants.length) {
    const noms = manquants.includes(CLE_POINTS_FIXATION)
      ? `« ${CLE_POINTS_FIXATION} » (nombre de points de fixation par module, non servi par les réglages de lestage)`
      : `« ${CODE_EFFORT} » (l’effort de soulèvement n’est pas calculé)`
    return {
      ...commun,
      valeur: null,
      manquants,
      mention: `Charge par point de fixation non publiée — champ manquant : ${noms}.`,
    }
  }
  return {
    ...commun,
    valeur: Number(effortValeur) / nombreDePoints,
    manquants: [],
    mention: '',
    provenance: points.source,
  }
}

/** Une mesure servie, mise en forme ; `null` reste « non publiée ». */
function mesure(valeur, unite, decimals = 2) {
  if (valeur === null || valeur === undefined) return 'non publiée'
  if (typeof valeur !== 'number') return `${valeur}${unite ? ` ${unite}` : ''}`
  return `${formatNumber(valeur, { decimals })}${unite ? ` ${unite}` : ''}`
}

function BlocMasse({ masse }) {
  const pans = Array.isArray(masse?.pans) ? masse.pans : []
  const poids = masse?.poids_unitaire ?? {}
  const manquants = Array.isArray(masse?.manquants) ? masse.manquants : []
  const sansPoids = poids.module_kg === null || poids.module_kg === undefined

  return (
    <Card className="p-4" data-testid="calx17-masse">
      <h3 className="text-sm font-semibold">Masse installée</h3>
      {sansPoids ? (
        <p className="mt-2 text-sm text-muted-foreground" data-testid="calx17-masse-absente">
          Aucune masse n’est affichée : le poids unitaire du module n’est pas
          publié par sa fiche produit.
        </p>
      ) : (
        <>
          <p className="mt-2 text-sm" data-testid="calx17-masse-totale">
            Masse totale posée : {mesure(masse.masse_totale_kg, 'kg')} pour
            {' '}{masse.total_modules} module(s).
          </p>
          <p className="text-xs text-muted-foreground" data-testid="calx17-poids-unitaire">
            Poids unitaire : {mesure(poids.module_kg, 'kg')} — provenance :
            {' '}{poids.module_source || 'non servie'} ({poids.module_designation || 'module non désigné'})
            {poids.structure_kg_par_module === null || poids.structure_kg_par_module === undefined
              ? ' ; structure non comptée (masse de structure non saisie)'
              : ` ; structure ${mesure(poids.structure_kg_par_module, 'kg')} par module — provenance : ${poids.structure_source || 'non servie'}`}
          </p>
          <table className="mt-3 w-full text-left text-sm" data-testid="calx17-masse-pans">
            <thead>
              <tr className="text-xs uppercase text-muted-foreground">
                <th scope="col" className="py-1">Pan</th>
                <th scope="col" className="py-1">Modules</th>
                <th scope="col" className="py-1">Surface du pan</th>
                <th scope="col" className="py-1">Masse</th>
                <th scope="col" className="py-1">Masse par m²</th>
              </tr>
            </thead>
            <tbody>
              {pans.map((pan) => (
                <tr key={pan.pan} data-testid={`calx17-pan-${pan.pan}`}>
                  <th scope="row" className="py-1 font-normal">{pan.pan}</th>
                  <td className="py-1">{pan.modules}</td>
                  <td className="py-1">{mesure(pan.surface_pan_m2, 'm²')}</td>
                  <td className="py-1">{mesure(pan.masse_kg, 'kg')}</td>
                  <td className="py-1">
                    {mesure(pan.masse_par_m2_kg, 'kg/m²')}
                    {pan.mention ? (
                      <span className="block text-xs text-muted-foreground">{pan.mention}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {manquants.length > 0 && (
        <ul className="mt-3 space-y-1" data-testid="calx17-masse-manquants">
          {manquants.map((manquant) => (
            <li key={manquant.quoi} className="text-xs text-destructive"
              data-testid={`calx17-manquant-${manquant.quoi}`}
            >
              <strong>{manquant.libelle}</strong> — {manquant.message}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function LigneFeuille({ ligne, parametres }) {
  const entrees = Array.isArray(ligne.entrees) ? ligne.entrees : []
  const manquants = Array.isArray(ligne.manquants) ? ligne.manquants : []
  const omise = ligne.valeur === null || ligne.valeur === undefined
  return (
    <li className="border-t border-border py-2" data-testid={`calx17-ligne-${ligne.code}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm font-medium">{ligne.libelle}</span>
        <span className="text-sm" data-testid={`calx17-valeur-${ligne.code}`}>
          {omise ? 'ligne omise' : mesure(ligne.valeur, ligne.unite)}
        </span>
      </div>
      <p className="text-xs text-muted-foreground" data-testid={`calx17-formule-${ligne.code}`}>
        {ligne.formule}
      </p>
      <ul className="mt-1 space-y-0.5" data-testid={`calx17-entrees-${ligne.code}`}>
        {entrees.map((cle) => {
          const entree = provenanceEntree(cle, parametres)
          const absente = manquants.includes(cle)
          return (
            <li key={cle} className="text-xs text-muted-foreground"
              data-testid={`calx17-entree-${ligne.code}-${cle}`}
            >
              {entree.libelle}
              {entree.valeur === null || entree.valeur === undefined
                ? '' : ` : ${entree.valeur}${entree.unite ? ` ${entree.unite}` : ''}`}
              {' — provenance : '}
              {absente || !entree.provenance ? 'non saisie' : entree.provenance}
            </li>
          )
        })}
      </ul>
      {omise && (
        <p className="mt-1 text-xs text-destructive" data-testid={`calx17-manque-${ligne.code}`}>
          {ligne.mention || `Champs manquants : ${manquants.join(', ')}.`}
        </p>
      )}
    </li>
  )
}

function BlocFixation({ charge }) {
  return (
    <Card className="p-4" data-testid="calx17-fixation">
      <h3 className="text-sm font-semibold">{charge.libelle}</h3>
      <p className="mt-1 text-sm" data-testid="calx17-fixation-valeur">
        {charge.valeur === null ? 'ligne omise' : mesure(charge.valeur, charge.unite)}
      </p>
      <p className="text-xs text-muted-foreground" data-testid="calx17-fixation-formule">
        {charge.formule}
      </p>
      {charge.mention ? (
        <p className="mt-1 text-xs text-destructive" data-testid="calx17-fixation-manque">
          {charge.mention}
        </p>
      ) : null}
    </Card>
  )
}

export default function PanneauMasseLestage({ calepinageId: idPropose = null }) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl ?? null

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.masseLestage(calepinageId),
    calepinageId,
    {
      select: (reponse) => reponse?.data ?? null,
      enabled: Boolean(calepinageId),
      errorMessage: 'La masse et la feuille de lestage n’ont pas pu être chargées.',
    },
  )

  if (loading) return <Spinner />
  if (error) {
    return (
      <p className="text-sm text-destructive" role="alert" data-testid="calx17-erreur">{error}</p>
    )
  }
  if (!data) return null

  const lestage = data.lestage ?? {}
  const lignes = Array.isArray(lestage.lignes) ? lestage.lignes : []
  const parametres = Array.isArray(lestage.parametres) ? lestage.parametres : []

  return (
    <div className="space-y-4" data-testid="calx17-panneau">
      <BlocMasse masse={data.masse ?? {}} />
      <BlocFixation charge={chargeParPointDeFixation(data)} />
      <Card className="p-4" data-testid="calx17-feuille">
        <h3 className="text-sm font-semibold">Feuille de lestage</h3>
        <p className="mt-1 text-xs text-muted-foreground" data-testid="calx17-mention">
          {lestage.mention}
        </p>
        <ul className="mt-2">
          {lignes.map((ligne) => (
            <LigneFeuille key={ligne.code} ligne={ligne} parametres={parametres} />
          ))}
        </ul>
      </Card>
    </div>
  )
}
