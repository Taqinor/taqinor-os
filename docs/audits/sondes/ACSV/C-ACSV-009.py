# flake8: noqa  (sonde PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K09 — devis accepté par l'API -> chantier ; avancé jusqu'à « Réceptionné » par `changer_statut_chantier`
(verifier_gates=False, cascade intégrale : jalon RÉCEPTION atteint, tranche « solde » liée). (T) GET
`chantiers/a-facturer/` le liste. Puis « Annuler le chantier » par l'API (motif « parc retiré ») et re-GET
`a-facturer` (lecteur de PilotageChantiersPage). Jumeau relu : `notifier_jalon_a_facturer` exclut l'annulé (ACHT2)."""
SONDE = {"constat": "C-ACSV-009", "sha": "f57951e87",
         "attendu": "repro si le chantier annulé figure encore dans a-facturer (tranche solde) ; T : présent avant annulation",
         "modeles": ["installations.Installation", "installations.JalonProjet"]}


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
    from apps.installations.services import changer_statut_chantier, notifier_jalon_a_facturer
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    S = Installation.Statut
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACSV 009', slug='sonde-acsv-009')
    u = U.objects.create_user(username='sonde-acsv-009', password='x', role_legacy='admin', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau 710W', sku='ACSV009-PAN', prix_vente=Decimal('1000'),
                                 prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=50)
    lead = Lead.objects.create(company=c, nom='Facturer', prenom='K09', telephone='+212600000909', ville='Rabat',
                               email='acsv009@example.invalid', type_installation='residentiel')
    cl = Client.objects.create(company=c, nom='Facturer', prenom='K09', email='acsv009@example.invalid')
    d = Devis.objects.create(company=c, reference='DEV-ACSV009-1', client=cl, lead=lead, statut='envoye',
                             date_envoi=timezone.now(), taux_tva=Decimal('20'), mode_installation='residentiel',
                             created_by=u)
    LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('10'),
                              prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
    api = APIClient()
    api.force_authenticate(u)

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth == 'get':
                    r = api.get(url, HTTP_HOST='localhost')
                else:
                    r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            try:
                return r.status_code, json.loads(r.content.decode('utf-8', 'replace') or '{}')
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return repr(e)[:200], {}

    def a_facturer(inst):
        s, r = appel('get', '/api/django/installations/chantiers/a-facturer/')
        return s, [x for x in (r if isinstance(r, list) else []) if x.get('installation_id') == inst.id]

    obs = {'accepter': appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})[0]}
    inst = Installation.objects.filter(devis=d).first()
    if inst is None:
        return {'repro': False, 'observe': obs}
    for st in [S.MATERIEL_COMMANDE, S.PLANIFIE, S.EN_COURS, S.INSTALLE, S.RECEPTIONNE]:
        changer_statut_chantier(Installation.objects.get(pk=inst.pk), st, u, verifier_gates=False)
    inst.refresh_from_db()
    obs['statut'] = inst.statut
    obs['jalons'] = list(JalonProjet.objects.filter(installation=inst, atteint=True)
                         .values_list('phase', 'tranche_echeancier'))
    obs['T_a_facturer'] = a_facturer(inst)
    s, r = appel('post', f'/api/django/installations/chantiers/{inst.id}/annuler/', {'motif': 'parc retiré'})
    inst.refresh_from_db()
    obs['annuler'] = [s, inst.annule, None if s == 200 else str(r)[:160]]
    obs['R_a_facturer'] = a_facturer(inst)
    # jumeau : le rappel exclut l'annulé
    j = JalonProjet.objects.filter(installation=inst, phase='reception').first()
    if j is not None:
        JalonProjet.objects.filter(pk=j.pk).update(rappel_facturation_envoye=False)
        obs['jumeau_notifier_sur_annule'] = notifier_jalon_a_facturer(JalonProjet.objects.get(pk=j.pk), u)
    temoin_ok = bool(obs['T_a_facturer'][0] == 200 and obs['T_a_facturer'][1])
    defaut = bool(inst.annule and obs['R_a_facturer'][1])
    obs['temoin_ok'] = temoin_ok
    return {'repro': bool(temoin_ok and defaut), 'observe': obs}
