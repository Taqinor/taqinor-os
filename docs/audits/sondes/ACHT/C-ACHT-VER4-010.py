# flake8: noqa  (sonde de contre-visite vérifie ACHT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ACHT124 : `InterventionCapturePanels.jsx::patchLigne` joint désormais `li.date_modification`
(version LUE au chargement du panneau) à chaque op hors ligne `intervention.consommation_ligne`.
Hors ligne, le panneau ne se recharge pas (`if (r.queued) toast…` sans `load()`) : deux saisies
successives sur la MÊME ligne (quantité puis justification de l'écart, deux `onBlur`) partent
toutes deux avec la même base T0. Au rejeu, la 1re op est appliquée et fait avancer
`date_modification` ; la 2de est alors comparée à T0 par `offlinesync/conflicts.py::detecter`
et revient `conflit` (« modifié ailleurs ») alors qu'AUCUN autre acteur n'a touché la ligne.
La sonde rejoue côté serveur les deux ops TELLES QUE L'ÉCRAN LES FORME (même base T0, même lot)
sans aucune correction en ligne entre-temps ; témoin : une seule op ⇒ applied."""
SONDE = {"constat": "C-ACHT-VER4-010", "sha": "fcbed3760",
         "modeles": ["installations.ConsommationLigne", "installations.MaterielConsommation",
                     "installations.Intervention", "installations.Installation",
                     "offlinesync.OfflineOperation", "installations.FieldOp",
                     "authentication.Company", "authentication.User"],
         "attendu": "2 ops hors ligne du même terminal sur la même ligne, base T0, sans correction en ligne : "
                    "op1 applied (8), op2 (justification) conflit — faux conflit ; témoin 1 op : applied"}


def sonde(ctx):
    import uuid
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import ConsommationLigne, Installation, Intervention
    from apps.installations import field_capture

    co = Company.objects.create(nom='Sonde ACHT VER4-010', slug='sonde-acht-ver4-010')
    u = get_user_model().objects.create_user(username='sonde-acht-ver4-010', password='x', company=co,
                                             role_legacy='responsable')
    inst = Installation.objects.create(company=co, reference='CH-SONDE-ACHT-V4-010')
    api = APIClient()
    api.force_authenticate(u)

    def _ligne():
        iv = Intervention.objects.create(company=co, installation=inst, type_intervention='pose', created_by=u,
                                         technicien=u, statut=Intervention.Statut.SUR_SITE)
        cons = field_capture.ensure_consommation(iv)
        li = ConsommationLigne.objects.create(company=co, consommation=cons, designation='Câble',
                                              hors_nomenclature=True, quantite_prevue=Decimal('10'),
                                              quantite_utilisee=Decimal('10'))
        # Ligne chargée par le terminal il y a 10 min (T0), personne ne la touche ensuite.
        ConsommationLigne.objects.filter(pk=li.pk).update(
            date_modification=li.date_modification - timedelta(minutes=10))
        li.refresh_from_db()
        return iv, li, li.date_modification.isoformat()

    def _op(iv, li, base, champs):
        return {'op_type': 'intervention.consommation_ligne', 'client_op_id': str(uuid.uuid4()),
                'client_ts': '2026-11-04T09:30:00Z', 'base_updated_at': base,
                'payload': dict({'intervention': iv.id, 'ligne': li.id}, **champs)}

    def _sync(ops):
        r = api.post('/api/django/installations/sync/', {'ops': ops}, format='json', HTTP_HOST='localhost')
        return r.status_code, [(x.get('status'), x.get('error') or x.get('detail')) for x in (r.json().get('results') or [])]

    # Témoin : une seule saisie hors ligne.
    iv_t, li_t, base_t = _ligne()
    code_t, res_t = _sync([_op(iv_t, li_t, base_t, {'quantite_utilisee': 8})])
    # Écran : quantité puis justification sur la même ligne, même base T0 (panneau non rechargé).
    iv, li, base = _ligne()
    code, res = _sync([_op(iv, li, base, {'quantite_utilisee': 8}),
                       _op(iv, li, base, {'justification': 'Casse au déroulage'})])
    li.refresh_from_db()
    print(f"témoin http={code_t} {res_t} ; écran http={code} {res} ; "
          f"ligne finale qte={li.quantite_utilisee} justification={li.justification!r}")
    statuts = [s for s, _ in res]
    repro = (res_t and res_t[0][0] == 'applied' and statuts[:1] == ['applied']
             and len(statuts) > 1 and statuts[1] == 'conflit' and li.justification == '')
    return {'repro': bool(repro), 'temoin': res_t, 'ecran': res,
            'justification_finale': li.justification, 'quantite_finale': str(li.quantite_utilisee)}
