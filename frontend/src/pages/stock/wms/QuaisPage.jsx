import { useCallback, useEffect, useState } from 'react'
import { Button, Input } from '../../../ui'
import { EnteteStock, BandeauxStock } from '../EnteteStock'
import quaisApi from '../../../features/stock/api/quaisApi'
import { messageServeur, telechargerTexte } from '../../../features/stock/api/erreurs'
import { todayLocalIso } from '../../../lib/dateLocale.js'

/* ASTK218 — Quais & rendez-vous : quais (création / activation), planning
   d'une journée avec, pour chaque rendez-vous, le fournisseur et le BCF
   (clés ASTK192), création / annulation d'un rendez-vous transporteur,
   import / export d'un ASN.

   Aucun état local persistant : chaque geste relit le serveur. Un
   chevauchement (400 serveur) est affiché mot pour mot. */

const liste = (d) => (Array.isArray(d) ? d : d?.results ?? [])
const STATUTS = {
  planifie: 'Planifié', arrive: 'Arrivé', en_cours: 'En cours',
  termine: 'Terminé', no_show: 'Non présenté', annule: 'Annulé',
}
const TYPES_QUAI = { reception: 'Réception', expedition: 'Expédition', mixte: 'Mixte' }
const selectCls = 'h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm'
const aujourdhui = () => todayLocalIso()
const heure = (iso) => (iso
  ? new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  : '—')

