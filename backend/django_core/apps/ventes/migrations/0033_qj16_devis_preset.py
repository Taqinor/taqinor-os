"""QJ16 — DevisPreset : modèles de devis réutilisables (templates).

Additive only: creates a new table ``ventes_devispreset``.  No existing
table or column is modified.  Fully revertable (RunSQL not used).

Multi-tenancy: company FK enforced at the model and service layer;
never accepted from the request body.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0032_qj22_devissignature_signed_pdf'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DevisPreset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('nom', models.CharField(
                    max_length=150,
                    verbose_name='Nom du modèle',
                    help_text='Ex. « Standard 6 kWc résidentiel ».',
                )),
                ('description', models.TextField(
                    blank=True, default='',
                    verbose_name='Description',
                    help_text='Note libre sur ce modèle (optionnel).',
                )),
                ('mode_installation', models.CharField(
                    blank=True, null=True, max_length=20,
                    choices=[
                        ('residentiel', 'Résidentiel'),
                        ('industriel', 'Industriel / Commercial'),
                        ('agricole', 'Agricole (pompage)'),
                    ],
                    verbose_name="Mode d'installation",
                )),
                ('taux_tva', models.DecimalField(
                    max_digits=5, decimal_places=2, default=20,
                    verbose_name='Taux TVA (%)',
                )),
                ('remise_globale', models.DecimalField(
                    max_digits=5, decimal_places=2, default=0,
                    verbose_name='Remise globale (%)',
                )),
                ('lignes_snapshot', models.JSONField(
                    verbose_name='Lignes (snapshot)',
                    help_text='Snapshot JSON des lignes du devis source.',
                )),
                ('etude_params_snapshot', models.JSONField(
                    blank=True, null=True,
                    verbose_name='Paramètres étude (snapshot)',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='devis_presets',
                    to='authentication.company',
                    verbose_name='Société',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='devis_presets_crees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
            ],
            options={
                'verbose_name': 'Modèle de devis',
                'verbose_name_plural': 'Modèles de devis',
                'ordering': ['nom'],
            },
        ),
        migrations.AddIndex(
            model_name='devispreset',
            index=models.Index(
                fields=['company', 'nom'],
                name='ventes_preset_co_nom_idx',
            ),
        ),
    ]
