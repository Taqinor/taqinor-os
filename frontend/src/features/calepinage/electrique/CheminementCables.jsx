/* eslint-disable react-refresh/only-export-components --
   `libelleOrigine`/`libelleCote` sont des fonctions PURES que le test
   unitaire confronte à l'exemple committé du contrat. Même dérogation que
   `AffectationChaines.jsx`/`PanneauMasseLestage.jsx` du même module. */
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Card, EmptyState, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'

/* ============================================================================
   CALX229 — L'ONGLET « CHEMINEMENT & CÂBLES » DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT QUI JUSTIFIE CE FICHIER. `resultat['cables']` (CAL131) ne porte que
   DEUX lignes scalaires (`W1` DC, `W2` AC) : aucune chute par tronçon, aucun
   métré par section, aucun cumul le long du chemin. `PanneauProduction.jsx`,
   `DiagrammePertes.jsx` et `AffectationChaines.jsx` lisent `resultat`, aucun
   n'affiche un tronçon. Parité HelioScope : chaque conducteur porte sa chute
   totale.

   LA SOURCE EST `GET calepinages/<pk>/troncons/` (CALX203, contrat
   `calepinage_troncons.json`) — SEULE porte de ce panneau, ajoutée EN FIN de
   `calepinageApi.js` (`// CALX229`). CETTE ROUTE N'EXISTE PAS ENCORE CÔTÉ
   SERVEUR au moment où cette lane est écrite (son producteur,
   `services/troncons.py`, est CALX224-226, une lane différente de celle-ci) :
   un 404 est donc un état ATTENDU et TRANSITOIRE, pas une panne — l'écran le
   dit avec un état dédié plutôt que le message d'erreur générique.

   ZÉRO CHIFFRE INVENTÉ (D-CALX 7), DANS LES DEUX SENS. `null` n'est JAMAIS
   affiché comme `0` : `formatNumber`/`formatPercent` (lib/format.js) rendent
   déjà « — » pour `null`, ce panneau ne réimplémente donc rien de son cru
   pour cette règle. Une longueur publie TOUJOURS son origine
   (`services/cables.py`, discipline `Longueur`) : jamais un nombre nu.

   LES OMISSIONS DU SERVEUR SONT RECOPIÉES, JAMAIS REFORMULÉES. `omissions[]`
   nomme déjà le tronçon, le champ et le motif en français — l'écran les
   affiche tels quels, un champ à côté (jamais fondu dans) le motif.
   ========================================================================== */

const LIBELLES_COTE = { dc: 'DC', ac: 'AC', terre: 'Terre' }

/** Le libellé du côté d'un tronçon — un code inconnu est NOMMÉ, jamais tu. */
export function libelleCote(cote) {
  return LIBELLES_COTE[cote] ?? `côté « ${cote} »`
}

const LIBELLES_ORIGINE = {
  plan: 'tracé sur le plan',
  saisie: 'saisie au clavier',
  mixte: 'tracé + saisie (mixte)',
}

/** Le libellé français de l'origine d'une longueur — jamais un nombre nu. */
export function libelleOrigine(origine) {
  if (!origine) return null
  return LIBELLES_ORIGINE[origine] ?? `origine « ${origine} »`
}

/** Le contenu de la cellule « longueur » : le nombre ET sa provenance ensemble. */
export function celluleLongueur(troncon) {
  if (troncon?.longueur_m === null || troncon?.longueur_m === undefined) return '—'
  const origine = libelleOrigine(troncon.longueur_origine)
  const nombre = formatNumber(troncon.longueur_m, { decimals: 1 })
  return origine ? `${nombre} m (${origine})` : `${nombre} m`
}

const CODE_NON_CALCULE = 'CALX229_NON_CALCULE'

