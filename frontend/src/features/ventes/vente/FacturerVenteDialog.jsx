// VNT45 (Groupe VNT, D-VNT-3) — « Facturer la vente » : UN dialogue pour
// l'acompte (montant MAD OU pourcentage), la totalité et le solde, avec
// « déjà payé » (le paiement est consigné dans le même appel atomique) ;
// remplace FacturerDevisDialog (100 % + paiements). Tout ce qui est affiché
// (prix convenu, reste, acompte proposé, prochaine tranche) est LU du serveur
// (GET devis/<id>/facturer/) — l'écran ne redérive aucun montant de la vente.
// Contrat : apps/ventes/contract_samples/devis_facturer.json.
// Règle fondateur « erreurs → le champ fautif » : message sous le champ + bandeau
// `Corrigez : …` (erreursVente.js) ; les refus métier codés (409/403) ont leur
// propre issue (émettre le brouillon, confirmer le remplacement, bandeau).
import { useCallback, useEffect, useState } from 'react'
import ventesApi from '../../../api/ventesApi'
import {
  Button, Input, FormField, Switch, Label,
  Tabs, TabsList, TabsTrigger,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  toast,
} from '../../../ui'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { formatMAD } from '../../../lib/format'
import { todayLocalIso } from '../../../lib/dateLocale.js'
import { MODES_PAIEMENT } from '../modesPaiement'
import { aplatirErreurs, erreursParChamp, bandeau } from './erreursVente'
import { ouvrirPdfFacture } from './facturePdf'

const REPLI_CHARGEMENT = "Impossible de lire l'état de la vente."
const REPLI_CREATION = 'Création de la facture impossible.'

const norm = (v) => String(v ?? '').trim().replace(/\s/g, '').replace(',', '.')
const num = (v) => {
  const n = parseFloat(norm(v))
  return Number.isFinite(n) ? n : 0
}

/** Code métier → erreur rattachée au champ fautif (sinon bandeau seul). */
function erreursDuServeur(data, { tab, pct }) {
  const liste = aplatirErreurs(data)
  const g = liste[0]
  if (liste.length !== 1 || g.cle !== 'submit' || !g.code) return liste
  const champMontant = tab === 'acompte'
    ? (pct ? { cle: 'pourcentage', libelle: 'Pourcentage' } : { cle: 'montant_ttc', libelle: 'Montant' })
    : null
  if ((g.code === 'montant_depasse_reste' || g.code === 'montant_invalide') && champMontant) {
    return [{ ...champMontant, message: g.message, code: g.code }]
  }
  if (g.code === 'paiements_invalides') {
    return [{ cle: 'paiements.0.montant', libelle: 'Paiement 1 — montant', message: g.message, code: g.code }]
  }
  return liste
}

function ongletParDefaut(apercu) {
  // Un acompte non émis (à faire ou brouillon VNT62) passe avant la « prochaine » tranche :
  // le plan saute le brouillon, mais « Créer » doit reprendre CE brouillon (sinon 409).
  const acompteNonEmis = (apercu?.plan || []).find((t) => t.cle === 'acompte' && t.statut !== 'emise')
  if (acompteNonEmis) return 'acompte'
  const cle = apercu?.prochaine?.cle || ''
  if (cle.startsWith('intermediaire')) return 'intermediaire'
  if (cle === 'solde') return 'solde'
  const acompte = (apercu?.plan || []).find((t) => t.cle === 'acompte')
  return acompte && acompte.statut === 'emise' ? 'complete' : 'acompte'
}

const NATURE_PAR_ONGLET = {
  acompte: 'acompte', intermediaire: 'intermediaire', solde: 'solde', complete: 'complete',
}

