/**
 * XGED1 / XGED2 — Cérémonie de signature électronique PUBLIQUE (sans login).
 *
 * Routes (hors coquille authentifiée) :
 *   /ged/signature/:token   — demande mono-signataire (jeton de la demande).
 *   /ged/signataire/:token  — un destinataire d'un circuit multi-signataires
 *                             (jeton PROPRE au destinataire).
 *
 * Déroulé : consulter le document → consentir (loi 53-05) → signer OU refuser.
 * L'aperçu du document se fait via le proxy même-origine GED14
 * (versions/<id>/apercu/). Sans jeton valide : message honnête (jamais de faux
 * succès, jamais de fuite d'une autre société). Le mode « signataire » gère en
 * plus le code d'authentification extra (OTP) exigé avant la signature (ZGED2).
 *
 * Ne touche NI contrats.SignatureContrat NI /proposal (règle #4) : c'est la
 * signature GED, un système documentaire distinct.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import gedApi from '../../api/gedApi'
import { Button } from '../../ui'
import { errMessage } from '../../features/ged/advanced/shared.js'
import NoIndex from '../../components/NoIndex'

// Types de champ dont la VALEUR doit être saisie par le signataire (XGED3).
const CHAMP_SAISIE = new Set(['texte', 'date', 'case'])

export default function PublicSignaturePage({ mode = 'signature' }) {
  const { token } = useParams()
  const signataireMode = mode === 'signataire'

  // loading | valid | invalid | done
  const [status, setStatus] = useState('loading')
  const [demande, setDemande] = useState(null)
  const [error, setError] = useState(null)

  // Consentement + saisies.
  const [consentement, setConsentement] = useState(false)
  const [signatureTexte, setSignatureTexte] = useState('')
  const [valeursChamps, setValeursChamps] = useState({})
  const [motif, setMotif] = useState('')
  const [showRefus, setShowRefus] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // ZGED2 — code d'authentification extra (mode signataire uniquement).
  const [code, setCode] = useState('')
  const [codeEnvoye, setCodeEnvoye] = useState(false)

  const consulter = useCallback(async () => {
    const call = signataireMode
      ? gedApi.getSignatairePublique(token)
      : gedApi.getSignaturePublique(token)
    try {
      const res = await call
      setDemande(res.data)
      // Une demande déjà signée/refusée renvoie 200 en mode mono via son statut.
      const statut = res.data?.statut || res.data?.demande_statut
      if (statut === 'signe' || statut === 'refuse') {
        setStatus('done')
      } else {
        setStatus('valid')
      }
    } catch (err) {
      const st = err?.response?.status
      // 410 = déjà traitée / expirée : on l'affiche comme un état terminal
      // honnête plutôt qu'une erreur brute.
      if (st === 410) {
        setError(errMessage(err, 'Ce lien de signature a expiré ou a déjà été traité.'))
        setStatus('done')
      } else {
        setError(errMessage(err, 'Ce lien de signature est introuvable ou a expiré.'))
        setStatus('invalid')
      }
    }
  }, [token, signataireMode])

  useEffect(() => {
    // `consulter` pilote lui-même `status` (valid/done/invalid) ; l'état initial
    // est déjà « loading », inutile de le réappliquer ici.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- consultation au montage
    consulter()
  }, [consulter])

  const champs = demande?.champs || []
  const otpRequis = signataireMode && demande?.otp_requis

  const setValeurChamp = (id, v) =>
    setValeursChamps((prev) => ({ ...prev, [id]: v }))

  const envoyerCode = async () => {
    setError(null)
    try {
      await gedApi.envoyerCodeSignataire(token)
      setCodeEnvoye(true)
    } catch (err) {
      setError(errMessage(err, 'Impossible d’envoyer le code — réessayez.'))
    }
  }

  const validerCode = async () => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await gedApi.validerCodeSignataire(token, code.trim())
      setDemande(res.data)
    } catch (err) {
      setError(errMessage(err, 'Code invalide — réessayez.'))
    } finally {
      setSubmitting(false)
    }
  }

  const signer = async () => {
    if (!consentement) {
      setError('Vous devez consentir avant de signer.')
      return
    }
    // Les champs requis (XGED3) doivent être remplis.
    const manquant = champs.find(
      (c) => c.requis && CHAMP_SAISIE.has(c.type_champ)
        && !String(valeursChamps[c.id] ?? '').trim(),
    )
    if (manquant) {
      setError('Veuillez remplir tous les champs requis.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      const payload = {
        consentement: true,
        signature_texte: signatureTexte.trim() || (demande?.signataire_nom || demande?.nom || ''),
      }
      if (champs.length) payload.valeurs_champs = valeursChamps
      const call = signataireMode
        ? gedApi.signerSignataire(token, payload)
        : gedApi.signerPublique(token, payload)
      await call
      setStatus('done')
      setDemande((d) => ({ ...(d || {}), statut: 'signe' }))
    } catch (err) {
      const st = err?.response?.status
      setError(errMessage(err, 'La signature n’a pas pu être enregistrée.'))
      if (st === 410) setStatus('done')
    } finally {
      setSubmitting(false)
    }
  }

  const refuser = async () => {
    if (!motif.trim()) {
      setError('Merci d’indiquer un motif de refus.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      const call = signataireMode
        ? gedApi.refuserSignataire(token, { motif: motif.trim() })
        : gedApi.refuserPublique(token, { motif: motif.trim() })
      await call
      setStatus('done')
      setDemande((d) => ({ ...(d || {}), statut: 'refuse' }))
    } catch (err) {
      setError(errMessage(err, 'Le refus n’a pas pu être enregistré.'))
    } finally {
      setSubmitting(false)
    }
  }

  const docNom = demande?.document_nom
  const docId = demande?.document_id
  const signataireNom = demande?.signataire_nom || demande?.nom

  return (
    <div className="ui-root page" style={{ maxWidth: 640, margin: '40px auto', padding: '0 16px' }}>
      <NoIndex />
      <h2>Signature électronique</h2>
      <p className="text-sm text-muted-foreground">
        Signature à valeur légale (loi 53-05). Consultez le document avant de signer.
      </p>

      {status === 'loading' && <p role="status">Chargement…</p>}

      {status === 'invalid' && (
        <p role="alert" className="page-error">{error}</p>
      )}

      {status === 'done' && (
        <div role="status" className="page-card" style={{ marginTop: 16 }}>
          {(demande?.statut || demande?.demande_statut) === 'refuse'
            ? <p>Vous avez refusé de signer ce document. Merci, votre décision a été enregistrée.</p>
            : <p>Merci{signataireNom ? ` ${signataireNom}` : ''} ! Votre signature a bien été enregistrée.</p>}
          {error && <p className="text-sm text-muted-foreground">{error}</p>}
        </div>
      )}

      {status === 'valid' && (
        <div style={{ marginTop: 16 }}>
          {docNom && (
            <p>
              Document à signer : <strong>{docNom}</strong>
              {signataireNom ? <> — destinataire : <strong>{signataireNom}</strong></> : null}
            </p>
          )}

          {docId && (
            <DocumentApercu documentId={docId} />
          )}

          {error && <p role="alert" className="page-error">{error}</p>}

          {/* ZGED2 — code d'authentification extra avant de débloquer la signature. */}
          {otpRequis ? (
            <div className="page-card" style={{ marginTop: 16 }}>
              <p className="text-sm">
                Un code de vérification est requis avant de signer.
              </p>
              {!codeEnvoye ? (
                <Button type="button" onClick={envoyerCode}>Recevoir un code</Button>
              ) : (
                <div className="flex flex-col gap-2" style={{ marginTop: 8 }}>
                  <label className="form-label" htmlFor="ged-otp">Code reçu</label>
                  <input
                    id="ged-otp"
                    className="form-control"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                  />
                  <Button type="button" onClick={validerCode} disabled={submitting || !code.trim()}>
                    {submitting ? 'Vérification…' : 'Valider le code'}
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); signer() }} noValidate style={{ marginTop: 16 }}>
              {/* XGED3 — champs positionnés à remplir. */}
              {champs.filter((c) => CHAMP_SAISIE.has(c.type_champ)).map((c) => (
                <div key={c.id} style={{ marginBottom: 12 }}>
                  <label className="form-label" htmlFor={`champ-${c.id}`}>
                    {c.type_champ_ref_detail?.libelle || libelleChamp(c.type_champ)}
                    {c.requis ? ' *' : ''}
                  </label>
                  {c.type_champ === 'case' ? (
                    <input
                      id={`champ-${c.id}`}
                      type="checkbox"
                      checked={!!valeursChamps[c.id]}
                      onChange={(e) => setValeurChamp(c.id, e.target.checked ? '1' : '')}
                    />
                  ) : (
                    <input
                      id={`champ-${c.id}`}
                      type={c.type_champ === 'date' ? 'date' : 'text'}
                      className="form-control"
                      value={valeursChamps[c.id] ?? ''}
                      onChange={(e) => setValeurChamp(c.id, e.target.value)}
                      placeholder={c.type_champ_ref_detail?.placeholder || ''}
                    />
                  )}
                </div>
              ))}

              <div style={{ marginBottom: 12 }}>
                <label className="form-label" htmlFor="ged-sig-nom">
                  Votre nom (apposé comme signature)
                </label>
                <input
                  id="ged-sig-nom"
                  className="form-control"
                  value={signatureTexte}
                  onChange={(e) => setSignatureTexte(e.target.value)}
                  placeholder={signataireNom || 'Prénom Nom'}
                />
              </div>

              <label className="flex items-center gap-2" style={{ marginBottom: 12 }}>
                <input
                  type="checkbox"
                  checked={consentement}
                  onChange={(e) => setConsentement(e.target.checked)}
                />
                <span className="text-sm">
                  Je consens à signer ce document par voie électronique et
                  reconnais la valeur juridique de cette signature (loi 53-05).
                </span>
              </label>

              <div className="flex gap-2">
                <Button type="submit" disabled={submitting || !consentement}>
                  {submitting ? 'Signature…' : 'Signer le document'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowRefus((v) => !v)}
                >
                  Refuser
                </Button>
              </div>

              {showRefus && (
                <div className="page-card" style={{ marginTop: 16 }}>
                  <label className="form-label" htmlFor="ged-refus-motif">
                    Motif du refus
                  </label>
                  <textarea
                    id="ged-refus-motif"
                    className="form-control"
                    value={motif}
                    onChange={(e) => setMotif(e.target.value)}
                    rows={3}
                  />
                  <Button
                    type="button"
                    variant="destructive"
                    onClick={refuser}
                    disabled={submitting || !motif.trim()}
                    style={{ marginTop: 8 }}
                  >
                    {submitting ? 'Envoi…' : 'Confirmer le refus'}
                  </Button>
                </div>
              )}
            </form>
          )}
        </div>
      )}
    </div>
  )
}

