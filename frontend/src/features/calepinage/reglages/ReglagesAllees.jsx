import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { Card } from '../../../ui'
import LectureSeuleSociete from '../commun/LectureSeuleSociete'
import { usePeutReglerSociete } from '../commun/useReglagesSociete'

/* ============================================================================
   ACAL893 — « RÉGLAGES › CALEPINAGE › ALLÉES » : le défaut de la société.
   ----------------------------------------------------------------------------
   Déplacé tel quel hors de l'atelier (`PanneauAllees.jsx`, ACAL258) : l'allée
   technique par défaut et les allées de circulation par pays s'écrivent ICI,
   avec la MÊME écriture (`calepinageApi.parametres.update({ degagements })`),
   la même confirmation (« ce défaut s'applique à tous vos calepinages ») et
   la même préservation du reste de la section. L'atelier ne garde que l'allée
   de CE calepinage (le document) et un lien vers cette page.
   ========================================================================== */

/** `allees_circulation` du serveur → lignes de formulaire (chaînes), une par pays. */
function lignesCirculation(brut) {
  if (!Array.isArray(brut)) return []
  return brut.map((e) => ({
    pays: String(e?.pays ?? ''), largeur_m: e?.largeur_m == null ? '' : String(e.largeur_m),
    source: String(e?.source ?? ''), reference: String(e?.reference ?? ''),
  }))
}
const ligneVide = (l) => Object.values(l).every((v) => String(v).trim() === '')
/** Le corps posté d'une ligne : texte rogné, largeur numérique ; le serveur valide et REFUSE. */
const corpsCirculation = (l) => ({
  pays: l.pays.trim().toLowerCase(),
  largeur_m: l.largeur_m.trim() === '' ? null : Number(l.largeur_m),
  source: l.source.trim(),
  reference: l.reference.trim(),
})
const CHAMPS_LIGNE = [['pays', 'Pays (2 lettres)'], ['largeur_m', 'Largeur (m)'], ['source', 'Source'], ['reference', 'Référence']]
const CLASSE_ETIQUETTE = 'text-xs font-semibold uppercase tracking-wide text-muted-foreground'
const CLASSE_CHAMP = 'mt-1 rounded border border-border bg-[var(--cal-surface)] px-2 py-1 text-sm text-foreground'