function CorpsFacturer({ devis, onOpenChange, onDone }) {
  const [apercu, setApercu] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [erreurChargement, setErreurChargement] = useState('')
  const [tab, setTab] = useState('acompte')
  const [montant, setMontant] = useState('')
  const [pct, setPct] = useState('')
  const [emettre, setEmettre] = useState(true)
  const [paye, setPaye] = useState(false)
  const [payeMontant, setPayeMontant] = useState('')
  const [payeDate, setPayeDate] = useState(() => todayLocalIso())
  const [payeMode, setPayeMode] = useState('virement')
  const [payeRef, setPayeRef] = useState('')
  const [erreurs, setErreurs] = useState([])
  const [remplacer, setRemplacer] = useState(null)
  const [brouillon, setBrouillon] = useState(null)
  const [saving, setSaving] = useState(false)
  const [emission, setEmission] = useState(false)

  const charger = useCallback(async () => {
    try {
      const { data } = await ventesApi.apercuFacturerVente(devis.id)
      setApercu(data)
      setTab(ongletParDefaut(data))
      setErreurChargement('')
    } catch (err) {
      setErreurChargement(err?.response?.data?.detail || REPLI_CHARGEMENT)
    } finally {
      setChargement(false)
    }
  }, [devis.id])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture serveur au montage (D-ENF22)
    charger()
  }, [charger])

  const plan = apercu?.plan || []
  const prochaine = apercu?.prochaine || null
  const vente = apercu?.vente || null
  const acompte = plan.find((t) => t.cle === 'acompte')
  const acompteOuvert = !acompte || acompte.statut !== 'emise'
  const cleAcompte = acompte && acompteOuvert ? acompte.cle : null
  const soldeOuvert = prochaine?.cle === 'solde'
  const tranche = prochaine?.cle?.startsWith('intermediaire') ? prochaine : null

  // Montant de la facture dont le paiement est consigné (par défaut = la facture).
  let montantFacture = ''
  if (tab === 'acompte') {
    montantFacture = montant
      ? norm(montant)
      : (pct && vente
        ? ((num(pct) * num(vente.prix_convenu_ttc)) / 100).toFixed(2)
        : (acompte && acompteOuvert ? acompte.montant_ttc : ''))
  } else if (tab === 'complete') {
    montantFacture = vente?.reste_a_facturer_ttc || ''
  } else {
    montantFacture = prochaine?.montant_ttc || ''
  }

  const parChamp = erreursParChamp(erreurs)
  const bandeauTexte = bandeau(erreurs)
  const champsRendus = ['montant_ttc', 'pourcentage', 'paiements.0.montant',
    'paiements.0.date_paiement', 'paiements.0.mode_paiement', 'paiements.0.reference']
  const orphelines = erreurs.filter((e) => e.cle !== 'submit' && !champsRendus.includes(e.cle))
  const codeErreur = erreurs.length === 1 && erreurs[0].cle === 'submit' ? erreurs[0].code : ''
  const succ = erreurs[0]?.successeur

  const choisirMontant = (v) => { setMontant(v); if (v) setPct('') }
  const choisirPct = (v) => { setPct(v); if (v) setMontant('') }
  const changerOnglet = (v) => { setTab(v); setErreurs([]); setRemplacer(null); setBrouillon(null) }

  const construireCorps = (avecRemplacement) => {
    const body = { nature: NATURE_PAR_ONGLET[tab] }
    if (tab === 'acompte') {
      if (pct) body.pourcentage = norm(pct)
      else if (montant) body.montant_ttc = norm(montant)
      if (cleAcompte) body.cle_attendue = cleAcompte
    } else if ((tab === 'solde' || tab === 'intermediaire') && prochaine) {
      body.cle_attendue = prochaine.cle
    }
    body.emettre = emettre || paye
    if (paye) {
      body.paiements = [{
        montant: payeMontant ? norm(payeMontant) : String(montantFacture),
        date_paiement: payeDate,
        mode_paiement: payeMode,
        reference: payeRef || '',
      }]
    }
    if (avecRemplacement) body.remplacer_brouillons = true
    return body
  }

  const soumettre = async (avecRemplacement = false) => {
    setSaving(true)
    setErreurs([])
    setBrouillon(null)
    try {
      const { data } = await ventesApi.facturerVente(devis.id, construireCorps(avecRemplacement))
      const f = data?.facture || {}
      const message = `Facture ${f.reference} créée`
      if (f.statut === 'brouillon') {
        toast.success(`${message} en brouillon`)
      } else {
        toast.success(message, {
          action: {
            label: 'Ouvrir le PDF',
            onClick: async () => {
              const issue = await ouvrirPdfFacture(f.id, f.reference)
              if (issue === 'attente') {
                toast.error('PDF encore en préparation : ouvrez-le depuis Ventes → Factures.')
              } else if (issue === 'indisponible') {
                toast.error('PDF de la facture indisponible pour le moment.')
              }
            },
          },
        })
      }
      onOpenChange?.(false)
      onDone?.(data)
    } catch (err) {
      const data = err?.response?.data
      const liste = erreursDuServeur(data, { tab, pct })
      const g = liste[0]
      if (liste.length === 1 && g.cle === 'submit' && g.code === 'brouillons_a_remplacer') {
        setRemplacer(Array.isArray(g.brouillons) ? g.brouillons : [])
      } else if (liste.length === 1 && g.cle === 'submit' && g.code === 'tranche_en_brouillon') {
        setBrouillon(g.facture || null)
      }
      if (liste.length === 1 && g.cle === 'submit' && !g.message) g.message = REPLI_CREATION
      setErreurs(liste)
    } finally {
      setSaving(false)
    }
  }

  const emettreBrouillon = async () => {
    if (!brouillon?.id) return
    setEmission(true)
    try {
      await ventesApi.emettreFacture(brouillon.id)
      setErreurs([])
      setBrouillon(null)
      await charger()
    } catch (err) {
      setErreurs(aplatirErreurs(err?.response?.data))
    } finally {
      setEmission(false)
    }
  }

  const ligneVente = (libelle, valeur, testid) => (
    <>
      <dt>{libelle}</dt>
      <dd className="text-right tabular-nums" data-testid={testid}>{formatMAD(valeur)}</dd>
    </>
  )

  const descriptionChamp = (cle, id) => (parChamp[cle] ? { id, 'aria-describedby': `${id}-error`, 'aria-invalid': true } : { id })

  if (chargement) {
    return <p className="py-6 text-center text-sm text-muted-foreground" data-testid="facturer-chargement">Chargement…</p>
  }
  if (erreurChargement) {
    return (
      <div className="grid gap-3">
        <p role="alert" className="text-sm text-destructive" data-testid="facturer-bandeau">{erreurChargement}</p>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => onOpenChange?.(false)}>Annuler</Button>
          <Button type="button" onClick={() => { setChargement(true); charger() }}>Réessayer</Button>
        </div>
      </div>
    )
  }

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); soumettre(false) }}
      className="grid gap-3"
      noValidate
      data-testid="facturer-vente-form"
    >
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-0.5 text-sm" data-testid="facturer-resume">
        {ligneVente('Prix convenu TTC', vente?.prix_convenu_ttc, 'facturer-prix')}
        {ligneVente('Déjà facturé (émis)', vente?.emis_ttc)}
        {Number(vente?.brouillons_ttc) > 0 && ligneVente('En brouillon', vente?.brouillons_ttc)}
        {ligneVente('Déjà encaissé', vente?.paye_ttc)}
        <dt className="font-medium">Reste à facturer</dt>
        <dd className="text-right font-medium tabular-nums" data-testid="facturer-reste">
          {formatMAD(vente?.reste_a_facturer_ttc)}
        </dd>
      </dl>
      {prochaine && (
        <p className="text-xs text-muted-foreground" data-testid="facturer-prochaine">
          Prochaine tranche : {prochaine.libelle} — {formatMAD(prochaine.montant_ttc)}
        </p>
      )}

      <Tabs value={tab} onValueChange={changerOnglet}>
        <TabsList className="w-full">
          <TabsTrigger value="acompte" disabled={!acompteOuvert}
                       title={acompteOuvert ? undefined : 'Acompte déjà émis'}>Acompte</TabsTrigger>
          {tranche && <TabsTrigger value="intermediaire">{tranche.libelle}</TabsTrigger>}
          <TabsTrigger value="complete">Totalité</TabsTrigger>
          <TabsTrigger value="solde" disabled={!soldeOuvert}
                       title={soldeOuvert ? undefined : "Le solde se facture après les tranches qui le précèdent"}>
            Solde
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === 'acompte' && (
        <div className="grid gap-2 sm:grid-cols-2">
          <FormField label="Montant (MAD)" htmlFor="facturer-montant" error={parChamp.montant_ttc}>
            <Input type="number" inputMode="decimal" step="any" min="0"
                   aria-label="Montant (MAD)"
                   placeholder={apercu?.acompte_propose || ''}
                   value={montant}
                   onChange={(e) => choisirMontant(e.target.value)}
                   {...descriptionChamp('montant_ttc', 'facturer-montant')} />
          </FormField>
          <FormField label="Pourcentage (%)" htmlFor="facturer-pct" error={parChamp.pourcentage}>
            <Input type="number" inputMode="decimal" step="any" min="0" max="100"
                   aria-label="Pourcentage (%)"
                   value={pct}
                   onChange={(e) => choisirPct(e.target.value)}
                   {...descriptionChamp('pourcentage', 'facturer-pct')} />
          </FormField>
          {apercu?.acompte_propose && (
            <p className="text-xs text-muted-foreground sm:col-span-2" data-testid="facturer-acompte-propose">
              Acompte proposé : {formatMAD(apercu.acompte_propose)}{' '}
              <button type="button" className="underline"
                      onClick={() => choisirMontant(String(apercu.acompte_propose))}>
                Utiliser
              </button>
            </p>
          )}
        </div>
      )}
      {tab === 'complete' && (
        <p className="text-sm text-muted-foreground">
          Facture du reste à facturer : {formatMAD(vente?.reste_a_facturer_ttc)}.
        </p>
      )}
      {(tab === 'solde' || tab === 'intermediaire') && prochaine && (
        <p className="text-sm text-muted-foreground">
          {prochaine.libelle} : {formatMAD(prochaine.montant_ttc)}.
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        <Label htmlFor="facturer-emettre">Émettre tout de suite</Label>
        <Switch id="facturer-emettre" aria-label="Émettre tout de suite"
                checked={emettre || paye} disabled={paye}
                onCheckedChange={setEmettre} />
      </div>
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor="facturer-paye">Déjà payé</Label>
        <Switch id="facturer-paye" aria-label="Déjà payé" checked={paye} onCheckedChange={setPaye} />
      </div>
      {paye && (
        <div className="grid gap-2 rounded-md border p-2 sm:grid-cols-2" data-testid="facturer-paiement">
          <FormField label="Montant encaissé" htmlFor="facturer-paye-montant" error={parChamp['paiements.0.montant']}>
            <Input type="number" inputMode="decimal" step="any" min="0"
                   aria-label="Montant encaissé"
                   placeholder={montantFacture ? String(montantFacture) : ''}
                   value={payeMontant}
                   onChange={(e) => setPayeMontant(e.target.value)}
                   {...descriptionChamp('paiements.0.montant', 'facturer-paye-montant')} />
          </FormField>
          <FormField label="Date du paiement" htmlFor="facturer-paye-date" error={parChamp['paiements.0.date_paiement']}>
            <Input type="date" max={todayLocalIso()}
                   aria-label="Date du paiement"
                   value={payeDate}
                   onChange={(e) => setPayeDate(e.target.value)}
                   {...descriptionChamp('paiements.0.date_paiement', 'facturer-paye-date')} />
          </FormField>
          <FormField label="Mode de paiement" htmlFor="facturer-paye-mode" error={parChamp['paiements.0.mode_paiement']}>
            <Select value={payeMode} onValueChange={setPayeMode}>
              <SelectTrigger aria-label="Mode de paiement"
                             {...descriptionChamp('paiements.0.mode_paiement', 'facturer-paye-mode')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODES_PAIEMENT.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Référence (optionnelle)" htmlFor="facturer-paye-ref" error={parChamp['paiements.0.reference']}>
            <Input aria-label="Référence" value={payeRef}
                   onChange={(e) => setPayeRef(e.target.value)}
                   {...descriptionChamp('paiements.0.reference', 'facturer-paye-ref')} />
          </FormField>
        </div>
      )}

      {erreurs.length > 0 && (
        <div className="grid gap-2">
          <div role="alert" data-testid="facturer-bandeau"
               className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm text-destructive">
            {bandeauTexte}
            {orphelines.length > 0 && (
              <ul className="mt-1 list-disc pl-5">
                {orphelines.map((e) => <li key={e.cle}>{e.message}</li>)}
              </ul>
            )}
            {codeErreur === 'version_remplacee' && succ?.reference && (
              <span> Version à jour : {succ.reference}.</span>
            )}
          </div>
          {brouillon && (
            <Button type="button" variant="outline" loading={emission} onClick={emettreBrouillon}>
              Émettre le brouillon
            </Button>
          )}
          {codeErreur === 'cle_inattendue' && (
            <Button type="button" variant="outline" onClick={() => { setErreurs([]); charger() }}>
              Recharger le plan
            </Button>
          )}
        </div>
      )}
      {remplacer && (
        <div className="grid gap-2 rounded-md border p-2 text-sm" data-testid="facturer-remplacer">
          <p>Ces brouillons seront remplacés par la nouvelle facture :</p>
          <ul className="list-disc pl-5">
            {remplacer.map((b) => (
              <li key={b.id}>{b.reference} — {formatMAD(b.total_ttc)}</li>
            ))}
          </ul>
          <Button type="button" loading={saving} onClick={() => soumettre(true)}>
            Remplacer les brouillons et facturer
          </Button>
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={() => onOpenChange?.(false)}>Annuler</Button>
        <Button type="submit" loading={saving}>Créer la facture</Button>
      </div>
    </form>
  )
}

export default function FacturerVenteDialog({ devis, onOpenChange, onDone }) {
  return (
    <ResponsiveDialog
      open={!!devis}
      onOpenChange={(o) => { if (!o) onOpenChange?.(false) }}
      title={`Facturer — ${devis?.reference ?? ''}`}
      description={`${devis?.client_nom ? `${devis.client_nom} — ` : ''}Choisissez ce que vous facturez : acompte, totalité ou solde.`}
    >
      {devis && <CorpsFacturer key={devis.id} devis={devis} onOpenChange={onOpenChange} onDone={onDone} />}
    </ResponsiveDialog>
  )
}
