# flake8: noqa  (sonde de session reprise telle quelle : style libre, logique validee le 09/10)
"""Sonde de la session audit-méthode du 09/10/2026 (R3), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
"""
SONDE = {
    'constat': 'C-AMET-012',
    'sha': 'f3716e3f0',
    'attendu': "ordre d'assemblage : PATCH quantité 1→2 efface la ligne manuelle (2 → 1) ; 3 règles de lecture des règlements",
}


def sonde(ctx):
    from django.db import transaction
    class R(Exception):
        pass
    _CELERY = _CELERY_CALLS = ctx['celery']
    import json
    from decimal import Decimal
    from django.db import transaction
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import (Produit, Fournisseur, FactureFournisseur, PaiementFournisseur)
    from apps.installations.models_kitting import Kit, KitComposant, OrdreAssemblage, OrdreAssemblageLigne
    U = get_user_model(); out = []
    P = dict(CANONICAL_SYSTEM_ROLES)
    def mkuser(co, nom, perms, uname):
        role = Role.objects.create(company=co, nom=nom, permissions=perms)
        return U.objects.create_user(username=uname, password='x', company=co, role=role)
    def api(u):
        a = APIClient(HTTP_HOST='localhost'); a.force_authenticate(u); return a
    try:
        with transaction.atomic():
            ff = FactureFournisseur.objects.filter(paiements__isnull=False).select_related('company').first()
            if ff is not None:
                co = ff.company; out.append('using existing facture fournisseur with paiement')
            else:
                co = U.objects.filter(is_active=True, company__isnull=False).order_by('id').first().company
                f = Fournisseur.objects.filter(company=co).first() or Fournisseur.objects.create(company=co, nom='R3V2 f')
                ff = FactureFournisseur.objects.create(company=co, fournisseur=f, date_facture=timezone.localdate(), montant_ht=Decimal('100'), montant_tva=Decimal('20'), montant_ttc=Decimal('120'))
                PaiementFournisseur.objects.create(company=co, facture=ff, montant=Decimal('50'), date_paiement=timezone.localdate())
                out.append('facture + paiement created in txn')
            # --- claim 3b: three read rules ---
            u_prix = mkuser(co, 'R3V2 lecture prix', ['stock_voir', 'prix_achat_voir'], 'r3v2_prix')
            u_payer = mkuser(co, 'R3V2 payeur', ['stock_voir', 'achats_payer'], 'r3v2_payer')
            for lbl, u in (('stock_voir+prix_achat_voir', u_prix), ('stock_voir+achats_payer', u_payer)):
                a = api(u)
                r1 = a.get('/api/django/stock/paiements-fournisseur/')
                r2 = a.get('/api/django/stock/factures-fournisseur/%s/paiements/' % ff.id)
                r3 = a.get('/api/django/stock/factures-fournisseur/%s/' % ff.id)
                k3 = ('paiements' in r3.json()) if r3.status_code == 200 else None
                out.append('[%s] is_responsable=%s | /paiements-fournisseur/ -> %s | /factures-fournisseur/<id>/paiements/ -> %s | detail -> %s, nested paiements key=%s' % (lbl, u.is_responsable, r1.status_code, r2.status_code, r3.status_code, k3))
            # --- claim 3a/3c: Technicien responsable ---
            tr = mkuser(co, 'R3V2 Tech resp', P['Technicien responsable'], 'r3v2_techresp')
            out.append('TechResp menu_tier=%s is_admin_role=%s is_responsable=%s achats_commander=%s catalogue_prix_modifier=%s' % (tr.menu_tier, tr.is_admin_role, tr.is_responsable, tr.has_erp_permission('achats_commander'), tr.has_erp_permission('catalogue_prix_modifier')))
            a = api(tr)
            f0 = Fournisseur.objects.filter(company=co).first()
            r = a.post('/api/django/stock/produits/generer-bcf-reappro/', {'fournisseur_id': f0.id if f0 else None}, format='json')
            out.append('TechResp POST produits/generer-bcf-reappro/ -> %s %s' % (r.status_code, (r.json().get('detail') if r.status_code >= 400 and 'json' in (r.get('Content-Type') or '') else '')))
            pid = Produit.objects.filter(company=co).values_list('id', flat=True).first()
            r = a.post('/api/django/stock/produits/bulk/', {'action': 'set_price', 'ids': [pid], 'mode': 'percent', 'valeur': '0'}, format='json')
            out.append('TechResp POST produits/bulk set_price -> %s' % r.status_code)
            r = a.get('/api/django/stock/modeles-bcf/')
            out.append('TechResp GET modeles-bcf/ -> %s' % r.status_code)
            r = a.post('/api/django/stock/modeles-bcf/', {'nom': 'R3V2 modele'}, format='json')
            out.append('TechResp POST modeles-bcf/ -> %s' % r.status_code)
            r = a.post('/api/django/stock/bons-commande-fournisseur/', {'fournisseur': f0.id if f0 else None, 'lignes': []}, format='json')
            out.append('TechResp POST bons-commande-fournisseur/ (OCR import path) -> %s' % r.status_code)
            # --- claim 4: assembly order ---
            adm = U.objects.filter(company=co, is_active=True, role__permissions__contains=['roles_gerer']).first() or mkuser(co, 'R3V2 admin', P['Administrateur'], 'r3v2_admin')
            prods = list(Produit.objects.filter(company=co).order_by('id')[:3])
            kit = Kit.objects.filter(company=co, composants__isnull=False).first()
            if kit is None:
                kit = Kit.objects.create(company=co, nom='R3V2 kit', produit_compose=prods[0])
                KitComposant.objects.create(kit=kit, produit=prods[1], quantite=2)
                out.append('kit created in txn')
            a = api(adm)
            r = a.post('/api/django/installations/ordres-assemblage/', {'kit': kit.id, 'quantite': 1}, format='json')
            out.append('POST ordres-assemblage -> %s' % r.status_code)
            if r.status_code == 201:
                oid = r.json()['id']
                o = OrdreAssemblage.objects.get(pk=oid)
                def compte():
                    q = OrdreAssemblageLigne.objects.filter(ordre_id=oid)
                    return '%d lignes (%d kit, %d ajout)' % (q.count(), q.filter(origine='kit').count(), q.filter(origine='ajout').count())
                out.append('after create: %s, statut=%s' % (compte(), o.statut))
                r = a.post('/api/django/installations/ordre-assemblage-lignes/', {'ordre': oid, 'produit': prods[2].id, 'quantite': 3, 'designation': 'ajout manuel R3V2'}, format='json')
                out.append('POST manual line -> %s ; %s' % (r.status_code, compte()))
                r = a.patch('/api/django/installations/ordres-assemblage/%s/' % oid, {'quantite': 2}, format='json')
                out.append('PATCH quantite 1->2 -> %s ; %s' % (r.status_code, compte()))
                out.append('manual line still exists: %s' % OrdreAssemblageLigne.objects.filter(ordre_id=oid, designation='ajout manuel R3V2').exists())
            else:
                out.append('create body: %s' % str(r.content[:300]))
            raise R()
    except R:
        pass
    print('\n'.join(out))
