import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import calepinageApi from '../../../../../api/calepinageApi'
import useResource from '../../../../../hooks/useResource'
import { renderTrustedSvg } from '../../../../../lib/trustedSvg'
import { Spinner } from '../../../../../ui'
import { downloadBlob } from '../../../../../utils/downloadBlob'
import { OPTIONS_TELECHARGEMENT, erreurDeTelechargement } from '../../../documents/telechargement'
import { phraseRaccordement } from '../../../electrique/resumeRaccordement'
import { MotifsSchema, PlancheSchema, SchemaEnBlocs } from '../../../SchemaUnifilairePanel'
import {
  lignesCartouche, lignesLegende, motifDuRefusDxf, nomFichierSchema, phraseCoteReseau, planDepuisDocument, planSchemaEnBlocs,
} from '../../../SchemaUnifilairePanel.helpers'
import { PARAM_ONGLET } from '../../onglets'
import { PARAM_CHAMP } from '../../ouvrirChamp'
import { DansPanneau, PiedEtape } from '../emplacements'
import { BoutonOr, Icone } from '../primitives'

/* ============================================================================
   ACAL1301 — LE SOUS-ÉCRAN « SCHÉMA ÉLECTRIQUE » (maquette `Schema.dc.html`, cadre `plein-panneau`).
   ----------------------------------------------------------------------------
   Au centre (F3, tour 2) : le schéma EN BLOCS de la maquette, composé à l'échelle 1 depuis les
   données SERVIES (`planSchemaEnBlocs` : blocs de `schema-unifilaire/`, chaînes et tronçons de
   `resultat/`) ; chaque élément ouvre la section de l'étape Électrique où sa valeur se règle.
   « Schéma détaillé » bascule sur le schéma unifilaire SERVI (le même SVG que l'onglet expert, celui
   que livrent PDF et DXF), entier, avec zoom ± et déplacement. À droite : « Légende » (les signes que CE dessin emploie),
   « Cartouche » (Projet / Date / Version / Auteur servis par le détail ; une ligne sans donnée est
   omise), la note bleue ; au pied (ACAL1508) : « Télécharger (PDF) » = le schéma unifilaire dessiné
   (`sldPdf`, `schema-unifilaire.pdf/`) et « DXF » = le même schéma (`sldDxf`) — jamais le plan de câblage, qui
   reste une pièce à part de l'étape Documents ; mêmes délais, refus du serveur dits tels quels. L'édition
   des libellés et les exports PNG/SVG restent dans l'onglet expert (`?mode=expert&onglet=schema`).
   ========================================================================== */

const TRAITS = { plein: 'csch-trait', chaine: 'csch-trait', batterie: 'csch-trait csch-trait-batterie', pointille: 'csch-trait csch-trait-pointille' }

