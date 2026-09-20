"""CAL13 — enregistrer une conception : empreinte + instantané de version.

LE HASH N'EST PAS RECODÉ
------------------------
L'empreinte géométrique existe déjà côté ventes et elle est la SEULE :
``apps.ventes.services.layout_hash`` (ré-export du corps réel qui vit dans
``apps/ventes/domain/geometrie.py``). Le recoder ici produirait deux
empreintes pour une même toiture — donc deux vérités, donc des versions
fantômes. On l'IMPORTE, on ne le réécrit jamais.

CE QUE FAIT LE SERVICE
----------------------
1. il pose ``roof_layout`` sur le pivot ;
2. il RECALCULE ``layout_hash`` par ce ré-export ;
3. il crée une ``CalepinageVersion`` **seulement si l'empreinte a changé** —
   un enregistrement à l'identique (double-clic, renvoi réseau) ne pollue pas
   l'historique et répond ``inchange: True``.

Aucun statut de devis n'est jamais écrit (règle #4), et la société/l'auteur
sont posés côté serveur.
"""
from __future__ import annotations


class LayoutRefuse(ValueError):
    """Refus métier d'enregistrement, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def enregistrer_layout(calepinage, roof_layout, *, user=None,
                       libelle='', resultat=None, roof_image=None,
                       version_moteur=None):
    """Enregistre la conception et historise SEULEMENT si elle a changé.

    Args:
        calepinage: le pivot (déjà enregistré).
        roof_layout: le document de conception (schéma v2, CAL232).
        user: l'auteur — posé côté serveur, jamais lu d'un corps de requête.
        libelle: libellé libre porté par la version créée.
        resultat / roof_image / version_moteur: mis à jour quand ils sont
            fournis ; ``None`` laisse la valeur en place.

    Returns:
        ``{'calepinage', 'version', 'layout_hash', 'inchange'}`` —
        ``version`` vaut ``None`` quand rien n'a changé, et ``inchange`` est
        alors ``True``.

    Raises:
        LayoutRefuse: pivot non enregistré, ou document de conception qui
            n'est pas un objet.
    """
    from django.db import transaction

    from apps.ventes.services import layout_hash

    from .versions import enregistrer_version

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise LayoutRefuse(
            "Le calepinage n'est pas encore enregistré : impossible d'y "
            "enregistrer une conception.", champ='calepinage')
    if roof_layout is not None and not isinstance(roof_layout, dict):
        raise LayoutRefuse(
            "La conception doit être un objet "
            f"(reçu : {type(roof_layout).__name__}).", champ='roof_layout')

    ancienne = calepinage.layout_hash or ''
    nouvelle = layout_hash(roof_layout) or ''
    inchange = bool(ancienne) and ancienne == nouvelle

    champs = ['roof_layout', 'layout_hash', 'updated_at']
    with transaction.atomic():
        calepinage.roof_layout = roof_layout
        calepinage.layout_hash = nouvelle
        if resultat is not None:
            calepinage.resultat = resultat
            champs.append('resultat')
        if roof_image is not None:
            calepinage.roof_image = roof_image or ''
            champs.append('roof_image')
        if version_moteur is not None:
            calepinage.version_moteur = version_moteur or ''
            champs.append('version_moteur')
        calepinage.save(update_fields=champs)

        version = None
        if not inchange:
            version = enregistrer_version(calepinage, user=user,
                                          libelle=libelle)

    return {
        'calepinage': calepinage,
        'version': version,
        'layout_hash': nouvelle,
        'inchange': inchange,
    }
