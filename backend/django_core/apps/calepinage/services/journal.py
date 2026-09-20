"""CAL26 — LE chatter du calepinage : la primitive plateforme, rien d'autre.

``apps.records.services.log_activity`` (ARC8) est le SEUL point d'écriture du
chatter générique, et ``apps/records/platform_guards.py`` fait rougir toute
nouvelle classe ``…Activity`` hors baseline gelée. Le module Calepinage ne crée
donc AUCUN modèle de journal : il appelle cette primitive, et la LECTURE passe
par ``records`` (le mixin de chatter du viewset), jamais par une seconde API de
chatter.

CE QUI EST JOURNALISÉ, AU FORMAT ANCIEN → NOUVEAU
--------------------------------------------------
création, rattachement d'un devis, rattachement d'une affaire d'AO,
enregistrement d'une conception (ancien/nouveau nombre de modules), bascule de
la variante retenue, restauration d'une version — plus les NOTES manuelles.

DEUX RÈGLES DURES
-----------------
* l'AUTEUR et la SOCIÉTÉ sont toujours posés CÔTÉ SERVEUR (``log_activity``
  déduit la société de la cible) — jamais lus d'un corps de requête ;
* journaliser ne fait JAMAIS échouer le geste métier. Une entrée de chatter
  perdue est regrettable ; une conception perdue parce que son journal a
  bronché serait inacceptable. Les échecs sont donc avalés ET tracés.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = [
    'journaliser_creation', 'journaliser_lien_devis',
    'journaliser_lien_appel_offre', 'journaliser_layout',
    'journaliser_variante_retenue', 'journaliser_restauration',
    'journaliser_verrou', 'noter',
]


def _ecrire(calepinage, kind, **champs):
    """Écrit UNE entrée par la primitive ``records`` — best-effort."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return None
    try:
        from apps.records.models import Activity
        from apps.records.services import log_activity

        return log_activity(calepinage, getattr(Activity.Kind, kind),
                            **champs)
    except Exception:  # noqa: BLE001 — un journal ne casse jamais un geste
        logger.exception('CAL26 : entrée de chatter perdue (calepinage %s)',
                         getattr(calepinage, 'pk', None))
        return None


def _modules(layout):
    """Le nombre de modules LU dans une conception, ou ``''`` (inconnu).

    Jamais ``0`` quand le document ne dit rien : « zéro module » et « on ne
    sait pas » ne se lisent pas de la même façon dans un journal.
    """
    if not isinstance(layout, dict):
        return ''
    resultat = layout.get('result')
    if isinstance(resultat, dict):
        for cle in ('panels', 'count', 'nb_panneaux'):
            valeur = resultat.get(cle)
            if isinstance(valeur, (int, float)) and not isinstance(valeur,
                                                                   bool):
                return str(int(valeur))
    return ''


def journaliser_creation(calepinage, *, user=None):
    """« Calepinage créé » — la première ligne de son histoire."""
    return _ecrire(calepinage, 'CREATION', user=user,
                   field='calepinage', field_label='Calepinage',
                   new_value=str(calepinage))


def journaliser_lien_devis(calepinage, *, ancien=None, nouveau=None,
                           user=None):
    """Rattachement (ou changement) du devis lié, ancien → nouveau."""
    return _ecrire(calepinage, 'MODIFICATION', user=user, field='devis',
                   field_label='Devis lié',
                   old_value='' if ancien is None else str(ancien),
                   new_value='' if nouveau is None else str(nouveau))


def journaliser_lien_appel_offre(calepinage, *, ancien=None, nouveau=None,
                                 user=None):
    """Rattachement (ou changement) de l'affaire d'appel d'offres."""
    return _ecrire(calepinage, 'MODIFICATION', user=user,
                   field='appel_offre', field_label="Appel d'offres",
                   old_value='' if ancien is None else str(ancien),
                   new_value='' if nouveau is None else str(nouveau))


def journaliser_layout(calepinage, *, ancien_layout=None, nouveau_layout=None,
                       user=None):
    """Enregistrement d'une conception : ancien → nouveau nombre de modules.

    C'est le chiffre qu'un lecteur du journal cherche — pas une empreinte de
    64 caractères qui ne lui dit rien.
    """
    return _ecrire(calepinage, 'MODIFICATION', user=user, field='roof_layout',
                   field_label='Conception (modules)',
                   old_value=_modules(ancien_layout),
                   new_value=_modules(nouveau_layout))


def journaliser_variante_retenue(calepinage, *, ancienne=None, nouvelle=None,
                                 user=None):
    """Bascule de la variante retenue, par son NOM (jamais par son id seul)."""
    return _ecrire(calepinage, 'MODIFICATION', user=user, field='variante',
                   field_label='Variante retenue',
                   old_value=getattr(ancienne, 'nom', '') or '',
                   new_value=getattr(nouvelle, 'nom', '') or '')


def journaliser_restauration(calepinage, *, version=None, user=None):
    """Restauration d'une version — l'événement, pas seulement son effet."""
    return _ecrire(calepinage, 'MODIFICATION', user=user, field='version',
                   field_label='Version restaurée', old_value='',
                   new_value=str(getattr(version, 'pk', '') or ''))


#: CAL207 — champ + valeurs du VERROU dans le chatter (source unique lue par
#: ``services.verrou`` — jamais un second champ, jamais un littéral ailleurs).
CHAMP_VERROU = 'verrou'
VERROU_OUVERT = 'ouvert'
VERROU_FERME = 'ferme'


def journaliser_verrou(calepinage, *, ouvert, user=None):
    """Bascule du verrou (devis envoyé) — l'entrée que ``services.verrou``
    relit pour savoir si un déverrouillage explicite a eu lieu."""
    nouvelle = VERROU_OUVERT if ouvert else VERROU_FERME
    ancienne = VERROU_FERME if ouvert else VERROU_OUVERT
    return _ecrire(calepinage, 'MODIFICATION', user=user, field=CHAMP_VERROU,
                   field_label='Verrou', old_value=ancienne,
                   new_value=nouvelle)


def dernier_etat_verrou(calepinage):
    """La dernière valeur du champ ``verrou`` déposée au chatter, ou ``None``
    si aucune bascule n'a encore eu lieu."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return None
    try:
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        ct = ContentType.objects.get_for_model(type(calepinage))
        entree = (Activity.objects
                  .filter(content_type=ct, object_id=calepinage.pk,
                          field=CHAMP_VERROU)
                  .order_by('-created_at', '-id')
                  .first())
        return entree.new_value if entree is not None else None
    except Exception:  # noqa: BLE001 — une lecture de journal ne casse rien
        logger.exception(
            'CAL207 : lecture du dernier état de verrou en échec '
            '(calepinage %s)', getattr(calepinage, 'pk', None))
        return None


def noter(calepinage, texte, *, user=None):
    """Une NOTE manuelle — même journal que les entrées automatiques.

    Refuse une note vide : une ligne de chatter sans contenu est du bruit qui
    fait défiler les vraies.
    """
    corps = (texte or '').strip()
    if not corps:
        return None
    return _ecrire(calepinage, 'NOTE', user=user, body=corps)
