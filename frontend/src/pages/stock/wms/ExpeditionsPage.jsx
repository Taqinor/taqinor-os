import { useCallback, useEffect, useState } from 'react'
import { Button, Input } from '../../../ui'
import { EnteteStock, BandeauxStock } from '../EnteteStock'
import expeditionsApi from '../../../features/stock/api/expeditionsApi'
import {
  messageServeur, messageServeurBlob, ouvrirBlob,
} from '../../../features/stock/api/erreurs'
import { Section, Vide } from './ElementsEcran'
import useGesteEcran from './useGesteEcran'
import { SELECT_CLS, enListe, champDe } from './constantesEcran'

/* ASTK220 — Expéditions : unités logistiques (lignes, scan, déplacement,
   scellage, étiquette), plans de chargement (capacité), expéditions
   (étiquette transporteur, CMR, suivi, tarifs), retours client (réceptionner,
   inspecter) et rebuts.

   Aucun état local persistant : chaque geste relit le serveur. Une unité
   SCELLÉE n'est plus éditable (champs désactivés) ; un refus serveur est
   affiché mot pour mot. Documents transporteur : aucun prix d'achat ni marge. */

const STATUTS_UNITE = { en_preparation: 'En préparation', scelle: 'Scellée', expedie: 'Expédiée' }
const STATUTS_EXPEDITION = {
  brouillon: 'Brouillon', etiquette: 'Étiquetée', expedie: 'Expédiée',
  livre: 'Livrée', annule: 'Annulée',
}
const STATUTS_RETOUR = {
  demande: 'Demandé', en_transit: 'En transit', receptionne: 'Réceptionné',
  inspecte: 'Inspecté', clos: 'Clos',
}
const MOTIFS_REBUT = {
  casse: 'Casse', perime: 'Périmé', vol: 'Vol', erreur_reception: 'Erreur de réception',
}
const ETATS = { revendable: 'Revendable', a_reparer: 'À réparer', rebut: 'Rebut' }
const VIDE_LIGNE = { produit: '', quantite: '' }

