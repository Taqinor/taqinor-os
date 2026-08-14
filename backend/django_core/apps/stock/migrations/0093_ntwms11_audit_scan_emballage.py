"""NTWMS11 — audit du contrôle de conformité au poste d'emballage.

Additif et réversible : deux colonnes NULLABLES sur la ligne d'unité
logistique (qui a scanné, quand). Les lignes existantes restent à NULL —
comportement strictement inchangé pour le colisage saisi sans scan.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stock', '0092_ntwms9_expedition_transporteur'),
    ]

    operations = [
        migrations.AddField(
            model_name='unitelogistiqueligne',
            name='scanne_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='unitelogistiqueligne',
            name='scanne_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lignes_unite_logistique_scannees',
                to=settings.AUTH_USER_MODEL),
        ),
    ]
