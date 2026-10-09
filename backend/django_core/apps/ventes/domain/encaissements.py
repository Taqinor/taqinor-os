"""Encaissements — paiements, avances, retenues, mandats, liens de paiement.

L'argent qui ENTRE : enregistrement d'un paiement (simple, groupé, avec
retenue à la source), avances et leur ventilation, consolidation de
factures, mandats de prélèvement, liens de paiement publics et leur QR.

QJR69 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.
"""
from decimal import Decimal

from apps.stock.services import qr_svg_for

# Tolérance d'arrondi partagée par toutes les gardes d'argent de ce module :
# un centime, exactement comme le chemin unitaire (ERR72, `views/facture.py`)
# et comme `ventiler_avance`. JAMAIS élargie sans décision fondateur.
TOLERANCE_CENTIME = Decimal('0.01')


class LinkError(Exception):
    """AUD136 — refus de CRÉATION d'un lien de paiement, avec son motif.

    La garde vivait dans la vue (`views/facture.lien_paiement`) : tout autre
    appelant de `create_payment_link` — script, futur webhook, tâche — pouvait
    donc créer un lien sur une facture annulée ou soldée. Elle est descendue
    dans le service, qui la porte pour tous.
    """

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def marquer_facture_soldee(facture, *, montant=None, user=None, source='',
                           reste=None, force=False):
    """AUD102 — LE SERVICE UNIQUE DE BASCULE « PAYÉE » d'une ``Facture``.

    AUCUN autre site du domaine ventes ne doit poser ``Facture.Statut.PAYEE``
    (test de parité : ``apps/ventes/tests/test_aud102_bascule_payee.py``).
    Avant ce service, NEUF chemins basculaient la facture et seuls TROIS
    émettaient ``facture_payee`` — or c'est ``facture_payee``, pas
    ``facture_paid``, qui est LE signal à consommer (``core/events.py``). Un
    chemin d'argent encaissé ne soldait rien du tout (débit de mandat,
    pile parquée par AFAC19).

    Le service :

      * VERROUILLE la ligne facture (``select_for_update``) — deux
        encaissements concurrents ne peuvent plus émettre deux fois ;
      * refuse silencieusement une facture ANNULÉE et est IDEMPOTENT sur une
        facture déjà PAYÉE (jamais un second événement) ;
      * applique la garde CENTIME-PRÈS sur le résiduel : la facture ne bascule
        que si ``montant_du`` (ou le ``reste`` fourni par l'appelant, pour les
        assiettes particulières comme la retenue à la source XFAC4) est
        retombé à zéro à un centime près ;
      * ``force=True`` — et seulement là — saute cette garde : ce sont les
        deux gestes délibérés qui SOLDENT sans encaisser, « marquer payée »
        manuel (geste responsable/admin) et l'abandon de créance XFAC13 ;
      * ré-arme les relances (``reset_relance_escalation``) ;
      * émet ``facture_paid`` PUIS ``facture_payee`` exactement une fois (donc
        déclenche le lettrage compta).

    RÈGLE #4 : seul le statut de la Facture change ; aucun document n'est
    rendu, le moteur de devis n'est jamais touché.

    Renvoie ``True`` si la facture vient de basculer, ``False`` sinon.
    """
    from decimal import Decimal

    from django.db import transaction

    from apps.ventes.models import Facture

    with transaction.atomic():
        locked = Facture.objects.select_for_update().get(pk=facture.pk)
        if locked.statut in (Facture.Statut.ANNULEE, Facture.Statut.PAYEE):
            # AFAC23 — une facture close (soldée ou annulée) ne garde aucun
            # lien de paiement ouvert, même sur un rejeu idempotent.
            _fermer_liens_facture_close(locked)
            return False
        if locked.statut == Facture.Statut.BROUILLON:
            # AFAC9 — un BROUILLON ne bascule jamais PAYÉE (non émis).
            return False
        if not force:
            residuel = locked.montant_du if reste is None else Decimal(
                str(reste))
            if residuel > Decimal('0.01'):
                return False
        locked.statut = Facture.Statut.PAYEE
        locked.save(update_fields=['statut'])
        reset_relance_escalation(locked)
        montant_evenement = (
            locked.total_ttc if montant is None else Decimal(str(montant)))
        from core.events import facture_paid, facture_payee
        facture_paid.send(
            sender=Facture, facture=locked, montant=montant_evenement,
            company=locked.company)
        facture_payee.send(
            sender=Facture, instance=locked, company=locked.company)
        # AFAC23 (C-AFAC-018) — le SOLDE (paiement manuel, avoir, abandon,
        # ventilation…) ferme les liens « Payer en ligne » encore ouverts :
        # la page client ne réclame plus rien sur une facture soldée. Le lien
        # soldé par SON propre encaissement est déjà PAYÉ (pas touché).
        _fermer_liens_facture_close(locked)

    # L'instance de l'appelant reflète la bascule (elle n'est pas ``locked``).
    if facture.pk == locked.pk:
        facture.statut = Facture.Statut.PAYEE
    return True


def recalculer_statut_paiement(facture, *, user=None, source=''):
    """ATOT8 (C-ATOT-006) — LE service unique qui DÉRIVE le statut de
    paiement d'une facture de son reste dû (D-ATOT-4) : « payée » si et
    seulement si ``montant_du`` ≤ 0 (au centime).

      * reste dû nul → bascule PAYÉE par ``marquer_facture_soldee`` (verrou,
        idempotent, ``facture_payee`` émis UNE fois) ;
      * reste EXIGIBLE > 0 (CIQ214 : une retenue de garantie non libérée ne
        rouvre pas) → ÉMISE, ou EN_RETARD si l'échéance est dépassée — une
        facture PAYÉE dont un avoir est annulé revient au recouvrement ;
      * brouillon et annulée : jamais touchées.

    Appelé après création ET annulation d'avoir, et au rejet d'un paiement
    (réouverture extraite de ``recouvrement._rouvrir_facture_apres_rejet``).
    Idempotent. Renvoie le statut résultant."""
    from decimal import Decimal

    from django.utils import timezone

    from apps.ventes.models import Facture

    facture.refresh_from_db()
    if facture.statut in (Facture.Statut.ANNULEE, Facture.Statut.BROUILLON):
        return facture.statut
    if facture.montant_du <= Decimal('0.01'):
        marquer_facture_soldee(facture, user=user,
                               source=source or 'recalcul_statut')
        facture.refresh_from_db()
        return facture.statut
    if facture.montant_exigible <= 0:
        return facture.statut
    today = timezone.now().date()
    nouveau = (Facture.Statut.EN_RETARD
               if facture.date_echeance and facture.date_echeance < today
               else Facture.Statut.EMISE)
    if facture.statut != nouveau:
        facture.statut = nouveau
        facture.save(update_fields=['statut'])
    return facture.statut


def enregistrer_paiement(*, facture, montant, mode, date_paiement, user,
                         reference='', note=''):
    """Enregistre un ``Paiement`` MANUEL sur une facture EXISTANTE.

    Thin service exposé pour apps.pos (encaissement comptoir XPOS1/XPOS6) —
    même modèle/table que le paiement enregistré depuis l'écran facture,
    aucune duplication de logique.

    CAD122 — REFUSE un encaissement d'ACOMPTE sur une commande signée au
    domicile du client tant que le délai des articles 49 et 50 de la loi 31-08
    court (``AcompteAvantDelaiLegal``, message nommant la date). Une commande
    signée à distance ou au bureau n'est pas concernée."""
    _verifier_delai_acompte_domicile(facture, date_paiement)
    # AFAC9 — LA porte unique (émise / en retard seulement).
    exiger_facture_encaissable(facture, date_paiement)
    from apps.ventes.models import Paiement
    paiement = Paiement.objects.create(
        company=facture.company,
        facture=facture,
        montant=montant,
        date_paiement=date_paiement,
        mode=mode,
        reference=reference or '',
        note=note or '',
        created_by=user,
    )
    # YLEDG1 — événement documentaire générique (pose du seam pour
    # compta.ecriture_pour_paiement, jamais d'import de son service ici).
    from core.events import paiement_enregistre
    paiement_enregistre.send(
        sender=Paiement, instance=paiement, company=facture.company)
    return paiement


