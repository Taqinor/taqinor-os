"""SOLMVP16 — Détache ``portail`` de la GED (module sorti du produit).

Retire ``DocumentClientPortail.document_ged`` (WIR94) : c'était le SEUL lien
FK gardé→parqué de ``portail`` vers ``ged`` (inventaire du 20/09,
docs/PLAN.md « Groupe SOLMVP »). Migration destructive-revertable : seule la
colonne de LIEN part (aucune table supprimée, aucune ligne
``django_migrations`` touchée) — le document client lui-même (fichier/
fichier_key/fichier_filename/fichier_size/fichier_mime) est INTACT, le miroir
GED du même fichier disparaît avec le champ.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0010_ntprt6_invitation_portail'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='documentclientportail',
            name='document_ged',
        ),
    ]
