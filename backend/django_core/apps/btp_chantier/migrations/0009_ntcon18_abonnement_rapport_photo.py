"""NTCON18 — opt-in par chantier au photo-rapport hebdomadaire.

Migration ADDITIVE : une table dans ``btp_chantier``. Aucun envoi n'est
activé par défaut (opt-in strict, ligne à créer explicitement).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('btp_chantier', '0008_ntcon16_ppsps'),
        ('installations', '0096_odx19_repoint_achats_crossapp'),
    ]

    operations = [
        migrations.CreateModel(
            name='AbonnementRapportPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actif', models.BooleanField(default=True, verbose_name='Envoi hebdomadaire activé')),
                ('destinataires', models.JSONField(blank=True, default=list, verbose_name='Destinataires (emails client/MOE)')),
                ('dernier_envoi', models.DateField(blank=True, null=True, verbose_name='Dernier envoi')),
                ('chantier', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='btp_abonnement_rapport_photo', to='installations.installation', verbose_name='Chantier')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_abonnements_rapport_photo', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Abonnement au photo-rapport hebdomadaire',
                'verbose_name_plural': 'Abonnements au photo-rapport hebdomadaire',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='abonnementrapportphoto',
            index=models.Index(fields=['company', 'actif'], name='btp_rapportphoto_co_actif'),
        ),
    ]
