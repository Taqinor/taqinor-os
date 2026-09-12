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


def controles_a_tester(company, within=0, aujourdhui=None):
    """NTGRC17 — contrôles ACTIFS dont le test est dû (ou le sera sous N j).

    L'échéance d'un contrôle = date de son dernier test EFFICACE + la fenêtre
    de sa fréquence (un mensuel : 30 jours). Un contrôle JAMAIS testé
    efficacement est TOUJOURS dû — c'est le cas qui compte le plus, et un
    « pas de test donc pas d'échéance » le rendrait invisible.

    Un test DÉFICIENT ne remet pas le compteur à zéro : le contrôle reste dû
    tant qu'on n'a pas démontré qu'il fonctionne.

    Renvoie une liste de dicts ``{controle, echeance, dernier_test}`` triée
    par échéance (la plus ancienne d'abord).
    """
    from django.utils import timezone

    from .models import ControleInterne, TestControle

    jour = aujourdhui or timezone.now().date()
    limite = jour + timezone.timedelta(days=max(0, int(within or 0)))

    controles = list(ControleInterne.objects.filter(
        company=company, actif=True).order_by('code', 'id'))
    if not controles:
        return []

    derniers = {}
    for test in (TestControle.objects
                 .filter(company=company,
                         controle_id__in=[c.pk for c in controles],
                         resultat=TestControle.RESULTAT_EFFICACE,
                         date_realisee__isnull=False)
                 .order_by('controle_id', 'date_realisee')):
        derniers[test.controle_id] = test

    dus = []
    for controle in controles:
        dernier = derniers.get(controle.pk)
        if dernier is None:
            echeance = None  # jamais testé : dû sans condition
        else:
            echeance = dernier.date_realisee + timezone.timedelta(
                days=controle.fenetre_jours)
            if echeance > limite:
                continue
        dus.append({
            'controle': controle,
            'echeance': echeance,
            'dernier_test': dernier,
        })
    dus.sort(key=lambda d: (d['echeance'] is not None, d['echeance'] or jour))
    return dus


def risques_a_revoir(company, within=0, aujourdhui=None):
    """NTGRC15 — risques dont la revue est due (ou le sera sous ``within`` j).

    ``date_revue_prevue`` vide = aucune cadence posée : le risque n'est pas
    « en retard de revue », il n'a simplement jamais eu de rendez-vous — on ne
    le fait pas remonter pour éviter de noyer les vraies échéances. Les
    risques CLOS sont exclus.
    """
    from django.utils import timezone

    from .models import RisqueEntreprise

    jour = aujourdhui or timezone.now().date()
    limite = jour + timezone.timedelta(days=max(0, int(within or 0)))
    return (RisqueEntreprise.objects
            .filter(company=company, date_revue_prevue__isnull=False,
                    date_revue_prevue__lte=limite)
            .exclude(statut=RisqueEntreprise.STATUT_CLOS)
            .order_by('date_revue_prevue', 'id'))


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


# ── NTGRC20 — attestations de lecture des politiques ────────────────────────

def employes_cibles(company, politique):
    """Ids des dossiers employés VISÉS par une politique (via ``rh.selectors``).

    Le dénominateur d'un taux d'attestation est la POPULATION CIBLE, pas le
    nombre de personnes qui ont déjà cliqué. La cible est lue chez ``rh`` par
    son ``selectors.py`` — jamais un import de ``rh.models``.

    * ``tous`` → tous les dossiers ACTIFS de la société ;
    * ``departement`` → ceux dont le département correspond (par nom, sans
      tenir compte de la casse, ou par identifiant) ;
    * ``role`` → les dossiers reliés à un compte portant le rôle visé.

    Une cible que l'on ne sait pas résoudre renvoie un ensemble VIDE : mieux
    vaut un taux affiché « sans cible » qu'un taux calculé sur une population
    inventée.
    """
    from apps.rh.selectors import dossiers_actifs

    from .models import PolitiqueInterne

    if company is None or politique is None:
        return set()

    ids = set(dossiers_actifs(company).values_list('id', flat=True))
    cible = getattr(politique, 'cible', None)
    valeur = (getattr(politique, 'cible_valeur', '') or '').strip()

    if cible == PolitiqueInterne.CIBLE_TOUS:
        return ids
    if not valeur:
        return set()

    if cible == PolitiqueInterne.CIBLE_DEPARTEMENT:
        from apps.rh.selectors import departements_par_employe

        mapping = departements_par_employe(company, ids)
        cherche = valeur.casefold()
        return {
            employe_id
            for employe_id, info in mapping.items()
            if (info.get('departement_nom') or '').casefold() == cherche
            or str(info.get('departement_id') or '') == valeur
        }

    if cible == PolitiqueInterne.CIBLE_ROLE:
        from django.contrib.auth import get_user_model

        from apps.rh.selectors import dossier_employe_for_user

        cibles = set()
        utilisateurs = get_user_model().objects.filter(
            company=company, is_active=True, role_legacy=valeur)
        for user_id in utilisateurs.values_list('id', flat=True):
            dossier = dossier_employe_for_user(company, user_id)
            if dossier is not None and dossier.pk in ids:
                cibles.add(dossier.pk)
        return cibles

    return set()


