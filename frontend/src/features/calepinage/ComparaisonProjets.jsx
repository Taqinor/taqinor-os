import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AlertCircle, ArrowLeft, Download, X } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import useResource from '../../hooks/useResource'
import { formatNumber } from '../../lib/format'
import { Badge, Button, Card, EmptyState, Spinner } from '../../ui'
import { telechargerBlob } from './exportImage'

/* ============================================================================
   CALX342 — COMPARER DE 1 À 5 CALEPINAGES, sur leur propre route de liste.
   ----------------------------------------------------------------------------
   Le seul comparatif de l'écran était celui des VARIANTES d'un calepinage
   (`VariantesCompare.jsx`, route `:id/variantes`) : il ne sort jamais d'un
   calepinage. Parité PV*SOL (comparaison de 5 projets, y compris de dossiers
   différents — https://help.valentin-software.com/pvsol/en/project-comparison/).

   LA SÉLECTION se fait dans la LISTE (`CalepinageList.jsx`, mode « Comparer »)
   et voyage dans l'URL : `/calepinage/comparaison?ids=3,1` — partageable et
   rechargeable à l'identique. Retirer un calepinage ici réécrit l'URL.

   TOUT VIENT DU CONTRAT `calepinage_comparaison_projets.json` (CALX331) — et
   RIEN n'est recalculé ici :
     * les COLONNES (libellé + unité) sont celles que le serveur publie, dans
       son ordre : l'écran et le classeur « Comparatif » ne peuvent pas
       diverger ;
     * UN CALEPINAGE NON SIMULÉ EST DIT NON SIMULÉ : `simule: false` ⇒ ses
       grandeurs valent `null`, l'écran écrit « — » et AFFICHE LE MOTIF du
       serveur (jamais simulé, ou simulation périmée) — jamais `0`, qui se
       lirait « zéro kWh » là où personne n'a lancé de calcul ;
     * les identifiants IGNORÉS (autre société, inexistants) sont listés avec
       le motif du serveur, jamais tus.

   Le classeur est produit par le SERVEUR (`comparatif.xlsx`, CALX341) : un
   refus 400 arrive en Blob, son JSON est relu pour afficher SA phrase.
   ========================================================================== */

/** La borne du comparatif — celle du serveur (`BORNE_PROJETS`, CALX341). */
const BORNE = 5

const errMsg = (e, repli) => {
  const donnees = e?.response?.data
  if (donnees && typeof donnees === 'object') {
    if (donnees.ids) return String(donnees.ids)
    if (donnees.detail) return String(donnees.detail)
  }
  return repli
}

/** `?ids=3,1,3,x` → `[3, 1]` : entiers positifs, dédoublonnés, dans l'ordre. */
function idsDepuisRecherche(brut) {
  const vus = []
  for (const morceau of String(brut || '').split(',')) {
    const texte = morceau.trim()
    if (!/^\d+$/.test(texte)) continue
    const n = Number(texte)
    if (n > 0 && !vus.includes(n)) vus.push(n)
  }
  return vus
}

/** Une grandeur non mesurée s'écrit « — », jamais `0`. */
const ou = (valeur, rendu) => (valeur === null || valeur === undefined ? '—' : rendu(valeur))

/* Le rendu d'une grandeur, par sa CLÉ publiée. Les ratios (`performance_ratio`,
   `self_consumption_rate`, unité vide) s'affichent en pourcentage, comme dans
   le comparatif des variantes ; le formatage vit dans `lib/format.js`. */
const DECIMALES = { modules: 0, kwc: 2, p50_kwh: 0, p75_kwh: 0, p90_kwh: 0, specific_yield_kwh_kwc: 0 }
const RATIOS = ['performance_ratio', 'self_consumption_rate']

function rendreValeur(cle, valeur) {
  if (RATIOS.includes(cle)) {
    return ou(valeur, (x) => `${formatNumber(Number(x) * 100, { decimals: 1 })} %`)
  }
  return ou(valeur, (x) => formatNumber(x, { decimals: DECIMALES[cle] ?? 2 }))
}

const libelleColonne = (colonne) => (colonne.unite && !RATIOS.includes(colonne.cle)
  ? `${colonne.libelle} (${colonne.unite})`
  : colonne.libelle)

/* Le motif d'un refus de CLASSEUR : la réponse est demandée en `blob`, un 400
   arrive donc lui aussi en Blob — son JSON (`{ids: motif}`) est relu pour
   afficher la phrase du serveur, jamais une phrase reformulée ici. */
async function motifDuRefusClasseur(erreur) {
  const donnees = erreur?.response?.data
  try {
    const texte = typeof donnees?.text === 'function' ? await donnees.text() : donnees
    const objet = typeof texte === 'string' ? JSON.parse(texte) : texte
    const premier = objet && typeof objet === 'object' ? Object.values(objet)[0] : null
    if (premier) return String(premier)
  } catch {
    // Le corps n'est pas un refus JSON : on ne devine pas ce qu'il disait.
  }
  return 'Le classeur n’a pas pu être produit par le serveur.'
}

