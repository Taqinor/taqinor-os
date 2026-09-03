"""AUD188 (rectificatif) — un ``Paiement`` négatif est une CONTRE-PASSATION.

La migration 0005 posait ``ck_paiement_montant_positif`` (``montant >= 0``) en
partant de « un encaissement négatif n'existe pas — un remboursement est un
avoir, pas un paiement de signe inverse ». Cette prémisse est FAUSSE dans ce
dépôt : FG50 (annulation d'une facture d'acompte, action « rembourser »,
``apps/ventes/views/facture.py``) écrit délibérément un ``Paiement`` NÉGATIF de
contre-passation, pour que le net encaissé de la facture morte retombe à zéro
et que l'acompte ne reste pas « coincé ». La contrainte transformait cet appel
en HTTP 500 (``IntegrityError`` sur ``ck_paiement_montant_positif``).

On retire donc CETTE contrainte, et elle seule : les huit autres backstops
d'AUD188 (Facture, LigneFacture, Avoir, LigneAvoir) restent en place, posés par
0005. Une ``RemoveConstraint`` séparée plutôt qu'une réécriture de 0005 : une
base déjà migrée en 0005 (dump de test restauré, environnement de recette)
porte réellement la contrainte et doit la voir tomber.

ADDITIF ET RÉVERSIBLE : aucune donnée touchée, ``git revert`` suffit.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0005_aud188_contraintes_argent'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='paiement',
            name='ck_paiement_montant_positif',
        ),
    ]
