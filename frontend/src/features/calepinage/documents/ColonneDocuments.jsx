import { Download, Info } from 'lucide-react'
import { formaterHeureBrouillon } from '../atelier/contexteAtelier'
import { MINUTES_DE_DELAI } from './telechargement'
import Vignette from './Vignettes'

/* ACAL1193 — « Documents du projet » (colonne de droite de la maquette `Documents.dc.html`) : cinq
   cartes — vignette, titre, deux lignes, « Aperçu » et « Télécharger ». Cette colonne ne fait QUE
   présenter : les gestes (`onTelecharger`, `onApercu`) et leurs erreurs sont ceux de
   `PanneauDocuments` (mêmes helpers, mêmes textes). Une pièce indisponible reste grisée avec son motif servi. */

function Erreurs({ erreurs }) {
  if (!erreurs?.length) return null
  return (
    <ul role="alert" className="cdoc-erreurs" data-testid="cal-docs-erreurs">
      {erreurs.map((e) => (
        <li key={`${e.champ}-${e.message}`}>{e.champ ? <strong>{`${e.champ} — `}</strong> : null}{e.message}</li>
      ))}
    </ul>
  )
}

function Carte({ carte, enCours, erreurs, onTelecharger, onApercu }) {
  const { entree, disponible } = carte
  return (
    <article data-testid="cal-docs-carte" data-document={carte.cle} data-disponible={disponible ? 'oui' : 'non'}
      className="cdoc-carte">
      <Vignette nom={carte.vignette} />
      <div className="cdoc-carte-texte">
        <h3 className="cdoc-carte-titre">{carte.titre}</h3>
        <p className="cdoc-carte-description">{carte.description}</p>
        {!disponible && carte.motif ? (
          <p className="cdoc-carte-motif" data-testid={`cal-docs-motif-${carte.cle}`}>{carte.motif}</p>
        ) : null}
        {enCours && entree.methode !== 'POST' ? (
          <p className="cdoc-carte-motif" role="status" data-testid="cal-docs-attente">
            {`Préparation en cours : jusqu'à ${MINUTES_DE_DELAI} minutes.`}
          </p>
        ) : null}
        <Erreurs erreurs={erreurs} />
      </div>
      {carte.apercu ? (
        <button type="button" className="cdoc-bouton" disabled={!disponible}
          data-testid={`cal-docs-apercu-${carte.cle}`} onClick={() => onApercu(carte)}>
          Aperçu
        </button>
      ) : null}
      <button type="button" className="cdoc-bouton" disabled={!disponible || enCours} aria-busy={enCours || undefined}
        data-testid={`cal-docs-telecharger-${carte.cle}`} onClick={() => onTelecharger(carte)}>
        <Download size={16} aria-hidden="true" />Télécharger
      </button>
    </article>
  )
}

export default function ColonneDocuments({
  cartes, enregistreLe = null, enCoursDe, erreursDe, onTelecharger, onApercu,
}) {
  const heure = enregistreLe ? formaterHeureBrouillon(enregistreLe) : ''
  return (
    <section data-testid="cal-docs-liste" aria-labelledby="cdoc-docs-titre" className="cdoc-docs">
      <div className="cdoc-docs-tete">
        <h2 id="cdoc-docs-titre" className="cdoc-titre">Documents du projet</h2>
        {heure ? <span className="cdoc-sous">{`Faits à partir de la version enregistrée à ${heure}.`}</span> : null}
      </div>
      {cartes.length === 0 ? (
        <p className="cdoc-sous" data-testid="cal-docs-vide">Aucun document disponible pour l’instant.</p>
      ) : cartes.map((carte) => (
        <Carte key={carte.cle} carte={carte} enCours={enCoursDe(carte)} erreurs={erreursDe(carte)}
          onTelecharger={onTelecharger} onApercu={onApercu} />
      ))}
      <div className="cdoc-info" data-testid="cal-docs-info-devis">
        <Info size={18} aria-hidden="true" />
        <span>
          Le devis remis au client ne se fait pas ici : il est créé à partir du devis, avec ses prix.
          {' « Générer le devis » prépare ce devis avec ce calepinage.'}
        </span>
      </div>
    </section>
  )
}
