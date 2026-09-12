"""Lectures du module GRC & Conformité (NTGRC).

Point d'entrée UNIQUE de lecture pour les autres apps. Toute fonction est
bornée à une société (multi-tenant) — jamais de lecture cross-société.
"""
from __future__ import annotations

#: NTGRC4 — un « mois » de rétention vaut 30 jours. Choix DÉLIBÉRÉ : la
#: rétention se raisonne en ordres de grandeur légaux (24/36/120 mois), et une
#: arithmétique calendaire exacte ferait dépendre le résultat du mois de
#: lancement du balayage — un objet basculerait « échu » ou non selon qu'on
#: passe en février ou en juillet. 30 jours est stable et reproductible.
JOURS_PAR_MOIS = 30


def politiques_retention_actives(types_objet):
    """NTGRC4 — politiques de rétention ACTIVES pour ces types d'objet.

    Balayage SYSTÈME (toutes sociétés) : ``core.retention`` exécute une
    politique par NOM, pas par société, et c'est à chaque politique de scoper
    elle-même. On renvoie donc des tuples explicitement porteurs de leur
    société, jamais un queryset non borné laissé à l'appelant.

    Renvoie une liste de dicts ``{company, type_objet, jours, action}``,
    triée de façon déterministe.
    """
    from .models import PolitiqueRetentionObjet

    if isinstance(types_objet, str):
        types_objet = [types_objet]
    qs = (PolitiqueRetentionObjet.objects
          .filter(actif=True, type_objet__in=list(types_objet))
          .select_related('company')
          .order_by('company_id', 'type_objet', 'id'))
    return [
        {
            'company': p.company,
            'politique_id': p.pk,
            'type_objet': p.type_objet,
            'jours': int(p.duree_conservation_mois) * JOURS_PAR_MOIS,
            'action': p.action_echeance,
        }
        for p in qs
    ]


def politiques_retention_de_societe(company):
    """Politiques de rétention d'UNE société (lecture bornée, écrans GRC)."""
    from .models import PolitiqueRetentionObjet

    return (PolitiqueRetentionObjet.objects
            .filter(company=company)
            .order_by('type_objet', 'id'))


def holds_actifs(company, aujourdhui=None):
    """NTGRC8 — mises sous séquestre ACTIVES de la société (liste)."""
    from .models import LegalHold

    qs = LegalHold.objects.filter(
        company=company, statut=LegalHold.STATUT_ACTIF).order_by('id')
    return [h for h in qs if h.est_actif(aujourdhui)]


def _resoudre_filtre(company, type_objet, filtre):
    """Ids couverts par UN filtre de périmètre, via les selectors des apps.

    Deux formes reconnues, volontairement explicites (jamais un mini-langage
    de requête qui laisserait un séquestre « couvrir » on ne sait quoi) :
      * ``{"ids": [1, 2]}`` — désignation directe ;
      * ``{"identifiant": "a@b.ma"}`` — la personne, résolue par le
        ``selectors.py`` de l'app cible (aucun import de ses modèles).
    Un type d'objet ou un filtre inconnu ne couvre RIEN (ensemble vide) — un
    séquestre mal saisi ne doit jamais geler tout le tenant par accident.
    """
    filtre = filtre or {}
    ids = set()

    brut = filtre.get('ids')
    if isinstance(brut, (list, tuple)):
        for valeur in brut:
            try:
                ids.add(int(valeur))
            except (TypeError, ValueError):
                continue

    identifiant = (filtre.get('identifiant') or '').strip()
    if identifiant:
        if type_objet == 'crm_client':
            from apps.crm.selectors import client_ids_par_identifiant
            ids.update(client_ids_par_identifiant(company, identifiant))
        elif type_objet == 'crm_lead':
            from apps.crm.selectors import lead_ids_par_identifiant
            ids.update(lead_ids_par_identifiant(company, identifiant))
    return ids


def _documents_ged_sous_hold(company):
    """Ids des documents déjà gelés côté GED (GED24) — COMPOSITION.

    Le séquestre transverse n'ignore pas celui de la GED et ne le duplique pas
    non plus : il le LIT par son selector. Best-effort — si la GED est
    indisponible, le reste du périmètre reste résolu.
    """
    try:
        from apps.ged.selectors import legal_holds_for_company
        return {
            hold.document_id
            for hold in legal_holds_for_company(company).filter(actif=True)
        }
    except Exception:  # noqa: BLE001 - GED absente/indisponible
        return set()


