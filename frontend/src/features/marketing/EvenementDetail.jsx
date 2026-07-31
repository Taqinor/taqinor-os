import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT7 — Détail d'un événement : liste des inscrits + check-in + QR par
   inscrit + segment « présents » en un clic.
   ----------------------------------------------------------------------------
   `marketing/inscriptions-evenement/?evenement=<id>` (statut inscrit/
   confirmé/présent/absent), action `pointer` (check-in sur place). Le
   « QR par inscrit » réutilise le badge PDF déjà généré côté serveur
   (`InscriptionEvenementViewSet.badge`, ZMKT19 — lui-même bâti sur
   `stock.labels.qr_svg`, XMKT29) plutôt que de dupliquer un rendu QR côté
   client : un badge téléchargé encode le même `qr_token` scannable qui
   compte le passage. « Créer le segment présents » (NTMKT4) pose
   `regles: {evenement_present: <id>}` — filtre déjà supporté par
   `apps.compta.services.valider_regles_segment` (XMKT28), aucun nouveau
   champ backend.

   WIR162 — 3 onglets supplémentaires (chargement paresseux, même patron que
   `SequenceDetail.jsx` — inactif = zéro appel réseau, préserve les tests
   existants du seul onglet Inscrits) :
   - Billets (ZMKT15, `billetsEvenement`) : libellé/prix/quota par type de
     billet, déjà enveloppé côté API mais jamais appelé.
   - Questions (ZMKT16, `questionsEvenement`) : constructeur de questions
     d'inscription (libellé/type/obligatoire/portée).
   - Communications (ZMKT17, `communicationsEvenement`) : planification de
     rappels/relances (canal, intervalle SIGNÉ relatif au début, gabarit).
   ========================================================================== */

const STATUTS = [
  { key: '', label: 'Tous' },
  { key: 'inscrit', label: 'Inscrit' },
  { key: 'confirme', label: 'Confirmé' },
  { key: 'present', label: 'Présent' },
  { key: 'absent', label: 'Absent' },
]

const ONGLETS = [
  { key: 'inscrits', label: 'Inscrits' },
  { key: 'billets', label: 'Billets' },
  { key: 'questions', label: 'Questions' },
  { key: 'communications', label: 'Communications' },
]

const TYPES_QUESTION = [
  { key: 'choix', label: 'Choix' },
  { key: 'texte', label: 'Texte' },
  { key: 'booleen', label: 'Booléen' },
]
const PORTEES_QUESTION = [
  { key: 'par_inscrit', label: 'Par inscrit' },
  { key: 'par_commande', label: 'Par commande' },
]
const CANAUX_COMMUNICATION = [
  { key: 'email', label: 'Email' },
  { key: 'sms', label: 'SMS' },
  { key: 'whatsapp', label: 'WhatsApp' },
]
const UNITES_INTERVALLE = [
  { key: 'jours', label: 'Jours' },
  { key: 'heures', label: 'Heures' },
]

