"""NTDOC16 — traces de fermeture d'une salle de données.

Additive : deux colonnes optionnelles (qui / quand). Aucune donnée existante
n'est modifiée.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('datarooms', '0004_ntdoc15_index_source_concurrent'),
    ]

    operations = [
        migrations.AddField(
            model_name='sallededonnees',
            name='fermee_le',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Fermée le'),
        ),
        migrations.AddField(
            model_name='sallededonnees',
            name='fermee_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='salles_donnees_fermees',
                to=settings.AUTH_USER_MODEL, verbose_name='Fermée par'),
        ),
    ]
