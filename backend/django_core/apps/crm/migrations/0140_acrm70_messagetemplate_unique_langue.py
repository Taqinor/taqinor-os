"""ACRM70 (C-ACRM-VER-002) — l'unicité d'un modèle de message CRM passe de
(société, nom) à (société, nom, langue).

Constat : la file WhatsApp en masse (``fiche_funnel._corps_whatsapp_en_masse``)
cherche le jumeau d'un gabarit dans la langue préférée du lead, mais
l'ancienne contrainte interdisait ce jumeau : « RDV » FR et « RDV » darija ne
pouvaient pas coexister. Élargir la contrainte ne rend aucune ligne existante
invalide (tout couple (société, nom) unique l'est aussi avec la langue) ;
additive et réversible (la marche arrière échoue seulement s'il existe déjà
un jumeau de langue, à fusionner avant).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0139_agq39_mode_pompe_plaque'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='messagetemplate',
            unique_together={('company', 'nom', 'langue')},
        ),
    ]
