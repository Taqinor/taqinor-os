import { useState } from 'react'
import crmApi from '../../api/crmApi'
import { Input, Label } from '../../ui'
import { usePasteClean, parsePastedPhone } from '../../hooks/usePasteClean'
import { useDuplicateCheck } from '../../hooks/useDuplicateCheck'
import PhoneHint from '../../components/PhoneHint'
import { frErrRapide } from '../../lib/frErr'
import ModaleCreationRapide from '../../components/ModaleCreationRapide'
import ComboboxEntreprise from '../../components/ComboboxEntreprise'
import AvertissementDoublons from '../../components/AvertissementDoublons'

/* QG3 — « + Nouveau client » quick-create depuis le générateur de devis
   (chemin sans lead). Minimal : nom + téléphone/email — appelle
   crmApi.createClient (company forcée côté serveur, apps/crm/views.py
   perform_create) puis rappelle onCreated(client) pour que l'appelant
   sélectionne automatiquement le nouveau client.
   QC1 — autocomplete entreprise (données propres) : taper un nom suggère les
   clients/fournisseurs/leads existants et remplit téléphone/email au choix. */
export default function ClientQuickCreateModal({ open, onClose, onCreated }) {
  const [nom, setNom] = useState('')
  const [prenom, setPrenom] = useState('')
  const [telephone, setTelephone] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [dupWarning, setDupWarning] = useState(null)

  const reset = () => {
    setNom(''); setPrenom(''); setTelephone(''); setEmail(''); setError(null); setDupWarning(null)
  }
  const handleClose = () => { reset(); onClose?.() }
  // VX237 — collage téléphone/WhatsApp nettoyé vers la forme canonique de
  // stockage (espaces/points/tirets tolérés) au lieu de tomber brut.
  const onTelephonePaste = usePasteClean(parsePastedPhone, setTelephone)
  // VX239 — avertissement doublon EN DIRECT (jusqu'ici limité à
  // l'autocomplete NOM ci-dessus) : réutilise `useDuplicateCheck` (extrait de
  // LeadForm) dès que le téléphone/email tapé correspond à un contact connu.
  const dupMatches = useDuplicateCheck(telephone, email)

  // Remplit seulement les champs vides (jamais d'écrasement) ; avertit d'un
  // doublon quand on choisit un CLIENT existant.
  const fillFromHit = (hit) => {
    if (!hit) return
    setNom((v) => hit.nom || v)
    setTelephone((v) => (v.trim() ? v : (hit.telephone || v)))
    setEmail((v) => (v.trim() ? v : (hit.email || v)))
    setDupWarning(hit.source === 'client'
      ? `« ${hit.nom} » existe déjà comme client — vérifiez avant de recréer.`
      : null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!nom.trim()) { setError('Le nom est requis.'); return }
    setBusy(true)
    try {
      const payload = {
        nom: nom.trim(),
        prenom: prenom.trim() || null,
        telephone: telephone.trim() || null,
        email: email.trim() || null,
      }
      const res = await crmApi.createClient(payload)
      onCreated?.(res.data)
      reset()
    } catch (err) {
      setError(frErrRapide(err, 'La création du client a échoué.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <ModaleCreationRapide open={open} onFermer={handleClose} onSubmit={handleSubmit}
      titre="Nouveau client"
      description={<>
        Création rapide — vous pourrez compléter la fiche complète (ICE, adresse…)
        plus tard depuis Clients.
      </>}
      error={error} busy={busy} libelle="Créer et sélectionner" libelleEnCours="Création…">
      {/* QC1 — autocomplete entreprise (données propres). */}
      <div className="grid gap-1.5">
        <Label htmlFor="cqc-company-search">Rechercher une entreprise existante — optionnel</Label>
        <ComboboxEntreprise id="cqc-company-search" onChoisir={fillFromHit} />
        {dupWarning && (
          <p className="text-xs text-warning" data-testid="cqc-dup-warning">{dupWarning}</p>
        )}
      </div>
      {/* MB5 — sur mobile (<640px), le prénom passe sous le nom au lieu de
          se comprimer en deux colonnes de ~150px dans la feuille tactile. */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor="cqc-nom" required>Nom</Label>
          <Input id="cqc-nom" value={nom} autoFocus
                 invalid={error && !nom.trim() ? true : undefined}
                 onChange={(e) => setNom(e.target.value)}
                 placeholder="Dupont" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="cqc-prenom">Prénom</Label>
          <Input id="cqc-prenom" value={prenom}
                 onChange={(e) => setPrenom(e.target.value)}
                 placeholder="Jean" />
        </div>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="cqc-tel">Téléphone</Label>
        <Input id="cqc-tel" type="tel" value={telephone}
               onChange={(e) => setTelephone(e.target.value)}
               onPaste={onTelephonePaste}
               placeholder="+212 6 XX XX XX XX" />
        {/* VX239 — <PhoneHint> extrait de ClientForm. */}
        <PhoneHint value={telephone} testId="cqc-tel-hint" />
        <AvertissementDoublons matches={dupMatches} className="text-xs text-warning"
                               testId="cqc-dup-live-warning" />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="cqc-email">Email</Label>
        <Input id="cqc-email" type="email" value={email}
               onChange={(e) => setEmail(e.target.value)}
               placeholder="jean.dupont@exemple.com" />
      </div>
    </ModaleCreationRapide>
  )
}