function Legende({ lignes }) {
  return (
    <section className="cel-section" data-testid="cal-schema-legende">
      <h2>Légende</h2>
      <ul className="csch-legende">
        {lignes.map((l) => (
          <li key={l.cle}>
            {l.trait === 'mm2'
              ? <span className="csch-mm2" aria-hidden="true">mm²</span>
              /* La couleur d'une chaîne est SERVIE (`couleur_chaine`) : la même que la carte de l'étape Électrique. */
              : <span className={TRAITS[l.trait]} aria-hidden="true" style={l.couleur ? { background: l.couleur } : undefined} />}
            <span>{l.libelle}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Cartouche({ lignes }) {
  return (
    <section className="cel-section" data-testid="cal-schema-cartouche">
      <h2>Cartouche</h2>
      <dl className="csch-cartouche">
        {lignes.map((l) => (
          <div key={l.libelle}>
            <dt>{l.libelle}</dt>
            <dd>{l.valeur}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

/** Les deux téléchargements du pied : le schéma unifilaire dessiné, en PDF A3 et en DXF (ACAL1508). */
function Telechargements({ id, schemaServi, reference }) {
  const [enCours, setEnCours] = useState(null)
  const [erreurs, setErreurs] = useState(null)
  const telecharger = (cle, extension, appel, motifDuRefus) => {
    setErreurs(null)
    setEnCours(cle)
    appel(id, OPTIONS_TELECHARGEMENT)
      .then((reponse) => downloadBlob(reponse.data, nomFichierSchema(reference, extension)))
      .catch(async (err) => setErreurs(await motifDuRefus(err)))
      .finally(() => setEnCours(null))
  }
  const motifPdf = async (err) => (await erreurDeTelechargement(err, { delai: true })).map((d) => d.message)
  const motifDxf = async (err) => [await motifDuRefusDxf(err)]
  return (
    <div className="csch-pied">
      {erreurs && (
        <div role="alert" className="csch-pied-messages">
          {erreurs.map((m) => <p key={m}>{m}</p>)}
        </div>
      )}
      <div className="csch-pied-boutons">
        <BoutonOr plein disabled={!schemaServi || enCours !== null}
          onClick={() => telecharger('pdf', 'pdf', calepinageApi.calepinages.sldPdf, motifPdf)}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>
          {enCours === 'pdf' ? 'Préparation…' : 'Télécharger (PDF)'}
        </BoutonOr>
        <button type="button" className="csch-dxf" disabled={!schemaServi || enCours !== null}
          onClick={() => telecharger('dxf', 'dxf', calepinageApi.calepinages.sldDxf, motifDxf)}>
          {enCours === 'dxf' ? '…' : 'DXF'}
        </button>
      </div>
    </div>
  )
}

export default function EtapeSchema({ calepinageId: id }) {
  const [parametres, setParametres] = useSearchParams()
  const { data: schema, loading, error } = useResource((p) => calepinageApi.calepinages.schemaUnifilaire(p), id,
    { select: (r) => r?.data ?? null, errorMessage: 'Schéma unifilaire indisponible.' })
  const { data: detail } = useResource((p) => calepinageApi.calepinages.get(p), id, { select: (r) => r?.data ?? null })
  const { data: resultat } = useResource((p) => calepinageApi.calepinages.resultat(p), id, { select: (r) => r?.data ?? null })

  const [detaille, setDetaille] = useState(false)
  const balisage = renderTrustedSvg(schema?.svg)
  // F3 — le schéma EN BLOCS (maquette) à partir des données servies ; le SVG détaillé du serveur
  // reste consultable (« Schéma détaillé ») et c'est lui que livrent PDF et DXF.
  // LOT 6 — le document structuré `schema_electrique` (chaînes, batterie, côté réseau) quand le serveur le
  // sert ; sinon (serveur plus ancien) le plan composé des deux réponses, comme avant.
  const doc = schema?.schema_electrique ?? null
  const plan = planDepuisDocument(doc, schema?.edition?.libelles) ?? (balisage ? planSchemaEnBlocs(schema, resultat) : null)
  const motifCoteReseau = doc?.cote_reseau?.etat === 'a_calculer' ? doc.cote_reseau.motif : null
  const enBlocs = Boolean(plan) && !detaille
  const legende = enBlocs ? plan.legende : (balisage ? lignesLegende(schema.svg) : [])
  const cartouche = lignesCartouche(detail)
  const ouvrirOnglet = (onglet) => {
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, onglet)
    suivants.delete(PARAM_CHAMP)
    setParametres(suivants)
  }

  return (
    <div className="csch-ecran" data-testid="csch-ecran">
      <PlancheSchema balisage={balisage} note={balisage ? phraseRaccordement(resultat) : null}
        dessin={enBlocs ? <SchemaEnBlocs plan={plan} onOuvrir={ouvrirOnglet}
          coteReseau={{ texte: motifCoteReseau ?? phraseCoteReseau(resultat), onOuvrir: resultat?.simule === true ? null : () => ouvrirOnglet('production') }} /> : null}
        actions={(
          <>
            {plan && (
              <button type="button" className="csch-retour" aria-pressed={detaille} data-testid="csch-detaille"
                onClick={() => setDetaille((d) => !d)}>
                {detaille ? 'Schéma en blocs' : 'Schéma détaillé'}
              </button>
            )}
            {/* l'onglet qui ouvre l'étape Électrique */}
            <button type="button" className="csch-retour" onClick={() => ouvrirOnglet('verdict-electrique')}>
              <Icone nom="retour" taille={18} epaisseur={2} />
              Raccordement
            </button>
          </>
        )}>
        {loading && <Spinner />}
        {!loading && error && <p role="alert" className="cel-refus">{error}</p>}
        {!loading && !error && <MotifsSchema donnees={schema} />}
      </PlancheSchema>
      <DansPanneau>
        {legende.length > 0 && <Legende lignes={legende} />}
        {cartouche.length > 0 && <Cartouche lignes={cartouche} />}
        <section className="csch-info">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.5" /></svg>
          <span>
            {enBlocs
              ? 'Le schéma se redessine quand le raccordement change. Cliquez sur un élément pour voir d’où vient sa valeur.'
              : 'Le schéma se redessine quand le raccordement change.'}
          </span>
        </section>
      </DansPanneau>
      <PiedEtape>
        <Telechargements id={id} schemaServi={Boolean(balisage)} reference={schema?.calepinage} />
      </PiedEtape>
    </div>
  )
}
