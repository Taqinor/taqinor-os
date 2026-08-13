# NTCRM23 — Défis et leaderboards d'équipe : un nouveau modèle additif (Defi).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0073_dealenregistre_statut_a_payer'),
    ]

    operations = [
        migrations.CreateModel(
            name='Defi',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom du défi')),
                ('periode_debut', models.DateField(verbose_name='Début')),
                ('periode_fin', models.DateField(verbose_name='Fin')),
                ('metrique', models.CharField(choices=[
                    ('nb_leads', 'Nombre de leads'),
                    ('nb_contacts', 'Leads contactés'),
                    ('nb_devis', 'Nombre de devis'),
                    ('ca_signe', 'CA signé (MAD TTC)'),
                    ('nb_rdv', 'Rendez-vous effectués')], max_length=12,
                    verbose_name='Métrique')),
                ('cible_equipe', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    verbose_name="Cible d'équipe (optionnelle)")),
                ('recompense', models.CharField(
                    blank=True, default='', max_length=300, verbose_name='Récompense')),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='defis', to='authentication.company')),
            ],
            options={
                'verbose_name': "Défi d'équipe",
                'verbose_name_plural': "Défis d'équipe",
                'ordering': ['-periode_debut', '-id'],
            },
        ),
    ]