def taux_attestation(company, politique):
    """NTGRC20 — taux d'attestation de la VERSION COURANTE d'une politique.

    Renvoie ``{'version', 'cible', 'attestants', 'taux_pct', 'manquants'}``.

    Le taux porte sur la version PUBLIÉE en cours : une attestation de la v2
    ne vaut pas pour la v3 (c'est tout l'intérêt de versionner). Une politique
    jamais publiée (``version`` = 0) renvoie 0 attestant et un taux de 0 — pas
    une division par zéro, et surtout pas un « 100 % » flatteur sur une
    politique que personne n'a jamais pu lire.
    """
    from .models import AttestationPolitique

    version = int(getattr(politique, 'version', 0) or 0)
    cibles = employes_cibles(company, politique) if version else set()
    attestants = set()
    if version:
        lignes = (AttestationPolitique.objects
                  .filter(company=company, politique=politique,
                          version_attestee=version)
                  .exclude(employe_ref='')
                  .values_list('employe_ref', flat=True))
        for ref in lignes:
            try:
                attestants.add(int(ref))
            except (TypeError, ValueError):
                continue

    dedans = cibles & attestants
    total = len(cibles)
    taux = round(100.0 * len(dedans) / total, 1) if total else 0.0
    return {
        'version': version,
        'cible': total,
        'attestants': len(dedans),
        'taux_pct': taux,
        'manquants': sorted(cibles - attestants),
    }


def attestations_manquantes(company):
    """NTGRC21 — qui doit encore attester quoi, par politique PUBLIÉE.

    Renvoie une liste de dicts ``{politique, version, manquants}`` où
    ``manquants`` est la liste triée des ids de dossiers employés visés qui
    n'ont pas attesté la version COURANTE. Les politiques sans manquant sont
    omises (une relance vide n'existe pas) ; les brouillons et les politiques
    obsolètes ne sont jamais relancés — on ne réclame pas la lecture d'un
    texte qui peut encore changer ou qui n'est plus en vigueur.
    """
    from .models import PolitiqueInterne

    if company is None:
        return []
    resultats = []
    publiees = (PolitiqueInterne.objects
                .filter(company=company,
                        statut=PolitiqueInterne.STATUT_PUBLIEE,
                        version__gte=1)
                .order_by('titre', 'id'))
    for politique in publiees:
        taux = taux_attestation(company, politique)
        manquants = taux['manquants']
        if not manquants:
            continue
        resultats.append({
            'politique': politique,
            'version': taux['version'],
            'manquants': manquants,
        })
    return resultats


# ── NTGRC27 — analyses d'impact (AIPD) ──────────────────────────────────────

def traitements_dpia_manquante(company):
    """NTGRC27 — traitements à HAUT RISQUE sans AIPD VALIDÉE.

    Lecture du registre des traitements par le sélecteur FIN de ``core``
    (``core.selectors.traitements_haut_risque``) — jamais par une règle
    « qu'est-ce qu'un traitement sensible » redupliquée ici.

    Un traitement compte comme couvert UNIQUEMENT si son AIPD est au statut
    « validée ». Un brouillon ou une analyse « à réviser » ne protège
    personne : c'est exactement le cas que ce sélecteur existe pour faire
    remonter.

    Renvoie une liste de dicts ``{traitement, analyse}`` (``analyse`` = la
    dernière AIPD connue, ou ``None`` si aucune n'existe), triée par code.
    """
    from core.selectors import traitements_haut_risque

    from .models import AnalyseImpactDPIA

    if company is None:
        return []
    traitements = list(traitements_haut_risque(company))
    if not traitements:
        return []

    refs = {str(t.pk) for t in traitements}
    analyses = {}
    for analyse in (AnalyseImpactDPIA.objects
                    .filter(company=company, traitement_ref__in=refs)
                    .order_by('id')):
        # La plus RÉCENTE fait foi (order_by croissant + écrasement).
        analyses[analyse.traitement_ref] = analyse

    manquants = []
    for traitement in traitements:
        analyse = analyses.get(str(traitement.pk))
        if (analyse is not None
                and analyse.statut == AnalyseImpactDPIA.STATUT_VALIDEE):
            continue
        manquants.append({'traitement': traitement, 'analyse': analyse})
    return manquants


