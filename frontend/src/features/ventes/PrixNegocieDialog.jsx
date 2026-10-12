// VNT73 (Groupe VNT, D-VNT-2) — « Prix négocié » sur une vente acceptée : le
// commercial tape le prix TTC convenu (ou une remise), l'écran affiche l'aperçu
// SERVEUR (remise la plus ronde, factures annulées / reprises, régularisation,
// reste à facturer), puis applique en un geste (V2 acceptée, facturation reprise).
// Aucune arithmétique de vente côté écran : la remise en MAD tapée est seulement
// convertie en `prix_ttc` (prix actuel − remise, en centimes entiers) ; tout ce
// qui est affiché vient de la réponse. Contrat :
// apps/ventes/contract_samples/devis_prix_negocie.json.
// Règle fondateur « erreurs → le champ fautif » : message sous le champ nommé +
// bandeau `Corrigez : …` ; `approbation_requise` / 409 en bandeau ;
// `avoir_a_confirmer` en case à cocher. « Faire signer l'avenant » (D-ADEV-6)
// copie le lien de la V2 et pose la tâche unique côté serveur.
import { useEffect, useRef, useState } from 'react'
import ventesApi from '../../api/ventesApi'
import { Button, Input, FormField, Switch, Label, toast } from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatMAD } from '../../lib/format'

const DEBOUNCE_MS = 350
const CHAMPS_VIDES = { prix: '', remiseMad: '', remisePct: '' }
const LIBELLES = { prix: 'Prix négocié TTC', remiseMad: 'Remise (MAD)', remisePct: 'Remise (%)' }
// Codes 400 qui désignent LE champ tapé (jamais un champ que l'écran n'a pas).
const CODES_CHAMP = ['prix_non_rond', 'prix_inatteignable', 'prix_superieur',
  'prix_identique', 'saisie_vide', 'saisie_double']
const REPLI = 'Opération impossible pour le moment.'

const norm = (v) => String(v ?? '').replace(/[\s\u00a0\u202f]/g, '').replace(',', '.')
const decimalValide = (s) => /^\d+(\.\d+)?$/.test(s)
const centimes = (s) => Math.round(parseFloat(s) * 100)
const pourcent = (s) => `${String(s ?? '').replace('.', ',')} %`

/** Le champ rempli (les trois s'excluent), ou null. */
function champActif(champs) {
  return ['prix', 'remiseMad', 'remisePct'].find((k) => champs[k] !== '') || null
}

/** Corps de la requête (valeurs en TEXTE) ; null tant que la saisie n'est pas un nombre. */
function corpsDepuis(champs, totalActuel, confirmerAvoir) {
  const actif = champActif(champs)
  if (!actif) return null
  const saisie = norm(champs[actif])
  if (!decimalValide(saisie)) return null
  let corps
  if (actif === 'prix') corps = { prix_ttc: saisie }
  else if (actif === 'remisePct') corps = { remise_pct: saisie }
  else {
    if (!decimalValide(norm(totalActuel))) return null
    corps = { prix_ttc: ((centimes(norm(totalActuel)) - centimes(saisie)) / 100).toFixed(2) }
  }
  if (confirmerAvoir) corps.confirmer_avoir = true
  return corps
}

function lireErreur(err) {
  const status = err?.response?.status || 0
  const data = err?.response?.data
  const objet = data && typeof data === 'object' && !Array.isArray(data) ? data : {}
  const detail = typeof objet.detail === 'string' && objet.detail ? objet.detail : ''
  return { status, code: objet.code || '', detail: detail || REPLI, data: objet }
}

