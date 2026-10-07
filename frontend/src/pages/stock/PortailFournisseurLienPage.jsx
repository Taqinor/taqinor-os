import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Button, Input } from '../../ui'
import NoIndex from '../../components/NoIndex'
import publicStockApi from '../../features/stock/publicStockApi'
import { erreurChamp, messageServeur } from '../../features/stock/api/erreurs'

/* ASTK228 — portail fournisseur PAR LIEN (/fournisseur/lien/:token).

   Page publique, sans login ni layout ERP : le jeton identifie UN fournisseur.
   L'écran n'affiche que ce que le serveur sert pour lui (ses BCF envoyés, ses
   réceptions, ses factures) — jamais de prix de vente ni de marge. Le
   fournisseur peut :
   - confirmer la date (+ n°) d'un BCF ENVOYÉ (un BCF déjà reçu n'offre aucune
     confirmation ; une date illisible est nommée sous le champ) ;
   - choisir un créneau parmi ceux que le serveur PROPOSE et le réserver —
     jamais de champ heure libre.
   Un jeton révoqué / expiré affiche le 404 du serveur tel quel. */

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')
const fmtCreneau = (c) => {
  const d = new Date(c.debut)
  const f = new Date(c.fin)
  const h = (x) => x.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  return `${c.quai_nom} — ${d.toLocaleDateString('fr-FR')} ${h(d)}–${h(f)}`
}

const Section = ({ titre, children }) => (
  <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
    <h2 className="mb-3 text-sm font-semibold">{titre}</h2>
    {children}
  </section>
)
const Vide = ({ children }) => <p className="text-sm text-[var(--muted-foreground)]">{children}</p>

function ConfirmationBcf({ bcf, token, onFait, onErreur }) {
  const [date, setDate] = useState('')
  const [numero, setNumero] = useState('')
  const [erreurDate, setErreurDate] = useState(null)
  const [erreurNumero, setErreurNumero] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const confirmer = async (ev) => {
    ev.preventDefault()
    setErreurDate(null); setErreurNumero(null); onErreur(null); setOccupe(true)
    try {
      await publicStockApi.confirmerBcf(token, bcf.id, {
        date_confirmee_fournisseur: date, numero_confirmation_fournisseur: numero,
      })
      await onFait()
    } catch (err) {
      const d = erreurChamp(err, 'date_confirmee_fournisseur')
      const n = erreurChamp(err, 'numero_confirmation_fournisseur')
      if (d || n) { setErreurDate(d); setErreurNumero(n) } else {
        onErreur(messageServeur(err, 'La confirmation a échoué.'))
      }
    } finally { setOccupe(false) }
  }

  return (
    <form onSubmit={confirmer} noValidate className="mt-2 flex flex-wrap items-start gap-2">
      <div className="flex flex-col gap-1 text-xs">
        <label className="flex flex-col gap-1">
          <span>Date de livraison confirmée</span>
          <Input
            value={date} onChange={(e) => setDate(e.target.value)} placeholder="AAAA-MM-JJ"
            inputMode="numeric" invalid={!!erreurDate} className="w-40"
            aria-describedby={erreurDate ? `erreur-date-${bcf.id}` : undefined}
          />
        </label>
        {erreurDate && (
          <span id={`erreur-date-${bcf.id}`} className="text-xs text-destructive">{erreurDate}</span>
        )}
      </div>
      <div className="flex flex-col gap-1 text-xs">
        <label className="flex flex-col gap-1">
          <span>N° de confirmation</span>
          <Input
            value={numero} onChange={(e) => setNumero(e.target.value)} className="w-44" invalid={!!erreurNumero}
            aria-describedby={erreurNumero ? `erreur-num-${bcf.id}` : undefined}
          />
        </label>
        {erreurNumero && (
          <span id={`erreur-num-${bcf.id}`} className="text-xs text-destructive">{erreurNumero}</span>
        )}
      </div>
      <Button type="submit" disabled={occupe} className="mt-5">Confirmer la commande</Button>
    </form>
  )
}

