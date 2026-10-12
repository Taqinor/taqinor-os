import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ListChecks } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card, Input, Label, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { refusParChamp } from './entreeElectrique'
import { TERRE_CHAMPS, corpsDeDecisions, depuisEntree } from './DecisionsElectriques.helpers'

/* ============================================================================
   ACAL154 — L'ONGLET « DÉCISIONS ÉLECTRIQUES » DE L'ATELIER.
   ----------------------------------------------------------------------------
   Les décisions de la société sur la check-list de protections (écarter un organe AVEC son
   motif écrit, en ajouter un), sur la check-list de terre (justification de continuité,
   point et date de mesure) et sur le polystring (pans regroupés sur une entrée MPPT).
   Postées par `POST entree-electrique/` ({protections, terre, polystring}), relues par
   `GET entree-electrique/`. Le refus du serveur s'affiche SOUS la ligne visée, mot pour
   mot ; aucun organe n'est décidé côté écran — l'écran ne calcule rien.
   ========================================================================== */

const idChamp = (cle) => `acal154-champ-${cle}`

/** Le message du serveur le plus précis pour une ligne : `<prefixe>.<champ>` puis le préfixe. */
function refusDeLigne(erreurs, prefixes, champ) {
  for (const prefixe of prefixes) {
    const trouve = erreurs[`${prefixe}.${champ}`] ?? erreurs[prefixe]
    if (trouve) return trouve
  }
  return undefined
}

const messageErreur = (err, defaut) => {
  const parChamp = refusParChamp(err?.response?.data)
  return Object.keys(parChamp).length ? parChamp : { decisions: defaut }
}

function Ligne({ children, onRetirer, testid, erreurs }) {
  return (
    <li className="flex flex-col gap-1 border border-white/10 p-2" data-testid={testid}>
      <div className="flex flex-wrap items-end gap-2">
        {children}
        <Button type="button" variant="ghost" onClick={onRetirer}>Retirer</Button>
      </div>
      {erreurs.map((m) => (
        <p key={m} className="text-xs text-destructive" data-testid={`${testid}-erreur`}>{m}</p>
      ))}
    </li>
  )
}

