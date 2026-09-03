# AUD205 — `LigneVenteComptoir.quantite` toujours strictement positive.
# Une quantité nulle/négative encaissait un montant négatif ET produisait, à la
# validation, un mouvement de stock au signe inversé (une entrée déguisée en
# vente). Le sens d'un mouvement est porté par son `type_mouvement`, jamais par
# le signe de la quantité.
#
# Additif : validateur (niveau formulaire/serializer) + CheckConstraint (dernier
# rempart en base). Les lignes existantes non conformes sont normalisées à 1
# AVANT la pose de la contrainte, sinon l'ajout échouerait sur une base réelle.
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


def _normaliser_quantites(apps, schema_editor):
    Ligne = apps.get_model('pos', 'LigneVenteComptoir')
    # Batching (garde check_safe_migrations) : mise à jour par tranches de pks
    # via .iterator() — un update global non borné verrouillerait toute la
    # table des lignes de vente comptoir le temps de la transaction. Patron
    # repris de ventes/0100_l_niv_niveau_otp_lecture.py.
    pks = Ligne.objects.filter(quantite__lte=0).values_list('pk', flat=True)
    batch = []
    for pk in pks.iterator(chunk_size=500):
        batch.append(pk)
        if len(batch) >= 500:
            Ligne.objects.filter(pk__in=batch).update(quantite=Decimal('1'))
            batch = []
    if batch:
        Ligne.objects.filter(pk__in=batch).update(quantite=Decimal('1'))


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0010_ntret31_panier_courant"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ligneventecomptoir",
            name="quantite",
            field=models.DecimalField(
                decimal_places=2,
                default=1,
                max_digits=10,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.01"))
                ],
            ),
        ),
        migrations.RunPython(
            _normaliser_quantites, migrations.RunPython.noop, elidable=True),
        migrations.AddConstraint(
            model_name="ligneventecomptoir",
            constraint=models.CheckConstraint(
                check=models.Q(quantite__gt=0),
                name="pos_lignevente_quantite_positive",
            ),
        ),
    ]
