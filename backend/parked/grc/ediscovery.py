"""NTGRC31 — recherche e-discovery transverse (lecture seule).

Module SÉPARÉ de ``selectors.py`` À DESSEIN. L'e-discovery est le seul point
de ``grc`` qui lit le journal d'activité (``apps.audit.selectors``), et
``apps.ventes.retention`` lit, lui, ``grc.selectors`` (politiques de
rétention). Laisser les deux dans le même module créait le chemin transitif
``ventes → grc.selectors → audit`` que le contrat import-linter « Business-core
ventes never imports the audit satellite » interdit (M4). Le contrat reste
donc STRICT — rien n'a été ajouté à ``ignore_imports`` : c'est le code qui a
été rangé. Ne JAMAIS ré-exporter ces fonctions depuis ``selectors.py``, cela
recréerait l'arête.

Lecture seule, scopée société ; chaque périmètre passe par le ``selectors.py``
de l'app cible, jamais par ses modèles.
"""

#: Périmètres interrogeables par la recherche e-discovery. Ensemble FERMÉ :
#: une app absente d'ici n'est jamais fouillée par accident, et une valeur
#: inconnue envoyée par l'appelant ne devient pas un scan sauvage.
APPS_E_DISCOVERY = ('crm_client', 'crm_lead', 'audit_log', 'ged_document')


def _resultats_crm(company, terme, type_objet):
    """Ids CRM correspondant au terme, via ``crm.selectors`` (jamais models).

    Le terme est résolu comme IDENTIFIANT de personne (email ou téléphone) :
    c'est ce que ``crm.selectors`` sait faire de façon fiable et indexée. Une
    recherche par nom libre traverserait toute la table sans index et
    ramènerait des homonymes — dans un dossier de contentieux, c'est pire que
    rien.
    """
    from apps.crm.selectors import (
        client_ids_par_identifiant, lead_ids_par_identifiant,
    )

    resolveur = (client_ids_par_identifiant if type_objet == 'crm_client'
                 else lead_ids_par_identifiant)
    return [
        {'id': objet_id, 'libelle': f'{type_objet} #{objet_id}',
         'horodatage': None}
        for objet_id in resolveur(company, terme)
    ]


def _resultats_audit(company, terme, debut, fin):
    """Lignes du journal d'activité, via ``audit.selectors`` (jamais models)."""
    from apps.audit.selectors import rechercher_journal

    return [
        {
            'id': ligne.pk,
            'libelle': (ligne.object_repr or ligne.detail or
                        ligne.get_action_display()),
            'horodatage': (ligne.timestamp.isoformat()
                           if ligne.timestamp else None),
        }
        for ligne in rechercher_journal(company, terme, debut, fin)
    ]


def _resultats_ged(user, terme):
    """Documents GED, via ``ged.selectors.search_documents`` — ACL RESPECTÉE.

    La recherche documentaire de la GED est bornée par les droits de coffre de
    l'utilisateur. On passe donc l'UTILISATEUR, jamais la seule société : une
    recherche e-discovery ne doit pas devenir le chemin détourné qui ouvre les
    coffres auxquels l'appelant n'a pas accès. Sans utilisateur, la GED est
    simplement omise du périmètre (et le dit).

    Best-effort : la recherche plein-texte dépend d'un index Postgres ; son
    indisponibilité ne doit pas faire échouer toute la recherche.
    """
    if user is None:
        return []
    try:
        from apps.ged.selectors import search_documents

        return [
            {
                'id': document.pk,
                'libelle': getattr(document, 'nom', '') or f'#{document.pk}',
                'horodatage': (document.created_at.isoformat()
                               if getattr(document, 'created_at', None)
                               else None),
            }
            for document in search_documents(user, terme)[:200]
        ]
    except Exception:  # noqa: BLE001 - GED/plein-texte indisponible
        return []


def rechercher_e_discovery(company, terme, apps=None, periode=None,
                           user=None, now=None):
    """NTGRC31 — recherche transverse horodatée, prête pour un dossier.

    ``apps`` : liste de périmètres parmi ``APPS_E_DISCOVERY`` (défaut : tous).
    ``periode`` : dict ``{debut, fin}`` (datetimes) appliqué aux résultats qui
    portent une date — le journal d'activité et la GED. Les objets métier
    (clients, leads) n'ont pas de « date d'apparition » pertinente ici : les
    filtrer sur une période donnerait l'illusion d'une exhaustivité qui
    n'existe pas.

    ``user`` : nécessaire pour fouiller la GED (son ACL de coffre est
    respectée). Sans lui, ``ged_document`` renvoie une liste vide et
    ``perimetres_omis`` le DIT — jamais un zéro silencieux qu'on prendrait
    pour « rien trouvé ».

    Renvoie ``{'terme', 'apps', 'periode', 'resultats', 'total',
    'perimetres_omis', 'genere_le'}`` — un jeu de résultats groupé par app,
    horodaté, directement exportable.
    """
    from django.utils import timezone

    maintenant = now or timezone.now()
    terme = (terme or '').strip()
    demandes = [a for a in (apps or APPS_E_DISCOVERY)
                if a in APPS_E_DISCOVERY]
    if not demandes:
        demandes = list(APPS_E_DISCOVERY)

    periode = periode or {}
    debut, fin = periode.get('debut'), periode.get('fin')

    resultats = {}
    omis = []
    if terme:
        for perimetre in demandes:
            if perimetre in ('crm_client', 'crm_lead'):
                resultats[perimetre] = _resultats_crm(
                    company, terme, perimetre)
            elif perimetre == 'audit_log':
                resultats[perimetre] = _resultats_audit(
                    company, terme, debut, fin)
            elif perimetre == 'ged_document':
                if user is None:
                    resultats[perimetre] = []
                    omis.append('ged_document')
                else:
                    resultats[perimetre] = _resultats_ged(user, terme)
    else:
        resultats = {perimetre: [] for perimetre in demandes}

    return {
        'terme': terme,
        'apps': demandes,
        'periode': {
            'debut': debut.isoformat() if debut else None,
            'fin': fin.isoformat() if fin else None,
        },
        'resultats': resultats,
        'total': sum(len(lignes) for lignes in resultats.values()),
        'perimetres_omis': omis,
        'genere_le': maintenant.isoformat(),
    }
