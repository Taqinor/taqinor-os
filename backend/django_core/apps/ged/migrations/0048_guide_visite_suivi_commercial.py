# VISITE-CADENCE (fondateur 15/09/2026) — dépose le guide PDF « La visite
# technique dans le suivi commercial » dans la GED de chaque société non-démo
# (cabinet « Documentation », dossier « Guides »).
#
# POURQUOI les services RUNTIME et pas les modèles historiques : le dépôt GED
# complet (cabinet, arbre de dossiers avec `path` matérialisé par save(),
# versionnage, stockage objet records.storage) vit dans `apps.ged.services` —
# le rejouer sur des modèles historiques réimplémenterait tout faux.
# CONTRAT DE SÛRETÉ : ce bloc ne fait JAMAIS échouer un migrate — toute
# erreur (stockage objet indisponible, schéma divergent sur une base neuve
# rejouant la chaîne) est journalisée et `manage.py seed_guide_visite`
# rattrape. Aucune donnée existante n'est modifiée : dépôt purement additif,
# idempotent par source.
import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def _deposer_guide(apps, schema_editor):
    try:
        from apps.ged.services import seed_guide_visite

        crees, existants, echecs = seed_guide_visite()
        logger.info(
            'guide visite : %s déposé(s), %s déjà présent(s), %s échec(s)',
            crees, existants, echecs)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'guide visite : seed impossible pendant migrate — relancer '
            '`manage.py seed_guide_visite` une fois le stockage disponible.',
            exc_info=True)


def _retirer_guide(apps, schema_editor):
    # Reverse : retire les documents déposés par CE seed (repérés par leur
    # source), best-effort — le binaire MinIO reste, seul le référencement
    # GED disparaît.
    try:
        from apps.ged.services import (
            GUIDE_VISITE_SOURCE_ID, GUIDE_VISITE_SOURCE_TYPE,
            find_document_by_source,
        )
        from authentication.models import Company

        for company in Company.objects.all():
            document = find_document_by_source(
                company, source_type=GUIDE_VISITE_SOURCE_TYPE,
                source_id=GUIDE_VISITE_SOURCE_ID)
            if document is not None:
                document.delete()
    except Exception:  # noqa: BLE001
        logger.warning('guide visite : reverse best-effort échoué',
                       exc_info=True)


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0047_ntdoc21_modele_sections'),
    ]

    operations = [
        migrations.RunPython(_deposer_guide, _retirer_guide),
    ]
