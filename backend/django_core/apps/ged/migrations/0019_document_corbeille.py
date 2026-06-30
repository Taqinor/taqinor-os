# GED26 — Corbeille & restauration (soft-delete réversible).
#
# Ajoute deux champs additifs et nullable sur `Document` : `supprime_le`
# (horodatage de mise en corbeille) et `supprime_par` (auteur). Un document est
# « dans la corbeille » quand `supprime_le` est renseigné : il disparaît des
# listes par défaut (filtre `supprime_le__isnull=True` dans
# `documents_visible_to_user`) mais n'est PAS effacé — il reste récupérable via
# `restaurer_de_corbeille`. Couche SÉPARÉE de l'archivage légal write-once
# (GED23) et du legal hold (GED24) : un document archivé / sous-hold n'est pas
# mettable en corbeille (mêmes gardes 403). Migration strictement additive et
# réversible ; aucune donnée existante n'est touchée (les documents existants
# restent hors corbeille, `supprime_le` NULL).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0018_legalhold"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="supprime_le",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="mis en corbeille le",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="supprime_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ged_documents_corbeille",
                to=settings.AUTH_USER_MODEL,
                verbose_name="mis en corbeille par",
            ),
        ),
    ]
