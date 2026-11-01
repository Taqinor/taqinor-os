# flake8: noqa  (sonde PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K03 : la porte « acompte encaissé avant planification » (`installations/services.py::verifier_gate_acompte_planification`
→ `ventes/selectors_facturation.py::acompte_paye_pour_devis`) lit `statut == payee`. Un avoir TOTAL sur la facture
d'acompte (aucun encaissement) la bascule PAYÉE (`encaissements.py::recalculer_statut_paiement`) : la porte s'ouvre.
Vraie API (creer-avoir, PATCH chantier), société neuve, transaction annulée."""
SONDE = {"constat": "C-AARG-003", "sha": "56d5b623a",
         "attendu": "réglage ON, acompte 3 000 émis, 0 encaissé, avoir total → planification toujours refusée (409)",
         "modeles": ["ventes.Facture", "ventes.Avoir", "ventes.Paiement", "installations.Installation"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.ventes.models import Devis, Facture
    from apps.installations.models import Installation
    from apps.installations.services import create_installation_from_devis, verifier_gate_acompte_planification
    from apps.parametres.models import CompanyProfile
    co = Company.objects.create(nom='Sonde AARG 003', slug='sonde-aarg-003')
    u = get_user_model().objects.create_user(username='sonde_aarg_003', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='AARG003', email='sonde-aarg-003@example.invalid')
    lead = Lead.objects.create(company=co, nom='Client', prenom='AARG003', stage='SIGNED')
    dv = Devis.objects.create(company=co, reference='DEV-SONDE-AARG-003', client=cl, lead=lead,
                              statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    inst, _ = create_installation_from_devis(dv, u, co)
    Installation.objects.filter(pk=inst.pk).update(statut=Installation.Statut.MATERIEL_COMMANDE)
    inst.refresh_from_db()
    profil = CompanyProfile.get(co)
    profil.exiger_acompte_avant_planification = True
    profil.save(update_fields=['exiger_acompte_avant_planification'])
    fa = Facture.objects.create(company=co, devis=dv, client=cl, reference='FAC-SONDE-AARG-003',
                                type_facture=Facture.TypeFacture.ACOMPTE, statut=Facture.Statut.EMISE,
                                taux_tva=Decimal('20'), montant_ht=Decimal('2500'), montant_tva=Decimal('500'),
                                montant_ttc=Decimal('3000'), date_emission=timezone.now().date())
    gate_avant = verifier_gate_acompte_planification(inst)
    api = APIClient()
    api.force_authenticate(u)
    r_avoir = api.post(f'/api/django/ventes/factures/{fa.id}/creer-avoir/',
                       {'type': 'correction', 'motif': 'annulation commerciale'}, format='json')
    fa = Facture.objects.get(pk=fa.pk)
    gate_apres = verifier_gate_acompte_planification(inst)
    r_plan = api.patch(f'/api/django/installations/chantiers/{inst.id}/',
                       {'statut': Installation.Statut.PLANIFIE}, format='json')
    inst.refresh_from_db()
    obs = {'gate_avant_avoir': gate_avant, 'http_avoir': r_avoir.status_code,
           'facture_statut': fa.statut, 'montant_paye': str(fa.montant_paye), 'avoirs_total': str(fa.avoirs_total),
           'montant_du': str(fa.montant_du), 'gate_apres_avoir': gate_apres,
           'http_planifier': r_plan.status_code, 'chantier_statut': inst.statut,
           'celery': list(ctx.get('celery') or [])[:5]}
    print(obs)
    obs['repro'] = (gate_avant is not None and gate_apres is None and fa.montant_paye == 0
                    and inst.statut == Installation.Statut.PLANIFIE)
    return obs
