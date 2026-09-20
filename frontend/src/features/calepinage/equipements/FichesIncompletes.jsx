/* eslint-disable react-refresh/only-export-components --
   `impactChamp` est une fonction PURE (un champ → la phrase du calcul qu'il
   débloque) : elle est exportée pour que le test jumeau puisse PARCOURIR les
   `champs_manquants` du contrat committé et exiger une phrase pour chacun. La
   sortir dans un `.js` voisin séparerait la table de son unique lecteur pour
   satisfaire une règle de fast-refresh qui ne s'applique pas à une constante ;
   même dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import {
  CHAMPS_REQUIS_PAR_TYPE,
} from '../../../pages/stock/ficheCompletude'

/* ============================================================================
   CAL121 — LE PANNEAU « FICHES INCOMPLÈTES » DU CALEPINAGE.
   ----------------------------------------------------------------------------
   LE TROU QU'IL BOUCHE. L'incomplétude d'une fiche technique ne se voit
   aujourd'hui QUE sur l'écran produit (`pages/stock/ficheCompletude.js`, rendu
   par `CatalogueTable.jsx` et `ProduitDetail.jsx`). L'utilisateur du calepinage,
   lui, découvre le trou au moment où un verdict SE TAIT : le modèle thermique
   ne sort pas, le verdict de courant ne sort pas, et rien ne lui dit pourquoi.
   Ce panneau nomme, POUR LES ÉQUIPEMENTS DE CE CALEPINAGE, le champ fautif et
   le calcul qu'il débloque.

   AUCUNE RÈGLE N'EST RECOPIÉE. La complétude est LUE chez son propriétaire :
   `CHAMPS_REQUIS_PAR_TYPE` de `pages/stock/ficheCompletude.js` dit quels champs
   sont REQUIS (import en lecture, zéro duplication de la liste — le jour où le
   stock en ajoute un, il devient bloquant ici aussi, sans qu'une ligne de ce
   fichier ne bouge). Ce que ce fichier apporte EN PLUS, et qui n'existe nulle
   part ailleurs, c'est l'IMPACT : quel calcul du calepinage chaque champ
   débloque. C'est une information neuve, pas une copie.

   LA SOURCE EST LE SERVEUR. Les champs manquants viennent de l'agrégat CAL243
   (`GET /calepinage/calepinages/<pk>/equipements/`, contrat
   `calepinage_equipements.json`) — jamais d'un mock écrit à la main, jamais
   d'un recalcul côté écran. Une famille sans ligne retenue vaut `null` dans le
   contrat : l'écran écrit alors « aucun … retenu », jamais « fiche complète ».

   ZÉRO MESSAGE GÉNÉRIQUE : chaque ligne porte le NOM du champ ET la phrase du
   calcul qui s'arrête sans lui. Le test jumeau parcourt les `champs_manquants`
   du contrat COMMITTÉ et exige une phrase d'impact pour CHACUN.
   ========================================================================== */

/* ── L'IMPACT, champ par champ ─────────────────────────────────────────────
   Chaque entrée dit ce que le calepinage NE PEUT PAS produire sans ce champ.
   Les clés sont celles du contrat CAL243 (les specs du bloc `specs`, telles
   que `apps.stock.selectors.specs_for_produit` les publie), pas les clés
   préfixées du catalogue — la correspondance est faite par `PREFIXE_FICHE`. */