def arrondir_au_pas(montant, pas):
    """ZFAC11 — arrondit ``montant`` au multiple le plus proche de ``pas``.

    Pur (aucune I/O). ``pas <= 0`` (arrondi désactivé) renvoie ``montant``
    inchangé — comportement actuel strictement préservé. Arrondi « half-up »
    (0,025 monte à 0,05 pour un pas de 0,05). Renvoie un ``Decimal`` quantifié
    à 2 décimales.

    Déplacé tel quel depuis ``views/facture.py`` (qui le ré-exporte) pour que
    le service d'encaissement ci-dessous n'importe jamais une vue.
    """
    from decimal import ROUND_HALF_UP
    montant = Decimal(str(montant))
    pas = Decimal(str(pas or 0))
    if pas <= 0:
        return montant.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    nb_pas = (montant / pas).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return (nb_pas * pas).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def proposer_arrondi_caisse(facture, mode, reste=None):
    """ZFAC11 — propose le reste à payer ARRONDI au pas de caisse société.

    Ne s'applique QU'aux règlements en espèces et seulement si la société a
    configuré un pas (> 0). Renvoie un dict
    ``{montant_arrondi, ecart, pas, applicable}`` où ``ecart`` = résiduel non
    perçu (montant_du − montant_arrondi, jamais négatif) qui sera tracé comme
    un abandon « Arrondi espèces ». Hors espèces ou pas nul → ``applicable`` est
    ``False`` et ``montant_arrondi`` = reste à payer (aucun arrondi).

    ``reste`` : résiduel de référence explicite. Indispensable au moment de
    l'encaissement, où ``facture.montant_du`` (propriété vivante) inclut DÉJÀ
    le paiement tout juste enregistré — la proposition doit se calculer sur le
    reste AVANT paiement, sinon elle ne correspond jamais au montant réglé.

    Déplacé tel quel depuis ``views/facture.py`` (qui le ré-exporte).
    """
    from apps.parametres.models import CompanyProfile
    from apps.ventes.models import Paiement
    reste = facture.montant_du if reste is None else reste
    profile = CompanyProfile.get(company=facture.company)
    pas = getattr(profile, 'arrondi_caisse', None) or Decimal('0')
    if mode != Paiement.Mode.ESPECES or pas <= 0 or reste <= 0:
        return {
            'montant_arrondi': reste, 'ecart': Decimal('0'),
            'pas': pas, 'applicable': False,
        }
    montant_arrondi = arrondir_au_pas(reste, pas)
    # On ne perçoit jamais plus que le dû : si l'arrondi monte au-dessus du
    # reste, on redescend au pas inférieur (l'écart reste ≥ 0, jamais un
    # trop-perçu à gérer).
    if montant_arrondi > reste:
        montant_arrondi = montant_arrondi - pas
    if montant_arrondi < 0:
        montant_arrondi = Decimal('0')
    ecart = reste - montant_arrondi
    return {
        'montant_arrondi': montant_arrondi, 'ecart': ecart,
        'pas': pas, 'applicable': ecart > 0,
    }


class EncaissementRefuse(Exception):
    """Refus d'un encaissement manuel (message FR, prêt pour un 400)."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


# ── AFAC9 (C-AFAC-003/011/014) — LA porte unique d'encaissement ─────────────
MOTIF_NON_EMISE = "Facture non émise : émettez-la avant d'encaisser."
MOTIF_ANNULEE = 'Facture annulée : aucun encaissement possible.'
MOTIF_SOLDEE = 'Facture soldée : plus rien à encaisser.'


class FactureNonEncaissable(ValueError):
    """AFAC9 — refus de la porte unique d'encaissement (motif FR, 400).

    Sous-classe de ``ValueError`` : les chemins qui traduisent déjà
    ``ValueError`` en 400 (encaissement groupé) le refusent sans code neuf."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


def _jour_encaissement(date_paiement):
    """Date du paiement en ``date`` (une chaîne ISO venue d'un corps de
    requête est lue ; illisible ou absente ⇒ ``None`` = aujourd'hui)."""
    import datetime as _dt
    if isinstance(date_paiement, _dt.datetime):
        return date_paiement.date()
    if isinstance(date_paiement, _dt.date):
        return date_paiement
    if isinstance(date_paiement, str) and date_paiement.strip():
        try:
            return _dt.date.fromisoformat(date_paiement.strip()[:10])
        except ValueError:
            return None
    return None


def motif_non_encaissable(facture, date_paiement=None):
    """AFAC9 — pourquoi ``facture`` ne s'encaisse pas (phrase FR), ou ``None``.

    Seule une facture ÉMISE ou EN RETARD s'encaisse (contrat
    ``facturation/contract_samples/facture_encaissable.json``) ; un acompte
    d'un bon signé au domicile ne s'encaisse pas avant le J+7 de la loi 31-08
    (CAD122, D-AFAC-C7 : sur TOUT encaissement). Pure lecture : aucune requête
    hors la résolution ``devis.bon_commande`` d'une facture d'ACOMPTE."""
    from apps.ventes.models import AcompteAvantDelaiLegal, Facture

    statut = facture.statut
    if statut == Facture.Statut.BROUILLON:
        return MOTIF_NON_EMISE
    if statut == Facture.Statut.ANNULEE:
        return MOTIF_ANNULEE
    if statut == Facture.Statut.PAYEE:
        return MOTIF_SOLDEE
    try:
        _verifier_delai_acompte_domicile(
            facture, _jour_encaissement(date_paiement))
    except AcompteAvantDelaiLegal as exc:
        return str(exc)
    return None


def exiger_facture_encaissable(facture, date_paiement=None):
    """AFAC9 — LA porte : lève ``FactureNonEncaissable`` (motif FR) si la
    facture ne s'encaisse pas. Appelée par CHAQUE service qui crée un
    ``Paiement`` ou un lien de paiement sur une facture."""
    motif = motif_non_encaissable(facture, date_paiement)
    if motif:
        raise FactureNonEncaissable(motif)


