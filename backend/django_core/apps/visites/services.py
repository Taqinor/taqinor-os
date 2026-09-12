"""Écritures/orchestration du module « Visites terrain » (``apps.visites``).

VT3 — LE FEU VERT DU BUREAU D'ÉTUDES
------------------------------------
Deux transitions, deux notifications au COMMERCIAL de la visite (primitive
``apps.notifications`` existante — jamais un second système de messages) :
« validée » (feu vert, il peut passer au calepinage) et « à refaire » (une
action lui est demandée, avec le motif). Ces deux transitions ne portent
AUCUN jugement automatisé : c'est un humain qui décide, le code se contente
d'enregistrer sa décision et de la faire savoir.

FRONTIÈRE M3 — cette app n'importe JAMAIS ``apps.crm.models`` et n'écrit
JAMAIS sur ``crm.Lead`` :

* le FEU VERT est publié comme ÉVÉNEMENT ``visite_validee`` (bus
  ``core.events``, M6) ; c'est ``apps.crm.receivers`` qui décide ce qu'il
  inscrit sur la fiche lead. Le ``lead_id`` voyage en entier, le récap est
  pré-calculé par le selector de cette app ;
* le chatter des AUTRES moments (création / terminée / à refaire) passe par
  ``journaliser_visite`` ci-dessous, qui délègue au ``services.py`` du CRM en
  import paresseux — le journal d'un lead appartient au lead.
"""


def _notifier_commercial_visite(visite, event_type, titre, corps):
    """Notifie le commercial de la visite. Best-effort, jamais bloquant."""
    destinataire = visite.commercial
    if destinataire is None:
        return None
    try:
        from apps.notifications.services import notify

        return notify(
            destinataire, event_type, titre, body=corps,
            link=f'/visites/{visite.pk}', company=visite.company)
    except Exception:  # pragma: no cover - défensif
        return None


def notifier_assignation(visite, acteur=None):
    """VTA7 — previent l'ASSIGNE qu'une visite l'attend.

    Appele a la creation ET a la reassignation : sans ce message, un commercial
    terrain ne decouvrait sa visite qu'en ouvrant l'app -- alors que sa journee
    vient justement de changer. Le lien pointe l'ecran de la visite dans l'app
    autonome (``/visites/<id>``).

    Trois prudences :

    * on ne notifie PAS l'acteur de sa propre assignation (s'assigner une
      visite ne merite pas une cloche) ;
    * pas de destinataire (visite non assignee) => rien a envoyer ;
    * best-effort -- la visite est deja creee/reassignee quand on arrive ici,
      une notification en echec ne doit pas defaire ce geste.

    La cloche elle-meme est ouverte a TOUT role (``apps.notifications`` la sert
    sous ``IsAnyRole``), donc un « Commercial terrain » -- qui n'a aucun droit
    CRM -- la recoit normalement.
    """
    destinataire = visite.commercial
    if destinataire is None:
        return None
    if acteur is not None and getattr(acteur, 'id', None) == destinataire.id:
        return None
    quand = ('' if visite.date_prevue is None
             else f" du {visite.date_prevue.strftime('%d/%m/%Y')}")
    return _notifier_commercial_visite(
        visite, 'visite_terrain_assignee',
        'Visite technique assignee',
        f'La visite{quand} chez « {visite.lead} » vous est assignee.')


def journaliser_visite(visite, user, moment, detail=''):
    """Pose la note de chatter du ``moment`` sur le LEAD de la visite.

    Le chatter d'un lead (``crm.LeadActivity``) est le journal COMMUN de tout
    ce qui lui arrive : la visite y écrit ses moments plutôt que d'ouvrir un
    second historique (la dette des 13 chatters hand-rollés). L'écriture
    appartient donc au CRM et passe par SON ``services.py`` (frontière M3,
    import paresseux) ; cette app n'importe jamais ``apps.crm.models``.

    Best-effort côté CRM : un chatter indisponible ne fait jamais échouer la
    transition métier qui vient d'aboutir.
    """
    from apps.crm import services as crm_services

    return crm_services.journaliser_visite(visite, user, moment, detail=detail)


