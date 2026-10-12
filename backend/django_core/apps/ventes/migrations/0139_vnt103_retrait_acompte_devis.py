"""VNT103 — retrait des champs morts ``Devis.acompte_pct`` / ``acompte_montant``.

D-VNT-3 fait de l'échéancier l'UNIQUE vérité de l'acompte (VNT28 l'écrit) ;
ces deux colonnes « persistées pour accès rapide » n'avaient plus aucun
lecteur (0 dans ``frontend/src``, 0 dans ``quote_engine``, non lues par
``_payload_content_hash``) et étaient NULL sur toutes les lignes de prod
(relevé du 12/10/2026 — l'orchestrateur recompte en lecture seule avant le
merge).

MIGRATION DESTRUCTIVE, RÉVERSIBLE (notée au DONE LOG) :
  1. ``RemoveConstraint ck_devis_acompte_montant_positif`` — retour :
     ``AddConstraint`` (Q(acompte_montant__gte=0)) re-posé APRÈS que le
     retour de (2) a recréé la colonne (ordre inverse de Django) ;
  2. ``RemoveField acompte_montant`` puis ``acompte_pct`` — retour :
     ``AddField`` (``null=True`` : les colonnes reviennent, vides — rien
     n'est perdu puisqu'elles étaient toutes NULL).
``migrate ventes 0138`` rejoue les trois retours.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0138_regles_calcul_devis_envoyes'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='devis',
            name='ck_devis_acompte_montant_positif',
        ),
        migrations.RemoveField(
            model_name='devis',
            name='acompte_montant',
        ),
        migrations.RemoveField(
            model_name='devis',
            name='acompte_pct',
        ),
    ]
