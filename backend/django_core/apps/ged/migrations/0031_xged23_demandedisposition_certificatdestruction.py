from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('ged', '0030_xged21_regleaclmetadonnee'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeDisposition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=200)),
                ('action', models.CharField(choices=[('detruire', 'Détruire'), ('archiver', 'Archiver')], default='detruire', max_length=10)),
                ('documents', models.JSONField(blank=True, default=list, verbose_name='ids des documents proposés')),
                ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('approuvee', 'Approuvée'), ('rejetee', 'Rejetée'), ('executee', 'Exécutée')], default='en_attente', max_length=10)),
                ('commentaire', models.TextField(blank=True, default='')),
                ('decision_le', models.DateTimeField(blank=True, null=True, verbose_name='décidée le')),
                ('executee_le', models.DateTimeField(blank=True, null=True, verbose_name='exécutée le')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_demandes_disposition', to='authentication.company')),
                ('demandeur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_demandes_disposition_emises', to=settings.AUTH_USER_MODEL)),
                ('approbateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_demandes_disposition_recues', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Demande de disposition',
                'verbose_name_plural': 'Demandes de disposition',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='CertificatDestruction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_id_origine', models.PositiveBigIntegerField(verbose_name="id d'origine du document détruit")),
                ('document_nom', models.CharField(max_length=255)),
                ('politique_appliquee', models.CharField(blank=True, default='', max_length=255)),
                ('hash_metadonnees', models.CharField(blank=True, default='', max_length=64, verbose_name='hash des métadonnées détruites (SHA-256)')),
                ('detruit_le', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_certificats_destruction', to='authentication.company')),
                ('demande', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='certificats', to='ged.demandedisposition')),
                ('detruit_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_certificats_destruction_emis', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Certificat de destruction',
                'verbose_name_plural': 'Certificats de destruction',
                'ordering': ['-detruit_le', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='demandedisposition',
            index=models.Index(fields=['company', 'statut'], name='ged_dispo_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='certificatdestruction',
            index=models.Index(fields=['company', 'demande'], name='ged_certif_co_demande_idx'),
        ),
    ]