export default function EvenementDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [evenement, setEvenement] = useState(null)
  const [inscriptions, setInscriptions] = useState([])
  const [statutFiltre, setStatutFiltre] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [segmentMsg, setSegmentMsg] = useState('')

  // WIR162 — onglets Billets/Questions/Communications (chargement paresseux).
  const [onglet, setOnglet] = useState('inscrits')
  const [billets, setBillets] = useState([])
  const [questions, setQuestions] = useState([])
  const [communications, setCommunications] = useState([])
  const [billetForm, setBilletForm] = useState({ libelle: '', prix_ttc_mad: '', quota: '' })
  const [questionForm, setQuestionForm] = useState({ libelle: '', type_question: 'texte', obligatoire: false, portee: 'par_inscrit' })
  const [communicationForm, setCommunicationForm] = useState({ canal: 'email', gabarit: '', intervalle: '', unite_intervalle: 'jours' })

  const loadEvenement = useCallback(() => {
    setLoading(true)
    return marketingApi.evenements.get(id)
      .then(r => setEvenement(r.data))
      .catch(() => setErr('Événement introuvable.'))
      .finally(() => setLoading(false))
  }, [id])

  const loadInscriptions = useCallback(() => {
    return marketingApi.inscriptionsEvenement.list(
      { evenement: id, ...(statutFiltre ? { statut: statutFiltre } : {}) })
      .then(r => setInscriptions(marketingApi.unwrapList(r)))
      .catch(() => setInscriptions([]))
  }, [id, statutFiltre])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { loadEvenement() }, [loadEvenement])
  useEffect(() => { loadInscriptions() }, [loadInscriptions])

  // WIR162 — chargement paresseux : SEUL l'onglet actif appelle son endpoint
  // (même patron que `SequenceDetail.jsx` participants) — un onglet jamais
  // ouvert ne fait AUCUN appel réseau.
  const loadBillets = useCallback(() => {
    return marketingApi.billetsEvenement.list({ evenement: id })
      .then(r => setBillets(marketingApi.unwrapList(r)))
      .catch(() => setBillets([]))
  }, [id])
  const loadQuestions = useCallback(() => {
    return marketingApi.questionsEvenement.list({ evenement: id })
      .then(r => setQuestions(marketingApi.unwrapList(r)))
      .catch(() => setQuestions([]))
  }, [id])
  const loadCommunications = useCallback(() => {
    return marketingApi.communicationsEvenement.list({ evenement: id })
      .then(r => setCommunications(marketingApi.unwrapList(r)))
      .catch(() => setCommunications([]))
  }, [id])

  useEffect(() => {
    if (onglet === 'billets') loadBillets()
    else if (onglet === 'questions') loadQuestions()
    else if (onglet === 'communications') loadCommunications()
  }, [onglet, loadBillets, loadQuestions, loadCommunications])

  const ajouterBillet = async (e) => {
    e.preventDefault()
    if (!billetForm.libelle.trim()) return
    setErr('')
    try {
      await marketingApi.billetsEvenement.create({
        evenement: Number(id),
        libelle: billetForm.libelle.trim(),
        prix_ttc_mad: billetForm.prix_ttc_mad === '' ? 0 : Number(billetForm.prix_ttc_mad),
        quota: billetForm.quota === '' ? null : Number(billetForm.quota),
      })
      setBilletForm({ libelle: '', prix_ttc_mad: '', quota: '' })
      loadBillets()
    } catch {
      setErr('Création du billet impossible.')
    }
  }
  const supprimerBillet = async (billetId) => {
    setErr('')
    try {
      await marketingApi.billetsEvenement.remove(billetId)
      loadBillets()
    } catch {
      setErr('Suppression du billet impossible.')
    }
  }

  const ajouterQuestion = async (e) => {
    e.preventDefault()
    if (!questionForm.libelle.trim()) return
    setErr('')
    try {
      await marketingApi.questionsEvenement.create({
        evenement: Number(id),
        libelle: questionForm.libelle.trim(),
        type_question: questionForm.type_question,
        obligatoire: questionForm.obligatoire,
        portee: questionForm.portee,
      })
      setQuestionForm({ libelle: '', type_question: 'texte', obligatoire: false, portee: 'par_inscrit' })
      loadQuestions()
    } catch {
      setErr('Création de la question impossible.')
    }
  }
  const supprimerQuestion = async (questionId) => {
    setErr('')
    try {
      await marketingApi.questionsEvenement.remove(questionId)
      loadQuestions()
    } catch {
      setErr('Suppression de la question impossible.')
    }
  }

  const ajouterCommunication = async (e) => {
    e.preventDefault()
    if (communicationForm.intervalle === '') return
    setErr('')
    try {
      await marketingApi.communicationsEvenement.create({
        evenement: Number(id),
        canal: communicationForm.canal,
        gabarit: communicationForm.gabarit,
        intervalle: Number(communicationForm.intervalle),
        unite_intervalle: communicationForm.unite_intervalle,
      })
      setCommunicationForm({ canal: 'email', gabarit: '', intervalle: '', unite_intervalle: 'jours' })
      loadCommunications()
    } catch {
      setErr('Planification de la communication impossible.')
    }
  }
  const supprimerCommunication = async (communicationId) => {
    setErr('')
    try {
      await marketingApi.communicationsEvenement.remove(communicationId)
      loadCommunications()
    } catch {
      setErr('Suppression de la communication impossible.')
    }
  }

  const pointer = async (inscriptionId) => {
    setErr('')
    try {
      await marketingApi.inscriptionsEvenement.pointer(inscriptionId)
      loadInscriptions()
    } catch {
      setErr('Check-in impossible.')
    }
  }

  const telechargerBadge = async (inscriptionId, nom) => {
    setErr('')
    try {
      const r = await marketingApi.inscriptionsEvenement.badgePdf(inscriptionId)
      marketingApi.downloadBlob(r.data, `badge-${nom || inscriptionId}.pdf`)
    } catch {
      setErr('Badge indisponible.')
    }
  }

  const creerSegmentPresents = async () => {
    setSegmentMsg('')
    setErr('')
    try {
      await marketingApi.segments.create({
        nom: `Présents — ${evenement.nom}`,
        regles: { evenement_present: Number(id) },
      })
      setSegmentMsg('Segment « Présents » créé.')
    } catch {
      setErr('Création du segment impossible.')
    }
  }

  if (loading) return <div className="page"><p className="page-loading">Chargement…</p></div>
  if (!evenement) return <div className="page"><p style={{ color: '#dc2626' }}>{err || 'Introuvable.'}</p></div>

  return (
    <div className="page">
      <div className="page-header">
        <button className="btn btn-light" onClick={() => navigate('/marketing/evenements')}>
          ← Événements
        </button>
        <h2>{evenement.nom}</h2>
        <button className="btn btn-primary" data-testid="evenement-segment-presents"
          onClick={creerSegmentPresents}>
          Créer le segment présents
        </button>
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      {segmentMsg && <p style={{ color: '#16a34a' }}>{segmentMsg}</p>}

      {/* WIR162 — onglets Billets/Questions/Communications, même patron que
          SequenceDetail.jsx (boutons plats togglant l'état local). */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {ONGLETS.map(o => (
          <button key={o.key} type="button"
            className={`btn ${onglet === o.key ? 'btn-primary' : 'btn-light'}`}
            data-testid={`evenement-onglet-${o.key}`} onClick={() => setOnglet(o.key)}>
            {o.label}
          </button>
        ))}
      </div>

      {onglet === 'inscrits' && (
        <>
          <select className="form-input" data-testid="inscriptions-filtre-statut"
            value={statutFiltre} onChange={e => setStatutFiltre(e.target.value)}
            style={{ marginBottom: 8 }}>
            {STATUTS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>

          <table className="data-table" data-testid="inscriptions-table">
            <thead>
              <tr><th>Nom</th><th>Email</th><th>Statut</th><th /></tr>
            </thead>
            <tbody>
              {inscriptions.map(insc => (
                <tr key={insc.id} data-testid="inscription-row">
                  <td>{insc.nom}</td>
                  <td>{insc.email || '—'}</td>
                  <td>{insc.statut_display || insc.statut}</td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    {insc.statut !== 'present' && (
                      <button className="btn btn-light" type="button"
                        data-testid="inscription-pointer" onClick={() => pointer(insc.id)}>
                        Check-in
                      </button>
                    )}
                    <button className="btn btn-light" type="button"
                      data-testid="inscription-badge"
                      onClick={() => telechargerBadge(insc.id, insc.nom)}>
                      Badge / QR
                    </button>
                  </td>
                </tr>
              ))}
              {inscriptions.length === 0 && (
                <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun inscrit
                </td></tr>
              )}
            </tbody>
          </table>
        </>
      )}

      {/* WIR162 (ZMKT15) — types de billets : libellé/prix/quota. */}
      {onglet === 'billets' && (
        <>
          <form onSubmit={ajouterBillet} data-testid="billet-form"
            style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            <input className="form-input" placeholder="Libellé (ex. VIP)" required
              data-testid="billet-libelle" value={billetForm.libelle}
              onChange={e => setBilletForm(f => ({ ...f, libelle: e.target.value }))}
              style={{ flex: '2 1 180px' }} />
            <input type="number" min={0} step="any" className="form-input" placeholder="Prix TTC (MAD)"
              data-testid="billet-prix" value={billetForm.prix_ttc_mad}
              onChange={e => setBilletForm(f => ({ ...f, prix_ttc_mad: e.target.value }))}
              style={{ flex: '1 1 140px' }} />
            <input type="number" min={0} className="form-input" placeholder="Quota (optionnel)"
              data-testid="billet-quota" value={billetForm.quota}
              onChange={e => setBilletForm(f => ({ ...f, quota: e.target.value }))}
              style={{ flex: '1 1 140px' }} />
            <button type="submit" className="btn btn-primary" data-testid="billet-ajouter">
              Ajouter
            </button>
          </form>
          <table className="data-table" data-testid="billets-table">
            <thead>
              <tr><th>Libellé</th><th>Prix TTC</th><th>Quota</th><th>Places restantes</th><th>Inscrits</th><th /></tr>
            </thead>
            <tbody>
              {billets.map(b => (
                <tr key={b.id} data-testid="billet-row">
                  <td>{b.libelle}</td>
                  <td>{b.prix_ttc_mad} MAD</td>
                  <td>{b.quota ?? '—'}</td>
                  <td>{b.places_restantes ?? '—'}</td>
                  <td>{b.nb_inscrits ?? 0}</td>
                  <td>
                    <button className="btn btn-light" type="button" data-testid="billet-supprimer"
                      onClick={() => supprimerBillet(b.id)}>
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
              {billets.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun billet
                </td></tr>
              )}
            </tbody>
          </table>
        </>
      )}

      {/* WIR162 (ZMKT16) — constructeur de questions d'inscription. */}
      {onglet === 'questions' && (
        <>
          <form onSubmit={ajouterQuestion} data-testid="question-form"
            style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: '0.75rem' }}>
            <input className="form-input" placeholder="Libellé de la question" required
              data-testid="question-libelle" value={questionForm.libelle}
              onChange={e => setQuestionForm(f => ({ ...f, libelle: e.target.value }))}
              style={{ flex: '2 1 220px' }} />
            <select className="form-input" data-testid="question-type"
              value={questionForm.type_question}
              onChange={e => setQuestionForm(f => ({ ...f, type_question: e.target.value }))}
              style={{ flex: '1 1 120px' }}>
              {TYPES_QUESTION.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
            <select className="form-input" data-testid="question-portee"
              value={questionForm.portee}
              onChange={e => setQuestionForm(f => ({ ...f, portee: e.target.value }))}
              style={{ flex: '1 1 140px' }}>
              {PORTEES_QUESTION.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem' }}>
              <input type="checkbox" data-testid="question-obligatoire"
                checked={questionForm.obligatoire}
                onChange={e => setQuestionForm(f => ({ ...f, obligatoire: e.target.checked }))} />
              Obligatoire
            </label>
            <button type="submit" className="btn btn-primary" data-testid="question-ajouter">
              Ajouter
            </button>
          </form>
          <table className="data-table" data-testid="questions-table">
            <thead>
              <tr><th>Libellé</th><th>Type</th><th>Portée</th><th>Obligatoire</th><th /></tr>
            </thead>
            <tbody>
              {questions.map(q => (
                <tr key={q.id} data-testid="question-row">
                  <td>{q.libelle}</td>
                  <td>{TYPES_QUESTION.find(t => t.key === q.type_question)?.label || q.type_question}</td>
                  <td>{PORTEES_QUESTION.find(p => p.key === q.portee)?.label || q.portee}</td>
                  <td>{q.obligatoire ? 'Oui' : 'Non'}</td>
                  <td>
                    <button className="btn btn-light" type="button" data-testid="question-supprimer"
                      onClick={() => supprimerQuestion(q.id)}>
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
              {questions.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune question
                </td></tr>
              )}
            </tbody>
          </table>
        </>
      )}

      {/* WIR162 (ZMKT17) — planification de communications (rappel/relance). */}
      {onglet === 'communications' && (
        <>
          <form onSubmit={ajouterCommunication} data-testid="communication-form"
            style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            <select className="form-input" data-testid="communication-canal"
              value={communicationForm.canal}
              onChange={e => setCommunicationForm(f => ({ ...f, canal: e.target.value }))}
              style={{ flex: '1 1 120px' }}>
              {CANAUX_COMMUNICATION.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
            <input type="number" className="form-input" placeholder="Intervalle (ex. -2)" required
              data-testid="communication-intervalle" value={communicationForm.intervalle}
              onChange={e => setCommunicationForm(f => ({ ...f, intervalle: e.target.value }))}
              style={{ flex: '1 1 140px' }} />
            <select className="form-input" data-testid="communication-unite"
              value={communicationForm.unite_intervalle}
              onChange={e => setCommunicationForm(f => ({ ...f, unite_intervalle: e.target.value }))}
              style={{ flex: '1 1 120px' }}>
              {UNITES_INTERVALLE.map(u => <option key={u.key} value={u.key}>{u.label}</option>)}
            </select>
            <input className="form-input" placeholder="Gabarit (corps du message)"
              data-testid="communication-gabarit" value={communicationForm.gabarit}
              onChange={e => setCommunicationForm(f => ({ ...f, gabarit: e.target.value }))}
              style={{ flex: '3 1 240px' }} />
            <button type="submit" className="btn btn-primary" data-testid="communication-ajouter">
              Planifier
            </button>
          </form>
          <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 0 }}>
            Intervalle signé relatif au début de l’événement (ex. -2 jours = rappel avant, +1 jour = relance après).
          </p>
          <table className="data-table" data-testid="communications-table">
            <thead>
              <tr><th>Canal</th><th>Intervalle</th><th>Gabarit</th><th>Envoyée le</th><th /></tr>
            </thead>
            <tbody>
              {communications.map(c => (
                <tr key={c.id} data-testid="communication-row">
                  <td>{CANAUX_COMMUNICATION.find(x => x.key === c.canal)?.label || c.canal}</td>
                  <td>{c.intervalle >= 0 ? `+${c.intervalle}` : c.intervalle} {c.unite_intervalle}</td>
                  <td>{(c.gabarit || '').slice(0, 60) || '—'}</td>
                  <td>{c.envoyee_le || '—'}</td>
                  <td>
                    <button className="btn btn-light" type="button" data-testid="communication-supprimer"
                      onClick={() => supprimerCommunication(c.id)}>
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
              {communications.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune communication planifiée
                </td></tr>
              )}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
