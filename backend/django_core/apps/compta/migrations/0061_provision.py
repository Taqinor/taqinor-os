"""XACC26 — Provisions pour risques & charges + dépréciation des stocks/immo.

Additif : ``Provision`` (générique, distincte de ``ProvisionCreance`` FG152 qui
ne couvre que les créances clients) — nature risques & charges (15x),
dépréciation stock (39x) ou immo (29x), dotation/reprise postées au GL.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0060_demandeapprobationrib'),
    ]

    operations = [
        migrations.CreateModel(
            name='Provision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(blank=True, default='', max_length=50, verbose_name='Référence')),
                ('nature', models.CharField(choices=[('risques_charges', 'Provisions pour risques & charges (15x)'), ('depreciation_stock', 'Dépréciation des stocks (39x)'), ('depreciation_immo', 'Dépréciation des immobilisations (29x)')], max_length=20, verbose_name='Nature')),
                ('motif', models.CharField(blank=True, default='', max_length=255, verbose_name='Motif')),
                ('montant_dotation', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant de la dotation')),
                ('montant_repris', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant déjà repris')),
                ('date_echeance_revue', models.DateField(blank=True, null=True, verbose_name='Échéance de revue')),
                ('date_dotation', models.DateField(verbose_name='Date de dotation')),
                ('ecriture_dotation_id', models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de l'écriture de dotation")),
                ('date_derniere_reprise', models.DateField(blank=True, null=True, verbose_name='Date de la dernière reprise')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='provisions', to='authentication.company', verbose_name='Société')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='provisions_creees', to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
            ],
            options={
                'verbose_name': 'Provision (risques/charges/stock/immo)',
                'verbose_name_plural': 'Provisions (risques/charges/stock/immo)',
                'ordering': ['-date_dotation', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='provision',
            constraint=models.UniqueConstraint(condition=models.Q(('reference__gt', '')), fields=('company', 'reference'), name='uniq_provision_ref'),
        ),
    ]
