import { useState, useEffect } from 'react'
import { Button, FormField, Input } from '../../../../ui'
import { getField, isSuggested } from '../draftCore'
import { useDuplicateCheck } from '../../../../hooks/useDuplicateCheck'
import { usePasteClean, parsePastedPhone, parsePasteCard } from '../../../../hooks/usePasteClean'
import PhoneHint from '../../../../components/PhoneHint'

// LW11 — Contact & site : port 1:1 des champs (recon 01 §2). Présentation pure ;
// tout l'état de données vit dans le moteur (`state`/`setField`). La détection
// de carte de visite (VX237) est une interaction locale éphémère, remise à zéro
// à chaque changement de lead (jamais de fuite inter-leads).
export default function SectionContact({ state, setField, errors = {}, mode, refData = {} }) {
  const v = (k) => getField(state, k) ?? ''
  const { leadId, onOpenDuplicate } = refData

  // VX237 — collage d'une carte de visite dans « Nom » : { nom, telephone }
  // détectés, JAMAIS répartis en silence — un bandeau propose « Répartir ».
  const [cardPaste, setCardPaste] = useState(null)
  useEffect(() => { setCardPaste(null) }, [state.leadId]) // scope lead
  const onNomPaste = (e) => {
    const text = e.clipboardData?.getData('text')
    const card = parsePasteCard(text)
    if (card) setCardPaste(card)
  }
  const applyCardPaste = () => {
    if (!cardPaste) return
    setField('nom', cardPaste.nom)
    setField('telephone', cardPaste.telephone)
    setCardPaste(null)
  }
  // VX237 — collage téléphone/WhatsApp nettoyé (espaces/points/tirets tolérés).
  const onTelephonePaste = usePasteClean(parsePastedPhone, (clean) => setField('telephone', clean))
  const onWhatsappPaste = usePasteClean(parsePastedPhone, (clean) => setField('whatsapp', clean))

  // VX239 — avertissement doublon EN DIRECT (non bloquant). En édition on exclut
  // le lead courant de ses propres doublons.
  const dupMatches = useDuplicateCheck(v('telephone'), v('email'), {
    exclude: mode === 'edit' ? leadId : undefined,
  })

  const villeSuggested = isSuggested(state, 'ville')

  return (
    <>
      {dupMatches.length > 0 && (
        <div className="lw-dup-warning" role="status">
          ⚠️ Un lead avec ce numéro existe déjà
          {dupMatches.length > 1 ? ` (${dupMatches.length})` : ''} :{' '}
          {dupMatches.slice(0, 3).map((d, i) => (
            <span key={d.id}>
              {i > 0 && ', '}
              <button type="button" className="lw-dup-link" onClick={() => onOpenDuplicate?.(d.id)}>
                {`${d.nom} ${d.prenom || ''}`.trim() || `#${d.id}`}
                {d.is_archived ? ' (archivé)' : ''}
              </button>
            </span>
          ))}
          {dupMatches.length > 3 && '…'}
        </div>
      )}
      <div className="form-row">
        <div className="form-group fg-grow">
          <FormField label="Nom" required htmlFor="lf-nom" error={errors.nom} errorKind="required">
            <Input
              id="lf-nom" autoFocus={mode === 'create'} invalid={!!errors.nom}
              value={v('nom')} onChange={(e) => setField('nom', e.target.value)}
              onPaste={onNomPaste}
            />
          </FormField>
          {cardPaste && (
            <div
              role="status"
              className="mt-1.5 flex flex-wrap items-center gap-2 rounded-md border border-info/30 bg-info/5 px-2.5 py-1.5 text-xs text-foreground"
            >
              <span>Carte de visite détectée — {cardPaste.nom} · {cardPaste.telephone}</span>
              <Button type="button" variant="outline" size="sm" onClick={applyCardPaste}>Répartir</Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setCardPaste(null)}>Ignorer</Button>
            </div>
          )}
        </div>
        <FormField label="Prénom" htmlFor="lf-prenom">
          <Input id="lf-prenom" value={v('prenom')} onChange={(e) => setField('prenom', e.target.value)} />
        </FormField>
        <FormField label="Téléphone" htmlFor="lf-telephone">
          <Input
            id="lf-telephone" value={v('telephone')}
            onChange={(e) => setField('telephone', e.target.value)} onPaste={onTelephonePaste}
          />
          <PhoneHint value={v('telephone')} testId="lf-tel-hint" />
        </FormField>
      </div>
      <div className="form-row">
        <FormField label="WhatsApp" htmlFor="lf-whatsapp">
          <Input
            id="lf-whatsapp" value={v('whatsapp')}
            onChange={(e) => setField('whatsapp', e.target.value)} onPaste={onWhatsappPaste}
          />
        </FormField>
        <FormField
          label="Ville / quartier"
          htmlFor="lf-ville"
          hint={villeSuggested ? 'Suggéré — modifiable' : undefined}
        >
          <Input
            id="lf-ville"
            className={villeSuggested ? 'vx-suggested-field' : undefined}
            value={v('ville')} onChange={(e) => setField('ville', e.target.value)}
          />
        </FormField>
        <div className="form-group">
          <FormField label="Email" htmlFor="lf-email" error={errors.email}>
            <Input
              id="lf-email" type="email" invalid={!!errors.email}
              value={v('email')} onChange={(e) => setField('email', e.target.value)}
            />
          </FormField>
        </div>
      </div>
      <div className="form-row">
        <FormField label="Société" htmlFor="lf-societe">
          <Input id="lf-societe" value={v('societe')} onChange={(e) => setField('societe', e.target.value)} />
        </FormField>
        <div className="form-group fg-grow">
          <FormField label="Adresse" htmlFor="lf-adresse">
            <Input id="lf-adresse" value={v('adresse')} onChange={(e) => setField('adresse', e.target.value)} />
          </FormField>
        </div>
        <FormField label="GPS lat." htmlFor="lf-gps-lat">
          <Input id="lf-gps-lat" type="number" step="any" value={v('gps_lat')} onChange={(e) => setField('gps_lat', e.target.value)} />
        </FormField>
        <FormField label="GPS long." htmlFor="lf-gps-lng">
          <Input id="lf-gps-lng" type="number" step="any" value={v('gps_lng')} onChange={(e) => setField('gps_lng', e.target.value)} />
        </FormField>
      </div>
      {v('gps_lat') && v('gps_lng') && (
        <div className="form-row">
          <a
            className="lw-gps-link"
            href={`https://maps.google.com/?q=${encodeURIComponent(v('gps_lat'))},${encodeURIComponent(v('gps_lng'))}`}
            target="_blank" rel="noopener noreferrer"
          >
            📍 Voir sur la carte
          </a>
        </div>
      )}
    </>
  )
}