/** « Faire signer l'avenant » : lien copié + tâche unique (idempotent côté serveur). */
export function FaireSignerAvenant({ devisId }) {
  const [etat, setEtat] = useState({ phase: 'repos' })
  const faire = async () => {
    setEtat({ phase: 'charge' })
    try {
      const { data } = await ventesApi.demanderSignatureAvenant(devisId)
      let copie = false
      try {
        await navigator.clipboard.writeText(data.share_link)
        copie = true
      } catch { /* presse-papiers refusé : le lien reste affiché, copiable à la main */ }
      if (copie) toast.success('Lien de signature copié')
      setEtat({ phase: 'fait', lien: data.share_link, tache: data.tache_id ?? null, copie })
    } catch (err) {
      setEtat({ phase: 'erreur', message: lireErreur(err).detail })
    }
  }
  if (etat.phase === 'fait') {
    return (
      <div className="grid gap-1.5" data-testid="avenant-signature">
        <p className="text-sm">
          {etat.copie ? 'Lien copié dans le presse-papiers.' : 'Copiez le lien ci-dessous.'}
          {etat.tache != null && ' La tâche « Faire signer l\'avenant » est posée.'}
        </p>
        <Input readOnly aria-label="Lien de signature de l'avenant" data-testid="avenant-lien"
               value={etat.lien} onFocus={(e) => e.target.select()} />
      </div>
    )
  }
  return (
    <div className="grid gap-1.5">
      <Button type="button" variant="outline" loading={etat.phase === 'charge'} onClick={faire}>
        Faire signer l'avenant
      </Button>
      {etat.phase === 'erreur' && (
        <p role="alert" className="text-xs text-destructive" data-testid="avenant-erreur">{etat.message}</p>
      )}
    </div>
  )
}

function Apercu({ apercu }) {
  const reg = apercu.regularisation || {}
  const annulees = apercu.factures_annulees || []
  const reprises = apercu.factures_reprises || []
  return (
    <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-0.5 rounded-md border p-2 text-sm"
        data-testid="prix-negocie-apercu">
      <dt>Remise</dt>
      <dd className="text-right font-medium tabular-nums" data-testid="prix-negocie-remise">
        {pourcent(apercu.remise_pct)}
      </dd>
      <dt>Nouveau prix TTC</dt>
      <dd className="text-right tabular-nums" data-testid="prix-negocie-total">{formatMAD(apercu.total_ttc)}</dd>
      <dt>Écart</dt>
      <dd className="text-right tabular-nums" data-testid="prix-negocie-ecart">{formatMAD(apercu.ecart_ttc)}</dd>
      <dt>Factures annulées</dt>
      <dd className="text-right" data-testid="prix-negocie-annulees">
        {annulees.length ? annulees.map((f) => f.reference).join(', ') : 'Aucune'}
      </dd>
      <dt>Factures reprises</dt>
      <dd className="text-right" data-testid="prix-negocie-reprises">
        {reprises.length
          ? reprises.map((f) => `${f.reference} (${formatMAD(f.total_ttc)})`).join(', ')
          : 'Aucune'}
      </dd>
      <dt>Régularisation</dt>
      <dd className="text-right" data-testid="prix-negocie-regularisation">
        {reg.type === 'avoir' && `Un avoir de ${formatMAD(reg.montant)} sera émis`}
        {reg.type === 'complement' && `Complément à encaisser : ${formatMAD(reg.montant)}`}
        {(!reg.type || reg.type === 'aucune') && 'Aucune'}
      </dd>
      <dt className="font-medium">Reste à facturer</dt>
      <dd className="text-right font-medium tabular-nums" data-testid="prix-negocie-reste">
        {formatMAD(apercu.reste_a_facturer)}
      </dd>
    </dl>
  )
}