# ── NTGRC28 — cockpit de conformité du DPO ──────────────────────────────────

#: Au-delà de cette criticité (grille 5×5), un risque est en ZONE ROUGE.
#: 15 = 3×5 ou 5×3 : le premier palier où un risque est à la fois probable et
#: grave. En-dessous, tout remonterait et le cockpit ne dirait plus rien.
SEUIL_CRITICITE_CRITIQUE = 15


def tableau_bord_dpo(company, now=None):
    """NTGRC28 — les SEPT compteurs de conformité, en UN seul appel.

    Un DPO ouvrait sept écrans pour savoir s'il était à jour ; ce sélecteur
    répond d'un coup. LECTURE SEULE et sans aucune donnée personnelle : des
    COMPTES et des ÉCHÉANCES, jamais un nom ni un email — un tableau de bord
    de conformité qui étale l'identité des personnes concernées serait
    lui-même un manquement.

    Les compteurs, dans l'ordre :
      1. ``dsr_ouverts`` — demandes de droits en cours + délais restants ;
      2. ``violations_72h`` — violations sous obligation de notification ;
      3. ``consentements_retires_mois`` — retraits du mois en cours ;
      4. ``politiques_non_attestees`` — politiques publiées non lues par tous ;
      5. ``controles_a_tester`` — contrôles internes dont le test est dû ;
      6. ``risques_critiques`` — risques résiduels en zone rouge ;
      7. ``traitements_sans_dpia`` — traitements sensibles sans AIPD validée.
    """
    from django.utils import timezone

    from core.models import ConsentRecord, DataSubjectRequest

    from .models import RisqueEntreprise, ViolationDonnees

    maintenant = now or timezone.now()
    if company is None:
        return {}

    # 1. Demandes de droits ouvertes + délai restant (jours, jamais négatif
    #    masqué : une demande en retard affiche un nombre NÉGATIF, c'est
    #    exactement l'information qui doit sauter aux yeux).
    ouvertes = (DataSubjectRequest.objects
                .filter(company=company)
                .exclude(statut__in=[DataSubjectRequest.STATUT_TRAITEE,
                                     DataSubjectRequest.STATUT_REFUSEE])
                .order_by('date_echeance', 'id'))
    dsr = []
    en_retard = 0
    for demande in ouvertes:
        echeance = demande.date_echeance
        jours = None
        if echeance is not None:
            jours = (echeance - maintenant).days
            if jours < 0:
                en_retard += 1
        dsr.append({
            'type': demande.kind,
            'statut': demande.statut,
            'echeance': echeance.isoformat() if echeance else None,
            'jours_restants': jours,
        })

    # 2. Violations : celles qui sont encore sous obligation de notification.
    violations = (ViolationDonnees.objects
                  .filter(company=company,
                          notification_cndp_requise=True,
                          date_notification_cndp__isnull=True)
                  .exclude(statut__in=[ViolationDonnees.STATUT_NOTIFIEE,
                                       ViolationDonnees.STATUT_CLOTUREE]))
    violations_depassees = violations.filter(
        date_echeance_72h__lt=maintenant).count()

    # 3. Consentements RETIRÉS depuis le début du mois courant.
    #    ``occurred_at`` (l'instant où la PERSONNE a agi) est facultatif : on
    #    retombe sur ``created_at`` (l'instant où NOUS l'avons enregistré)
    #    plutôt que d'ignorer la ligne — un retrait sans date saisie reste un
    #    retrait, et le compter à zéro serait le pire des deux mondes.
    from django.db.models.functions import Coalesce

    debut_mois = maintenant.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)
    retraits = (ConsentRecord.objects
                .filter(company=company, granted=False)
                .annotate(quand_effectif=Coalesce('occurred_at', 'created_at'))
                .filter(quand_effectif__gte=debut_mois)
                .count())

    return {
        'dsr_ouverts': len(dsr),
        'dsr_en_retard': en_retard,
        'dsr_details': dsr,
        'violations_72h': violations.count(),
        'violations_72h_depassees': violations_depassees,
        'consentements_retires_mois': retraits,
        'politiques_non_attestees': len(attestations_manquantes(company)),
        'controles_a_tester': len(controles_a_tester(company)),
        'risques_critiques': (
            RisqueEntreprise.objects
            .filter(company=company,
                    criticite_residuelle__gte=SEUIL_CRITICITE_CRITIQUE)
            .exclude(statut=RisqueEntreprise.STATUT_CLOS)
            .count()),
        'traitements_sans_dpia': len(traitements_dpia_manquante(company)),
        'calcule_le': maintenant.isoformat(),
    }


