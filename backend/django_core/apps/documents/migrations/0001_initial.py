# Écrite à la main (24/11/2026) sur le modèle de ``makemigrations`` : le démon
# Docker de la session de construction était arrêté. Additive : deux tables
# neuves, aucune table existante touchée.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0036_apfs66_appartenance_role'),
        ('installations', '0141_acel_jour_ancrage_recurrence'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActeContractuel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('contrat_installation', "Contrat d'installation"), ('pv_livraison', 'Livraison du matériel'), ('pv_reception', 'Réception des travaux'), ('cloture_garanties', 'Quitus et certificat de garantie')], max_length=30)),
                ('variante', models.CharField(blank=True, choices=[('', 'Aucune'), ('reste_a_regler', 'Reste à régler'), ('tranche_reglee', 'Tranche réglée')], default='', max_length=20)),
                ('reference', models.CharField(blank=True, default='', max_length=60)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('emis', 'Émis'), ('signe', 'Signé'), ('annule', 'Annulé')], default='brouillon', max_length=20)),
                ('version', models.PositiveIntegerField(default=1)),
                ('surcharges', models.JSONField(blank=True, default=dict)),
                ('surcharges_ar', models.JSONField(blank=True, default=dict)),
                ('contenu', models.JSONField(blank=True, null=True)),
                ('contenu_ar', models.JSONField(blank=True, null=True)),
                ('emis_le', models.DateTimeField(blank=True, null=True)),
                ('signe_le', models.DateTimeField(blank=True, null=True)),
                ('signataire_nom', models.CharField(blank=True, default='', max_length=150)),
                ('signature_client', models.TextField(blank=True, default='')),
                ('mode_signature', models.CharField(blank=True, choices=[('', 'Aucun'), ('sur_place', 'Sur place'), ('papier', 'Sur papier'), ('distance', 'À distance')], default='', max_length=20)),
                ('preuve', models.JSONField(blank=True, default=dict)),
                ('statut_avant_annulation', models.CharField(blank=True, default='', max_length=20)),
                ('motif_annulation', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chantier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='actes_contractuels', to='installations.installation')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actes_contractuels', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='actes_contractuels_crees', to=settings.AUTH_USER_MODEL)),
                ('emis_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='actes_contractuels_emis', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['company', 'chantier'], name='documents_acte_co_chantier')],
                'constraints': [models.UniqueConstraint(fields=('company', 'chantier', 'type', 'variante'), name='documents_acte_unique_par_chantier')],
            },
        ),
        migrations.CreateModel(
            name='ModeleActe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('contrat_installation', "Contrat d'installation"), ('pv_livraison', 'Livraison du matériel'), ('pv_reception', 'Réception des travaux'), ('cloture_garanties', 'Quitus et certificat de garantie')], max_length=30)),
                ('surcharges', models.JSONField(blank=True, default=dict)),
                ('surcharges_ar', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modeles_actes', to='authentication.company')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modeles_actes_modifies', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('company', 'type'), name='documents_modele_acte_unique')],
            },
        ),
    ]
