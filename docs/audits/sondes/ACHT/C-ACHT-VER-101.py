# flake8: noqa  (sonde de contre-visite vérifie ACHT, rejouable par scripts/sonde.py — AMET93)
"""ACHT33 : l'outbox terrain doit envoyer `base_updated_at` avec la correction de consommation
pour que le serveur (ACHT32, `offlinesync/conflicts.py`) détecte un conflit. Le seul écran qui
file `intervention.consommation_ligne` (`InterventionCapturePanels.jsx::patchLigne`) appelle
`withOfflineFallback` SANS `meta.baseUpdatedAt` : l'op part sans version lue. La sonde rejoue
côté serveur l'op TELLE QUE L'ÉCRAN LA FORME (client_ts, pas de base_updated_at) après une
correction en ligne : elle est appliquée et écrase la valeur en ligne ; le témoin avec
`base_updated_at` (forme du contrat) revient `conflit`."""
SONDE = {"constat": "C-ACHT-VER-101", "sha": "c6ab9b58e",
         "attendu": "op de l'écran (sans base_updated_at) après correction en ligne 12 : applied, ligne 8 (écrasée) ; témoin avec base_updated_at : conflit"}


def sonde(ctx):
    import uuid
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import (
        ConsommationLigne, Installation, Intervention, MaterielConsommation,
    )
    co = Company.objects.create(nom='Sonde ACHT VER-101', slug='sonde-acht-ver-101')
    u = get_user_model().objects.create_user(username='sonde-acht-ver-101', password='x', company=co,
                                             role_legacy='responsable')
    inst = Installation.objects.create(company=co, reference='CH-SONDE-ACHT-101')
    iv = Intervention.objects.create(company=co, installation=inst, type_intervention='pose', created_by=u,
                                     technicien=u, statut=Intervention.Statut.SUR_SITE)
    from apps.installations import field_capture
    cons = field_capture.ensure_consommation(iv)
    ligne = ConsommationLigne.objects.create(company=co, consommation=cons, designation='Câble', hors_nomenclature=True,
                                             quantite_prevue=Decimal('10'), quantite_utilisee=Decimal('10'))
    lu_par_terminal = ligne.date_modification.isoformat()
    # Correction EN LIGNE après la lecture du terminal (autre acteur) : 12, version plus récente.
    ConsommationLigne.objects.filter(pk=ligne.pk).update(
        quantite_utilisee=Decimal('12'), date_modification=ligne.date_modification + timedelta(minutes=5))
    api = APIClient()
    api.force_authenticate(u)

    def _sync(op):
        r = api.post('/api/django/installations/sync/', {'ops': [op]}, format='json', HTTP_HOST='localhost')
        return r.status_code, (r.json().get('results') or [{}])[0]

    base = {'op_type': 'intervention.consommation_ligne', 'client_ts': '2026-10-01T09:30:00Z',
            'payload': {'intervention': iv.id, 'ligne': ligne.id, 'quantite_utilisee': 8}}
    # Témoin : forme du contrat partagé (base_updated_at présent) -> conflit attendu.
    code_t, res_t = _sync(dict(base, client_op_id=str(uuid.uuid4()), base_updated_at=lu_par_terminal))
    ligne.refresh_from_db()
    apres_temoin = ligne.quantite_utilisee
    # Forme réellement produite par l'écran (patchLigne : aucun meta.baseUpdatedAt).
    code_e, res_e = _sync(dict(base, client_op_id=str(uuid.uuid4())))
    ligne.refresh_from_db()
    print(f"témoin(base_updated_at) http={code_t} status={res_t.get('status')} ligne={apres_temoin} ; "
          f"écran(sans base) http={code_e} status={res_e.get('status')} ligne={ligne.quantite_utilisee} (en ligne: 12) ; "
          f"detail_temoin={res_t!r} detail_ecran={res_e!r}")
    repro = (res_t.get('status') == 'conflit' and res_e.get('status') == 'applied'
             and ligne.quantite_utilisee == Decimal('8'))
    return {'repro': repro, 'temoin': res_t.get('status'), 'ecran': res_e.get('status'),
            'quantite_finale': str(ligne.quantite_utilisee)}
