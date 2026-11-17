"""17/11/2026 — les trois touches après devis sans heure en production.

Constat mesuré en prod (lecture seule, 17/11) : les barreaux `apres_devis` d'ordre
1 (WhatsApp J1, `j1_pdf`), 2 (appel J2, `appel_suivi_j2`) et 6 (appel J7,
`appel_suivi_j7`) portent `heure_cible` NULL, alors que le gabarit livré
(`CADENCE_APRES_DEVIS_DEFAUT`) dit 09:30 / 18:00 / 18:00 : la touche était donc
planifiée à l'heure où le devis est parti (« J2 » à 23 h si le devis est envoyé
à 23 h), hors des créneaux d'appel et de message du protocole.

Rattrapage, SEULEMENT sur une ligne dont l'heure est encore vide ET qui porte
exactement (cadence, ordre, canal, délai en jours, clé de message) du gabarit
livré : une heure saisie par la société, un barreau déplacé ou dont la clé a
changé restent intacts. Le libellé n'est pas un critère (la prod porte
« Appel de suivi J+2 » / « Appel de suivi J+7 »). Idempotent : la 2e
application ne retrouve plus aucune ligne à heure vide. Les touches déjà
posées (`RelanceEtape`) ne bougent pas. Marche arrière : rien (une heure posée
ne se distingue plus d'une heure réglée par la société).
"""
import datetime

from django.db import migrations

T = datetime.time

# (ordre, canal, delai_jours, template_cle, heure du gabarit livré)
_HEURES = (
    (1, 'whatsapp', 1, 'j1_pdf', T(9, 30)),
    (2, 'appel', 2, 'appel_suivi_j2', T(18, 0)),
    (6, 'appel', 7, 'appel_suivi_j7', T(18, 0)),
)


def poser_les_heures(apps, schema_editor):
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    for ordre, canal, jours, cle, heure in _HEURES:
        Etape.objects.filter(
            cadence='apres_devis', ordre=ordre, canal=canal,
            delai_jours=jours, template_cle=cle, heure_cible__isnull=True,
        ).update(heure_cible=heure)


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0142_gabarits_textes_1711'),
    ]

    operations = [
        migrations.RunPython(poser_les_heures, migrations.RunPython.noop),
    ]
