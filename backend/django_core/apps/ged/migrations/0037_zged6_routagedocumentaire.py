import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ged', '0036_zged5_document_proprietaire_contact'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoutageDocumentaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(max_length=50, verbose_name='source (code de module)')),
                ('dossier_cible', models.CharField(max_length=500, verbose_name='dossier cible (segments {{ jeton }})')),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cabinet_cible', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='routages_documentaires', to='ged.cabinet')),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ged_routages_documentaires', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_routages_documentaires_crees', to=settings.AUTH_USER_MODEL)),
                ('tags_defaut', models.ManyToManyField(blank=True, related_name='routages_documentaires', to='ged.documenttag')),
            ],
            options={
                'verbose_name': 'Routage documentaire',
                'verbose_name_plural': 'Routages documentaires',
                'ordering': ['source', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='routagedocumentaire',
            index=models.Index(fields=['company', 'source'], name='ged_routage_co_source_idx'),
        ),
        migrations.AddConstraint(
            model_name='routagedocumentaire',
            constraint=models.UniqueConstraint(fields=('company', 'source'), name='ged_routage_co_source_unique'),
        ),
    ]
