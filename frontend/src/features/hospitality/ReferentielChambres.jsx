import { useCallback, useEffect, useState } from 'react'
import hospitalityApi from '../../api/hospitalityApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   WIR211/NTHOT1+NTHOT2 — Référentiel hôtellerie : types de chambre, chambres,
   plans tarifaires.

   Le module était INERTE : les trois endpoints de création existaient et
   étaient même déjà exposés par `hospitalityApi`, mais aucun écran ne les
   appelait. Depuis une base vide, il était donc impossible de créer un type,
   donc une chambre, donc un plan tarifaire — d'où un plan des chambres vide,
   des folios sans nuitées et un RevPAR à 0.

   Cet écran est le maillon manquant : type → chambre → plan, dans cet ordre
   (une chambre exige son type, un plan tarifaire aussi).
   ========================================================================== */

// source-choix: hospitality.PlanTarifaire.Canal
const CANAUX = [
  { value: 'rack', label: 'Rack (tarif public)' },
  { value: 'corporate', label: 'Corporate' },
  { value: 'ota', label: 'OTA' },
]

// source-choix: hospitality.Chambre.Statut
const STATUTS_CHAMBRE = [
  { value: 'libre', label: 'Libre' },
  { value: 'occupee', label: 'Occupée' },
  { value: 'sale', label: 'Sale' },
  { value: 'en_nettoyage', label: 'En nettoyage' },
  { value: 'hors_service', label: 'Hors service' },
]

function lignes(reponse) {
  const charge = reponse?.data
  if (Array.isArray(charge)) return charge
  if (Array.isArray(charge?.results)) return charge.results
  return []
}

