# CALX274 — tranches horaires (time-of-use) et leurs tarifs SAISIS par la
# société, avec la source et sa date. Migration ADDITIVE : quatre champs vides
# par défaut, aucune donnée existante touchée.
#
# Chaînage : le nom est celui pré-déclaré par l'en-tête du plan (« 0097 »), mais
# la tête RÉELLE de ``parametres`` sur ``main`` est ``0102_cad31`` (la vague CAD
# a posé 0097→0102 après la rédaction du plan). La dépendance pointe donc sur
# cette tête : une seule feuille, aucun conflit de migrations (Django ordonne
# par le graphe de dépendances, jamais par le préfixe numérique — le dépôt
# porte déjà des préfixes doublés, ex. ventes 0021).

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
