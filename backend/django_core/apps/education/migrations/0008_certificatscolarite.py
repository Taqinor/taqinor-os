# NTEDU18 — Certificat de scolarité (numéroté via core.numbering).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('education', '0007_evaluation_note'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificatScolarite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('numero', models.CharField(db_index=True, max_length=30, verbose_name='Numéro')),
                ('date_generation', models.DateField(verbose_name='Date de génération')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('annee_scolaire', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='certificats_scolarite', to='education.anneescolaire', verbose_name='Année scolaire')),
                ('eleve', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='certificats_scolarite', to='education.eleve', verbose_name='Élève')),
                ('genere_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='education_certificats_generes', to=settings.AUTH_USER_MODEL, verbose_name='Généré par')),
            ],
            options={
                'verbose_name': 'Certificat de scolarité',
                'verbose_name_plural': 'Certificats de scolarité',
                'ordering': ['-id'],
                'constraints': [models.UniqueConstraint(fields=('company', 'numero'), name='education_certificat_numero_unique_par_societe')],
            },
        ),
    ]
