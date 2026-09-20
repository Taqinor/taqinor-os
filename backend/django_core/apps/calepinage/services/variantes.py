"""CAL9 — « une seule variante retenue », par un chemin d'écriture UNIQUE.

DEUX VERROUS, PAS UN
--------------------
1. **La base.** ``CalepinageVariante`` porte
   ``UniqueConstraint(fields=['calepinage'], condition=Q(retenue=True))``
   (CAL7/CAL9) : deux variantes retenues sur un même calepinage lèvent
   ``IntegrityError``. C'est la garantie qui survit à tout — script, admin,
   requête concurrente.
2. **Le chemin d'écriture.** La contrainte seule laisserait un appelant
   naïf « corriger » le problème en passant les DEUX à faux (zéro retenue,
   c'est-à-dire un calepinage sans option choisie — l'autre moitié du bug).
   Le champ ``retenue`` n'est donc écrivable QUE depuis ce module : partout
   ailleurs (vue, sérialiseur, script), une écriture est REFUSÉE en français.

Le service de bascule lui-même (``retenir_variante``), la création et la
duplication arrivent avec CAL14 — dans CE fichier, jamais dans un autre : un
second foyer d'écriture rouvrirait exactement ce que ce garde ferme.
"""
from __future__ import annotations

# Le verrou lui-même vit dans ``apps/calepinage/garde_retenue.py`` (stdlib
# pure) : le MODÈLE doit l'interroger, et s'il importait ce service la chaîne
# ``models -> services.variantes -> apps.ventes.services -> … -> apps.ao.models``
# ferait rougir le contrat import-linter CAL5 (mesuré). On le RÉ-EXPORTE ici :
# le chemin d'écriture unique reste le service.
from ..garde_retenue import (  # noqa: F401
    bascule_autorisee,
    bascule_en_cours,
    refuser_ecriture_directe,
)


# ---------------------------------------------------------------------------
# CAL14 — les trois écritures : créer, retenir, dupliquer.
# ---------------------------------------------------------------------------


class VarianteRefusee(ValueError):
    """Refus métier sur une variante, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def creer_variante(calepinage, *, nom, roof_layout=None, resultat=None,
                   user=None, retenir=False):
    """Crée une variante sur ``calepinage``.

    ``retenir=True`` passe par la bascule atomique : l'ancienne retenue
    repasse à faux dans la MÊME transaction — jamais deux, jamais zéro.
    """
    from django.db import transaction

    from apps.ventes.services import layout_hash

    from ..models import CalepinageVariante

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise VarianteRefusee(
            "Le calepinage n'est pas encore enregistré : impossible d'y "
            "ajouter une variante.", champ='calepinage')
    libelle = (nom or '').strip()
    if not libelle:
        raise VarianteRefusee(
            "Donnez un nom à la variante : c'est lui qui permet de la "
            "reconnaître dans la comparaison.", champ='nom')
    if roof_layout is not None and not isinstance(roof_layout, dict):
        raise VarianteRefusee(
            "La conception de la variante doit être un objet "
            f"(reçu : {type(roof_layout).__name__}).", champ='roof_layout')

    with transaction.atomic():
        variante = CalepinageVariante.objects.create(
            company=calepinage.company,
            calepinage=calepinage,
            nom=libelle,
            roof_layout=roof_layout,
            layout_hash=layout_hash(roof_layout) or '',
            resultat=resultat,
            cree_par=user,
        )
        if retenir:
            retenir_variante(variante)
    return variante


def retenir_variante(variante):
    """Bascule ``variante`` en RETENUE, atomiquement.

    L'ancienne retenue du même calepinage repasse à faux dans la même
    transaction : il n'y a jamais deux retenues, ni zéro, même une
    milliseconde.

    Returns:
        La variante retenue (rafraîchie).
    """
    from django.db import transaction

    from ..models import CalepinageVariante

    if variante is None or not getattr(variante, 'pk', None):
        raise VarianteRefusee(
            "La variante n'est pas encore enregistrée : impossible de la "
            "retenir.", champ='variante')

    with transaction.atomic():
        with bascule_autorisee():
            (CalepinageVariante.objects
             .select_for_update()
             .filter(calepinage_id=variante.calepinage_id, retenue=True)
             .exclude(pk=variante.pk)
             .update(retenue=False))
            variante.retenue = True
            variante.save(update_fields=['retenue', 'updated_at'])
    return variante


def dupliquer(calepinage, *, user=None, titre=''):
    """Recopie layout + variantes vers un NOUVEAU calepinage.

    Le duplicata reste dans la MÊME société et garde le rattachement
    lead/client (sinon il violerait la contrainte « lead ou client »), mais
    il ne porte NI ``devis`` NI ``appel_offre_id`` : dupliquer une conception
    ne réquisitionne pas le devis de l'original.
    """
    from django.db import transaction

    from ..models import Calepinage, CalepinageVariante

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise VarianteRefusee(
            "Le calepinage à dupliquer n'est pas enregistré.",
            champ='calepinage')

    with transaction.atomic():
        copie = Calepinage.objects.create(
            company=calepinage.company,
            lead_id=calepinage.lead_id,
            client_id=calepinage.client_id,
            titre=(titre or '').strip() or _titre_de_copie(calepinage),
            statut=Calepinage.Statut.BROUILLON,
            roof_layout=calepinage.roof_layout,
            layout_hash=calepinage.layout_hash or '',
            version_moteur=calepinage.version_moteur or '',
            resultat=calepinage.resultat,
            cree_par=user,
        )
        with bascule_autorisee():
            for source in (CalepinageVariante.objects
                           .filter(calepinage=calepinage).order_by('id')):
                CalepinageVariante.objects.create(
                    company=copie.company,
                    calepinage=copie,
                    nom=source.nom,
                    roof_layout=source.roof_layout,
                    layout_hash=source.layout_hash or '',
                    resultat=source.resultat,
                    retenue=source.retenue,
                    cree_par=user,
                )
    return copie


def _titre_de_copie(calepinage):
    """« <titre> (copie) » — dérivé de la donnée, jamais d'un nom figé."""
    titre = (getattr(calepinage, 'titre', '') or '').strip()
    return f'{titre} (copie)' if titre else 'Calepinage (copie)'
