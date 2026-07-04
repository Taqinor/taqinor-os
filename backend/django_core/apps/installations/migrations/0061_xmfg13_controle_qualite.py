import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0060_xmfg12_ordredemontage'),
        ('records', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ControleQualiteModele',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_controle_qualite_modeles', to='authentication.company')),
                ('kit', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='controle_qualite_modele', to='installations.kit')),
            ],
            options={
                'verbose_name': 'Modèle de contrôle qualité',
                'verbose_name_plural': 'Modèles de contrôle qualité',
                'ordering': ['kit_id'],
            },
        ),
        migrations.CreateModel(
            name='ControleQualiteItemModele',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=255)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('valeur_min', models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ('valeur_max', models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ('unite', models.CharField(blank=True, default='', max_length=20)),
                ('photo_requise', models.BooleanField(default=False)),
                ('modele', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='installations.controlequalitemodele')),
            ],
            options={
                'verbose_name': 'Item de contrôle qualité',
                'verbose_name_plural': 'Items de contrôle qualité',
                'ordering': ['modele_id', 'ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ControleQualiteOrdre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resultat', models.CharField(choices=[('en_attente', 'En attente'), ('pass', 'Passé'), ('fail', 'Échec')], default='en_attente', max_length=12)),
                ('valeur_mesuree', models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ('date_controle', models.DateTimeField(blank=True, null=True)),
                ('controle_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('item_modele', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='installations.controlequaliteitemmodele')),
                ('ordre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='controles_qualite', to='installations.ordreassemblage')),
                ('photo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='records.attachment')),
            ],
            options={
                'verbose_name': 'Exécution de contrôle qualité',
                'verbose_name_plural': 'Exécutions de contrôle qualité',
                'ordering': ['ordre_id', 'item_modele__ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='controlequaliteordre',
            index=models.Index(fields=['ordre', 'resultat'], name='idx_cqordre_ordre_resultat'),
        ),
        migrations.AlterUniqueTogether(
            name='controlequaliteordre',
            unique_together={('ordre', 'item_modele')},
        ),
    ]
