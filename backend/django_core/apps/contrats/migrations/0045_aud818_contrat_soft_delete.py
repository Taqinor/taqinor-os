# AUD818 — `Contrat` adopte le soft-delete partagé (`core.SoftDeleteModel`),
# premier objet À VALEUR LÉGALE branché sur la corbeille transverse 30 jours.
#
# Migration ADDITIVE : trois champs (is_deleted avec défaut booléen déjà connu
# de Django, deleted_at/deleted_by nullables). Aucune ligne existante n'est
# touchée — toutes restent `is_deleted=False`, donc visibles exactement comme
# avant. La suppression d'un contrat par l'API devient une suppression DOUCE
# (`ContratViewSet.perform_destroy`), restaurable depuis `/api/django/trash/`.
#
# Aucune `AlterModelManagers` : depuis Django 5.x l'état de migration ne porte
# plus de shim pour les managers non `use_in_migrations` — en écrire un
# recréerait exactement la dérive que `crm/0055_alter_lead_managers` a dû
# corriger après `crm/0054`.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0044_aud182_echeancier_gele_par_suspension'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='contrat',
            name='is_deleted',
            field=models.BooleanField(
                db_index=True, default=False, verbose_name='Supprimé'),
        ),
        migrations.AddField(
            model_name='contrat',
            name='deleted_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Supprimé le'),
        ),
        migrations.AddField(
            model_name='contrat',
            name='deleted_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Supprimé par'),
        ),
    ]