const IMPACT = {
  panneau: {
    longueur_mm: 'sans longueur : aucun calepinage — le pas de pose est inconnu',
    largeur_mm: 'sans largeur : aucun calepinage — le pas de pose est inconnu',
    epaisseur_mm: 'sans épaisseur : pas de hauteur de rail ni de garde au vent',
    poids_kg: 'sans poids : aucune descente de charge sur la toiture',
    pmax_wc: 'sans Pmax : aucune puissance crête, donc aucun productible',
    rendement_pct: 'sans rendement : aucune surface utile par kWc',
    voc_v: 'sans Voc : aucun verdict de tension de chaîne',
    vmp_v: 'sans Vmp : aucun placement dans la plage MPPT',
    isc_a: 'sans Isc : aucun verdict de courant d’entrée',
    imp_a: 'sans Imp : aucun courant de chaîne au point de puissance',
    temp_coeff_voc_pct_c: 'sans coefficient de température Voc : aucune tension à froid, donc aucun verdict de tension maximale',
    temp_coeff_pmax_pct_c: 'sans coefficient de température Pmax : aucune perte thermique, donc un productible surévalué',
    noct_c: 'sans NOCT : pas de modèle thermique — la température de cellule n’est pas calculable',
    uc_w_m2k: 'sans coefficient Uc : pas de modèle thermique au vent (Faiman)',
    uv_w_m3sk: 'sans coefficient Uv : pas de modèle thermique au vent (Faiman)',
    techno_cellule: 'sans technologie de cellule : aucun modèle de faible éclairement',
    bifacial: 'sans le caractère bifacial : aucun gain de face arrière n’est pris en compte',
    bifacialite_pct: 'sans taux de bifacialité : aucun gain de face arrière chiffré',
    degradation_annuelle_pct: 'sans dégradation annuelle : aucun productible à 10 ou 25 ans',
    degradation_annee1_pct: 'sans dégradation de première année : aucun productible d’année 1',
    garantie_pct_a_10_ans: 'sans garantie à 10 ans : aucun plancher de production contractuel à 10 ans',
    garantie_pct_a_25_ans: 'sans garantie à 25 ans : aucun plancher de production contractuel à 25 ans',
  },
  onduleur: {
    n_mppt: 'sans nombre de MPPT : aucune répartition des chaînes',
    mppt_v_min: 'sans tension MPPT minimale : aucun verdict de plage MPPT à chaud',
    mppt_v_max: 'sans tension MPPT maximale : aucun verdict de plage MPPT à froid',
    v_max_abs: 'sans tension maximale absolue : aucun verdict de sécurité de tension',
    v_demarrage_v: 'sans tension de démarrage : aucune heure de démarrage au lever du jour',
    i_max_mppt_a: 'sans courant MPPT maximal : aucun verdict de courant par entrée',
    isc_max_mppt_a: 'sans Isc maximal par MPPT : aucun verdict de courant de court-circuit',
    entrees_par_mppt: 'sans entrées par MPPT : aucun câblage de chaînes vérifiable',
    chaines_max_par_mppt: 'sans chaînes maximales par MPPT : aucun verdict de nombre de chaînes',
    ac_kw: 'sans puissance AC : aucun taux de surdimensionnement DC/AC',
    dc_max_kwc: 'sans puissance DC admissible : aucune limite de champ photovoltaïque',
    s_max_kva: 'sans puissance apparente maximale : aucun dimensionnement de raccordement',
    phases: 'sans nombre de phases : aucun verdict de raccordement mono/triphasé',
    rendement_euro_pct: 'sans rendement européen : aucune perte de conversion au productible',
    bat_max_charge_kw: 'sans puissance de charge batterie : aucun profil de charge',
    bat_max_decharge_kw: 'sans puissance de décharge batterie : aucun profil de décharge',
  },
  batterie: {
    kwh_nominal: 'sans capacité nominale : aucune autonomie calculable',
    dod_pct: 'sans profondeur de décharge : aucune énergie réellement utilisable',
    kwh_utile: 'sans énergie utile : aucune autonomie calculable',
    v_nominal: 'sans tension nominale : aucun verdict de compatibilité onduleur',
    p_charge_kw: 'sans puissance de charge : aucun temps de recharge',
    p_decharge_kw: 'sans puissance de décharge : aucune pointe soutenable',
    cycles: 'sans nombre de cycles : aucune durée de vie chiffrée',
    rendement_pct: 'sans rendement : aucune perte de stockage au bilan',
  },
  optimiseur: {
    p_max_wc: 'sans puissance maximale : aucun appairage au panneau',
    v_entree_max: 'sans tension d’entrée maximale : aucun verdict de compatibilité panneau',
    v_sortie_max: 'sans tension de sortie maximale : aucune longueur de chaîne admissible',
    i_entree_max_a: 'sans courant d’entrée maximal : aucun verdict de courant',
    rendement_pct: 'sans rendement : aucune perte d’optimisation au bilan',
  },
}

/* Les quatre familles de l'agrégat CAL243, dans l'ordre où elles se posent sur
   une toiture. Le libellé est celui qu'un poseur emploie. */
const FAMILLES = [
  ['panneau', 'Panneau', 'Aucun panneau retenu'],
  ['onduleur', 'Onduleur', 'Aucun onduleur retenu'],
  ['batterie', 'Batterie', 'Aucune batterie retenue'],
  ['optimiseur', 'Optimiseur', 'Aucun optimiseur retenu'],
]

/* Correspondance clé d'agrégat → clé du catalogue : `ficheCompletude.js` nomme
   les champs d'onduleur `ond_*` et ceux de batterie `bat_*`, l'agrégat les sert
   sans préfixe. On PRÉFIXE pour interroger la liste des requis — on ne la
   recopie pas. */
const PREFIXE_FICHE = { panneau: '', onduleur: 'ond_', batterie: 'bat_', optimiseur: '' }
const TYPE_FICHE = {
  panneau: 'module', onduleur: 'onduleur', batterie: 'batterie', optimiseur: null,
}

/** Les champs REQUIS de cette famille, lus chez leur propriétaire (stock). */
function champsRequis(famille) {
  const type = TYPE_FICHE[famille]
  const requis = type ? CHAMPS_REQUIS_PAR_TYPE[type] : null
  if (!requis) return new Map()
  const prefixe = PREFIXE_FICHE[famille]
  return new Map(requis.map(([cle, label]) => [
    prefixe && cle.startsWith(prefixe) ? cle.slice(prefixe.length) : cle,
    label,
  ]))
}

