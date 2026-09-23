# CALX274 — tranches horaires (time-of-use) et leurs tarifs SAISIS par la
# société, avec la source et sa date. Migration ADDITIVE : quatre champs vides
# par défaut, aucune donnée existante touchée.
#
# Chaînage : le plan pré-déclarait « 0097 », mais la vague CAD tenait déjà
# 0097→0102 sur ``main`` ; la chaîne CALX du lot 5 est donc renumérotée
# 0103→0107 (arbitrage orchestrateur M4) et part de la tête réelle
# ``0102_cad31_paliers_premier_contact`` — une seule feuille, aucun préfixe
# en double.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0102_cad31_paliers_premier_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='tou_heures',
            field=models.JSONField(blank=True, help_text='24 libellés de tranche, un par heure de la journée (ex. « creuse », « pleine », « pointe »), tels que votre facture ou votre contrat les nomme.', null=True, verbose_name='Tranche de chaque heure (00 h → 23 h)'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='tou_tarifs',
            field=models.JSONField(blank=True, help_text='Objet {tranche: MAD/kWh} : un tarif par libellé employé dans les tranches horaires.', null=True, verbose_name='Tarif de chaque tranche (MAD/kWh)'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='tou_source',
            field=models.TextField(blank=True, default='', help_text="Obligatoire dès qu'une grille est saisie : facture, contrat ou barème officiel d'où viennent ces valeurs.", verbose_name='Source des tarifs horaires'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='tou_date_source',
            field=models.DateField(blank=True, null=True, verbose_name='Date de la source des tarifs horaires'),
        ),
    ]
