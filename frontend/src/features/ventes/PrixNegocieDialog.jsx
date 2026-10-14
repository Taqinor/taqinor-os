import { useState } from 'react'
import ventesApi from '../../api/ventesApi'
import { formatMAD } from '../../lib/format'
import { toastError, toastSuccess } from '../../lib/toast'
import { Button, Checkbox, Input, Label } from '../../ui'
import ResponsiveDialog from '../../ui/ResponsiveDialog'

/* ============================================================================
   VNT73 — « Prix négocié » : le client négocie un prix TTC rond, le serveur le
   convertit en remise, crée la V2 et reprend la facturation.
   Contrat : apps/ventes/contract_samples/devis_prix_negocie.json.
   Le serveur décide de tout (remise la plus ronde, factures annulées/reprises,
   reste) : l'écran n'affiche QUE l'aperçu renvoyé. Les montants sont 100 % TTC ;
   les champs restent libres (step="any", aucune saisie arrondie ni rejetée).
   Une remise tapée en MAD est convertie en `prix_ttc` (prix actuel − remise) en
   centimes entiers, jamais en flottant.
   ========================================================================== */

const CODES_SOUS_LE_CHAMP = new Set([
  'prix_non_rond', 'prix_inatteignable', 'prix_superieur', 'prix_identique',
  'saisie_double', 'saisie_vide',
])

const MESSAGE_LOCAL = {
  saisie_vide: 'Indiquez un prix TTC ou une remise.',
  saisie_double: 'Indiquez le prix TTC OU la remise, pas les deux.',
}

const centimes = (txt) => {
  const m = String(txt ?? '').trim().replace(',', '.').match(/^(\d+)(?:\.(\d*))?$/)
  if (!m) return null
  return Number(m[1]) * 100 + Number(`${m[2] || ''}00`.slice(0, 2))
}
const enTexte = (c) => `${Math.floor(c / 100)}.${String(c % 100).padStart(2, '0')}`
const net = (v) => String(v).trim().replace(',', '.')

// Le corps de requête : exactement UN champ rempli (prix TTC, remise % ou remise MAD).
function corpsSaisie({ prix, pct, mad }, totalTtc) {
  const remplis = [prix, pct, mad].filter((v) => String(v).trim() !== '')
  if (remplis.length !== 1) return { erreur: remplis.length ? 'saisie_double' : 'saisie_vide' }
  if (String(prix).trim() !== '') return { corps: { prix_ttc: net(prix) } }
  if (String(pct).trim() !== '') return { corps: { remise_pct: net(pct) } }
  const total = centimes(totalTtc)
  const remise = centimes(mad)
  if (total === null || remise === null) return { erreur: 'saisie_vide' }
  return { corps: { prix_ttc: enTexte(Math.max(total - remise, 0)) } }
}

function formatPct(v) {
  const n = Number(String(v ?? '').replace(',', '.'))
  return Number.isFinite(n) ? `${n.toFixed(2).replace('.', ',')} %` : '—'
}