export default function ReglagesAllees() {
  const peutGerer = usePeutReglerSociete()
  const [parametres, setParametres] = useState(null)
  const [champ, setChamp] = useState('')
  const [source, setSource] = useState('')
  const [circulation, setCirculation] = useState([])
  const [confirme, setConfirme] = useState(false)
  const [enregistrement, setEnregistrement] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    let annule = false
    Promise.resolve(calepinageApi.parametres.get()).then((res) => {
      if (annule) return
      const reglages = res?.data ?? null
      setParametres(reglages)
      const actuelle = reglages?.degagements?.allee_technique_m
      setChamp(Number.isFinite(actuelle) ? String(actuelle) : '')
      setSource(typeof reglages?.degagements?.source === 'string' ? reglages.degagements.source : '')
      setCirculation(lignesCirculation(reglages?.degagements?.allees_circulation))
    }).catch(() => { if (!annule) setMessage('Réglages indisponibles.') })
    return () => { annule = true }
  }, [])

  const enregistrer = () => {
    setEnregistrement(true)
    setMessage(null)
    const nombre = champ === '' ? null : Number(champ)
    if (champ !== '' && !Number.isFinite(nombre)) {
      setMessage('L’allée technique doit être un nombre de mètres.')
      setEnregistrement(false)
      return
    }
    const section = { ...(parametres?.degagements ?? {}) }
    if (nombre === null) delete section.allee_technique_m
    else section.allee_technique_m = nombre
    if (source.trim()) section.source = source.trim()
    else delete section.source
    const lignes = circulation.filter((l) => !ligneVide(l))
    if (lignes.length) section.allees_circulation = lignes.map(corpsCirculation)
    else delete section.allees_circulation
    Promise.resolve(calepinageApi.parametres.update({ degagements: section }))
      .then((res) => {
        setParametres(res?.data ?? null)
        setConfirme(false)
        setMessage('Défaut de la société enregistré — il s’applique à tous vos calepinages.')
      })
      .catch((e) => setMessage(
        e?.response?.data?.['degagements.allee_technique_m']
        || e?.response?.data?.degagements
        || 'L’allée technique n’a pas pu être enregistrée.'))
      .finally(() => setEnregistrement(false))
  }

  return (
    <div className="page cal-reglages flex flex-col gap-4" data-testid="acal893-ecran">
      <div className="flex flex-col gap-1">
        <a href="/calepinage/reglages" className="text-xs underline">← Réglages simulation</a>
        <h1 className="text-lg font-semibold text-foreground">Allées</h1>
        <p className="text-sm text-muted-foreground">
          Le défaut de la société s’applique à tous vos calepinages ; l’allée d’un calepinage se règle dans son atelier.
        </p>
        {!peutGerer && <LectureSeuleSociete />}
      </div>
      <Card className="p-4">
        <section data-testid="cal-allees-societe">
          <p className={CLASSE_ETIQUETTE}>Défaut de la société</p>
          <label className="mt-2 block max-w-xs" data-testid="cal-allees-champ">
            <span className={CLASSE_ETIQUETTE}>Largeur d’allée technique par défaut (m)</span>
            <input type="number" step="any" min="0" id="cal-allees-largeur" value={champ}
              onChange={(e) => setChamp(e.target.value)} disabled={!peutGerer} className={`${CLASSE_CHAMP} w-full`} />
          </label>
          {/* D-ACAL-105 — UNE source pour la largeur d'allée par défaut ET le retrait de bord par défaut :
              la clé `degagements.source`, celle que « Sources des paramètres » lit déjà. */}
          <label className="mt-2 block max-w-xs" data-testid="cal-allees-source">
            <span className={CLASSE_ETIQUETTE}>Source</span>
            <input type="text" id="cal-allees-source" value={source}
              onChange={(e) => setSource(e.target.value)} disabled={!peutGerer} className={`${CLASSE_CHAMP} w-full`} />
            <span className="mt-1 block text-xs text-muted-foreground">
              D’où viennent la largeur d’allée par défaut et le retrait de bord par défaut (notice, norme, relevé…).
              Cette source vaut pour les deux.
            </span>
          </label>

          <div className="mt-3" data-testid="cal-allees-circulation">
            <p className={CLASSE_ETIQUETTE}>Allées de circulation par pays</p>
            {circulation.map((l, i) => (
              <div key={i} className="mt-2 flex flex-wrap items-end gap-2" data-testid={`cal-allees-circulation-${i}`}>
                {CHAMPS_LIGNE.map(([cle, libelle]) => (
                  <label key={cle} className="block">
                    <span className={CLASSE_ETIQUETTE}>{libelle}</span>
                    <input id={`cal-allees-circulation-${i}-${cle}`} value={l[cle]}
                      onChange={(e) => setCirculation((c) => c.map((x, j) => (j === i ? { ...x, [cle]: e.target.value } : x)))}
                      disabled={!peutGerer} className={`${CLASSE_CHAMP} w-32`} />
                  </label>
                ))}
                {peutGerer && (
                  <button type="button" onClick={() => setCirculation((c) => c.filter((_, j) => j !== i))}
                    className="min-h-11 rounded border border-border px-3 py-1 text-xs text-foreground">
                    Retirer
                  </button>
                )}
              </div>
            ))}
            {peutGerer && (
              <button type="button" data-testid="cal-allees-circulation-ajouter"
                onClick={() => setCirculation((c) => [...c, { pays: '', largeur_m: '', source: '', reference: '' }])}
                className="mt-2 min-h-11 rounded border border-border px-3 py-1.5 text-xs font-semibold text-foreground">
                Ajouter un pays
              </button>
            )}
          </div>

          {peutGerer && (
            <label className="mt-3 flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={confirme} data-testid="cal-allees-confirmer-societe"
                onChange={(e) => setConfirme(e.target.checked)} />
              Je confirme : ce défaut s’applique à tous vos calepinages.
            </label>
          )}
          {peutGerer && (
            <div className="mt-3">
              <button type="button" onClick={enregistrer} disabled={enregistrement || !confirme}
                data-testid="cal-allees-enregistrer"
                className="min-h-11 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-primary-text disabled:opacity-60">
                Enregistrer le défaut de la société
              </button>
            </div>
          )}
        </section>
        {message && (
          <p className="mt-3 text-sm text-foreground" role="status" data-testid="cal-allees-message">{message}</p>
        )}
      </Card>
    </div>
  )
}
