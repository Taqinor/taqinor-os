import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useDocumentCalepinage from '../useDocumentCalepinage'
import { libellePan, planDessus, tuilesClient } from './vueClient.helpers'
import '../../../styles/calepinage/58-telephone.css'

/* ============================================================================
   « MONTRER AU CLIENT » AU TÉLÉPHONE (`/calepinage/:id/client`, maquette TelephoneClient).
   ----------------------------------------------------------------------------
   CE QUI EST MONTRÉ : le toit ENREGISTRÉ et ses panneaux, dessinés depuis le document
   (`roof_layout` : pans + modules par `modulesDuDocument`, le même habillage que la page
   photo) — une vue DE DESSUS, dite telle. Le produit n'a aujourd'hui aucune vue 3D
   autonome d'un calepinage enregistré : la 3D est celle du constructeur de l'atelier,
   qui exige toute sa page ; le lien « Voir la 3D dans l'atelier » y mène. Sans ce
   constructeur, le lecteur du soleil (Hiver / Été) n'a rien à piloter : il est omis.
   CHIFFRES : document enregistré + résultat publié seulement ; jamais un montant.
   PARTAGE : le lien client est celui de la proposition du DEVIS, préparé depuis la fiche
   du lead (niveau et sections choisis là, L-SECT) — le bouton dit pourquoi il est
   désactivé ici ; aucune porte publique neuve.
   ========================================================================== */

const RAISON_LIEN = 'Le lien se prépare depuis la fiche du lead, onglet Devis, « Envoyer au client » : '
  + 'le niveau et les sections du devis s’y choisissent.'

function PlanDessus({ plan }) {
  const marge = 2
  const larg = plan.maxX - plan.minX + 2 * marge
  const haut = plan.maxY - plan.minY + 2 * marge
  const pt = (p) => `${(p.x - plan.minX + marge).toFixed(2)},${(plan.maxY - p.y + marge).toFixed(2)}`
  return (
    <svg className="cal-client-plan" viewBox={`0 0 ${larg.toFixed(2)} ${haut.toFixed(2)}`}
      preserveAspectRatio="xMidYMid meet" role="img" data-testid="client-plan"
      aria-label={`Le toit vu de dessus : ${plan.pans.length} pan${plan.pans.length > 1 ? 's' : ''}, ${plan.modules.length} panneau${plan.modules.length > 1 ? 'x' : ''} dessiné${plan.modules.length > 1 ? 's' : ''}`}>
      {plan.pans.map((pan, i) => <polygon key={`p${i}`} className="cal-client-pan" points={pan.map(pt).join(' ')} />)}
      {plan.modules.map((q, i) => <polygon key={`m${i}`} className="cal-client-module" points={q.map(pt).join(' ')} />)}
    </svg>
  )
}

export default function VueClient() {
  const { id } = useParams()
  const doc = useDocumentCalepinage(id)
  const [contexte, setContexte] = useState(null)
  const [resultat, setResultat] = useState(null)

  useEffect(() => {
    if (!id) return undefined
    let vivant = true
    Promise.resolve(calepinageApi.calepinages.designContext?.(id))
      .then((res) => { if (vivant) setContexte(res?.data ?? null) }).catch(() => {})
    Promise.resolve(calepinageApi.calepinages.resultat?.(id))
      .then((res) => { if (vivant) setResultat(res?.data ?? null) }).catch(() => {})
    return () => { vivant = false }
  }, [id])

  const plan = doc.etat === 'ok' ? planDessus(doc.document) : null
  const tuiles = doc.etat === 'ok' ? tuilesClient(doc.document, resultat) : []
  const titre = (contexte?.calepinage?.titre ?? '').trim()
  const ville = (contexte?.calepinage?.client_ville ?? '').trim()
  const pan = doc.etat === 'ok' ? libellePan(doc.document) : ''
  const sousTitre = [ville, pan].filter(Boolean).join(' · ')
  const aKwh = tuiles.some((t) => t.cle === 'kwh')

  return (
    <div className="cal-tel" data-testid="cal-vue-client">
      <div className="cal-client-scene" data-testid="client-scene">
        {plan ? <PlanDessus plan={plan} /> : (
          <p className="cal-client-vide" data-testid="client-sans-toit">
            {doc.etat === 'chargement' ? 'Lecture du toit enregistré…' : 'Aucun toit enregistré pour ce calepinage.'}
          </p>
        )}
        {(titre || sousTitre) && (
          <div className="cal-client-puce" data-testid="client-projet">
            {titre && <span className="cal-client-puce-titre">{titre}</span>}
            {sousTitre && <span className="cal-client-puce-ligne">{sousTitre}</span>}
          </div>
        )}
        <Link to={`/calepinage/${id}`} className="cal-client-pastille" data-testid="client-voir-3d">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 11-3-6.7" /><path d="M21 4v5h-5" /></svg>
          Vue de dessus · voir la 3D dans l’atelier
        </Link>
      </div>

      <div className="cal-client-corps">
        {tuiles.length > 0 && (
          <div className={`cal-client-tuiles cal-client-tuiles-${tuiles.length}`} data-testid="client-tuiles">
            {tuiles.map((t) => (
              <div key={t.cle} className={t.marine ? 'cal-client-tuile cal-client-tuile-marine' : 'cal-client-tuile'}
                data-testid={`client-tuile-${t.cle}`}>
                <span className="cal-client-tuile-valeur">{t.valeur}</span>
                <span className="cal-client-tuile-libelle">{t.libelle}</span>
              </div>
            ))}
          </div>
        )}
        {aKwh && (
          <span className="cal-client-mention">
            {`Estimation pour une année moyenne${ville ? ` à ${ville}` : ''}. Les montants figurent dans le devis.`}
          </span>
        )}
        <p id="client-lien-raison" className="cal-client-mention" data-testid="client-lien-raison">{RAISON_LIEN}</p>
      </div>

      <footer className="cal-tel-pied">
        <Link to={`/calepinage/${id}/releve`} className="cal-tel-pied-secondaire" data-testid="client-retour-releve">Retour au relevé</Link>
        <button type="button" className="cal-tel-pied-or" disabled aria-describedby="client-lien-raison"
          data-testid="client-envoyer-lien">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
            <path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" />
          </svg>
          Envoyer le lien
        </button>
      </footer>
    </div>
  )
}
