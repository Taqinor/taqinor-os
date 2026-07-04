"""XPUR21 — réponse fournisseur en ligne à une RFQ, SANS LOGIN.

Le lien envoyé (XPUR20) mène à cette page publique tokenisée PAR (RFQ,
fournisseur) : le fournisseur saisit prix/délai/validité/commentaire →
crée ou complète SA PROPRE ``RFQOffre`` (idempotent : re-soumettre tant que
la RFQ n'est pas clôturée MET À JOUR la même offre). Le token est unique par
(RFQ, fournisseur), expire à ``date_limite_reponse``, est révocable, et ne
montre JAMAIS les offres des autres fournisseurs ni un prix interne (aucun
``prix_achat``/marge n'existe sur ce modèle — seul le montant proposé PAR CE
fournisseur transite)."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RFQConsultation, RFQOffre


def _consultation_or_404(token):
    return RFQConsultation.objects.select_related(
        'rfq', 'fournisseur').filter(token=token).first()


def _public_payload(consultation):
    rfq = consultation.rfq
    offre = consultation.offre
    return {
        'reference': rfq.reference,
        'objet': rfq.objet,
        'date_limite_reponse': rfq.date_limite_reponse,
        'fournisseur_nom': getattr(consultation.fournisseur, 'nom', ''),
        'cloturee': rfq.statut == rfq.Statut.CLOTUREE,
        'offre': {
            'montant_ht': offre.montant_ht if offre else None,
            'delai_jours': offre.delai_jours if offre else None,
            'validite_jours': offre.validite_jours if offre else None,
            'note': offre.note if offre else '',
        } if offre else None,
    }


class RFQConsultationPublicView(APIView):
    """XPUR21 — GET affiche la RFQ (sans prix interne, sans autres offres) +
    la propre offre déjà soumise (le cas échéant). POST crée/complète
    l'offre du fournisseur — idempotent tant que la RFQ n'est pas clôturée.
    Token invalide/expiré/révoqué → 404 (jamais 403 : on ne confirme pas
    l'existence du token à un tiers)."""
    permission_classes = [AllowAny]

    def get(self, request, token):
        consultation = _consultation_or_404(token)
        if consultation is None or not consultation.is_valid:
            return Response(
                {'detail': 'Lien invalide ou expiré.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(_public_payload(consultation))

    def post(self, request, token):
        consultation = _consultation_or_404(token)
        if consultation is None or not consultation.is_valid:
            return Response(
                {'detail': 'Lien invalide ou expiré.'},
                status=status.HTTP_404_NOT_FOUND)
        rfq = consultation.rfq
        if rfq.statut == rfq.Statut.CLOTUREE:
            return Response(
                {'detail': 'Cette demande de prix est clôturée.'},
                status=status.HTTP_400_BAD_REQUEST)
        data = request.data
        montant = data.get('montant_ht')
        try:
            montant = float(montant)
        except (TypeError, ValueError):
            return Response(
                {'montant_ht': 'Montant invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        if montant < 0:
            return Response(
                {'montant_ht': 'Le montant HT ne peut pas être négatif.'},
                status=status.HTTP_400_BAD_REQUEST)

        def _int_or_none(value):
            try:
                return int(value) if value not in (None, '') else None
            except (TypeError, ValueError):
                return None

        offre = consultation.offre
        if offre is None:
            offre = RFQOffre.objects.create(
                company=rfq.company, rfq=rfq,
                fournisseur=consultation.fournisseur,
                montant_ht=montant,
                delai_jours=_int_or_none(data.get('delai_jours')),
                validite_jours=_int_or_none(data.get('validite_jours')),
                note=(data.get('note') or '').strip())
            consultation.offre = offre
            consultation.save(update_fields=['offre', 'date_modification'])
        else:
            offre.montant_ht = montant
            offre.delai_jours = _int_or_none(data.get('delai_jours'))
            offre.validite_jours = _int_or_none(data.get('validite_jours'))
            offre.note = (data.get('note') or '').strip()
            offre.save(update_fields=[
                'montant_ht', 'delai_jours', 'validite_jours', 'note',
                'date_modification'])
        return Response(
            _public_payload(consultation), status=status.HTTP_200_OK)
