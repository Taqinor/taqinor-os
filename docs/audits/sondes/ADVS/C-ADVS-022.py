# flake8: noqa  (sonde de vérification C-L3-1, rejouable par scripts/sonde.py)
"""C-L3-1 — paire de gammes (source « Essentielle » + sœur « Premium » née brouillon, `creer_variante_gamme`) ;
le vendeur envoie la SOURCE par l'API réelle (`share-link {envoi, gamme_envoi: les_deux}`) ; le client lit
`/public/proposal/<jeton source>/data/` : le bloc `gammes` sert-il la sœur BROUILLON (prix, comparatif, lien) ? le
GET crée-t-il un ShareLink sur la sœur ? le lien servi s'ouvre-t-il (404 attendu sur un brouillon au jeton client) ?
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-022", "sha": "1dfa7986c",
         "attendu": "aucune gamme brouillon servie, aucun ShareLink créé par la lecture (défaut : sœur brouillon servie, lien +1, 404)",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.LigneDevis"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    from apps.ventes.services import creer_variante_gamme
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 022', slug='sonde-advs-022')
    u = U.objects.create_user(username='sonde-advs-022', password='x', role_legacy='responsable', company=c)
    cl = Client.objects.create(company=c, nom='Gamme', prenom='Salma', email='sonde-advs-022@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau 550W', sku='ADVS022-P', prix_vente=Decimal('2000'),
                                 prix_achat=Decimal('1200'), quantite_stock=50)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau 5kW', sku='ADVS022-O', prix_vente=Decimal('9000'),
                                 prix_achat=Decimal('6000'), quantite_stock=50)
    src = Devis.objects.create(company=c, reference='DEV-ADVS022-01', client=cl, statut='brouillon', created_by=u)
    LigneDevis.objects.create(devis=src, produit=pan, designation=pan.nom, quantite=Decimal('10'),
                              prix_unitaire=Decimal('2000'), remise=Decimal('0'))
    LigneDevis.objects.create(devis=src, produit=ond, designation=ond.nom, quantite=Decimal('1'),
                              prix_unitaire=Decimal('9000'), remise=Decimal('0'))
    obs = {}
    try:
        with transaction.atomic():
            soeur = creer_variante_gamme(src, 'Premium', user=u)
    except Exception as e:
        return {'repro': False, 'observe': {'creer_variante_err': repr(e)[:300]}}
    src.refresh_from_db()
    # la sœur « Premium » coûte plus : on monte le prix de ses panneaux
    LigneDevis.objects.filter(devis=soeur, produit=pan).update(prix_unitaire=Decimal('2600'))
    soeur.refresh_from_db()
    api = APIClient()
    api.force_authenticate(u)
    pub = APIClient()

    def appel(client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
            try:
                return r.status_code, json.loads(brut.decode('utf-8', 'replace'))
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return repr(e)[:200], {}

    with mock.patch('apps.ventes.public_views._notify_open'):
        s, rs = appel(api, 'post', f'/api/django/ventes/devis/{src.id}/share-link/',
                      {'envoi': True, 'gamme_envoi': 'les_deux'})
        obs['envoi_source'] = s
        src.refresh_from_db()
        soeur.refresh_from_db()
        obs['statuts_apres_envoi'] = {'source': src.statut, 'soeur': soeur.statut,
                                      'soeur_envoi': (soeur.etude_params or {}).get('gamme', {}).get('envoi')
                                      if isinstance((soeur.etude_params or {}).get('gamme'), dict) else None}
        link = ShareLink.objects.filter(devis=src, revoque_le__isnull=True).order_by('-id').first()
        if link is None:
            return {'repro': False, 'observe': obs}
        n0 = ShareLink.objects.filter(devis=soeur).count()
        s, lu = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        n1 = ShareLink.objects.filter(devis=soeur).count()
        g = lu.get('gammes')
        obs['lecture_client'] = s
        obs['gammes_servies'] = None if not g else {
            'courante': g.get('courante'),
            'soeur': {k: (g.get('soeur') or {}).get(k) for k in ('nom', 'reference', 'total_ttc', 'ecart_ttc',
                                                                   'proposition_path')},
            'comparatif_n': len(g.get('comparatif') or [])}
        obs['sharelinks_soeur_avant_apres_GET'] = [n0, n1]
        nouveau = ShareLink.objects.filter(devis=soeur).order_by('-id').first()
        if nouveau is not None:
            obs['lien_soeur'] = {'sections': nouveau.sections, 'otp_lecture': nouveau.otp_lecture,
                                 'niveau': getattr(nouveau, 'niveau', None)}
            s2, lu2 = appel(pub, 'get', f'/api/django/public/proposal/{nouveau.token}/data/')
            obs['ouverture_lien_soeur'] = [s2, lu2.get('detail')]
    repro = bool(g and soeur.statut == 'brouillon' and (g.get('soeur') or {}).get('reference') == soeur.reference)
    return {'repro': repro, 'observe': obs}
