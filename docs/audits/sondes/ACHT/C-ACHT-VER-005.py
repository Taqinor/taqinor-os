# flake8: noqa  (sonde de contre-visite vérifie ACHT, rejouable par scripts/sonde.py — AMET93)
"""ACHT7 (jumeau oublié) : la ré-acceptation d'un devis dés-accepté (lead sorti de « Signé ») réactive le
chantier par `services.py::_reactiver_chantier_reaccepte`, qui réamorce les réservations sur l'ANCIENNE
nomenclature sans `realigner_nomenclature_si_divergente`. Entre-temps la ligne a été corrigée sur place
(devis « envoyé », QJR5) : ici par l'ORM, la route d'édition n'étant pas l'objet de la sonde. Acceptations et
sortie de « Signé » par les vraies routes. Transaction annulée."""
SONDE = {"constat": "C-ACHT-VER-005", "sha": "db8ca9670",
         "attendu": "V1 acceptée (PAN 10), lead sorti de Signé, ligne corrigée à 14, ré-acceptée : chantier actif mais nomenclature restée à 10"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    import apps.crm.stages as stages
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    co = Company.objects.create(nom='Sonde ACHT VER-002', slug='sonde-acht-ver-002')
    u = get_user_model().objects.create_user(username='sonde-acht-ver-002', password='x', company=co,
                                             role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Panneau', sku='SONDE-ACHT-002', prix_vente=Decimal('100'),
                               prix_achat=Decimal('0'), quantite_stock=50)
    cl = Client.objects.create(company=co, nom='Site', prenom='VER002', email='sonde-acht-ver-002@example.invalid')
    lead = Lead.objects.create(company=co, nom='Site VER002', stage=stages.FOLLOW_UP)
    d = Devis.objects.create(company=co, reference=f"DEV-{timezone.now():%Y%m}-9702", client=cl, lead=lead,
                             statut=Devis.Statut.ENVOYE, date_envoi=timezone.now(), taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                              prix_unitaire=Decimal('100'))
    url_acc = f'/api/django/ventes/devis/{d.id}/accepter/'
    r1 = api.post(url_acc, {'nom': 'M. Client'}, format='json', HTTP_HOST='localhost')
    inst = Installation.objects.filter(devis=d, company=co).first()
    bom_1 = {li.get('produit_id'): li.get('quantite') for li in ((inst.bom if inst else None) or [])}
    r2 = api.patch(f'/api/django/crm/leads/{lead.id}/', {'stage': stages.FOLLOW_UP, 'confirme_recul': True},
                   format='json', HTTP_HOST='localhost')
    d.refresh_from_db()
    if inst:
        inst.refresh_from_db()
    annule_milieu = inst.annule if inst else None
    LigneDevis.objects.filter(devis=d, produit=p).update(quantite=Decimal('14'))
    r3 = api.post(url_acc, {'nom': 'M. Client'}, format='json', HTTP_HOST='localhost')
    chantiers = Installation.objects.filter(devis=d, company=co)
    inst = chantiers.first()
    bom_2 = {li.get('produit_id'): li.get('quantite') for li in ((inst.bom if inst else None) or [])}
    print(f'acc1={r1.status_code} bom1={bom_1} sortie={r2.status_code} devis_milieu={d.statut} '
          f'annule_milieu={annule_milieu} acc2={r3.status_code} chantiers={chantiers.count()} '
          f'annule={inst.annule if inst else None} bom2={bom_2} (attendu {p.id}: 14)')
    q = bom_2.get(p.id)
    return {'repro': bool(inst) and annule_milieu is True and not inst.annule and q is not None and float(q) == 10.0,
            'statuts': [r1.status_code, r2.status_code, r3.status_code], 'annule_milieu': annule_milieu,
            'bom1': bom_1, 'bom2': bom_2, 'chantiers': chantiers.count()}
