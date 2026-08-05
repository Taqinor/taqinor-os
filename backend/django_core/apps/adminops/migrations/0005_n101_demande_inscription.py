import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """N101(b) — demandes d'inscription self-service (installateurs pilotes).

    Purement additive. Table GLOBALE par conception (aucune FK ``company`` —
    exemptée du garde YDATA4) : au dépôt de la demande, la société n'existe pas
    encore. L'endpoint public qui l'alimente est PARQUÉ par défaut
    (``TENANT_SIGNUP_ENABLED``) et ne crée jamais ni compte ni société.
    """

    dependencies = [
        ('adminops', '0004_n100e_facture_licence'),
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeInscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('societe', models.CharField(max_length=200, verbose_name='Société')),
                ('nom', models.CharField(max_length=150, verbose_name='Nom du contact')),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('telephone', models.CharField(blank=True, default='', max_length=30, verbose_name='Téléphone')),
                ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('approuvee', 'Approuvée'), ('refusee', 'Refusée')], default='en_attente', max_length=12, verbose_name='Statut')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('traite_le', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company_creee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demandes_inscription', to='authentication.company', verbose_name='Société créée')),
                ('traite_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demandes_inscription_traitees', to=settings.AUTH_USER_MODEL, verbose_name='Traitée par')),
            ],
            options={
                'verbose_name': "Demande d'inscription",
                'verbose_name_plural': "Demandes d'inscription",
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
