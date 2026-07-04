import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0055_xmfg3_ato_devis_chantier'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordreassemblage',
            name='statut',
            field=models.CharField(choices=[('planifie', 'Planifié'), ('en_cours', 'En cours'), ('termine', 'Terminé'), ('annule', 'Annulé')], default='planifie', max_length=20),
        ),
        migrations.AddField(
            model_name='ordreassemblage',
            name='date_prevue',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ordreassemblage',
            name='responsable',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_assemblage_responsable', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='ordreassemblage',
            name='motif_annulation',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='OrdreAssemblageActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('creation', 'Création'), ('modification', 'Modification'), ('note', 'Note')], max_length=15)),
                ('field', models.CharField(blank=True, max_length=100, null=True)),
                ('field_label', models.CharField(blank=True, max_length=150, null=True)),
                ('old_value', models.TextField(blank=True, null=True)),
                ('new_value', models.TextField(blank=True, null=True)),
                ('body', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_ordre_assemblage_activities', to='authentication.company')),
                ('ordre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activites', to='installations.ordreassemblage')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordre_assemblage_activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Activité d'ordre d'assemblage",
                'verbose_name_plural': "Activités d'ordre d'assemblage",
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='ordreassemblageactivity',
            index=models.Index(fields=['ordre', '-created_at'], name='idx_asmact_ordre_created'),
        ),
    ]
