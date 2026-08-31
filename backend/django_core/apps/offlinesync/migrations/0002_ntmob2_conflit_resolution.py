# NTMOB2 — arbitrage explicite d'un conflit de synchronisation.
#
# Purement ADDITIVE et réversible : quatre colonnes nullables/à défaut sur
# ``OfflineOperation``. Aucune donnée existante n'est touchée (une op déjà
# journalisée reste dans son statut, sans conflit ni arbitrage).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offlinesync', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='offlineoperation',
            name='conflit',
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name='Détail du conflit'),
        ),
        migrations.AddField(
            model_name='offlineoperation',
            name='resolution',
            field=models.CharField(
                blank=True, default='',
                choices=[('mienne', 'Ma version conservée'),
                         ('serveur', 'Version du serveur conservée'),
                         ('fusion', 'Fusion manuelle')],
                max_length=12, verbose_name='Arbitrage'),
        ),
        migrations.AddField(
            model_name='offlineoperation',
            name='date_resolution',
            field=models.DateTimeField(blank=True, null=True,
                                       verbose_name='Arbitré le'),
        ),
        migrations.AddField(
            model_name='offlineoperation',
            name='resolu_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL,
                verbose_name='Arbitré par'),
        ),
    ]
