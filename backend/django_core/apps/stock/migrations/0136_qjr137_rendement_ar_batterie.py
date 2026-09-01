"""QJR137 (audit QJR79) — LE RENDEMENT ALLER-RETOUR BATTERIE, ENFIN SOURÇABLE.

``quote_engine.pricing.BATTERY_ROUNDTRIP = 0.90`` était un forfait de code que
rien ne pouvait sourcer : il borne pourtant ``restitue_kwh`` du simulateur
(``apps/ventes/etude_horaire.py``), donc ``auto_jour_avec``, donc
``bareme.economie_deux_factures_mad`` — l'ÉCONOMIE « avec batterie » montrée au
client. Contraste probant relevé par l'audit : la CAPACITÉ, elle, est bien lue
sur la fiche (``bat_kwh_usable``, sinon ``bat_kwh_nominal × bat_dod_pct``) — la
profondeur de décharge était sourcée, le rendement non, et AUCUN champ de fiche
ne pouvait le porter. ``bat_rendement_ar_pct`` est ce champ.

ADDITIF PUR (``null=True``/``blank=True``) : aucune fiche existante n'est
impactée, aucune valeur n'est écrite. Vide = NON PUBLIÉ — le moteur applique
alors l'hypothèse de référence 0,90 et l'ÉCRIT dans les hypothèses affichées
(la discipline déjà appliquée à la provision de remplacement onduleur).

AUCUN REMPLISSAGE, DÉLIBÉRÉMENT — et c'est la différence avec 0125/0130/0132.
Ces migrations-là comblaient une valeur que le fondateur avait déjà PUBLIÉE
dans ``seed_catalogue``. Ici, aucune valeur de rendement n'est sourcée au dépôt
pour aucun SKU : en écrire une serait inventer un chiffre qui repartirait
ensuite au client comme s'il venait de la datasheet (règle fondateur « zéro
chiffre inventé »). Les fiches restent donc vides jusqu'à ce que le fondateur
saisisse les valeurs constructeur, et le moteur dit l'hypothèse en attendant.

RÉVERSIBLE : oui — un ``AddField`` d'une colonne NULL se défait par un
``RemoveField`` automatique, sans perte (aucune donnée n'est écrite ici).
"""
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0135_produit_nom_sans_sku_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_rendement_ar_pct',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text='Rendement aller-retour publié (%, « round-trip '
                          'efficiency »). Vide = non publié : le moteur '
                          'applique alors son hypothèse de référence et le dit.',
                max_digits=4, null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('1')),
                    django.core.validators.MaxValueValidator(Decimal('100')),
                ]),
        ),
    ]
