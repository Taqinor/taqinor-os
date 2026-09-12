"""NTCON19 — checklist de réception de lot (avant paiement final du lot).

Migration ADDITIVE : une table dans ``btp_chantier``. La checklist
d'EXÉCUTION du chantier (``installations.ChantierChecklistItem``) reste
strictement inchangée — aucune migration ajoutée chez ``installations``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('btp_chantier', '0009_ntcon18_abonnement_rapport_photo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LotChecklistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cle', models.CharField(max_length=40, verbose_name='Clé')),
                ('libelle', models.CharField(max_length=120, verbose_name='Libellé')),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('obligatoire', models.BooleanField(default=True, verbose_name='Obligatoire pour la réception')),
                ('fait', models.BooleanField(default=False, verbose_name='Fait')),
                ('fait_le', models.DateTimeField(blank=True, null=True, verbose_name='Fait le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_lot_checklist_items', to='authentication.company', verbose_name='Société')),
                ('fait_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='btp_lot_checklist_faits', to=settings.AUTH_USER_MODEL, verbose_name='Fait par')),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='checklist', to='btp_chantier.lot', verbose_name='Lot')),
            ],
            options={
                'verbose_name': 'Étape de checklist de réception (lot)',
                'verbose_name_plural': 'Étapes de checklist de réception (lot)',
                'ordering': ['ordre', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='lotchecklistitem',
            constraint=models.UniqueConstraint(fields=('lot', 'cle'), name='btp_lot_checklist_cle_uniq'),
        ),
    ]
