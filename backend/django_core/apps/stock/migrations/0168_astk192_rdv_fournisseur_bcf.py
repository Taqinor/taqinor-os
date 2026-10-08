"""ASTK192 — un rendez-vous de quai réservé par jeton porte son fournisseur et
son BCF.

ADDITIF PUR : deux FK NULLABLES (``SET_NULL``) sur ``RendezVousTransporteur``.
Les rendez-vous existants restent à NULL (comportement inchangé). RÉVERSIBLE :
``RemoveField`` sans perte de donnée métier (colonnes neuves).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0007_astk59_quantite_appliquee'),
        ('stock', '0167_astk50_accordrfa_avoir_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='rendezvoustransporteur',
            name='fournisseur',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rendez_vous_quai', to='stock.fournisseur'),
        ),
        migrations.AddField(
            model_name='rendezvoustransporteur',
            name='bon_commande',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rendez_vous_quai',
                to='achats.boncommandefournisseur'),
        ),
    ]
