/* eslint-disable react-refresh/only-export-components --
   `nomFichierSchema`/`exporterSchemaPng`/`exporterSchemaSvg` sont des
   fonctions PURES (aucun état, aucun React) que le test unitaire de CALX236
   doit pouvoir appeler/mocker sans monter le panneau. Les sortir dans un
   `.js` voisin séparerait l'export de son unique lecteur pour satisfaire une
   règle de fast-refresh qui ne s'applique pas à une fonction pure — même
   dérogation que `AffectationChaines.jsx`/`PanneauMasseLestage.jsx`. */
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import useResource from '../../hooks/useResource'
import { renderTrustedSvg } from '../../lib/trustedSvg'
import { Button, Card, Spinner } from '../../ui'
import RetourAtelier from './atelier/RetourAtelier'
import { telechargerBlob } from './exportImage'

/* ============================================================================
   CAL195 — LE SCHÉMA UNIFILAIRE, DANS LE MODULE.
   ----------------------------------------------------------------------------
   Le schéma existait déjà — mais seulement à l'intérieur du PDF de devis. Un
   calepinage sans devis n'en avait aucun, et personne ne pouvait le regarder
   avant d'avoir chiffré.

   CE PANNEAU NE DESSINE RIEN. Le SVG est composé PAR LE SERVEUR (le MÊME
   moteur `core.electrique` que le devis, à travers la porte
   `apps.ventes.selectors.schema_unifilaire_svg`) : deux surfaces ne peuvent
   donc pas montrer deux schémas qui se contredisent. L'écran l'insère tel
   quel et n'ajoute pas un trait.

   FICHE INCOMPLÈTE ⇒ PAS DE SCHÉMA, et on le DIT. `svg: null` n'est jamais
   affiché comme un cadre vide : les libellés français du serveur
   (`manquantes`, `bloquants`) sont rendus TELS QUELS — l'écran ne reformule
   aucun motif et n'en invente aucun. Même discipline que PVFCH-ANNEXE côté
   devis : un schéma d'aspect officiel bâti sur des caractéristiques devinées
   est un défaut invisible.

   CALX236 — EXPORTER LE SCHÉMA, DEPUIS LE NAVIGATEUR, JAMAIS DEPUIS LE
   SERVEUR (D1 : aucun rastériseur SVG côté serveur). Le SVG est DÉJÀ dans le
   DOM (inséré ci-dessus) : l'export PNG le sérialise dans un canvas hors
   écran (même patron que `features/ged/capture.js`) et télécharge l'image —
   AUCUN second appel à `schemaUnifilaire()`, aucune route neuve. Le lien SVG
   télécharge le TEXTE déjà reçu, tel quel. Les deux boutons n'existent QUE
   quand `balisage` est vrai (`svg` non nul) : un schéma absent n'a rien à
   exporter.

   CE QUI N'EST PAS FAIT ICI — ET POURQUOI. La tâche demande aussi un lien
   vers le DXF de CALX235 (`services/sld_export.py::exporter_sld_dxf`) :
   cette route n'existe PAS ENCORE côté serveur au moment où cette lane est
   écrite (CALX235 est une lane différente, non postée sur cette branche) et
   la discipline PACT10/D-CALX 13 de ce lot interdit d'ajouter à
   `calepinageApi.js` un appel vers une route absente — le lien DXF est donc
   OMIS, pas deviné. CROCHET ATTENDU : `calepinageApi.calepinages.sldDxf(id)`,
   à ajouter EN FIN de `calepinageApi.js` avec `// CALX235` le jour où cette
   route existe (l'`url_path` exact sera celui que CALX235 posera dans
   `views/schema.py`) — puis un troisième bouton ici, sur le même modèle que
   les deux ci-dessous.
   ========================================================================== */

/** Le nom du fichier exporté : porte la RÉFÉRENCE du calepinage servie par
    CETTE réponse (`data.calepinage`, le seul identifiant que ce contrat
    publie — aucun titre n'y est servi, donc aucun titre n'est inventé ici). */
export function nomFichierSchema(referenceCalepinage, extension) {
  const base = referenceCalepinage === null || referenceCalepinage === undefined
    ? 'calepinage'
    : `calepinage-${referenceCalepinage}`
  return `${base}-schema-unifilaire.${extension}`
}

/**
 * Sérialise le SVG (déjà reçu, déjà affiché) dans un canvas hors écran et
 * télécharge le PNG obtenu. Aucun appel réseau : Blob/URL.createObjectURL
 * sont locaux au navigateur. Un échec de rastérisation (navigateur trop
 * ancien, contexte 2D indisponible) revient en REJET avec un motif
 * affichable — jamais une exception qui casserait l'écran.
 */
