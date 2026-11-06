# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K61 — détection de récidive (XFSM15) seulement sur la porte manuelle. Chantier réceptionné il y a 6 ans,
onduleur hors garantie, aucun contrat ; une intervention DÉPANNAGE TERMINÉE il y a 10 jours. Trois portes
ouvrent un ticket sur le même équipement : (T) POST /sav/tickets/ (témoin, attendu récidive non facturable ->
facturer 403), (Q) QR public /public/sav/equipement/<token>/signaler/, (A) escalade d'une alarme onduleur.
Pour chaque ticket : est_recidive, non_facturable, puis POST facturer (1 pièce au prix de vente)."""
SONDE = {"constat": "C-ACSV-061", "sha": "f57951e87",
         "attendu": "repro si T : est_recidive True, facturer 403 ; ET Q ou A : est_recidive False, facturer 201 "
                    "facturable (pièce 5000)",
         "modeles": ["sav.Ticket", "ventes.Facture", "sav.AlarmeOnduleur"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention
    from apps.sav.models import AlarmeOnduleur, Equipement, PieceConsommee, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 061', slug='sonde-acsv-061')
    u = get_user_model().objects.create_user(username='sonde-acsv-061', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-061', prix_achat=Decimal('2000'),
                               prix_vente=Decimal('5000'), garantie_mois=12)
    cl = Client.objects.create(company=co, nom='Client', prenom='K61', email='acsv061@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-061', client=cl,
                                       statut=Installation.Statut.CLOTURE, date_reception=date(today.year - 6, 1, 15))
    eq = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie='SN-ACSV-061',
                                   date_pose=date(today.year - 6, 1, 15))
    eq.recompute_garanties()
    eq.save()
    Intervention.objects.create(company=co, installation=inst, type_intervention=Intervention.Type.DEPANNAGE,
                                statut=Intervention.Statut.TERMINEE, date_realisee=today - timedelta(days=10),
                                created_by=u)
    obs = {'garantie_eq': str(eq.date_fin_garantie_effective)}

    def lire(t, nom):
        t.refresh_from_db()
        PieceConsommee.objects.create(company=co, ticket=t, produit=p, quantite=Decimal('1'), created_by=u)
        rf = api.post(f'/api/django/sav/tickets/{t.pk}/facturer/', {}, format='json', **H)
        t.refresh_from_db()
        lignes = []
        if t.facture_id_ext:
            lignes = [str(lg.prix_unitaire) for lg in Facture.objects.get(pk=t.facture_id_ext).lignes.all()]
        obs[nom] = {'est_recidive': t.est_recidive, 'non_facturable': t.non_facturable,
                    'intervention_origine_id': t.intervention_origine_id, 'facturer_http': rf.status_code,
                    'couverture': (rf.data or {}).get('couverture') if isinstance(getattr(rf, 'data', None), dict) else None,
                    'lignes': lignes}

    # (T) porte manuelle
    r = api.post('/api/django/sav/tickets/', {'client': cl.pk, 'installation': inst.pk, 'equipement': eq.pk,
                                              'type': 'correctif', 'description': 'Onduleur en défaut (manuel)'},
                 format='json', **H)
    if r.status_code != 201:
        return {'repro': False, 'erreur_creation_manuelle': r.status_code, 'detail': str(r.data)[:300]}
    lire(Ticket.objects.get(pk=r.data['id']), 'T_manuel')
    # (Q) QR public
    tok = eq.ensure_public_token()
    rq = APIClient().post(f'/api/django/public/sav/equipement/{tok}/signaler/',
                          {'description': 'Onduleur en défaut (QR)'}, format='json', **H)
    tq = Ticket.objects.filter(company=co, description__startswith='Onduleur en défaut (QR)').first()
    obs['Q_http'] = rq.status_code
    if tq is not None:
        lire(tq, 'Q_qr')
    # (A) escalade d'alarme
    al = AlarmeOnduleur.objects.create(company=co, equipement=eq, code='F-061', libelle='Isolement')
    ra = api.post(f'/api/django/sav/alarmes-onduleur/{al.pk}/escalader/', {}, format='json', **H)
    al.refresh_from_db()
    obs['A_http'] = ra.status_code
    if al.ticket_id:
        lire(Ticket.objects.get(pk=al.ticket_id), 'A_alarme')
    print(obs)
    t = obs.get('T_manuel', {})
    temoin_ok = t.get('est_recidive') is True and t.get('facturer_http') == 403
    trous = [k for k in ('Q_qr', 'A_alarme') if k in obs and obs[k]['est_recidive'] is False
             and obs[k]['facturer_http'] == 201 and '5000.00' in obs[k]['lignes']]
    obs.update({'temoin_ok': temoin_ok, 'portes_sans_recidive': trous, 'repro': bool(temoin_ok and trous)})
    return obs
