# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K06 — abonné « best-effort » SANS point de sauvegarde dans la transaction d'acceptation.
Injection : une erreur BASE (`SELECT 1/0`) pendant l'arrêt de cadence.
(R) erreur posée sur `receivers_cadence.arreter_cadence` = chemin `devis_accepted` -> crm avance l'étape ->
`lead_stage_changed` -> `_arreter_cadence_on_stage_change` (try nu, pas d'atomic) ; vraie route
`POST ventes/devis/<id>/accepter/`. (T) même erreur posée sur `cadence_plan.arreter_cadence` = chemin
`_arreter_cadence_on_devis_accepted` -> `arreter_cadence_du_lead_id` (avec atomic, ADEV54) : doit passer."""
SONDE = {"constat": "C-ASOC-003", "sha": "c514bd8ba",
         "attendu": "repro si R : acceptation en échec (exception/500), devis non accepté, 0 chantier ; "
                    "T : 200, accepté, 1 chantier",
         "modeles": ["ventes.Devis", "installations.Installation", "crm.Lead"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ASOC 003', slug='sonde-asoc-003')
    u = U.objects.create_user(username='sonde-asoc-003', password='x', role_legacy='admin', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau 710W', sku='ASOC003-PAN', prix_vente=Decimal('1000'),
                                 prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=50)
    api = APIClient()
    api.force_authenticate(u)
    appels = []

    def boom(*a, **k):
        appels.append('boom')
        connection.cursor().execute('SELECT 1/0')

    def affaire(tag):
        lead = Lead.objects.create(company=c, nom='Affaire', prenom=tag, telephone='+21260000300' + tag[-1],
                                   ville='Rabat', email=f'asoc003-{tag.lower()}@example.invalid',
                                   type_installation='residentiel', stage=stages.QUOTE_SENT)
        cl = Client.objects.create(company=c, nom='Affaire', prenom=tag, email=f'asoc003-{tag.lower()}@example.invalid')
        d = Devis.objects.create(company=c, reference=f'DEV-ASOC003-{tag}', client=cl, lead=lead, statut='envoye',
                                 date_envoi=timezone.now(), taux_tva=Decimal('20'), mode_installation='residentiel',
                                 created_by=u)
        LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('4'),
                                  prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
        return lead, d

    def accepter(d, cible):
        del appels[:]
        res = {}
        try:
            with mock.patch(cible, boom):
                with transaction.atomic():
                    r = api.post(f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'}, format='json',
                                 HTTP_HOST='localhost')
            res['http'] = r.status_code
            if r.status_code >= 400:
                res['detail'] = r.content.decode('utf-8', 'replace')[:200]
        except Exception as e:
            res['http'] = 'exception'
            res['exception'] = (type(e).__name__ + ': ' + str(e))[:220]
        d.refresh_from_db()
        d.lead.refresh_from_db()
        res.update({'injections': len(appels), 'devis_statut': d.statut, 'lead_stage': d.lead.stage,
                    'chantiers': Installation.objects.filter(devis=d).count()})
        return res

    _l, dR = affaire('R1')
    obs = {'R': accepter(dR, 'apps.crm.receivers_cadence.arreter_cadence')}
    _l, dT = affaire('T2')
    obs['T'] = accepter(dT, 'apps.crm.cadence_plan.arreter_cadence')
    print(obs)
    r, t = obs['R'], obs['T']
    temoin_ok = t['http'] == 200 and t['devis_statut'] == 'accepte' and t['chantiers'] == 1 and t['injections'] >= 1
    defaut = r['injections'] >= 1 and (r['http'] != 200 or r['devis_statut'] != 'accepte' or r['chantiers'] == 0)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
