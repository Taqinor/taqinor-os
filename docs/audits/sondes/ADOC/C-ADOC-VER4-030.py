# flake8: noqa  (sonde de contre-visite « vérifie ADOC » 04/11, rejouable par scripts/sonde.py — AMET93)
"""ADOC143 (jumeau du refus) : `apps/portail/views.py::PaiementFacturePortailViewSet.rapprocher` ne traduit que
`AcompteAvantDelaiLegal` en 400 ; `apps/portail/services.py::rapprocher_paiement_facture` appelle
`ventes.services.enregistrer_paiement`, dont la porte AFAC9 `exiger_facture_encaissable` lève
`FactureNonEncaissable` (ValueError, non traduite par `core/exceptions.py`) pour une facture ANNULÉE dont
`montant_exigible` reste le TTC. Scénario : PaiementFacturePortail INITIÉ, la facture est annulée, un responsable
rapproche. Chaîne API réelle. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADOC-VER4-030", "sha": "c38868a62",
         "attendu": "POST paiements-facture-portail/<id>/rapprocher/ sur une facture ANNULÉE → 500 (FactureNonEncaissable non traduite) ; paiement toujours INITIÉ, 0 Paiement (rollback) ; attendu sain : 400 nommé (motif AFAC9) comme le refus loi 31-08",
         "modeles": ["authentication.Company", "portail.PaiementFacturePortail", "facturation.Facture",
                     "facturation.Paiement", "ventes.Devis"]}


def sonde(ctx):
    from decimal import Decimal
    from rest_framework.test import APIClient
    from authentication.models import Company, CustomUser
    from apps.crm.models import Client
    from apps.facturation.models import Facture, Paiement
    from apps.portail.models import PaiementFacturePortail
    from apps.ventes.models import Devis
    co = Company.objects.create(nom='Sonde ADOC-VER4-030', slug='sonde-adoc-ver4-030')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER4-030', email='ver4-030@example.invalid')
    devis = Devis.objects.create(company=co, reference='DEV-SONDE-VER4-030', client=cl,
                                 statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    f = Facture.objects.create(company=co, reference='FAC-SONDE-VER4-030', client=cl, devis=devis,
                               statut=Facture.Statut.EMISE, montant_ht=Decimal('1000.00'),
                               montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'),
                               taux_tva=Decimal('20'))
    p = PaiementFacturePortail.objects.create(company=co, facture_id=f.id, montant=Decimal('1200.00'),
                                              methode=PaiementFacturePortail.Methode.VIREMENT,
                                              statut=PaiementFacturePortail.Statut.INITIE)
    Facture.objects.filter(pk=f.pk).update(statut=Facture.Statut.ANNULEE)
    f.refresh_from_db()
    exigible = str(f.montant_exigible)
    resp = CustomUser.objects.create_user(username='sonde-ver4-030-resp', password='motdepasse-test-1234',
                                          company=co, role_legacy='responsable')
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(user=resp)
    r = api.post(f'/api/django/portail/paiements-facture-portail/{p.id}/rapprocher/', {}, format='json',
                 HTTP_HOST='localhost')
    corps = None
    try:
        corps = r.json()
    except Exception:
        corps = (r.content or b'')[:200].decode('utf-8', 'replace')
    p.refresh_from_db()
    obs = {'http': r.status_code, 'corps': corps, 'facture_statut': f.statut, 'montant_exigible': exigible,
           'paiement_statut': p.statut, 'paye_le': str(p.paye_le),
           'nb_paiements': Paiement.objects.filter(facture_id=f.id).count()}
    print(f'obs={obs}')
    return {'repro': r.status_code == 500 and p.statut == PaiementFacturePortail.Statut.INITIE, **obs}