def encaisser_sur_facture(*, facture, donnees, user):
    """LE chemin de l'encaissement MANUEL d'une facture (montant + date + mode).

    Corps extrait À L'IDENTIQUE de ``FactureViewSet.enregistrer_paiement``
    (``POST factures/{id}/enregistrer-paiement/``) pour qu'un second appelant —
    « Facturer » un devis accepté avec ses paiements déjà reçus
    (``facturer-complet``) — passe EXACTEMENT par le même code : verrou ERR72,
    garde sur-paiement au centime, escompte XFAC12, chatter, événement
    ``paiement_enregistre``, bascule « Payée » AUD102 (reset des relances
    U10), arrondi espèces ZFAC11 et tolérance XFAC13.

    ``donnees`` = les champs validés du paiement (``montant``,
    ``date_paiement``, ``mode``, ``reference``…) — jamais ``company``,
    ``facture`` ni ``created_by``, posés ici côté serveur.

    Lève ``EncaissementRefuse`` (rien n'est écrit). Renvoie
    ``(facture_verrouillee_rafraichie, paiement)``.
    """
    from django.db import transaction

    from apps.ventes.models import Facture, Paiement

    montant = donnees.get('montant')
    if montant is None or montant <= 0:
        raise EncaissementRefuse('Le montant du paiement doit être positif.')
    # ERR72 — la garde sur-paiement et l'écriture du paiement doivent être
    # sérialisées : on verrouille la ligne facture (select_for_update) puis
    # on lit le reste à payer, on contrôle, et on enregistre — le tout dans
    # une seule transaction. Sans le verrou, deux paiements concurrents
    # lisaient chacun l'ancien reste et passaient tous deux la garde.
    with transaction.atomic():
        locked = Facture.objects.select_for_update().get(pk=facture.pk)
        if locked.statut == Facture.Statut.ANNULEE:
            raise EncaissementRefuse(
                'Impossible d\'encaisser sur une facture annulée.')
        # AFAC9 — LA porte unique (brouillon, soldée, acompte CAD122 J+7).
        motif = motif_non_encaissable(locked, donnees.get('date_paiement'))
        if motif:
            raise EncaissementRefuse(motif)
        # Garde sur-paiement : refuser un encaissement qui dépasse le reste
        # à payer (TTC − déjà payé − avoirs). Tolérance d'un centime pour
        # les arrondis ; un montant égal au reste passe (solde la facture).
        reste = locked.montant_du
        # XFAC12 — escompte pour règlement anticipé : si la fenêtre est
        # atteinte (date_paiement <= émission + escompte_jours) ET que le
        # montant réglé correspond au NET après escompte (reste − escompte,
        # tolérance 1 centime), l'escompte se calcule automatiquement et
        # SOLDE la facture avec le règlement — jamais hors fenêtre (plein
        # tarif reste dû, comportement actuel inchangé).
        date_paiement = donnees.get('date_paiement')
        escompte_montant = Decimal('0')
        if locked.escompte_applicable(date_paiement):
            escompte_potentiel = locked.calcul_escompte(reste, date_paiement)
            net_attendu = reste - escompte_potentiel
            if abs(montant - net_attendu) <= TOLERANCE_CENTIME:
                escompte_montant = escompte_potentiel
                reste = net_attendu
        if montant - reste > TOLERANCE_CENTIME:
            raise EncaissementRefuse(
                f'Le paiement dépasse le reste à payer ({reste:.2f} MAD).')
        paiement = Paiement.objects.create(
            **donnees,
            facture=locked,
            company=locked.company,
            created_by=user,
            escompte_montant=escompte_montant,
        )
        # Chatter facture : trace l'encaissement (acteur côté serveur,
        # jamais lu du corps de la requête).
        from apps.ventes import activity
        activity.log_facture_paiement(locked, user, paiement)
        # YLEDG1 — événement documentaire générique (pose du seam pour
        # compta.ecriture_pour_paiement, jamais d'import de son service ici).
        from core.events import paiement_enregistre
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=locked.company)
        # Statut auto : intégralement réglée → « Payée ».
        # AUD102 (P2) — la bascule (garde centime-près, U10
        # reset_relance_escalation, YDOCF4 `facture_paid` + YEVNT6
        # `facture_payee`) vit DANS le service unique.
        locked.refresh_from_db()
        soldee = marquer_facture_soldee(
            locked, montant=montant, user=user,
            source='encaissement_facture')
        if not soldee and locked.statut != Facture.Statut.ANNULEE:
            # ZFAC11 — arrondi de caisse : un règlement EN ESPÈCES égal au
            # reste à payer arrondi au pas société (défaut 0 = désactivé,
            # comportement inchangé) solde la facture, l'écart d'arrondi
            # étant tracé comme un abandon « Arrondi espèces » (jamais
            # silencieux). Ne s'applique qu'aux espèces ; virement/chèque
            # l'ignorent. Passe AVANT la tolérance XFAC13 (motif dédié).
            mode = donnees.get('mode', Paiement.Mode.VIREMENT)
            # ``reste`` = résiduel AVANT ce paiement (capturé plus haut) —
            # montant_du est déjà retombé après la création du paiement.
            prop = proposer_arrondi_caisse(locked, mode, reste=reste)
            if (prop['applicable']
                    and abs(montant - prop['montant_arrondi']) <= TOLERANCE_CENTIME
                    and Decimal('0') < locked.montant_du <= prop['pas']):
                from apps.ventes.services import abandonner_solde_facture
                abandonner_solde_facture(
                    locked, motif=Facture.MotifAbandon.ARRONDI_CAISSE,
                    user=user, auto=True,
                )
                locked.refresh_from_db()
            else:
                # XFAC13 — tolérance société : un résiduel sous le seuil
                # (défaut 0 = désactivé, comportement inchangé) est abandonné
                # automatiquement à l'encaissement plutôt que de laisser la
                # facture « en retard » pour quelques centimes.
                from apps.parametres.models import CompanyProfile
                profile = CompanyProfile.get(company=locked.company)
                tolerance = getattr(
                    profile, 'tolerance_ecart_reglement', None) or Decimal('0')
                if tolerance > 0 and locked.montant_du <= tolerance:
                    from apps.ventes.services import abandonner_solde_facture
                    abandonner_solde_facture(
                        locked, motif=Facture.MotifAbandon.ECART_REGLEMENT,
                        user=user, auto=True,
                    )
                    locked.refresh_from_db()
    return locked, paiement


def facture_montant_du(facture):
    """Solde restant dû d'une facture (lecture, thin service pour apps.pos)."""
    return facture.montant_du


def affecter_encaissement_groupe(
        *, company, client, montant, mode, date_paiement, user, factures,
        reference='', repartition=None):
    """ZFAC6 — un seul règlement client réparti sur PLUSIEURS factures.

    Crée un ``Paiement`` par facture réglée : par défaut FIFO (la facture à
    l'échéance la plus ancienne d'abord, jusqu'à épuisement du montant) ; ou
    une répartition EXPLICITE si ``repartition`` (dict facture_id -> montant)
    est fournie. Toutes les factures doivent appartenir à ``company`` ET
    ``client`` (sinon ValueError — le viewset traduit en 400). Atomique :
    échec partiel = rollback total. Bascule le statut « Payée » sur toute
    facture intégralement soldée par ce geste (comportement identique à un
    encaissement facture-par-facture).

    AUD120 — bornes de la répartition explicite. Cette branche n'avait
    AUCUNE garde : ni la somme des parts contre le ``montant`` réellement
    encaissé, ni chaque part contre le reste dû de sa facture — alors que
    la branche FIFO plafonne déjà (``min(restant, reste_facture)``) et que
    le chemin unitaire refuse le sur-paiement sous verrou (ERR72). Un
    virement de 5 000 réparti en 3 000 + 4 000 créait 7 000 MAD de
    paiements, dont 2 000 n'existaient pas. Les deux bornes sont
    désormais posées (tolérance d'un centime, même formulation d'erreur
    que le chemin unitaire), et le reliquat FIFO n'est plus abandonné en
    silence : il devient une avance XFAC1 explicite, non affectée et
    ventilable plus tard."""
    from decimal import Decimal

    from django.db import transaction

    from apps.ventes.models import Facture
    from core.money import quantize_mad

    montant = quantize_mad(montant)
    if montant <= 0:
        raise ValueError("Le montant doit être positif.")
    if not factures:
        raise ValueError("Aucune facture fournie.")

    for f in factures:
        if f.company_id != company.id or f.client_id != client.id:
            raise ValueError(
                f"La facture {f.reference} n'appartient pas à ce client.")

    paiements = []
    with transaction.atomic():
        locked = list(
            Facture.objects.select_for_update()
            .filter(id__in=[f.id for f in factures])
        )
        by_id = {f.id: f for f in locked}
        # AFAC9 — LA porte unique, AVANT toute écriture : une facture listée
        # non encaissable (brouillon, annulée, acompte CAD122) refuse tout le
        # lot. Une facture déjà soldée n'absorbe rien (FIFO la sautait déjà).
        for facture in locked:
            if facture.statut == Facture.Statut.PAYEE:
                continue
            motif = motif_non_encaissable(facture, date_paiement)
            if motif:
                raise FactureNonEncaissable(
                    f"Facture {facture.reference} : {motif}")

        if isinstance(repartition, dict) and repartition:
            # Répartition explicite fournie par l'appelant. AUD120 — on
            # VALIDE tout avant d'écrire quoi que ce soit : aucune facture
            # ne doit voir un Paiement si une seule part est hors borne.
            parts = []
            for fid, part in repartition.items():
                facture = by_id.get(int(fid))
                if facture is None:
                    raise ValueError(f"Facture {fid} inconnue dans ce lot.")
                part = quantize_mad(part)
                if part <= 0:
                    continue
                parts.append((facture, part))
            total_parts = quantize_mad(
                sum((p for _, p in parts), Decimal('0')))
            if total_parts - montant > TOLERANCE_CENTIME:
                raise ValueError(
                    f"La répartition ({total_parts:.2f} MAD) dépasse le "
                    f"montant encaissé ({montant:.2f} MAD).")
            for facture, part in parts:
                reste_facture = facture.montant_du
                if part - reste_facture > TOLERANCE_CENTIME:
                    raise ValueError(
                        f"Le paiement dépasse le reste à payer "
                        f"({reste_facture:.2f} MAD).")
            for facture, part in parts:
                paiements.append(_creer_paiement_groupe(
                    facture, part, mode, date_paiement, user, reference))
            # AFAC8 (C-AFAC-010) — Σ parts < montant encaissé : le reste
            # était PERDU (seule la branche FIFO créait l'avance). Même
            # traitement que FIFO ci-dessous.
            restant = montant - total_parts
        else:
            # FIFO : échéance la plus ancienne d'abord (None en dernier) ; à
            # échéance égale, la facture la plus ancienne (pk) — sans ce
            # départage, l'ordre suivait celui, non garanti, de la base.
            ordonnees = sorted(
                locked,
                key=lambda f: (f.date_echeance is None, f.date_echeance, f.pk))
            restant = montant
            for facture in ordonnees:
                if restant <= 0:
                    break
                reste_facture = facture.montant_du
                if reste_facture <= 0:
                    continue
                part = min(restant, reste_facture)
                paiements.append(_creer_paiement_groupe(
                    facture, part, mode, date_paiement, user, reference))
                restant -= part
        # AUD120 / AFAC8 — le reliquat n'est plus abandonné en silence (ni
        # en FIFO, ni en répartition explicite) : ce qui a été encaissé et
        # que les factures listées n'absorbent pas devient une avance XFAC1
        # (Paiement sans facture, non affecté), ventilable plus tard par
        # ``ventiler_avance``. Un reliquat ≤ 1 centime ne crée rien.
        restant = quantize_mad(restant)
        if restant > TOLERANCE_CENTIME:
            paiements.append(enregistrer_avance(
                company=company, client=client, montant=restant,
                date_paiement=date_paiement, mode=mode,
                reference=reference,
                note="Reliquat d'encaissement groupé (XFAC1).",
                created_by=user))

        # AUD102 (P3) — la bascule passe par LE service unique : ce chemin
        # soldait en silence, sans `facture_payee`, donc sans lettrage compta.
        for facture in locked:
            facture.refresh_from_db()
            marquer_facture_soldee(
                facture, montant=facture.total_ttc,
                source='encaissement_groupe')

    return paiements