export default function PrixNegocieDialog({ devis, open, onOpenChange, onApplied }) {
  const [saisie, setSaisie] = useState({ prix: '', pct: '', mad: '' })
  const [apercu, setApercu] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [avoirConfirme, setAvoirConfirme] = useState(false)
  const [occupe, setOccupe] = useState(false)
  const [applique, setApplique] = useState(null)
  const [signature, setSignature] = useState(null)
  const [signatureEnCours, setSignatureEnCours] = useState(false)

  const modifier = (cle) => (e) => {
    setSaisie((s) => ({ ...s, [cle]: e.target.value }))
    setApercu(null)
    setErreur(null)
  }

  const lancer = async (mode) => {
    const { corps, erreur: locale } = corpsSaisie(saisie, devis?.total_ttc)
    if (locale) {
      setErreur({ code: locale, detail: MESSAGE_LOCAL[locale] })
      return
    }
    setOccupe(true)
    setErreur(null)
    try {
      const body = { ...corps, mode }
      if (avoirConfirme) body.confirmer_avoir = true
      const { data } = await ventesApi.prixNegocie(devis.id, body)
      if (mode === 'apercu') setApercu(data)
      else {
        setApplique(data)
        toastSuccess('Prix négocié appliqué : version 2 créée.')
        if (onApplied) onApplied(data)
      }
    } catch (err) {
      const data = err?.response?.data
      if (data?.code) setErreur(data)
      else {
        setErreur({ code: 'inconnue', detail: data?.detail || 'Le prix négocié n\'a pas pu être traité.' })
        toastError('Le prix négocié n\'a pas pu être traité.')
      }
    } finally {
      setOccupe(false)
    }
  }

  const faireSignerAvenant = async () => {
    if (signature || signatureEnCours || !applique?.devis_v2?.id) return
    setSignatureEnCours(true)
    try {
      const { data } = await ventesApi.demanderSignatureAvenant(applique.devis_v2.id)
      setSignature(data)
      try {
        await navigator.clipboard.writeText(data.share_link)
        toastSuccess('Lien de signature copié.')
      } catch {
        toastError('Copie du lien impossible : copiez-le depuis la page.')
      }
    } catch {
      toastError('Demande de signature impossible.')
    } finally {
      setSignatureEnCours(false)
    }
  }

  const erreurChamp = erreur && CODES_SOUS_LE_CHAMP.has(erreur.code) ? erreur : null
  const bandeau = erreur && !CODES_SOUS_LE_CHAMP.has(erreur.code) ? erreur : null
  const resultat = applique || apercu

  const champ = (id, libelle, cle) => (
    <div className="space-y-1">
      <Label htmlFor={id}>{libelle}</Label>
      <Input id={id} type="number" step="any" inputMode="decimal"
             value={saisie[cle]} onChange={modifier(cle)}
             disabled={Boolean(applique)}
             aria-invalid={cle === 'prix' && erreurChamp ? true : undefined}
             aria-describedby={cle === 'prix' && erreurChamp ? 'prix-negocie-erreur' : undefined} />
    </div>
  )

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Prix négocié"
      description={`Prix actuel : ${formatMAD(devis?.total_ttc)} TTC. Le serveur calcule la remise et ses effets.`}
      footer={(
        <>
          <Button type="button" variant="outline" onClick={() => onOpenChange?.(false)}>
            Fermer
          </Button>
          {!applique && (
            <>
              <Button type="button" variant="outline" disabled={occupe}
                      onClick={() => lancer('apercu')}>
                Voir les effets
              </Button>
              <Button type="button" disabled={occupe || !apercu}
                      onClick={() => lancer('appliquer')}>
                Appliquer le prix négocié
              </Button>
            </>
          )}
        </>
      )}
    >
      <div className="space-y-3">
        {champ('prix-negocie-prix', 'Nouveau prix TTC (MAD)', 'prix')}
        {erreurChamp && (
          <div id="prix-negocie-erreur" role="alert" className="text-sm text-destructive">
            <p>{erreurChamp.detail}</p>
            {erreurChamp.code === 'prix_inatteignable' && (
              <div className="mt-1 flex flex-wrap gap-2">
                {(erreurChamp.prix_atteignables || []).map((p) => (
                  <Button key={p} type="button" size="sm" variant="outline"
                          onClick={() => {
                            setSaisie({ prix: p, pct: '', mad: '' })
                            setErreur(null)
                          }}>
                    {p}
                  </Button>
                ))}
              </div>
            )}
          </div>
        )}
        {champ('prix-negocie-pct', 'ou Remise (%)', 'pct')}
        {champ('prix-negocie-mad', 'ou Remise (MAD TTC)', 'mad')}

        {bandeau && (
          <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm">
            <p>
              {bandeau.detail}
              {bandeau.code === 'version_remplacee' && bandeau.successeur?.reference
                && ` Version à jour : ${bandeau.successeur.reference}.`}
            </p>
            {bandeau.code === 'avoir_a_confirmer' && (
              <label className="mt-1 flex items-center gap-2">
                <Checkbox checked={avoirConfirme}
                          onCheckedChange={(v) => setAvoirConfirme(v === true)}
                          aria-label="Je confirme l'émission de l'avoir" />
                Je confirme l'émission de l'avoir
              </label>
            )}
          </div>
        )}

        {resultat && (
          <dl className="space-y-1 rounded-md border p-2 text-sm" aria-label="Effets du prix négocié">
            <div className="flex justify-between"><dt>Remise</dt><dd>{formatPct(resultat.remise_pct)}</dd></div>
            <div className="flex justify-between"><dt>Nouveau total TTC</dt><dd>{formatMAD(resultat.total_ttc)}</dd></div>
            <div className="flex justify-between"><dt>Écart TTC</dt><dd>{formatMAD(resultat.ecart_ttc)}</dd></div>
            <div className="flex justify-between"><dt>Reste à facturer</dt><dd>{formatMAD(resultat.reste_a_facturer)}</dd></div>
            <div>
              <dt>Factures annulées</dt>
              <dd>{(resultat.factures_annulees || []).map((f) => f.reference).join(', ') || 'aucune'}</dd>
            </div>
            <div>
              <dt>Factures reprises</dt>
              <dd>{(resultat.factures_reprises || []).map((f) => f.reference).join(', ') || 'aucune'}</dd>
            </div>
            {resultat.regularisation && resultat.regularisation.type !== 'aucune' && (
              <div className="flex justify-between">
                <dt>Régularisation ({resultat.regularisation.type})</dt>
                <dd>{formatMAD(resultat.regularisation.montant)}</dd>
              </div>
            )}
          </dl>
        )}

        {applique && (
          <div className="space-y-2">
            <p className="text-sm">Version 2 créée : {applique.devis_v2?.reference}.</p>
            <Button type="button" disabled={Boolean(signature) || signatureEnCours}
                    onClick={faireSignerAvenant}>
              Faire signer l'avenant
            </Button>
            {signature && (
              <p className="break-all text-sm" data-testid="lien-avenant">
                {signature.share_link}
              </p>
            )}
          </div>
        )}
      </div>
    </ResponsiveDialog>
  )
}
