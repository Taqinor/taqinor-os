import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import {
  CHAMPS_REQUIS_PAR_TYPE,
} from '../../../pages/stock/ficheCompletude'
import RetourAtelier from '../atelier/RetourAtelier'
import { impactChamp } from './FichesIncompletes.helpers'

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

/* ACAL264 — LE MATÉRIEL RÉELLEMENT UTILISÉ PAR LE CALCUL. Les familles
   ci-dessus sont celles du DEVIS ; le calcul (kWc de pose, chaînes,
   simulation) utilise, lui, le matériel RÉSOLU que sert
   `GET entree-electrique/` (`materiel`, contrat
   `calepinage_entree_electrique.json`) : désignation explicite d'abord, la
   ligne du devis à défaut — et le module de CHAQUE pan quand le plan en porte
   un autre. On l'affiche tel que servi, jamais recalculé ici. */
const ROLES_CALCUL = [
  ['module', 'Module'],
  ['onduleur', 'Onduleur'],
  ['optimiseur', 'Optimiseur'],
]
const PROVENANCES = {
  explicite: 'désigné dans l’entrée électrique',
  devis: 'ligne du devis lié',
}

function MaterielDuCalcul({ materiel, panneauDevis }) {
  if (!materiel) return null
  const module = materiel.module
  /* ACAL359 — une ligne par pan dès qu'un pan porte un autre module, ou que
     la fiche d'un pan manque ; un champ mono-module garde la ligne « Module ». */
  const lignes = Array.isArray(materiel.modules_par_pan) ? materiel.modules_par_pan : []
  const parPan = lignes.length > 1 || lignes.some((l) => !l.fiche_resolue) ? lignes : []
  const ecart = module && panneauDevis
    && module.produit_id != null && panneauDevis.produit != null
    && String(module.produit_id) !== String(panneauDevis.produit)
  return (
    <section className="mt-4" data-testid="cal-fiches-materiel-calcul">
      <h4 className="tech-label text-lune-faint">Matériel utilisé par le calcul</h4>
      <ul className="mt-2 space-y-1.5">
        {ROLES_CALCUL.map(([role, libelle]) => {
          const bloc = materiel[role]
          return (
            <li key={role} className="text-sm text-lune-soft"
              data-testid={`cal-fiches-materiel-${role}`}>
              <span className="text-lune">{libelle}</span>
              {' — '}
              {bloc
                ? (
                  <>
                    {bloc.designation || `produit ${bloc.produit_id}`}
                    {bloc.provenance && ` (${PROVENANCES[bloc.provenance] ?? bloc.provenance})`}
                    {bloc.fiche_complete === false && (bloc.champs_manquants ?? []).length > 0 && (
                      <span className="text-red-300">
                        {' '}— fiche incomplète : {bloc.champs_manquants.join(', ')}
                      </span>
                    )}
                  </>
                )
                : 'aucun'}
            </li>
          )
        })}
      </ul>
      {parPan.length > 0 && (
        <ul className="mt-2 space-y-1" data-testid="cal-fiches-modules-par-pan">
          {parPan.map((ligne) => (
            <li key={ligne.pan} className="text-sm text-lune-soft"
              data-testid={`cal-fiches-module-pan-${ligne.pan}`}>
              <span className="text-lune">Pan {ligne.pan}</span>
              {' — '}
              {ligne.designation || 'module sans désignation'}
              {!ligne.fiche_resolue && (
                <span className="text-red-300">
                  {' '}— sans fiche : chaîné avec la fiche du module par défaut
                </span>
              )}
              {ligne.fiche_resolue && !ligne.fiche_complete && (
                <span className="text-red-300"> — fiche incomplète</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {ecart && (
        <p className="mt-2 text-sm text-red-300" role="alert" data-testid="cal-fiches-ecart-module">
          Le calcul utilise « {module.designation} », le devis chiffre
          « {panneauDevis.designation ?? `produit ${panneauDevis.produit}`} ».
        </p>
      )}
      <p className="mt-2 text-xs text-lune-faint">
        Un pan qui porte son propre module dans le plan est chiffré et chaîné
        avec CE module ; le module ci-dessus n’est que le défaut des autres pans.
      </p>
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

  // ACAL264 — le matériel RÉSOLU du calcul. Son échec n'éteint pas le
  // panneau : le bloc ne s'affiche simplement pas.
  const [materiel, setMateriel] = useState(null)
  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve()
      .then(() => calepinageApi.calepinages.entreeElectrique(calepinageId))
      .then((res) => { if (!annule) setMateriel(res?.data?.materiel ?? null) })
      .catch(() => { if (!annule) setMateriel(null) })
    return () => { annule = true }
  }, [calepinageId])

  if (erreur) {
    return (
      <>
        <RetourAtelier calepinageId={calepinageId} />
        <div className="cine-card mt-6 p-6" data-testid="cal-fiches-incompletes">
          <p className="tech-label rule-brass text-brass-300">Fiches incomplètes</p>
          <p className="mt-2 text-sm text-red-300" role="alert" data-testid="cal-fiches-erreur">
            {erreur}
          </p>
        </div>
      </>
    )
  }

  // Tant que l'agrégat n'est pas arrivé, rien : jamais un panneau de tirets qui
  // ferait croire que toutes les fiches sont complètes.
  if (!agregat) return null

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
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

      <MaterielDuCalcul materiel={materiel} panneauDevis={agregat.panneau ?? null} />

    </div>
    </>
  )
}