def _creer_paiement_groupe(facture, montant, mode, date_paiement, user,
                           reference):
    from apps.ventes.models import Paiement

    paiement = Paiement.objects.create(
        company=facture.company, facture=facture, montant=montant,
        date_paiement=date_paiement, mode=mode,
        reference=reference or '', created_by=user,
    )
    # YLEDG1 — événement documentaire générique (même seam que
    # enregistrer_paiement / le geste facture-par-facture).
    from core.events import paiement_enregistre
    paiement_enregistre.send(
        sender=Paiement, instance=paiement, company=facture.company)
    return paiement


# ── FG53 — Liens de paiement « Payer en ligne » ──────────────────────────────

# AUD136 — l'expiration n'est JAMAIS facultative : sans elle, un lien reste
# payable des mois après la facture. Elle est portée par le modèle
# (`PaymentLink.expires_at`, non nul, défaut `PAYMENT_LINK_TTL_DAYS` = 30 j) —
# une seule source de vérité, jamais dupliquée ici.


def fermer_liens_paiement(facture, statut):
    """AFAC23 (C-AFAC-018) — LE service unique de fermeture des liens
    « Payer en ligne » d'une facture : tout lien EN ATTENTE passe ``statut``
    (``annule`` sur annulation / solde par un autre chemin, ``paye`` quand la
    facture est soldée par son propre encaissement). Appelé par l'annulation,
    le solde (``marquer_facture_soldee``) et la révocation manuelle.
    Idempotent ; renvoie le nombre de liens fermés."""
    from ..models import PaymentLink

    return PaymentLink.objects.filter(
        facture=facture, statut=PaymentLink.Statut.EN_ATTENTE,
    ).update(statut=statut)


def _fermer_liens_facture_close(facture):
    from ..models import PaymentLink
    return fermer_liens_paiement(facture, PaymentLink.Statut.ANNULE)


def expirer_liens_paiement_perimes(facture):
    """AUD136 — bascule en EXPIRÉ les liens EN ATTENTE dont la date est passée.

    Un lien périmé restait EN ATTENTE en base : `is_valid` le refusait bien au
    paiement, mais il occupait la place du « lien actif » de la facture. On le
    ferme explicitement, ce qui rend la contrainte partielle « un seul lien
    actif par facture » applicable sans jamais bloquer une ré-émission
    légitime. Renvoie le nombre de liens fermés.
    """
    from django.utils import timezone
    from ..models import PaymentLink

    return PaymentLink.objects.filter(
        facture=facture, statut=PaymentLink.Statut.EN_ATTENTE,
        expires_at__lte=timezone.now(),
    ).update(statut=PaymentLink.Statut.EXPIRE)


def argent_rattache(facture):
    """AFAC11 (C-AFAC-004) — TOUT l'argent rattaché à une facture, par nature.

    Prédicat UNIQUE du domaine (lu par « Remettre en brouillon » et par la
    garde d'annulation AFAC12) : une facture qui porte de l'argent ne se
    rouvre ni ne s'annule sans qu'on dise où va cet argent. L'ancienne garde
    (``facture.paiements.exists()``) ne voyait ni une avance VENTILÉE (zéro
    paiement direct), ni une note de débit émise, ni une retenue subie.

    Renvoie ``{paiements, affectations, notes_debit, retenues, avoirs_actifs}``
    en ``Decimal`` (TTC), clés du contrat ``facture_annulation.json``
    (``argent_rattache``). Un paiement REJETÉ ne porte plus d'argent (YLEDG5)."""
    from ..models import Paiement

    non_comptes = Paiement.STATUTS_NON_COMPTES
    paiements = sum(
        (p.montant for p in facture.paiements.all() if p.statut not in non_comptes),
        Decimal('0'))
    affectations = sum(
        (a.montant for a in facture.affectations_paiement.select_related(
            'paiement') if a.paiement.statut not in non_comptes),
        Decimal('0'))
    return {
        'paiements': paiements,
        'affectations': affectations,
        'notes_debit': facture.notes_debit_total,
        'retenues': facture.retenues_subies_total,
        'avoirs_actifs': facture.avoirs_total,
    }


#: Libellés français des natures d'argent (message de refus).
LIBELLES_ARGENT_RATTACHE = {
    'paiements': 'paiements',
    'affectations': 'avances ventilées',
    'notes_debit': 'notes de débit',
    'retenues': 'retenues à la source subies',
    'avoirs_actifs': 'avoirs actifs',
}


def decrire_argent_rattache(argent):
    """AFAC11 — phrase française qui NOMME l'argent rattaché (ou '' si aucun)."""
    morceaux = [
        f"{LIBELLES_ARGENT_RATTACHE[cle]} {montant:.2f} MAD"
        for cle, montant in argent.items() if montant and montant > 0]
    return ', '.join(morceaux)


def revoquer_lien_paiement(*, facture, user=None):
    """AUD136 — révoque le lien de paiement actif d'une facture (ANNULÉ).

    Le cycle de vie n'avait aucune sortie manuelle : un lien créé avec un
    montant erroné ne pouvait être ni corrigé ni fermé. Idempotent — renvoie le
    lien révoqué, ou ``None`` si la facture n'en portait aucun d'actif.
    """
    from ..models import PaymentLink

    lien = (PaymentLink.objects
            .filter(facture=facture, statut=PaymentLink.Statut.EN_ATTENTE)
            .order_by('-created_at').first())
    if lien is None:
        return None
    # AFAC23 — même service de fermeture que l'annulation et le solde.
    fermer_liens_paiement(facture, PaymentLink.Statut.ANNULE)
    lien.refresh_from_db()
    return lien


def create_payment_link(*, facture, provider=None):
    """FG53 — crée (ou réutilise) LE lien de paiement d'une facture.

    Réutilise le lien encore valide (en attente, non expiré) de la facture
    plutôt que d'en empiler : c'est le get_or_create du couple, doublé depuis
    AUD136 d'une contrainte partielle en base (un seul lien EN ATTENTE par
    facture). Le fournisseur par défaut est NoOp (page interne, aucun coût).
    Société forcée depuis la facture, jamais lue d'un corps de requête.

    AUD136 — cycle de vie BORNÉ, là où il ne l'était pas :
    - `montant` n'est qu'une TRACE de ce qui était dû à la création ; ce que le
      client paie est dérivé de `facture.montant_du` à l'instant du paiement
      (`record_payment_from_link`, déjà correct) et affiché via
      `PaymentLink.montant_a_payer` ;
    - les liens périmés sont fermés (EXPIRÉ) avant toute ré-émission ;
    - une facture ANNULÉE ou PAYÉE n'obtient plus de lien (`LinkError`) ;
    - `revoquer_lien_paiement` ferme un lien à la demande.
    """
    from decimal import Decimal
    from django.utils import timezone
    from ..models import Facture, PaymentLink

    if facture.statut == Facture.Statut.ANNULEE:
        raise LinkError('Facture annulée : aucun lien de paiement.')
    if facture.statut == Facture.Statut.PAYEE:
        raise LinkError('Facture déjà payée : aucun lien de paiement.')
    # AFAC9 — LA porte unique : un brouillon ou un acompte CAD122 avant J+7
    # n'obtient pas de lien.
    motif = motif_non_encaissable(facture, timezone.localdate())
    if motif:
        raise LinkError(motif)
    if (facture.montant_du or Decimal('0')) <= Decimal('0'):
        raise LinkError('Cette facture est déjà soldée.')
    # AFAC24 (C-AFAC-019) — le lien RÉCLAME de l'argent : il ne porte que ce
    # qui est EXIGIBLE maintenant (CIQ214), jamais la retenue de garantie non
    # libérée. Rien d'exigible ⇒ aucun lien.
    if (facture.montant_exigible or Decimal('0')) <= Decimal('0'):
        raise LinkError(
            "Rien d'exigible maintenant : seule la retenue de garantie reste "
            "due.")

    # Ferme d'abord ce qui est périmé : sinon un lien mort tiendrait la place
    # du lien actif et la contrainte partielle bloquerait la ré-émission.
    expirer_liens_paiement_perimes(facture)

    existing = (PaymentLink.objects
                .filter(facture=facture,
                        statut=PaymentLink.Statut.EN_ATTENTE,
                        expires_at__gt=timezone.now())
                .order_by('-created_at').first())
    if existing is not None:
        return existing

    return PaymentLink.objects.create(
        company=facture.company,
        facture=facture,
        provider=(provider or 'noop'),
        montant=facture.montant_exigible,
    )


