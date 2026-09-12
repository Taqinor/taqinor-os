"""NTSRV23 - Enquete CSAT enrichie multi-question (purement additif).

* ``TicketSatisfaction.sous_notes`` : JSON nullable
  ``{rapidite, courtoisie, resolution}``, chaque cle OPTIONNELLE. Toutes les
  reponses deja enregistrees gardent ``NULL`` - la note globale reste la
  seule obligatoire, donc aucun rapport existant ne change.
* ``SavSlaSettings.csat_detaille_actif`` : drapeau par societe, defaut False
  = formulaire public STRICTEMENT inchange.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0060_ntsrv16_probleme'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketsatisfaction',
            name='sous_notes',
            field=models.JSONField(
                blank=True, null=True,
                help_text="{'rapidite': 1-5, 'courtoisie': 1-5, "
                          "'resolution': 1-5} — toutes optionnelles "
                          '(NTSRV23).',
                verbose_name='Sous-notes détaillées'),
        ),
        migrations.AddField(
            model_name='savslasettings',
            name='csat_detaille_actif',
            field=models.BooleanField(
                default=False,
                help_text='Ajoute au formulaire public trois sous-notes '
                          'optionnelles (rapidité, courtoisie, résolution). '
                          'OFF = formulaire actuel inchangé.',
                verbose_name='Enquête CSAT détaillée'),
        ),
    ]
