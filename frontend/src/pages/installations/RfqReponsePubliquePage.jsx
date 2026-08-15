/**
 * WIR215/XPUR21 — Page PUBLIQUE de réponse à une demande de prix (RFQ).
 *
 * Route `/rfq/:token`, hors coquille authentifiée. C'est la destination du
 * lien envoyé au fournisseur par WhatsApp/email : ce lien pointait jusqu'ici
 * sur l'endpoint JSON `/api/django/public/installations/rfq/<token>/`, si bien
 * que le fournisseur recevait un objet brut au lieu d'un formulaire.
 *
 * Le fournisseur ne voit QUE sa propre offre : jamais les autres offres, jamais
 * un prix interne. Une RFQ clôturée est en lecture seule. La re-soumission est
 * idempotente (le serveur met à jour l'offre existante au lieu d'en créer une
 * seconde). Un token invalide donne un message français, jamais du JSON.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { rfqPublicApi } from '../../api/installationsApi'
import { frenchError } from '../../lib/frenchError'
import { Button } from '../../ui'
import NoIndex from '../../components/NoIndex'

// VX202 — throttle CLIENT de re-soumission (défense en profondeur ; le vrai
// rate-limit vit côté nginx) : un échec ne doit pas permettre une rafale.
const THROTTLE_MS = 4000

export default function RfqReponsePubliquePage() {
  const { token } = useParams()
  const [etat, setEtat] = useState('chargement') // chargement | valide | invalide
  const [rfq, setRfq] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [succes, setSucces] = useState(false)
  const [envoi, setEnvoi] = useState(false)
  const [throttled, setThrottled] = useState(false)
  const [form, setForm] = useState({
    montant_ht: '', delai_jours: '', validite_jours: '', note: '',
  })

  useEffect(() => {
    let vivant = true
    rfqPublicApi.get(token)
      .then((res) => {
        if (!vivant) return
        const d = res.data || {}
        setRfq(d)
        // Une offre déjà soumise pré-remplit le formulaire : le fournisseur
        // CORRIGE son offre, il ne la retape pas (et le POST est idempotent).
        if (d.offre) {
          setForm({
            montant_ht: d.offre.montant_ht ?? '',
            delai_jours: d.offre.delai_jours ?? '',
            validite_jours: d.offre.validite_jours ?? '',
            note: d.offre.note ?? '',
          })
        }
        setEtat('valide')
      })
      .catch((err) => {
        if (!vivant) return
        setErreur(frenchError(err, 'Ce lien de demande de prix est introuvable ou a expiré.'))
        setEtat('invalide')
      })
    return () => { vivant = false }
  }, [token])

  const set = (champ, valeur) => {
    setForm(f => ({ ...f, [champ]: valeur }))
    setSucces(false)
  }

  const soumettre = async (e) => {
    e.preventDefault()
    if (throttled || envoi) return
    if (form.montant_ht === '') { setErreur('Indiquez votre montant HT.'); return }
    setErreur(null)
    setEnvoi(true)
    setThrottled(true)
    setTimeout(() => setThrottled(false), THROTTLE_MS)
    try {
      const res = await rfqPublicApi.repondre(token, {
        montant_ht: form.montant_ht,
        // Les entiers optionnels partent vides plutôt qu'en 0 inventé : le
        // serveur les normalise lui-même (`_int_or_none`).
        delai_jours: form.delai_jours,
        validite_jours: form.validite_jours,
        note: form.note,
      })
      setRfq(res.data)
      setSucces(true)
    } catch (err) {
      setErreur(frenchError(err, "L'envoi de votre offre a échoué."))
    } finally { setEnvoi(false) }
  }

  if (etat === 'chargement') {
    return (
      <div className="ui-root page mx-auto max-w-xl p-4">
        <NoIndex />
        <p>Chargement de la demande de prix…</p>
      </div>
    )
  }

  if (etat === 'invalide') {
    return (
      <div className="ui-root page mx-auto max-w-xl p-4">
        <NoIndex />
        <h1 className="mb-2 text-lg font-semibold">Demande de prix indisponible</h1>
        <p role="alert">{erreur}</p>
      </div>
    )
  }

  const cloturee = !!rfq?.cloturee

  return (
    <div className="ui-root page mx-auto max-w-xl p-4">
      <NoIndex />
      <h1 className="mb-1 text-lg font-semibold">
        Demande de prix {rfq.reference}
      </h1>
      <p className="mb-1 text-sm text-muted-foreground">{rfq.objet}</p>
      {rfq.fournisseur_nom && (
        <p className="mb-1 text-sm text-muted-foreground">
          Destinataire : {rfq.fournisseur_nom}
        </p>
      )}
      {rfq.date_limite_reponse && (
        <p className="mb-3 text-sm text-muted-foreground">
          Date limite de réponse : {rfq.date_limite_reponse}
        </p>
      )}

      {erreur && <p role="alert" className="mb-3 text-sm text-destructive">{erreur}</p>}
      {succes && (
        <p role="status" className="mb-3 text-sm text-success">
          Votre offre a bien été enregistrée. Vous pouvez la corriger et la
          renvoyer tant que la demande est ouverte.
        </p>
      )}

      {cloturee ? (
        <>
          <p className="mb-3 text-sm font-medium text-warning">
            Cette demande de prix est clôturée : elle n'accepte plus d'offre.
          </p>
          {rfq.offre ? (
            <ul className="text-sm">
              <li>Montant HT proposé : {rfq.offre.montant_ht}</li>
              <li>Délai : {rfq.offre.delai_jours ?? '—'} jour(s)</li>
              <li>Validité : {rfq.offre.validite_jours ?? '—'} jour(s)</li>
              {rfq.offre.note && <li>Note : {rfq.offre.note}</li>}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              Aucune offre n'a été enregistrée pour vous.
            </p>
          )}
        </>
      ) : (
        <form onSubmit={soumettre} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="rfq-montant">Votre montant HT</label>
            {/* step="any" : aucune valeur saisie n'est snappée ni refusée. */}
            <input id="rfq-montant" type="number" step="any" className="form-control"
                   value={form.montant_ht}
                   onChange={(e) => set('montant_ht', e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="rfq-delai">Délai de livraison (jours)</label>
            <input id="rfq-delai" type="number" step="any" className="form-control"
                   value={form.delai_jours}
                   onChange={(e) => set('delai_jours', e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="rfq-validite">Validité de l'offre (jours)</label>
            <input id="rfq-validite" type="number" step="any" className="form-control"
                   value={form.validite_jours}
                   onChange={(e) => set('validite_jours', e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="rfq-note">Note (optionnel)</label>
            <textarea id="rfq-note" rows={3} className="form-control"
                      value={form.note}
                      onChange={(e) => set('note', e.target.value)} />
          </div>
          <Button type="submit" disabled={envoi || throttled}>
            {envoi ? 'Envoi…' : (rfq.offre ? 'Mettre à jour mon offre' : 'Envoyer mon offre')}
          </Button>
        </form>
      )}
    </div>
  )
}
