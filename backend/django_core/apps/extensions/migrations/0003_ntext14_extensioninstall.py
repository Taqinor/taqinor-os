"""NTEXT14 — installation d'un package par tenant (additif, réversible)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('extensions', '0002_seed_sav_avance_package'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtensionInstall',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('version', models.CharField(
                    blank=True, default='', max_length=20,
                    verbose_name='Version installée')),
                ('statut', models.CharField(
                    choices=[('installe', 'Installé'),
                             ('desinstalle', 'Désinstallé'),
                             ('erreur', 'Erreur')],
                    default='installe', max_length=12)),
                ('installe_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Installé le')),
                ('objets_crees', models.JSONField(
                    blank=True, default=list,
                    help_text="Références 'app.model:pk' créées PAR "
                              "l'installation.",
                    verbose_name='Objets posés')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('package', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='installs',
                    to='extensions.extensionpackage',
                    verbose_name='Package')),
            ],
            options={
                'verbose_name': "Installation d'extension",
                'verbose_name_plural': "Installations d'extension",
                'ordering': ['-created_at', '-id'],
                'unique_together': {('company', 'package')},
            },
        ),
        migrations.AddIndex(
            model_name='extensioninstall',
            index=models.Index(
                fields=['company', 'statut'],
                name='ext_install_co_statut_idx'),
        ),
    ]
