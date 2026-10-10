# flake8: noqa  (sonde de session reprise telle quelle : style libre, logique validee le 09/10)
"""Sonde de la session audit-méthode du 09/10/2026 (R3), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
"""
SONDE = {
    'constat': 'C-AMET-010',
    'sha': 'f3716e3f0',
    'attendu': 'suggestions-bcf sert montant_total à un Commercial sans prix_achat_voir',
}


def sonde(ctx):
    from django.db import transaction
    class R(Exception):
        pass
    _CELERY = _CELERY_CALLS = ctx['celery']
    from datetime import timedelta
    from decimal import Decimal
    from django.db import transaction
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit, LigneBonCommandeFournisseur
    U = get_user_model()
    out = []
    try:
        with transaction.atomic():
            perms_com = dict(CANONICAL_SYSTEM_ROLES)['Commercial']
            out.append('Commercial canonical has prix_achat_voir: %s' % ('prix_achat_voir' in perms_com))
            # pick a company that has an active user and a fournisseur
            u0 = None
            if u0 is None:
                u0 = U.objects.filter(is_active=True, company__isnull=False).order_by('id').first()
            co = u0.company
            out.append('company id=%s' % co.id)
            role = Role.objects.filter(company=co, nom='Commercial').first()
            created_role = False
            if role is None:
                role = Role.objects.create(company=co, nom='Commercial', permissions=perms_com); created_role = True
            out.append('Commercial role existed: %s; role has prix_achat_voir: %s' % (not created_role, 'prix_achat_voir' in (role.permissions or [])))
            com = U.objects.filter(company=co, role=role, is_active=True).first()
            if com is None:
                com = U.objects.create_user(username='r3v2_probe_commercial', password='x', company=co, role=role)
                out.append('commercial user created in txn')
            else:
                out.append('existing active commercial user used')
            out.append('can_view_buy_prices=%s' % getattr(com, 'can_view_buy_prices', None))
            f = Fournisseur.objects.filter(company=co).first()
            if f is None:
                f = Fournisseur.objects.create(company=co, nom='R3V2 fournisseur')
            bcs = BonCommandeFournisseur.objects.filter(company=co, fournisseur=f, statut__in=['envoye','recu'], date_commande__gte=timezone.localdate()-timedelta(days=60))
            if not bcs.exists():
                bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, statut=BonCommandeFournisseur.Statut.ENVOYE, date_commande=timezone.localdate())
                p = Produit.objects.filter(company=co).first()
                LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=1, prix_achat_unitaire=Decimal('820'))
                out.append('BCF created in txn')
            api = APIClient(HTTP_HOST='localhost'); api.force_authenticate(com)
            for base in ('/api/django/stock/', '/api/django/achats/'):
                r = api.get(base + 'factures-fournisseur/suggestions-bcf/', {'fournisseur': f.id, 'montant': '900'})
                body = r.json() if 'json' in (r.get('Content-Type') or '') else None
                keys = sorted(body[0].keys()) if isinstance(body, list) and body else body if not isinstance(body, list) else []
                mt = [str(x.get('montant_total')) for x in body] if isinstance(body, list) else None
                out.append('%s -> %s keys=%s n=%s montant_total=%s' % (base, r.status_code, keys, len(body) if isinstance(body, list) else '-', mt[:2] if mt else mt))
            # control: same commercial on BCF list (ASTK10) to show prix masked there
            r2 = api.get('/api/django/stock/bons-commande-fournisseur/')
            b2 = r2.json(); rows = b2.get('results', b2) if isinstance(b2, dict) else b2
            import json as _j
            txt = _j.dumps(b2)
            out.append('control BCF list -> %s ; contains prix_achat_unitaire key: %s ; total_achat: %s' % (r2.status_code, '"prix_achat_unitaire"' in txt, '"total_achat"' in txt))
            # control: guard without param
            r3 = api.get('/api/django/stock/factures-fournisseur/suggestions-bcf/')
            out.append('no-param call (what the ASTK14 sweep does) -> %s' % r3.status_code)
            raise R()
    except R:
        pass
    print('\n'.join(out))
