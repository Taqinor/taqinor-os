# Generated for FG307 — Attestations & assurances obligatoires des sous-traitants.
# Additif : on AJOUTE une seule table (AttestationSousTraitant). Aucune colonne
# d'une table existante n'est modifiée. Aucune migration destructive.
# Noms d'index ≤ 30 caractères : idx_att_co_soustrait, idx_att_co_expiration.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0022_fg306_facture_soustraitant'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AttestationSousTraitant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_piece', models.CharField(choices=[('cnss', 'Attestation CNSS'), ('rc_decennale', 'Assurance RC décennale'), ('rc_travaux', 'Assurance RC travaux'), ('agrement', 'Agrément métier'), ('fiscale', 'Attestation fiscale'), ('autre', 'Autre pièce')], default='autre', max_length=20)),
                ('reference', models.CharField(blank=True, max_length=120, null=True)),
                ('organisme', models.CharField(blank=True, max_length=255, null=True)),
                ('date_emission', models.DateField(blank=True, null=True)),
                ('date_expiration', models.DateField(blank=True, null=True)),
                ('obligatoire', models.BooleanField(default=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_attestations_sous_traitant', to='authentication.company')),
                ('sous_traitant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attestations', to='installations.soustraitant')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_attestations_sous_traitant_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Attestation sous-traitant',
                'verbose_name_plural': 'Attestations sous-traitant',
                'ordering': ['sous_traitant_id', 'type_piece'],
            },
        ),
        migrations.AddIndex(
            model_name='attestationsoustraitant',
            index=models.Index(fields=['company', 'sous_traitant'], name='idx_att_co_soustrait'),
        ),
        migrations.AddIndex(
            model_name='attestationsoustraitant',
            index=models.Index(fields=['company', 'date_expiration'], name='idx_att_co_expiration'),
        ),
    ]
