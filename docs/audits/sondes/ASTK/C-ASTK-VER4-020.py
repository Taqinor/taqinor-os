# flake8: noqa  (sonde de contre-visite « vérifie ASTK » 04/11, rejouable par scripts/sonde.py — AMET93)
"""ASTK56 + ASTK57 + ASTK59 + ASTK60 bout à bout, par l'API réelle : BCF « besoin chantier » (chantier_origine)
ligne 10 @ 60, réception de 12 avec la série S1 → confirmer (API) → provision GR/IR, série, réservation YPROC10 ;
puis annuler (API) et exécution des rappels on_commit enregistrés par l'annulation (le signal
`reception_fournisseur_annulee` part après commit ; la sonde tourne dans une transaction annulée, elle rejoue donc
elle-même les rappels). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASTK-VER4-020", "sha": "c38868a62",
         "attendu": "création 12 → 201 ; confirmer → 200, stock 10, quantite_appliquee 10, provision 600.00, série S1 en_stock, réservation 10 ; annuler → 200, 1 émission ; après rappels : provision ouverte absente, S1 retourne, réservation ≤ reçu net (0, inactive) ; rejeu du signal sans effet",
         "modeles": ["authentication.Company", "stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "installations.ReceptionNonFacturee", "installations.SerieEntrepot",
                     "installations.StockReservation", "installations.Installation"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import connection
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import SerieEntrepot, StockReservation
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    from apps.stock.models import (BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
                                   ReceptionFournisseur)
    from core.events import reception_fournisseur_annulee
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-VER4-020', slug='sonde-astk-ver4-020')
    u = U.objects.create_user(username='sonde-astk-ver4-020', password='x', company=co, role_legacy='admin')
    cable = Produit.objects.create(company=co, nom='Câble V4-020', sku='V4020-C', prix_vente=Decimal('10'),
                                   quantite_stock=100)
    pan = Produit.objects.create(company=co, nom='Panneau V4-020', sku='V4020-P', prix_vente=Decimal('100'),
                                 quantite_stock=0)
    cl = Client.objects.create(company=co, nom='Site', prenom='V4020', email='v4020@example.invalid')
    # Lead absent : la base de la pile locale n'a pas toutes les colonnes crm_lead (migrations en retard).
    from apps.installations.models import Installation
    inst = Installation.objects.create(company=co, reference='CH-V4020', client=cl,
                                       puissance_installee_kwc=Decimal('5.00'))
    f = Fournisseur.objects.create(company=co, nom='F V4-020')
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-V4020',
                                               chantier_origine=inst, statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=pan, quantite=10,
                                                    prix_achat_unitaire=Decimal('60'))
    api = APIClient()
    api.force_authenticate(u)
    url = '/api/django/stock/receptions-fournisseur/'
    r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 12,
                                                           'numeros_serie': ['S1']}]},
                 format='json', HTTP_HOST='localhost')
    etapes = {'creer': (r.status_code, r.data if r.status_code >= 400 else None)}
    if r.status_code != 201:
        return {'repro': True, 'etapes': etapes}
    rid = r.data['id']
    r = api.post(f'{url}{rid}/confirmer/', HTTP_HOST='localhost')
    etapes['confirmer'] = (r.status_code, r.data if r.status_code >= 400 else None)
    rec = ReceptionFournisseur.objects.get(pk=rid)
    pan.refresh_from_db()
    lr = rec.lignes.get()

    def _etat():
        prov = list(ReceptionNonFacturee.objects.filter(company=co, reception=rec, lettre=False)
                    .values_list('montant_provision', flat=True))
        s = SerieEntrepot.objects.filter(company=co, produit=pan, numero_serie='S1').first()
        resa = StockReservation.objects.filter(installation=inst, produit=pan).first()
        return ([str(x) for x in prov], getattr(s, 'statut', None),
                (resa.quantite, resa.active) if resa else None)

    apres_conf = {'stock': pan.quantite_stock, 'quantite_appliquee': lr.quantite_appliquee, 'etat': _etat()}
    emissions = []

    def _capter(sender, **kw):
        emissions.append([(l['produit'].pk, l['quantite_annulee']) for l in kw.get('lignes', [])])
    reception_fournisseur_annulee.connect(_capter)
    try:
        avant = len(connection.run_on_commit)
        r = api.post(f'{url}{rid}/annuler/', HTTP_HOST='localhost')
        etapes['annuler'] = (r.status_code, r.data if r.status_code >= 400 else None)
        rappels = list(connection.run_on_commit[avant:])
        for entree in rappels:
            entree[1]()
        lc.refresh_from_db()
        pan.refresh_from_db()
        apres_annul = {'stock': pan.quantite_stock, 'quantite_recue': lc.quantite_recue, 'etat': _etat(),
                       'emissions': list(emissions), 'nb_rappels': len(rappels)}
        reception_fournisseur_annulee.send(sender=ReceptionFournisseur, reception=rec, company=co, user=u,
                                           lignes=[])
        rejeu = _etat()
    finally:
        reception_fournisseur_annulee.disconnect(_capter)
    print(f'etapes={etapes} apres_conf={apres_conf} apres_annul={apres_annul} rejeu={rejeu}')
    sain = (etapes['confirmer'][0] == 200 and apres_conf['stock'] == 10 and apres_conf['quantite_appliquee'] == 10
            and apres_conf['etat'][0] == ['600.00'] and apres_conf['etat'][1] == 'en_stock'
            and etapes['annuler'][0] == 200 and len(apres_annul['emissions']) == 1
            and apres_annul['etat'][0] == [] and apres_annul['etat'][1] == 'retourne'
            and (apres_annul['etat'][2] is None or apres_annul['etat'][2][0] <= apres_annul['quantite_recue'])
            and rejeu == apres_annul['etat'])
    return {'repro': not sain, 'etapes': etapes, 'apres_conf': apres_conf, 'apres_annul': apres_annul,
            'rejeu': rejeu}