# ── NTGRC29 — score de maturité conformité ──────────────────────────────────

#: Pondération des six critères du score (somme = 100).
#:
#: Les poids ne sont pas « au feeling » : les deux premiers critères sont ceux
#: qu'un contrôleur demande EN PREMIER (le registre des traitements et la
#: preuve que les contrôles tournent), les quatre suivants mesurent la
#: RÉACTION (délais tenus, politiques lues, violations notifiées, AIPD à jour).
PONDERATION_CONFORMITE = {
    'ropa': 20,
    'controles': 20,
    'dsr': 15,
    'politiques': 15,
    'violations': 15,
    'dpia': 15,
}

#: Champs qui rendent une ligne de RoPA réellement exploitable. Un registre
#: où il ne reste que le code et la finalité ne prouve rien à personne.
CHAMPS_ROPA_REQUIS = ('finalite', 'base_legale', 'categories_donnees',
                      'duree_conservation')


def _pourcent(numerateur, denominateur, sans_donnee=0.0):
    """Pourcentage borné 0-100 ; ``sans_donnee`` quand il n'y a rien à mesurer.

    La valeur par défaut du « rien à mesurer » est un CHOIX explicite, jamais
    le même partout : ce qu'on doit DÉCLARER (registre, contrôles, politiques)
    vaut 0 quand c'est vide — une absence de déclaration n'est pas une
    conformité ; ce à quoi on doit RÉAGIR (demandes, violations, AIPD) vaut
    100 quand il n'y a rien eu — on ne reproche pas un retard à qui n'a rien
    reçu.
    """
    if not denominateur:
        return float(sans_donnee)
    return round(max(0.0, min(100.0, 100.0 * numerateur / denominateur)), 1)


