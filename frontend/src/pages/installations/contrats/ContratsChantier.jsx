// Onglet « Contrats » de la fiche chantier : le dossier contractuel — quatre
// actes (contrat, livraison, réception, clôture) en parcours. Tout vient du
// serveur (contrat : apps/documents/contract_samples/dossier_contractuel.json) :
// états, avertissements, gestes permis, montants (chaînes décimales). L'écran
// ne recalcule rien et ne montre qu'en mots l'état de chaque acte.
import { useEffect, useState } from 'react'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Button, Spinner, toast,
} from '../../../ui'
import documentsApi from '../../../api/documentsApi'
import { downloadBlob } from '../../../utils/downloadBlob'
import { useHasPermission, useIsAdmin } from '../../../hooks/useHasPermission'
import ActeEtape from './ActeEtape'
import ActeEditeur from './ActeEditeur'
import SignatureActeDialog from './SignatureActeDialog'
import SignaturePapierDialog from './SignaturePapierDialog'
import {
  actionPrincipale, detailErreur, formaterDh, grouperParRang,
} from './outils'

function nomFichier(acte) {
  const variante = acte.variante ? `-${acte.variante}` : ''
  return `${acte.reference}${variante}.pdf`
}

export default function ContratsChantier({
  installation, peutGerer = false, ouvrirApercu, rechargerApercu,
}) {
  const chantierId = installation?.id
  const [dossier, setDossier] = useState(null)
  const [etat, setEtat] = useState('chargement') // chargement | pret | erreur
  const [erreurChargement, setErreurChargement] = useState('')
  const [cle, setCle] = useState(0)
  const [occupe, setOccupe] = useState(null) // id de l'acte en cours d'action
  const [erreurs, setErreurs] = useState({}) // id d'acte → detail du serveur
  const [aEmettre, setAEmettre] = useState(null)
  const [aSigner, setASigner] = useState(null)
  const [surPapier, setSurPapier] = useState(null)
  const [aModifier, setAModifier] = useState(null)

  // Le Directeur (ou le palier admin) enregistre un modèle de société ; sinon
  // le serveur refuse et son `detail` s'affiche dans l'éditeur.
  const estDirecteur = useHasPermission(null, ['Directeur'])
  const estAdmin = useIsAdmin()
  const peutModele = peutGerer && (estDirecteur || estAdmin)

  useEffect(() => {
    if (!chantierId) return undefined
    let annule = false
    documentsApi.dossierContrats(chantierId)
      .then((res) => {
        if (annule) return
        setDossier(res.data)
        setEtat('pret')
      })
      .catch(async (err) => {
        const detail = await detailErreur(err)
        if (annule) return
        setErreurChargement(detail)
        setEtat('erreur')
      })
    return () => { annule = true }
  }, [chantierId, cle])

  const recharger = () => { setCle((k) => k + 1) }
  const reessayer = () => { setEtat('chargement'); recharger() }

  const annule = !!dossier?.chantier?.annule
  const peutEcrire = peutGerer && !annule

  const noterErreur = (id, detail) => setErreurs((e) => ({ ...e, [id]: detail }))
  const effacerErreur = (id) => setErreurs((e) => {
    if (!(id in e)) return e
    const reste = { ...e }
    delete reste[id]
    return reste
  })

  // Un geste serveur : le refus `{detail, code}` s'affiche sur l'acte, en place.
  const executer = async (acte, appel, succes) => {
    setOccupe(acte.id)
    effacerErreur(acte.id)
    try {
      await appel()
      if (succes) toast.success(succes)
      recharger()
      rechargerApercu?.()
      return true
    } catch (err) {
      noterErreur(acte.id, await detailErreur(err))
      return false
    } finally {
      setOccupe(null)
    }
  }

  const apercu = (acte) => {
    if (ouvrirApercu) {
      ouvrirApercu(acte.titre, nomFichier(acte), () => documentsApi.pdfActe(acte.id))
      return
    }
    telecharger(acte)
  }

  const telecharger = async (acte) => {
    setOccupe(acte.id)
    effacerErreur(acte.id)
    try {
      const res = await documentsApi.pdfActe(acte.id)
      downloadBlob(res.data, nomFichier(acte))
    } catch (err) {
      noterErreur(acte.id, await detailErreur(err))
    } finally {
      setOccupe(null)
    }
  }

  const surAction = (nom, acte) => {
    effacerErreur(acte.id)
    if (nom === 'apercu') apercu(acte)
    else if (nom === 'telecharger') telecharger(acte)
    else if (nom === 'modifier') setAModifier(acte)
    else if (nom === 'emettre') setAEmettre(acte)
    else if (nom === 'signer') setASigner(acte)
    else if (nom === 'papier') setSurPapier(acte)
    else if (nom === 'rouvrir') {
      executer(acte, () => documentsApi.rouvrirActe(acte.id), 'Acte rouvert : il redevient un brouillon.')
    }
  }

  const confirmerEmission = async () => {
    const acte = aEmettre
    setAEmettre(null)
    if (acte) await executer(acte, () => documentsApi.emettreActe(acte.id), 'Acte émis.')
  }

  if (etat === 'chargement') {
    return (
      <div className="contrats-chantier">
        <p className="contrats-chantier__chargement" role="status">
          <Spinner /> Chargement du dossier contractuel…
        </p>
      </div>
    )
  }

  if (etat === 'erreur') {
    return (
      <div className="contrats-chantier">
        <div className="contrats-chantier__refus" role="alert">
          <p>{erreurChargement}</p>
          <Button size="sm" variant="outline" className="contrats-acte__bouton" onClick={reessayer}>
            Réessayer
          </Button>
        </div>
      </div>
    )
  }

  const etapes = grouperParRang(dossier.actes)
  const sansDevis = !dossier.chantier.devis_id
  const prochaine = dossier.prochaine_action
  const acteProchain = prochaine
    ? dossier.actes.find((a) => a.id === prochaine.acte_id)
    : null
  const gestePrincipal = acteProchain ? actionPrincipale(acteProchain, peutEcrire) : null

  return (
    <div className="contrats-chantier">
      {annule && (
        <p className="contrats-chantier__bandeau" role="status">
          Ce chantier est annulé : les actes non signés sont annulés, aucun geste n’est possible.
          Un acte déjà signé reste signé.
        </p>
      )}
      {sansDevis && !annule && (
        <p className="contrats-chantier__bandeau" role="status">
          Ce chantier n’a pas de devis accepté : le prix et l’échéancier sont à préciser.
        </p>
      )}

      <section className="contrats-chantier__resume" aria-label="Situation du prix">
        <dl className="contrats-chantier__chiffres">
          <div>
            <dt>Prix</dt>
            <dd>{formaterDh(dossier.prix_ttc)}</dd>
          </div>
          <div>
            <dt>Réglé</dt>
            <dd>{formaterDh(dossier.regle_ttc)}</dd>
          </div>
          <div>
            <dt>Reste</dt>
            <dd>{formaterDh(dossier.reste_ttc)}</dd>
          </div>
        </dl>
        <p className="contrats-chantier__client">{dossier.client}</p>
        {prochaine && !annule && (
          <div className="contrats-chantier__prochaine">
            <p>
              <strong>Prochaine action :</strong> {prochaine.libelle}
            </p>
            {acteProchain && gestePrincipal && (
              <Button
                className="contrats-acte__bouton"
                disabled={occupe === acteProchain.id}
                onClick={() => surAction(gestePrincipal, acteProchain)}
              >
                {gestePrincipal === 'emettre' ? 'Émettre cet acte' : 'Faire signer sur place'}
              </Button>
            )}
          </div>
        )}
        {!prochaine && !annule && (
          <p className="contrats-chantier__prochaine">Tout le dossier contractuel est à jour.</p>
        )}
      </section>

      <ol className="contrats-parcours">
        {etapes.map((etape) => {
          const variantes = etape.actes.length > 1
          const fait = etape.actes.some((a) => a.statut === 'signe'
            || (a.statut === 'emis' && a.type === 'cloture_garanties'))
          const enCours = !fait && acteProchain?.rang === etape.rang
          return (
            <li
              key={etape.rang}
              className="contrats-parcours__etape"
              data-etat={fait ? 'fait' : (enCours ? 'en-cours' : 'a-venir')}
            >
              <span className="contrats-parcours__numero" aria-hidden="true">{etape.rang}</span>
              <div className="contrats-parcours__corps">
                <p className="contrats-parcours__rang">Étape {etape.rang} sur {etapes.length}</p>
                <div
                  className={variantes ? 'contrats-parcours__variantes' : 'contrats-parcours__seul'}
                >
                  {etape.actes.map((acte) => (
                    <ActeEtape
                      key={acte.id}
                      acte={acte}
                      peutEcrire={peutEcrire}
                      occupe={occupe === acte.id}
                      erreur={erreurs[acte.id]}
                      onAction={surAction}
                      enVariante={variantes}
                    />
                  ))}
                </div>
              </div>
            </li>
          )
        })}
      </ol>

      <AlertDialog open={!!aEmettre} onOpenChange={(o) => { if (!o) setAEmettre(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Émettre « {aEmettre?.titre} » ?</AlertDialogTitle>
            <AlertDialogDescription>
              Émettre fige le texte et le PDF. Tant que l’acte n’est pas signé, vous pourrez
              le rouvrir ; il repartira alors en version suivante.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction variant="default" onClick={confirmerEmission}>
              Émettre l’acte
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {aSigner && (
        <SignatureActeDialog
          open
          acte={aSigner}
          onOpenChange={(o) => { if (!o) setASigner(null) }}
          onSigned={() => { setASigner(null); recharger(); rechargerApercu?.() }}
        />
      )}
      {surPapier && (
        <SignaturePapierDialog
          open
          acte={surPapier}
          onOpenChange={(o) => { if (!o) setSurPapier(null) }}
          onDone={() => { setSurPapier(null); recharger(); rechargerApercu?.() }}
        />
      )}
      {aModifier && (
        <ActeEditeur
          open
          acteId={aModifier.id}
          peutModele={peutModele}
          onOpenChange={(o) => { if (!o) setAModifier(null) }}
          onSaved={() => { recharger(); rechargerApercu?.() }}
          onApercu={() => apercu(aModifier)}
        />
      )}
    </div>
  )
}
