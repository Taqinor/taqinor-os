import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import { Button } from '../../ui'
import { messageRefus } from './commun/refusServeur'
import { ligneModule } from './atelier/coque/etapes/panneaux/formats'

/* ============================================================================
   ACAL600 — « COMPARER D'AUTRES MODULES » (étape Panneaux, niveau expert).
   ----------------------------------------------------------------------------
   La boîte lit `modulesDisponibles` (CALX109), fait cocher 2 à 3 fiches
   complètes, appelle `variantesParModule` (ACAL594) AVEC LES SEULS COCHÉS, puis
   ouvre le comparatif du rail (`?onglet=variantes`, ACAL409). Rien n'est
   calculé ici : la production affichée ensuite vient du contrat. Une fiche
   incomplète est listée avec SON motif, jamais cochable ; sans assez de fiches
   complètes, le bouton est absent et l'écran dit pourquoi (motif servi).
   ========================================================================== */

const MIN = 2
const MAX = 3

/** Le module que NOMME le refus serveur (« « libellé » : motif »), sinon aucun. */
const moduleNomme = (texte, entrees, coches) => entrees.find(
  (e) => coches.includes(e.module.id) && texte.includes(`« ${e.module.libelle} »`))?.module.id ?? null

export default function ComparerModules({ calepinageId }) {
  const naviguer = useNavigate()
  const [servi, setServi] = useState(null)
  const [ouvert, setOuvert] = useState(false)
  const [coches, setCoches] = useState([])
  const [refus, setRefus] = useState(null)
  const [envoi, setEnvoi] = useState(false)

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.modulesDisponibles(calepinageId))
      .then((res) => { if (!annule) setServi(res?.data ?? null) })
      .catch(() => { if (!annule) setServi(null) })
    return () => { annule = true }
  }, [calepinageId])

  if (!servi) return null
  const entrees = Array.isArray(servi.modules) ? servi.modules : []
  const completes = entrees.filter((e) => e.selectionnable)
  if (completes.length < MIN) {
    return (
      <p className="text-xs text-muted-foreground" role="status" data-testid="cal-comparer-modules-absent">
        {servi.motif_liste_vide
          || 'Comparer d’autres modules demande au moins deux fiches « module » complètes au stock.'}
      </p>
    )
  }

  const basculer = (id) => setCoches((avant) => (avant.includes(id)
    ? avant.filter((c) => c !== id) : [...avant, id].slice(0, MAX)))

  const valider = async () => {
    setEnvoi(true)
    setRefus(null)
    try {
      await calepinageApi.calepinages.variantesParModule(calepinageId, coches)
      naviguer(`/calepinage/${calepinageId}?onglet=variantes`)
    } catch (erreur) {
      const texte = messageRefus(erreur, 'Les variantes n’ont pas pu être créées.')
      setRefus({ texte, module: moduleNomme(texte, entrees, coches) })
    } finally {
      setEnvoi(false)
    }
  }

  if (!ouvert) {
    return (
      <button type="button" onClick={() => setOuvert(true)} data-testid="cal-comparer-modules"
        className="min-h-11 text-sm font-semibold text-primary-text underline">
        Comparer d’autres modules
      </button>
    )
  }

  return (
    <fieldset className="mt-2 rounded-lg border border-border p-3" data-testid="cal-comparer-modules-boite">
      <legend className="px-1 text-sm font-semibold text-foreground">
        {`Comparer d’autres modules : cochez de ${MIN} à ${MAX} modules`}
      </legend>
      <ul className="space-y-1">
        {entrees.map(({ module, selectionnable, motif, en_stock: enStock }) => (
          <li key={module.id}>
            <label className="flex min-h-11 items-center gap-2 text-sm text-foreground">
              <input type="checkbox" data-testid={`cal-comparer-module-${module.id}`}
                checked={coches.includes(module.id)} onChange={() => basculer(module.id)}
                disabled={!selectionnable || (!coches.includes(module.id) && coches.length >= MAX)} />
              {module.libelle}
            </label>
            {!selectionnable && motif && <p className="ml-6 text-xs text-muted-foreground">{motif}</p>}
            {selectionnable && (enStock || ligneModule(module)) && (
              <p className="ml-6 text-xs text-muted-foreground">
                {[enStock ? 'En stock' : '', ligneModule(module)].filter(Boolean).join(' · ')}
              </p>
            )}
            {refus?.module === module.id && (
              <p role="alert" className="ml-6 text-xs text-destructive" data-testid={`cal-comparer-refus-${module.id}`}>
                {refus.texte}
              </p>
            )}
          </li>
        ))}
      </ul>
      {refus && !refus.module && (
        <p role="alert" className="mt-2 text-xs text-destructive" data-testid="cal-comparer-refus">{refus.texte}</p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" onClick={valider} data-testid="cal-comparer-modules-valider"
          disabled={envoi || coches.length < MIN || coches.length > MAX}>
          {envoi ? 'Création…' : 'Créer les variantes et comparer'}
        </Button>
        <Button size="sm" variant="outline" onClick={() => setOuvert(false)}>Fermer</Button>
      </div>
    </fieldset>
  )
}
