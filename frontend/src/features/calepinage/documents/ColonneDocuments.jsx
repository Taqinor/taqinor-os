import { useState } from 'react'
import { Download, Info } from 'lucide-react'
import { formaterHeureBrouillon } from '../atelier/contexteAtelier'
import { MINUTES_DE_DELAI } from './telechargement'
import ApercuDocument from './ApercuDocument'
import Vignette from './Vignettes'

/* ACAL1193 / ACAL1726 / ACAL1834 — « Documents du projet » (colonne de droite de la maquette v2 `Documents.dc.html`) :
   la COLONNE D'APERÇU du document choisi (320 px, avec « Aperçu » et « Télécharger » et la note bleue sous elle) et
   les cinq cartes (386 px) — vignette portrait, titre (qui choisit), deux lignes, pastille d'état « Prêt · PDF » ou
   « Il manque … » (celle que le serveur sert), icône de téléchargement. Cette colonne ne FAIT QUE présenter : les gestes
   (`onTelecharger`, `onApercu`, `chargerHtml`) et leurs erreurs sont ceux de `PanneauDocuments` (mêmes helpers, mêmes
   textes). Une pièce indisponible reste grisée avec son motif servi. */

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

/** L'état de la pièce, en un mot : le format quand elle est prête, ce qui manque (libellé SERVI) sinon. */
function etatDeLaCarte(carte) {
  if (carte.disponible) return { ton: 'pret', texte: `Prêt · ${String(carte.entree?.format || 'PDF').toUpperCase()}` }
  const manque = carte.entree?.manque?.[0]?.libelle
  return { ton: 'manque', texte: manque ? `Il manque : ${manque}` : 'Pas encore prête' }
}

function Carte({ carte, choisie, enCours, erreurs, onChoisir, onTelecharger }) {
  const { disponible } = carte
  const etat = etatDeLaCarte(carte)
  return (
    <article data-testid="cal-docs-carte" data-document={carte.cle} data-disponible={disponible ? 'oui' : 'non'}
      data-choisie={choisie ? 'oui' : 'non'} className="cdoc-carte">
      <Vignette nom={carte.vignette} />
      <div className="cdoc-carte-texte">
        <button type="button" className="cdoc-carte-titre" aria-pressed={choisie} onClick={() => onChoisir(carte.cle)}>
          {carte.titre}
        </button>
        <p className="cdoc-carte-description">{carte.description}</p>
        <span className="cdoc-pastille" data-ton={etat.ton} data-testid={`cal-docs-pastille-${carte.cle}`}>
          <span className="cdoc-pastille-point" aria-hidden="true" />{etat.texte}
        </span>
        {!disponible && carte.motif ? (
          <p className="cdoc-carte-motif" data-testid={`cal-docs-motif-${carte.cle}`}>{carte.motif}</p>
        ) : null}
        {enCours && carte.entree?.methode !== 'POST' ? (
          <p className="cdoc-carte-motif" role="status" data-testid="cal-docs-attente">
            {`Préparation en cours : jusqu'à ${MINUTES_DE_DELAI} minutes.`}
          </p>
        ) : null}
        <Erreurs erreurs={erreurs} />
      </div>
      <button type="button" className="cdoc-icone" disabled={!disponible || enCours} aria-busy={enCours || undefined}
        aria-label={`Télécharger : ${carte.titre}`} title="Télécharger"
        data-testid={`cal-docs-telecharger-${carte.cle}`} onClick={() => onTelecharger(carte)}>
        <Download size={20} aria-hidden="true" />
      </button>
    </article>
  )
}

export default function ColonneDocuments({
  cartes, enregistreLe = null, enCoursDe, erreursDe, onTelecharger, onApercu, chargerHtml = null,
}) {
  const heure = enregistreLe ? formaterHeureBrouillon(enregistreLe) : ''
  // La pièce choisie : la première qui est prête (sinon la première), tant que l'on n'en a pas choisi une autre.
  const [cleChoisie, setCleChoisie] = useState(null)
  const choisie = cartes.find((c) => c.cle === cleChoisie) ?? cartes.find((c) => c.disponible) ?? cartes[0] ?? null
  const note = (
    <div className="cdoc-info" data-testid="cal-docs-info-devis">
      <Info size={18} aria-hidden="true" />
      <span>
        Le devis remis au client ne se fait pas ici : il est créé à partir du devis, avec ses prix.
        {' « Générer le devis » prépare ce devis avec ce calepinage.'}
      </span>
    </div>
  )
  return (
    <section data-testid="cal-docs-liste" aria-labelledby="cdoc-docs-titre" className="cdoc-docs">
      <div className="cdoc-docs-tete">
        <h2 id="cdoc-docs-titre" className="cdoc-titre">Documents du projet</h2>
        {heure ? <span className="cdoc-sous">{`Faits à partir de la version enregistrée à ${heure}.`}</span> : null}
      </div>
      {cartes.length === 0 ? (
        <>
          <p className="cdoc-sous" data-testid="cal-docs-vide">Aucun document disponible pour l’instant.</p>
          {note}
        </>
      ) : (
        <div className="cdoc-docs-corps">
          <ApercuDocument key={choisie.cle} carte={choisie} enCours={enCoursDe(choisie)} onApercu={onApercu}
            onTelecharger={onTelecharger} chargerHtml={chargerHtml} note={note} />
          <div className="cdoc-cartes">
            {cartes.map((carte) => (
              <Carte key={carte.cle} carte={carte} choisie={carte.cle === choisie.cle} enCours={enCoursDe(carte)}
                erreurs={erreursDe(carte)} onChoisir={setCleChoisie} onTelecharger={onTelecharger} />
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
