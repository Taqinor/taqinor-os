import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0033_xfsm14_thermographie'),
        ('stock', '0040_fournisseur_custom_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CampagneRappel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre', models.CharField(max_length=255, verbose_name='Titre')),
                ('serie_debut', models.CharField(blank=True, default='', max_length=120, verbose_name='Série début')),
                ('serie_fin', models.CharField(blank=True, default='', max_length=120, verbose_name='Série fin')),
                ('lot', models.CharField(blank=True, default='', max_length=120, verbose_name='Lot')),
                ('motif', models.TextField(blank=True, default='', verbose_name='Motif')),
                ('gravite', models.CharField(choices=[('mineure', 'Mineure'), ('majeure', 'Majeure'), ('critique', 'Critique')], default='majeure', max_length=10, verbose_name='Gravité')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('en_cours', 'En cours'), ('cloturee', 'Clôturée')], default='brouillon', max_length=15, verbose_name='Statut')),
                ('date_verification_efficacite', models.DateField(blank=True, null=True, verbose_name="Vérification d'efficacité")),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_campagnes_rappel', to='authentication.company', verbose_name='Société')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='qhse_campagnes_rappel', to='stock.produit', verbose_name='Produit concerné')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_campagnes_rappel', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
            ],
            options={
                'verbose_name': 'Campagne de rappel',
                'verbose_name_plural': 'Campagnes de rappel',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='ElementRappel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('equipement_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID équipement (parc)')),
                ('numero_serie', models.CharField(blank=True, default='', max_length=120, verbose_name='Numéro de série')),
                ('installation_id', models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de l'installation")),
                ('statut', models.CharField(choices=[('a_notifier', 'À notifier'), ('notifie', 'Notifié'), ('planifie', 'Planifié'), ('remplace', 'Remplacé'), ('clos', 'Clos')], default='a_notifier', max_length=15, verbose_name='Statut')),
                ('ticket_sav_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID ticket SAV (remplacement)')),
                ('notifie_le', models.DateTimeField(blank=True, null=True, verbose_name='Notifié le')),
                ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('campagne', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements', to='qhse.campagnerappel', verbose_name='Campagne')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_elements_rappel', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Élément de rappel',
                'verbose_name_plural': 'Éléments de rappel',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='elementrappel',
            index=models.Index(fields=['company', 'statut'], name='qhse_elemrappel_co_statut'),
        ),
        migrations.AddConstraint(
            model_name='elementrappel',
            constraint=models.UniqueConstraint(fields=['campagne', 'equipement_id'], name='qhse_elemrappel_campagne_equip_uniq'),
        ),
    ]
