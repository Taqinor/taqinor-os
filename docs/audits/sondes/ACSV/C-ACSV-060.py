# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K60 — ticket né d'une réserve sur un chantier Installé NON réceptionné : vraie route
`interventions/<id>/ajouter-reserve/` (creer_ticket=True) puis `sav/tickets/<id>/facturer/`.
(R) chantier Installé sans date_reception ; (T) témoin : même geste sur un chantier réceptionné il y a 30 j
(garantie légale 12 mois en cours) -> 409 « garantie à confirmer » (ASAV11 / D-ASAV-2)."""
SONDE = {"constat": "C-ACSV-060", "sha": "f57951e87",
         "attendu": "repro si R : facturer 201 couverture facturable, facture au prix de vente (5000) ; "
                    "T : 409 garantie de chantier à confirmer",
         "modeles": ["sav.Ticket", "ventes.Facture", "installations.Reserve"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention
    from apps.sav.models import PieceConsommee, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 060', slug='sonde-acsv-060')
    u = get_user_model().objects.create_user(username='sonde-acsv-060', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-060', prix_achat=Decimal('2000'),
                               prix_vente=Decimal('5000'))

    def jeu(nom, statut, reception):
        cl = Client.objects.create(company=co, nom='Client', prenom=nom, email=f'acsv060-{nom}@example.invalid')
        inst = Installation.objects.create(company=co, reference=f'CHT-ACSV-060-{nom}', client=cl, statut=statut,
                                           date_reception=reception)
        iv = Intervention.objects.create(company=co, installation=inst,
                                         type_intervention=Intervention.Type.POSE, created_by=u)
        r = api.post(f'/api/django/installations/interventions/{iv.pk}/ajouter-reserve/',
                     {'description': 'Onduleur mal fixé', 'creer_ticket': True}, format='json', **H)
        out = {'reserve_http': r.status_code}
        t = Ticket.objects.filter(company=co, installation=inst).first()
        if t is None:
            out['detail'] = str(getattr(r, 'data', ''))[:200]
            return out
        PieceConsommee.objects.create(company=co, ticket=t, produit=p, quantite=Decimal('1'), created_by=u)
        out.update({'ticket_couverture': t.couverture, 'sous_garantie': t.sous_garantie,
                    'equipement': t.equipement_id, 'couverture_calculee': t.couverture_calculee(),
                    'garantie_a_confirmer': t.garantie_chantier_a_confirmer})
        rf = api.post(f'/api/django/sav/tickets/{t.pk}/facturer/', {}, format='json', **H)
        t.refresh_from_db()
        out['facturer_http'] = rf.status_code
        out['facturer'] = dict(rf.data) if hasattr(rf, 'data') and isinstance(rf.data, dict) else None
        if t.facture_id_ext:
            f = Facture.objects.get(pk=t.facture_id_ext)
            out['facture_ht'] = str(f.montant_ht)
            out['lignes'] = [(lg.designation, str(lg.prix_unitaire)) for lg in f.lignes.all()]
        return out

    R = jeu('R', Installation.Statut.INSTALLE, None)
    T = jeu('T', Installation.Statut.RECEPTIONNE, today - timedelta(days=30))
    print({'R': R, 'T': T})
    temoin_ok = T.get('facturer_http') == 409
    defaut = R.get('facturer_http') == 201 and (R.get('facturer') or {}).get('couverture') == 'facturable' \
        and any(px != '0.00' for _, px in R.get('lignes', []))
    return {'repro': bool(temoin_ok and defaut), 'temoin_ok': temoin_ok, 'R': R, 'T': T}
