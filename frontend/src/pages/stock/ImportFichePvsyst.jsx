import { useId, useState } from 'react'
import { Button, FileUpload } from '../../ui'
import stockApi from '../../api/stockApi'
import { getApiError } from '../../lib/apiError'
import { LIBELLES_FICHE } from './pvondFicheTechnique'

/* CALX357 — dépôt d'un fichier PVsyst .PAN (module) / .OND (onduleur) depuis
   le formulaire produit. Le lecteur serveur existe déjà (CAL117, complété par
   CALX356 : `POST stock/fiches-techniques/importer-datasheet/`) ; cet écran
   en est la seule entrée.

   Deux temps, jamais un : le dépôt demande un APERÇU (rien n'est écrit), puis
   « Appliquer à la fiche » renvoie le même fichier avec `confirmer=true` — le
   serveur n'écrit alors que les champs encore vides. Les trois listes de
   l'aperçu (champs repris / champs du fichier non utilisés / champs attendus
   absents) sont toujours affichées, même vides, avec leur libellé : une clé
   inconnue n'est jamais devinée, un champ absent n'est jamais rempli.
   Forme de la réponse : apps/stock/contract_samples/fiche_import_pan_ond.json. */

const ACCEPT = '.pan,.ond'

// Champs que le lecteur sait remplir mais que LIBELLES_FICHE ne nomme pas.
const LIBELLES_EN_PLUS = {
  epaisseur_mm: 'Épaisseur (mm)',
  poids_kg: 'Poids (kg)',
  ond_conso_nuit_w: 'Consommation de nuit (W)',
}

function libelleChamp(champ) {
  return LIBELLES_FICHE[champ] || LIBELLES_EN_PLUS[champ] || champ
}

function ListeApercu({ titre, elements, testId }) {
  return (
    <div data-testid={testId}>
      <p className="text-sm font-medium text-foreground">
        {titre} ({elements.length})
      </p>
      {elements.length === 0 ? (
        <p className="text-xs text-muted-foreground">Aucun</p>
      ) : (
        <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
          {elements.map((el) => <li key={el}>{el}</li>)}
        </ul>
      )}
    </div>
  )
}

export default function ImportFichePvsyst({ produitId, onApplique }) {
  const erreurId = useId()
  const [fichier, setFichier] = useState(null)
  const [apercu, setApercu] = useState(null)
  const [refus, setRefus] = useState(null) // { nom, message }
  const [enCours, setEnCours] = useState(false)
  const [resultat, setResultat] = useState(null)

  const demanderApercu = async (file) => {
    setFichier(file)
    setApercu(null)
    setResultat(null)
    setRefus(null)
    setEnCours(true)
    try {
      const res = await stockApi.deposerFichierPvsyst(produitId, file)
      setApercu(res.data)
    } catch (err) {
      setRefus({ nom: file.name, message: getApiError(err, 'Fichier refusé.').message })
    } finally {
      setEnCours(false)
    }
  }

  const appliquer = async () => {
    if (!fichier) return
    setEnCours(true)
    setRefus(null)
    try {
      const res = await stockApi.deposerFichierPvsyst(produitId, fichier, true)
      setResultat(res.data)
      setApercu(null)
      onApplique?.(res.data?.fiche ?? null)
    } catch (err) {
      setRefus({ nom: fichier.name, message: getApiError(err, 'Import refusé.').message })
    } finally {
      setEnCours(false)
    }
  }

  const rejeterLocalement = (rejetes) => {
    const premier = rejetes[0]
    setApercu(null)
    setResultat(null)
    setRefus({ nom: premier?.file?.name ?? '', message: premier?.error ?? 'Fichier refusé.' })
  }

  const repris = apercu
    ? Object.entries(apercu.mapping ?? {}).map(([champ, valeur]) => `${libelleChamp(champ)} : ${valeur}`)
    : []
  const dejaSaisis = apercu?.deja_saisis ?? []
  const controlesOmis = apercu?.controles_omis ?? []

  return (
    <div className="flex flex-col gap-3" data-testid="import-fiche-pvsyst">
      <p className="text-sm font-medium text-foreground">
        Importer un fichier PVsyst (.PAN module, .OND onduleur)
      </p>

      {refus && (
        <div role="alert" data-testid="pvsyst-bandeau"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Import refusé{refus.nom ? ` : ${refus.nom}` : ''} — rien n’a été écrit.
        </div>
      )}

      <FileUpload
        accept={ACCEPT}
        busy={enCours}
        onFiles={(files) => demanderApercu(files[0])}
        onReject={rejeterLocalement}
        hint="aperçu d’abord, rien n’est écrit sans confirmation"
        aria-describedby={refus ? erreurId : undefined}
        aria-label="Fichier PVsyst .PAN ou .OND"
      />
      {refus && (
        <p id={erreurId} className="text-xs text-destructive" data-testid="pvsyst-erreur">
          {refus.message}
        </p>
      )}

      {apercu && (
        <div className="flex flex-col gap-3 rounded-md border border-border p-3" data-testid="pvsyst-apercu">
          <p className="text-xs text-muted-foreground">
            Aperçu de {fichier?.name} ({apercu.type_fiche === 'onduleur' ? 'onduleur' : 'module'}) — rien n’est encore écrit.
          </p>
          <ListeApercu titre="Champs repris" elements={repris} testId="pvsyst-repris" />
          {dejaSaisis.length > 0 && (
            <p className="text-xs text-muted-foreground" data-testid="pvsyst-deja-saisis">
              Déjà saisis, conservés tels quels : {dejaSaisis.map(libelleChamp).join(', ')}
            </p>
          )}
          {controlesOmis.length > 0 && (
            <p className="text-xs text-muted-foreground" data-testid="pvsyst-controles-omis">
              Contrôle non fait : {controlesOmis.join(' ; ')}
            </p>
          )}
          <ListeApercu titre="Champs du fichier non utilisés" elements={apercu.non_reconnus ?? []}
            testId="pvsyst-non-utilises" />
          <ListeApercu titre="Champs attendus absents"
            elements={(apercu.champs_attendus_absents ?? []).map(libelleChamp)}
            testId="pvsyst-absents" />
          <div>
            <Button type="button" onClick={appliquer} disabled={enCours || repris.length === 0}>
              Appliquer à la fiche
            </Button>
          </div>
        </div>
      )}

      {resultat && (
        <p role="status" className="text-sm text-foreground" data-testid="pvsyst-resultat">
          {resultat.ecrits?.length ?? 0} champ(s) écrit(s) dans la fiche technique.
        </p>
      )}
    </div>
  )
}
