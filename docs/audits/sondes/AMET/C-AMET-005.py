"""Lecture seule : compare montant_du et montant_exigible sur les factures émises portant une retenue non libérée."""
SONDE = {
    'constat': 'C-AMET-005',
    'sha': 'f3716e3f0',
    'attendu': ('portail payer : montant_du (retenue incluse) ≠ montant_exigible '
                'sur la facture 8 de démo (32 023,50 vs 31 023,50)'),
}


def sonde(ctx):
    from apps.facturation.models import Facture
    ecarts = []
    for f in Facture.objects.exclude(statut=Facture.Statut.BROUILLON)[:500]:
        du, ex = f.montant_du, getattr(f, 'montant_exigible', None)
        if ex is not None and du != ex:
            ecarts.append((f.pk, str(du), str(ex)))
    return {'repro': bool(ecarts), 'factures_ecart_du_vs_exigible': len(ecarts), 'exemples': ecarts[:5]}