def score_conformite(company, now=None):
    """NTGRC29 — score de maturité conformité (0-100) + détail par critère.

    Renvoie ``{'score', 'details': [{critere, libelle, score, poids,
    points, commentaire}], 'calcule_le'}``. Le total est la somme des
    ``score × poids / 100`` — borné 0-100 par construction.

    Aucun chiffre n'est inventé : chaque critère dit SUR QUOI il porte
    (numérateur/dénominateur réels) dans son commentaire, pour qu'un score
    médiocre soit actionnable au lieu d'être vexant.
    """
    from django.utils import timezone

    from core.models import DataSubjectRequest, RegistreTraitement
    from core.selectors import traitements_haut_risque

    from .models import ControleInterne, PolitiqueInterne, ViolationDonnees

    maintenant = now or timezone.now()
    if company is None:
        return {'score': 0.0, 'details': [], 'calcule_le': None}

    details = []

    # 1. RoPA — part des traitements ACTIFS réellement renseignés.
    traitements = list(RegistreTraitement.objects.filter(
        company=company, actif=True))
    complets = sum(
        1 for t in traitements
        if all((getattr(t, champ, '') or '').strip()
               for champ in CHAMPS_ROPA_REQUIS))
    details.append({
        'critere': 'ropa',
        'libelle': 'Registre des traitements renseigné',
        'score': _pourcent(complets, len(traitements)),
        'poids': PONDERATION_CONFORMITE['ropa'],
        'commentaire': (f'{complets} traitement(s) complet(s) sur '
                        f'{len(traitements)} actif(s).'),
    })

    # 2. Contrôles internes — part des contrôles actifs NON dus (donc testés
    #    efficacement dans leur fenêtre de fréquence).
    total_controles = ControleInterne.objects.filter(
        company=company, actif=True).count()
    dus = len(controles_a_tester(company, aujourdhui=maintenant.date()))
    details.append({
        'critere': 'controles',
        'libelle': 'Contrôles internes testés et efficaces',
        'score': _pourcent(total_controles - dus, total_controles),
        'poids': PONDERATION_CONFORMITE['controles'],
        'commentaire': (f'{total_controles - dus} contrôle(s) à jour sur '
                        f'{total_controles} actif(s).'),
    })

    # 3. Demandes de droits — part traitée DANS les délais légaux.
    dsr_total = dsr_dans_delai = 0
    for demande in DataSubjectRequest.objects.filter(company=company):
        echeance = demande.date_echeance
        if echeance is None:
            continue
        close = demande.statut in (DataSubjectRequest.STATUT_TRAITEE,
                                   DataSubjectRequest.STATUT_REFUSEE)
        if not close and echeance >= maintenant:
            continue  # encore dans les temps : rien à juger.
        dsr_total += 1
        if close and (demande.traitee_le or maintenant) <= echeance:
            dsr_dans_delai += 1
    details.append({
        'critere': 'dsr',
        'libelle': 'Demandes de droits traitées dans les délais',
        'score': _pourcent(dsr_dans_delai, dsr_total, sans_donnee=100.0),
        'poids': PONDERATION_CONFORMITE['dsr'],
        'commentaire': (f'{dsr_dans_delai} demande(s) dans les délais sur '
                        f'{dsr_total} arrivée(s) à échéance.'),
    })

    # 4. Politiques — moyenne des taux d'attestation des politiques PUBLIÉES.
    publiees = list(PolitiqueInterne.objects.filter(
        company=company, statut=PolitiqueInterne.STATUT_PUBLIEE,
        version__gte=1))
    if publiees:
        moyenne = round(sum(
            taux_attestation(company, p)['taux_pct']
            for p in publiees) / len(publiees), 1)
    else:
        moyenne = 0.0
    details.append({
        'critere': 'politiques',
        'libelle': 'Politiques publiées et attestées',
        'score': moyenne,
        'poids': PONDERATION_CONFORMITE['politiques'],
        'commentaire': (f'{len(publiees)} politique(s) publiée(s), taux '
                        f"d'attestation moyen {moyenne} %."),
    })

    # 5. Violations — part notifiée AVANT l'échéance de 72 h. Le dénominateur
    #    ne retient que celles dont l'échéance est passée ou déjà notifiées :
    #    on ne reproche pas un retard à une violation d'il y a deux heures.
    violations = ViolationDonnees.objects.filter(
        company=company, notification_cndp_requise=True)
    v_total = v_a_temps = 0
    for violation in violations:
        echeance = violation.date_echeance_72h
        notifiee = violation.date_notification_cndp
        if notifiee is None and (echeance is None or echeance >= maintenant):
            continue
        v_total += 1
        if notifiee is not None and echeance is not None \
                and notifiee <= echeance:
            v_a_temps += 1
    details.append({
        'critere': 'violations',
        'libelle': 'Violations notifiées sous 72 h',
        'score': _pourcent(v_a_temps, v_total, sans_donnee=100.0),
        'poids': PONDERATION_CONFORMITE['violations'],
        'commentaire': (f'{v_a_temps} violation(s) notifiée(s) à temps sur '
                        f'{v_total} à notifier.'),
    })

    # 6. AIPD — part des traitements à haut risque COUVERTS par une analyse
    #    validée.
    haut_risque = traitements_haut_risque(company).count()
    manquantes = len(traitements_dpia_manquante(company))
    details.append({
        'critere': 'dpia',
        'libelle': 'Analyses d\'impact (AIPD) à jour',
        'score': _pourcent(haut_risque - manquantes, haut_risque,
                           sans_donnee=100.0),
        'poids': PONDERATION_CONFORMITE['dpia'],
        'commentaire': (f'{haut_risque - manquantes} traitement(s) à haut '
                        f'risque couvert(s) sur {haut_risque}.'),
    })

    for detail in details:
        detail['points'] = round(detail['score'] * detail['poids'] / 100.0, 2)
    total = round(sum(d['points'] for d in details), 1)
    return {
        'score': max(0.0, min(100.0, total)),
        'details': details,
        'calcule_le': maintenant.isoformat(),
    }


# ── NTGRC30 — cartographie des flux de données ──────────────────────────────

def flux_hors_maroc(company):
    """NTGRC30 — flux SORTANT du Maroc, à surveiller.

    Un transfert international n'est pas interdit, il est CONDITIONNÉ : il
    faut pouvoir nommer la garantie qui l'encadre. Ce sélecteur remonte donc
    TOUS les flux déclarés hors Maroc — y compris (et surtout) ceux SANS
    garantie déclarée, qui sont précisément ceux qu'il faut régulariser.

    Trié garanties manquantes d'abord : c'est la file de travail, pas une
    liste alphabétique.
    """
    from .models import FluxDonnees

    if company is None:
        return FluxDonnees.objects.none()
    return (FluxDonnees.objects
            .filter(company=company, transfert_hors_maroc=True)
            .order_by('garanties', 'pays_destination', 'id'))