def _public_url(path, request=None):
    """Construit une URL publique ABSOLUE à partir d'un chemin.

    AFAC21 (C-AFAC-017) — l'UNIQUE constructeur des URL de paiement :
    ``settings.PUBLIC_BASE_URL`` d'abord (même pattern que
    ``bcf_share_url``), sinon ``request.build_absolute_uri`` quand la requête
    est connue, sinon ``''`` — jamais un chemin relatif (un client ne peut
    rien en faire : le lien était cassé dans l'e-mail et le QR)."""
    from django.conf import settings
    base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    if base:
        return base.rstrip('/') + path
    if request is not None:
        return request.build_absolute_uri(path)
    return ''


def url_page_paiement(token, request=None):
    """AFAC21 — l'URL de la page CLIENT « Payer » ``/payer/<token>``
    (contrat ``lien_paiement.json``), absolue ou ``''``."""
    return _public_url(f'/payer/{token}', request)


def qr_svg_for_facture_pdf(facture):
    """XFAC19 — QR de paiement/vérification pour le PDF facture LEGACY (jamais
    le moteur devis premium — voir RULE #4).

    Si un ``PaymentLink`` actif (en attente, non expiré) existe déjà pour la
    facture, le QR pointe vers sa page « Payer en ligne » publique. Sinon, il
    pointe vers le ``ShareLink`` public (lecture seule) du document. Ajout
    SILENCIEUX : renvoie ``None`` si aucun lien ne peut être établi (comportement
    actuel inchangé — pas de QR, pas d'erreur). Le rendu SVG délègue au
    générateur QR pur de N20 via ``apps.stock.services.qr_svg_for`` (jamais
    d'import direct de ``apps.stock.labels``)."""
    from django.utils import timezone
    from ..models import PaymentLink, ShareLink

    active_link = (
        PaymentLink.objects.filter(
            facture=facture, statut=PaymentLink.Statut.EN_ATTENTE,
            expires_at__gt=timezone.now(),
        ).order_by('-created_at').first())
    # AFAC21 — le QR d'un lien actif porte la page CLIENT absolue
    # ``/payer/<token>`` (la même URL que l'e-mail et l'écran) ; sans base
    # absolue connue, repli sur le lien de partage du document (chemin
    # d'hier, inchangé) plutôt qu'un QR de paiement cassé.
    url = (url_page_paiement(active_link.token)
           if active_link is not None else '')
    if not url:
        share = ShareLink.for_facture(facture)
        path = f'/api/django/public/document/{share.token}/'
        url = _public_url(path) or path

    if not url:
        return None
    return qr_svg_for(url)


def record_payment_from_link(*, link, payload=None):
    """FG53 — enregistre un Paiement quand un lien est confirmé payé (webhook).

    Idempotent : un lien déjà payé renvoie le paiement existant sans en créer un
    second. Le fournisseur valide d'abord la notification (verify_webhook) ; tant
    qu'il ne confirme pas, rien n'est écrit. Le montant et le statut de la
    facture sont mis à jour exactement comme un encaissement manuel.

    Retourne (paiement, message_erreur). En succès message_erreur=None.
    """
    from decimal import Decimal
    from django.db import transaction
    from django.utils import timezone
    from ..models import Facture, Paiement, PaymentLink
    from ..payments.providers import get_provider

    if link.statut == PaymentLink.Statut.PAYE and link.paiement_id:
        # Déjà encaissé — idempotent.
        return link.paiement, None
    if not link.is_valid:
        return None, 'Lien de paiement expiré ou invalide.'

    provider = get_provider(link.provider)
    result = provider.verify_webhook(link, payload or {})
    if not result.get('paid'):
        return None, 'Paiement non confirmé par le fournisseur.'

    # AFAC23 (C-AFAC-023) — sans montant déclaré, le repli est ce qui reste
    # à payer MAINTENANT (`montant_a_payer`), jamais le montant FIGÉ à la
    # création du lien (une note de débit postérieure était perdue).
    montant = result.get('montant')
    if montant is None:
        montant = link.montant_a_payer
    montant = Decimal(str(montant))
    provider_ref = (result.get('provider_ref') or '')[:120]

    with transaction.atomic():
        locked_link = (PaymentLink.objects.select_for_update()
                       .get(pk=link.pk))
        if locked_link.statut == PaymentLink.Statut.PAYE \
                and locked_link.paiement_id:
            return locked_link.paiement, None
        facture = (Facture.objects.select_for_update()
                   .get(pk=locked_link.facture_id))
        if facture.statut == Facture.Statut.ANNULEE:
            return None, 'Facture annulée.'
        # AFAC9 — LA porte unique (même refus que l'écran).
        motif = motif_non_encaissable(facture, timezone.localdate())
        if motif and facture.statut != Facture.Statut.PAYEE:
            return None, motif
        # AFAC23 — rejeu d'une confirmation PARTIELLE (le lien reste ouvert) :
        # même référence fournisseur ⇒ le paiement existant, jamais un second.
        if provider_ref:
            deja = Paiement.objects.filter(
                facture=facture, mode=Paiement.Mode.CARTE,
                reference=provider_ref).first()
            if deja is not None:
                return deja, None
        # Borne le montant au reste à payer (jamais de sur-paiement).
        reste = facture.montant_du
        if montant > reste:
            montant = reste
        if montant <= Decimal('0'):
            return None, 'Aucun reste à payer sur cette facture.'
        paiement = Paiement.objects.create(
            company=facture.company,
            facture=facture,
            montant=montant,
            date_paiement=timezone.localdate(),
            mode=Paiement.Mode.CARTE,
            reference=provider_ref,
            note='Paiement en ligne (lien « Payer en ligne »).',
        )
        # YLEDG1 — événement documentaire générique (pose du seam pour
        # compta.ecriture_pour_paiement).
        from core.events import paiement_enregistre
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=facture.company)
        facture.refresh_from_db()
        # AFAC23 — le lien ne passe PAYÉ que si la facture est SOLDÉE : un
        # règlement partiel le laisse ouvert pour le reste (la page affiche
        # alors le nouveau reste, `paye: false`).
        locked_link.provider_ref = (result.get('provider_ref') or '')[:200]
        # AFAC24 — « soldée » au sens de ce que le lien réclame : l'exigible
        # (une retenue de garantie non libérée ne garde pas le lien ouvert).
        if facture.montant_exigible <= Decimal('0.01'):
            locked_link.statut = PaymentLink.Statut.PAYE
            locked_link.paiement = paiement
            locked_link.paid_at = timezone.now()
        locked_link.save(update_fields=[
            'statut', 'paiement', 'provider_ref', 'paid_at'])
        # AUD102 (P4) — YDOCF4/YEVNT6 passent par LE service unique (garde
        # centime-près, verrou, `facture_paid` + `facture_payee` une seule
        # fois). Comportement identique pour ce chemin, déjà correct.
        marquer_facture_soldee(
            facture, montant=montant, source='lien_paiement')
    return paiement, None


# ── XFAC1 — Avances client (paiement sans facture) + affectation multi- ────
# ────────────────────────── factures ───────────────────────────────────────

def enregistrer_avance(*, company, client, montant, date_paiement, mode,
                       reference='', note='', created_by=None):
    """Enregistre un règlement reçu SANS facture (avance, acompte à la
    commande, trop-perçu). Le paiement reste ``statut_affectation=non_affecte``
    tant qu'il n'a pas été ventilé sur une ou plusieurs factures ouvertes du
    même client (voir ``ventiler_avance``)."""
    from decimal import Decimal, InvalidOperation
    from rest_framework.exceptions import ValidationError
    from ..models import Paiement

    if montant is None:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    try:
        montant = Decimal(str(montant))
    except InvalidOperation:
        raise ValidationError({'montant': 'Montant invalide.'})
    if montant <= 0:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    if client is None:
        raise ValidationError({'client': 'Client requis pour une avance.'})
    return Paiement.objects.create(
        company=company, client=client, facture=None,
        statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
        montant=montant, date_paiement=date_paiement, mode=mode,
        reference=reference, note=note, created_by=created_by,
    )


