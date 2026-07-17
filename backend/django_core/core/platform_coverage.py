"""ARC41 — Matrice de dérive des surfaces plateforme (étend YEVNT7).

``core.event_coverage`` (YEVNT7) garde le BUS d'événements : un signal sans
abonné, un ``EventType`` sans producteur = rouge. Ce qui manque est la couche
SURFACES : les INCOHÉRENCES INTER-MANIFESTES (ARC28) ne sont détectées par
personne. Exemples visés par ARC41 :

* un modèle chatter-isé (dans ``record_targets``) mais INTROUVABLE en recherche
  (absent de ``searchable_models``) — « Contrat chatter-isé mais invisible » ;
* un modèle cherchable mais SANS chatter (l'inverse).

Ce module CROISE les manifestes ``core.platform`` (ARC28) et produit une
**matrice de dérive** : par modèle ``'app.model'``, quelles surfaces le couvrent,
et quelles incohérences en découlent. Comme ``event_coverage``, il est
DATA-DRIVEN et sans DB (il lit les manifestes déjà collectés, aucun import d'app
métier — ``core`` reste fondation) et applique la politique « ROUGE seulement sur
RÉGRESSION » : une ``BASELINE`` gelée liste les incohérences CONNUES aujourd'hui
(remontées en warnings) ; toute incohérence NOUVELLE au-delà de la baseline fait
échouer le test.

Il ne DUPLIQUE PAS YEVNT7 : le bus d'événements reste couvert par
``event_coverage`` ; ARC41 ne regarde QUE les surfaces déclaratives ARC28.
"""
from __future__ import annotations

from core import platform


# ── Règles de cohérence inter-surfaces ────────────────────────────────────────
# Chaque règle porte sur l'espace de clés ``'app.model'`` PARTAGÉ par
# ``record_targets`` et ``searchable_models`` (les deux surfaces qui indexent le
# même identifiant de modèle). On ne croise PAS ici les surfaces à espace de clés
# DIFFÉRENT (customfields = ``'model'`` nu, import_specs = clés d'entité libres) :
# les relier exigerait une table de correspondance métier codée dans ``core``, ce
# que le contrat de fondation interdit. Ces surfaces-là restent visibles dans la
# matrice informative (:func:`platform_matrix`) sans règle de dérive croisée.

# Code de règle -> (surface source, surface cible, libellé FR de l'incohérence).
DRIFT_RULES = {
    # Un modèle qui a un chatter DOIT être trouvable dans la recherche globale.
    'chatter_sans_recherche': (
        'record_targets', 'searchable_models',
        "chatter-isé (records) mais introuvable en recherche globale"),
    # Un modèle cherchable DOIT avoir un chatter (sinon l'utilisateur le trouve
    # mais ne peut ni le commenter ni y attacher une pièce).
    'recherche_sans_chatter': (
        'searchable_models', 'record_targets',
        "cherchable mais sans chatter/records (ni notes ni pièces jointes)"),
}