/** La phrase d'impact d'un champ. Jamais un message générique de remplissage. */
export function impactChamp(famille, champ) {
  return IMPACT[famille]?.[champ] ?? null
}

function LigneChamp({ famille, champ, requis }) {
  const impact = impactChamp(famille, champ)
  return (
    <li
      className="flex flex-wrap items-baseline gap-x-2 text-sm"
      data-testid={`cal-fiche-manquant-${famille}-${champ}`}
    >
      <code className="text-xs text-brass-300">{champ}</code>
      {requis && (
        <span className="tech-label text-lune-faint" data-testid={`cal-fiche-requis-${famille}-${champ}`}>
          requis
        </span>
      )}
      <span className="text-lune-soft">
        {impact ?? `champ servi par la fiche technique, hors du contrat de calcul documenté du calepinage (${champ})`}
      </span>
    </li>
  )
}

function Famille({ famille, label, absence, equipement }) {
  if (!equipement) {
    return (
      <section className="mt-4" data-testid={`cal-fiches-${famille}`}>
        <h4 className="tech-label text-lune-faint">{label}</h4>
        <p className="mt-1 text-sm text-lune-soft">
          {absence} sur le devis lié : rien à compléter ici tant qu’aucune ligne
          de cette famille n’est chiffrée.
        </p>
      </section>
    )
  }

  const manquants = equipement.champs_manquants ?? []
  const requis = champsRequis(famille)

  return (
    <section className="mt-4" data-testid={`cal-fiches-${famille}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h4 className="tech-label text-lune-faint">
          {label} — {equipement.designation ?? '—'}
        </h4>
        {/* Il n'existe aucune route `/stock/produits/:id` dans ce dépôt (la
            fiche s'ouvre en volet depuis le catalogue) : on renvoie donc vers
            le CATALOGUE, jamais vers un lien profond qui n'existe pas. */}
        <Link
          to="/stock"
          className="text-sm font-semibold text-brass-300 underline"
          data-testid={`cal-fiches-lien-${famille}`}
        >
          Ouvrir la fiche au catalogue
        </Link>
      </div>

      {manquants.length === 0 ? (
        <p className="mt-1 text-sm text-lune-soft" data-testid={`cal-fiches-complet-${famille}`}>
          Fiche complète : aucun calcul du calepinage n’est bloqué par cette
          famille.
        </p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {manquants.map((champ) => (
            <LigneChamp
              key={champ}
              famille={famille}
              champ={champ}
              requis={requis.has(champ)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

export default function FichesIncompletes({ calepinageId: idPropose }) {
  /* Montable des DEUX façons : en panneau de l'atelier (le parent passe
     `calepinageId`) ou en écran à part entière sous `/calepinage/:id/fiches`
     (le routeur monte le composant SANS props — l'identifiant vient alors de
     l'URL). Sans ce repli, la route serait déclarée et l'écran resterait vide :
     une route de plus qui ne mène à rien, exactement l'incident du 03/08/2026. */
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [agregat, setAgregat] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    /* Aucun `setState` SYNCHRONE dans le corps de l'effet (react-hooks v7) :
       l'état n'est touché que dans les callbacks de la promesse. */
    Promise.resolve(calepinageApi.calepinages.equipements(calepinageId))
      .then((res) => {
        if (annule) return
        setErreur(null)
        setAgregat(res?.data ?? null)
      })
      .catch((e) => {
        if (annule) return
        setAgregat(null)
        setErreur(e?.response?.data?.detail
          || 'Les équipements de ce calepinage n’ont pas pu être lus.')
      })
    return () => { annule = true }
  }, [calepinageId])

  if (erreur) {
    return (
      <div className="cine-card mt-6 p-6" data-testid="cal-fiches-incompletes">
        <p className="tech-label rule-brass text-brass-300">Fiches incomplètes</p>
        <p className="mt-2 text-sm text-red-300" role="alert" data-testid="cal-fiches-erreur">
          {erreur}
        </p>
      </div>
    )
  }

  // Tant que l'agrégat n'est pas arrivé, rien : jamais un panneau de tirets qui
  // ferait croire que toutes les fiches sont complètes.
  if (!agregat) return null

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-fiches-incompletes">
      <p className="tech-label rule-brass text-brass-300">Fiches incomplètes</p>

      {agregat.devis == null ? (
        <p className="mt-2 text-sm text-lune-soft" data-testid="cal-fiches-sans-devis">
          Aucun devis lié à ce calepinage : les équipements retenus se lisent sur
          le devis, il n’y a donc aucune fiche à vérifier pour l’instant.
        </p>
      ) : (
        <p className="mt-2 text-sm text-lune-soft">
          Chaque champ manquant ci-dessous nomme le calcul du calepinage qu’il
          débloque. Complétez-le sur la fiche technique du produit au catalogue.
        </p>
      )}

      {FAMILLES.map(([famille, label, absence]) => (
        <Famille
          key={famille}
          famille={famille}
          label={label}
          absence={absence}
          equipement={agregat[famille] ?? null}
        />
      ))}
    </div>
  )
}