def ventiler_avance(*, paiement, facture, montant, user=None):
    """Ventile UN paiement non affecté (avance) sur UNE facture ouverte du
    même client, pour ``montant``. Peut être appelée plusieurs fois pour
    répartir un même paiement sur plusieurs factures.

    Garde-fous (jamais de sur-affectation) :
      - la facture cible doit appartenir à la même société ET au même client
        que le paiement ;
      - le montant ventilé ne peut jamais dépasser le solde disponible du
        paiement (``montant_disponible``) ;
      - le montant ventilé ne peut jamais dépasser le reste à payer de la
        facture cible (``montant_du``).

    Met à jour ``statut_affectation`` du paiement (affecte / partiellement
    affecte) et le statut de la facture si elle devient intégralement réglée
    (réutilise le même seuil que ``enregistrer_paiement``)."""
    from decimal import Decimal
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.exceptions import ValidationError
    from ..models import AffectationPaiement, Facture, Paiement

    montant = Decimal(montant)
    if montant <= 0:
        raise ValidationError(
            {'montant': "Le montant ventilé doit être positif."})

    with transaction.atomic():
        locked_paiement = Paiement.objects.select_for_update().get(
            pk=paiement.pk)
        if locked_paiement.facture_id is not None:
            raise ValidationError(
                {'paiement': "Ce paiement est déjà rattaché à une facture."})
        locked_facture = Facture.objects.select_for_update().get(
            pk=facture.pk)
        if locked_facture.company_id != locked_paiement.company_id:
            raise ValidationError(
                {'facture': "Facture d'une autre société."})
        if locked_facture.client_id != locked_paiement.client_id:
            raise ValidationError(
                {'facture': "La facture doit appartenir au même client "
                            "que l'avance."})
        if locked_facture.statut == Facture.Statut.ANNULEE:
            raise ValidationError(
                {'facture': "Impossible de ventiler sur une facture annulée."})
        # AFAC9 (C-AFAC-014) — une avance REJETÉE (chèque impayé) n'a jamais
        # été encaissée : elle ne se ventile pas.
        if locked_paiement.statut in Paiement.STATUTS_NON_COMPTES:
            raise ValidationError(
                {'paiement': "Avance rejetée ou annulée : elle ne peut pas "
                             "être ventilée."})
        # AFAC9 — LA porte unique (brouillon, soldée, acompte CAD122).
        motif = motif_non_encaissable(locked_facture, timezone.localdate())
        if motif:
            raise ValidationError({'facture': motif})

        disponible = locked_paiement.montant_disponible
        if montant - disponible > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f"Le montant ventilé dépasse le solde disponible de "
                    f"l'avance ({disponible:.2f} MAD)."),
            })
        reste_facture = locked_facture.montant_du
        if montant - reste_facture > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f"Le montant ventilé dépasse le reste à payer de la "
                    f"facture ({reste_facture:.2f} MAD)."),
            })

        affectation = AffectationPaiement.objects.create(
            company=locked_paiement.company, paiement=locked_paiement,
            facture=locked_facture, montant=montant, created_by=user,
        )

        locked_paiement.refresh_from_db()
        if locked_paiement.montant_disponible <= 0:
            locked_paiement.statut_affectation = (
                Paiement.StatutAffectation.AFFECTE)
        else:
            locked_paiement.statut_affectation = (
                Paiement.StatutAffectation.PARTIELLEMENT_AFFECTE)
        locked_paiement.save(update_fields=['statut_affectation'])

        locked_facture.refresh_from_db()
        # AUD102 (P5) — la ventilation d'une avance soldait en silence : elle
        # passe par LE service unique (donc `facture_payee` + lettrage).
        marquer_facture_soldee(
            locked_facture, montant=montant, source='ventilation_avance')

        from .. import activity
        activity.log_facture_avance_affectee(
            locked_facture, user, locked_paiement, montant)

    return affectation


# ── XFAC4 — Retenue à la source SUBIE (RAS TVA/RAS IS) sur factures ────────
# ────────────────────────── clients ────────────────────────────────────────

def enregistrer_paiement_avec_retenue(
        *, facture, montant, date_paiement, mode, type_retenue, taux,
        reference='', note='', created_by=None):
    """Enregistre un paiement PARTIEL accompagné d'une retenue à la source
    (RAS TVA / RAS IS) qui, ENSEMBLE, soldent la facture : payé + retenue +
    avoirs = TTC. Sans cette écriture, la facture resterait « partiellement
    payée » à tort — la retenue n'est pas un montant perdu, c'est une créance
    d'attestation à recevoir de la DGT/du client.

    AFAC30 — le MONTANT de la retenue vient de son assiette fiscale (TVA ou
    HT × ``taux``), moins les RAS déjà constatées, plafonné au reste après
    paiement ; le reste non couvert RESTE DÛ. Rejette un montant qui
    dépasserait seul le reste à payer. Le
    paiement + la retenue sont créés dans la MÊME transaction ; la facture
    bascule automatiquement « Payée » si le solde tombe à zéro (même seuil que
    ``enregistrer_paiement``).
    """
    from decimal import Decimal, InvalidOperation
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from ..models import Facture, Paiement, RetenueSubie

    try:
        montant = Decimal(str(montant))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({'montant': 'Montant invalide.'})
    if montant <= 0:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    try:
        taux = Decimal(str(taux))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({'taux': 'Taux de RAS invalide.'})
    if taux < 0 or taux > 100:
        raise ValidationError(
            {'taux': 'Le taux de RAS doit être compris entre 0 et 100 %.'})

    with transaction.atomic():
        locked = Facture.objects.select_for_update().get(pk=facture.pk)
        if locked.statut == Facture.Statut.ANNULEE:
            raise ValidationError(
                {'detail': "Impossible d'encaisser sur une facture annulée."})
        # AFAC9 — LA porte unique (brouillon, soldée, acompte CAD122).
        motif = motif_non_encaissable(locked, date_paiement)
        if motif:
            raise ValidationError({'detail': motif})
        reste = locked.montant_du
        if montant - reste > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f'Le paiement dépasse le reste à payer '
                    f'({reste:.2f} MAD).'),
            })
        # AFAC30 (C-AFAC-028) — ASSIETTE FISCALE de la RAS, plus le reste
        # dû : RAS-TVA = TVA × taux, RAS-IS = HT × taux, moins les RAS du
        # même type déjà constatées (hors paiement rejeté), plafonnée au
        # reste après le paiement. Ce qui n'est pas couvert RESTE DÛ (l'ancien
        # `reste − montant` soldait toute facture : 1 MAD à 0 % = tout le
        # reste en « RAS »).
        if type_retenue == RetenueSubie.TypeRetenue.RAS_IS:
            base = Decimal(str(locked.total_ht))
        else:
            base = Decimal(str(locked.total_tva))
        from core.money import quantize_mad
        due = quantize_mad(base * taux / Decimal('100'))
        deja = sum(
            (r.montant for r in locked.retenues_subies.select_related(
                'paiement').filter(type_retenue=type_retenue)
             if not (r.paiement_id
                     and r.paiement.statut in Paiement.STATUTS_NON_COMPTES)),
            Decimal('0'))
        retenue_montant = min(due - deja, reste - montant)
        if retenue_montant < 0:
            retenue_montant = Decimal('0')
        retenue_montant = quantize_mad(retenue_montant)

        paiement = Paiement.objects.create(
            company=locked.company, facture=locked, montant=montant,
            date_paiement=date_paiement, mode=mode, reference=reference,
            note=note, created_by=created_by,
        )
        retenue = RetenueSubie.objects.create(
            company=locked.company, facture=locked, paiement=paiement,
            type_retenue=type_retenue, taux=taux, base=base,
            montant=retenue_montant, note=note,
            created_by=created_by,
        )

        from .. import activity
        activity.log_facture_paiement(locked, created_by, paiement)
        activity.log_facture_retenue_subie(locked, created_by, retenue)

        locked.refresh_from_db()
        # AUD102 (P6) / AFAC30 — la bascule passe par le service unique, sur
        # le reste dû RÉEL (paiements + RAS + avoirs + notes de débit) : une
        # RAS ne solde plus ce qu'elle ne couvre pas.
        marquer_facture_soldee(
            locked, montant=montant, source='retenue_source')

    return paiement, retenue


# ── XFAC11 — Facture consolidée multi-devis/BC d'un même client ────────────

