"""CADV33 — registre des expériences de cadence (``crm.ExperienceCadence``).

Table nouvelle, additive : aucune donnée existante touchée. Réversible
(``migrate crm 0147``).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0035_customuser_fonction'),
        ('crm', '0147_enf15_code_parrainage_par_societe'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExperienceCadence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField(verbose_name='Date du changement')),
                ('changement', models.CharField(max_length=255, verbose_name='Changement')),
                ('metrique', models.CharField(max_length=120, verbose_name='Métrique')),
                ('effet_attendu', models.CharField(blank=True, default='', max_length=255, verbose_name='Effet attendu')),
                ('date_lecture', models.DateField(blank=True, null=True, verbose_name='Date de lecture')),
                ('resultat', models.TextField(blank=True, default='', verbose_name='Résultat')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Expérience de cadence',
                'verbose_name_plural': 'Expériences de cadence',
                'ordering': ['date', 'id'],
                'indexes': [models.Index(fields=['company', 'date'], name='crm_expcad_company_date_idx')],
            },
        ),
    ]