def valider_visite(visite, user):
    """Feu vert calepinage : la visite passe VALIDÉE et devient lecture seule.

    VTA5 — le retour vers le lead se fait par ÉVÉNEMENT (``visite_validee``,
    bus ``core.events``), plus par un appel direct : c'est ``apps.crm`` qui
    décide, dans SON ``receivers.py``, ce qu'il inscrit sur la fiche. Le récap
    est PRÉ-CALCULÉ ici (le selector de cette app en est la source de vérité)
    et le ``lead_id`` voyage en ENTIER — l'app visites ne fait plus aucun écrit
    sur ``crm.Lead``.
    """
    from core.events import visite_validee

    from . import selectors
    from .models import VisiteTerrain

    visite.statut = VisiteTerrain.Statut.VALIDEE
    visite.save(update_fields=['statut'])
    visite_validee.send(
        sender=VisiteTerrain, visite=visite, lead_id=visite.lead_id,
        user=user, recap=selectors.recap_visite_terrain(visite))
    _notifier_commercial_visite(
        visite, 'visite_terrain_validee',
        'Visite technique validée',
        f'La visite du lead « {visite.lead} » a reçu le feu vert du bureau '
        "d'études.")
    return visite


def renvoyer_visite(visite, user, *, photos=None, mesures=None, motif=''):
    """Renvoie la visite au commercial avec le détail EXACT de ce qu'il refaire.

    ``photos`` — ids de ``VisiteMedia`` à reprendre ; ``mesures`` — liste de
    ``{'categorie': ..., 'code': ...}`` à re-relever. Le ``motif`` est
    obligatoire (validé côté sérialiseur) et il est recopié sur CHAQUE élément
    marqué, pour que la tuile porte elle-même son explication.

    Renvoie un message d'erreur FR si un id de photo ne correspond à rien sur
    cette visite (l'erreur NOMME ce qui cloche), sinon ``''``.
    """
    from . import visite_checklist as checklist
    from .models import VisiteTerrain

    ids = [int(pk) for pk in (photos or [])]
    medias = list(visite.medias.filter(pk__in=ids)) if ids else []
    if len(medias) != len(set(ids)):
        connus = sorted(str(media.pk) for media in medias)
        return ('Une ou plusieurs photos demandées n’appartiennent pas à cette '
                'visite. Photos reconnues : '
                + (', '.join(connus) if connus else 'aucune') + '.')

    for media in medias:
        media.a_refaire = True
        media.motif_refaire = motif
        media.save(update_fields=['a_refaire', 'motif_refaire'])

    # Une mesure « à refaire » est une mesure à RE-RELEVER : on la vide, donc
    # la complétude serveur la redemande d'elle-même — aucun second registre
    # d'état à tenir synchrone.
    stockees = dict(visite.mesures if isinstance(visite.mesures, dict) else {})
    touchee = False
    for demande in (mesures or []):
        categorie = (demande or {}).get('categorie')
        code = (demande or {}).get('code')
        if checklist.mesure(categorie, code) is None:
            continue
        bloc = dict(stockees.get(categorie) or {})
        if code in bloc:
            bloc[code] = None
            stockees[categorie] = bloc
            touchee = True
    if touchee:
        visite.mesures = stockees

    visite.statut = VisiteTerrain.Statut.A_REFAIRE
    champs = ['statut', 'mesures'] if touchee else ['statut']
    visite.save(update_fields=champs)
    journaliser_visite(visite, user, 'a_refaire', detail=f'Motif : {motif}')
    _notifier_commercial_visite(
        visite, 'visite_terrain_a_refaire',
        'Visite technique à refaire',
        f'La visite du lead « {visite.lead} » revient à refaire. '
        f'Motif : {motif}')
    return ''


# ── VTA10 — LA SAISIE DES MESURES, UNE SEULE FOIS ────────────────────────────
#
# La validation ET l'écriture des mesures vivent ICI, pas dans la vue : le même
# geste arrive par DEUX portes — le PATCH en ligne
# (``/visites/visites/<id>/mesures/``) et le REJEU hors-ligne du moteur
# ``apps.offlinesync`` (op ``visite.mesures``). Deux copies de ces règles
# seraient deux vérités : la vue et le handler appellent la même fonction.
#
# L'écriture est « last-write-wins » (elle POSE des valeurs, jamais un
# incrément) : rejouer deux fois la même opération donne exactement le même
# état — c'est ce que le moteur hors-ligne exige de tout handler.

def valeur_mesure(declaration, brute):
    """Convertit/valide UNE valeur de mesure. Renvoie ``(valeur, message)``.

    ``message`` NOMME le champ fautif en français (règle maison) ; il vaut
    ``None`` quand la valeur est acceptée. Aucun SEUIL technique n'est jugé
    ici : on vérifie la NATURE d'une mesure, jamais si elle est « suffisante ».
    """
    from decimal import Decimal, InvalidOperation

    from . import visite_checklist as checklist

    if brute is None or brute == '':
        return None, None
    nature = declaration['nature']
    if nature == checklist.NOMBRE:
        try:
            nombre = Decimal(str(brute))
        except (InvalidOperation, ValueError, TypeError):
            return None, (f"« {declaration['libelle']} » attend un nombre "
                          f'(reçu : {brute!r}).')
        if nombre < 0:
            return None, (f"« {declaration['libelle']} » ne peut pas être "
                          'négatif.')
        return float(nombre), None
    if nature == checklist.BOOLEEN:
        if isinstance(brute, bool):
            return brute, None
        texte = str(brute).strip().lower()
        if texte in ('true', '1', 'oui'):
            return True, None
        if texte in ('false', '0', 'non'):
            return False, None
        return None, f"« {declaration['libelle']} » attend oui ou non."
    if nature == checklist.CHOIX:
        texte = str(brute).strip()
        if texte not in declaration['choix']:
            options = ', '.join(declaration['choix'])
            return None, (f"« {declaration['libelle']} » : valeur inconnue "
                          f'« {texte} ». Choix possibles : {options}.')
        return texte, None
    return str(brute), None


