"""CAL52 — la photo drone / oblique du site.

AUCUN champ fichier (ARC26) : le fichier vit dans ``records.Attachment``, ce
modèle ne porte que ce que la pièce jointe générique ne sait pas dire d'une
photo de site (genre, date de prise de vue SAISIE, légende, calage à venir).

Purement ADDITIVE : une table neuve, aucune colonne existante touchée, aucune
donnée réécrite — donc revertable par un simple ``git revert`` + rollback.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0001_initial'),
        ('records', '0013_vx210_snooze_trigger_event'),
        ('authentication', '0032_customuser_calendrier_hegirien'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PhotoSite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('genre', models.CharField(choices=[('drone', 'Drone'), ('oblique', 'Oblique (aérienne)'), ('sol', 'Depuis le sol')], default='drone', max_length=10, verbose_name='Genre')),
                ('prise_le', models.DateField(verbose_name='Prise de vue le')),
                ('legende', models.CharField(blank=True, default='', max_length=200, verbose_name='Légende')),
                ('calage', models.JSONField(blank=True, null=True, verbose_name='Calage')),
                ('ajoutee_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calepinage_photos_site', to=settings.AUTH_USER_MODEL, verbose_name='Ajoutée par')),
                ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos_site_calepinage', to='records.attachment', verbose_name='Pièce jointe')),
                ('calepinage', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos_site', to='calepinage.calepinage', verbose_name='Calepinage')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Photo de site',
                'verbose_name_plural': 'Photos de site',
                'ordering': ['-prise_le', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='photosite',
            index=models.Index(fields=['calepinage', '-prise_le'], name='cal_pho_cal_prise_idx'),
        ),
        migrations.AddIndex(
            model_name='photosite',
            index=models.Index(fields=['company', '-created_at'], name='cal_pho_co_cree_idx'),
        ),
    ]