def _composer_remise_et_palier(facture, devis_qs):
    """ATOT3 — pose sur la consolidée la remise globale et le palier
    d'arrondi qui lui font valoir Σ TTC des devis (``option_totaux``) AU
    CENTIME, ou refuse (400) : jamais un total faux.

    Une remise globale n'est composable que si TOUS les devis portent la
    même ; le palier ARRONDI-100 du devis (appliqué par devis) n'est gardé
    que s'il redonne la somme, sinon le total brut des lignes est essayé."""
    from rest_framework.exceptions import ValidationError

    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    from apps.ventes.utils.options import option_totaux

    noms = ', '.join(d.reference for d in devis_qs)
    remises = {Decimal(str(d.remise_globale or 0)) for d in devis_qs}
    if len(remises) > 1:
        raise ValidationError({'devis_ids': (
            f'Les devis {noms} portent des remises globales différentes : '
            'une seule facture ne peut pas les reproduire au centime. '
            'Facturez-les séparément.')})
    attendu = sum((Decimal(str(option_totaux(d)['ttc'])) for d in devis_qs),
                  Decimal('0'))
    facture.remise_globale = remises.pop()
    facture.arrondi_unites = 1
    for pas in (int(PAS_ARRONDI_DEVIS), 0):
        facture.arrondi_pas = pas
        facture.save(update_fields=[
            'remise_globale', 'arrondi_pas', 'arrondi_unites'])
        if Decimal(str(facture.total_ttc)) == attendu:
            return
    raise ValidationError({'devis_ids': (
        f'Les devis {noms} ne se regroupent pas en une facture au centime '
        f'(total attendu {attendu:.2f} MAD : remises ou arrondis non '
        'composables). Facturez-les séparément.')})


def _entete_consolidee(facture, devis_qs):
    """ATOT4 — l'en-tête de la consolidée par LE geste partagé
    ``entete_facture_depuis_devis``, appelé devis par devis : retenue de
    garantie = Σ des retenues de chaque devis sur SON TTC (prorata), phrases
    AUD180 conservées, références de commande client distinctes jointes. Le
    taux de tête n'est pas repris (chaque ligne porte son taux effectif)."""
    from apps.ventes.domain.facturation_ops import entete_facture_depuis_devis
    retenue = Decimal('0')
    phrases, refs = [], []
    for d in devis_qs:
        entete = entete_facture_depuis_devis(d)
        if entete.get('retenue_garantie_mad') is not None:
            retenue += Decimal(str(entete['retenue_garantie_mad']))
            phrases.append(f'{d.reference} : {entete["conditions_paiement"]}')
        ref = entete.get('reference_commande_client') or ''
        if ref and ref not in refs:
            refs.append(ref)
    champs = []
    if phrases:
        facture.retenue_garantie_mad = retenue
        facture.conditions_paiement = '\n'.join(phrases)
        champs += ['retenue_garantie_mad', 'conditions_paiement']
    if refs:
        facture.reference_commande_client = ', '.join(refs)[:60]
        champs.append('reference_commande_client')
    if champs:
        facture.save(update_fields=champs)


def consolider_factures(*, company, devis_ids, user, created_by=None):
    """Crée UNE Facture unique regroupant PLUSIEURS devis acceptés du MÊME
    client (ex. projet multi-sites : ferme à N forages, tranches). Chaque
    document source garde ses lignes (recopiées, groupées par ``source_devis``
    pour le sous-titre « Devis DV-… » sur le PDF) et une ``FactureSource``
    trace le sous-total HT de son document d'origine.

    Contrôles :
      - au moins 2 devis, tous acceptés, tous de la MÊME société ET du MÊME
        client (clients différents → rejeté) ;
      - un devis déjà facturé (une Facture non annulée référence ce devis,
        directement ou via une FactureSource antérieure) est refusé.

    La chaîne Sous-total → Remise → HT → TVA → TTC reste calculée par les
    propriétés existantes de ``Facture`` (aucune formule dupliquée) : les
    lignes recopiées portent leur ``taux_tva`` d'origine, donc la ventilation
    TVA par taux (10 %/20 %) reste correcte pour le mélange.
    """
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from ..models import Devis, Facture, FactureSource, LigneFacture
    from ..selectors_facturation import (
        DevisDejaFacture, exiger_devis_facturable,
    )
    from ..utils.company_settings import create_numbered

    if not devis_ids or len(devis_ids) < 2:
        raise ValidationError(
            {'devis_ids': 'Au moins 2 devis sont requis pour consolider.'})

    devis_qs = list(Devis.objects.select_related('client').filter(
        id__in=devis_ids, company=company).prefetch_related('lignes'))
    if len(devis_qs) != len(set(devis_ids)):
        raise ValidationError({'devis_ids': 'Un ou plusieurs devis introuvables.'})

    client_ids = {d.client_id for d in devis_qs}
    if len(client_ids) > 1:
        raise ValidationError(
            {'devis_ids': 'Tous les devis doivent appartenir au même client.'})

    for d in devis_qs:
        if d.statut != Devis.Statut.ACCEPTE:
            raise ValidationError({
                'devis_ids': (
                    f'Le devis {d.reference} doit être accepté pour être '
                    f'consolidé.'),
            })
        # ATOT2 — LA garde unique des quatre portes (``factures_du_devis`` :
        # échéancier, complète, BC ET consolidée active) ; une consolidée
        # ANNULÉE ne bloque plus (elle bloquait à vie via FactureSource).
        try:
            exiger_devis_facturable(d, 'consolidee')
        except DevisDejaFacture as exc:
            raise ValidationError({
                'devis_ids': f'{d.reference} — {exc.motif}',
            })

    client = devis_qs[0].client

    with transaction.atomic():
        def _create(ref):
            return Facture.objects.create(
                reference=ref, company=company, client=client,
                statut=Facture.Statut.BROUILLON, created_by=created_by,
            )

        facture = create_numbered(Facture, company, 'facture', _create)

        # ATOT3 (C-ATOT-002) — chaque devis apporte EXACTEMENT le panier de
        # `copier_devis_sur_facture` (`lignes_facture_du_devis` : option
        # effective, lignes comptées seulement, ×N villas, taux par ligne —
        # effectif, le repli de la consolidée n'étant pas le taux du devis).
        # La boucle `d.lignes.all()` recopiait les sections (500), les
        # options non activées et les deux options, et perdait la remise.
        from apps.ventes.domain.facturation_ops import lignes_facture_du_devis
        for d in devis_qs:
            sous_total = Decimal('0')
            for champs in lignes_facture_du_devis(d, taux_effectif=True):
                ligne = LigneFacture.objects.create(
                    facture=facture, source_devis=d,
                    **{**champs, 'designation':
                       f'{d.reference} — {champs["designation"]}'},
                )
                sous_total += Decimal(str(ligne.total_ht))
            FactureSource.objects.create(
                company=company, facture=facture, devis=d,
                sous_total_ht=sous_total,
            )
        _composer_remise_et_palier(facture, devis_qs)
        _entete_consolidee(facture, devis_qs)

        # AUD101 — l'émission passe par LE service unique, APRÈS la recopie
        # des lignes (émettre une facture consolidée encore vide écrirait une
        # écriture comptable à zéro). Elle hérite ainsi du verrou de période,
        # du blocage crédit XFAC28 et de `facture_emise` — qu'elle n'avait
        # jamais alors qu'elle posait EMISE.
        from apps.ventes.domain.facturation_ops import emettre_facture
        emettre_facture(facture, user=user, source='consolidation')

    return facture


# AFAC19 (C-AFAC-015) — la pile XCTR22 (débit automatique sur mandat :
# ``mandat_actif_pour_client``, ``debiter_mandat_pour_facture``,
# ``DUNNING_RETRY_DAYS``) est PARQUÉE : aucun appelant MVP. Les modèles
# restent ; retour éventuel par la branche d'archive.


