SONDE = {"constat": "C-ASEC-005", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : un utilisateur de A qui poste un id de B (activité assigned_to/activity_type, "
                    "entité de facture, produit/lot de ligne de devis, chantier de dossier réglementaire, FK de "
                    "facture/BC/relance/remise, règle/suppléant/délégant d'automatisation, technicien d'intervention/"
                    "équipe/chantier, technicien/catégorie de ticket SAV) -> 400/404 sur le champ visé, aucun libellé "
                    "de B, ligne relue inchangée ; ids de A -> 200/201"}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.entites.models import Entite
    from apps.records.models import Activity, ActivityType
    from apps.stock.models import Produit
    from apps.ventes.models import (
        BonCommande, Devis, Facture, LigneDevis, LigneFacture, ListePrix, LotDevis, ParametrageRelanceClient,
        RegulatoryDossier, RemiseEncaissement)
    from apps.parametres.models_payment_terms import ConditionPaiement
    from apps.installations.models import Installation, Intervention
    from apps.installations.models_equipe import Equipe
    from apps.automation.models import (
        ActionType, ApprovalDelegation, ApprovalRequest, ApprovalRequestType, AutomationRule,
        IncomingWebhookTrigger, TriggerType)
    from apps.sav.models import CategorieEquipement, CategorieTicket, Ticket
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    P = 'sonde-asec005-'

    a = Company.objects.create(nom='Sonde ASEC005 A', slug=P + 'a')
    b = Company.objects.create(nom='Sonde ASEC005 B', slug=P + 'b')

    def usr(nom, co, legacy):
        return User.objects.create_user(username=P + nom, password='x', role_legacy=legacy, company=co)

    resp, admin = usr('resp-a', a, 'responsable'), usr('admin-a', a, 'admin')
    col_a, user_b = usr('col-a', a, 'normal'), usr('user-b-secret', b, 'normal')
    api_r, api_ad = APIClient(), APIClient()
    api_r.force_authenticate(resp)
    api_ad.force_authenticate(admin)

    resultats, tous = {}, []

    def refus(site, label, r, champ, relu_ok, secret=()):
        """400/404 sur le champ visé (r.data), aucun libellé de B, ligne relue inchangée."""
        data = getattr(r, 'data', None)
        champ_ok = isinstance(data, dict) and champ in data
        fuite = any(s in str(data) + r.content.decode('utf-8', 'ignore') for s in secret)
        ok = r.status_code in (400, 404) and champ_ok and not fuite and bool(relu_ok)
        ligne = [label, r.status_code, 'refus ok' if ok else 'KO']
        if not ok:
            ligne.append({'champ_dans_reponse': champ_ok, 'fuite_B': fuite, 'relu_inchange': bool(relu_ok)})
        resultats.setdefault(site, []).append(ligne)
        tous.append(ok)

    def ok_legit(site, label, r, attendus):
        ok = r.status_code in attendus
        ligne = ['contre-épreuve ' + label, r.status_code, 'ok' if ok else 'KO']
        if not ok:
            ligne.append(str(getattr(r, 'data', ''))[:300])
        resultats.setdefault(site, []).append(ligne)
        tous.append(ok)

    # ---------- mondes A et B ----------
    def monde(co, s):
        cl = Client.objects.create(company=co, nom=f'Client {s}', prenom='X', email=f'asec005-{s}@sonde.invalid',
                                   telephone=f'+2126000{ord(s):05d}', adresse='Casa')
        dv = Devis.objects.create(company=co, reference=f'DEV-SONDE-ASEC005-{s}', client=cl,
                                  statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20.00'))
        return {
            'client': cl, 'devis': dv,
            'produit': Produit.objects.create(company=co, nom=f'Produit {s} secret', sku=f'SONDE-ASEC005-{s}',
                                              prix_vente=Decimal('10'), quantite_stock=5),
            'lot': LotDevis.objects.create(company=co, devis=dv, nom_lot=f'Lot {s} secret'),
            'lead': Lead.objects.create(company=co, nom='Lead', prenom=s),
            'entite': Entite.objects.create(company=co, nom=f'Entité {s} secrète', code=f'SA5-{s}'),
            'bc': BonCommande.objects.create(company=co, reference=f'BC-SONDE-ASEC005-{s}', client=cl,
                                             statut=BonCommande.Statut.EN_ATTENTE),
            'cond': ConditionPaiement.objects.create(company=co, libelle=f'30 jours {s} secret'),
            'chantier': Installation.objects.create(company=co, reference=f'CH-SONDE-ASEC005-{s}-SECRET',
                                                    client=cl),
        }
    ma, mb = monde(a, 'A'), monde(b, 'B')
    LigneDevis.objects.create(devis=ma['devis'], designation='Centrale', quantite=Decimal('1'),
                              prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))

    # ---------- ASEC6 : Activity (records) ----------
    S = 'ASEC6'
    URL = '/api/django/records/activities/'
    type_a = ActivityType.objects.create(company=a, nom='Appel A')
    type_b = ActivityType.objects.create(company=b, nom='Type B secret')
    sec = ('sonde-asec005-user-b-secret', 'Type B secret')
    avant = Activity.objects.count()
    for champ, val in (('assigned_to', user_b.id), ('activity_type', type_b.id)):
        corps = {'summary': 'x', 'assigned_to': col_a.id, 'activity_type': type_a.id}
        corps[champ] = val
        r = api_r.post(URL, corps, format='json', **H)
        refus(S, f'POST {champ} de B', r, champ, Activity.objects.count() == avant, sec)
    act = Activity.objects.create(company=a, personnelle=True, activity_type=type_a, summary='A faire',
                                  assigned_to=resp, created_by=resp)
    for champ, val in (('assigned_to', user_b.id), ('activity_type', type_b.id)):
        r = api_r.patch(f'{URL}{act.id}/', {champ: val}, format='json', **H)
        act.refresh_from_db()
        refus(S, f'PATCH {champ} de B', r, champ, act.assigned_to_id == resp.id and act.activity_type_id == type_a.id,
              sec)
    r = api_r.post(URL, {'summary': 'x', 'assigned_to': col_a.id, 'activity_type': type_a.id}, format='json', **H)
    ok_legit(S, 'POST ids de A', r, (201,))

    # ---------- ASEC7 : entité de B sur facture et lead (utilisateur sans périmètre d'entités) ----------
    S = 'ASEC7'
    fac = Facture.objects.create(company=a, reference='FAC-SONDE-ASEC005-1', client=ma['client'],
                                 statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20.00'), created_by=resp)
    r = api_r.patch(f'/api/django/ventes/factures/{fac.id}/', {'entite': mb['entite'].pk}, format='json', **H)
    fac.refresh_from_db()
    refus(S, 'PATCH facture.entite de B', r, 'entite', fac.entite_id is None, ('secrète',))
    r = api_r.patch(f'/api/django/ventes/factures/{fac.id}/', {'entite': ma['entite'].pk}, format='json', **H)
    ok_legit(S, 'PATCH facture.entite de A', r, (200,))
    lead_a = Lead.objects.create(company=a, nom='Lead', prenom='cible')
    r = api_r.patch(f'/api/django/crm/leads/{lead_a.id}/', {'entite': mb['entite'].pk}, format='json', **H)
    lead_a.refresh_from_db()
    refus(S, 'PATCH lead.entite de B', r, 'entite', lead_a.entite_id is None, ('secrète',))

    # ---------- ASEC22 : devis (lignes produit/lot, règle de liste de prix) ----------
    S = 'ASEC22'
    LIG = '/api/django/ventes/devis-lignes/'
    ligne = LigneDevis.objects.create(devis=ma['devis'], produit=ma['produit'], designation='P',
                                      quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    base = {'devis': ma['devis'].id, 'produit': ma['produit'].id, 'designation': 'Panneau', 'quantite': '1',
            'prix_unitaire': '1000', 'remise': '0'}
    n0 = LigneDevis.objects.count()
    for champ, val in (('produit', mb['produit'].id), ('lot', mb['lot'].id)):
        r = api_r.post(LIG, {**base, champ: val}, format='json', **H)
        refus(S, f'POST ligne {champ} de B', r, champ, LigneDevis.objects.count() == n0, ('secret',))
        r = api_r.patch(f'{LIG}{ligne.id}/', {champ: val}, format='json', **H)
        ligne.refresh_from_db()
        refus(S, f'PATCH ligne {champ} de B', r, champ, ligne.produit_id == ma['produit'].id and ligne.lot_id is None,
              ('secret',))
    liste_a = ListePrix.objects.create(company=a, nom='Gros A')
    r = api_r.post(f'/api/django/ventes/listes-prix/{liste_a.id}/regles/',
                   {'produit': mb['produit'].id, 'type_regle': 'remise_pct', 'valeur': '8', 'quantite_min': '1'},
                   format='json', **H)
    refus(S, 'POST règle liste de prix produit de B', r, 'produit', not liste_a.regles.exists(), ('secret',))
    r = api_r.post(LIG, {**base, 'lot': ma['lot'].id}, format='json', **H)
    ok_legit(S, 'POST ligne produit+lot de A', r, (201,))
    r = api_r.post(f'/api/django/ventes/listes-prix/{liste_a.id}/regles/',
                   {'produit': ma['produit'].id, 'type_regle': 'remise_pct', 'valeur': '8', 'quantite_min': '1'},
                   format='json', **H)
    ok_legit(S, 'POST règle produit de A', r, (201,))

    # ---------- ASEC26 : dossier réglementaire, chantier de B ----------
    S = 'ASEC26'
    URL = '/api/django/ventes/dossiers-reglementaires/'
    n0 = RegulatoryDossier.objects.count()
    r = api_r.post(URL, {'devis': ma['devis'].id, 'regime_8221': 'declaration_bt', 'chantier': mb['chantier'].id},
                   format='json', **H)
    refus(S, 'POST dossier chantier de B', r, 'chantier', RegulatoryDossier.objects.count() == n0, ('SECRET',))
    dossier = RegulatoryDossier.objects.create(company=a, devis=ma['devis'], regime_8221='declaration_bt',
                                               chantier=ma['chantier'], created_by=resp)
    r = api_r.patch(f'{URL}{dossier.id}/', {'chantier': mb['chantier'].id}, format='json', **H)
    dossier.refresh_from_db()
    refus(S, 'PATCH dossier chantier de B', r, 'chantier', dossier.chantier_id == ma['chantier'].id, ('SECRET',))
    r = api_r.post(URL, {'devis': ma['devis'].id, 'regime_8221': 'declaration_bt', 'chantier': ma['chantier'].id},
                   format='json', **H)
    ok_legit(S, 'POST dossier chantier de A', r, (201,))

    # ---------- ASEC27 : FactureWriteSerializer ----------
    S = 'ASEC27'
    F = f'/api/django/ventes/factures/{fac.id}/'
    fk = {'client': mb['client'].pk, 'devis': mb['devis'].pk, 'bon_commande': mb['bc'].pk, 'lead': mb['lead'].pk,
          'entite': mb['entite'].pk, 'condition_paiement_ref': mb['cond'].pk}
    for champ, val in fk.items():
        r = api_r.patch(F, {champ: val}, format='json', **H)
        fac.refresh_from_db()
        refus(S, f'PATCH facture.{champ} de B', r, champ,
              fac.client_id == ma['client'].pk and fac.devis_id is None and fac.bon_commande_id is None
              and fac.lead_id is None and fac.condition_paiement_ref_id is None, ('Client B', 'secret', 'secrète'))
    nf = Facture.objects.count()
    r = api_r.post('/api/django/ventes/factures/', {'client': mb['client'].pk, 'taux_tva': '20.00'},
                   format='json', **H)
    refus(S, 'POST facture client de B', r, 'client', Facture.objects.count() == nf, ('Client B',))
    for champ, val in (('produit', mb['produit'].pk), ('source_devis', mb['devis'].pk)):
        corps = {'facture': fac.id, 'designation': 'X', 'quantite': '1', 'prix_unitaire': '10',
                 'produit': ma['produit'].pk}
        corps[champ] = val
        r = api_r.post('/api/django/ventes/factures-lignes/', corps, format='json', **H)
        refus(S, f'POST ligne facture {champ} de B', r, champ,
              not LigneFacture.objects.filter(facture=fac).exists(), ('secret',))
    r = api_r.patch(F, {'statut': 'payee', 'revue_statut': 'validee'}, format='json', **H)
    fac.refresh_from_db()
    ok = r.status_code in (200, 400) and fac.statut == Facture.Statut.BROUILLON
    resultats[S].append(['PATCH statut=payee/revue_statut ignorés (champs serveur)', r.status_code,
                         'ok, statut relu=' + fac.statut if ok else 'KO'])
    tous.append(ok)
    r = api_r.patch(F, {'client': ma['client'].pk, 'lead': ma['lead'].pk, 'condition_paiement_ref': ma['cond'].pk},
                    format='json', **H)
    ok_legit(S, 'PATCH facture client/lead/condition de A', r, (200,))

    # ---------- ASEC28 : BC, relance, remise (mandat PARQUÉ — non rejoué) ----------
    S = 'ASEC28'
    bc_url = f'/api/django/ventes/bons-commande/{ma["bc"].id}/'
    for champ, val in (('client', mb['client'].pk), ('devis', mb['devis'].pk), ('lead', mb['lead'].pk)):
        r = api_r.patch(bc_url, {champ: val}, format='json', **H)
        ma['bc'].refresh_from_db()
        refus(S, f'PATCH BC {champ} de B', r, champ,
              ma['bc'].client_id == ma['client'].pk and ma['bc'].devis_id is None and ma['bc'].lead_id is None)
    relance = ParametrageRelanceClient.objects.create(company=a, client=ma['client'], responsable=resp)
    for champ, val in (('responsable', user_b.pk), ('client', mb['client'].pk)):
        r = api_r.patch(f'/api/django/ventes/parametrages-relance-client/{relance.id}/', {champ: val},
                        format='json', **H)
        relance.refresh_from_db()
        refus(S, f'PATCH relance {champ} de B', r, champ,
              relance.responsable_id == resp.pk and relance.client_id == ma['client'].pk)
    from datetime import date
    remise = RemiseEncaissement.objects.create(company=a, technicien=resp, reference='REM-SONDE-ASEC005',
                                               date_collecte=date.today(), montant_declare=Decimal('10.00'))
    r = api_r.patch(f'/api/django/ventes/remises-encaissement/{remise.id}/', {'technicien': user_b.pk},
                    format='json', **H)
    remise.refresh_from_db()
    refus(S, 'PATCH remise technicien de B', r, 'technicien', remise.technicien_id == resp.pk)
    r = api_r.patch(f'/api/django/ventes/parametrages-relance-client/{relance.id}/', {'responsable': col_a.pk},
                    format='json', **H)
    ok_legit(S, 'PATCH relance responsable de A', r, (200,))
    resultats[S].append(['NON REJOUE : MandatPaiement.client (route/service parqués AFAC19)'])

    # ---------- ASEC30 : automatisations ----------
    S = 'ASEC30'
    BASE = '/api/django/automation'

    def regle(co, nom):
        return AutomationRule.objects.create(company=co, nom=nom, trigger_type=TriggerType.LEAD_STAGE_CHANGE,
                                             trigger_config={}, action_type=ActionType.CREATE_ACTIVITY,
                                             action_config={'body': 'x'})
    regle_a, regle_b = regle(a, 'Règle A'), regle(b, 'Règle B secrète')
    trig = IncomingWebhookTrigger.objects.create(company=a, rule=regle_a)
    r = api_ad.patch(f'{BASE}/incoming-webhooks/{trig.pk}/', {'rule': regle_b.pk}, format='json', **H)
    trig.refresh_from_db()
    refus(S, 'PATCH webhook rule de B', r, 'rule', trig.rule_id == regle_a.pk, ('secrète',))
    tq_a = ApprovalRequestType.objects.create(company=a, nom='Achat A')
    tq_b = ApprovalRequestType.objects.create(company=b, nom='Achat B secret')
    dem = ApprovalRequest.objects.create(company=a, request_type=tq_a, demandeur=col_a, payload={'montant': 100},
                                         status=ApprovalRequest.Status.PENDING)
    r = api_ad.patch(f'{BASE}/approval-requests/{dem.pk}/', {'request_type': tq_b.pk}, format='json', **H)
    dem.refresh_from_db()
    refus(S, 'PATCH demande request_type de B', r, 'request_type', dem.request_type_id == tq_a.pk, ('secret',))
    debut, fin = timezone.now() - timedelta(days=1), timezone.now() + timedelta(days=1)
    n0 = ApprovalDelegation.objects.count()
    for champ in ('suppleant', 'delegant'):
        corps = {'delegant': admin.pk, 'suppleant': col_a.pk, 'date_debut': debut.isoformat(),
                 'date_fin': fin.isoformat()}
        corps[champ] = user_b.pk
        r = api_ad.post(f'{BASE}/approval-delegations/', corps, format='json', **H)
        refus(S, f'POST délégation {champ} de B', r, champ, ApprovalDelegation.objects.count() == n0, ('secret',))
    ok_corps = {'delegant': admin.pk, 'suppleant': col_a.pk, 'date_debut': debut.isoformat(),
                'date_fin': fin.isoformat()}
    r = api_ad.post(f'{BASE}/approval-delegations/', ok_corps, format='json', **H)
    ok_legit(S, 'POST délégation de A', r, (201,))

    # ---------- ASEC32 : intervention / chantier ----------
    S = 'ASEC32'
    IB = '/api/django/installations'
    eq_a, eq_b = Equipe.objects.create(company=a, nom='Équipe A'), Equipe.objects.create(company=b, nom='Équipe B')
    interv = Intervention.objects.create(company=a, installation=ma['chantier'])
    for champ, val in (('technicien', user_b.pk), ('equipe_ref', eq_b.pk), ('equipe', [user_b.pk])):
        r = api_ad.patch(f'{IB}/interventions/{interv.pk}/', {champ: val}, format='json', **H)
        interv.refresh_from_db()
        refus(S, f'PATCH intervention {champ} de B', r, champ,
              interv.technicien_id is None and interv.equipe_ref_id is None and not interv.equipe.exists(),
              ('secret',))
    n0 = Intervention.objects.filter(company=a).count()
    r = api_ad.post(f'{IB}/interventions/', {'installation': ma['chantier'].pk, 'technicien': user_b.pk,
                                             'type_intervention': Intervention.Type.CONTROLE}, format='json', **H)
    refus(S, 'POST intervention technicien de B', r, 'technicien', Intervention.objects.filter(company=a).count() == n0,
          ('secret',))
    r = api_ad.patch(f'{IB}/chantiers/{ma["chantier"].pk}/', {'technicien_responsable': user_b.pk}, format='json', **H)
    ma['chantier'].refresh_from_db()
    refus(S, 'PATCH chantier technicien_responsable de B', r, 'technicien_responsable',
          ma['chantier'].technicien_responsable_id is None, ('secret',))
    corps_ok = {'technicien': col_a.pk, 'equipe_ref': eq_a.pk, 'equipe': [col_a.pk]}
    r = api_ad.patch(f'{IB}/interventions/{interv.pk}/', corps_ok, format='json', **H)
    ok_legit(S, 'PATCH intervention technicien/équipe de A', r, (200,))
    r = api_ad.patch(f'{IB}/chantiers/{ma["chantier"].pk}/', {'technicien_responsable': col_a.pk}, format='json', **H)
    ok_legit(S, 'PATCH chantier technicien_responsable de A', r, (200,))

    # ---------- ASEC34 : ticket SAV ----------
    S = 'ASEC34'
    TU = '/api/django/sav/tickets/'
    cat_a, cat_b = (CategorieTicket.objects.create(company=a, libelle='Panne A'),
                    CategorieTicket.objects.create(company=b, libelle='Panne B secrète'))
    ce_a, ce_b = (CategorieEquipement.objects.create(company=a, nom='Onduleurs A'),
                  CategorieEquipement.objects.create(company=b, nom='Pompes B secrètes'))
    tk = Ticket.objects.create(company=a, reference='SAV-SONDE-ASEC005-1', client=ma['client'], cout=Decimal('100.00'))
    for champ, val in (('technicien_responsable', user_b.id), ('categorie', cat_b.id),
                       ('categorie_equipement', ce_b.id)):
        r = api_ad.patch(f'{TU}{tk.id}/', {champ: val}, format='json', **H)
        tk.refresh_from_db()
        refus(S, f'PATCH ticket {champ} de B', r, champ,
              tk.technicien_responsable_id is None and tk.categorie_id is None and tk.categorie_equipement_id is None,
              ('secrète', 'secret'))
    n0 = Ticket.objects.count()
    r = api_ad.post(TU, {'client': ma['client'].id, 'type': 'correctif', 'description': 'x',
                         'technicien_responsable': user_b.id}, format='json', **H)
    refus(S, 'POST ticket technicien_responsable de B', r, 'technicien_responsable', Ticket.objects.count() == n0,
          ('secret',))
    corps_ok = {'technicien_responsable': col_a.id, 'categorie': cat_a.id, 'categorie_equipement': ce_a.id}
    r = api_ad.patch(f'{TU}{tk.id}/', corps_ok, format='json', **H)
    ok_legit(S, 'PATCH ticket ids de A', r, (200,))
    r = api_ad.patch(f'{TU}{tk.id}/', {'cout': '999.00', 'non_facturable': True, 'est_recidive': True},
                     format='json', **H)
    tk.refresh_from_db()
    ok = r.status_code == 200 and tk.cout == Decimal('100.00') and not tk.non_facturable and not tk.est_recidive
    resultats[S].append(['PATCH cout/non_facturable/est_recidive ignorés (champs serveur)', r.status_code,
                         'ok, cout relu=' + str(tk.cout) if ok else 'KO'])
    tous.append(ok)

    return {'sites': resultats, 'gestes_total': len(tous), 'gestes_ko': tous.count(False),
            'repro': bool(tous) and all(tous)}
