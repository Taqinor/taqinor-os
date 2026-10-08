import { useCallback, useEffect, useState } from 'react'
import { Button, Input } from '../../../ui'
import { EnteteStock, BandeauxStock } from '../EnteteStock'
import qualiteApi from '../../../features/stock/api/qualiteApi'
import { messageServeur } from '../../../features/stock/api/erreurs'
import { Section, Vide } from './ElementsEcran'
import useGesteEcran from './useGesteEcran'
import { SELECT_CLS, enListe, champDe } from './constantesEcran'

/* ASTK224 — Qualité & rappels : alertes de rappel (impact, blocages créés,
   clôture), blocages qualité (lever, lever la quarantaine d'un casier),
   plans d'échantillonnage (contrôle qualité à réception) et casiers
   autorisés par classe de danger.

   Aucun état local persistant : chaque geste relit le serveur ; chaque erreur
   serveur est affichée mot pour mot. */

const STATUTS_RAPPEL = { en_cours: 'En cours', clos: 'Clos' }
const STATUTS_BLOCAGE = { en_quarantaine: 'En quarantaine', levee: 'Levé', rebutee: 'Rebuté' }
const CLASSES_DANGER = {
  BATTERIE_LITHIUM: 'Batterie lithium', INFLAMMABLE: 'Inflammable', CORROSIF: 'Corrosif',
}

