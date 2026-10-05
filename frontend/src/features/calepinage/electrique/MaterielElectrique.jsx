/* eslint-disable react-refresh/only-export-components --
   `ROLES` et `libelleProvenance` sont une table et une fonction PURES que le test
   confronte directement (même dérogation que `Raccordement.jsx`). */
import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Cpu } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { Badge, Button, Card, Label, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { refusParChamp } from './entreeElectrique'

/* ============================================================================
   ACAL149 — L'ONGLET « MATÉRIEL ÉLECTRIQUE » DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT. Le calcul électrique n'avait aucun geste pour DÉSIGNER le module, l'onduleur
   et l'optimiseur : « module PV non désigné » restait sans issue. D-ACAL-10 : par défaut
   les lignes du devis lié, avec leur PROVENANCE visible ; sinon « à désigner », jamais un
   produit supposé.

   LA SOURCE est `GET`/`POST calepinages/<pk>/entree-electrique/` : les `candidats` (bornés à
   la société, SANS prix) viennent du serveur — aucun appel stock côté écran. Une fiche
   incomplète est LISTÉE grisée, avec ses `champs_manquants`, et n'est pas sélectionnable.
   Après l'enregistrement l'écran RELIT le GET : ce qu'il affiche est ce que le serveur a
   stocké (provenance « désigné »), pas ce qui a été tapé.
   ========================================================================== */

/** Les trois rôles : clé du corps posté, clé de `materiel`, clé de `candidats`, libellé. */
export const ROLES = [
  { role: 'module', champ: 'module_produit', candidats: 'modules', libelle: 'Module photovoltaïque' },
  { role: 'onduleur', champ: 'onduleur_produit', candidats: 'onduleurs', libelle: 'Onduleur' },
  { role: 'optimiseur', champ: 'optimiseur_produit', candidats: 'optimiseurs', libelle: 'Optimiseur (facultatif)' },
]

/** La provenance rendue en FRANÇAIS ; `null` = rien de désigné. */
export function libelleProvenance(materiel) {
  if (!materiel) return 'à désigner'
  if (materiel.provenance === 'devis') return 'ligne du devis'
  if (materiel.provenance === 'explicite') return 'désigné'
  return 'à désigner'
}

const idChamp = (champ) => `acal149-champ-${champ}`

export default function MaterielElectrique({ calepinageId, lectureSeule = false } = {}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const [bloc, setBloc] = useState(null)
  const [erreurLecture, setErreurLecture] = useState(null)
  const [choix, setChoix] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [enregistrement, setEnregistrement] = useState(false)

  const lire = useCallback(() => calepinageApi.calepinages.entreeElectrique(id)
    .then((res) => { setBloc(res?.data ?? null); setChoix(null); setErreurLecture(null) })
    .catch(() => setErreurLecture('Matériel électrique indisponible.')), [id])

  useEffect(() => { lire() }, [lire])

  const valeur = (role) => {
    if (choix && role.champ in choix) return choix[role.champ]
    return bloc?.materiel?.[role.role]?.produit_id ?? bloc?.entree?.[role.champ] ?? null
  }

  const enregistrer = (evenement) => {
    evenement.preventDefault()
    setEnregistrement(true)
    setErreurs({})
    const corps = {}
    for (const role of ROLES) corps[role.champ] = valeur(role)
    calepinageApi.calepinages.enregistrerEntreeElectrique(id, corps)
      .then(() => lire())
      .catch((err) => {
        const parChamp = refusParChamp(err?.response?.data)
        setErreurs(Object.keys(parChamp).length
          ? parChamp
          : { materiel: 'Matériel non enregistré : le serveur n’a pas accepté la désignation.' })
      })
      .finally(() => setEnregistrement(false))
  }

  if (erreurLecture) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="materiel-electrique" />
        <p className="text-sm text-destructive" data-testid="acal149-erreur">{erreurLecture}</p>
      </>
    )
  }
  if (!bloc) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="materiel-electrique" />
        <Spinner />
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={id} cle="materiel-electrique" />
      <Card className="flex flex-col gap-4 p-4" data-testid="acal149-panneau">
        <header className="flex items-center gap-2">
          <Cpu size={16} aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <h2 className="text-base font-semibold">Matériel électrique</h2>
            <p className="text-sm text-muted-foreground">
              Le module, l’onduleur et l’optimiseur du calcul électrique. Par défaut, les lignes du
              devis lié ; rien n’est supposé quand elles manquent.
            </p>
          </div>
        </header>

        {erreurs.materiel
          ? <p role="alert" className="text-sm text-destructive" data-testid="acal149-bandeau">{erreurs.materiel}</p>
          : null}

        <form className="flex flex-col gap-3" onSubmit={enregistrer} data-testid="acal149-formulaire">
          {ROLES.map((role) => {
            const lu = bloc.materiel?.[role.role] ?? null
            const candidats = bloc.candidats?.[role.candidats] ?? []
            const manque = (bloc.absents ?? []).includes(role.role)
            return (
              <div key={role.role} className="flex flex-col gap-1" data-testid={`acal149-role-${role.role}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <Label htmlFor={idChamp(role.champ)}>{role.libelle}</Label>
                  <Badge
                    tone={lu ? (lu.provenance === 'devis' ? 'info' : 'success') : 'neutral'}
                    data-testid={`acal149-provenance-${role.role}`}
                  >
                    {libelleProvenance(lu)}
                  </Badge>
                  {lu && lu.fiche_complete === false
                    ? <Badge tone="warning">fiche incomplète</Badge> : null}
                </div>
                <select
                  id={idChamp(role.champ)}
                  name={role.champ}
                  disabled={lectureSeule}
                  value={valeur(role) ?? ''}
                  aria-invalid={erreurs[role.champ] ? 'true' : undefined}
                  onChange={(e) => setChoix({
                    ...(choix ?? {}),
                    [role.champ]: e.target.value === '' ? null : Number(e.target.value),
                  })}
                  className="w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
                >
                  <option value="">{manque ? '— à désigner —' : '— aucun —'}</option>
                  {candidats.map((c) => {
                    const incomplet = c.fiche_complete === false
                    return (
                      <option
                        key={c.id}
                        value={c.id}
                        disabled={incomplet}
                        data-testid={`acal149-candidat-${c.id}`}
                      >
                        {incomplet
                          ? `${c.libelle} — fiche incomplète : ${(c.champs_manquants ?? []).join(', ')}`
                          : `${c.libelle}${c.marque ? ` (${c.marque})` : ''}${c.favori ? ' ★' : ''}`}
                      </option>
                    )
                  })}
                </select>
                {lu && lu.fiche_complete === false && (lu.champs_manquants ?? []).length
                  ? (
                    <p className="text-xs text-warning" data-testid={`acal149-manquants-${role.role}`}>
                      {`Champs manquants : ${lu.champs_manquants.join(', ')}`}
                    </p>
                  ) : null}
                {erreurs[role.champ]
                  ? (
                    <p className="text-xs text-destructive" data-testid={`acal149-erreur-${role.champ}`}>
                      {erreurs[role.champ]}
                    </p>
                  ) : null}
              </div>
            )
          })}
          <div>
            <Button type="submit" disabled={enregistrement || lectureSeule} data-testid="acal149-enregistrer">
              {enregistrement ? 'Enregistrement…' : 'Enregistrer le matériel'}
            </Button>
          </div>
        </form>
      </Card>
    </>
  )
}
