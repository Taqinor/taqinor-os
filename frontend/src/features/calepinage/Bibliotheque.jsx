import { useEffect, useState } from 'react'
import calepinageApi from '../../api/calepinageApi'
import { useHasPermission } from '../../hooks/useHasPermission'
import { Badge, Card, Spinner } from '../../ui'

/* ============================================================================
   CAL201 — L'ÉCRAN « BIBLIOTHÈQUE » DU MODULE (presets, kits, modèles,
   favoris), SOCIÉTÉ ACTIVE RESPECTÉE.
   ----------------------------------------------------------------------------
   Constat : aucune surface frontend n'exposait ces réglages hors du studio AO
   (`features/ao/calepinage/CalepinageStudio.jsx`) — le module autonome
   n'avait nulle part où les consulter.

   LES QUATRE LISTES VIENNENT DE DEUX ENDPOINTS, JAMAIS D'UNE TROISIÈME
   FORME (CAL233/CAL246) :
     * `GET /calepinage/parametres/` sert `presets`, `favoris_materiel` (les
       deux sections de `ParametresCalepinage`, CAL197/CAL200) et `kits` (le
       catalogue AO LU, jamais stocké, CAL198) ;
     * `GET /calepinage/calepinages/modeles/` sert les calepinages marqués
       MODÈLE (drapeau `records.Tag`, CAL199).

   LECTURE SEULE SANS `calepinage_gerer` (Done de la tâche) : l'écran affiche
   TOUJOURS les quatre listes — seule l'ÉDITION des presets/favoris (les deux
   sections que `PUT /calepinage/parametres/` accepte SANS normaliseur dédié,
   `services/parametres.py::_normaliseurs`) est gardée par la permission.
   Kits et modèles restent lecture seule ICI QUEL QUE SOIT LE DROIT : aucun
   endpoint d'écriture n'existe pour eux depuis cet écran — la tâche ne
   l'invente pas, elle le DIT (PACT159, jamais une promesse en prose).
   ========================================================================== */

function Section({ titre, sousTitre, children }) {
  return (
    <Card className="p-4" data-testid={`cal-biblio-${titre.toLowerCase()}`}>
      <p className="text-sm font-semibold text-foreground">{titre}</p>
      {sousTitre && <p className="mt-0.5 text-xs text-muted-foreground">{sousTitre}</p>}
      <div className="mt-3">{children}</div>
    </Card>
  )
}

function ListeVide({ enfant }) {
  return <p className="text-sm text-muted-foreground">{enfant}</p>
}

export default function Bibliotheque() {
  const peutGerer = useHasPermission('calepinage_gerer')

  const [parametres, setParametres] = useState(null)
  const [modeles, setModeles] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let annule = false
    Promise.all([
      Promise.resolve(calepinageApi.parametres.get()),
      Promise.resolve(calepinageApi.calepinages.modeles()),
    ])
      .then(([resParametres, resModeles]) => {
        if (annule) return
        setParametres(resParametres?.data ?? null)
        const liste = resModeles?.data
        setModeles(Array.isArray(liste) ? liste : (liste?.results ?? []))
      })
      .catch((e) => {
        if (annule) return
        setErreur(e?.response?.data?.detail
          || 'La bibliothèque n’a pas pu être chargée.')
      })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [])

  if (chargement) {
    return <div className="page" data-testid="cal-bibliotheque"><Spinner /></div>
  }
  if (erreur) {
    return (
      <div className="page" data-testid="cal-bibliotheque">
        <p role="alert" className="text-sm text-destructive"
          data-testid="cal-biblio-erreur">{erreur}</p>
      </div>
    )
  }

  const presets = parametres?.presets ?? {}
  const favoris = parametres?.favoris_materiel ?? {}
  const kits = Array.isArray(parametres?.kits) ? parametres.kits : []

  const clesPresets = Object.keys(presets)
  const clesFavoris = Object.keys(favoris)

  return (
    <div className="page" data-testid="cal-bibliotheque">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-lg font-semibold text-foreground">Bibliothèque</h1>
        {!peutGerer && (
          <Badge variant="outline" data-testid="cal-biblio-lecture-seule">
            Lecture seule
          </Badge>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Presets, kits de pose, calepinages modèles et matériel favori de votre
        société — réutilisés à chaque conception, jamais réinventés.
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Section titre="Presets"
          sousTitre="Marges, espacements et dégagements réutilisés (CAL197)">
          {clesPresets.length === 0
            ? <ListeVide enfant="Aucun preset réglé : les valeurs de l’atelier s’appliquent." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-presets-liste">
                {clesPresets.map((cle) => (
                  <li key={cle} data-testid={`cal-biblio-preset-${cle}`}>
                    <span className="font-medium">{cle}</span>
                    {' — '}
                    <span className="text-muted-foreground">
                      {Object.entries(presets[cle] ?? {})
                        .map(([champ, valeur]) => `${champ} : ${valeur}`)
                        .join(', ') || 'aucun champ'}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          {!peutGerer && (
            <p className="mt-2 text-xs text-muted-foreground">
              Sans le droit « gérer le calepinage », la création/édition des
              presets n’est pas proposée ici.
            </p>
          )}
        </Section>

        <Section titre="Kits"
          sousTitre="Catalogue de pose du stock, lu (jamais dupliqué, CAL198)">
          {kits.length === 0
            ? <ListeVide enfant="Aucun kit de pose disponible pour votre société." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-kits-liste">
                {kits.map((kit) => (
                  <li key={kit.id} data-testid={`cal-biblio-kit-${kit.id}`}>
                    <span className="font-medium">{kit.libelle || kit.code}</span>
                    {' — '}
                    <span className="text-muted-foreground">
                      {kit.modules_par_kit != null
                        ? `${kit.modules_par_kit} module(s)/kit`
                        : 'composition non renseignée'}
                      {kit.puissance_module_w ? ` · ${kit.puissance_module_w} W` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          <p className="mt-2 text-xs text-muted-foreground">
            Catalogue en lecture seule depuis cet écran : gérez-le depuis le
            stock.
          </p>
        </Section>

        <Section titre="Modèles"
          sousTitre="Calepinages marqués réutilisables (CAL199)">
          {(modeles ?? []).length === 0
            ? <ListeVide enfant="Aucun calepinage n’est marqué modèle." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-modeles-liste">
                {modeles.map((modele) => (
                  <li key={modele.id} data-testid={`cal-biblio-modele-${modele.id}`}>
                    <span className="font-medium">
                      {modele.titre || `Calepinage #${modele.id}`}
                    </span>
                    {modele.statut_libelle && (
                      <span className="text-muted-foreground"> — {modele.statut_libelle}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
        </Section>

        <Section titre="Favoris matériel"
          sousTitre="Modules et onduleurs favoris du catalogue (CAL200)">
          {clesFavoris.length === 0
            ? <ListeVide enfant="Aucun matériel favori réglé pour votre société." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-favoris-liste">
                {clesFavoris.map((cle) => {
                  const ids = Array.isArray(favoris[cle]) ? favoris[cle] : []
                  return (
                    <li key={cle} data-testid={`cal-biblio-favori-${cle}`}>
                      <span className="font-medium">{cle}</span>
                      {' — '}
                      <span className="text-muted-foreground">
                        {ids.length > 0
                          ? `${ids.length} produit(s) (#${ids.join(', #')})`
                          : 'aucun produit'}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          {!peutGerer && (
            <p className="mt-2 text-xs text-muted-foreground">
              Sans le droit « gérer le calepinage », la création/édition des
              favoris n’est pas proposée ici.
            </p>
          )}
        </Section>
      </div>
    </div>
  )
}