# ── CAD122 ── délai légal de rétractation (démarchage à domicile) ───────────
def _verifier_delai_acompte_domicile(facture, date_paiement=None):
    """Refuse un encaissement d'ACOMPTE pendant le délai de la loi 31-08.

    Trois conditions cumulatives, sinon la fonction ne fait RIEN (aucun
    changement de comportement pour l'immense majorité des paiements) :
    la facture est de type ACOMPTE, elle remonte à un bon de commande, et ce
    bon porte le marqueur « signé au domicile » (CAD122). Le refus vient du
    modèle (``BonCommande.verifier_encaissement_acompte``) : une seule règle,
    un seul endroit, un message qui nomme la date.

    Best-effort sur la RÉSOLUTION du bon (une chaîne documentaire incomplète
    ne fait jamais tomber un encaissement) — mais JAMAIS sur le refus
    lui-même, qui remonte tel quel à l'appelant.
    """
    from apps.ventes.models import AcompteAvantDelaiLegal, Facture

    try:
        if getattr(facture, 'type_facture', None) != Facture.TypeFacture.ACOMPTE:
            return
        devis = getattr(facture, 'devis', None)
        bon = getattr(devis, 'bon_commande', None) if devis is not None else None
        if bon is None:
            return
    except AcompteAvantDelaiLegal:
        raise
    except Exception:  # noqa: BLE001 — une chaîne incomplète ne bloque rien
        return
    bon.verifier_encaissement_acompte(a_la_date=date_paiement)


# ── PONT M3 : noms hébergés par un autre module ──────────────────────────────
# Import EN BAS DE FICHIER : il s'exécute après toutes les définitions de ce
# module, donc un import croisé ne peut jamais lire un module à moitié
# construit, quel que soit celui qui est chargé le premier.
from apps.ventes.domain.recouvrement import reset_relance_escalation  # noqa: E402,F401


# ── AFAC17 (C-AFAC-013, D-AFAC-C2 a) — corriger un paiement mal saisi ──────
class CorrectionPaiementRefusee(Exception):
    """AFAC17 — refus d'une correction de paiement (``code`` + ``detail`` FR,
    contrats ``paiement_annuler_saisie.json`` / ``paiement_reaffecter.json``).
    ``conflit`` : l'état du paiement interdit le geste (409)."""

    def __init__(self, code, detail, conflit=False):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.conflit = conflit


def _remise_du_paiement(paiement):
    """La remise d'encaissement qui porte ``paiement``, ou ``None``."""
    from apps.ventes.models import LigneRemiseEncaissement
    ligne = (LigneRemiseEncaissement.objects.select_related('remise')
             .filter(paiement=paiement).first())
    return ligne.remise if ligne is not None else None


def _refus_si_remis(paiement, geste):
    remise = _remise_du_paiement(paiement)
    if remise is not None:
        raise CorrectionPaiementRefusee(
            'paiement_remis_en_banque',
            f'Ce paiement est déjà porté par la remise '
            f'{remise.reference or remise.pk} : retirez-le de la remise '
            f'avant {geste}.')


def _note_facture(facture, user, field, label, body, ancien='', nouveau=''):
    """Ligne de chatter facture (FactureActivity) d'une correction."""
    from apps.ventes.models import FactureActivity
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION, field=field,
        field_label=label, old_value=str(ancien), new_value=str(nouveau),
        body=body)


def _rattacher_paiement(paiement, cible):
    """Déplace ``paiement`` sur ``cible`` (sans garde) : le seul geste de
    déplacement, partagé par ``reaffecter_paiement`` et le transfert
    d'acompte de l'annulation de facture."""
    paiement.facture = cible
    paiement.save(update_fields=['facture'])


def reaffecter_paiement(*, paiement, facture_cible, user=None):
    """AFAC17 — réaffecte un paiement rapproché sur la MAUVAISE facture vers
    ``facture_cible`` (même société, même client, encaissable — porte AFAC9),
    sous verrou des deux factures (ordre des pk : jamais d'interblocage).
    Les deux statuts sont redérivés (``recalculer_statut_paiement``, ATOT8)
    et le chatter des deux factures dit ancien → nouveau. Lève
    ``CorrectionPaiementRefusee``. Renvoie ``(paiement, source, cible)``."""
    from django.db import transaction

    from apps.ventes.models import Facture, Paiement

    with transaction.atomic():
        p = Paiement.objects.select_for_update().get(pk=paiement.pk)
        if p.statut in Paiement.STATUTS_NON_COMPTES:
            raise CorrectionPaiementRefusee(
                'paiement_non_compte',
                f'Paiement {p.get_statut_display().lower()} : il ne se '
                'réaffecte pas.', conflit=True)
        if p.facture_id is None:
            raise CorrectionPaiementRefusee(
                'paiement_sans_facture',
                "Avance non rattachée : utilisez la ventilation.")
        if facture_cible is None or facture_cible.pk == p.facture_id:
            raise CorrectionPaiementRefusee(
                'cible_invalide',
                'Choisissez une autre facture que celle du paiement.')
        _refus_si_remis(p, 'de le réaffecter')
        ids = sorted([p.facture_id, facture_cible.pk])
        verrous = {f.pk: f for f in
                   Facture.objects.select_for_update().filter(pk__in=ids)
                   .order_by('pk')}
        source, cible = verrous[p.facture_id], verrous.get(facture_cible.pk)
        if cible is None or cible.company_id != source.company_id:
            raise CorrectionPaiementRefusee(
                'cible_invalide', 'Facture cible inconnue.')
        if cible.client_id != source.client_id:
            raise CorrectionPaiementRefusee(
                'facture_autre_client',
                "La facture cible appartient à un autre client : un paiement "
                "ne se réaffecte qu'entre factures du même client.")
        motif = motif_non_encaissable(cible, p.date_paiement)
        if motif:
            raise CorrectionPaiementRefusee('cible_non_encaissable', motif)
        total = Decimal(str(p.montant)) + Decimal(
            str(p.escompte_montant or 0))
        if total - cible.montant_du > Decimal('0.01'):
            raise CorrectionPaiementRefusee(
                'depasse_reste_cible',
                f'Le paiement ({total:.2f} MAD) dépasse le reste à payer de '
                f'la facture cible ({cible.montant_du:.2f} MAD).')
        _rattacher_paiement(p, cible)
        texte = (f'Paiement de {p.montant} MAD du {p.date_paiement} '
                 f'réaffecté : {source.reference} → {cible.reference}.')
        _note_facture(source, user, 'paiement_reaffecte',
                      'Paiement réaffecté', texte, source.reference,
                      cible.reference)
        _note_facture(cible, user, 'paiement_reaffecte',
                      'Paiement réaffecté', texte, source.reference,
                      cible.reference)
        recalculer_statut_paiement(source, user=user,
                                   source='reaffectation_paiement')
        recalculer_statut_paiement(cible, user=user,
                                   source='reaffectation_paiement')
    paiement.refresh_from_db()
    source.refresh_from_db()
    cible.refresh_from_db()
    return paiement, source, cible


def annuler_saisie_paiement(*, paiement, motif, user=None):
    """AFAC17 — annule une saisie de paiement ERRONÉE : statut
    ``annule_saisie`` daté (``annule_le``), motif obligatoire, auteur tracé.
    Le paiement sort du payé (``Paiement.STATUTS_NON_COMPTES``), la ou les
    factures touchées sont redérivées (ATOT8) ; ce n'est PAS un rejet
    bancaire : aucun ``paiement_rejete`` émis, aucun impayé compté. Jamais
    une suppression (le journal garde la ligne). Lève
    ``CorrectionPaiementRefusee``."""
    from django.db import transaction
    from django.utils import timezone

    from apps.ventes.models import Paiement

    motif = (motif or '').strip()
    if not motif:
        raise CorrectionPaiementRefusee(
            'motif_requis',
            'Motif obligatoire pour annuler une saisie de paiement.')
    with transaction.atomic():
        p = Paiement.objects.select_for_update().get(pk=paiement.pk)
        if p.statut in Paiement.STATUTS_NON_COMPTES:
            raise CorrectionPaiementRefusee(
                'paiement_non_compte',
                f'Paiement déjà {p.get_statut_display().lower()}.',
                conflit=True)
        _refus_si_remis(p, "d'annuler la saisie")
        p.statut = Paiement.Statut.ANNULE_SAISIE
        p.annule_le = timezone.now()
        p.annule_par = user if getattr(user, 'is_authenticated', False) \
            else None
        p.motif_annulation = motif[:255]
        p.save(update_fields=['statut', 'annule_le', 'annule_par',
                              'motif_annulation'])
        touchees = []
        if p.facture_id:
            touchees.append(p.facture)
        touchees.extend(a.facture for a in
                        p.affectations.select_related('facture')
                        if a.facture is not None)
        for facture in touchees:
            _note_facture(
                facture, user, 'paiement_annule_saisie',
                'Saisie de paiement annulée',
                f'Saisie de paiement annulée : {p.montant} MAD du '
                f'{p.date_paiement} — motif : {p.motif_annulation}.',
                Paiement.Statut.ENCAISSE, Paiement.Statut.ANNULE_SAISIE)
            recalculer_statut_paiement(facture, user=user,
                                       source='annulation_saisie_paiement')
    paiement.refresh_from_db()
    return paiement
