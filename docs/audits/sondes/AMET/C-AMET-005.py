# SONDE = {'constat': 'C-AMET-005', 'sha': 'f3716e3f0', 'attendu': "portail payer : montant_du (retenue incluse) ≠ montant_exigible sur la facture 8 de démo (32 023,50 vs 31 023,50)"}
# Lecture seule : compare les deux champs sur les factures émises portant une retenue non libérée.
from django.db import transaction


def sonde(ctx):
    from apps.facturation.models import Facture
    ecarts = []
    with transaction.atomic():
        for f in Facture.objects.exclude(statut=Facture.Statut.BROUILLON)[:500]:
            du, ex = f.montant_du, getattr(f, 'montant_exigible', None)
            if ex is not None and du != ex:
                ecarts.append((f.pk, str(du), str(ex)))
        transaction.set_rollback(True)
    return {'factures_ecart_du_vs_exigible': len(ecarts), 'exemples': ecarts[:5]}
