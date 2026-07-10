"""SCA18 — Backfill NON destructif du ``statut`` depuis le bool ``actif``.

Le schéma (0017) pose ``statut='actif'`` par défaut sur toutes les lignes
existantes ; ici on réaligne les sociétés déjà DÉSACTIVÉES (``actif=False``)
sur ``statut='suspendu'`` pour que le pont bool↔statut soit cohérent dès le
premier déploiement (une désactivation historique reste effective). Réversible :
le sens inverse remet ``statut='actif'`` sur ces lignes suspendues sans toucher
``actif`` (l'état opérationnel reste identique — le pont recalcule).
"""
from django.db import migrations


BATCH = 500


def _update_par_lots(qs, **valeurs):
    # YOPSB4 — mise à jour PAR LOTS (marqueur .iterator) : jamais d'update
    # global non borné dans une RunPython, même sur une table réputée petite.
    Model = qs.model
    lot = []
    for pk in qs.values_list('pk', flat=True).iterator(chunk_size=BATCH):
        lot.append(pk)
        if len(lot) >= BATCH:
            Model.objects.filter(pk__in=lot).update(**valeurs)
            lot = []
    if lot:
        Model.objects.filter(pk__in=lot).update(**valeurs)


def forwards(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    _update_par_lots(
        Company.objects.filter(actif=False, statut='actif'),
        statut='suspendu')


def backwards(apps, schema_editor):
    # Restaure la valeur par défaut du schéma pour les lignes backfillées.
    Company = apps.get_model('authentication', 'Company')
    _update_par_lots(
        Company.objects.filter(actif=False, statut='suspendu'),
        statut='actif')


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0017_company_date_fermeture_company_statut'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
