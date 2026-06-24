"""QJ4 — DevisNudgeLog : trace de relance automatique vendeur pour devis envoyé.

Additive, reversible. Tracks which nudge levels have fired per devis so the
beat task stays idempotent. One row per (devis, niveau) — unique_together
enforces exactly-once-per-level.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0034_qj17_devis_layout_hash'),
    ]

    operations = [
        migrations.CreateModel(
            name='DevisNudgeLog',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('niveau', models.PositiveSmallIntegerField(
                    help_text='0 = premier palier, 1 = deuxième, etc.',
                    verbose_name='Niveau (indice 0-based)')),
                ('jours', models.PositiveSmallIntegerField(
                    help_text='Nombre de jours après date_envoi de ce palier.',
                    verbose_name='Jours après envoi')),
                ('canal', models.CharField(
                    choices=[('email', 'Email'), ('wa_draft', 'WhatsApp draft (wa.me)')],
                    default='wa_draft', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='devis_nudge_logs',
                    to='authentication.company')),
                ('devis', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='nudge_logs',
                    to='ventes.devis')),
            ],
            options={
                'verbose_name': 'Relance automatique devis',
                'verbose_name_plural': 'Relances automatiques devis',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='devisnudgelog',
            unique_together={('devis', 'niveau')},
        ),
        migrations.AddIndex(
            model_name='devisnudgelog',
            index=models.Index(
                fields=['devis', 'niveau'],
                name='ventes_nudge_dev_niv_idx'),
        ),
    ]
