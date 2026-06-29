"""FG254 / DC35 — FicheTechnique : datasheets normalisées modules/onduleurs.

Additive only: creates the new table ``ventes_fichetechnique`` (FK chaîne vers
``stock.Produit`` + ``authentication.Company``). No existing table or column is
modified. Fully revertable (no RunSQL / no data migration).

Multi-tenancy: ``company`` FK enforced at the model + viewset layer; never
accepted from the request body. La fiche ne re-stocke aucun attribut déjà porté
par ``Produit`` (DC35) : uniquement les paramètres électriques normalisés + un
PDF datasheet optionnel.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        ('ventes', '0037_fg245_rooflayout'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FicheTechnique',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type_fiche', models.CharField(
                    choices=[('panneau', 'Module PV (panneau)'),
                             ('onduleur', 'Onduleur')],
                    default='panneau', max_length=10,
                    verbose_name='Type de fiche')),
                ('pmax_w', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    help_text='Panneau : puissance crête Wc ; onduleur : '
                              'puissance AC W.',
                    verbose_name='Pmax (W)')),
                ('voc_v', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    help_text='Tension circuit ouvert (STC).',
                    verbose_name='Voc (V)')),
                ('isc_a', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    help_text='Courant de court-circuit (STC).',
                    verbose_name='Isc (A)')),
                ('vmp_v', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    help_text='Tension au point de puissance max.',
                    verbose_name='Vmp (V)')),
                ('imp_a', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    help_text='Courant au point de puissance max.',
                    verbose_name='Imp (A)')),
                ('coef_temp_voc', models.DecimalField(
                    blank=True, decimal_places=4, max_digits=6, null=True,
                    verbose_name='Coef. température Voc (%/°C)')),
                ('datasheet_pdf', models.CharField(
                    blank=True, max_length=500, null=True,
                    verbose_name='Datasheet PDF')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ventes_fiches_techniques',
                    to='authentication.company',
                    verbose_name='Société')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='fiches_techniques_creees',
                    to=settings.AUTH_USER_MODEL)),
                ('produit', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fiches_techniques',
                    to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': 'Fiche technique',
                'verbose_name_plural': 'Fiches techniques',
            },
        ),
        migrations.AddIndex(
            model_name='fichetechnique',
            index=models.Index(
                fields=['company', 'type_fiche'],
                name='ix_fiche_comp_type'),
        ),
        migrations.AddConstraint(
            model_name='fichetechnique',
            constraint=models.UniqueConstraint(
                fields=['company', 'produit'],
                name='uniq_fiche_company_produit'),
        ),
    ]