export default function QualitePage() {
  const [rappels, setRappels] = useState([])
  const [blocages, setBlocages] = useState([])
  const [plans, setPlans] = useState([])
  const [hazmat, setHazmat] = useState([])
  const [produits, setProduits] = useState([])
  const [casiers, setCasiers] = useState([])
  const [categories, setCategories] = useState([])
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [impact, setImpact] = useState(null)
  const [rappelForm, setRappelForm] = useState({ produit: '', lot: '', motif: '' })
  const [casierQuarantaine, setCasierQuarantaine] = useState('')
  const [planForm, setPlanForm] = useState({ categorie: '', taux_echantillon_pct: '' })
  const [hazmatForm, setHazmatForm] = useState({ bin: '', classe_danger: 'BATTERIE_LITHIUM' })

  const charger = useCallback(async () => {
    const reponses = await Promise.allSettled([
      qualiteApi.listRappels(), qualiteApi.listBlocages(),
      qualiteApi.listPlans(), qualiteApi.listHazmat(),
    ])
    const poseurs = [setRappels, setBlocages, setPlans, setHazmat]
    reponses.forEach((r, i) => { if (r.status === 'fulfilled') poseurs[i](enListe(r.value.data)) })
    const ko = reponses.find((r) => r.status === 'rejected')
    setErreur(ko ? messageServeur(ko.reason, 'Chargement impossible.') : null)
  }, [])

  useEffect(() => {
    Promise.resolve().then(charger)
    qualiteApi.listProduits().then((r) => setProduits(enListe(r.data))).catch(() => {})
    qualiteApi.listCasiers().then((r) => setCasiers(enListe(r.data))).catch(() => {})
    qualiteApi.listCategories().then((r) => setCategories(enListe(r.data))).catch(() => {})
  }, [charger])

  const { occupe, geste } = useGesteEcran(charger, setErreur, setInfo)

  const voirImpact = async (id) => {
    setErreur(null)
    try { setImpact((await qualiteApi.impactRappel(id)).data) } catch (err) {
      setErreur(messageServeur(err, 'Impact indisponible.'))
    }
  }

  const declarerRappel = async (ev) => {
    ev.preventDefault()
    if (!rappelForm.produit || !rappelForm.motif.trim()) {
      setErreur('Choisissez le produit et indiquez le motif du rappel.'); return
    }
    const corps = { produit: Number(rappelForm.produit), motif: rappelForm.motif.trim() }
    if (rappelForm.lot !== '') corps.lot = Number(rappelForm.lot)
    const ok = await geste(() => qualiteApi.declarerRappel(corps),
      "Le rappel n'a pas pu être déclaré.", 'Rappel déclaré.')
    if (ok) setRappelForm({ produit: '', lot: '', motif: '' })
  }

  const leverQuarantaine = async (ev) => {
    ev.preventDefault()
    if (!casierQuarantaine) { setErreur('Choisissez un casier.'); return }
    const ok = await geste(() => qualiteApi.leverQuarantaine({ bin: Number(casierQuarantaine) }),
      'Levée de la quarantaine impossible.', 'Quarantaine levée.')
    if (ok) setCasierQuarantaine('')
  }

  const creerPlan = async (ev) => {
    ev.preventDefault()
    if (!planForm.categorie || planForm.taux_echantillon_pct === '') {
      setErreur('Choisissez la catégorie et le taux.'); return
    }
    const ok = await geste(() => qualiteApi.creerPlan({
      categorie: Number(planForm.categorie), taux_echantillon_pct: planForm.taux_echantillon_pct,
    }), "Le plan n'a pas pu être enregistré.", "Plan d'échantillonnage enregistré.")
    if (ok) setPlanForm({ categorie: '', taux_echantillon_pct: '' })
  }

  const declarerHazmat = async (ev) => {
    ev.preventDefault()
    if (!hazmatForm.bin) { setErreur('Choisissez un casier.'); return }
    const ok = await geste(() => qualiteApi.creerHazmat({
      bin: Number(hazmatForm.bin), classe_danger: hazmatForm.classe_danger,
    }), "La compatibilité n'a pas pu être déclarée.", 'Casier déclaré compatible.')
    if (ok) setHazmatForm((f) => ({ ...f, bin: '' }))
  }

  const champRappel = champDe(setRappelForm)
  const champPlan = champDe(setPlanForm)
  const champHazmat = champDe(setHazmatForm)
  const blocagesDuRappel = (r) => r.blocages ?? []

  return (
    <div className="space-y-4">
      <EnteteStock
        title="Qualité et rappels"
        subtitle="Rappels de lots, blocages qualité, échantillonnage à réception et casiers compatibles."
      />

      <BandeauxStock erreur={erreur} info={info} />

      <Section id="rappels" titre="Alertes de rappel">
        <form onSubmit={declarerRappel} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Produit du rappel</span>
            <select className={SELECT_CLS} value={rappelForm.produit} onChange={champRappel('produit')}>
              <option value="">—</option>
              {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Lot (identifiant)</span>
            <Input type="number" step="any" value={rappelForm.lot} onChange={champRappel('lot')} className="w-28" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Motif du rappel</span>
            <Input value={rappelForm.motif} onChange={champRappel('motif')} className="w-64" />
          </label>
          <Button type="submit" disabled={occupe}>Déclarer le rappel</Button>
        </form>
        {rappels.length === 0 ? <Vide>Aucun rappel.</Vide> : (
          <ul className="space-y-2 text-sm">
            {rappels.map((r) => (
              <li key={r.id} className="rounded-md border border-[var(--border)] p-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <strong>{r.produit_nom}</strong>
                  <span>{r.numero_lot || 'Sans lot'}</span>
                  <span>{STATUTS_RAPPEL[r.statut] ?? r.statut}</span>
                  <span className="text-[var(--muted-foreground)]">{r.motif}</span>
                  <Button size="sm" variant="outline" aria-label={`Impact du rappel ${r.id}`}
                    onClick={() => voirImpact(r.id)}>Impact</Button>
                  {r.statut === 'en_cours' && (
                    <Button size="sm" disabled={occupe} aria-label={`Clôturer le rappel ${r.id}`}
                      onClick={() => geste(() => qualiteApi.cloturerRappel(r.id),
                        'Clôture impossible.', 'Rappel clôturé.')}>
                      Clôturer
                    </Button>
                  )}
                </div>
                {blocagesDuRappel(r).length > 0 && (
                  <ul className="mt-1 text-xs">
                    {blocagesDuRappel(r).map((b) => (
                      <li key={b.id}>
                        Blocage {b.id} — {b.quantite} unité(s) — {STATUTS_BLOCAGE[b.statut] ?? b.statut}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
        {impact && (
          <div role="status" className="mt-3 text-sm">
            <p>
              Impact — {impact.produit.nom} : {impact.stock_restant} en stock,
              {' '}{impact.chantiers.length} chantier(s), {impact.colis.length} colis.
            </p>
            <ul className="text-xs">
              {impact.casiers.map((c) => <li key={c.bin_id}>{c.code} — {c.quantite}</li>)}
            </ul>
          </div>
        )}
      </Section>

      <Section id="blocages" titre="Blocages qualité">
        <form onSubmit={leverQuarantaine} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Casier en quarantaine</span>
            <select className={SELECT_CLS} value={casierQuarantaine}
              onChange={(e) => setCasierQuarantaine(e.target.value)}>
              <option value="">—</option>
              {casiers.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
            </select>
          </label>
          <Button type="submit" variant="outline" disabled={occupe}>Lever la quarantaine du casier</Button>
        </form>
        {blocages.length === 0 ? <Vide>Aucun blocage.</Vide> : (
          <ul className="space-y-1 text-sm">
            {blocages.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <strong>{b.produit_nom}</strong>
                <span>{b.quantite} unité(s)</span>
                <span>{b.bin_code || '—'}</span>
                <span>{STATUTS_BLOCAGE[b.statut] ?? b.statut}</span>
                <span className="text-[var(--muted-foreground)]">{b.motif}</span>
                {b.statut === 'en_quarantaine' && (
                  <Button size="sm" disabled={occupe} aria-label={`Lever le blocage ${b.id}`}
                    onClick={() => geste(() => qualiteApi.leverBlocage(b.id),
                      'Levée impossible.', 'Blocage levé.')}>
                    Lever
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="echantillonnage" titre="Plans d'échantillonnage">
        <form onSubmit={creerPlan} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Catégorie contrôlée</span>
            <select className={SELECT_CLS} value={planForm.categorie} onChange={champPlan('categorie')}>
              <option value="">—</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Taux d&apos;échantillon (%)</span>
            <Input type="number" step="any" value={planForm.taux_echantillon_pct}
              onChange={champPlan('taux_echantillon_pct')} className="w-28" />
          </label>
          <Button type="submit" disabled={occupe}>Enregistrer le plan</Button>
        </form>
        {plans.length === 0 ? <Vide>Aucun plan d&apos;échantillonnage.</Vide> : (
          <ul className="space-y-1 text-sm">
            {plans.map((p) => (
              <li key={p.id}>
                {p.categorie_nom} — {p.taux_echantillon_pct} % {p.actif ? '' : '(inactif)'}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="hazmat" titre="Casiers compatibles par classe de danger">
        <form onSubmit={declarerHazmat} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Casier compatible</span>
            <select className={SELECT_CLS} value={hazmatForm.bin} onChange={champHazmat('bin')}>
              <option value="">—</option>
              {casiers.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Classe de danger</span>
            <select className={SELECT_CLS} value={hazmatForm.classe_danger} onChange={champHazmat('classe_danger')}>
              {Object.entries(CLASSES_DANGER).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <Button type="submit" disabled={occupe}>Déclarer le casier compatible</Button>
        </form>
        {hazmat.length === 0 ? <Vide>Aucun casier déclaré compatible.</Vide> : (
          <ul className="space-y-1 text-sm">
            {hazmat.map((h) => (
              <li key={h.id}>{h.bin_code} — {CLASSES_DANGER[h.classe_danger] ?? h.classe_danger}</li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}
