# flake8: noqa  (sonde de contre-visite vérifie ACHT, rejouable par scripts/sonde.py — AMET93)
"""ACHT26 : AteliersPage envoie resultat='conforme' / 'echec' alors que le serveur n'accepte que
pass / fail / en_attente ; qcBloque de l'écran (null ou 'echec') est faux sur 'en_attente' : la case
« Forcer » n'apparaît jamais et le serveur refuse la clôture. Charges exactes de l'écran. Transaction annulée."""
SONDE = {"constat": "C-ACHT-VER-006", "sha": "db8ca9670",
         "attendu": "POST controle-qualite {resultat: conforme} 400, résultats restés en_attente, terminer sans forcer refusé"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import (
        ControleQualiteItemModele, ControleQualiteModele, Kit, KitComposant, OrdreAssemblage)
    from apps.stock.models import Produit
    co = Company.objects.create(nom='Sonde ACHT VER-003', slug='sonde-acht-ver-003')
    u = get_user_model().objects.create_user(username='sonde-acht-ver-003', password='x', company=co, role_legacy='admin')
    coffret = Produit.objects.create(company=co, nom='Coffret', sku='SONDE-ACHT-003-C', prix_vente=Decimal('200'),
                                     prix_achat=Decimal('0'), quantite_stock=0)
    disj = Produit.objects.create(company=co, nom='Disjoncteur', sku='SONDE-ACHT-003-D', prix_vente=Decimal('20'),
                                  prix_achat=Decimal('0'), quantite_stock=100)
    kit = Kit.objects.create(company=co, nom='KA', produit_compose=coffret)
    KitComposant.objects.create(kit=kit, produit=disj, quantite=1)
    modele = ControleQualiteModele.objects.create(company=co, kit=kit, active=True)
    item = ControleQualiteItemModele.objects.create(modele=modele, libelle='Serrage', ordre=1)
    ordre = OrdreAssemblage.objects.create(company=co, reference='ASM-SONDE-003', kit=kit, quantite=1,
                                           statut=OrdreAssemblage.Statut.EN_COURS)
    api = APIClient()
    api.force_authenticate(u)
    base = f'/api/django/installations/ordres-assemblage/{ordre.id}'
    g = api.get(f'{base}/controle-qualite/', HTTP_HOST='localhost')
    r_qc = api.post(f'{base}/controle-qualite/{item.id}/', {'resultat': 'conforme'}, format='json', HTTP_HOST='localhost')
    g2 = api.get(f'{base}/controle-qualite/', HTTP_HOST='localhost')
    donnees = g2.data
    if isinstance(donnees, dict):
        donnees = donnees.get('results') or donnees.get('items') or donnees.get('controles') or []
    resultats = [c.get('resultat') for c in donnees] if isinstance(donnees, list) else None
    qc_bloque_ecran = any(x is None or x == 'echec' for x in resultats) if resultats is not None else None
    r_t = api.post(f'{base}/terminer/', {'quantite_produite': '1'}, format='json', HTTP_HOST='localhost')
    ordre.refresh_from_db()
    print(f'get={g.status_code} qc(conforme)={r_qc.status_code} {getattr(r_qc, "data", None)} resultats={resultats} '
          f'qcBloque_ecran={qc_bloque_ecran} terminer={r_t.status_code} {getattr(r_t, "data", None)} statut={ordre.statut}')
    return {'repro': r_qc.status_code == 400 and qc_bloque_ecran is False and r_t.status_code >= 400,
            'qc': r_qc.status_code, 'resultats': resultats, 'qcBloque_ecran': qc_bloque_ecran,
            'terminer': r_t.status_code, 'statut': ordre.statut}
