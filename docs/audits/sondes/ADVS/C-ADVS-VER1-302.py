# flake8: noqa  (sonde de verification VER1, rejouable par scripts/sonde.py)
"""VER1-302 (ADVS32) — dés-acceptation : le ShareLink d'un devis accepté (suivi_prolonge_le posé à l'acceptation, expires_at
dépassé) redevient expirable : suivi_prolonge_le vide, is_valid faux ; les liens d'un autre devis restent prolongés ; la
ré-acceptation le prolonge de nouveau. repro=True = l'écart existe encore. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-030", "sha": "06ced8b1a",
         "attendu": "après dés-acceptation : suivi_prolonge_le vide, is_valid faux (défaut : lien prolongé encore valide)",
         "modeles": ["ventes.Devis", "ventes.ShareLink"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes import services
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde VER1 302', slug='sonde-ver1-302')
    u = U.objects.create_user(username='sonde-ver1-302', password='x', role_legacy='admin', company=c,
                              email='vendeur-ver1-302@example.invalid')
    cl = Client.objects.create(company=c, nom='Papier', prenom='Fatima', email='client-ver1-302@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='V302-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)

    def devis(n):
        d = Devis.objects.create(company=c, reference=f'DEV-V302-0{n}', client=cl, statut='envoye',
                                 taux_tva=Decimal('20'), created_by=u)
        LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('4'),
                                  prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
        return d
    obs = {}
    d1, d2 = devis(1), devis(2)
    l1, l2 = ShareLink.for_devis(d1), ShareLink.for_devis(d2)
    hier = timezone.now() - timedelta(days=1)
    try:
        with transaction.atomic():
            services.accept_devis(devis=d1, user=u, nom='Commercial', consentement=False, idempotent_reaccept=False)
            services.accept_devis(devis=d2, user=u, nom='Commercial', consentement=False, idempotent_reaccept=False)
    except Exception as e:
        return {'repro': True, 'observe': {'accept_exc': repr(e)[:300]}}
    ShareLink.objects.filter(pk__in=[l1.pk, l2.pk]).update(expires_at=hier)
    l1.refresh_from_db(); l2.refresh_from_db()
    obs['apres_acceptation'] = {'l1_prolonge': l1.suivi_prolonge_le is not None, 'l1_valide': l1.is_valid,
                                'l2_prolonge': l2.suivi_prolonge_le is not None}
    with transaction.atomic():
        services.annuler_acceptation(devis=d1, user=u, motif='sonde')
    l1.refresh_from_db(); l2.refresh_from_db(); d1.refresh_from_db()
    obs['service'] = {'statut': d1.statut, 'l1_suivi_prolonge_le': str(l1.suivi_prolonge_le), 'l1_valide': l1.is_valid,
                      'l2_inchange_prolonge': l2.suivi_prolonge_le is not None}
    with transaction.atomic():
        services.accept_devis(devis=d1, user=u, nom='Commercial', consentement=False, idempotent_reaccept=False)
    l1.refresh_from_db()
    obs['reacceptation'] = {'l1_reprolonge': l1.suivi_prolonge_le is not None}
    ecart = bool(l1.suivi_prolonge_le is None and False)
    ecart = bool(obs['service']['l1_suivi_prolonge_le'] != 'None' or obs['service']['l1_valide']
                 or not obs['service']['l2_inchange_prolonge'] or not obs['reacceptation']['l1_reprolonge']
                 or not obs['apres_acceptation']['l1_prolonge'])
    return {'repro': ecart, 'observe': obs}
