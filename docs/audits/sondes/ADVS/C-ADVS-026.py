# flake8: noqa  (sonde de vérification C-L5-1, rejouable par scripts/sonde.py)
"""C-L5-1 — « Refuser » (POST /ventes/devis/<id>/refuser/) lit le devis par `get_object()` SANS verrou, contrôle
« envoyé », puis `devis.save(update_fields=[statut…])`. On rejoue en séquence l'entrelacement réel : l'acceptation
du client (`accept_devis(user=None)`, commitée dans son savepoint) s'insère entre le contrôle et l'écriture
(`valider_corps` de la vue patché pour la déclencher). Relevé : réponse, statut final, aval de l'acceptation
(signature, chantier, étape du lead). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-026", "sha": "1dfa7986c",
         "attendu": "refus relu sous verrou → 409 statut, devis accepté (défaut : 200, « refusé » posé sur une vente signée, aval vivant)",
         "modeles": ["ventes.Devis", "ventes.DevisSignature", "installations.Installation", "crm.Lead"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, DevisSignature, LigneDevis
    from apps.ventes.services import accept_devis
    from apps.ventes.views import devis_cycle
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 026', slug='sonde-advs-026')
    u = U.objects.create_user(username='sonde-advs-026', password='x', role_legacy='admin', company=c)
    lead = Lead.objects.create(company=c, nom='Course', prenom='Refus', telephone='+212600002600', ville='Casablanca',
                               email='sonde-advs-026@example.invalid')
    cl = Client.objects.create(company=c, nom='Course', prenom='Refus', email='sonde-advs-026@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS026-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS026-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    d = Devis.objects.create(company=c, reference='DEV-ADVS026-01', client=cl, lead=lead, statut='envoye',
                             taux_tva=Decimal('20'), created_by=u)
    LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('12'),
                              prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
    LigneDevis.objects.create(devis=d, produit=ond, designation=ond.nom, quantite=Decimal('1'),
                              prix_unitaire=ond.prix_vente, remise=Decimal('0'), ordre=1)
    api = APIClient()
    api.force_authenticate(u)
    obs = {}
    vrai = devis_cycle.valider_corps
    inter = {}

    def entrelace(request, schema):
        res = vrai(request, schema)
        if schema is devis_cycle.D.RefuserRequest and 'fait' not in inter:
            inter['fait'] = True
            try:
                with transaction.atomic():
                    acc = accept_devis(devis=Devis.objects.get(pk=d.pk), user=None, nom='Client Signataire',
                                       consentement=True, ip='203.0.113.7')
                inter['acceptation_inseree'] = acc.statut
            except Exception as e:
                inter['acceptation_inseree'] = repr(e)[:200]
        return res

    with mock.patch.object(devis_cycle, 'valider_corps', side_effect=entrelace):
        try:
            with transaction.atomic():
                r = api.post(f'/api/django/ventes/devis/{d.id}/refuser/', {}, format='json', HTTP_HOST='localhost')
            j = json.loads(r.content.decode() or '{}')
            obs['refuser'] = [r.status_code, j.get('statut'), j.get('code'), j.get('detail')]
        except Exception as e:
            obs['refuser'] = repr(e)[:200]
    obs['entrelacement'] = inter
    d.refresh_from_db()
    lead.refresh_from_db()
    obs['devis_final'] = {'statut': d.statut, 'date_acceptation': str(d.date_acceptation), 'date_refus': str(d.date_refus),
                          'accepte_par_nom': d.accepte_par_nom}
    obs['signature'] = DevisSignature.objects.filter(devis=d).count()
    try:
        from apps.installations.models import Installation
        obs['chantiers_vivants'] = list(Installation.objects.filter(devis=d, annule=False).values_list('statut', flat=True))
    except Exception as e:
        obs['chantiers_vivants'] = repr(e)[:160]
    obs['lead'] = {'stage': getattr(lead, 'stage', None), 'perdu': getattr(lead, 'perdu', None)}
    repro = bool(inter.get('acceptation_inseree') == 'accepte' and d.statut == 'refuse')
    return {'repro': repro, 'observe': obs}