function CorpsPrixNegocie({ devis, onOpenChange, onApplied, onOuvrirDevis }) {
  const totalActuel = devis.vente?.prix_convenu_ttc ?? devis.total_ttc
  const [champs, setChamps] = useState(CHAMPS_VIDES)
  const [apercu, setApercu] = useState(null)
  const [apercuPour, setApercuPour] = useState('')
  const [erreur, setErreur] = useState(null)
  const [avoirConfirme, setAvoirConfirme] = useState(false)
  const [montantAvoir, setMontantAvoir] = useState('')
  const [saving, setSaving] = useState(false)
  const [resultat, setResultat] = useState(null)
  const minuteur = useRef(null)
  const sequence = useRef(0)

  useEffect(() => () => { clearTimeout(minuteur.current) }, [])

  const actif = champActif(champs)
  const corpsCourant = corpsDepuis(champs, totalActuel, avoirConfirme)
  const clePourCourant = corpsCourant ? JSON.stringify(corpsCourant) : ''
  const pret = !!apercu && apercuPour === clePourCourant && !saving

  const traiterErreur = (err) => {
    const e = lireErreur(err)
    setErreur(e)
    setApercu(null)
    if (e.code === 'avoir_a_confirmer') setMontantAvoir(e.data.montant_avoir || '')
  }

  const lancerApercu = async (nouveauxChamps, confirmer) => {
    const corps = corpsDepuis(nouveauxChamps, totalActuel, confirmer)
    if (!corps) return
    const mon = ++sequence.current
    try {
      const { data } = await ventesApi.prixNegocie(devis.id, { ...corps, mode: 'apercu' })
      if (mon !== sequence.current) return
      setApercu(data)
      setApercuPour(JSON.stringify(corps))
      setErreur(null)
    } catch (err) {
      if (mon !== sequence.current) return
      traiterErreur(err)
    }
  }

  const reinitialiser = () => {
    clearTimeout(minuteur.current)
    sequence.current += 1
    setApercu(null)
    setErreur(null)
    setAvoirConfirme(false)
    setMontantAvoir('')
  }

  const saisir = (cle, valeur) => {
    const nouveaux = { ...CHAMPS_VIDES, [cle]: valeur }
    setChamps(nouveaux)
    reinitialiser()
    if (valeur !== '') {
      minuteur.current = setTimeout(() => lancerApercu(nouveaux, false), DEBOUNCE_MS)
    }
  }

  const utiliserVoisin = (prix) => {
    const nouveaux = { ...CHAMPS_VIDES, prix: String(prix) }
    setChamps(nouveaux)
    reinitialiser()
    lancerApercu(nouveaux, false)
  }

  const confirmerAvoir = (coche) => {
    setAvoirConfirme(coche)
    setApercu(null)
    setErreur(null)
    lancerApercu(champs, coche)
  }

  const appliquer = async () => {
    if (!pret) return
    setSaving(true)
    setErreur(null)
    try {
      const { data } = await ventesApi.prixNegocie(devis.id, { ...corpsCourant, mode: 'appliquer' })
      setResultat(data)
      onApplied?.(data)
    } catch (err) {
      traiterErreur(err)
    } finally {
      setSaving(false)
    }
  }

  if (resultat) {
    const v2 = resultat.devis_v2 || {}
    return (
      <div className="grid gap-3" data-testid="prix-negocie-resultat">
        <p className="text-sm">
          Prix négocié appliqué : {v2.reference} (version {v2.version}) à{' '}
          {formatMAD(resultat.total_ttc)}, remise {pourcent(resultat.remise_pct)}.
        </p>
        <Apercu apercu={resultat} />
        {v2.id != null && <FaireSignerAvenant devisId={v2.id} />}
        <div className="flex justify-end">
          <Button type="button" variant="ghost" onClick={() => onOpenChange?.(false)}>Fermer</Button>
        </div>
      </div>
    )
  }

  // Erreur rattachée au champ tapé (jamais un message flottant).
  const surChamp = erreur && CODES_CHAMP.includes(erreur.code) ? (actif || 'prix') : null
  let messageChamp = erreur?.detail || ''
  if (erreur?.code === 'prix_non_rond' && erreur.data.multiple) {
    messageChamp += ` Multiple de ${formatMAD(erreur.data.multiple)} attendu.`
  }
  const voisins = erreur?.code === 'prix_inatteignable' && Array.isArray(erreur.data.prix_atteignables)
    ? erreur.data.prix_atteignables : []
  const erreurDe = (cle) => (surChamp === cle ? messageChamp : undefined)
  const decrit = (cle, id) => (surChamp === cle
    ? { id, 'aria-describedby': `${id}-error`, 'aria-invalid': true } : { id })

  let bandeau = ''
  if (surChamp) bandeau = `Corrigez : ${LIBELLES[surChamp]}`
  else if (erreur && erreur.code !== 'avoir_a_confirmer') bandeau = erreur.detail
  const cible = erreur?.data?.successeur || erreur?.data?.vente_active || null
  const montantAvoirAffiche = apercu?.regularisation?.type === 'avoir'
    ? apercu.regularisation.montant : montantAvoir
  const avoirVisible = erreur?.code === 'avoir_a_confirmer' || avoirConfirme

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); appliquer() }}
      className="grid gap-3"
      noValidate
      data-testid="prix-negocie-form"
    >
      <p className="text-sm text-muted-foreground" data-testid="prix-negocie-actuel">
        Prix actuel : {formatMAD(totalActuel)}
      </p>
      <div className="grid gap-2 sm:grid-cols-3">
        <FormField label="Prix négocié TTC (MAD)" htmlFor="pn-prix" error={erreurDe('prix')}>
          <Input type="text" inputMode="decimal" aria-label="Prix négocié TTC (MAD)"
                 value={champs.prix} onChange={(e) => saisir('prix', e.target.value)}
                 {...decrit('prix', 'pn-prix')} />
        </FormField>
        <FormField label="Remise (MAD)" htmlFor="pn-remise-mad" error={erreurDe('remiseMad')}>
          <Input type="text" inputMode="decimal" aria-label="Remise (MAD)"
                 value={champs.remiseMad} onChange={(e) => saisir('remiseMad', e.target.value)}
                 {...decrit('remiseMad', 'pn-remise-mad')} />
        </FormField>
        <FormField label="Remise (%)" htmlFor="pn-remise-pct" error={erreurDe('remisePct')}>
          <Input type="text" inputMode="decimal" aria-label="Remise (%)"
                 value={champs.remisePct} onChange={(e) => saisir('remisePct', e.target.value)}
                 {...decrit('remisePct', 'pn-remise-pct')} />
        </FormField>
      </div>

      {voisins.length > 0 && (
        <div className="flex flex-wrap items-center gap-2" data-testid="prix-negocie-voisins">
          <span className="text-xs text-muted-foreground">Prix atteignables :</span>
          {voisins.map((p) => (
            <Button key={p} type="button" size="sm" variant="outline" onClick={() => utiliserVoisin(p)}>
              {formatMAD(p)}
            </Button>
          ))}
        </div>
      )}

      {avoirVisible && (
        <div className="flex items-center justify-between gap-3 rounded-md border p-2 text-sm"
             data-testid="prix-negocie-avoir">
          <Label htmlFor="pn-avoir">
            Un avoir de {formatMAD(montantAvoirAffiche)} sera émis (le déjà facturé dépasse le nouveau prix).
          </Label>
          <Switch id="pn-avoir" aria-label="Confirmer l'avoir" checked={avoirConfirme}
                  onCheckedChange={confirmerAvoir} />
        </div>
      )}

      {bandeau && (
        <div className="grid gap-2">
          <div role="alert" data-testid="prix-negocie-bandeau"
               className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm text-destructive">
            {bandeau}
          </div>
          {cible?.reference && cible.id != null && (
            <Button type="button" variant="outline" onClick={() => onOuvrirDevis?.(cible.id)}>
              Ouvrir {cible.reference}
            </Button>
          )}
        </div>
      )}

      {apercu && <Apercu apercu={apercu} />}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={() => onOpenChange?.(false)}>Annuler</Button>
        <Button type="submit" loading={saving} disabled={!pret}>Appliquer le prix négocié</Button>
      </div>
    </form>
  )
}

export default function PrixNegocieDialog({ devis, onOpenChange, onApplied, onOuvrirDevis }) {
  return (
    <ResponsiveDialog
      open={!!devis}
      onOpenChange={(o) => { if (!o) onOpenChange?.(false) }}
      title={`Prix négocié — ${devis?.reference ?? ''}`}
      description={`${devis?.client_nom ? `${devis.client_nom} — ` : ''}Tapez le prix TTC convenu ou une remise : l'aperçu montre l'effet avant d'appliquer.`}
    >
      {devis && (
        <CorpsPrixNegocie key={devis.id} devis={devis} onOpenChange={onOpenChange}
                          onApplied={onApplied} onOuvrirDevis={onOuvrirDevis} />
      )}
    </ResponsiveDialog>
  )
}
