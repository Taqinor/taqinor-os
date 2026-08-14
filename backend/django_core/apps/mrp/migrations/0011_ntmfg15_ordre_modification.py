# NTMFG15 — PLM léger : Ordre de Modification (ECO) avec effectivité.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mrp', '0010_ntmfg14_maintenance_poste'),
        ('stock', '0085_ntadm2_produit_entite'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrdreModification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_eco', models.CharField(choices=[('nomenclature', 'Nomenclature'), ('gamme', 'Gamme'), ('les_deux', 'Nomenclature + gamme')], default='gamme', max_length=16, verbose_name='Type de changement')),
                ('description', models.TextField(blank=True, default='')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('en_revue', 'En revue'), ('approuve', 'Approuvé'), ('applique', 'Appliqué'), ('rejete', 'Rejeté')], default='brouillon', max_length=10)),
                ('date_effectivite', models.DateField(blank=True, null=True, verbose_name="Date d'effectivité (vide = immédiat)")),
                ('changements', models.JSONField(blank=True, default=dict)),
                ('applique_le', models.DateTimeField(blank=True, null=True)),
                ('approbateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mrp_ecos_approuves', to=settings.AUTH_USER_MODEL, verbose_name='Approbateur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('demandeur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mrp_ecos_demandes', to=settings.AUTH_USER_MODEL, verbose_name='Demandeur')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mrp_ecos', to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': 'Ordre de modification (ECO)',
                'verbose_name_plural': 'Ordres de modification (ECO)',
                'ordering': ['-id'],
                'indexes': [
                    models.Index(fields=['company', 'statut'], name='mrp_eco_co_statut_idx'),
                    models.Index(fields=['company', 'produit'], name='mrp_eco_co_produit_idx'),
                ],
            },
        ),
    ]
