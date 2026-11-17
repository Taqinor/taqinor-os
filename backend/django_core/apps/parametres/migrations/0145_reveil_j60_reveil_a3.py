"""17/11/2026 — le barreau « Réveil J60 » de la cadence `reveil` porte
`reveil_a3`, la clé que le moteur lui assigne TOUJOURS.

`apps.crm.cadence_plan._adapter_gabarits_reveil` réaffecte la clé du J60 par
rang (`reveil_a3`, que le lead ait ou non un devis) : le barreau seedé sous
`reveil_a2` annonçait donc dans Paramètres un texte qui ne partait jamais. Le
gabarit livré dit désormais `reveil_a3` ; ce rattrapage aligne les lignes
déjà seedées.

SEULEMENT une ligne `reveil` d'ordre 2, WhatsApp, J60, encore à `reveil_a2` :
une clé choisie par la société reste intacte, ainsi qu'un barreau déplacé ou
passé en appel. Idempotent. Les touches déjà posées ne bougent pas. Marche
arrière : rien (la ligne ne se distingue plus d'un réglage de la société).
"""
from django.db import migrations


def poser_reveil_a3(apps, schema_editor):
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    for ligne in Etape.objects.filter(
        cadence='reveil', ordre=2, canal='whatsapp', delai_jours=60,
        template_cle='reveil_a2',
    ).iterator():
        ligne.template_cle = 'reveil_a3'
        ligne.save(update_fields=['template_cle'])


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0144_messagetemplate_cles_passation_appel'),
    ]

    operations = [
        migrations.RunPython(poser_reveil_a3, migrations.RunPython.noop),
    ]
