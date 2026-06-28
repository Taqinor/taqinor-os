"""FG245 — RoofLayout : éditeur de calepinage toiture (placement panneaux).

Additive only: creates a new table ``ventes_rooflayout``. No existing table or
column is modified. Fully revertable (no RunSQL / no data migration).

Multi-tenancy: company FK enforced at the model and viewset layer; never
accepted from the request body. ``panel_count`` is recomputed server-side.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0036_alter_devisnudgelog_id_alter_devispreset_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RoofLayout',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('nom', models.CharField(
                    blank=True, default='', max_length=150,
                    help_text='Ex. « Pan sud — toiture tôle ».',
                    verbose_name='Nom du calepinage')),
                ('largeur_m', models.DecimalField(
                    decimal_places=2, default=0, max_digits=8,
                    verbose_name='Largeur du pan (m)')),
                ('hauteur_m', models.DecimalField(
                    decimal_places=2, default=0, max_digits=8,
                    verbose_name='Hauteur / longueur du pan (m)')),
                ('retrait_m', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    help_text='Marge libre sur chaque bord du pan.',
                    verbose_name='Retrait de sécurité (m)')),
                ('module_largeur_m', models.DecimalField(
                    decimal_places=3, default=1.134, max_digits=6,
                    verbose_name='Largeur module (m)')),
                ('module_hauteur_m', models.DecimalField(
                    decimal_places=3, default=2.278, max_digits=6,
                    verbose_name='Hauteur module (m)')),
                ('espacement_m', models.DecimalField(
                    decimal_places=3, default=0.02, max_digits=6,
                    verbose_name='Espacement entre modules (m)')),
                ('orientation', models.CharField(
                    choices=[('portrait', 'Portrait'),
                             ('paysage', 'Paysage')],
                    default='portrait', max_length=10,
                    verbose_name='Orientation des modules')),
                ('puissance_module_wc', models.PositiveIntegerField(
                    default=0,
                    help_text='Pour déduire le kWc total du calepinage '
                              '(0 = inconnu).',
                    verbose_name='Puissance unitaire module (Wc)')),
                ('panels', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Panneaux placés')),
                ('panel_count', models.PositiveIntegerField(
                    default=0, verbose_name='Nombre de panneaux')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ventes_roof_layouts',
                    to='authentication.company',
                    verbose_name='Société')),
                ('devis', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ventes_roof_layouts',
                    to='ventes.devis',
                    verbose_name='Devis')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ventes_roof_layouts_crees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par')),
            ],
            options={
                'verbose_name': 'Calepinage toiture',
                'verbose_name_plural': 'Calepinages toiture',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='rooflayout',
            index=models.Index(
                fields=['company', 'devis'],
                name='ventes_roof_co_dev_idx'),
        ),
    ]
