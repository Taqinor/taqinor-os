"""NTOBS5 — RTO annoncé (heures) pour l'écran self-service « Sauvegardes ».

Additive : nullable, vide par défaut = comportement historique inchangé pour
toute société existante (non communiqué)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0087_companyprofile_fuseau_horaire'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='rto_annonce_heures',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Temps de restauration cible annoncé au client '
                          '(heures), texte informatif — pas un engagement '
                          'technique automatisé. Vide = non communiqué.',
                verbose_name='RTO annoncé (heures)'),
        ),
    ]
