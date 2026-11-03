# flake8: noqa  (constat C-ACVI-141 : copie rejouable de la sonde groupée C-ACVI-140, sa clé dans `observe`)
"""H-1 + H-2 : la colonne `ventes_devis.etude_params` (JSON d'étude, jusqu'à 1,45 Mio en prod) est-elle
SÉLECTIONNÉE par (H-1) GET relance-etapes/?scope=all, ?lead=<id> et le sélecteur `relance_etapes_dues`
(digest 08:30), (H-2) les sélecteurs cockpit / attribution qui font `prefetch_related('devis')` ?
Société NEUVE, 6 leads × 1 devis (étude 744 h) × 1 touche `apres_devis` ouverte. Transaction annulée."""
SONDE = {"constat": "C-ACVI-140+141", "sha": "352ae5455",
         "attendu": "aucune requête capturée ne sélectionne \"etude_params\" (defer comme relance_etapes_periode)",
         "modeles": ["crm.Lead", "crm.RelanceEtape", "ventes.Devis", "crm.Client"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from django.test.utils import CaptureQueriesContext
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Lead, Client
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.models_clients import EquipeCommerciale
    from apps.roles.models import Role
    from apps.roles.permissions_registre import ADMIN_PERMISSIONS
    from apps.ventes.models import Devis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 140', slug='sonde-acvi-140')
    role = Role.objects.create(company=c, nom='Administrateur', permissions=ADMIN_PERMISSIONS, est_systeme=True)
    u = U.objects.create_user(username='sonde-acvi-140', password='x', company=c, role=role, role_legacy='admin')
    eq = EquipeCommerciale.objects.create(company=c, nom='Equipe sonde', actif=True)
    eq.membres.add(u)
    etude = {'scenario': 'Avec batterie', 'profil_horaire': [round(i % 24 * 0.37, 3) for i in range(744)]}
    jour = timezone.localdate()
    leads = []
    for i in range(6):
        cl = Client.objects.create(company=c, nom=f'Client {i}')
        l = Lead.objects.create(company=c, nom=f'L{i}', owner=u, stage=stages.QUOTE_SENT, client=cl,
                                telephone=f'06610014{i:02d}', utm_campaign='camp-sonde')
        statut = Devis.Statut.ACCEPTE if i % 2 else Devis.Statut.ENVOYE
        d = Devis.objects.create(company=c, reference=f'DEV-ACVI140-{i:03d}', client=cl, lead=l, statut=statut,
                                 taux_tva=Decimal('20'), version=1, etude_params=dict(etude),
                                 date_envoi=timezone.now(), **({'date_acceptation': jour} if i % 2 else {}))
        RelanceEtape.objects.create(company=c, lead=l, cadence='apres_devis', ordre=i + 1,
                                    canal=RelanceEtape.Canal.WHATSAPP, libelle=f'Relance {i}', devis=d,
                                    due_at=timezone.now(), due_date=jour, statut=RelanceEtape.Statut.A_FAIRE)
        leads.append(l)
    api = APIClient()
    api.force_authenticate(u)
    url = reverse('relance-etape-list')

    def mesure(nom, fn):
        try:
            with transaction.atomic():
                with CaptureQueriesContext(connection) as cq:
                    res = fn()
            fautives = [q['sql'] for q in cq.captured_queries if 'etude_params' in q['sql']]
            return {'requetes': len(cq.captured_queries), 'avec_etude_params': len(fautives),
                    'extrait': (fautives[0][:140] if fautives else ''), 'resultat': res}
        except Exception as e:
            return {'exception': repr(e)[:250]}

    obs = {}
    obs['H1_get_scope_all'] = mesure('all', lambda: api.get(url, {'scope': 'all'}, HTTP_HOST='localhost').status_code)
    obs['H1_get_lead'] = mesure('lead', lambda: api.get(url, {'lead': leads[0].pk}, HTTP_HOST='localhost').status_code)
    from apps.crm.cadence_selectors import relance_etapes_dues, relance_etapes_periode
    obs['H1_selecteur_dues'] = mesure('dues', lambda: len(list(relance_etapes_dues(c, u, scope='all'))))
    from apps.crm import clients_selectors as cs, attribution_selectors as ats, cockpit_equipe as ce
    debut, fin = jour - datetime.timedelta(days=30), jour + datetime.timedelta(days=1)
    t0 = timezone.now() - datetime.timedelta(days=30)
    t1 = timezone.now() + datetime.timedelta(days=1)
    obs['H2_ca_signe_periode'] = mesure('ca', lambda: str(cs.ca_signe_periode(c, None, debut, fin))[:80])
    obs['H2_nb_devis_envoyes_periode'] = mesure('nb', lambda: str(cs.nb_devis_envoyes_periode(c, None, t0, t1))[:80])
    obs['H2_stats_equipe'] = mesure('stats', lambda: len(cs.stats_equipe(c)))
    obs['H2_attribution_leads'] = mesure('attr', lambda: type(ats.attribution_leads(c)).__name__)
    obs['H2_attribution_lead_rows'] = mesure('rows', lambda: len(list(ats.attribution_lead_rows(c))))
    obs['H2_revenu_attribue_campagne'] = mesure('rev', lambda: str(ats.revenu_attribue_campagne(c, 'camp-sonde'))[:80])
    obs['H2_cockpit_devis_ouverts'] = mesure('cock', lambda: str(ce._devis_ouverts(c, [u.pk]))[:80])
    # témoin : la période (AOOM3) ne doit PAS charger la colonne
    obs['temoin_relance_etapes_periode'] = mesure('periode', lambda: len(list(
        relance_etapes_periode(c, u, date_debut=debut, date_fin=fin))))
    fautifs = sorted(k for k, v in obs.items() if not k.startswith('temoin') and v.get('avec_etude_params'))
    obs['charge_etude_params'] = fautifs
    return {'repro': bool(fautifs), 'observe': obs}