# ── BASELINE gelée — incohérences CONNUES aujourd'hui (warnings, pas d'échec) ──
# Chaque entrée = ``(model, code_regle)``. Politique « rouge sur régression » :
# une incohérence NOUVELLE (hors baseline) fait échouer le test ; les entrées
# ci-dessous sont tolérées (dérives héritées, remontées en warnings). RETIRER une
# entrée quand la surface manquante est enfin câblée (le test le vérifie :
# une entrée baseline qui n'est PLUS une incohérence réelle devient rouge).
#
# ARC29 — l'entrée ARC28 pilote (``'contrats.contrat', 'chatter_sans_recherche'``)
# a été RETIRÉE : Contrat est désormais cherchable (apps/contrats/platform.py
# déclare 'contrats.contrat' dans searchable_models, apps/reporting/search.py
# le résout via _spec_contrat) — la dérive n'existe plus, la garder aurait menti.
# En sens inverse, déclarer les surfaces RÉELLES de ventes/installations/sav/
# stock (ARC29) rend VISIBLES des dérives HÉRITÉES jusque-là silencieuses —
# elles préexistaient au registre, on les gèle ici au lieu de les masquer.
BASELINE_DRIFT: set[tuple[str, str]] = {
    # Cherchables SANS chatter générique (hérité — l'utilisateur les trouve
    # mais ne peut ni les commenter ni y joindre une pièce) : à retirer le
    # jour où ils entreront dans records.ALLOWED_TARGETS.
    ('sav.equipement', 'recherche_sans_chatter'),
    ('sav.contratmaintenance', 'recherche_sans_chatter'),
    # Chatter-isé SANS recherche globale (hérité, DC33) : à retirer le jour où
    # le fournisseur deviendra cherchable.
    ('stock.fournisseur', 'chatter_sans_recherche'),
    # ARC30 — la migration des 19 cibles records vers les manifestes rend
    # VISIBLES les cibles chatter-isées historiques jamais branchées sur la
    # recherche globale (dérives héritées, préexistantes au registre — la
    # recherche de ces modèles est un trou à combler modèle par modèle, chaque
    # câblage retirant son entrée ici).
    ('outillage.outillage', 'chatter_sans_recherche'),
    ('rh.dossieremploye', 'chatter_sans_recherche'),
    ('qhse.relevecontrole', 'chatter_sans_recherche'),
    ('qhse.nonconformite', 'chatter_sans_recherche'),
    ('kb.kbarticle', 'chatter_sans_recherche'),
    ('ged.document', 'chatter_sans_recherche'),
    ('flotte.vehicule', 'chatter_sans_recherche'),
    ('gestion_projet.projet', 'chatter_sans_recherche'),
    ('ao.appeloffre', 'chatter_sans_recherche'),
    # ODX17 (2026-07-13) — la Facture a migré ventes -> facturation (split
    # state-only). Sa cible chatter porte désormais le label `facturation.facture`
    # (ContentType du modèle déplacé) tandis que la recherche globale garde la
    # clé opaque historique `ventes.facture` (apps/reporting/search.py) — les
    # deux résolvent le MÊME modèle, la cohérence de label est un trou assumé
    # (retirer quand la clé de recherche sera relabelée aussi).
    ('facturation.facture', 'chatter_sans_recherche'),
    # ODX17 (2026-07-13) — le REVERS de l'entrée ci-dessus : la recherche
    # globale garde la clé opaque `ventes.facture` (apps/reporting/search.py)
    # alors que le chatter porte désormais `facturation.facture` — les deux
    # surfaces référencent le MÊME modèle déplacé, l'écart de label est assumé.
    ('ventes.facture', 'recherche_sans_chatter'),
    # SCA34 (2026-07-10) — pilote 1 du kit core.documents : l'ordre de
    # sous-traitance gagne le chatter générique (périmètre du pilote =
    # socle+chatter+PDF) ; son câblage en recherche globale
    # (apps/reporting/search.py) est un trou assumé à combler plus tard,
    # comme les 9 cibles héritées ci-dessus — retirer cette entrée le jour
    # où il deviendra cherchable.
    ('installations.ordresoustraitance', 'chatter_sans_recherche'),
    # SCA36 (2026-07-10) — pilote 3 du kit (dégradation gracieuse sans
    # totaux) : même dérive assumée que SCA34, même remède futur.
    ('installations.demandeachat', 'chatter_sans_recherche'),
    # NTIDE1 (2026-07-16) — l'idée gagne le chatter/tag générique records
    # (ARC8/FG9) ; son câblage en recherche globale est un trou assumé (même
    # dérive héritée que les cibles ci-dessus) — retirer le jour où l'idée
    # deviendra cherchable via apps/reporting/search.py.
    ('innovation.idee', 'chatter_sans_recherche'),
    # NTASS14/ARC26 — sinistre, police et attestation d'assurance sont
    # chatter-isés via records.Attachment (constat, rapport d'expertise,
    # contrat/attestation scannés) mais pas encore cherchables : dérive
    # assumée identique aux cibles ci-dessus — retirer le jour où assurances
    # entrera dans apps/reporting/search.py.
    ('assurances.declarationsinistre', 'chatter_sans_recherche'),
    ('assurances.policeassurance', 'chatter_sans_recherche'),
    ('assurances.attestationassurance', 'chatter_sans_recherche'),
    # NTCRD43 — LimiteCredit et DerogationCredit sont chatter-isés via records
    # (changement de limite NTCRD22, décision de dérogation) mais pas encore
    # cherchables : même dérive assumée — retirer le jour où crédit entrera
    # dans apps/reporting/search.py.
    ('credit.limitecredit', 'chatter_sans_recherche'),
    ('credit.derogationcredit', 'chatter_sans_recherche'),
}


