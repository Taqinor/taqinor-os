# AUD718 — le justificatif de congé et le CV de candidature quittent le
# `FileField` disque (irrécupérable : ni `STORAGES`, ni route `/media/`, ni
# `location /media/` nginx) pour `records.Attachment` (MinIO), servi par
# `/api/django/records/attachments/<id>/download/`.
#
# Purement ADDITIF et réversible : les deux `FileField` d'origine sont
# CONSERVÉS (plus jamais écrits, juste renommés en « legacy » dans leur
# verbose_name) pour ne rien perdre des lignes historiques.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0013_vx210_snooze_trigger_event'),
        ('rh', '0083_yhard1_encrypt_dossieremploye'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeconge',
            name='justificatif_attachment',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rh_justificatifs_conge',
                to='records.attachment',
                verbose_name='Justificatif (pièce jointe)'),
        ),
        migrations.AddField(
            model_name='candidature',
            name='cv_attachment',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rh_cv_candidatures',
                to='records.attachment',
                verbose_name='CV (pièce jointe)'),
        ),
        migrations.AlterField(
            model_name='demandeconge',
            name='justificatif',
            field=models.FileField(
                blank=True, null=True,
                upload_to='rh/demandes_conge/justificatifs/',
                verbose_name='Justificatif (legacy, hors MinIO)'),
        ),
        migrations.AlterField(
            model_name='candidature',
            name='cv_fichier',
            field=models.FileField(
                blank=True, null=True, upload_to='rh/candidatures/cv/',
                verbose_name='CV (legacy, hors MinIO)'),
        ),
    ]