const Section = ({ id, titre, children }) => (
  <section aria-labelledby={id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
    <h2 id={id} className="mb-3 text-sm font-semibold">{titre}</h2>
    {children}
  </section>
)
const Vide = ({ children }) => <p className="text-sm text-[var(--muted-foreground)]">{children}</p>

const lireFichier = (fichier) => new Promise((resolve, reject) => {
  const lecteur = new FileReader()
  lecteur.onload = () => resolve(String(lecteur.result))
  lecteur.onerror = () => reject(lecteur.error)
  lecteur.readAsText(fichier)
})

export default function QuaisPage() {
  const [quais, setQuais] = useState([])
  const [emplacements, setEmplacements] = useState([])
  const [planning, setPlanning] = useState(null)
  const [rdvs, setRdvs] = useState([])
  const [unites, setUnites] = useState([])
  const [date, setDate] = useState(aujourdhui)
  const [vue, setVue] = useState('jour')
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [quaiForm, setQuaiForm] = useState({ nom: '', type_quai: 'reception', emplacement: '' })
  const [rdvForm, setRdvForm] = useState({ quai: '', debut: '', fin: '', chauffeur_nom: '', immatriculation: '' })
  const [uniteExport, setUniteExport] = useState('')
  const [resultatAsn, setResultatAsn] = useState(null)

  const charger = useCallback(async () => {
    const [q, p, r] = await Promise.allSettled([
      quaisApi.listQuais(),
      quaisApi.planning({ date, vue }),
      quaisApi.listRendezVous({ date }),
    ])
    if (q.status === 'fulfilled') setQuais(liste(q.value.data))
    if (p.status === 'fulfilled') setPlanning(p.value.data)
    if (r.status === 'fulfilled') setRdvs(liste(r.value.data))
    const ko = [q, p, r].find((x) => x.status === 'rejected')
    setErreur(ko ? messageServeur(ko.reason, 'Chargement impossible.') : null)
  }, [date, vue])

  useEffect(() => { Promise.resolve().then(charger) }, [charger])
  useEffect(() => {
    quaisApi.listEmplacements().then((r) => setEmplacements(liste(r.data))).catch(() => {})
    quaisApi.listUnites({ statut: 'scellee' }).then((r) => setUnites(liste(r.data))).catch(() => {})
  }, [])

  const geste = async (action, repli, succes) => {
    setOccupe(true); setErreur(null); setInfo(null)
    try {
      await action()
      if (succes) setInfo(succes)
      await charger()
      return true
    } catch (err) {
      setErreur(messageServeur(err, repli))
      return false
    } finally { setOccupe(false) }
  }

  const ajouterQuai = async (ev) => {
    ev.preventDefault()
    if (!quaiForm.nom.trim()) { setErreur('Le nom du quai est requis.'); return }
    const corps = { nom: quaiForm.nom.trim(), type_quai: quaiForm.type_quai, actif: true }
    if (quaiForm.emplacement) corps.emplacement = Number(quaiForm.emplacement)
    const ok = await geste(() => quaisApi.saveQuai(null, corps), "Le quai n'a pas pu être créé.")
    if (ok) setQuaiForm({ nom: '', type_quai: 'reception', emplacement: '' })
  }

  const creerRdv = async (ev) => {
    ev.preventDefault()
    if (!rdvForm.quai || !rdvForm.debut || !rdvForm.fin) {
      setErreur('Choisissez le quai, le début et la fin.'); return
    }
    const corps = {
      quai: Number(rdvForm.quai),
      date_heure_debut: new Date(rdvForm.debut).toISOString(),
      date_heure_fin: new Date(rdvForm.fin).toISOString(),
      chauffeur_nom: rdvForm.chauffeur_nom,
      immatriculation: rdvForm.immatriculation,
    }
    const ok = await geste(() => quaisApi.creerRendezVous(corps),
      "Le rendez-vous n'a pas pu être créé.")
    if (ok) setRdvForm({ quai: '', debut: '', fin: '', chauffeur_nom: '', immatriculation: '' })
  }

  const exporterAsn = async () => {
    if (!uniteExport) { setErreur('Choisissez une unité scellée.'); return }
    setErreur(null)
    try {
      const { data } = await quaisApi.exportAsn(uniteExport)
      telechargerTexte(`asn-${uniteExport}.json`, JSON.stringify(data, null, 2))
    } catch (err) { setErreur(messageServeur(err, "Export de l'ASN impossible.")) }
  }

  const importerAsn = async (ev) => {
    const fichier = ev.target.files?.[0]
    if (!fichier) return
    setErreur(null); setResultatAsn(null)
    let document
    try {
      document = JSON.parse(await lireFichier(fichier))
    } catch { setErreur("Ce fichier n'est pas un ASN JSON lisible."); return }
    try {
      const { data } = await quaisApi.importAsn(document)
      setResultatAsn(data)
    } catch (err) { setErreur(messageServeur(err, "Import de l'ASN impossible.")) }
  }

  const rdvParId = Object.fromEntries(rdvs.map((r) => [r.id, r]))
  const champ = (setter) => (k) => (e) => setter((f) => ({ ...f, [k]: e.target.value }))
  const champQuai = champ(setQuaiForm)
  const champRdv = champ(setRdvForm)

  return (
    <div className="space-y-4">
      <EnteteStock
                title="Quais et rendez-vous"
        subtitle="Planning des quais, rendez-vous transporteur et bordereaux ASN."
      />

      <BandeauxStock erreur={erreur} info={info} />

      <Section id="planning-quais" titre="Planning">
        <div className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Date du planning</span>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-40" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Vue</span>
            <select className={selectCls} value={vue} onChange={(e) => setVue(e.target.value)}>
              <option value="jour">Jour</option>
              <option value="semaine">Semaine</option>
            </select>
          </label>
        </div>
        {!planning || planning.quais.length === 0 ? <Vide>Aucun quai planifié.</Vide> : (
          <div className="space-y-3">
            {planning.quais.map((q) => (
              <div key={q.quai_id} className="rounded-md border border-[var(--border)] p-3">
                <h3 className="mb-2 text-sm font-medium">
                  {q.quai_nom} <span className="text-[var(--muted-foreground)]">({TYPES_QUAI[q.type_quai] ?? q.type_quai})</span>
                </h3>
                {q.rendez_vous.length === 0 ? <Vide>Aucun rendez-vous.</Vide> : (
                  <ul className="space-y-1 text-sm">
                    {q.rendez_vous.map((r) => {
                      const detail = rdvParId[r.id] ?? {}
                      return (
                        <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                          <span>{heure(r.debut)}–{heure(r.fin)}</span>
                          <span>{STATUTS[r.statut] ?? r.statut}</span>
                          <span>Fournisseur : {detail.fournisseur_nom || '—'}</span>
                          <span>BCF : {detail.bon_commande_reference || '—'}</span>
                          {r.transporteur_nom && <span>{r.transporteur_nom}</span>}
                          {r.statut !== 'annule' && (
                            <Button
                              size="sm" variant="outline" disabled={occupe}
                              aria-label={`Annuler le rendez-vous ${r.id}`}
                              onClick={() => geste(() => quaisApi.annulerRendezVous(r.id),
                                "Annulation impossible.")}
                            >Annuler</Button>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section id="nouveau-rdv" titre="Nouveau rendez-vous">
        <form onSubmit={creerRdv} noValidate className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Quai du rendez-vous</span>
            <select className={selectCls} value={rdvForm.quai} onChange={champRdv('quai')}>
              <option value="">—</option>
              {quais.map((q) => <option key={q.id} value={q.id}>{q.nom}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Début</span>
            <Input type="datetime-local" value={rdvForm.debut} onChange={champRdv('debut')} />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Fin</span>
            <Input type="datetime-local" value={rdvForm.fin} onChange={champRdv('fin')} />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Chauffeur</span>
            <Input value={rdvForm.chauffeur_nom} onChange={champRdv('chauffeur_nom')} className="w-40" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Immatriculation</span>
            <Input value={rdvForm.immatriculation} onChange={champRdv('immatriculation')} className="w-36" sanitize="code" />
          </label>
          <Button type="submit" disabled={occupe}>Créer le rendez-vous</Button>
        </form>
      </Section>

      <Section id="liste-quais" titre="Quais">
        <form onSubmit={ajouterQuai} noValidate className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Nom du quai</span>
            <Input value={quaiForm.nom} onChange={champQuai('nom')} className="w-40" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Type de quai</span>
            <select className={selectCls} value={quaiForm.type_quai} onChange={champQuai('type_quai')}>
              {Object.entries(TYPES_QUAI).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Emplacement du quai</span>
            <select className={selectCls} value={quaiForm.emplacement} onChange={champQuai('emplacement')}>
              <option value="">—</option>
              {emplacements.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}
            </select>
          </label>
          <Button type="submit" disabled={occupe}>Ajouter le quai</Button>
        </form>
        {quais.length === 0 ? <Vide>Aucun quai.</Vide> : (
          <ul className="space-y-1 text-sm">
            {quais.map((q) => (
              <li key={q.id} className="flex flex-wrap items-center gap-3">
                <strong>{q.nom}</strong>
                <span>{TYPES_QUAI[q.type_quai] ?? q.type_quai}</span>
                <span className="text-[var(--muted-foreground)]">{q.emplacement_nom ?? '—'}</span>
                <span>{q.actif ? 'Actif' : 'Inactif'}</span>
                <Button
                  size="sm" variant="outline" disabled={occupe}
                  aria-label={`${q.actif ? 'Désactiver' : 'Activer'} le quai ${q.nom}`}
                  onClick={() => geste(() => quaisApi.saveQuai(q.id, { actif: !q.actif }), 'Modification impossible.')}
                >{q.actif ? 'Désactiver' : 'Activer'}</Button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="asn" titre="ASN (bordereau d'expédition)">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs">
            <span>Unité à exporter</span>
            <select className={selectCls} value={uniteExport} onChange={(e) => setUniteExport(e.target.value)}>
              <option value="">—</option>
              {unites.map((u) => <option key={u.id} value={u.id}>{u.sscc}</option>)}
            </select>
          </label>
          <Button variant="outline" onClick={exporterAsn}>Exporter l'ASN</Button>
          <label className="flex flex-col gap-1 text-xs">
            <span>Fichier ASN</span>
            <input type="file" accept="application/json,.json" onChange={importerAsn} className="text-sm" />
          </label>
        </div>
        {resultatAsn && (
          <div className="mt-3 text-sm">
            {resultatAsn.valide ? (
              <>
                <p>ASN valide — SSCC {resultatAsn.sscc}{resultatAsn.unite_connue ? ' (unité connue)' : ''}.</p>
                <ul className="mt-1 space-y-1">
                  {resultatAsn.lignes.map((l, i) => (
                    <li key={i}>{l.sku} — {l.designation} × {l.quantite}{l.numero_lot ? ` (lot ${l.numero_lot})` : ''}</li>
                  ))}
                </ul>
              </>
            ) : (
              <ul className="space-y-1 text-destructive">
                {resultatAsn.erreurs.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
          </div>
        )}
      </Section>
    </div>
  )
}
