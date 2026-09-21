/* eslint-disable react-refresh/only-export-components --
   `TYPES_EQUIPEMENT`/`LIBELLES_TYPE`/`libelleType`/`libelleProduit` sont des
   constantes et fonctions PURES que le test unitaire de la tâche confronte
   directement à l'énumération du contrat (`electrique_equipements.json`,
   CALX201). Les sortir dans un `.js` voisin séparerait la table de son unique
   lecteur pour satisfaire une règle de fast-refresh qui ne s'applique pas à
   une constante — même dérogation que `AffectationChaines.jsx` et
   `PanneauMasseLestage.jsx` du même module. */
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Zap } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { Button, Card, EmptyState, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'

/* ============================================================================
   CALX222 — L'ONGLET « ÉQUIPEMENTS ÉLECTRIQUES » DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT QUI JUSTIFIE CE FICHIER. Aucun composant du module ne pilotait un
   équipement électrique : `AffectationChaines.jsx` affecte des chaînes de
   modules et `SchemaUnifilairePanel.jsx` insère un SVG serveur, mais rien
   n'affichait les organes posés dans la scène 3D (`electrical.equipements[]`,
   CALX201 — onduleur, coffret DC/AC, compteurs, TGBT, batterie, parafoudre).
   Parité Aurora : les équipements se placent dans le modèle système AVANT le
   stringage.

   LA SOURCE EST LE DOCUMENT, PAS UNE SECONDE COPIE. `electrical.equipements[]`
   est une clé racine OPTIONNELLE du document `roof_layout` v2 (CALX201) : ce
   panneau LIT ce document par la porte EXISTANTE `calepinages.layout(id)`
   (CAL18, la même que `PlanImporteCalage.jsx`/`ModeTerrain.jsx`) — aucune
   route neuve n'est ajoutée pour la lecture. Un document sans clé `electrical`
   (aucune tâche CALX2xx encore posée côté serveur, ou une conception jamais
   électrifiée) est traité EXACTEMENT comme une liste vide : c'est ce que
   `exemple_document_sans_electrical` du contrat exerce.

   LA POSE N'EST PAS UN GESTE DE CE PANNEAU. « Poser, déplacer, retirer » un
   équipement est le geste de CALX220 (`electrique3d.ts`, scène 3D) : ce
   panneau ARME le mode de pose et laisse la scène faire le clic. `builderApi`
   est un prop OPTIONNEL (même patron que `PanneauCalques.jsx`, CALX54) — sans
   lui, ou avant que le builder soit prêt, le bouton reste actionnable mais
   RÉPOND avec un motif nommé plutôt que d'échouer en silence :
     CROCHET ATTENDU (pas encore posé sur cette branche) :
       `apps/web/src/scripts/roofPro11/electrique3d.ts` (CALX220), exposé à
       l'hôte via `builderApi.electrique.armerPose(type)` (namespace
       `electrique` déclaré par `onApiReady` de CALX220). L'écran qui monte ce
       panneau DANS la scène 3D est celui qui doit un jour lui passer
       `builderApi` — `atelier/Rail.jsx` (CALX1, hors périmètre de cette lane)
       ne le fait pas aujourd'hui, exactement comme il ne le fait pas pour
       `PanneauCalques.jsx`.

   ZÉRO FAIT INVENTÉ (D-CALX 7). Un `type` hors des huit connus est NOMMÉ tel
   quel (`libelleType`), jamais masqué ni requalifié. `produitId` n'est JAMAIS
   résolu en désignation ici : ce document ne porte que l'identifiant, et
   aucune autre porte de ce lot ne fait le lien organe-par-organe vers une
   fiche `stock.Produit` (`calepinages.equipements()`, CAL243, sert une AUTRE
   agrégation — panneau/onduleur/batterie/optimiseur retenus par le DEVIS,
   pas les organes posés dans la scène) — afficher un nom ici serait un fait
   inventé. L'écran affiche donc la RÉFÉRENCE brute (« Fiche produit #12 »)
   quand `produitId` est renseigné, et le dit explicitement sinon.
   ========================================================================== */

/** Les huit types posables — ÉNUMÉRATION FERMÉE (électrique_equipements.json). */
export const LIBELLES_TYPE = {
  onduleur: 'Onduleur',
  coffret_dc: 'Coffret DC',
  coffret_ac: 'Coffret AC',
  compteur_production: 'Compteur de production',
  compteur_reseau: 'Compteur réseau',
  tgbt: 'TGBT',
  batterie: 'Batterie',
  parafoudre: 'Parafoudre',
}

export const TYPES_EQUIPEMENT = Object.keys(LIBELLES_TYPE)

/** Le libellé français d'un type — un type hors énumération est NOMMÉ, jamais tu. */
export function libelleType(type) {
  return LIBELLES_TYPE[type] ?? `Type inconnu : ${type}`
}

/** La RÉFÉRENCE du produit rattaché — jamais une désignation devinée. */
export function libelleProduit(produitId) {
  return produitId === null || produitId === undefined
    ? 'Aucune fiche produit rattachée'
    : `Fiche produit #${produitId}`
}

const LIBELLES_SOURCE = { saisie: 'saisie', import: 'import' }

export default function EquipementsElectriques({ calepinageId, builderApi } = {}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.layout(id), id,
    { select: (r) => r.data, errorMessage: 'Équipements électriques indisponibles.' },
  )

  const [type, setType] = useState(TYPES_EQUIPEMENT[0])
  const [motifArmement, setMotifArmement] = useState(null)

  const equipements = data?.roof_layout?.electrical?.equipements
  const liste = Array.isArray(equipements) ? equipements : []

  const armerLaPose = () => {
    const armer = builderApi?.electrique?.armerPose
    if (typeof armer !== 'function') {
      setMotifArmement(
        'Outil 3D non prêt — ouvrez la conception dans l’atelier 3D avant d’armer une pose.',
      )
      return
    }
    setMotifArmement(null)
    armer(type)
  }

  if (loading) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="equipements-electriques" />
        <Spinner />
      </>
    )
  }
  if (error) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="equipements-electriques" />
        <p className="text-sm text-destructive" data-testid="calx222-erreur">{error}</p>
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={id} cle="equipements-electriques" />
      <Card className="flex flex-col gap-4 p-4" data-testid="calx222-panneau">
        <header className="flex flex-col gap-1">
          <h2 className="text-base font-semibold">Équipements électriques</h2>
          <p className="text-sm text-muted-foreground">
            Les organes posés dans l’atelier 3D (onduleur, coffrets, compteurs,
            TGBT, batterie, parafoudre) — cet écran ne pose rien, il arme la
            scène pour que le clic pose l’organe choisi.
          </p>
        </header>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground" htmlFor="calx222-type">
              Type à poser
            </label>
            <select
              id="calx222-type"
              data-testid="calx222-type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="h-9 rounded border border-border bg-card px-2 text-sm"
            >
              {TYPES_EQUIPEMENT.map((t) => (
                <option key={t} value={t}>{libelleType(t)}</option>
              ))}
            </select>
          </div>
          <Button type="button" onClick={armerLaPose} data-testid="calx222-armer">
            Armer la pose
          </Button>
        </div>
        {motifArmement
          ? <p className="text-sm text-destructive" data-testid="calx222-armement-motif">{motifArmement}</p>
          : null}

        {liste.length === 0
          ? (
            <EmptyState
              data-testid="calx222-vide"
              icon={Zap}
              title="Aucun équipement électrique posé"
              description="Choisissez un type ci-dessus puis « Armer la pose » pour poser le premier organe dans l’atelier 3D."
            />
          )
          : (
            <ul className="flex flex-col gap-2" data-testid="calx222-liste">
              {liste.map((eq) => (
                <li
                  key={eq?.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-border px-3 py-2 text-sm"
                  data-testid={`calx222-equipement-${eq?.id}`}
                >
                  <span className="flex flex-col">
                    <span className="font-medium">{eq?.label || libelleType(eq?.type)}</span>
                    <span className="text-xs text-muted-foreground">
                      {libelleType(eq?.type)}
                      {' — '}
                      {libelleProduit(eq?.produitId)}
                    </span>
                  </span>
                  <span className="text-xs text-muted-foreground" data-testid={`calx222-source-${eq?.id}`}>
                    {LIBELLES_SOURCE[eq?.source] ?? (eq?.source || 'source inconnue')}
                  </span>
                </li>
              ))}
            </ul>
          )}
      </Card>
    </>
  )
}
