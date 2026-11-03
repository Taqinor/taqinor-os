# flake8: noqa  (constat C-ACVI-147 : copie rejouable de la sonde groupée C-ACVI-143, sa clé dans `observe`)
"""H-4 + H-5 + H-8 : croissance ∝ N des beats crm, par CaptureQueriesContext à DEUX tailles (N = 4 puis 12) dans
une société NEUVE (delta seul : les beats parcourent toutes les sociétés, la base démo donne un socle constant).
H-4 : `escalader_premier_contact(dry_run=True)` sur des leads de 60 jours jamais contactés, marqueur déjà posé ;
H-5 : `recalculer_scores_obsoletes()` (les leads des AUTRES sociétés sont rendus « récents » dans la transaction
      annulée pour borner le passage à la société de la sonde) ;
H-8 : `dispatch.escalader_file()` sur des attentes « À prendre » de 3 jours, trois marqueurs déjà posés (aucune
      écriture). Transaction annulée."""
SONDE = {"constat": "C-ACVI-143+144+147", "sha": "352ae5455",
         "attendu": "nombre de requêtes ≈ constant (ou borné) quand N passe de 4 à 12, pour chacun des trois beats",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.AttributionEnAttente", "crm.EquipeCommerciale"]}


def sonde(ctx):
    import datetime
    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from django.test.utils import CaptureQueriesContext
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.models_clients import EquipeCommerciale, AttributionEnAttente
    from apps.crm import dispatch
    from apps.crm.leads_score import recalculer_scores_obsoletes
    from apps.crm.management.commands.escalader_premier_contact import escalader_premier_contact, MARQUEUR
    from apps.roles.models import Role
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 143', slug='sonde-acvi-143')
    r = Role.objects.create(company=c, nom='Commercial sonde 143', permissions=['crm_creer', 'crm_voir'])
    u = U.objects.create_user(username='sonde-acvi-143', password='x', company=c, role=r)
    eq = EquipeCommerciale.objects.create(company=c, nom='File sonde', actif=True, responsable=u,
                                          file_a_prendre=True)
    eq.membres.add(u)
    maintenant = timezone.now()
    n = [0]
    # H-5 borné à la société de la sonde (annulé avec la transaction)
    Lead.objects.exclude(company=c).update(date_modification=maintenant)

    def ajouter(k):
        for _ in range(k):
            n[0] += 1
            i = n[0]
            l = Lead.objects.create(company=c, nom=f'L{i}', owner=u, telephone=f'066143{i:04d}', ville='Rabat',
                                    email=f'l{i}-143@example.invalid')
            Lead.objects.filter(pk=l.pk).update(date_creation=maintenant - datetime.timedelta(days=60),
                                                date_modification=maintenant - datetime.timedelta(days=3))
            LeadActivity.objects.create(company=c, lead=l, user=None, kind=LeadActivity.Kind.NOTE,
                                        body=MARQUEUR + ' (sonde)')
            for _m, _p, marqueur in dispatch.PALIERS_FILE:
                LeadActivity.objects.create(company=c, lead=l, user=None, kind=LeadActivity.Kind.NOTE,
                                            body=marqueur + ' (sonde)')
            a = AttributionEnAttente.objects.create(company=c, lead=l, equipe=eq)
            AttributionEnAttente.objects.filter(pk=a.pk).update(created_at=maintenant - datetime.timedelta(days=3))

    def compte(fn):
        try:
            with transaction.atomic():
                with CaptureQueriesContext(connection) as cq:
                    res = fn()
            return [len(cq.captured_queries), str(res)[:80]]
        except Exception as e:
            return ['exc', repr(e)[:200]]

    beats = {
        'H4_escalader_premier_contact': lambda: escalader_premier_contact(dry_run=True, now=maintenant),
        'H5_recalculer_scores_obsoletes': lambda: recalculer_scores_obsoletes(),
        'H8_escalader_file': lambda: dispatch.escalader_file(maintenant=maintenant),
    }
    obs = {}
    ajouter(4)
    for k, fn in beats.items():
        compte(fn)  # échauffement (et premier passage sur les données démo)
        obs[k] = {'N4': compte(fn)}
    ajouter(8)
    for k, fn in beats.items():
        obs[k]['N12'] = compte(fn)
        a, b = obs[k]['N4'][0], obs[k]['N12'][0]
        obs[k]['delta_par_N'] = round((b - a) / 8, 2) if isinstance(a, int) and isinstance(b, int) else None
    repro = {k: (obs[k]['delta_par_N'] or 0) >= 0.9 for k in beats}
    obs['repro_par_constat'] = repro
    return {'repro': any(repro.values()), 'observe': obs}