export default function DecisionsElectriques({ calepinageId, lectureSeule = false } = {}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const [entree, setEntree] = useState(null)
  const [etat, setEtat] = useState(null)
  const [erreurLecture, setErreurLecture] = useState(null)
  const [enregistrement, setEnregistrement] = useState(false)
  const [erreurs, setErreurs] = useState({})

  const lire = useCallback(() => calepinageApi.calepinages.entreeElectrique(id)
    .then((res) => {
      const lue = res?.data?.entree ?? {}
      setEntree(lue)
      setEtat(depuisEntree(lue))
      setErreurLecture(null)
    })
    .catch(() => setErreurLecture('Décisions électriques indisponibles.')), [id])

  useEffect(() => { lire() }, [lire])

  const changer = (liste, i, cle, valeur) => setEtat((s) => ({
    ...s, [liste]: s[liste].map((l, j) => (j === i ? { ...l, [cle]: valeur } : l)),
  }))
  const ajouter = (liste, ligne) => setEtat((s) => ({ ...s, [liste]: [...s[liste], ligne] }))
  const retirer = (liste, i) => setEtat((s) => ({ ...s, [liste]: s[liste].filter((_, j) => j !== i) }))
  const poserTerre = (cle, valeur) => setEtat((s) => ({ ...s, terre: { ...s.terre, [cle]: valeur } }))

  const enregistrer = (evenement) => {
    evenement.preventDefault()
    setEnregistrement(true)
    setErreurs({})
    calepinageApi.calepinages.enregistrerEntreeElectrique(id, corpsDeDecisions(etat, entree))
      .then(() => lire())
      .catch((err) => setErreurs(messageErreur(err, 'Décisions non enregistrées : le serveur n’a pas accepté la saisie.')))
      .finally(() => setEnregistrement(false))
  }

  if (erreurLecture) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="decisions-electriques" />
        <p className="text-sm text-destructive" data-testid="acal154-erreur">{erreurLecture}</p>
      </>
    )
  }
  if (!etat) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="decisions-electriques" />
        <Spinner />
      </>
    )
  }

  /* Un refus se pose sous la LIGNE qu'il vise : motif ⇒ les lignes sans motif, repère ⇒ celles
     sans repère (ou dont le message cite le repère), désignation/quantité de même. */
  const ecart = (l) => [
    l.motif.trim() === '' ? refusDeLigne(erreurs, ['protections.ecartes'], 'motif') : null,
    l.repere.trim() === '' || (erreurs['protections.ecartes.repere'] ?? '').includes(`« ${l.repere.trim()} »`)
      ? refusDeLigne(erreurs, ['protections.ecartes'], 'repere') : null,
  ].filter(Boolean)
  const ajout = (l) => [
    l.designation.trim() === '' ? refusDeLigne(erreurs, ['protections.ajouts'], 'designation') : null,
    l.motif.trim() === '' ? refusDeLigne(erreurs, ['protections.ajouts'], 'motif') : null,
    l.quantite.trim() !== '' ? erreurs['protections.ajouts.quantite'] : null,
  ].filter(Boolean)
  const groupe = (i) => Object.entries(erreurs)
    .filter(([cle]) => cle === `groupes.${i}` || cle.startsWith(`groupes.${i}.`))
    .map(([, m]) => m)
  const connu = (cle) => cle.startsWith('protections') || cle.startsWith('terre.') || cle.startsWith('groupes')
  const generaux = Object.entries(erreurs).filter(([cle]) => !connu(cle)).map(([cle, m]) => `${cle} : ${m}`)

  return (
    <>
      <RetourAtelier calepinageId={id} cle="decisions-electriques" />
      <Card className="flex flex-col gap-4 p-4" data-testid="acal154-panneau">
        <header className="flex items-center gap-2">
          <ListChecks size={16} aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <h2 className="text-base font-semibold">Décisions électriques</h2>
            <p className="text-sm text-muted-foreground">
              Ce que la société décide sur les protections, la mise à la terre et le regroupement des pans.
              Un organe écarté reste listé, barré, avec son motif ; un organe ajouté est une « décision société ».
            </p>
          </div>
        </header>

        {generaux.length
          ? <p role="alert" className="text-sm text-destructive" data-testid="acal154-bandeau">{generaux.join(' ')}</p>
          : null}

        <form className="flex flex-col gap-5" onSubmit={enregistrer} data-testid="acal154-formulaire">
          <section className="flex flex-col gap-2" data-testid="acal154-protections">
            <h3 className="text-sm font-semibold">Protections — organes écartés</h3>
            {erreurs.protections
              ? <p className="text-xs text-destructive" data-testid="acal154-erreur-protections">{erreurs.protections}</p>
              : null}
            <ul className="flex flex-col gap-2">
              {etat.ecartes.map((l, i) => (
                <Ligne key={`e${i}`} testid={`acal154-ecarte-${i}`} erreurs={ecart(l)} onRetirer={() => retirer('ecartes', i)}>
                  <div className="flex flex-col gap-1">
                    <Label htmlFor={idChamp(`ecarte-${i}-repere`)}>Repère de l’organe</Label>
                    <Input id={idChamp(`ecarte-${i}-repere`)} value={l.repere} onChange={(e) => changer('ecartes', i, 'repere', e.target.value)} />
                  </div>
                  <div className="flex min-w-[12rem] flex-1 flex-col gap-1">
                    <Label htmlFor={idChamp(`ecarte-${i}-motif`)}>Motif écrit</Label>
                    <Input id={idChamp(`ecarte-${i}-motif`)} value={l.motif} onChange={(e) => changer('ecartes', i, 'motif', e.target.value)} />
                  </div>
                </Ligne>
              ))}
            </ul>
            <div>
              <Button type="button" variant="outline" onClick={() => ajouter('ecartes', { repere: '', motif: '' })} data-testid="acal154-ajouter-ecarte">
                Écarter un organe
              </Button>
            </div>

            <h3 className="mt-2 text-sm font-semibold">Protections — organes ajoutés (décision société)</h3>
            <ul className="flex flex-col gap-2">
              {etat.ajouts.map((l, i) => (
                <Ligne key={`a${i}`} testid={`acal154-ajout-${i}`} erreurs={ajout(l)} onRetirer={() => retirer('ajouts', i)}>
                  {[['designation', 'Désignation'], ['quantite', 'Quantité'], ['calibre', 'Calibre'], ['motif', 'Motif']].map(([cle, libelle]) => (
                    <div key={cle} className="flex min-w-[8rem] flex-1 flex-col gap-1">
                      <Label htmlFor={idChamp(`ajout-${i}-${cle}`)}>{libelle}</Label>
                      <Input id={idChamp(`ajout-${i}-${cle}`)} value={l[cle]} onChange={(e) => changer('ajouts', i, cle, e.target.value)} />
                    </div>
                  ))}
                </Ligne>
              ))}
            </ul>
            <div>
              <Button type="button" variant="outline" onClick={() => ajouter('ajouts', { repere: '', designation: '', calibre: '', quantite: '', motif: '' })} data-testid="acal154-ajouter-ajout">
                Ajouter un organe
              </Button>
            </div>
          </section>

          <section className="flex flex-col gap-2" data-testid="acal154-terre">
            <h3 className="text-sm font-semibold">Mise à la terre</h3>
            {Object.entries(erreurs)
              .filter(([cle]) => cle.startsWith('terre.') && !TERRE_CHAMPS.some((c) => cle === `terre.${c.cle}`))
              .map(([cle, m]) => <p key={cle} className="text-xs text-destructive">{m}</p>)}
            <div className="grid gap-3 sm:grid-cols-2">
              {TERRE_CHAMPS.map(({ cle, libelle, genre }) => (
                <div key={cle} className="flex flex-col gap-1">
                  {genre === 'bool'
                    ? (
                      <label className="flex items-center gap-2 text-sm" htmlFor={idChamp(cle)}>
                        <input
                          id={idChamp(cle)}
                          type="checkbox"
                          checked={etat.terre[cle]}
                          onChange={(e) => poserTerre(cle, e.target.checked)}
                        />
                        {libelle}
                      </label>
                    )
                    : (
                      <>
                        <Label htmlFor={idChamp(cle)}>{libelle}</Label>
                        <Input
                          id={idChamp(cle)}
                          type={genre === 'nombre' ? 'number' : 'text'}
                          step={genre === 'nombre' ? 'any' : undefined}
                          invalid={Boolean(erreurs[`terre.${cle}`])}
                          value={etat.terre[cle]}
                          onChange={(e) => poserTerre(cle, e.target.value)}
                        />
                      </>
                    )}
                  {erreurs[`terre.${cle}`]
                    ? <p className="text-xs text-destructive" data-testid={`acal154-erreur-${cle}`}>{erreurs[`terre.${cle}`]}</p>
                    : null}
                </div>
              ))}
            </div>
          </section>

          <section className="flex flex-col gap-2" data-testid="acal154-polystring">
            <h3 className="text-sm font-semibold">Polystring — pans regroupés sur une entrée MPPT</h3>
            {erreurs.groupes
              ? <p className="text-xs text-destructive" data-testid="acal154-erreur-groupes">{erreurs.groupes}</p>
              : null}
            <ul className="flex flex-col gap-2">
              {etat.polystring.map((g, i) => (
                <Ligne key={`p${i}`} testid={`acal154-groupe-${i}`} erreurs={groupe(i)} onRetirer={() => retirer('polystring', i)}>
                  <div className="flex flex-col gap-1">
                    <Label htmlFor={idChamp(`groupe-${i}-mppt`)}>Entrée MPPT</Label>
                    <Input id={idChamp(`groupe-${i}-mppt`)} type="number" value={g.mppt} onChange={(e) => changer('polystring', i, 'mppt', e.target.value)} />
                  </div>
                  <div className="flex min-w-[12rem] flex-1 flex-col gap-1">
                    <Label htmlFor={idChamp(`groupe-${i}-pans`)}>Pans (séparés par des virgules)</Label>
                    <Input id={idChamp(`groupe-${i}-pans`)} value={g.pans} onChange={(e) => changer('polystring', i, 'pans', e.target.value)} />
                  </div>
                </Ligne>
              ))}
            </ul>
            <div>
              <Button type="button" variant="outline" onClick={() => ajouter('polystring', { mppt: '', pans: '' })} data-testid="acal154-ajouter-groupe">
                Regrouper des pans
              </Button>
            </div>
          </section>

          <div>
            <Button type="submit" disabled={enregistrement || lectureSeule} data-testid="acal154-enregistrer">
              {enregistrement ? 'Enregistrement…' : 'Enregistrer les décisions'}
            </Button>
          </div>
        </form>
      </Card>
    </>
  )
}