def objets_sous_hold(company, aujourdhui=None):
    """NTGRC8 — ensemble des objets gelés de la société.

    Renvoie ``{type_objet: set(ids)}`` : le périmètre des séquestres
    transverses ACTIFS, PLUS les documents déjà gelés par ``ged.LegalHold``
    (sous la clé ``ged_document``).
    """
    couverture = {}
    for hold in holds_actifs(company, aujourdhui):
        for entree in (hold.perimetre or []):
            if not isinstance(entree, dict):
                continue
            type_objet = (entree.get('type_objet') or '').strip()
            if not type_objet:
                continue
            ids = _resoudre_filtre(company, type_objet, entree.get('filtre'))
            if ids:
                couverture.setdefault(type_objet, set()).update(ids)

    documents = _documents_ged_sous_hold(company)
    if documents:
        couverture.setdefault('ged_document', set()).update(documents)
    return couverture


def est_sous_hold(company, type_objet, objet_id, aujourdhui=None):
    """Cet objet précis est-il gelé ? (raccourci de ``objets_sous_hold``)."""
    try:
        objet_id = int(objet_id)
    except (TypeError, ValueError):
        return False
    return objet_id in objets_sous_hold(company, aujourdhui).get(
        type_objet, set())


def matrice_risques(company, residuelle=False):
    """NTGRC13 — grille 5×5 des risques, comptée par case.

    Renvoie ``{'cases': [{probabilite, impact, criticite, nombre}],
    'total': n}`` — les 25 cases sont TOUJOURS présentes (une case vide vaut
    0), sinon la heatmap se déformerait selon les données. Les risques CLOS
    sont exclus : une matrice de risques montre ce qui est encore ouvert.
    """
    from django.db.models import Count

    from .models import RisqueEntreprise

    champ_p = 'probabilite_residuelle' if residuelle else 'probabilite'
    champ_i = 'impact_residuel' if residuelle else 'impact'
    comptes = {
        (ligne[champ_p], ligne[champ_i]): ligne['nombre']
        for ligne in (RisqueEntreprise.objects
                      .filter(company=company)
                      .exclude(statut=RisqueEntreprise.STATUT_CLOS)
                      .values(champ_p, champ_i)
                      .annotate(nombre=Count('id')))
    }
    bornes = range(RisqueEntreprise.ECHELLE_MIN,
                   RisqueEntreprise.ECHELLE_MAX + 1)
    cases = [
        {
            'probabilite': p,
            'impact': i,
            'criticite': p * i,
            'nombre': comptes.get((p, i), 0),
        }
        for p in bornes for i in bornes
    ]
    return {'cases': cases, 'total': sum(c['nombre'] for c in cases)}


def plans_en_retard(company, aujourdhui=None):
    """NTGRC14 — plans de traitement dont l'échéance est passée et non faits.

    Le retard est calculé sur la DATE, pas lu du champ ``statut`` : un statut
    se périme dès que personne ne le met à jour, et le tableau de bord du
    risque afficherait alors « tout va bien » sur des actions abandonnées.
    """
    from django.utils import timezone

    from .models import PlanTraitementRisque

    jour = aujourdhui or timezone.now().date()
    return (PlanTraitementRisque.objects
            .filter(company=company, echeance__lt=jour)
            .exclude(statut=PlanTraitementRisque.STATUT_FAIT)
            .select_related('risque')
            .order_by('echeance', 'id'))


def violations_echeance_72h_depassee(company, now=None):
    """NTGRC6 — violations dont le délai légal de notification est DÉPASSÉ.

    « Dépassée » = échéance (détection + 72 h) passée ET notification CNDP
    requise ET pas encore notifiée. Une violation déjà notifiée, ou pour
    laquelle la notification n'est pas requise, n'est PAS en retard — on ne
    crie pas au dépassement là où il n'y a pas d'obligation.
    """
    from django.utils import timezone

    from .models import ViolationDonnees

    now = now or timezone.now()
    return (ViolationDonnees.objects
            .filter(company=company,
                    notification_cndp_requise=True,
                    date_notification_cndp__isnull=True,
                    date_echeance_72h__lt=now)
            .exclude(statut__in=[ViolationDonnees.STATUT_NOTIFIEE,
                                 ViolationDonnees.STATUT_CLOTUREE])
            .order_by('date_echeance_72h', 'id'))
