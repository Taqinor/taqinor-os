"""NTCON16 — PPSPS de chantier + signatures sous-traitant (e-sign loi 53-05).

Migration ADDITIVE : deux tables dans ``btp_chantier`` (+ la table de liaison
auto du M2M ``lots_couverts``, elle aussi locale). Aucune migration ajoutée
chez ``qhse``/``installations``/``stock`` — les références croisées sont des
FK déclarées PAR CHAÎNE depuis cette app, ou des IDs lâches (document GED).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('btp_chantier', '0007_ntcon14_lot_lottache'),
        ('installations', '0096_odx19_repoint_achats_crossapp'),
        ('stock', '0141_fichetechnique_pdf_filename_fichetechnique_pdf_key_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PPSPSChantier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(blank=True, default='', max_length=200, verbose_name='Titre')),
                ('document_ged_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID du document GED du PPSPS')),
                ('date_validation', models.DateField(blank=True, null=True, verbose_name='Validé le')),
                ('chantier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_ppsps', to='installations.installation', verbose_name='Chantier')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_ppsps', to='authentication.company', verbose_name='Société')),
                ('lots_couverts', models.ManyToManyField(blank=True, related_name='ppsps', to='btp_chantier.lot', verbose_name='Lots couverts')),
                ('valide_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='btp_ppsps_valides', to=settings.AUTH_USER_MODEL, verbose_name='Validé par')),
            ],
            options={
                'verbose_name': 'PPSPS de chantier',
                'verbose_name_plural': 'PPSPS de chantier',
                'ordering': ['-date_validation', '-id'],
            },
        ),
        migrations.CreateModel(
            name='PPSPSSignature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('signataire_nom', models.CharField(max_length=255, verbose_name='Nom du signataire')),
                ('methode', models.CharField(choices=[('typed', 'Nom dactylographié'), ('draw', 'Signature dessinée')], default='typed', max_length=20, verbose_name='Méthode de signature')),
                ('date_signature', models.DateTimeField(auto_now_add=True, verbose_name='Signé le')),
                ('ip_adresse', models.CharField(blank=True, default='', max_length=45)),
                ('user_agent', models.TextField(blank=True, default='')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_ppsps_signatures', to='authentication.company', verbose_name='Société')),
                ('ppsps', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signatures', to='btp_chantier.ppspschantier', verbose_name='PPSPS')),
                ('sous_traitant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_ppsps_signatures', to='stock.fournisseur', verbose_name='Sous-traitant')),
            ],
            options={
                'verbose_name': 'Signature de PPSPS',
                'verbose_name_plural': 'Signatures de PPSPS',
                'ordering': ['-date_signature', '-id'],
            },
        ),
        migrations.AddField(
            model_name='ppspschantier',
            name='sous_traitants_signataires',
            field=models.ManyToManyField(blank=True, related_name='btp_ppsps_signes', through='btp_chantier.PPSPSSignature', to='stock.fournisseur', verbose_name='Sous-traitants signataires'),
        ),
        migrations.AddIndex(
            model_name='ppspschantier',
            index=models.Index(fields=['company', 'chantier'], name='btp_ppsps_co_chantier'),
        ),
        migrations.AddConstraint(
            model_name='ppspssignature',
            constraint=models.UniqueConstraint(fields=('ppsps', 'sous_traitant'), name='btp_ppsps_signataire_uniq'),
        ),
    ]
