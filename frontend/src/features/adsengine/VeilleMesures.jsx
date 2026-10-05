import { useEffect, useState } from 'react'
import adsengineApi from './adsengineApi'
import { nomPays } from './VeilleLibelles'
import { formatNumber } from '../../lib/format'

/* ============================================================================
   VEIL33 — Panneau « Mesures » d'une découverte (contrat veille_mesures.json).
   ----------------------------------------------------------------------------
   Toute valeur `null` est affichée « non mesurable » avec son motif — JAMAIS
   « 0 » (« calculé et nul » ≠ « non calculable »). Les parts sont des
   fractions 0..1 servies par le serveur ; l'écran ne calcule rien.
   ========================================================================== */

const NON_MESURABLE = 'non mesurable'
const nombre = (v) => (v === null || v === undefined ? NON_MESURABLE : String(v).replace('.', ','))
const part = (v) => (v === null || v === undefined
  ? NON_MESURABLE
  : `${formatNumber(Math.round(v * 1000) / 10)} %`)

function Valeur({ testid, texte, motif }) {
  return (
    <span data-testid={testid}>
      {texte}
      {texte === NON_MESURABLE && motif && <em className="text-muted small"> — {motif}</em>}
    </span>
  )
}

export default function VeilleMesures({ decouverteId = null }) {
  const [mesures, setMesures] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    if (!decouverteId) return
    adsengineApi.veille.mesures(decouverteId)
      .then(r => { setMesures(r.data); setErreur('') })
      .catch(() => setErreur('Mesures illisibles pour le moment.'))
  }, [decouverteId])

  if (!decouverteId) return <p data-testid="ae-veille-mesures-vide">Choisir d&apos;abord une découverte.</p>
  if (erreur) return <p className="text-danger" data-testid="ae-veille-mesures-erreur">{erreur}</p>
  if (!mesures) return <p>Chargement…</p>

  const m = mesures
  const ppa = m.pubs_par_appel || {}
  const rappel = m.rappel_concurrents_nommes || {}
  const doublons = m.doublons || {}
  return (
    <div data-testid="ae-veille-mesures">
      <h2 className="h6">Annonceurs distincts : {m.annonceurs_distincts?.total}</h2>
      <ul className="small" data-testid="ae-veille-mesures-par-mot-cle">
        {(m.annonceurs_distincts?.par_mot_cle || []).map(x => (
          <li key={x.mot_cle}>{x.mot_cle} : {x.valeur}</li>
        ))}
        {(m.annonceurs_distincts?.par_pays || []).map(x => (
          <li key={x.pays}>{nomPays(x.pays)} : {x.valeur}</li>
        ))}
      </ul>
      <p className="small">
        Pubs par appel : moyenne <Valeur testid="ae-veille-mesures-ppa-moyenne" texte={nombre(ppa.moyenne)} motif={ppa.motif_fr} />,
        {' '}médiane {nombre(ppa.mediane)}, min {nombre(ppa.min)}, max {nombre(ppa.max)}
      </p>
      <ul className="small" data-testid="ae-veille-mesures-appels">
        {(m.appels_par_mot_cle || []).map(x => <li key={x.mot_cle}>{x.mot_cle} : {x.appels} appel(s)</li>)}
      </ul>
      <p className="small" data-testid="ae-veille-mesures-saturation">
        Saturation (nouvelles Pages cumulées par page) :{' '}
        {(m.saturation?.global || []).map(p => `p${p.page} → ${p.nouveaux_page_id_cumules}`).join(' · ')}
      </p>
      <p className="small">
        Rappel sur les concurrents nommés :{' '}
        <Valeur
          testid="ae-veille-mesures-rappel"
          texte={rappel.trouves === null || rappel.trouves === undefined
            ? NON_MESURABLE : `${rappel.trouves} / ${rappel.total}`}
          motif={rappel.motif_fr} />
        {(rappel.absents || []).length > 0 && ` — absents : ${rappel.absents.join(', ')}`}
      </p>
      <p className="small">
        Doublons : recouvrement entre requêtes{' '}
        <Valeur testid="ae-veille-mesures-recouvrement" texte={part(doublons.recouvrement_entre_requetes)} motif={doublons.motif_fr} />,
        {' '}annonceurs multi-pays {nombre(doublons.annonceurs_multi_pays)},
        {' '}domaines partagés {nombre(doublons.domaines_partages)}
      </p>
      <p className="small">
        Domaine affiché renseigné :{' '}
        <Valeur
          testid="ae-veille-mesures-domaine" texte={part(m.taux_remplissage_domaine?.valeur)}
          motif={m.taux_remplissage_domaine?.motif_fr} />
      </p>
      <p className="small">
        Pubs actives depuis 5 jours ou plus :{' '}
        <Valeur testid="ae-veille-mesures-actives" texte={part(m.part_pubs_actives_5_jours)} />
      </p>
      <ul className="small" data-testid="ae-veille-mesures-classes">
        {(m.part_par_classe || []).map(x => <li key={x.classe}>{x.classe} : {part(x.part)}</li>)}
      </ul>
      <p className="small">
        Part de dropshippers :{' '}
        <Valeur
          testid="ae-veille-mesures-dropshipper" texte={part(m.part_dropshipper?.valeur)}
          motif={m.part_dropshipper?.motif_fr} />
      </p>
    </div>
  )
}
