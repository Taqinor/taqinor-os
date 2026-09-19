"""CAL8 — l'historique du calepinage : des instantanés GELÉS, purge bornée.

LE DÉFAUT QUE CE MODULE CORRIGE
--------------------------------
L'atelier 3D des ventes n'historise RIEN : ``Devis.roof_layout`` est écrasé à
chaque enregistrement. Un commercial qui a repris sa toiture ce matin ne peut
pas revenir à l'état de la veille — l'état de la veille n'existe plus nulle
part. Le module Calepinage garde, lui, une trace de chaque enregistrement
SIGNIFICATIF.

LES TROIS RÈGLES
----------------
1. **Une version par enregistrement SIGNIFICATIF.** « Significatif » = la
   géométrie a changé, c'est-à-dire l'empreinte ``layout_hash`` diffère de
   celle de la dernière version. Ré-enregistrer à l'identique (double-clic,
   renvoi réseau) ne pollue pas l'historique.
2. **Une version n'est JAMAIS modifiée après sa création.** C'est ce qui en
   fait une preuve : un instantané qu'on peut retoucher ne prouve rien. Le
   modèle lui-même refuse la ré-écriture (``CalepinageVersion.save``).
3. **La purge est BORNÉE et OFF par défaut.** Rien n'est jamais purgé tant que
   la société n'a pas SAISI sa borne : une conservation « par défaut » qui
   efface silencieusement l'historique de quelqu'un est exactement ce qu'il ne
   faut pas faire. La borne est rangée dans la section ``presets`` des
   réglages société (CAL45) — aucune huitième section n'est créée.

Aucune migration ici : les modèles arrivent dans ``0001_initial`` (CAL7).
"""
from __future__ import annotations

#: Clé de la borne de conservation, dans la section ``presets`` des réglages
#: société (CAL45). Absente ⇒ purge DÉSACTIVÉE (rien n'est jamais retiré).
CLE_BORNE_PURGE = 'versions_conservees'


class VersionInvalide(ValueError):
    """Erreur métier sur l'historique, avec un message français.

    ``champ`` nomme le champ fautif pour que l'écran puisse le pointer au lieu
    d'afficher un « non enregistré » générique.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def derniere_version(calepinage):
    """La version la plus récente de ``calepinage``, ou ``None``."""
    from ..models import CalepinageVersion

    if calepinage is None or not calepinage.pk:
        return None
    return (CalepinageVersion.objects
            .filter(calepinage=calepinage)
            .order_by('-created_at', '-id')
            .first())


def enregistrer_version(calepinage, *, user=None, libelle=''):
    """Dépose un instantané GELÉ — seulement si l'empreinte a changé.

    Returns:
        La ``CalepinageVersion`` créée, ou ``None`` si l'empreinte est
        identique à celle de la dernière version (rien à historiser).

    La société et l'auteur sont posés CÔTÉ SERVEUR : la société est celle du
    calepinage, jamais une valeur lue d'un corps de requête.
    """
    from ..models import CalepinageVersion

    if calepinage is None or not calepinage.pk:
        raise VersionInvalide(
            "Impossible d'historiser un calepinage qui n'est pas encore "
            "enregistré.", champ='calepinage')

    precedente = derniere_version(calepinage)
    empreinte = calepinage.layout_hash or ''
    if precedente is not None and (precedente.layout_hash or '') == empreinte:
        return None

    return CalepinageVersion.objects.create(
        company=calepinage.company,
        calepinage=calepinage,
        libelle=libelle or '',
        roof_layout=calepinage.roof_layout,
        layout_hash=empreinte,
        resultat=calepinage.resultat,
        cree_par=user,
    )


def borne_de_purge(company):
    """La borne de conservation SAISIE par ``company``, ou ``None`` (= OFF).

    Une valeur absente, nulle, non entière ou ``<= 0`` vaut OFF : on ne devine
    jamais une borne, et on ne purge jamais « par défaut ».
    """
    from ..selectors import parametres_de_societe

    brut = (parametres_de_societe(company).get('presets')
            or {}).get(CLE_BORNE_PURGE)
    if isinstance(brut, bool) or not isinstance(brut, int):
        return None
    return brut if brut > 0 else None


def purger_versions(calepinage, *, garder=None):
    """Retire les versions AU-DELÀ de la borne — les plus récentes survivent.

    Args:
        calepinage: le calepinage dont l'historique est purgé.
        garder: la borne. ``None`` ⇒ on lit celle SAISIE par la société ;
            toujours ``None`` ⇒ la purge est DÉSACTIVÉE et rien n'est retiré.

    Returns:
        Le nombre de versions effectivement retirées (0 si la purge est OFF).
    """
    from ..models import CalepinageVersion

    if calepinage is None or not calepinage.pk:
        return 0
    if garder is None:
        garder = borne_de_purge(getattr(calepinage, 'company', None))
    if garder is None:
        return 0
    if isinstance(garder, bool) or not isinstance(garder, int) or garder <= 0:
        raise VersionInvalide(
            "La borne de conservation des versions doit être un entier "
            f"strictement positif (reçu : {garder!r}).",
            champ=CLE_BORNE_PURGE)

    survivantes = list(
        CalepinageVersion.objects
        .filter(calepinage=calepinage)
        .order_by('-created_at', '-id')
        .values_list('pk', flat=True)[:garder])
    a_retirer = (CalepinageVersion.objects
                 .filter(calepinage=calepinage)
                 .exclude(pk__in=survivantes))
    retirees = a_retirer.count()
    if retirees:
        a_retirer.delete()
    return retirees
