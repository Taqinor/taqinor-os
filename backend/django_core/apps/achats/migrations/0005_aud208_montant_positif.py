"""AUD208 (ZACC9) — `PaiementFournisseur.montant` toujours strictement
positif au niveau BASE, en complément (best-effort) du verrou
`select_for_update` posé côté vue contre le sur-paiement concurrent.

La garde de concurrence RÉELLE (Σ paiements <= montant_ttc de la facture) est
une invariante CROISÉE entre lignes/tables : hors de portée d'un CHECK
PostgreSQL — c'est le verrou de ligne qui la garantit (voir
`apps.stock.services.verrouiller_facture_fournisseur_et_verifier_solde`).
Cette contrainte-ci ne couvre qu'un plancher plus modeste, déjà validé côté
serializer (`validate_montant`) mais jamais imposé en base : `montant > 0`.

Même patron que `pos/0011_aud205_quantite_positive` : les lignes existantes
non conformes (aucune attendue — `validate_montant` refuse déjà un montant
<= 0 à la création depuis longtemps) sont normalisées AVANT la pose de la
contrainte, sinon l'ajout échouerait sur une base réelle qui en porterait.
"""
from decimal import Decimal

from django.db import migrations, models


def _normaliser_montants(apps, schema_editor):
    PaiementFournisseur = apps.get_model('achats', 'PaiementFournisseur')
    # Batching (garde check_safe_migrations) : mise à jour par tranches de
    # pks via .iterator() — un update global non borné verrouillerait toute
    # la table le temps de la transaction. Patron repris de
    # pos/0011_aud205_quantite_positive.py.
    pks = PaiementFournisseur.objects.filter(
        montant__lte=0).values_list('pk', flat=True)
    batch = []
    for pk in pks.iterator(chunk_size=500):
        batch.append(pk)
        if len(batch) >= 500:
            PaiementFournisseur.objects.filter(pk__in=batch).update(
                montant=Decimal('0.01'))
            batch = []
    if batch:
        PaiementFournisseur.objects.filter(pk__in=batch).update(
            montant=Decimal('0.01'))


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0004_aud207_protect_paiementfournisseur_facture'),
    ]

    operations = [
        migrations.RunPython(
            _normaliser_montants, migrations.RunPython.noop, elidable=True),
        migrations.AddConstraint(
            model_name='paiementfournisseur',
            constraint=models.CheckConstraint(
                check=models.Q(montant__gt=0),
                name='achats_paiementfournisseur_montant_positif',
            ),
        ),
    ]