export default function ReferentielChambres({ onChanged }) {
  const [types, setTypes] = useState([])
  const [chambres, setChambres] = useState([])
  const [plans, setPlans] = useState([])
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const [formType, setFormType] = useState({ libelle: '', capacite_max: '2', description: '' })
  const [formChambre, setFormChambre] = useState({
    type_chambre: '', numero: '', nom: '', etage: '', statut: 'libre', vue: '',
  })
  const [formPlan, setFormPlan] = useState({
    type_chambre: '', canal: 'rack', date_debut: '', date_fin: '',
    prix_nuit_ht: '', min_nuits: '1',
  })

  const charger = useCallback(() => {
    Promise.all([
      hospitalityApi.listTypesChambre(),
      hospitalityApi.listChambres(),
      hospitalityApi.listPlansTarifaires(),
    ])
      .then(([t, c, p]) => {
        setTypes(lignes(t)); setChambres(lignes(c)); setPlans(lignes(p))
      })
      .catch((err) => setErreur(frenchError(err, 'Chargement du référentiel impossible.')))
  }, [])

  useEffect(() => { charger() }, [charger])

  const apres = () => { charger(); onChanged?.() }

  async function creerType(e) {
    e.preventDefault()
    if (occupe) return
    if (!formType.libelle.trim()) { setErreur('Le libellé du type est requis.'); return }
    setOccupe(true); setErreur(null)
    try {
      await hospitalityApi.createTypeChambre({
        libelle: formType.libelle.trim(),
        capacite_max: formType.capacite_max,
        description: formType.description,
      })
      setFormType({ libelle: '', capacite_max: '2', description: '' })
      apres()
    } catch (err) {
      setErreur(frenchError(err, 'Création du type impossible.'))
    } finally { setOccupe(false) }
  }

  async function creerChambre(e) {
    e.preventDefault()
    if (occupe) return
    if (!formChambre.type_chambre) { setErreur("Choisissez d'abord un type de chambre."); return }
    if (!formChambre.numero.trim()) { setErreur('Le numéro de chambre est requis.'); return }
    setOccupe(true); setErreur(null)
    try {
      await hospitalityApi.createChambre({
        type_chambre: formChambre.type_chambre,
        numero: formChambre.numero.trim(),
        nom: formChambre.nom,
        // `etage` vide part en null : le serveur refuse une chaîne vide sur un
        // entier, et on n'invente jamais un étage 0.
        etage: formChambre.etage === '' ? null : formChambre.etage,
        statut: formChambre.statut,
        vue: formChambre.vue,
      })
      setFormChambre({
        type_chambre: '', numero: '', nom: '', etage: '', statut: 'libre', vue: '',
      })
      apres()
    } catch (err) {
      setErreur(frenchError(err, 'Création de la chambre impossible.'))
    } finally { setOccupe(false) }
  }

  async function creerPlan(e) {
    e.preventDefault()
    if (occupe) return
    if (!formPlan.type_chambre) { setErreur('Choisissez le type de chambre du plan.'); return }
    if (formPlan.prix_nuit_ht === '') { setErreur('Le prix par nuit est requis.'); return }
    setOccupe(true); setErreur(null)
    try {
      await hospitalityApi.createPlanTarifaire({
        type_chambre: formPlan.type_chambre,
        canal: formPlan.canal,
        date_debut: formPlan.date_debut || null,
        date_fin: formPlan.date_fin || null,
        prix_nuit_ht: formPlan.prix_nuit_ht,
        min_nuits: formPlan.min_nuits || '1',
      })
      setFormPlan({
        type_chambre: '', canal: 'rack', date_debut: '', date_fin: '',
        prix_nuit_ht: '', min_nuits: '1',
      })
      apres()
    } catch (err) {
      setErreur(frenchError(err, 'Création du plan tarifaire impossible.'))
    } finally { setOccupe(false) }
  }

  return (
    <div className="hotel-referentiel" data-testid="hotel-referentiel">
      <h3>Référentiel des chambres</h3>
      <p>
        Un hôtel se paramètre dans cet ordre : un <strong>type</strong> de
        chambre, puis les <strong>chambres</strong> de ce type, puis un
        <strong> plan tarifaire</strong> qui leur donne un prix par nuit. Sans
        plan tarifaire, une réservation part sans prix et le folio reste vide.
      </p>
      {erreur && <p role="alert" className="hotel-referentiel__error">{erreur}</p>}

      {/* ── 1. Types de chambre ── */}
      <section>
        <h4>1. Types de chambre</h4>
        {types.length === 0 ? (
          <p>Aucun type de chambre : commencez ici.</p>
        ) : (
          <ul>
            {types.map((t) => (
              <li key={t.id}>
                {t.libelle} — jusqu'à {t.capacite_max} personne(s)
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={creerType} noValidate>
          <label htmlFor="tc-libelle">Libellé du type</label>
          <input id="tc-libelle" value={formType.libelle}
                 onChange={(e) => setFormType(f => ({ ...f, libelle: e.target.value }))}
                 placeholder="ex : Double supérieure" />
          <label htmlFor="tc-capacite">Capacité maximale</label>
          <input id="tc-capacite" type="number" step="any" value={formType.capacite_max}
                 onChange={(e) => setFormType(f => ({ ...f, capacite_max: e.target.value }))} />
          <label htmlFor="tc-description">Description</label>
          <input id="tc-description" value={formType.description}
                 onChange={(e) => setFormType(f => ({ ...f, description: e.target.value }))} />
          <button type="submit" disabled={occupe}>Créer le type</button>
        </form>
      </section>

      {/* ── 2. Chambres ── */}
      <section>
        <h4>2. Chambres</h4>
        {chambres.length === 0 ? (
          <p>Aucune chambre.</p>
        ) : (
          <ul>
            {chambres.map((c) => (
              <li key={c.id}>
                {c.numero}{c.nom ? ` — ${c.nom}` : ''}
                {c.type_chambre_libelle ? ` (${c.type_chambre_libelle})` : ''}
                {' · '}{c.statut_display ?? c.statut}
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={creerChambre} noValidate>
          <label htmlFor="ch-type">Type de chambre</label>
          <select id="ch-type" value={formChambre.type_chambre}
                  onChange={(e) => setFormChambre(f => ({ ...f, type_chambre: e.target.value }))}>
            <option value="">— Choisir un type —</option>
            {types.map((t) => (
              <option key={t.id} value={String(t.id)}>{t.libelle}</option>
            ))}
          </select>
          <label htmlFor="ch-numero">Numéro</label>
          <input id="ch-numero" value={formChambre.numero}
                 onChange={(e) => setFormChambre(f => ({ ...f, numero: e.target.value }))}
                 placeholder="ex : 101" />
          <label htmlFor="ch-nom">Nom (facultatif)</label>
          <input id="ch-nom" value={formChambre.nom}
                 onChange={(e) => setFormChambre(f => ({ ...f, nom: e.target.value }))} />
          <label htmlFor="ch-etage">Étage</label>
          <input id="ch-etage" type="number" step="any" value={formChambre.etage}
                 onChange={(e) => setFormChambre(f => ({ ...f, etage: e.target.value }))} />
          <label htmlFor="ch-statut">Statut</label>
          <select id="ch-statut" value={formChambre.statut}
                  onChange={(e) => setFormChambre(f => ({ ...f, statut: e.target.value }))}>
            {STATUTS_CHAMBRE.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <label htmlFor="ch-vue">Vue</label>
          <input id="ch-vue" value={formChambre.vue}
                 onChange={(e) => setFormChambre(f => ({ ...f, vue: e.target.value }))}
                 placeholder="ex : mer, jardin" />
          <button type="submit" disabled={occupe || types.length === 0}>
            Créer la chambre
          </button>
        </form>
      </section>

      {/* ── 3. Plans tarifaires ── */}
      <section>
        <h4>3. Plans tarifaires</h4>
        {plans.length === 0 ? (
          <p>
            Aucun plan tarifaire : sans lui, une réservation ne porte aucun prix
            et le folio reste vide.
          </p>
        ) : (
          <ul>
            {plans.map((p) => (
              <li key={p.id}>
                {p.canal_display ?? p.canal} · {p.prix_nuit_ht} / nuit
                {p.date_debut || p.date_fin
                  ? ` (${p.date_debut || '—'} → ${p.date_fin || '—'})` : ''}
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={creerPlan} noValidate>
          <label htmlFor="pt-type">Type de chambre</label>
          <select id="pt-type" value={formPlan.type_chambre}
                  onChange={(e) => setFormPlan(f => ({ ...f, type_chambre: e.target.value }))}>
            <option value="">— Choisir un type —</option>
            {types.map((t) => (
              <option key={t.id} value={String(t.id)}>{t.libelle}</option>
            ))}
          </select>
          <label htmlFor="pt-canal">Canal</label>
          <select id="pt-canal" value={formPlan.canal}
                  onChange={(e) => setFormPlan(f => ({ ...f, canal: e.target.value }))}>
            {CANAUX.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
          <label htmlFor="pt-debut">Début de la période</label>
          <input id="pt-debut" type="date" value={formPlan.date_debut}
                 onChange={(e) => setFormPlan(f => ({ ...f, date_debut: e.target.value }))} />
          <label htmlFor="pt-fin">Fin de la période</label>
          <input id="pt-fin" type="date" value={formPlan.date_fin}
                 onChange={(e) => setFormPlan(f => ({ ...f, date_fin: e.target.value }))} />
          <label htmlFor="pt-prix">Prix par nuit (HT)</label>
          {/* step="any" : aucune valeur saisie n'est snappée ni refusée. */}
          <input id="pt-prix" type="number" step="any" value={formPlan.prix_nuit_ht}
                 onChange={(e) => setFormPlan(f => ({ ...f, prix_nuit_ht: e.target.value }))} />
          <label htmlFor="pt-min">Nuits minimum</label>
          <input id="pt-min" type="number" step="any" value={formPlan.min_nuits}
                 onChange={(e) => setFormPlan(f => ({ ...f, min_nuits: e.target.value }))} />
          <button type="submit" disabled={occupe || types.length === 0}>
            Créer le plan tarifaire
          </button>
        </form>
      </section>
    </div>
  )
}
