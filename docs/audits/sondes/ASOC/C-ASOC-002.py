# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K02 — un abonné du bus ignore un module désinstallé. Société R : `desactiver_module(R, 'installations')`
(Paramètres -> Applications), puis devis de 10 panneaux accepté par la vraie route
`POST ventes/devis/<id>/accepter/`. Relevé : chantiers du devis, réservations actives, disponible stock lu
par le sélecteur, `module_actif`. (T) société témoin, module actif : même geste -> 1 chantier, 10 réservés."""
SONDE = {"constat": "C-ASOC-002", "sha": "c514bd8ba",
         "attendu": "repro si R : module inactif ET chantier créé (1) + 10 réservés ; T : 1 chantier, 10 réservés",
         "modeles": ["ventes.Devis", "installations.Installation", "installations.StockReservation", "core.ModuleToggle"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation, StockReservation
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from core import feature_flags
    U = get_user_model()
    obs = {}

    def scenario(tag, desinstaller):
        c = Company.objects.create(nom=f'Sonde ASOC 002 {tag}', slug=f'sonde-asoc-002-{tag.lower()}')
        u = U.objects.create_user(username=f'sonde-asoc-002-{tag.lower()}', password='x', role_legacy='admin',
                                  company=c)
        pan = Produit.objects.create(company=c, nom='Panneau 710W', sku=f'ASOC002-PAN-{tag}', prix_vente=Decimal('1000'),
                                     prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=50)
        res = {}
        if desinstaller:
            try:
                res['desactiver'] = feature_flags.desactiver_module(c, 'installations', user=u)
            except Exception as e:
                res['desactiver'] = repr(e)[:200]
        res['module_actif'] = feature_flags.module_actif(c, 'installations')
        lead = Lead.objects.create(company=c, nom='Affaire', prenom=tag, telephone='+21260000200' + str(len(tag)),
                                   ville='Rabat', email=f'asoc002-{tag.lower()}@example.invalid',
                                   type_installation='residentiel')
        cl = Client.objects.create(company=c, nom='Affaire', prenom=tag, email=f'asoc002-{tag.lower()}@example.invalid')
        d = Devis.objects.create(company=c, reference=f'DEV-ASOC002-{tag}', client=cl, lead=lead, statut='envoye',
                                 date_envoi=timezone.now(), taux_tva=Decimal('20'), mode_installation='residentiel',
                                 created_by=u)
        LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('10'),
                                  prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
        api = APIClient()
        api.force_authenticate(u)
        try:
            with transaction.atomic():
                r = api.post(f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'}, format='json',
                             HTTP_HOST='localhost')
            res['accepter_http'] = r.status_code
        except Exception as e:
            res['accepter_http'] = repr(e)[:200]
        d.refresh_from_db()
        res['devis_statut'] = d.statut
        insts = Installation.objects.filter(devis=d)
        res['chantiers'] = insts.count()
        res['reserve_actif'] = str(sum(StockReservation.objects.filter(installation__in=insts, active=True)
                                       .values_list('quantite', flat=True)) or 0)
        try:
            from apps.stock.services import reserved_quantities
            res['reserved_quantities_sel'] = str((reserved_quantities(c) or {}).get(pan.pk, 0))
        except Exception as e:
            res['reserved_quantities_sel'] = repr(e)[:160]
        return res

    obs['R'] = scenario('R', True)
    obs['T'] = scenario('T', False)
    print(obs)
    r, t = obs['R'], obs['T']
    temoin_ok = t['accepter_http'] == 200 and t['chantiers'] == 1
    defaut = (r['module_actif'] is False and r['accepter_http'] == 200 and r['chantiers'] >= 1)
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
