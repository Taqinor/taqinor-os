"""17/11/2026 (fondateur) — les libellés des barreaux ne mentent plus.

« Appel 3 », « Appel de suivi » (deux fois), « Dimanche famille », « Dernier
message », « Réveil J30 »… ne disaient ni le canal ni le moment : la
commerciale ne savait pas ce que la touche lui demandait. Les gabarits livrés
(`CADENCES_DEFAUT`) portent désormais des noms parlants ; les LIBELLÉS seuls
changent — jamais un rythme, un canal, une clé de message ou un texte.

Rattrapage des lignes déjà seedées, chacune SEULEMENT si son (cadence, ordre)
correspond ET si son libellé vaut EXACTEMENT l'ancien défaut : un libellé
retouché à la main n'est jamais écrasé, et les lignes de la production qui
portent déjà « Appel de suivi J+2 » / « J+7 » (après devis, ordres 2 et 6)
restent telles quelles. Les touches déjà posées (`RelanceEtape`) gardent leur
libellé : il est copié à la création. Le moteur reconnaît ces barreaux (contact,
après devis, réveil) par leur ordre et leur clé de message, jamais par leur
libellé. Idempotent. Marche arrière : rien (une ligne renommée ne se distingue plus
d'une ligne que la société a nommée elle-même).
"""
from django.db import migrations

# (cadence, ordre, ancien libellé, nouveau libellé)
_RENOMMAGES = (
    ('contact', 3, 'Appel 2 (répondeur)', '2e appel — laisser un message vocal'),
    ('contact', 4, 'Appel 3', '3e appel — le lendemain'),
    ('contact', 5, 'Appel 4 (répondeur)', '4e appel — laisser un message vocal'),
    ('contact', 7, 'Appel 5 (dernier)', '5e appel — dernier essai par téléphone'),
    ('contact', 8, '« Je classe ? »', 'WhatsApp de clôture — « Je classe ? »'),
    ('apres_devis', 2, 'Appel de suivi', 'Appel de suivi J+2'),
    ('apres_devis', 6, 'Appel de suivi', 'Appel de suivi J+7'),
    ('apres_devis', 3, 'Dimanche famille', 'WhatsApp — décision en famille'),
    ('apres_devis', 10, 'Dernier message', 'WhatsApp à 2 mois'),
    ('apres_devis', 11, 'Dernier appel', 'Dernier appel à 3 mois'),
    ('reveil', 1, 'Réveil J30', 'Appel de réveil à 1 mois'),
    ('reveil', 2, 'Réveil J60', 'WhatsApp de réveil à 2 mois'),
)


def renommer(apps, schema_editor):
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    for cadence, ordre, ancien, nouveau in _RENOMMAGES:
        for ligne in Etape.objects.filter(
            cadence=cadence, ordre=ordre, libelle=ancien,
        ).iterator():
            ligne.libelle = nouveau
            ligne.save(update_fields=['libelle'])


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0145_reveil_j60_reveil_a3'),
    ]

    operations = [
        migrations.RunPython(renommer, migrations.RunPython.noop),
    ]
