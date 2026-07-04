from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('flotte', '0051_conducteur_conformite_transport_lourd'),
    ]

    operations = [
        migrations.CreateModel(
            name='RappelConstructeur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference_campagne', models.CharField(max_length=80, verbose_name='Référence de campagne')),
                ('constructeur', models.CharField(blank=True, max_length=120, verbose_name='Constructeur')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('vin_concernes', models.JSONField(blank=True, default=list, verbose_name='VIN concernés')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flotte_rappels_constructeur', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Rappel constructeur',
                'verbose_name_plural': 'Rappels constructeur',
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='rappelconstructeur',
            index=models.Index(fields=['company', 'reference_campagne'], name='flotte_rappel_co_ref_idx'),
        ),
    ]
