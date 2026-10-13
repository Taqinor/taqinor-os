"""ENF1 — prépare la base JETABLE du job `api-fuzz`.

À lancer depuis ``backend/django_core``, après seed_demo + seed_catalogue :
    FUZZ_PASSWORD=... python ../../scripts/fuzz/prepare_fuzz_env.py ETAT.json

1. Crée/actualise le compte dédié ``fuzz_admin`` (admin, protégé) dans la
   société démo ``taqinor-demo`` — jamais ``demo_admin`` : le fuzzeur écrit
   partout, y compris sur les utilisateurs et la société ; un compte à lui
   seul garde ``demo_admin`` (e2e, QA nocturne) hors de portée et donne au
   crochet ``before_call`` un id précis à protéger. Le mot de passe est
   ALÉATOIRE, tiré par le workflow (``FUZZ_PASSWORD``, masqué) — jamais en
   dur.
2. Inventorie, pour chaque NOM de champ clé étrangère des modèles Django,
   les ids qui EXISTENT dans la société de fuzz (cluster C12 « Clé primaire
   0 non valide ») ; lus par ``scripts/fuzz/schemathesis_hooks.py``.
3. ENF11 — sème UNE ligne par modèle référencé que la base démo n'a pas
   (``SEMEURS``) et inventorie des ids PAR CHEMIN (``REGLES_PAR_CHEMIN``)
   quand un même nom de champ vise des modèles différents selon l'app.
4. Écrit l'état (ids du compte, de la société, tables des ids FK) en JSON.

Refuse de tourner hors DEBUG (même garde qu'ERR88 sur seed_demo).
"""
from __future__ import annotations

import json
import os
import sys

USERNAME = 'fuzz_admin'
SLUG_DEMO = 'taqinor-demo'
MAX_IDS_PAR_CHAMP = 25


def demarrer_django():
    sys.path.insert(0, os.getcwd())
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'erp_agentique.settings.dev')
    import django
    django.setup()


def preparer_compte(company, password):
    from django.apps import apps
    from django.core.management import call_command

    user_model = apps.get_model('authentication', 'CustomUser')
    user, _ = user_model.objects.get_or_create(
        username=USERNAME,
        defaults={'email': 'fuzz_admin@taqinor.local', 'company': company},
    )
    user.company = company
    user.role_legacy = user_model.ROLE_ADMIN
    user.is_staff = True
    user.is_active = True
    user.is_protected = True
    user.set_password(password)
    user.save()
    user.societes_autorisees.add(company)
    # Rattache le rôle système « admin » (comptes sans rôle fin, init_roles).
    call_command('init_roles')
    user.refresh_from_db()
    return user


def _a_un_champ_company(modele):
    return any(getattr(f, 'name', None) == 'company'
               for f in modele._meta.get_fields())


def _ids_existants(modele, company, cache):
    from django.apps import apps

    if modele in cache:
        return cache[modele]
    company_model = apps.get_model('authentication', 'Company')
    ids = set()
    try:
        qs = modele._default_manager.all()
        if modele is company_model:
            qs = qs.filter(pk=company.pk)
        elif _a_un_champ_company(modele):
            qs = qs.filter(company=company)
        valeurs = qs.order_by('pk').values_list('pk', flat=True)
        ids = {v for v in valeurs[:MAX_IDS_PAR_CHAMP]
               if isinstance(v, int) and not isinstance(v, bool)}
    except Exception as exc:  # table absente / manager exotique : ignoré
        print(f'  (ignoré) {modele._meta.label}: {exc}', file=sys.stderr)
    cache[modele] = ids
    return ids


def _cibles_par_nom():
    from django.apps import apps

    cibles = {}
    for modele in apps.get_models():
        for champ in modele._meta.get_fields():
            # ENF11 — les M2M DIRECTS (``entites_visibles``…) sont des FK du
            # corps comme les autres : leurs ids doivent être connus aussi
            # (``concrete`` est faux pour un M2M, qui n'a pas de colonne).
            directe_m2m = (getattr(champ, 'many_to_many', False)
                           and not getattr(champ, 'auto_created', False))
            if not (getattr(champ, 'is_relation', False)
                    and (getattr(champ, 'concrete', False) or directe_m2m)):
                continue
            cible = champ.related_model
            if cible is None or isinstance(cible, str):
                continue
            noms = {champ.name}
            if champ.many_to_one or champ.one_to_one:
                noms.add(champ.attname)
            for nom in noms - {'id', 'pk'}:
                cibles.setdefault(nom, set()).add(cible)
    return cibles


# ── ENF11 — un objet RÉEL par modèle référencé (seed du fuzz) ────────────
# Les lanes ont mesuré des « API rejected schema-compliant request » dus à
# une base de fuzz SANS ligne du modèle visé : le fuzzeur envoyait ``lot: 0``,
# ``dashboard: 0``… et l'API répondait 400, à raison. Chaque semeur crée UNE
# ligne minimale de la société de fuzz si elle n'en a aucune (idempotent),
# dans un point de sauvegarde : un échec est journalisé, jamais bloquant.