function EnTeteCalepinage({ ligne, onRetirer }) {
  return (
    <div className="space-y-1">
      <div className="flex items-start justify-between gap-2">
        <Link to={`/calepinage/${ligne.id}`} className="font-medium hover:underline">
          {ligne.titre || `Calepinage #${ligne.id}`}
        </Link>
        <button
          type="button"
          className="shrink-0 text-muted-foreground hover:text-foreground"
          aria-label={`Retirer ${ligne.titre || `le calepinage #${ligne.id}`} de la comparaison`}
          onClick={() => onRetirer(ligne.id)}
        >
          <X size={14} aria-hidden="true" />
        </button>
      </div>
      {!ligne.simule ? <Badge variant="outline">Non simulé</Badge> : null}
      {!ligne.simule && ligne.motif ? (
        <p className="text-xs font-normal text-muted-foreground"
          data-testid={`cal-comparaison-motif-${ligne.id}`}>
          {ligne.motif}
        </p>
      ) : null}
    </div>
  )
}

export default function ComparaisonProjets() {
  const [searchParams, setSearchParams] = useSearchParams()
  const ids = useMemo(() => idsDepuisRecherche(searchParams.get('ids')), [searchParams])
  const [motifClasseur, setMotifClasseur] = useState(null)
  const [classeurEnCours, setClasseurEnCours] = useState(false)

  const { data, loading, error } = useResource(
    (p) => calepinageApi.calepinages.comparerProjets(p.ids),
    { ids },
    {
      initialData: null,
      enabled: ids.length > 0,
      select: (res) => res?.data ?? null,
      errorMessage: (e) => errMsg(e, 'Impossible de charger la comparaison des calepinages.'),
    },
  )

  const colonnes = Array.isArray(data?.colonnes) ? data.colonnes : []
  const lignes = Array.isArray(data?.lignes) ? data.lignes : []
  const refus = Array.isArray(data?.refus) ? data.refus : []

  const retirer = (id) => {
    const restants = ids.filter((autre) => autre !== id)
    const suivants = new URLSearchParams(searchParams)
    if (restants.length) suivants.set('ids', restants.join(','))
    else suivants.delete('ids')
    setSearchParams(suivants)
  }

  const telechargerClasseur = () => {
    if (!lignes.length) return
    const [premier, ...autres] = lignes.map((ligne) => ligne.id)
    setMotifClasseur(null)
    setClasseurEnCours(true)
    calepinageApi.calepinages.comparatifXlsx(premier, autres)
      .then((reponse) => {
        telechargerBlob(reponse.data, `comparatif-calepinages-${[premier, ...autres].join('-')}.xlsx`)
      })
      .catch(async (err) => { setMotifClasseur(await motifDuRefusClasseur(err)) })
      .finally(() => setClasseurEnCours(false))
  }

  const retour = (
    <Link to="/calepinage" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft size={15} aria-hidden="true" />
      Retour à la liste
    </Link>
  )

  if (!ids.length) {
    return (
      <div className="space-y-4">
        {retour}
        <EmptyState
          title="Aucun calepinage à comparer"
          description={`Depuis la liste, activez « Comparer » puis cochez de 2 à ${BORNE} calepinages.`}
          action={(
            <Button size="sm" asChild>
              <Link to="/calepinage?comparer=1">Choisir dans la liste</Link>
            </Button>
          )}
        />
      </div>
    )
  }

  if (loading && !data) return <div className="flex justify-center py-10"><Spinner /></div>

  return (
    <div className="space-y-4">
      {retour}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold">Comparer des calepinages</h1>
        <Button size="sm" variant="outline" onClick={telechargerClasseur}
          disabled={!lignes.length || classeurEnCours} data-testid="cal-comparaison-classeur">
          <Download size={16} aria-hidden="true" />
          {classeurEnCours ? 'Préparation…' : 'Télécharger le classeur'}
        </Button>
      </div>

      {error ? (
        <Card className="border-destructive/50 bg-destructive/5 p-3" role="alert">
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        </Card>
      ) : null}

      {motifClasseur ? (
        <p role="alert" className="text-sm text-destructive" data-testid="cal-comparaison-motif-classeur">
          {motifClasseur}
        </p>
      ) : null}

      {refus.length > 0 ? (
        <Card className="space-y-1 p-3 text-sm text-muted-foreground" data-testid="cal-comparaison-refus">
          {refus.map((r) => (
            <div key={r.id}>{`Calepinage #${r.id} — ${r.motif}`}</div>
          ))}
        </Card>
      ) : null}

      {!error && lignes.length > 0 ? (
        <Card className="overflow-x-auto p-0">
          <table role="grid" aria-label="Comparaison des calepinages" className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="p-3 text-left font-medium">Grandeur</th>
                {lignes.map((ligne) => (
                  <th key={ligne.id} scope="col" className="p-3 text-left align-top">
                    <EnTeteCalepinage ligne={ligne} onRetirer={retirer} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border/60">
                <th scope="row" className="p-3 text-left font-normal text-muted-foreground">Statut</th>
                {lignes.map((ligne) => (
                  <td key={ligne.id} className="p-3">{ligne.statut || '—'}</td>
                ))}
              </tr>
              {colonnes.map((colonne) => (
                <tr key={colonne.cle} className="border-b border-border/60">
                  <th scope="row" className="p-3 text-left font-normal text-muted-foreground">
                    {libelleColonne(colonne)}
                  </th>
                  {lignes.map((ligne) => (
                    <td key={ligne.id} className="p-3" data-testid={`cal-comparaison-${colonne.cle}-${ligne.id}`}>
                      {rendreValeur(colonne.cle, ligne[colonne.cle])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      {!error && !loading && data && !lignes.length ? (
        <Card className="p-4 text-sm text-muted-foreground">
          Aucun des calepinages demandés n’est comparable dans cette société.
        </Card>
      ) : null}
    </div>
  )
}
