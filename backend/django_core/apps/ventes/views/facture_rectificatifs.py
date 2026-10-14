"""VNT99 — rectificatifs de la facture (avoir, note de débit, retour client,
pénalités de retard) : actions de ``FactureViewSet`` portées par
``FactureRectificatifsActionsMixin``, déplacées telles quelles depuis
``views/facture.py`` avec leurs bornes de ligne (``_MAX_MONTANT_LIGNE``,
``_montants_ligne_corrective``). Le logger garde le nom
``apps.ventes.views.facture`` (configuration et filtres de journaux
inchangés). Aucune route dans ``urls.py`` : le routeur les découvre sur le
viewset.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from . import openapi_docs as D
from .facture_gardes import PeutEncaisser
from ..models import Facture, LigneNoteDebit, NoteDebit
from ..serializers_facturation import (
    AvoirSerializer, FactureSerializer, NoteDebitSerializer,
)
from ..utils.company_settings import create_numbered, create_provisoire
from ..utils.corps import valider_corps, valider_corps_lignes

logger = logging.getLogger('apps.ventes.views.facture')

# CAD177 — bornes des colonnes des lignes d'avoir / de note de débit
# (DecimalField max_digits=10, decimal_places=2 → |x| < 10^8 ; remise et
# taux TVA max_digits=5 et bornés 0..100 par contrainte). Hors bornes
# (1e12, NaN, Infinity, remise 1000), l'INSERT levait DataError « numeric
# field overflow » → 500 (marcheur aléatoire, nocturne 37792898726).
_MAX_MONTANT_LIGNE = 10 ** 8


def _montants_ligne_corrective(i, ligne):
    """Valide quantité / prix unitaire / remise / taux TVA d'une ligne saisie
    (avoir ou note de débit). Rend ``((qte, pu, remise, taux_tva), None)`` ou
    ``(None, message)`` — message 400 nommant la ligne, jamais un 500."""
    from decimal import Decimal, InvalidOperation
    try:
        qte = Decimal(str(ligne.get('quantite')))
        pu = Decimal(str(ligne.get('prix_unitaire')))
    except (InvalidOperation, TypeError, ValueError):
        return None, (f'Ligne {i} : quantité et prix unitaire '
                      'numériques requis.')
    if not qte.is_finite() or not pu.is_finite() or qte <= 0 or pu < 0:
        return None, f'Ligne {i} : quantité > 0 et prix unitaire ≥ 0 requis.'
    if qte >= _MAX_MONTANT_LIGNE or pu >= _MAX_MONTANT_LIGNE:
        return None, (f'Ligne {i} : quantité et prix unitaire doivent rester '
                      'sous 100 000 000.')
    try:
        remise = Decimal(str(ligne.get('remise') or 0))
    except (InvalidOperation, TypeError, ValueError):
        return None, f'Ligne {i} : remise invalide.'
    if not remise.is_finite() or not 0 <= remise <= 100:
        return None, f'Ligne {i} : remise entre 0 et 100 % requise.'
    taux_tva = ligne.get('taux_tva')
    if taux_tva in (None, ''):
        return (qte, pu, remise, None), None
    try:
        taux_tva = Decimal(str(taux_tva))
    except (InvalidOperation, TypeError, ValueError):
        return None, f'Ligne {i} : taux TVA invalide.'
    if not taux_tva.is_finite() or not 0 <= taux_tva <= 100:
        return None, f'Ligne {i} : taux TVA invalide.'
    return (qte, pu, remise, taux_tva), None


def _montant_note_debit(donnees, facture):
    """AFAC32 — montant HT + taux saisis d'une note de débit SANS lignes.
    Rend ``((montant, taux), None)`` ou ``((None, None), message)`` — 400.
    ENF11 : montant borné comme une ligne (< 10^8, publié dans le motif) —
    au-delà, le TTC débordait la colonne (500)."""
    brut = donnees.get('montant')
    if brut in (None, ''):
        return (None, None), ('Saisissez les lignes ou le montant de la '
                              'note de débit.')
    try:
        montant = Decimal(str(brut))
        taux_brut = donnees.get('taux_tva')
        taux = (Decimal(str(taux_brut)) if taux_brut not in (None, '')
                else Decimal(str(facture.taux_tva)))
    except (InvalidOperation, TypeError, ValueError):
        return (None, None), 'Montant ou taux de TVA invalide.'
    if (not montant.is_finite() or not taux.is_finite() or montant <= 0
            or montant >= _MAX_MONTANT_LIGNE or not 0 <= taux <= 100
            or montant.as_tuple().exponent < -2
            or taux.as_tuple().exponent < -2):
        return (None, None), ('Le montant doit être positif (sous '
                              '100 000 000) et le taux de TVA compris entre '
                              '0 et 100 %, deux décimales au plus.')
    return (montant, taux), None


class FactureRectificatifsActionsMixin:
    """Les documents qui corrigent une facture émise : avoir, note de
    débit, retour client, facture de pénalités."""

    @extend_schema(request=D.CreerAvoirRequest,
                   responses={201: AvoirSerializer})
    @action(detail=True, methods=['post'], url_path='creer-avoir',
            permission_classes=[PeutEncaisser])
    def creer_avoir(self, request, pk=None):
        """Crée un Avoir (note de crédit) depuis une facture ÉMISE — admin only
        (get_permissions par défaut). Total ou partiel : si `lignes` est fourni
        on crédite ces lignes ; sinon on crédite toute la facture. Lié à la
        facture d'origine ; le PDF reprend le style facture.

        ZFAC5 — ``mode`` ∈ {``correction`` (défaut, comportement ci-dessus
        inchangé), ``contre_passation``} : en ``contre_passation`` l'avoir
        reprend TOUTES les lignes de la facture à l'identique (les `lignes`
        du corps sont ignorées) et, à son émission, la facture d'origine
        passe ``annulee`` avec un ``FactureActivity`` liant les deux pièces.
        Refusé (409) si la facture a déjà des paiements (dû négatif évité)."""
        facture = self.get_object()
        # Tour 3 M1 — corps validé (types, listes, enums) AVANT toute lecture.
        valider_corps_lignes(request, D.CreerAvoirRequest)
        if facture.statut not in ('emise', 'payee', 'en_retard'):
            return Response(
                {'detail': 'Un avoir ne peut être créé que depuis une '
                           'facture émise (ou payée/en retard).'},
                status=status.HTTP_409_CONFLICT)
        # `mode` ∈ enum garanti par le corps validé ; refus d'ÉTAT = 409 (ENF11).
        mode = (request.data.get('mode') or 'correction').strip()
        if mode == 'contre_passation' and facture.montant_paye > 0:
            return Response(
                {'detail': ("Contre-passation refusée : cette facture a déjà "
                            "des paiements enregistrés.")},
                status=status.HTTP_409_CONFLICT)
        # AFAC32 (D-AFAC-C4) — la contre-passation ANNULE la facture : ses
        # notes de débit actives s'annulent d'abord (par avoir de ND).
        from ..domain.facturation_ops import notes_debit_actives
        if mode == 'contre_passation' and notes_debit_actives(facture):
            return Response(
                {'detail': ("Contre-passation refusée : la facture porte une "
                            "note de débit active — annulez-la d'abord."),
                 'code': 'note_debit_active'},
                status=status.HTTP_409_CONFLICT)
        company = facture.company
        motif = (request.data.get('motif') or '').strip()
        lignes = None if mode == 'contre_passation' \
            else request.data.get('lignes')
        # Plafond : un avoir ne peut pas dépasser le reste créditable de la
        # facture (TTC − avoirs actifs déjà émis). AUD126 — il est désormais
        # mesuré SOUS LE VERROU de ligne, juste avant la création (voir le
        # bloc atomique plus bas) : le lire ici, hors transaction, laissait
        # deux requêtes concurrentes lire chacune l'ancien reste et passer
        # toutes deux la garde.

        # ERR34 — valider les lignes fournies AVANT toute création, et échouer
        # bruyamment (400) au lieu de les avaler en silence (l'ancien
        # `except Exception: continue` créait un avoir amputé de son montant,
        # sans erreur). On vérifie désignation / quantité / prix_unitaire de
        # chaque ligne et on renvoie une erreur 400 claire si l'une est
        # invalide.
        clean_lignes = None
        if isinstance(lignes, list) and lignes:
            clean_lignes = []
            for i, ligne in enumerate(lignes, start=1):
                designation = (ligne.get('designation') or '').strip()
                if not designation:
                    return Response(
                        {'detail': f'Ligne {i} : désignation requise.'},
                        status=status.HTTP_400_BAD_REQUEST)
                montants, erreur = _montants_ligne_corrective(i, ligne)
                if erreur:
                    return Response(
                        {'detail': erreur},
                        status=status.HTTP_400_BAD_REQUEST)
                qte, pu, remise, taux_tva = montants
                # DC10 — produit REQUIS sur une nouvelle ligne d'avoir (lien
                # snapshot fort). Le FK reste nullable en base pour l'historique,
                # mais toute ligne saisie ici doit désigner un produit de la
                # société.
                produit_id = ligne.get('produit') or None
                if produit_id is None:
                    return Response(
                        {'detail': f'Ligne {i} : produit requis.'},
                        status=status.HTTP_400_BAD_REQUEST)
                from apps.stock.selectors import get_produit_scoped
                if get_produit_scoped(company, produit_id) is None:
                    return Response(
                        {'detail': f'Ligne {i} : produit inconnu.'},
                        status=status.HTTP_400_BAD_REQUEST)
                clean_lignes.append({
                    'produit_id': produit_id,
                    'designation': designation[:255],
                    'quantite': qte, 'prix_unitaire': pu,
                    'remise': remise, 'taux_tva': taux_tva,
                })

        # AFAC27 — LE constructeur unique (`creer_avoir_facture`) : verrou de
        # la facture, plafond lu SOUS le verrou (AUD126), remise globale et
        # palier repris, ventilation TVA (ATOT6), chatter, `avoir_cree`,
        # contre-passation (ZFAC5) et recalcul du statut (ATOT8).
        from ..domain.facturation_ops import AvoirRefuse, creer_avoir_facture
        try:
            avoir = creer_avoir_facture(
                facture=facture, user=request.user, motif=motif, mode=mode,
                lignes_saisies=clean_lignes,
                type_avoir=str(request.data.get('type') or '').strip() or None)
        except AvoirRefuse as exc:
            # Refus de VALEUR (ligne, type, plafond créditable) : 400 — les
            # oracles ATOT (machine, reste, avoir/échéancier, AUD126) le
            # figent ; seul le refus d'ÉTAT ci-dessus est un 409 (ENF11).
            return Response({'detail': exc.motif},
                            status=status.HTTP_400_BAD_REQUEST)
        # Le PDF est de l'I/O : hors transaction, verrou déjà relâché.
        try:
            from ..utils.pdf import generate_avoir_pdf
            generate_avoir_pdf(avoir.id)
            avoir.refresh_from_db()
        except Exception:
            logger.warning("facture.FactureViewSet.creer_avoir : erreur ignorée (mode dégradé)", exc_info=True)
        return Response(AvoirSerializer(avoir).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=D.CreerNoteDebitRequest,
                   responses={201: NoteDebitSerializer},
                   extensions=D.CORPS_NOTE_DEBIT_LIGNES_OU_MONTANT)
    @action(detail=True, methods=['post'], url_path='creer-note-debit')
    def creer_note_debit(self, request, pk=None):
        """ZFAC4 — crée une NoteDebit (majoration d'une facture déjà émise) —
        pendant de l'avoir. Total (copie des lignes de la facture) ou
        personnalisé (`lignes` fourni) ; augmente ``Facture.montant_du``."""
        facture = self.get_object()
        if facture.statut not in ('emise', 'payee', 'en_retard'):
            # ENF11 — refus d'ÉTAT (brouillon, annulée) : 409.
            return Response(
                {'detail': 'Une note de débit ne peut être créée que depuis '
                           'une facture émise (ou payée/en retard).'},
                status=status.HTTP_409_CONFLICT)
        motif = (request.data.get('motif') or '').strip()
        lignes = request.data.get('lignes')

        clean_lignes = None
        if isinstance(lignes, list) and lignes:
            clean_lignes = []
            for i, ligne in enumerate(lignes, start=1):
                if not isinstance(ligne, dict):
                    return Response(
                        {'detail': f'Ligne {i} invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)
                designation = (ligne.get('designation') or '').strip()
                if not designation:
                    return Response(
                        {'detail': f'Ligne {i} : désignation requise.'},
                        status=status.HTTP_400_BAD_REQUEST)
                montants, erreur = _montants_ligne_corrective(i, ligne)
                if erreur:
                    return Response(
                        {'detail': erreur},
                        status=status.HTTP_400_BAD_REQUEST)
                qte, pu, remise, taux_tva = montants
                produit_id = ligne.get('produit') or None
                if produit_id is None:
                    return Response(
                        {'detail': f'Ligne {i} : produit requis.'},
                        status=status.HTTP_400_BAD_REQUEST)
                from apps.stock.selectors import get_produit_scoped
                if get_produit_scoped(facture.company, produit_id) is None:
                    return Response(
                        {'detail': f'Ligne {i} : produit inconnu.'},
                        status=status.HTTP_400_BAD_REQUEST)
                clean_lignes.append({
                    'produit_id': produit_id,
                    'designation': designation[:255],
                    'quantite': qte, 'prix_unitaire': pu,
                    'remise': remise, 'taux_tva': taux_tva,
                })

        # AFAC32 (C-AFAC-026, D-AFAC-C4) — note de débit PARTIELLE seulement :
        # des `lignes` saisies, ou un `montant` HT + `taux_tva`. Plus jamais
        # la copie silencieuse de toute la facture (le montant dû doublait).
        montant_saisi = taux_saisi = None
        if not clean_lignes:
            (montant_saisi, taux_saisi), erreur = _montant_note_debit(
                request.data, facture)
            if erreur:
                return Response({'detail': erreur},
                                status=status.HTTP_400_BAD_REQUEST)

        def _create(ref):
            note_debit = NoteDebit.objects.create(
                company=facture.company, reference=ref, facture=facture,
                client=facture.client, statut=NoteDebit.Statut.EMISE,
                motif=motif, taux_tva=facture.taux_tva,
                # AUD107 — la remise globale de la facture SUIT sur la note de
                # débit. Le repli « facture entière » recopie les lignes 1:1
                # (remise DE LIGNE incluse) mais jamais la remise GLOBALE du
                # document : une pénalité adossée à une facture remisée à 15 %
                # majorait le client sur le montant NON remisé. Seul le repli
                # « facture SANS lignes » lisait la propriété remise-aware ;
                # le chemin normal, le cas courant, ne le faisait jamais.
                remise_globale=facture.remise_globale,
                created_by=request.user)
            if clean_lignes:
                for ligne in clean_lignes:
                    LigneNoteDebit.objects.create(
                        note_debit=note_debit, **ligne)
            else:
                # AFAC32 — montant saisi (HT) au taux saisi : un seul panier,
                # aucune remise globale de la facture (montant déjà net).
                from core.money import quantize_mad
                tva = quantize_mad(montant_saisi * taux_saisi / Decimal('100'))
                note_debit.taux_tva = taux_saisi
                note_debit.remise_globale = Decimal('0')
                note_debit.montant_ht = quantize_mad(montant_saisi)
                note_debit.montant_tva = tva
                note_debit.montant_ttc = quantize_mad(montant_saisi) + tva
                note_debit.save(update_fields=[
                    'taux_tva', 'remise_globale', 'montant_ht',
                    'montant_tva', 'montant_ttc'])
                return note_debit
            # ATOT6 — même règle que l'avoir : paniers de la facture.
            from ..domain.facturation_ops import (
                ventiler_document_depuis_facture,
            )
            ventiler_document_depuis_facture(
                note_debit, facture, partiel=bool(clean_lignes),
                lignes_saisies=clean_lignes)
            return note_debit

        note_debit = create_numbered(
            NoteDebit, facture.company, 'note_debit', _create)
        # AFAC29 (C-AFAC-027) — une note de débit AUGMENTE le reste dû : le
        # statut de paiement est re-dérivé par LE service d'ATOT8 (une facture
        # PAYÉE majorée revient au recouvrement, émise ou en retard).
        from ..domain.encaissements import recalculer_statut_paiement
        recalculer_statut_paiement(
            facture, user=request.user, source='note_debit')
        try:
            from ..utils.pdf import generate_note_debit_pdf
            generate_note_debit_pdf(note_debit.id)
            note_debit.refresh_from_db()
        except Exception:
            logger.warning("facture.FactureViewSet.creer_note_debit : erreur ignorée (mode dégradé)", exc_info=True)
        return Response(NoteDebitSerializer(note_debit).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=D.RetourClientRequest,
                   responses={201: AvoirSerializer})
    @action(detail=True, methods=['post'], url_path='retour-client',
            permission_classes=[IsResponsableOrAdmin])
    def retour_client(self, request, pk=None):
        """XPOS7 — Retour client avec re-stockage (contre ticket/facture
        d'origine). Sélectionne des lignes + quantités retournées → crée
        l'avoir référençant la facture d'origine (même chemin Avoir que
        `creer_avoir`, inchangé) + option « remettre en stock » (MouvementStock
        ENTREE via `stock.services`). Motif de retour OBLIGATOIRE. Une
        quantité retournée supérieure à ce qui a été vendu (moins les retours
        déjà actés) est refusée."""
        facture = self.get_object()
        if facture.statut not in ('emise', 'payee', 'en_retard'):
            # ENF11 — refus d'ÉTAT (brouillon, annulée) : 409.
            return Response(
                {'detail': 'Un retour ne peut être créé que depuis une '
                           'facture émise (ou payée/en retard).'},
                status=status.HTTP_409_CONFLICT)
        motif = valider_corps(request, D.RetourClientRequest)['motif'].strip()
        restocker = bool(request.data.get('restocker', False))
        lignes = request.data.get('lignes')
        if not isinstance(lignes, list) or not lignes:
            return Response(
                {'detail': 'Au moins une ligne retournée est requise.'},
                status=status.HTTP_400_BAD_REQUEST)

        # AFAC27 (C-AFAC-024) — LE constructeur unique d'avoir : quantités
        # retournables, prix/remise/TVA FACTURÉS, remise globale et palier
        # d'arrondi de la facture (au prorata, le dernier retour porte le
        # solde au centime), plafond SOUS verrou, re-stockage dans la même
        # transaction, `avoir_cree`, recalcul du statut (ATOT8).
        from ..domain.facturation_ops import AvoirRefuse, creer_avoir_facture
        try:
            avoir = creer_avoir_facture(
                facture=facture, user=request.user, motif=motif,
                retour_lignes=lignes, restocker=restocker)
        except AvoirRefuse as exc:
            return Response({'detail': exc.motif},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            from ..utils.pdf import generate_avoir_pdf
            generate_avoir_pdf(avoir.id)
            avoir.refresh_from_db()
        except Exception:
            logger.warning("facture.FactureViewSet.retour_client : erreur ignorée (mode dégradé)", exc_info=True)
        return Response(AvoirSerializer(avoir).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None,
                   responses={201: FactureSerializer, 403: D.ErreurDetail})
    @action(detail=True, methods=['post'], url_path='facturer-penalites',
            permission_classes=[IsResponsableOrAdmin])
    def facturer_penalites(self, request, pk=None):
        """XFAC6 — action OPTIONNELLE : crée une facture de frais dédiée pour
        la pénalité de retard calculée au niveau de relance courant. Ne
        modifie JAMAIS ``montant_du`` de la facture d'origine (la pénalité
        reste indicative tant que non facturée — cette action la matérialise
        volontairement en un nouveau document, séparé)."""
        from decimal import Decimal

        facture = self.get_object()
        # AFAC24 (C-AFAC-040, base) — UNE formule : la pénalité facturée est
        # la pénalité INDICATIVE de la lettre et de la liste des relances
        # (`recouvrement._current_level`), calculée sur l'EXIGIBLE (CIQ214),
        # jamais sur `montant_du` (qui compte la retenue de garantie).
        from ..recouvrement import _current_level, _levels, montant_exigible
        jr = facture.jours_retard
        niveau = _current_level(
            jr, _levels(facture.company),
            montant_du=montant_exigible(facture))
        # ENF11 — corps vide : aucun niveau atteint ou pénalité nulle sont
        # des refus d'ÉTAT (retard, réglage des niveaux) → 409.
        if niveau is None:
            return Response(
                {'detail': "Aucun niveau de relance atteint pour "
                           "cette facture."},
                status=status.HTTP_409_CONFLICT,
            )
        penalite = Decimal(niveau['penalite'])
        if penalite <= 0:
            return Response(
                {'detail': "Aucune pénalité à facturer (taux/frais à 0)."},
                status=status.HTTP_409_CONFLICT,
            )
        libelle = (
            f"Pénalités de retard — facture {facture.reference} "
            f"({jr} jour(s) de retard, {niveau['nom']})")

        def _create(ref):
            return Facture.objects.create(
                reference=ref, company=facture.company,
                client=facture.client, statut=Facture.Statut.BROUILLON,
                libelle=libelle, montant_ht=penalite,
                montant_tva=Decimal('0'), montant_ttc=penalite,
                taux_tva=Decimal('0'), created_by=request.user,
            )

        # AUD101 — la facture de pénalités passe par LE service unique : elle
        # posait EMISE sans jamais émettre `facture_emise`, donc sans écriture
        # au grand livre, et sans consulter le blocage crédit du client.
        from ..domain.facturation_ops import EmissionRefusee, emettre_facture
        from ..domain.recouvrement import CreditHoldError
        from ..models import FacturePenalite
        from django.db import IntegrityError

        def _deja_facturee(liaison):
            return Response(
                {'detail': (
                    'Pénalités déjà facturées pour ce niveau : '
                    f'{liaison.facture_penalite.reference}.')},
                status=status.HTTP_409_CONFLICT)

        try:
            with transaction.atomic():
                # AFAC50 (C-AFAC-040 a) — idempotent par (facture, niveau) :
                # verrou sur la facture d'origine, puis liaison durable lue
                # AVANT toute numérotation (un double clic ne consomme aucun
                # numéro et n'émet rien).
                Facture.objects.select_for_update().get(pk=facture.pk)
                liaison = (FacturePenalite.objects.select_for_update()
                           .select_related('facture_penalite')
                           .filter(facture_origine=facture,
                                   niveau=niveau['ordre']).first())
                if liaison is not None and \
                        liaison.facture_penalite.statut != \
                        Facture.Statut.ANNULEE:
                    return _deja_facturee(liaison)
                facture_penalite = create_provisoire(  # ATOT27
                    _create)
                emettre_facture(
                    facture_penalite, user=request.user,
                    source='penalites_retard')
                if liaison is not None:
                    # Facture de pénalités ANNULÉE : la liaison pointe la
                    # nouvelle.
                    liaison.facture_penalite = facture_penalite
                    liaison.save(update_fields=['facture_penalite'])
                else:
                    FacturePenalite.objects.create(
                        company=facture.company, facture_origine=facture,
                        niveau=niveau['ordre'],
                        facture_penalite=facture_penalite)
        except EmissionRefusee as exc:
            # ENF11 — corps vide : un refus d'émission (période verrouillée,
            # revue…) tient à l'ÉTAT → 409.
            return Response({'detail': exc.motif},
                            status=status.HTTP_409_CONFLICT)
        except CreditHoldError as exc:
            return Response({'detail': exc.motif},
                            status=status.HTTP_403_FORBIDDEN)
        except IntegrityError:
            # Course perdue contre un appel concurrent (contrainte d'unicité).
            liaison = FacturePenalite.objects.select_related(
                'facture_penalite').filter(
                    facture_origine=facture, niveau=niveau['ordre']).first()
            if liaison is None:
                raise
            return _deja_facturee(liaison)
        from .. import activity
        activity.log_facture_penalite_facturee(
            facture, request.user, facture_penalite, penalite)
        return Response(
            FactureSerializer(facture_penalite).data,
            status=status.HTTP_201_CREATED,
        )
