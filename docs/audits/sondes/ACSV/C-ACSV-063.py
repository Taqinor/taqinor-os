# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K63 (part NON couverte par AAPV31 / D-AAPV-3) — la consommation F11 d'une intervention planifiée depuis un
ticket SAV hors garantie ne rejoint jamais la facture du ticket. Chantier SANS devis (aucune nomenclature :
le pré-remplissage F11, objet d'AAPV31, est neutralisé), réceptionné il y a 6 ans, onduleur hors garantie,
aucun contrat. Vraies routes : planifier-intervention, ajouter-ligne-consommation (fusible hors nomenclature,
justifié), valider-consommation, puis POST facturer ; `generer_facture_intervention` appelé aussi (l'autre
porte de facturation d'une intervention)."""
SONDE = {"constat": "C-ACSV-063", "sha": "f57951e87",
         "attendu": "repro si : stock du fusible 10 -> 9 (sorti par F11), facture du ticket sans ligne fusible, "
                    "et generer_facture_intervention refusée (intervention rattachée au ticket)",
         "modeles": ["sav.Ticket", "ventes.Facture", "installations.ConsommationLigne", "stock.MouvementStock"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention
    from apps.sav.models import Equipement, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    from apps.ventes.domain.facturation_ops import generer_facture_intervention
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 063', slug='sonde-acsv-063')
    u = get_user_model().objects.create_user(username='sonde-acsv-063', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    ond = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-063-O', prix_vente=Decimal('5000'),
                                 garantie_mois=12)
    fus = Produit.objects.create(company=co, nom='Fusible', sku='SONDE-ACSV-063-F', prix_vente=Decimal('80'),
                                 quantite_stock=10)
    cl = Client.objects.create(company=co, nom='Client', prenom='K63', email='acsv063@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-063', client=cl,
                                       statut=Installation.Statut.CLOTURE, date_reception=date(today.year - 6, 1, 15))
    eq = Equipement.objects.create(company=co, produit=ond, installation=inst, numero_serie='SN-ACSV-063',
                                   date_pose=date(today.year - 6, 1, 15))
    eq.recompute_garanties()
    eq.save()
    t = Ticket.objects.create(company=co, reference='SAV-ACSV-063', client=cl, installation=inst, equipement=eq,
                              type=Ticket.Type.CORRECTIF, created_by=u, date_ouverture=today)
    obs = {'couverture_calculee': t.couverture_calculee()}
    rp = api.post(f'/api/django/sav/tickets/{t.pk}/planifier-intervention/', {}, format='json', **H)
    obs['planifier_http'] = rp.status_code
    if rp.status_code != 201:
        return {'repro': False, 'obs': obs, 'detail': str(rp.data)[:300]}
    iv = Intervention.objects.get(pk=rp.data['intervention_id'])
    obs['intervention'] = {'type': iv.type_intervention, 'ticket_id': iv.ticket_id}
    base = f'/api/django/installations/interventions/{iv.pk}/'
    rl = api.post(base + 'ajouter-ligne-consommation/', {'designation': 'Fusible', 'produit': fus.pk,
                                                       'quantite_utilisee': 1, 'justification': 'fusible grillé'},
                  format='json', **H)
    obs['ligne_http'] = rl.status_code
    obs['lignes_semees_hors_fusible'] = iv.consommation.lignes.filter(hors_nomenclature=False).count()
    rv = api.post(base + 'valider-consommation/', {}, format='json', **H)
    obs['valider_http'] = rv.status_code
    fus.refresh_from_db()
    obs['stock_fusible'] = fus.quantite_stock
    rf = api.post(f'/api/django/sav/tickets/{t.pk}/facturer/', {}, format='json', **H)
    t.refresh_from_db()
    obs['facturer_http'] = rf.status_code
    obs['facturer'] = str(getattr(rf, 'data', ''))[:200]
    lignes = []
    if t.facture_id_ext:
        lignes = [(lg.designation, str(lg.quantite), str(lg.prix_unitaire))
                  for lg in Facture.objects.get(pk=t.facture_id_ext).lignes.all()]
    obs['lignes_facture_ticket'] = lignes
    try:
        f2 = generer_facture_intervention(intervention=iv, user=u)
        obs['facture_intervention'] = f'creee {f2.pk}'
    except Exception as exc:  # noqa
        obs['facture_intervention'] = f'refus {type(exc).__name__}: {exc}'[:160]
    print(obs)
    fusible_facture = any('Fusible' in d for d, _, _ in lignes)
    repro = (obs['valider_http'] == 200 and fus.quantite_stock == 9 and not fusible_facture
             and obs['facture_intervention'].startswith('refus'))
    obs['repro'] = bool(repro)
    return obs