export default function CheminementCables({ calepinageId } = {}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.troncons(id), id,
    {
      select: (r) => r.data,
      errorMessage: (err) => (err?.response?.status === 404
        ? CODE_NON_CALCULE
        : 'Métré des tronçons indisponible.'),
    },
  )

  if (loading) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="cheminement-cables" />
        <Spinner />
      </>
    )
  }

  if (error === CODE_NON_CALCULE) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="cheminement-cables" />
        <EmptyState
          data-testid="calx229-non-calcule"
          tone="neutral"
          title="Métré des tronçons pas encore calculable ici"
          description="Cette porte serveur n’est pas encore déployée sur cet environnement (vague Électrique Pro) : aucune longueur ni chute n’est calculée, ce n’est pas une panne de l’écran."
        />
      </>
    )
  }
  if (error) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="cheminement-cables" />
        <p className="text-sm text-destructive" data-testid="calx229-erreur">{error}</p>
      </>
    )
  }

  const troncons = Array.isArray(data?.troncons) ? data.troncons : []
  const totaux = data?.totaux || {}
  const metreParSection = Array.isArray(totaux.metre_par_section) ? totaux.metre_par_section : []
  const omissions = Array.isArray(data?.omissions) ? data.omissions : []

  return (
    <>
      <RetourAtelier calepinageId={id} cle="cheminement-cables" />
      <Card className="flex flex-col gap-4 p-4" data-testid="calx229-panneau">
        <header className="flex flex-col gap-1">
          <h2 className="text-base font-semibold">Cheminement &amp; câbles</h2>
          <p className="text-sm text-muted-foreground">
            Le métré et la chute de tension, tronçon par tronçon — recopiés du
            serveur, aucun calcul refait côté écran.
          </p>
        </header>

        <div className="flex flex-wrap gap-4 text-sm" data-testid="calx229-totaux">
          <span>
            Chute DC cumulée :
            {' '}
            <strong data-testid="calx229-total-dc">{formatPercent(totaux.dc_chute_pct, { decimals: 2 })}</strong>
          </span>
          <span>
            Chute AC cumulée :
            {' '}
            <strong data-testid="calx229-total-ac">{formatPercent(totaux.ac_chute_pct, { decimals: 2 })}</strong>
          </span>
        </div>

        {troncons.length === 0
          ? (
            <EmptyState
              data-testid="calx229-vide"
              title="Aucun tronçon mesurable"
              description="Aucun cheminement n’est tracé sur ce plan — tracez les liaisons dans l’atelier 3D, ou saisissez leurs longueurs."
            />
          )
          : (
            <table className="w-full text-left text-sm" data-testid="calx229-troncons">
              <thead>
                <tr className="text-xs uppercase text-muted-foreground">
                  <th scope="col" className="py-1">Repère</th>
                  <th scope="col" className="py-1">Côté</th>
                  <th scope="col" className="py-1">De → vers</th>
                  <th scope="col" className="py-1">Longueur</th>
                  <th scope="col" className="py-1">Section</th>
                  <th scope="col" className="py-1">Critère dimensionnant</th>
                  <th scope="col" className="py-1">Chute</th>
                  <th scope="col" className="py-1">Chute cumulée</th>
                </tr>
              </thead>
              <tbody>
                {troncons.map((t) => (
                  <tr key={t.id} data-testid={`calx229-troncon-${t.id}`}>
                    <th scope="row" className="py-1 font-normal">{t.id}</th>
                    <td className="py-1">{libelleCote(t.cote)}</td>
                    <td className="py-1">{`${t.de ?? '—'} → ${t.vers ?? '—'}`}</td>
                    <td className="py-1" data-testid={`calx229-longueur-${t.id}`}>
                      {celluleLongueur(t)}
                    </td>
                    <td className="py-1" data-testid={`calx229-section-${t.id}`}>
                      {t.section_mm2 === null || t.section_mm2 === undefined
                        ? '—'
                        : `${formatNumber(t.section_mm2, { decimals: 1 })} mm²`}
                    </td>
                    <td className="py-1" title={t.regle_source || ''}>
                      {t.critere_dimensionnant || '—'}
                    </td>
                    <td className="py-1" data-testid={`calx229-chute-${t.id}`}>
                      {formatPercent(t.chute_pct, { decimals: 2 })}
                    </td>
                    <td className="py-1">{formatPercent(t.chute_cumulee_pct, { decimals: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

        <section className="flex flex-col gap-1" data-testid="calx229-metre-section">
          <p className="text-xs font-medium text-muted-foreground">Métré à commander, par section</p>
          {metreParSection.length === 0
            ? <p className="text-sm text-muted-foreground">Aucun métré publié.</p>
            : (
              <ul className="text-sm">
                {metreParSection.map((ligne, index) => (
                  // La section peut valoir `null` plusieurs fois (pas de clé
                  // stable côté serveur) : l'ordre servi fait foi.
                  <li key={index}>
                    {ligne.section_mm2 === null || ligne.section_mm2 === undefined
                      ? 'Section non déterminée'
                      : `${formatNumber(ligne.section_mm2, { decimals: 1 })} mm²`}
                    {' : '}
                    {formatNumber(ligne.longueur_m, { decimals: 1 })}
                    {' m'}
                  </li>
                ))}
              </ul>
            )}
        </section>

        {omissions.length > 0
          ? (
            <section className="flex flex-col gap-1" data-testid="calx229-omissions">
              <p className="text-xs font-medium text-muted-foreground">Ce que le serveur n’a pas pu calculer</p>
              <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                {omissions.map((o, index) => (
                  // Pas d'identifiant stable côté serveur pour une omission.
                  <li key={index} data-testid={`calx229-omission-${index}`}>
                    {o.champ ? <span className="font-medium">{`${o.champ} — `}</span> : null}
                    {o.motif}
                  </li>
                ))}
              </ul>
            </section>
          )
          : null}
      </Card>
    </>
  )
}