def _surface_models(manifest, surface):
    """Ensemble des modèles ``'app.model'`` couverts par ``surface`` dans un manifeste."""
    return set(manifest.get(surface) or [])


def all_drift(manifests=None):
    """Toutes les incohérences inter-surfaces détectées.

    Renvoie un ``set`` de couples ``(model, code_regle)``. Un couple est présent
    quand ``model`` est dans la surface SOURCE d'une règle mais absent de sa
    surface CIBLE, agrégé sur TOUS les manifestes (un modèle peut être déclaré
    par un manifeste et pas un autre — l'union reflète la couverture réelle).
    """
    if manifests is None:
        manifests = platform.collect_platform_manifests()

    # Union par surface sur tous les manifestes.
    union: dict[str, set[str]] = {}
    for surface in ('record_targets', 'searchable_models'):
        acc: set[str] = set()
        for manifest in manifests.values():
            acc |= _surface_models(manifest, surface)
        union[surface] = acc

    drift: set[tuple[str, str]] = set()
    for code, (source, cible, _label) in DRIFT_RULES.items():
        for model in union[source]:
            if model not in union[cible]:
                drift.add((model, code))
    return drift


def new_drift(manifests=None):
    """Incohérences NOUVELLES (hors ``BASELINE_DRIFT``) — font échouer le test."""
    return all_drift(manifests) - BASELINE_DRIFT


def stale_baseline(manifests=None):
    """Entrées ``BASELINE_DRIFT`` qui ne sont PLUS des incohérences réelles.

    Une entrée gelée dont la surface manquante a été câblée doit être RETIRÉE de
    la baseline — sinon elle ment. Le test échoue tant qu'elle traîne."""
    return BASELINE_DRIFT - all_drift(manifests)


def platform_matrix(manifests=None):
    """Matrice de couverture des surfaces, par modèle ``'app.model'``.

    Renvoie une liste triée de dicts, un par modèle apparaissant dans AU MOINS
    une surface à espace ``'app.model'`` (record_targets / searchable_models /
    automation_state_fields), avec ses drapeaux de présence et les codes de
    dérive qui le concernent. Sert de sortie LISIBLE dans le test (comme la
    couverture d'``event_coverage``), pas de garde en soi.
    """
    if manifests is None:
        manifests = platform.collect_platform_manifests()

    searchable: set[str] = set()
    record: set[str] = set()
    automation: set[str] = set()
    for manifest in manifests.values():
        searchable |= _surface_models(manifest, 'searchable_models')
        record |= _surface_models(manifest, 'record_targets')
        automation |= {e['model'] for e in manifest.get('automation_state_fields') or []}

    drift = all_drift(manifests)
    tous = sorted(searchable | record | automation)
    rows = []
    for model in tous:
        codes = sorted(code for (m, code) in drift if m == model)
        rows.append({
            'model': model,
            'searchable': model in searchable,
            'record_target': model in record,
            'automation': model in automation,
            'drift': codes,
        })
    return rows


def format_matrix(manifests=None):
    """Rendu texte de la matrice (une ligne par modèle) pour la sortie de test."""
    lignes = ['modèle                          rech chat auto  dérive']
    for row in platform_matrix(manifests):
        lignes.append(
            f"{row['model']:<32}"
            f"{'X' if row['searchable'] else '·':<5}"
            f"{'X' if row['record_target'] else '·':<5}"
            f"{'X' if row['automation'] else '·':<6}"
            f"{','.join(row['drift']) or '—'}")
    return '\n'.join(lignes)
