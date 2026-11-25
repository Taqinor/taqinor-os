// AGEN12 (D-ACAL-97, réponse Q2 du fondateur 23/11/2026, contrôle C4-E4) — LE
// BANDEAU « La conception a changé » de l'écran devis.
//
// Un brouillon RETOUCHÉ à la main garde ses valeurs quand la conception du lead
// bouge (voulu) : le serveur le liste dans `brouillons_a_mettre_a_jour` de la
// conception servie (`GET conception/<lead>/`). Le bandeau le DIT et propose
// « Mettre à jour » (`POST devis/<id>/mettre-a-jour-conception/`, ADEV148), puis
// dit ce qui a été appliqué et ce qui ne l'a pas été (les quantités tapées sont
// gardées). Un devis envoyé dont la conception a bougé propose « Réviser le
// devis » (geste existant). Un brouillon intact : aucun bandeau. Aucun calcul :
// des lectures de la conception servie (contrat `conception_lead.json`).
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ventesApi from '../../../api/ventesApi'
import { Button } from '../../../ui'
import { comptePanneauxOption } from '../../../features/ventes/solar'
import { reviserEtOuvrir } from '../../../features/ventes/reviserDevis'

const PARTIS = ['envoye', 'accepte']

/** « panneaux 40 → 48 » quand le compte du devis diffère de la conception, sinon ''. */
function ecartPanneaux(devis, conception) {
  const option = conception?.option_retenue || 'sans'
  const cible = conception?.valeurs?.[option]?.nb_panneaux?.valeur
  const actuel = comptePanneauxOption(devis?.lignes || [], option)
  return cible != null && actuel !== cible ? `panneaux ${actuel} → ${cible}` : ''
}

//: `avantMiseAJour` (E7d, M4) : appelé avant le POST ; `false` ⇒ rien n'est fait.
export default function BandeauConception({ devis, onMisAJour, avantMiseAJour = null }) {
  const navigate = useNavigate()
  const [conception, setConception] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [resultat, setResultat] = useState(null)
  const [erreur, setErreur] = useState('')
  const leadId = devis?.lead ?? null

  const [tour, setTour] = useState(0)  // relire après « Mettre à jour »
  const devisId = devis?.id

  useEffect(() => {
    let vivant = true
    const lire = async () => {
      if (!leadId) { setConception(null); return }
      try {
        const { data } = await ventesApi.getConceptionLead(leadId)
        if (vivant) setConception(data?.etat ? data : null)
      } catch {
        if (vivant) setConception(null)  // aucune conception rangée : rien à dire
      }
    }
    lire()
    return () => { vivant = false }
  }, [leadId, devisId, tour])

  if (!devis?.id || !leadId) return null
  const aJour = (conception?.brouillons_a_mettre_a_jour || []).find((b) => b.devis === devis.id)
  const ecartsEnvoye = PARTIS.includes(devis.statut)
    ? (conception?.ecart_devis || []).filter((e) => e.devis_ref === devis.reference && e.reviser_possible)
    : []

  const mettreAJour = async () => {
    if (avantMiseAJour && !(await avantMiseAJour())) return
    setEnCours(true)
    setErreur('')
    try {
      const { data } = await ventesApi.mettreAJourConception(devis.id)
      setResultat(data)
      if (onMisAJour) await onMisAJour()
      setTour((t) => t + 1)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setErreur(typeof detail === 'string' ? detail : 'La mise à jour a échoué — réessayez.')
    } finally {
      setEnCours(false)
    }
  }

  if (resultat) {
    const non = resultat.non_appliquees || []
    return (
      <div className="rounded-lg border border-info/30 bg-info/10 p-3 text-sm" data-testid="bandeau-conception-resultat">
        <p>
          {(resultat.appliquees || []).length
            ? 'Brouillon mis à jour sur la conception du lead.'
            : 'Rien n’a été appliqué : le brouillon garde ses valeurs.'}
        </p>
        {non.length > 0 && (
          <ul className="mt-1 list-disc pl-5" data-testid="bandeau-conception-non-appliquees">
            {non.map((n) => <li key={`${n.champ}-${n.raison}`}>Non appliqué — {n.raison}</li>)}
          </ul>
        )}
      </div>
    )
  }

  if (aJour) {
    const ecart = ecartPanneaux(devis, conception)
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm"
           data-testid="bandeau-conception">
        <p className="flex-1">
          La conception de ce lead a changé{ecart ? ` : ${ecart}` : ''}. Ce brouillon a été {aJour.motif} : ses
          valeurs sont gardées tant que vous ne le mettez pas à jour.
        </p>
        <Button type="button" size="sm" onClick={mettreAJour} disabled={enCours}
                data-testid="bandeau-conception-mettre-a-jour">
          {enCours ? 'Mise à jour…' : 'Mettre à jour'}
        </Button>
        {erreur && <p className="w-full text-xs text-destructive">{erreur}</p>}
      </div>
    )
  }

  if (ecartsEnvoye.length) {
    const texte = ecartsEnvoye.map((e) => `${e.valeur} ${e.devis} → ${e.conception}`).join(', ')
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm"
           data-testid="bandeau-conception-envoye">
        <p className="flex-1">
          La conception de ce lead a changé depuis l’envoi ({texte}) : ce devis ne bouge pas, révisez-le pour
          la suivre.
        </p>
        <Button type="button" size="sm" variant="outline" data-testid="bandeau-conception-reviser"
                onClick={() => reviserEtOuvrir({ devis, navigate })}>
          Réviser le devis
        </Button>
      </div>
    )
  }
  return null
}