export default function PortailFournisseurLienPage() {
  const { token } = useParams()
  const [portail, setPortail] = useState(null)
  const [creneaux, setCreneaux] = useState([])
  const [erreur, setErreur] = useState(null)
  const [fatale, setFatale] = useState(null)
  const [choix, setChoix] = useState(null)
  const [chauffeur, setChauffeur] = useState('')
  const [immat, setImmat] = useState('')
  const [reservation, setReservation] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    try {
      const { data } = await publicStockApi.portailFournisseur(token)
      setPortail(data)
      setFatale(null)
    } catch (err) {
      setFatale(messageServeur(err, 'Ce lien est introuvable ou a expiré.'))
    }
  }, [token])

  const chargerCreneaux = useCallback(async () => {
    try {
      const { data } = await publicStockApi.creneauxDisponibles(token, {})
      setCreneaux(data.creneaux ?? [])
    } catch (err) { setErreur(messageServeur(err, 'Créneaux indisponibles.')) }
  }, [token])

  useEffect(() => {
    Promise.resolve().then(charger)
    Promise.resolve().then(chargerCreneaux)
  }, [charger, chargerCreneaux])

  const envoyes = (portail?.bons_commande ?? []).filter((b) => b.statut === 'envoye')

  const reserver = async () => {
    if (!choix) { setErreur('Choisissez un créneau.'); return }
    setErreur(null); setOccupe(true)
    const corps = {
      quai: choix.quai, debut: choix.debut,
      chauffeur_nom: chauffeur, immatriculation: immat,
    }
    // Le BCF concerné : le premier BCF envoyé (jamais un identifiant saisi).
    if (envoyes[0]) corps.bon_commande = envoyes[0].id
    try {
      const { data } = await publicStockApi.reserverCreneau(token, corps)
      setReservation(data)
      setChoix(null)
      await chargerCreneaux()
    } catch (err) {
      setErreur(erreurChamp(err, 'debut') || messageServeur(err, "La réservation a échoué."))
    } finally { setOccupe(false) }
  }

  if (fatale) {
    return (
      <main className="mx-auto max-w-2xl p-6">
        <NoIndex />
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {fatale}
        </div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6">
      <NoIndex />
      <h1 className="text-2xl font-semibold">Portail fournisseur</h1>
      {portail && <p className="text-lg">{portail.fournisseur_nom}</p>}

      {erreur && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {erreur}
        </div>
      )}

      {portail && (
        <>
          <Section titre="Commandes envoyées">
            {portail.bons_commande.length === 0 ? <Vide>Aucune commande.</Vide> : (
              <ul className="space-y-4 text-sm">
                {portail.bons_commande.map((b) => (
                  <li key={b.id}>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                      <strong>{b.reference}</strong>
                      <span>{b.statut_display}</span>
                      <span>Livraison prévue : {fmtDate(b.date_livraison_prevue)}</span>
                      {b.date_confirmee_fournisseur && (
                        <span>Confirmée pour le {fmtDate(b.date_confirmee_fournisseur)}</span>
                      )}
                    </div>
                    <ul className="mt-1 text-[var(--muted-foreground)]">
                      {b.lignes.map((l, i) => (
                        <li key={i}>{l.produit_nom} — {l.quantite} (reçu {l.quantite_recue})</li>
                      ))}
                    </ul>
                    {b.statut === 'envoye' && (
                      <ConfirmationBcf bcf={b} token={token} onFait={charger} onErreur={setErreur} />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section titre="Réceptions">
            {portail.receptions.length === 0 ? <Vide>Aucune réception.</Vide> : (
              <ul className="space-y-1 text-sm">
                {portail.receptions.map((r) => (
                  <li key={r.id}>{r.reference} — BCF {r.bon_commande_reference} — {r.statut} — {fmtDate(r.date_reception)}</li>
                ))}
              </ul>
            )}
          </Section>

          <Section titre="Factures">
            {portail.factures.length === 0 ? <Vide>Aucune facture.</Vide> : (
              <ul className="space-y-1 text-sm">
                {portail.factures.map((f) => (
                  <li key={f.id}>
                    {f.reference} — {f.statut_display} — échéance {fmtDate(f.date_echeance)} — solde dû {f.solde_du}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section titre="Réserver un créneau de livraison">
            {creneaux.length === 0 ? <Vide>Aucun créneau proposé pour le moment.</Vide> : (
              <fieldset className="space-y-1 text-sm">
                <legend className="sr-only">Créneaux proposés</legend>
                {creneaux.map((c) => (
                  <label key={`${c.quai}-${c.debut}`} className="flex items-center gap-2">
                    <input
                      type="radio" name="creneau"
                      checked={choix?.debut === c.debut && choix?.quai === c.quai}
                      onChange={() => setChoix(c)}
                    />
                    <span>{fmtCreneau(c)}</span>
                  </label>
                ))}
              </fieldset>
            )}
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1 text-xs">
                <span>Chauffeur</span>
                <Input value={chauffeur} onChange={(e) => setChauffeur(e.target.value)} className="w-44" />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span>Immatriculation</span>
                <Input value={immat} onChange={(e) => setImmat(e.target.value)} className="w-36" sanitize="code" />
              </label>
              <Button onClick={reserver} disabled={occupe || creneaux.length === 0}>Réserver ce créneau</Button>
            </div>
            {reservation && (
              <div role="status" className="mt-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
                Créneau réservé. Code d&apos;arrivée à remettre au chauffeur :{' '}
                <strong className="tracking-widest">{reservation.code_checkin}</strong>
              </div>
            )}
          </Section>
        </>
      )}
    </main>
  )
}
