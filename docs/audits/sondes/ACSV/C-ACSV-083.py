# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""T4 — prêt d'équipement (loaner) : le ticket se clôt / s'annule / se fusionne avec le prêt dehors.
Vraies routes : `sav/tickets/<id>/prets-equipement/` (POST), `demarrer|resoudre|cloturer|annuler|fusionner`,
`prets-equipement/<pid>/retourner/`.
(C) ticket avec prêt EN_COURS -> démarrer/résoudre/clôturer : 200 sans avertissement ? prêt toujours en_cours ?
(F) doublon D avec prêt fusionné dans P -> le prêt reste sur D (annulé) ?
(A) ticket avec prêt annulé -> 200 ?
Contournement : le prêt d'un ticket clôturé / d'un doublon reste-t-il retournable ?
(T) témoin de la famille de garde : clôture refusée (409) tant qu'une INTERVENTION est ouverte (YSERV2)."""
SONDE = {"constat": "C-ACSV-083", "sha": "7f4ba787d",
         "attendu": "repro si C : cloturer 200 et prêt en_cours ; F : principal 0 prêt ; témoin : 409 intervention ouverte",
         "modeles": ["sav.Ticket", "sav.PretEquipement", "stock.MouvementStock", "installations.Intervention"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention
    from apps.sav.models import PretEquipement, Ticket
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 083', slug='sonde-acsv-083')
    u = get_user_model().objects.create_user(username='sonde-acsv-083', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur de prêt', sku='SONDE-ACSV-083',
                               prix_achat=Decimal('2000'), prix_vente=Decimal('5000'), quantite_stock=5)
    cl = Client.objects.create(company=co, nom='Client', prenom='T4', email='acsv083@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-083', client=cl,
                                       statut=Installation.Statut.RECEPTIONNE,
                                       date_reception=today - timedelta(days=30))

    def ticket(ref):
        return Ticket.objects.create(company=co, reference=ref, client=cl, installation=inst,
                                     type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.NOUVEAU,
                                     description='Onduleur en réparation fournisseur', created_by=u)

    def preter(t):
        r = api.post(f'/api/django/sav/tickets/{t.pk}/prets-equipement/',
                     {'produit': p.pk, 'date_retour_prevue': str(today + timedelta(days=14)),
                      'numero_serie': f'LOAN-{t.reference}'}, format='json', **H)
        return r.status_code, (r.data.get('id') if r.status_code == 201 else str(r.data)[:200])

    def post(t, action, body=None):
        r = api.post(f'/api/django/sav/tickets/{t.pk}/{action}/', body or {}, format='json', **H)
        return r.status_code

    # C — clôture avec prêt dehors
    tC = ticket('SAV-083-C')
    pretC = preter(tC)
    C = {'preter': pretC, 'stock_apres_pret': Produit.objects.get(pk=p.pk).quantite_stock,
         'demarrer': post(tC, 'demarrer'), 'resoudre': post(tC, 'resoudre'), 'cloturer': post(tC, 'cloturer')}
    tC.refresh_from_db()
    C['ticket_statut'] = tC.statut
    if pretC[0] == 201:
        C['pret_statut'] = PretEquipement.objects.get(pk=pretC[1]).statut
        rr = api.post(f'/api/django/sav/tickets/{tC.pk}/prets-equipement/{pretC[1]}/retourner/', {}, format='json', **H)
        C['contournement_retour_sur_ticket_clos'] = rr.status_code

    # A — annulation avec prêt dehors
    tA = ticket('SAV-083-A')
    pretA = preter(tA)
    A = {'preter': pretA, 'annuler': post(tA, 'annuler', {'motif': 'client injoignable'})}
    if pretA[0] == 201:
        A['pret_statut'] = PretEquipement.objects.get(pk=pretA[1]).statut

    # F — fusion : le prêt du doublon
    tP = ticket('SAV-083-P')
    tD = ticket('SAV-083-D')
    pretD = preter(tD)
    F = {'preter_doublon': pretD, 'fusion': post(tP, 'fusionner', {'doublon_id': tD.pk})}
    tD.refresh_from_db()
    F['doublon_annule'] = tD.annule
    F['prets_principal'] = PretEquipement.objects.filter(ticket=tP).count()
    F['prets_doublon'] = PretEquipement.objects.filter(ticket=tD).count()
    if pretD[0] == 201:
        rr = api.post(f'/api/django/sav/tickets/{tD.pk}/prets-equipement/{pretD[1]}/retourner/', {}, format='json', **H)
        F['contournement_retour_sur_doublon'] = rr.status_code

    # T — témoin : clôture refusée tant qu'une intervention liée est ouverte
    tT = ticket('SAV-083-T')
    post(tT, 'demarrer')
    post(tT, 'resoudre')
    Intervention.objects.create(company=co, installation=inst, ticket=tT,
                                type_intervention=Intervention.Type.DEPANNAGE, created_by=u)
    T = {'cloturer': post(tT, 'cloturer')}
    out = {'C': C, 'A': A, 'F': F, 'T': T,
           'stock_final': Produit.objects.get(pk=p.pk).quantite_stock}
    print(out)
    temoin_ok = T['cloturer'] == 409
    defaut = C['cloturer'] == 200 and C.get('pret_statut') == PretEquipement.Statut.EN_COURS \
        and F['prets_principal'] == 0 and F['doublon_annule']
    out.update({'temoin_ok': temoin_ok, 'repro': bool(temoin_ok and defaut)})
    return out