def marquer_en_cours(visite):
    """Un brouillon (ou une visite à refaire) devient « en cours ».

    Déclenché par la première contribution réelle du terrain — photo, mesure
    ou pointage d'arrivée.
    """
    from .models import VisiteTerrain

    if visite.statut in (VisiteTerrain.Statut.BROUILLON,
                         VisiteTerrain.Statut.A_REFAIRE):
        visite.statut = VisiteTerrain.Statut.EN_COURS
        visite.save(update_fields=['statut'])
    return visite


def enregistrer_mesures(visite, categorie, valeurs):
    """POSE les mesures d'UNE catégorie. Renvoie ``(visite, erreurs)``.

    ``erreurs`` est le dict ``{champ: message FR}`` servi tel quel en 400 par
    la vue — chaque message NOMME son champ. Rien n'est écrit dès qu'une seule
    valeur est refusée : la catégorie part entière ou pas du tout.
    """
    from . import visite_checklist as checklist

    declaration = checklist.categorie(categorie)
    if declaration is None or not declaration['mesures']:
        return None, {'categorie': ('Catégorie de mesures inconnue '
                                    f'« {categorie} ».')}
    if not isinstance(valeurs, dict):
        return None, {'valeurs': ('Les valeurs doivent être un objet '
                                  '{champ: valeur}.')}

    connus = {champ['code']: champ for champ in declaration['mesures']}
    erreurs = {}
    propres = {}
    for code, brute in valeurs.items():
        champ = connus.get(code)
        if champ is None:
            erreurs[code] = (f'Champ inconnu dans la catégorie '
                             f'« {declaration["libelle"]} ».')
            continue
        valeur, message = valeur_mesure(champ, brute)
        if message:
            erreurs[code] = message
        else:
            propres[code] = valeur
    if erreurs:
        return None, erreurs

    stockees = visite.mesures if isinstance(visite.mesures, dict) else {}
    bloc = dict(stockees.get(categorie) or {})
    bloc.update(propres)
    stockees = dict(stockees)
    stockees[categorie] = bloc
    visite.mesures = stockees
    visite.save(update_fields=['mesures'])
    marquer_en_cours(visite)
    return visite, {}


def appliquer_mesures_hors_ligne(company, user, visite_id, categorie, valeurs):
    """Rejeu HORS-LIGNE de la saisie de mesures — ``(resultat, motif)``.

    C'est la porte d'entrée que ``apps.offlinesync`` appelle (jamais les
    modèles de cette app). Elle refait, dans l'ordre, TOUTES les gardes de la
    route en ligne — sinon la file hors-ligne serait un contournement de
    permission :

    1. la SOCIÉTÉ : la visite est cherchée bornée ``company`` (posée serveur),
       donc l'id d'un autre locataire est indiscernable d'un id inconnu ;
    2. la portée dure « mes visites » (VTA6) : sans ``visites_valider``, on ne
       peut écrire que sur SA visite ;
    3. le gel VT3 : une visite validée reste en lecture seule.

    ``motif`` est un message FR prêt à afficher, ``None`` en cas de succès.
    """
    from core.permissions import _user_has_or_legacy

    from .models import VisiteTerrain

    visite = (VisiteTerrain.objects
              .filter(company=company, pk=visite_id).first())
    if visite is None:
        return None, 'Visite inconnue.'
    if (visite.commercial_id != getattr(user, 'id', None)
            and not _user_has_or_legacy(user, 'visites_valider')):
        return None, ('Cette visite est assignée à un autre commercial : '
                      'vous ne pouvez pas saisir ses mesures.')
    if not visite.modifiable:
        return None, visite.raison_lecture_seule

    visite, erreurs = enregistrer_mesures(visite, categorie, valeurs)
    if erreurs:
        return None, ' '.join(str(message) for message in erreurs.values())
    return {'visite': visite.id, 'categorie': categorie,
            'mesures': visite.mesures.get(categorie, {})}, None
