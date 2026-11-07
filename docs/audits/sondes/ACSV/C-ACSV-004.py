# flake8: noqa  (sonde PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K04 — devis accepté par l'API -> chantier « Signé » ; avancé pas à pas jusqu'à « Installé » par le point
d'écriture unique `changer_statut_chantier(verifier_gates=False)` (cascade intégrale, gardes d'étape sautées) ->
jalons `appro` / `pose` atteints et publiés au portail. Puis RECUL d'un pas par la vraie route du kanban
(PATCH `installations/chantiers/<id>/` {statut: en_cours}), puis jusqu'à « Signé » (PATCH successifs, repli sur le
service si la route refuse). Relevé : JalonProjet(appro/pose).atteint et `portail.selectors.jalons_du_chantier`
(la ligne que lisent `ventes.selectors.devis_milestones` et « Mes chantiers »). (T) témoin : le recul depuis
« Réceptionné » défait bien le jalon RÉCEPTION (AARG46)."""
SONDE = {"constat": "C-ACSV-004", "sha": "f57951e87",
         "attendu": "repro si après recul à « En cours » le jalon pose reste atteint (interne + portail), et appro après recul à « Signé »",
         "modeles": ["installations.Installation", "installations.JalonProjet", "portail.JalonChantierPortail"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation, JalonProjet
    from apps.installations.services import changer_statut_chantier
    from apps.portail.selectors import jalons_du_chantier
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    S = Installation.Statut
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACSV 004', slug='sonde-acsv-004')
    u = U.objects.create_user(username='sonde-acsv-004', password='x', role_legacy='admin', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau 710W', sku='ACSV004-PAN', prix_vente=Decimal('1000'),
                                 prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=50)
    api = APIClient()
    api.force_authenticate(u)

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            try:
                return r.status_code, json.loads(r.content.decode('utf-8', 'replace') or '{}')
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return repr(e)[:200], {}

    def chantier(suffixe):
        lead = Lead.objects.create(company=c, nom='Jalons', prenom=suffixe, telephone='+21260000040' + suffixe[-1],
                                   ville='Rabat', email=f'acsv004-{suffixe}@example.invalid',
                                   type_installation='residentiel')
        cl = Client.objects.create(company=c, nom='Jalons', prenom=suffixe, email=f'acsv004-{suffixe}@example.invalid')
        d = Devis.objects.create(company=c, reference=f'DEV-ACSV004-{suffixe}', client=cl, lead=lead, statut='envoye',
                                 date_envoi=timezone.now(), taux_tva=Decimal('20'), mode_installation='residentiel',
                                 created_by=u)
        LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('10'),
                                  prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
        appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})
        return Installation.objects.filter(devis=d).first()

    def jalons(inst):
        interne = {j.phase: j.atteint for j in JalonProjet.objects.filter(installation=inst)
                   if j.phase in ('appro', 'pose', 'reception')}
        portail = {j.cle_phase: j.atteint for j in jalons_du_chantier(c, inst.id)
                   if j.cle_phase in ('appro', 'pose', 'reception')}
        return {'interne': interne, 'portail': portail}

    def avancer(inst, statuts):
        for st in statuts:
            inst = Installation.objects.get(pk=inst.pk)
            changer_statut_chantier(inst, st, u, verifier_gates=False)

    def reculer(inst, st):
        s, r = appel('patch', f'/api/django/installations/chantiers/{inst.id}/', {'statut': st})
        inst.refresh_from_db()
        voie = 'PATCH'
        if inst.statut != st:
            avant = s
            changer_statut_chantier(Installation.objects.get(pk=inst.pk), st, u, verifier_gates=False)
            inst.refresh_from_db()
            voie = f'service (PATCH {avant} {str(r)[:120]})'
        return {'http': s, 'voie': voie, 'statut': inst.statut, 'jalons': jalons(inst)}

    obs = {}
    inst = chantier('R1')
    if inst is None:
        return {'repro': False, 'observe': 'pas de chantier'}
    avancer(inst, [S.MATERIEL_COMMANDE, S.PLANIFIE, S.EN_COURS, S.INSTALLE])
    obs['R_installe'] = jalons(inst)
    obs['R_recul_en_cours'] = reculer(inst, S.EN_COURS)
    obs['R_recul_planifie'] = reculer(inst, S.PLANIFIE)
    obs['R_recul_materiel'] = reculer(inst, S.MATERIEL_COMMANDE)
    obs['R_recul_signe'] = reculer(inst, S.SIGNE)
    # T — témoin AARG46
    instT = chantier('T1')
    avancer(instT, [S.MATERIEL_COMMANDE, S.PLANIFIE, S.EN_COURS, S.INSTALLE, S.RECEPTIONNE])
    obs['T_receptionne'] = jalons(instT)
    obs['T_recul_installe'] = reculer(instT, S.INSTALLE)
    t = obs['T_recul_installe']['jalons']
    temoin_ok = bool(obs['T_receptionne']['interne'].get('reception') is True
                     and t['interne'].get('reception') is False and t['portail'].get('reception') is False)
    e = obs['R_recul_en_cours']['jalons']
    sg = obs['R_recul_signe']['jalons']
    defaut = bool(obs['R_installe']['portail'].get('pose') is True and obs['R_recul_en_cours']['statut'] == 'en_cours'
                  and e['interne'].get('pose') is True and e['portail'].get('pose') is True
                  and sg['portail'].get('appro') is True)
    obs['temoin_ok'] = temoin_ok
    return {'repro': bool(temoin_ok and defaut), 'observe': obs}