export default function ExpeditionsPage() {
  const [unites, setUnites] = useState([])
  const [plans, setPlans] = useState([])
  const [expeditions, setExpeditions] = useState([])
  const [retours, setRetours] = useState([])
  const [rebuts, setRebuts] = useState([])
  const [produits, setProduits] = useState([])
  const [clients, setClients] = useState([])
  const [casiers, setCasiers] = useState([])
  const [casierDest, setCasierDest] = useState('')
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [uniteForm, setUniteForm] = useState({ type_unite: 'colis', poids_kg: '', dimensions: '' })
  const [ligneForm, setLigneForm] = useState({ unite: '', ...VIDE_LIGNE })
  const [planForm, setPlanForm] = useState({ capacite_kg: '', capacite_m3: '' })
  const [planUnite, setPlanUnite] = useState({ plan: '', unite: '' })
  const [expForm, setExpForm] = useState({ unite_logistique: '', destination: '', cout_reel: '' })
  const [retourForm, setRetourForm] = useState({ client: '', motif: '', produit: '', quantite: '' })
  const [rebutForm, setRebutForm] = useState({ produit: '', quantite: '', motif: 'casse' })
  const [capacite, setCapacite] = useState(null)
  const [suivi, setSuivi] = useState(null)
  const [tarifs, setTarifs] = useState(null)

  const charger = useCallback(async () => {
    const reponses = await Promise.allSettled([
      expeditionsApi.listUnites(), expeditionsApi.listPlans(),
      expeditionsApi.listExpeditions(), expeditionsApi.listRetours(),
      expeditionsApi.listRebuts(),
    ])
    const poseurs = [setUnites, setPlans, setExpeditions, setRetours, setRebuts]
    reponses.forEach((r, i) => { if (r.status === 'fulfilled') poseurs[i](enListe(r.value.data)) })
    const ko = reponses.find((r) => r.status === 'rejected')
    setErreur(ko ? messageServeur(ko.reason, 'Chargement impossible.') : null)
  }, [])

  useEffect(() => {
    Promise.resolve().then(charger)
    expeditionsApi.listProduits().then((r) => setProduits(enListe(r.data))).catch(() => {})
    expeditionsApi.listCasiers().then((r) => setCasiers(enListe(r.data))).catch(() => {})
    expeditionsApi.listClients().then((r) => setClients(enListe(r.data))).catch(() => {})
  }, [charger])

  const nomProduit = (id) => produits.find((p) => p.id === id)?.nom ?? `Produit #${id}`

  const { occupe, geste } = useGesteEcran(charger, setErreur, setInfo)

  const lire = async (action, poser, repli) => {
    setErreur(null)
    try { poser((await action()).data) } catch (err) { setErreur(messageServeur(err, repli)) }
  }

  const ouvrirPdf = async (action, repli) => {
    setErreur(null)
    try { ouvrirBlob((await action()).data) } catch (err) {
      setErreur(await messageServeurBlob(err, repli))
    }
  }

  const creerUnite = async (ev) => {
    ev.preventDefault()
    const corps = { type_unite: uniteForm.type_unite }
    if (uniteForm.poids_kg !== '') corps.poids_kg = uniteForm.poids_kg
    if (uniteForm.dimensions) corps.dimensions = uniteForm.dimensions
    const ok = await geste(() => expeditionsApi.creerUnite(corps), "L'unité n'a pas pu être créée.")
    if (ok) setUniteForm({ type_unite: 'colis', poids_kg: '', dimensions: '' })
  }

  const ajouterLigne = async (ev) => {
    ev.preventDefault()
    if (!ligneForm.unite || !ligneForm.produit || !ligneForm.quantite) {
      setErreur("Choisissez l'unité, le produit et la quantité."); return
    }
    const ok = await geste(() => expeditionsApi.ajouterLigne(ligneForm.unite, {
      produit: Number(ligneForm.produit), quantite: Number(ligneForm.quantite),
    }), "La ligne n'a pas pu être ajoutée.")
    if (ok) setLigneForm((f) => ({ ...f, ...VIDE_LIGNE }))
  }

  const controlerScan = async () => {
    if (!ligneForm.unite || !ligneForm.produit) {
      setErreur("Choisissez l'unité et le produit scanné."); return
    }
    await geste(() => expeditionsApi.controlerScan(ligneForm.unite, {
      produit: Number(ligneForm.produit), quantite: Number(ligneForm.quantite || 1),
    }), 'Contrôle du scan impossible.', 'Scan contrôlé.')
  }

  const deplacerUnite = async () => {
    if (!ligneForm.unite || !casierDest) { setErreur("Choisissez l'unité et le casier de destination."); return }
    const ok = await geste(() => expeditionsApi.deplacer(ligneForm.unite, {
      bin_destination: Number(casierDest),
    }), 'Déplacement impossible.', 'Unité déplacée.')
    if (ok) setCasierDest('')
  }

  const creerPlan = async (ev) => {
    ev.preventDefault()
    const corps = {}
    if (planForm.capacite_kg !== '') corps.capacite_kg = planForm.capacite_kg
    if (planForm.capacite_m3 !== '') corps.capacite_m3 = planForm.capacite_m3
    const ok = await geste(() => expeditionsApi.creerPlan(corps), "Le plan n'a pas pu être créé.")
    if (ok) setPlanForm({ capacite_kg: '', capacite_m3: '' })
  }

  const rattacherUnite = async (ev) => {
    ev.preventDefault()
    if (!planUnite.plan || !planUnite.unite) { setErreur("Choisissez le plan et l'unité."); return }
    const ok = await geste(() => expeditionsApi.ajouterUnitePlan(planUnite.plan, {
      unite_logistique: Number(planUnite.unite),
    }), "L'unité n'a pas pu être ajoutée au plan.")
    if (ok) setPlanUnite({ plan: '', unite: '' })
  }

  const creerExpedition = async (ev) => {
    ev.preventDefault()
    if (!expForm.unite_logistique) { setErreur('Choisissez une unité logistique.'); return }
    const corps = {
      unite_logistique: Number(expForm.unite_logistique), destination: expForm.destination,
    }
    if (expForm.cout_reel !== '') corps.cout_reel = expForm.cout_reel
    const ok = await geste(() => expeditionsApi.creerExpedition(corps),
      "L'expédition n'a pas pu être créée.")
    if (ok) setExpForm({ unite_logistique: '', destination: '', cout_reel: '' })
  }

  const creerRetour = async (ev) => {
    ev.preventDefault()
    if (!retourForm.client || !retourForm.produit || !retourForm.quantite) {
      setErreur('Choisissez le client, le produit et la quantité.'); return
    }
    const corps = {
      client: Number(retourForm.client), motif: retourForm.motif,
      lignes: [{
        produit: Number(retourForm.produit), quantite: Number(retourForm.quantite),
        etat_constate: 'revendable',
      }],
    }
    const ok = await geste(() => expeditionsApi.creerRetour(corps),
      "Le retour n'a pas pu être enregistré.")
    if (ok) setRetourForm({ client: '', motif: '', produit: '', quantite: '' })
  }

  const declarerRebut = async (ev) => {
    ev.preventDefault()
    if (!rebutForm.produit || !rebutForm.quantite) {
      setErreur('Choisissez le produit et la quantité.'); return
    }
    const ok = await geste(() => expeditionsApi.declarerRebut({
      produit: Number(rebutForm.produit), quantite: Number(rebutForm.quantite),
      motif: rebutForm.motif,
    }), "Le rebut n'a pas pu être déclaré.")
    if (ok) setRebutForm({ produit: '', quantite: '', motif: 'casse' })
  }

  const champUnite = champDe(setUniteForm)
  const champLigne = champDe(setLigneForm)
  const champPlan = champDe(setPlanForm)
  const champExp = champDe(setExpForm)
  const champRetour = champDe(setRetourForm)
  const champRebut = champDe(setRebutForm)
  const selectProduit = (valeur, onChange, label) => (
    <label className="flex flex-col gap-1 text-xs">
      <span>{label}</span>
      <select className={SELECT_CLS} value={valeur} onChange={onChange}>
        <option value="">—</option>
        {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
      </select>
    </label>
  )

  return (
    <div className="space-y-4">
      <EnteteStock
        title="Expéditions"
        subtitle="Unités logistiques, plans de chargement, expéditions transporteur, retours client et rebuts."
      />

      <BandeauxStock erreur={erreur} info={info} />

      <Section id="unites-logistiques" titre="Unités logistiques">
        <form onSubmit={creerUnite} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Type d&apos;unité</span>
            <select className={SELECT_CLS} value={uniteForm.type_unite} onChange={champUnite('type_unite')}>
              <option value="colis">Colis</option>
              <option value="palette">Palette</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Poids (kg)</span>
            <Input type="number" step="any" value={uniteForm.poids_kg} onChange={champUnite('poids_kg')} className="w-28" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Dimensions</span>
            <Input value={uniteForm.dimensions} onChange={champUnite('dimensions')} className="w-32" />
          </label>
          <Button type="submit" disabled={occupe}>Créer l&apos;unité</Button>
        </form>

        <form onSubmit={ajouterLigne} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Unité à remplir</span>
            <select className={SELECT_CLS} value={ligneForm.unite} onChange={champLigne('unite')}>
              <option value="">—</option>
              {unites.map((u) => (
                <option key={u.id} value={u.id} disabled={u.est_figee}>{u.sscc}</option>
              ))}
            </select>
          </label>
          {selectProduit(ligneForm.produit, champLigne('produit'), 'Produit de la ligne')}
          <label className="flex flex-col gap-1 text-xs">
            <span>Quantité de la ligne</span>
            <Input type="number" step="any" value={ligneForm.quantite} onChange={champLigne('quantite')} className="w-28" />
          </label>
          <Button type="submit" disabled={occupe}>Ajouter la ligne</Button>
          <Button type="button" variant="outline" disabled={occupe} onClick={controlerScan}>
            Contrôler le scan
          </Button>
          <label className="flex flex-col gap-1 text-xs">
            <span>Casier de destination</span>
            <select className={SELECT_CLS} value={casierDest} onChange={(e) => setCasierDest(e.target.value)}>
              <option value="">—</option>
              {casiers.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
            </select>
          </label>
          <Button type="button" variant="outline" disabled={occupe} onClick={deplacerUnite}>
            Déplacer l&apos;unité
          </Button>
        </form>

        {unites.length === 0 ? <Vide>Aucune unité logistique.</Vide> : (
          <ul className="space-y-2 text-sm">
            {unites.map((u) => (
              <li key={u.id} className="rounded-md border border-[var(--border)] p-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <strong>{u.sscc}</strong>
                  <span>{u.type_unite === 'palette' ? 'Palette' : 'Colis'}</span>
                  <span>{STATUTS_UNITE[u.statut] ?? u.statut}</span>
                  <label className="flex items-center gap-1 text-xs">
                    <span>Dimensions de l&apos;unité {u.sscc}</span>
                    <Input
                      defaultValue={u.dimensions} disabled={u.est_figee || occupe} className="w-28"
                      onBlur={(e) => {
                        if (e.target.value !== (u.dimensions ?? '')) {
                          geste(() => expeditionsApi.modifierUnite(u.id, { dimensions: e.target.value }),
                            "L'unité n'a pas pu être modifiée.")
                        }
                      }}
                    />
                  </label>
                  {!u.est_figee && (
                    <Button size="sm" disabled={occupe} aria-label={`Sceller l'unité ${u.sscc}`}
                      onClick={() => geste(() => expeditionsApi.sceller(u.id), "Scellage impossible.",
                        'Unité scellée.')}>
                      Sceller
                    </Button>
                  )}
                  <Button size="sm" variant="outline" aria-label={`Étiquette de l'unité ${u.sscc}`}
                    onClick={() => ouvrirPdf(() => expeditionsApi.etiquetteUnitePdf(u.id),
                      'Étiquette indisponible.')}>
                    Étiquette
                  </Button>
                </div>
                {(u.lignes ?? []).length > 0 && (
                  <ul className="mt-1 text-xs text-[var(--muted-foreground)]">
                    {u.lignes.map((l) => (
                      <li key={l.id}>{l.produit_nom ?? nomProduit(l.produit)} × {l.quantite}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="plans-chargement" titre="Plans de chargement">
        <form onSubmit={creerPlan} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Capacité (kg)</span>
            <Input type="number" step="any" value={planForm.capacite_kg} onChange={champPlan('capacite_kg')} className="w-28" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Capacité (m³)</span>
            <Input type="number" step="any" value={planForm.capacite_m3} onChange={champPlan('capacite_m3')} className="w-28" />
          </label>
          <Button type="submit" disabled={occupe}>Créer le plan</Button>
        </form>
        <form onSubmit={rattacherUnite} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Plan de chargement</span>
            <select className={SELECT_CLS} value={planUnite.plan}
              onChange={(e) => setPlanUnite((f) => ({ ...f, plan: e.target.value }))}>
              <option value="">—</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.reference}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Unité à charger</span>
            <select className={SELECT_CLS} value={planUnite.unite}
              onChange={(e) => setPlanUnite((f) => ({ ...f, unite: e.target.value }))}>
              <option value="">—</option>
              {unites.map((u) => <option key={u.id} value={u.id}>{u.sscc}</option>)}
            </select>
          </label>
          <Button type="submit" disabled={occupe}>Ajouter au plan</Button>
        </form>
        {plans.length === 0 ? <Vide>Aucun plan de chargement.</Vide> : (
          <ul className="space-y-1 text-sm">
            {plans.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-3">
                <strong>{p.reference}</strong>
                <span>{p.nb_unites} unité(s)</span>
                <span>{p.capacite_kg ? `${p.capacite_kg} kg` : '—'}</span>
                <Button size="sm" variant="outline" aria-label={`Vérifier la capacité du plan ${p.reference}`}
                  onClick={() => lire(() => expeditionsApi.verifierCapacite(p.id), setCapacite,
                    'Vérification impossible.')}>
                  Vérifier la capacité
                </Button>
              </li>
            ))}
          </ul>
        )}
        {capacite && (
          <p role="status" className="mt-2 text-sm">
            Poids {capacite.poids_kg} kg ({capacite.poids_utilise_pct} %) · volume {capacite.volume_m3} m³
            ({capacite.volume_utilise_pct} %)
            {capacite.depassement ? ` — ${capacite.avertissement}` : ' — dans la capacité.'}
          </p>
        )}
      </Section>

      <Section id="expeditions" titre="Expéditions transporteur">
        <form onSubmit={creerExpedition} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Unité à expédier</span>
            <select className={SELECT_CLS} value={expForm.unite_logistique} onChange={champExp('unite_logistique')}>
              <option value="">—</option>
              {unites.filter((u) => u.est_figee).map((u) => <option key={u.id} value={u.id}>{u.sscc}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Destination</span>
            <Input value={expForm.destination} onChange={champExp('destination')} className="w-40" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Coût réel (MAD)</span>
            <Input type="number" step="any" value={expForm.cout_reel} onChange={champExp('cout_reel')} className="w-28" />
          </label>
          <Button type="submit" disabled={occupe}>Créer l&apos;expédition</Button>
        </form>
        {expeditions.length === 0 ? <Vide>Aucune expédition.</Vide> : (
          <ul className="space-y-1 text-sm">
            {expeditions.map((x) => (
              <li key={x.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <strong>{x.numero_suivi || `Expédition ${x.id}`}</strong>
                <span>{x.destination || '—'}</span>
                <span>{STATUTS_EXPEDITION[x.statut] ?? x.statut}</span>
                <Button size="sm" disabled={occupe} aria-label={`Générer l'étiquette de l'expédition ${x.id}`}
                  onClick={() => geste(() => expeditionsApi.genererEtiquette(x.id),
                    "L'étiquette n'a pas pu être générée.", 'Étiquette générée.')}>
                  Générer l&apos;étiquette
                </Button>
                <Button size="sm" variant="outline" aria-label={`CMR de l'expédition ${x.id}`}
                  onClick={() => ouvrirPdf(() => expeditionsApi.cmrPdf(x.id), 'CMR indisponible.')}>
                  CMR
                </Button>
                <Button size="sm" variant="outline" aria-label={`Suivi de l'expédition ${x.id}`}
                  onClick={() => lire(() => expeditionsApi.tracking(x.id), setSuivi, 'Suivi indisponible.')}>
                  Suivi
                </Button>
                <Button size="sm" variant="outline" aria-label={`Tarifs de l'expédition ${x.id}`}
                  onClick={() => lire(() => expeditionsApi.tarifs({
                    unite_logistique: x.unite_logistique, destination: x.destination,
                  }), setTarifs, 'Tarifs indisponibles.')}>
                  Tarifs
                </Button>
              </li>
            ))}
          </ul>
        )}
        {suivi && (
          <p role="status" className="mt-2 text-sm">
            Suivi {suivi.numero_suivi} : {STATUTS_EXPEDITION[suivi.statut] ?? suivi.statut}
            {suivi.destination ? ` vers ${suivi.destination}` : ''}.
          </p>
        )}
        {tarifs && (
          <ul className="mt-2 text-sm">
            {tarifs.offres.map((o) => (
              <li key={`${o.source}-${o.code}`}>
                {o.libelle} — {o.cout} {o.devise}{o.delai_jours != null ? ` · ${o.delai_jours} j` : ''}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="retours-client" titre="Retours client">
        <form onSubmit={creerRetour} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Client du retour</span>
            <select className={SELECT_CLS} value={retourForm.client} onChange={champRetour('client')}>
              <option value="">—</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Motif du retour</span>
            <Input value={retourForm.motif} onChange={champRetour('motif')} className="w-48" />
          </label>
          {selectProduit(retourForm.produit, champRetour('produit'), 'Produit retourné')}
          <label className="flex flex-col gap-1 text-xs">
            <span>Quantité retournée</span>
            <Input type="number" step="any" value={retourForm.quantite} onChange={champRetour('quantite')} className="w-28" />
          </label>
          <Button type="submit" disabled={occupe}>Enregistrer le retour</Button>
        </form>
        {retours.length === 0 ? <Vide>Aucun retour client.</Vide> : (
          <ul className="space-y-1 text-sm">
            {retours.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <strong>{r.reference}</strong>
                <span>{r.client_nom}</span>
                <span>{STATUTS_RETOUR[r.statut] ?? r.statut}</span>
                {['demande', 'en_transit'].includes(r.statut) && (
                  <Button size="sm" disabled={occupe} aria-label={`Réceptionner le retour ${r.reference}`}
                    onClick={() => geste(() => expeditionsApi.receptionnerRetour(r.id),
                      'Réception impossible.', 'Retour réceptionné.')}>
                    Réceptionner
                  </Button>
                )}
                {r.statut === 'receptionne' && (
                  <Button size="sm" disabled={occupe} aria-label={`Inspecter le retour ${r.reference}`}
                    onClick={() => geste(() => expeditionsApi.inspecterRetour(r.id, {
                      lignes: (r.lignes ?? []).map((l) => ({ ligne: l.id, etat_constate: l.etat_constate })),
                    }), 'Inspection impossible.', 'Retour inspecté.')}>
                    Inspecter
                  </Button>
                )}
                <span className="text-xs text-[var(--muted-foreground)]">
                  {(r.lignes ?? []).map((l) => `${l.produit_nom} × ${l.quantite} (${ETATS[l.etat_constate] ?? l.etat_constate})`).join(', ')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="rebuts" titre="Rebuts">
        <form onSubmit={declarerRebut} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          {selectProduit(rebutForm.produit, champRebut('produit'), 'Produit du rebut')}
          <label className="flex flex-col gap-1 text-xs">
            <span>Quantité du rebut</span>
            <Input type="number" step="any" value={rebutForm.quantite} onChange={champRebut('quantite')} className="w-28" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Motif du rebut</span>
            <select className={SELECT_CLS} value={rebutForm.motif} onChange={champRebut('motif')}>
              {Object.entries(MOTIFS_REBUT).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <Button type="submit" disabled={occupe}>Déclarer le rebut</Button>
        </form>
        {rebuts.length === 0 ? <Vide>Aucun rebut déclaré.</Vide> : (
          <ul className="space-y-1 text-sm">
            {rebuts.map((r) => (
              <li key={r.id}>
                {r.produit_nom} × {r.quantite} — {r.motif_libelle || MOTIFS_REBUT[r.motif] || r.motif}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}
