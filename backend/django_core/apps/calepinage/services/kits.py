"""CAL198 — kit de pose du module : structures/fixations du catalogue AO ET
cotes RÉELLES du module posé.

LE DÉFAUT QUE CE SERVICE CORRIGE
---------------------------------
``KitCalepinage`` (AOF26) existe côté AO, string-FK sur ``stock.Produit``
(le produit qui porte le PRIX), et le module autonome n'y avait aucun accès.
Pire : les kits du noyau (``core/calepinage/types.py``) sont des CONSTANTES
(un module 2 384 × 1 303 mm figé en dur), et l'unique passerelle
produit→kit (``apps.ao.services.kit_panneau_du_produit``) ne servait que
l'AO. Un module d'une autre dimension se retrouvait donc calepiné avec les
cotes d'un AUTRE module (CAL169, fondue ici).

CE QUE FAIT CE SERVICE
------------------------
Il COMBINE, sans jamais recoder ni copier :

* les structures/fixations du kit AO (``apps.ao.selectors.kits_de_pose``) —
  code, libellé, mode de pose, emprise, produit qui porte le prix ;
* les cotes RÉELLES du module POSÉ — celles du produit demandé
  (``apps.stock.selectors.dimensions_de_pose``, CAL119) quand un module est
  précisé, sinon celles DÉJÀ portées par le kit AO (comportement
  HISTORIQUE inchangé — un kit qui ne change pas de produit ne change pas
  de cotes).

Une dimension manquante sur le module demandé REFUSE le kit, en NOMMANT le
champ (jamais un repli sur les cotes d'un autre module). Un produit — kit OU
module — archivé est SIGNALÉ (``*_archive: true``), jamais silencieusement
ignoré : le kit reste utilisable, l'écran décide quoi en faire.

Construit dans ``apps.calepinage`` — jamais dans le noyau (``core.
calepinage``), qui reste pur (contrat import-linter mesuré).
"""
from __future__ import annotations

__all__ = ['KitDePoseRefuse', 'construire_kit_de_pose']


class KitDePoseRefuse(ValueError):
    """Erreur métier sur un kit de pose, message français, champ nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


#: Les trois cotes REQUISES pour poser un module réel (CAL119).
_COTES_REQUISES = ('longueur_mm', 'largeur_mm', 'puissance_wc')


def construire_kit_de_pose(company, *, kit_id, produit_module_id=None):
    """Le kit de pose : structures/fixations AO + cotes du module posé.

    Args:
        company: la société — jamais lue d'un corps de requête.
        kit_id: l'identifiant du ``KitCalepinage`` (AO) à utiliser.
        produit_module_id: le produit MODULE réellement posé, s'il diffère
            du module par défaut du kit. ``None`` ⇒ cotes du kit inchangées
            (comportement historique).

    Returns:
        ``{'kit', 'module', 'produit_module_id', 'produit_module_archive'}``
        — ``kit`` est la ligne du catalogue AO (avec son propre
        ``produit_archive``), ``module`` porte les cotes RETENUES et leur
        ``source`` (``'kit'`` ou ``'produit'``).

    Raises:
        KitDePoseRefuse: société/kit absent, kit introuvable, produit module
            introuvable, ou dimension de pose manquante sur ce produit.
    """
    from apps.ao.selectors import kits_de_pose
    from apps.stock.selectors import dimensions_de_pose, get_produit_scoped

    if company is None or not kit_id:
        raise KitDePoseRefuse(
            'Un kit de pose exige une société et un identifiant de kit.',
            champ='kit')

    kit_ao = next(
        (ligne for ligne in kits_de_pose(company, actifs_seulement=False)
         if ligne['id'] == kit_id), None)
    if kit_ao is None:
        raise KitDePoseRefuse(f'Kit de pose introuvable : « {kit_id} ».',
                              champ='kit')

    module = {
        'longueur_mm': None,
        'largeur_mm': None,
        'puissance_wc': kit_ao['puissance_module_w'],
        'source': 'kit',
    }
    produit_archive = False
    if produit_module_id:
        produit = get_produit_scoped(company, produit_module_id)
        if produit is None:
            raise KitDePoseRefuse(
                'Produit module introuvable dans cette société.',
                champ='produit_module')
        cotes = dimensions_de_pose(produit)
        manquantes = [cle for cle in _COTES_REQUISES if cle not in cotes]
        if manquantes:
            raise KitDePoseRefuse(
                'Dimensions de pose manquantes sur la fiche du module '
                f'« {produit.nom} » : {", ".join(manquantes)}.',
                champ=manquantes[0])
        module = {
            'longueur_mm': cotes['longueur_mm'],
            'largeur_mm': cotes['largeur_mm'],
            'puissance_wc': cotes['puissance_wc'],
            'source': 'produit',
        }
        produit_archive = bool(getattr(produit, 'is_archived', False))

    return {
        'kit': kit_ao,
        'module': module,
        'produit_module_id': produit_module_id or None,
        'produit_module_archive': produit_archive,
    }
