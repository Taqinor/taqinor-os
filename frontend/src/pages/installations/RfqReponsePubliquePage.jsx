/**
 * WIR215/XPUR21 — Page PUBLIQUE de réponse fournisseur à une demande de prix.
 * Route /rfq/:token — autonome (aucun login, aucun layout ERP), destination du
 * lien envoyé par email/WhatsApp (XPUR20).
 *
 * Le lien envoyé pointait jusqu'ici vers l'ENDPOINT JSON
 * (`/api/django/public/installations/rfq/<token>/`) : le fournisseur recevait
 * du JSON brut. Cette page est la destination humaine ; l'endpoint reste sa
 * source de données.
 *
 * Même patron que SignalementPublicPage (WIR214) / EquipementSignalerPage
 * (XSAV19) : jeton imprévisible, message FRANÇAIS honnête si invalide ou
 * expiré (jamais du JSON à l'écran), jamais de fausse réussite. La société, la
 * RFQ et le fournisseur sont TOUJOURS résolus depuis le jeton côté serveur.
 * Re-soumettre met à jour LA MÊME offre (idempotent) ; une RFQ clôturée est en
 * lecture seule. Aucun prix interne, aucune offre concurrente n'est servie.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../../api/axios'
import { Button, Input, Textarea, Label } from '../../ui'
import { useNavigationGuard } from '../../hooks/useNavigationGuard'

export default function RfqReponsePubliquePage() {
  const { token } = useParams()
  const [lienStatus, setLienStatus] = useState('loading') // loading|valide|invalide
  const [rfq, setRfq] = useState(null)

  const [montant, setMontant] = useState('')
  const [delai, setDelai] = useState('')
  const [validite, setValidite] = useState('')
  const [note, setNote] = useState('')
  const [status, setStatus] = useState('form') // form|submitting|done|error
  const [error, setError] = useState(null)

  const dirty = status !== 'done' && Boolean(montant || delai || validite || note)
  useNavigationGuard(dirty)

  useEffect(() => {
    let vivant = true
    api.get(`/public/installations/rfq/${token}/`)
      .then((res) => {
        if (!vivant) return
        const data = res.data || {}
        setRfq(data)
        // Une offre déjà soumise se ré-affiche : le fournisseur CORRIGE la
        // sienne au lieu d'en créer une seconde.
        if (data.offre) {
          setMontant(data.offre.montant_ht != null ? String(data.offre.montant_ht) : '')
          setDelai(data.offre.delai_jours != null ? String(data.offre.delai_jours) : '')
          setValidite(data.offre.validite_jours != null ? String(data.offre.validite_jours) : '')
          setNote(data.offre.note || '')
        }
        setLienStatus('valide')
      })
      .catch(() => { if (vivant) setLienStatus('invalide') })
    return () => { vivant = false }
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (montant.trim() === '') return
    setStatus('submitting')
    setError(null)
    try {
      const res = await api.post(`/public/installations/rfq/${token}/`, {
        montant_ht: montant,
        delai_jours: delai === '' ? null : delai,
        validite_jours: validite === '' ? null : validite,
        note,
      })
      setRfq(res.data || null)
      setStatus('done')
    } catch (err) {
      const data = err?.response?.data
      setError(
        data?.detail
        ?? data?.montant_ht
        ?? "Impossible d'envoyer votre offre — réessayez.")
      setStatus(err?.response?.status === 404 ? 'invalid' : 'error')
    }
  }

  if (lienStatus === 'loading') {
    return (
      <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
        <p>Chargement…</p>
      </div>
    )
  }

  if (lienStatus === 'invalide' || status === 'invalid') {
    return (
      <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
        <h2>Demande de prix</h2>
        <p role="alert" className="page-error">
          Ce lien est introuvable, expiré ou révoqué — contactez-nous
          directement pour obtenir un nouveau lien.
        </p>
      </div>
    )
  }

  const cloturee = Boolean(rfq?.cloturee)

  return (
    <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
      <h2>Demande de prix {rfq?.reference ?? ''}</h2>
      {rfq?.objet && <p className="text-sm text-muted-foreground">{rfq.objet}</p>}
      {rfq?.fournisseur_nom && (
        <p className="text-sm text-muted-foreground">
          Destinataire : {rfq.fournisseur_nom}
        </p>
      )}
      {rfq?.date_limite_reponse && (
        <p className="text-sm text-muted-foreground">
          Date limite de réponse : {rfq.date_limite_reponse}
        </p>
      )}

      {status === 'done' && (
        <p role="status">
          Merci, votre offre a bien été enregistrée. Vous pouvez la corriger
          tant que la demande de prix reste ouverte.
        </p>
      )}

      {cloturee ? (
        <div>
          <p role="status">
            Cette demande de prix est clôturée — votre offre n’est plus
            modifiable.
          </p>
          {rfq?.offre && (
            <ul className="text-sm" data-testid="rfq-offre-lecture">
              <li>Montant HT proposé : {rfq.offre.montant_ht ?? '—'}</li>
              <li>Délai (jours) : {rfq.offre.delai_jours ?? '—'}</li>
              <li>Validité (jours) : {rfq.offre.validite_jours ?? '—'}</li>
              {rfq.offre.note && <li>Commentaire : {rfq.offre.note}</li>}
            </ul>
          )}
        </div>
      ) : (
        /* Les nombres tapés ne sont ni rognés ni rejetés : `noValidate` et
           `step="any"` sur chaque champ numérique. */
        <form onSubmit={handleSubmit} noValidate>
          <p className="text-sm text-muted-foreground">
            Indiquez votre meilleure offre. Vous pouvez la corriger tant que la
            demande reste ouverte — la re-soumission remplace la précédente.
          </p>

          <Label htmlFor="rfq-montant">Montant HT proposé</Label>
          <Input
            id="rfq-montant"
            className="form-control"
            type="number"
            step="any"
            value={montant}
            onChange={(e) => setMontant(e.target.value)}
            required
          />

          <Label htmlFor="rfq-delai">Délai de livraison (jours)</Label>
          <Input
            id="rfq-delai"
            className="form-control"
            type="number"
            step="any"
            value={delai}
            onChange={(e) => setDelai(e.target.value)}
          />

          <Label htmlFor="rfq-validite">Validité de l’offre (jours)</Label>
          <Input
            id="rfq-validite"
            className="form-control"
            type="number"
            step="any"
            value={validite}
            onChange={(e) => setValidite(e.target.value)}
          />

          <Label htmlFor="rfq-note">Commentaire (optionnel)</Label>
          <Textarea
            id="rfq-note"
            className="form-control"
            rows={4}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />

          {error && <p role="alert" className="page-error">{error}</p>}

          <Button type="submit" disabled={status === 'submitting' || montant.trim() === ''}>
            {status === 'submitting' ? 'Envoi…' : 'Envoyer mon offre'}
          </Button>
        </form>
      )}
    </div>
  )
}