export function exporterSchemaPng(svgTexte, nomFichier, { telecharger = telechargerBlob } = {}) {
  return new Promise((resolve, reject) => {
    let url
    try {
      url = URL.createObjectURL(new Blob([svgTexte], { type: 'image/svg+xml;charset=utf-8' }))
    } catch (err) {
      reject(err)
      return
    }
    const img = new Image()
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = img.width || 1
        canvas.height = img.height || 1
        const ctx = canvas.getContext('2d')
        if (!ctx) throw new Error('Contexte de dessin 2D indisponible sur ce navigateur.')
        ctx.drawImage(img, 0, 0)
        canvas.toBlob((blobPng) => {
          URL.revokeObjectURL(url)
          if (!blobPng) { reject(new Error('Rendu PNG indisponible sur ce navigateur.')); return }
          telecharger(blobPng, nomFichier)
          resolve({ ok: true, nom: nomFichier })
        }, 'image/png')
      } catch (err) {
        URL.revokeObjectURL(url)
        reject(err)
      }
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Le schéma n’a pas pu être rastérisé sur ce navigateur.'))
    }
    img.src = url
  })
}

/** Télécharge le SVG texte tel quel — aucune conversion, aucun appel réseau. */
export function exporterSchemaSvg(svgTexte, nomFichier, { telecharger = telechargerBlob } = {}) {
  telecharger(new Blob([svgTexte], { type: 'image/svg+xml;charset=utf-8' }), nomFichier)
}

const LISTES = [
  { cle: 'manquantes', titre: 'Fiche technique incomplète' },
  { cle: 'bloquants', titre: 'Conception non conforme' },
]

function Motifs({ donnees }) {
  const blocs = LISTES
    .map(({ cle, titre }) => ({ titre, cle, lignes: donnees?.[cle] || [] }))
    .filter((bloc) => bloc.lignes.length > 0)
  if (!blocs.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal195-sans-motif">
        Aucun schéma pour cette conception.
      </p>
    )
  }
  return blocs.map((bloc) => (
    <div key={bloc.cle} className="flex flex-col gap-1" data-testid={`cal195-${bloc.cle}`}>
      <div className="flex items-center gap-2 text-sm font-medium">
        <AlertCircle size={15} aria-hidden="true" />
        {bloc.titre}
      </div>
      <ul className="list-disc pl-5 text-sm text-muted-foreground">
        {bloc.lignes.map((ligne) => <li key={ligne}>{ligne}</li>)}
      </ul>
    </div>
  ))
}

export default function SchemaUnifilairePanel({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.schemaUnifilaire(id), id,
    { select: (r) => r.data, errorMessage: 'Schéma unifilaire indisponible.' },
  )

  const balisage = renderTrustedSvg(data?.svg)
  const [motifExport, setMotifExport] = useState(null)

  // CALX236 — le clic sérialise le SVG déjà reçu (`data.svg`) : aucun second
  // appel à `schemaUnifilaire()`, aucune route neuve.
  const exporterPng = () => {
    setMotifExport(null)
    exporterSchemaPng(data.svg, nomFichierSchema(data?.calepinage, 'png'))
      .catch((err) => setMotifExport(err?.message || 'Export PNG impossible sur ce navigateur.'))
  }
  const telechargerSvg = () => {
    exporterSchemaSvg(data.svg, nomFichierSchema(data?.calepinage, 'svg'))
  }

  if (loading) {
    return (
      <>
        <RetourAtelier calepinageId={id} />
        <Spinner />
      </>
    )
  }
  if (error) {
    return (
      <>
        <RetourAtelier calepinageId={id} />
        <p className="text-sm text-destructive" data-testid="cal195-erreur">{error}</p>
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={id} />
      <Card className="flex flex-col gap-3 p-4" data-testid="cal195-panneau">
      <h2 className="text-base font-semibold">Schéma unifilaire</h2>
      {balisage
        ? (
          <>
            <div
              data-testid="cal195-svg"
              /* Le SVG vient du serveur, jamais d'une saisie. Il passe malgré
                 tout par `renderTrustedSvg` (VX120, défense en profondeur) :
                 un balisage capable d'exécuter du code n'est PAS inséré — on
                 montre alors les motifs plutôt qu'un cadre piégé. */
              dangerouslySetInnerHTML={balisage}
            />
            {/* CALX236 — les boutons n'existent QUE quand un schéma est
                affiché : `svg` nul n'a rien à exporter. */}
            <div className="flex flex-wrap gap-2" data-testid="calx236-export">
              <Button type="button" onClick={exporterPng} data-testid="calx236-exporter-png">
                Exporter en PNG
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={telechargerSvg}
                data-testid="calx236-telecharger-svg"
              >
                Télécharger le SVG
              </Button>
            </div>
            {motifExport
              ? <p className="text-sm text-destructive" data-testid="calx236-erreur-export">{motifExport}</p>
              : null}
          </>
        )
        : <Motifs donnees={data} />}
    </Card>
    </>
  )
}