def _modele(label):
    from django.apps import apps

    return apps.get_model(label)


def _premier(label, company, **filtres):
    return (_modele(label).objects.filter(company=company, **filtres)
            .order_by('pk').first())


def _semer(nom, fabrique):
    from django.db import transaction

    try:
        with transaction.atomic():
            objet = fabrique()
        print(f'  seed {nom} : id {getattr(objet, "pk", None)}')
        return objet
    except Exception as exc:  # donnée de seed impossible : on continue
        print(f'  (seed ignoré) {nom} : {exc}', file=sys.stderr)
        return None


def _semer_lot(company, user):
    existant = _premier('stock.LotEntrepot', company)
    if existant is not None:
        return existant
    produit = _premier('stock.Produit', company)
    if produit is None:
        raise ValueError('aucun produit dans la société de fuzz')
    return _modele('stock.LotEntrepot').objects.create(
        company=company, produit=produit, numero_lot='FUZZ-LOT-0001',
        created_by=user)


SEMEURS = (
    ('stock.LotEntrepot', _semer_lot),
)


def semer_objets_references(company, user):
    for nom, fabrique in SEMEURS:
        _semer(nom, lambda f=fabrique: f(company, user))


# ── ENF11 — ids par CHEMIN : un même nom de champ vise des modèles différents
# selon l'app (``lot`` = stock.LotEntrepot ici, ventes.LotDevis ailleurs ;
# ``tag`` = records.Tag ou ged.DocumentTag…). La table par nom (intersection
# ou union) donnait alors des ids d'un AUTRE modèle. Chaque règle :
# (motif du gabarit de chemin, champs du corps/de la requête, modèle,
#  filtre optionnel ``f(qs, company) -> qs``, longueur max d'une liste).
REGLES_PAR_CHEMIN = (
    (r'^/api/django/stock/', ('lot', 'lot_id'), 'stock.LotEntrepot',
     None, None),
)


def inventorier_ids_par_chemin(company):
    regles = []
    for motif, champs, label, filtre, maxi in REGLES_PAR_CHEMIN:
        try:
            qs = _modele(label)._default_manager.all()
            if _a_un_champ_company(qs.model):
                qs = qs.filter(company=company)
            if filtre is not None:
                qs = filtre(qs, company)
            ids = [v for v in qs.order_by('pk').values_list('pk', flat=True)
                   .distinct()[:MAX_IDS_PAR_CHAMP]
                   if isinstance(v, int) and not isinstance(v, bool)]
        except Exception as exc:  # modèle absent / filtre cassé : ignoré
            print(f'  (règle ignorée) {motif} {champs}: {exc}',
                  file=sys.stderr)
            continue
        if ids:
            regles.append({'motif': motif, 'champs': list(champs),
                           'ids': ids, 'max': maxi})
        else:
            print(f'  (règle sans id) {motif} {champs} -> {label}',
                  file=sys.stderr)
    return regles


def inventorier_ids_fk(company):
    cache = {}
    table = {}
    for nom, modeles in sorted(_cibles_par_nom().items()):
        ensembles = [_ids_existants(m, company, cache) for m in modeles]
        ensembles = [s for s in ensembles if s]
        if not ensembles:
            continue
        # Un même nom peut viser plusieurs modèles : on préfère les ids
        # valides pour TOUS (intersection), à défaut l'union (meilleur
        # effort).
        choisis = set.intersection(*ensembles) or set.union(*ensembles)
        table[nom] = sorted(choisis)[:MAX_IDS_PAR_CHAMP]
    return table


def main():
    if len(sys.argv) != 2:
        sys.exit('usage : prepare_fuzz_env.py <fichier_etat.json>')
    password = os.environ.get('FUZZ_PASSWORD', '')
    if len(password) < 16:
        sys.exit('FUZZ_PASSWORD absent ou trop court')
    demarrer_django()
    from django.apps import apps
    from django.conf import settings

    if not settings.DEBUG:
        sys.exit('refusé hors DEBUG : base de fuzz jetable uniquement')
    company = apps.get_model('authentication', 'Company').objects.get(
        slug=SLUG_DEMO)
    user = preparer_compte(company, password)
    semer_objets_references(company, user)
    table = inventorier_ids_fk(company)
    regles = inventorier_ids_par_chemin(company)
    etat = {
        'username': USERNAME,
        'user_id': user.pk,
        'company_id': company.pk,
        # ENF1b — rôle du compte, protégé par le crochet ``before_call``.
        'role_id': user.role_id,
        'fk_ids': table,
        # ENF11 — ids par chemin (prioritaires sur ``fk_ids``).
        'fk_ids_chemin': regles,
    }
    with open(sys.argv[1], 'w', encoding='utf-8') as fh:
        json.dump(etat, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f'{USERNAME} prêt (id {user.pk}, rôle {user.role_id}, '
          f'société {company.pk}) ; {len(table)} noms de champs FK '
          'avec ids connus')


if __name__ == '__main__':
    main()
