import { useState } from 'react'
import { ArrowLeftRight, Info } from 'lucide-react'
import api from '../../api/axios'
import { Button } from '../../ui'

/* ============================================================================
   CAL242 — LE BOUTON D'IMPORT DE CONTOUR côté affaire d'appel d'offres.
   ----------------------------------------------------------------------------
   SOLMVP15 — ce fichier portait LES DEUX SENS. Le sens affaire → atelier
   (CAL240) est parti avec son endpoint : l'app d'appels d'offres sort du
   produit, il n'y a plus d'affaire dont reprendre le contour, et l'atelier
   garde son contour canonique (`roof_layout.outline`, v2) et le tracé sur
   carte pour le poser. Le sens inverse (CAL241), lui, est monté sur l'écran de
   TOITURE d'une affaire : il vit donc jusqu'au retrait de cet écran, et part
   avec lui. Il n'appelle plus le client d'API de cette app (qui s'en va) mais
   la même route, par le client HTTP commun — aucun comportement ne change.
   ----------------------------------------------------------------------------
   CONSTAT : sans bouton, CAL240 et CAL241 restent des ENDPOINTS MORTS — le même
   oubli qu'au 03/08/2026, où 61 écrans livrés sur 68 n'étaient atteignables
   depuis aucun menu. La conversion ENU ↔ repère local métrique (CAL31) a déjà
   vécu ainsi : écrite, testée, sans aucun consommateur.

   CE QUI VOYAGE, ET SEULEMENT ÇA : la GÉOMÉTRIE DE CONTOUR. Dans un sens comme
   dans l'autre, aucune géométrie opposable ne bouge — ni obstacle, ni chaîne de
   cotes, ni zone AO, ni variante retenue. Les deux boutons le RAPPELLENT à
   l'écran : c'est la seule façon qu'un utilisateur a de savoir ce qu'il
   déclenche avant de cliquer.

   LE REFUS VIENT DU SERVEUR, MOT POUR MOT. Un 409 « affaire déposée/close »
   (`selectors.raison_conception_figee`) ou un 400 « toiture sans origine
   géographique » porte déjà la raison exacte ; la réécrire côté client produit
   un texte qui a l'air d'une explication sans en être une. Le message s'affiche
   donc SOUS le bouton, tel quel, et l'écran n'en fabrique aucun — sauf quand le
   serveur n'a rien dit du tout (réseau), cas où il le dit aussi.
   ========================================================================== */

/** Le message du serveur, tel quel. Aucun texte fabriqué quand il en donne un. */
function messageRefus(e) {
  const data = e?.response?.data
  if (typeof data === 'string' && data.trim()) return data
  if (data && typeof data === 'object') {
    for (const cle of ['detail', 'message', 'non_field_errors']) {
      const valeur = data[cle]
      if (Array.isArray(valeur) && valeur.length) return valeur.join(' ')
      if (typeof valeur === 'string' && valeur.trim()) return valeur
    }
    // Erreur nommant un CHAMP (400 « origine géographique manquante ») : on
    // nomme le champ, et on rend le message du serveur tel quel.
    const premier = Object.entries(data).find(([, v]) => v)
    if (premier) {
      const [champ, valeur] = premier
      const texte = Array.isArray(valeur) ? valeur.join(' ') : String(valeur)
      return `${champ} : ${texte}`
    }
  }
  return 'Le serveur n’a pas répondu. Réessayez dans un instant.'
}

function BoutonImport({ testid, libelle, rappel, action, onImporte }) {
  const [enCours, setEnCours] = useState(false)
  const [refus, setRefus] = useState(null)

  const cliquer = async () => {
    setRefus(null)
    setEnCours(true)
    try {
      await action()
      // RAFRAÎCHIR : l'écran ne devine pas la nouvelle géométrie, il la relit.
      await onImporte?.()
    } catch (e) {
      setRefus(messageRefus(e))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="space-y-1" data-testid={testid}>
      <Button size="sm" variant="outline" disabled={enCours} onClick={cliquer}>
        <ArrowLeftRight size={15} aria-hidden="true" />
        {libelle}
      </Button>
      <p className="flex items-start gap-1 text-xs text-muted-foreground">
        <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
        {rappel}
      </p>
      {refus ? (
        <p className="text-sm text-destructive" role="alert" data-testid={`${testid}-refus`}>
          {refus}
        </p>
      ) : null}
    </div>
  )
}

const RAPPEL = 'Seule la géométrie de contour est reprise : obstacles, cotes, '
  + 'zones et variante retenue ne sont pas touchés.'

/**
 * Sens calepinage → AO (CAL241). Posé sur l'écran de toiture d'une affaire.
 * `toitureId` : la toiture AO qui REÇOIT ; `calepinageId` la source, quand
 * l'écran la connaît — sinon le serveur résout le calepinage de l'affaire.
 */
export function BoutonReprendreTrace3D({ toitureId, calepinageId, onImporte }) {
  return (
    <BoutonImport
      testid="ao-bouton-trace-3d"
      libelle="Reprendre le tracé 3D"
      rappel={RAPPEL}
      onImporte={onImporte}
      action={() => api.post(
        `/ao/toitures/${toitureId}/reprendre-contour-3d/`,
        calepinageId ? { calepinage: calepinageId } : {})}
    />
  )
}

export default BoutonReprendreTrace3D
