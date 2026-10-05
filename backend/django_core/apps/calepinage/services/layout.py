"""CAL13 / ACAL39 — enregistrer une conception : DEUX empreintes, deux usages.

DEUX EMPREINTES (D-ACAL-4 + D-ACAL-21), JAMAIS CONFONDUES
---------------------------------------------------------
* **L'empreinte « document »** — :func:`empreinte_document`, définie ICI et
  nulle part ailleurs : SHA-256 du document ENTIER (JSON trié), moins les
  seules clés VOLATILES nommées dans :data:`CLES_VOLATILES` (état d'écran qui
  ne change rien à la conception). Elle décide « inchangé », la version et le
  journal : un horizon dessiné, un champ au sol retiré, une épingle recentrée
  (D-ACAL-13) sont des changements de conception, même quand le devis n'en
  voit rien. Le jeton If-Match (C-ACAL-044) et l'empreinte de simulation
  (C-ACAL-073) la RÉUTILISERONT — jamais une seconde fonction.
* **L'empreinte « imprimée »** — ``apps.ventes.services.layout_hash`` (corps
  réel dans ``apps/ventes/domain/geometrie.py``), stockée dans
  ``Calepinage.layout_hash`` : elle ne couvre que ce qui change un chiffre que
  le client voit, et sert à la péremption du devis et à la dédup. Elle n'est
  pas recodée ici : on l'IMPORTE.

CE QUE FAIT LE SERVICE
----------------------
1. il pose ``roof_layout`` sur le pivot ;
2. il RECALCULE ``layout_hash`` (empreinte imprimée) par le ré-export ventes ;
3. il crée une ``CalepinageVersion`` et une ligne de journal **seulement si
   l'empreinte DOCUMENT a changé** — un enregistrement à l'identique (double
   clic, renvoi réseau, simple changement d'état d'écran) ne pollue pas
   l'historique et répond ``inchange: True``.

Aucun statut de devis n'est jamais écrit (règle #4), et la société/l'auteur
sont posés côté serveur.
"""
from __future__ import annotations


import hashlib
import json

#: ACAL39 — les SEULES clés « volatiles » du document : état d'écran qui ne
#: change rien à la conception, donc hors empreinte « document ». Chaque
#: entrée est un CHEMIN ; ``[]`` parcourt une liste. Les pans se lisent aussi
#: sous les alias historiques ``areas`` / ``pans`` (même règle que l'empreinte
#: imprimée).
#:
#: * ``activeAreaId`` — le pan sélectionné à l'écran ;
#: * ``scene`` — l'instant du soleil affiché ({sunDay, sunHour}, CALX88) : un
#:   point de vue, aucun calcul n'en dépend ;
#: * ``zones[].geometry.solarAccess.computedAt`` — l'horodatage d'un calcul,
#:   pas son résultat ;
#: * ``consumption.source.saisi_le`` — l'horodatage d'une saisie, pas la
#:   saisie.
#:
#: ``pin`` n'y est PAS : un recentrage de l'épingle est versionné (D-ACAL-13).
CLES_VOLATILES = (
    'activeAreaId',
    'scene',
    'zones[].geometry.solarAccess.computedAt',
    'consumption.source.saisi_le',
)

_ALIAS_PANS = ('zones', 'areas', 'pans')


def _retirer_chemin(noeud, morceaux):
    """Retire, EN PLACE (sur une copie), la clé désignée par ``morceaux``."""
    if not morceaux or not isinstance(noeud, dict):
        return
    tete, reste = morceaux[0], morceaux[1:]
    liste = tete.endswith('[]')
    cle = tete[:-2] if liste else tete
    if cle not in noeud:
        return
    if not reste:
        noeud.pop(cle, None)
        return
    valeur = noeud[cle]
    if liste:
        for element in valeur if isinstance(valeur, list) else ():
            _retirer_chemin(element, reste)
    else:
        _retirer_chemin(valeur, reste)


def _document_sans_volatiles(roof_layout):
    """Une COPIE du document, privée des seules :data:`CLES_VOLATILES`."""
    import copy

    document = copy.deepcopy(roof_layout)
    for chemin in CLES_VOLATILES:
        morceaux = chemin.split('.')
        if morceaux[0] == 'zones[]':
            for alias in _ALIAS_PANS:
                _retirer_chemin(document, [f'{alias}[]'] + morceaux[1:])
        else:
            _retirer_chemin(document, morceaux)
    return document


def empreinte_document(roof_layout):
    """ACAL39 — l'empreinte « document » (D-ACAL-4) : SHA-256 hex du JSON trié.

    Tout le document compte, sauf :data:`CLES_VOLATILES`. Un document absent
    (``None``) rend ``''`` : « rien » n'a pas d'empreinte. Fonction PURE.
    """
    if roof_layout is None:
        return ''
    canonique = json.dumps(_document_sans_volatiles(roof_layout),
                           sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, default=str)
    return hashlib.sha256(canonique.encode('utf-8')).hexdigest()


class LayoutRefuse(ValueError):
    """Refus métier d'enregistrement, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def enregistrer_layout(calepinage, roof_layout, *, user=None,
                       libelle='', resultat=None, roof_image=None,
                       version_moteur=None):
    """Enregistre la conception et historise SEULEMENT si elle a changé.

    « A changé » = l'empreinte DOCUMENT (:func:`empreinte_document`) de
    ``roof_layout`` diffère de celle du document déjà enregistré.

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

    # CAL207 — miroir de la règle ventes/sync-layout : un calepinage dont le
    # devis lié a été envoyé est en lecture seule (409), sauf déverrouillage
    # explicite. La restauration de version (CAL20) passe par ICI, donc elle
    # hérite du même refus sans code dupliqué (CAL203).
    from .verrou import verifier_ecriture_autorisee

    verifier_ecriture_autorisee(calepinage)

    ancien_layout = calepinage.roof_layout
    # ACAL39 — « inchangé » se décide sur l'empreinte DOCUMENT de l'ancien
    # document relu, jamais sur layout_hash (empreinte imprimée, aveugle à
    # l'horizon, aux champs au sol, à l'épingle…).
    inchange = (empreinte_document(ancien_layout)
                == empreinte_document(roof_layout))
    if inchange and roof_layout is not None:
        # Un calepinage NÉ avec un document (copie d'un devis, d'un modèle)
        # n'a encore aucune version : le premier enregistrement la dépose.
        from .versions import derniere_version

        inchange = derniere_version(calepinage) is not None
    nouvelle = layout_hash(roof_layout) or ''

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

    if not inchange:
        # CAL26 — un enregistrement SIGNIFICATIF se journalise ; un renvoi à
        # l'identique n'est pas un événement (il ne s'est rien passé).
        from .journal import journaliser_layout

        journaliser_layout(calepinage, ancien_layout=ancien_layout,
                           nouveau_layout=roof_layout, user=user)

    # CAL128 — le verdict onduleur est REJOUÉ à chaque enregistrement de
    # conception : sans cela, on pourrait dessiner un champ que l'onduleur ne
    # peut pas recevoir en sautant simplement l'écran qui avertit. Le rejeu
    # n'écrit AUCUN statut (le blocage vit dans ``garde_publication``) et ne
    # lève jamais — une conception enregistrée ne se perd pas parce que son
    # verdict a bronché.
    from .electrique import rejouer_apres_layout

    rejouer_apres_layout(calepinage, user=user)
    return {
        'calepinage': calepinage,
        'version': version,
        'layout_hash': nouvelle,
        'inchange': inchange,
    }
