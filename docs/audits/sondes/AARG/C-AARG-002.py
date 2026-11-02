# flake8: noqa  (sonde PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K02 : une facture PAYÉE annulée avec `garder_en_avance` (`domain/annulation_facture.py::annuler_facture`) voit
ses paiements détachés en avance client puis reçoit un avoir de contre-passation (trace old_value='payee').
Annuler cet avoir (`views/avoir.py::AvoirViewSet.annuler`) remet `statut = trace.old_value` sans recalcul et sans
rattacher l'avance : facture « payée » avec montant_paye 0 / montant_du 12 000, avance 12 000 toujours libre.
Fonctions réelles + vraie API, société neuve, transaction annulée."""
SONDE = {"constat": "C-AARG-002", "sha": "56d5b623a",
         "attendu": "après annulation de l'avoir miroir : statut cohérent avec le reste dû (pas « payée » à 12 000 dus) et l'avance rattachée ou refus",
         "modeles": ["ventes.Facture", "ventes.Avoir", "ventes.Paiement"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture, Paiement, Avoir
    from apps.ventes.domain.encaissements import enregistrer_paiement, recalculer_statut_paiement
    from apps.ventes.domain.annulation_facture import annuler_facture
    co = Company.objects.create(nom='Sonde AARG 002', slug='sonde-aarg-002')
    u = get_user_model().objects.create_user(username='sonde_aarg_002', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='AARG002', email='sonde-aarg-002@example.invalid')
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG-002', client=cl, statut='emise',
                               taux_tva=Decimal('20'), montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
                               montant_ttc=Decimal('12000'), date_emission=timezone.now().date())
    enregistrer_paiement(facture=f, montant=Decimal('12000'), mode='virement',
                         date_paiement=timezone.now().date(), user=u)
    recalculer_statut_paiement(f, user=u)
    f.refresh_from_db()
    statut_initial = f.statut
    annulee = annuler_facture(f, user=u, directive={'action': 'garder_en_avance'})
    avoir = getattr(annulee, 'avoir_annulation', None)
    f.refresh_from_db()
    statut_annulee = f.statut
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/ventes/avoirs/{avoir.id}/annuler/', {}, format='json')
    f = Facture.objects.get(pk=f.pk)
    avances = [(str(p.montant), p.statut_affectation) for p in
               Paiement.objects.filter(company=co, facture__isnull=True)]
    obs = {'statut_initial': statut_initial, 'statut_apres_annulation': statut_annulee,
           'avoir': avoir.reference if avoir else None, 'http_annuler_avoir': r.status_code,
           'statut_final': f.statut, 'montant_paye': str(f.montant_paye), 'montant_du': str(f.montant_du),
           'avances_libres': avances}
    print(obs)
    obs['repro'] = (r.status_code == 200 and f.statut == Facture.Statut.PAYEE
                    and Decimal(str(f.montant_du)) > 0)
    return obs