function libelleChamp(type) {
  return ({
    texte: 'Texte', date: 'Date', case: 'Case à cocher',
    signature: 'Signature', initiales: 'Initiales',
  })[type] || 'Champ'
}

/**
 * GED14 — Aperçu inline du document via le proxy même-origine. On récupère la
 * dernière version du document puis on l'affiche dans un <iframe> (PDF/texte)
 * ou <img> selon le mime. Dégrade proprement en lien de consultation si
 * l'aperçu échoue (jamais un écran cassé).
 */
function DocumentApercu({ documentId }) {
  const [version, setVersion] = useState(null)
  const [failed, setFailed] = useState(false)
  const done = useRef(false)

  useEffect(() => {
    if (done.current) return
    done.current = true
    gedApi.getVersions({ document: documentId })
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
        // La version courante = la plus récente (numéro le plus élevé).
        const courante = [...list].sort(
          (a, b) => (b.numero || 0) - (a.numero || 0))[0]
        if (courante) setVersion(courante)
        else setFailed(true)
      })
      .catch(() => setFailed(true))
  }, [documentId])

  if (failed) {
    return (
      <p className="text-sm text-muted-foreground" style={{ marginTop: 8 }}>
        L’aperçu du document n’est pas disponible ; vous pouvez tout de même signer ci-dessous.
      </p>
    )
  }
  if (!version) {
    return <p className="text-sm text-muted-foreground" style={{ marginTop: 8 }}>Chargement de l’aperçu…</p>
  }
  const src = gedApi.apercuVersionUrl(version.id)
  const isImage = String(version.mime || '').startsWith('image/')
  return (
    <div style={{ marginTop: 12, marginBottom: 12 }}>
      {isImage ? (
        <img
          src={src}
          alt={`Aperçu de ${version.filename || 'document'}`}
          style={{ maxWidth: '100%', border: '1px solid var(--border, #ddd)', borderRadius: 6 }}
        />
      ) : (
        <iframe
          title="Aperçu du document"
          src={src}
          style={{ width: '100%', height: 420, border: '1px solid var(--border, #ddd)', borderRadius: 6 }}
        />
      )}
    </div>
  )
}
