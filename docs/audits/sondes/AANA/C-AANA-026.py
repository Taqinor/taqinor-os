"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-026 (audit analyse du 05/10, §6) : paiement.recorded perdu (Decimal brut non sérialisable dans le journal).
"""
SONDE = {
    'constat': 'C-AANA-026',
    'sha': '5908d43bb',
    'attendu': "défaut absent : un paiement Decimal('123.45') produit un ApiEvent paiement.recorded de montant 123.45 (témoin facture.created présent)",
}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.db import connection
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture, Paiement
    from apps.publicapi.constants import EVENT_FACTURE_CREATED, EVENT_PAIEMENT_RECORDED
    from apps.publicapi.models import ApiEvent
    co = Company.objects.create(nom='Sonde 026', slug='sonde-aana-026')
    cl = Client.objects.create(company=co, nom='Cli sonde 026')
    f = Facture.objects.create(company=co, reference='FA-SONDE-026', client=cl, statut=Facture.Statut.EMISE)
    p = Paiement.objects.create(company=co, facture=f, montant=Decimal('123.45'), date_paiement=datetime.date(2026, 10, 5))
    # Transaction externe jamais commitée : on rejoue à la main les callbacks on_commit en attente.
    for _sids, fonc, *_ in list(connection.run_on_commit):
        fonc()
    temoin = ApiEvent.objects.filter(company=co, type=EVENT_FACTURE_CREATED).count()
    evt = ApiEvent.objects.filter(company=co, type=EVENT_PAIEMENT_RECORDED).first()
    montant = evt.payload.get('montant') if evt else None
    print('facture.created=%s paiement.recorded=%s montant=%r' % (temoin, bool(evt), montant))
    return {'repro': bool(evt) and montant == 123.45 and evt.payload.get('id') == p.pk,
            'temoin_facture_created': temoin, 'montant': montant}
