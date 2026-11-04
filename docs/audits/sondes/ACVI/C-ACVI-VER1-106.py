# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""C-ACVI-VER1-106 — ACVI77/ACVI78/ACVI94 : C-ACVI-140 cherche le mot `etude_params` dans le SQL et sort `repro: true` après
ACVI94, parce que `prefetch_devis_resume` annote des chemins JSON (`etude_params -> 'scenario'`) permis. Même scénario, même
critère que le test `test_aprf4_devis_liste_prechargement.py::charge_le_json` : colonne lue HORS d'un `->` / `#>`.
`repro: true` = au moins un sélecteur décode encore le JSON entier."""
SONDE = {"constat": "C-ACVI-140+141", "sha": "06ced8b1a",
         "attendu": "aucune requête ne lit etude_params hors d'un chemin JSON ; montants inchangés",
         "modeles": ["crm.Lead", "crm.RelanceEtape", "ventes.Devis", "crm.Client"]}


def sonde(ctx):
    import datetime
    import re
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from django.test.utils import CaptureQueriesContext
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Lead, Client
    from apps.crm.models_clients import EquipeCommerciale
    from apps.roles.models import Role
    from apps.roles.permissions_registre import ADMIN_PERMISSIONS
    from apps.ventes.models import Devis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde VER1 106', slug='sonde-ver1-106')
    role = Role.objects.create(company=c, nom='Administrateur', permissions=ADMIN_PERMISSIONS, est_systeme=True)
    u = U.objects.create_user(username='sonde-ver1-106', password='x', company=c, role=role, role_legacy='admin')
    eq = EquipeCommerciale.objects.create(company=c, nom='Equipe sonde', actif=True)
    eq.membres.add(u)
    etude = {'scenario': 'Avec batterie', 'profil_horaire': [round(i % 24 * 0.37, 3) for i in range(744)]}
    jour = timezone.localdate()
    for i in range(6):
        cl = Client.objects.create(company=c, nom=f'Client {i}')
        l = Lead.objects.create(company=c, nom=f'L{i}', owner=u, stage=stages.QUOTE_SENT, client=cl,
                                telephone=f'06610016{i:02d}', utm_campaign='camp-sonde')
        statut = Devis.Statut.ACCEPTE if i % 2 else Devis.Statut.ENVOYE
        Devis.objects.create(company=c, reference=f'DEV-V106-{i:03d}', client=cl, lead=l, statut=statut,
                             taux_tva=Decimal('20'), version=1, etude_params=dict(etude),
                             date_envoi=timezone.now(), **({'date_acceptation': jour} if i % 2 else {}))

    def mesure(fn):
        try:
            with transaction.atomic():
                with CaptureQueriesContext(connection) as cq:
                    res = fn()
            json_entier = [q['sql'] for q in cq.captured_queries
                           if re.search(r'"etude_params"(?!\s*(?:->|#>))', q['sql'])]
            chemins = [q['sql'] for q in cq.captured_queries if 'etude_params' in q['sql']]
            return {'requetes': len(cq.captured_queries), 'json_entier': len(json_entier),
                    'chemins_json': len(chemins) - len(json_entier), 'resultat': res}
        except Exception as e:
            return {'exception': repr(e)[:250]}

    from apps.crm import clients_selectors as cs, attribution_selectors as ats, cockpit_equipe as ce
    debut, fin = jour - datetime.timedelta(days=30), jour + datetime.timedelta(days=1)
    t0 = timezone.now() - datetime.timedelta(days=30)
    t1 = timezone.now() + datetime.timedelta(days=1)
    obs = {
        'ca_signe_periode': mesure(lambda: str(cs.ca_signe_periode(c, None, debut, fin))[:80]),
        'nb_devis_envoyes_periode': mesure(lambda: str(cs.nb_devis_envoyes_periode(c, None, t0, t1))[:80]),
        'stats_equipe': mesure(lambda: len(cs.stats_equipe(c))),
        'attribution_leads': mesure(lambda: type(ats.attribution_leads(c)).__name__),
        'revenu_attribue_campagne': mesure(lambda: str(ats.revenu_attribue_campagne(c, 'camp-sonde'))[:80]),
        'cockpit_devis_ouverts': mesure(lambda: str(ce._devis_ouverts(c, [u.pk]))[:80]),
    }
    fautifs = sorted(k for k, v in obs.items() if v.get('json_entier') or v.get('exception'))
    return {'repro': bool(fautifs), 'fautifs': fautifs, 'observe': obs}
