"""XACC17 — Table de taux de change + contre-valeur MAD au grand livre.

Additif : ``TauxDevise`` (taux quotidien devise → MAD par société, source
manuelle ou feed key-gated). Aucun modèle existant n'est modifié ; l'absence
de table laisse le repli actuel (taux=1/MAD) intact.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0053_planamortissementfiscal_dotationderogatoire'),
    ]

    operations = [
        migrations.CreateModel(
            name='TauxDevise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('devise', models.CharField(max_length=10, verbose_name='Devise (ISO 4217)')),
                ('date_taux', models.DateField(verbose_name='Date du taux')),
                ('taux_vers_mad', models.DecimalField(decimal_places=6, default='1.000000', max_digits=14, verbose_name='Taux vers MAD (1 devise = X MAD)')),
                ('source', models.CharField(choices=[('manuel', 'Saisie manuelle'), ('bkam', 'Bank Al-Maghrib (feed)'), ('ecb', 'Banque Centrale Européenne (feed)')], default='manuel', max_length=10, verbose_name='Source')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='taux_devise', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Taux de change',
                'verbose_name_plural': 'Taux de change',
                'ordering': ['-date_taux', 'devise'],
            },
        ),
        migrations.AddConstraint(
            model_name='tauxdevise',
            constraint=models.UniqueConstraint(fields=('company', 'devise', 'date_taux'), name='uniq_taux_devise_par_jour'),
        ),
    ]
