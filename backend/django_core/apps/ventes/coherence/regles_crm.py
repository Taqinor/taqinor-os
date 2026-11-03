"""QA-COHERENCE — invariants CRM ↔ ventes (lecture par ``apps.crm.selectors``).

Frontière cross-app (CLAUDE.md) : aucune importation des modèles CRM ici ;
l'étape SIGNED vient de STAGES.py via ``apps.crm.stages`` à l'intérieur du
sélecteur, jamais codée en dur.

Invariant écarté après lecture du code : « ``devis.client`` ≠ client résolu
du lead ». ``Lead.client`` est « rempli au premier devis OU MANUELLEMENT »
(apps/crm/models.py) et reste modifiable ensuite — un devis ancien peut donc
légitimement pointer l'ancien client. Règle non fiable, non ajoutée.
"""
from __future__ import annotations

from .registre import GRAVITE_AVERTISSEMENT, PORTEE_SOCIETE, regle


@regle('CRM_SIGNE_SANS_DEVIS_ACCEPTE',
       "Lead à l'étape Signé sans aucun devis accepté (« signé fantôme »)",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_SOCIETE)
def signe_sans_devis_accepte(r, company, ctx):
    """Décision fondateur U11 (apps/crm/services.py,
    ``lead_signe_sans_devis_actif``) : le funnel ne recule jamais, donc un
    lead peut rester SIGNED alors que son seul devis accepté a disparu — on
    le SIGNALE sans reculer l'étape. Leads perdus, archivés et importés
    d'Odoo exclus (voir le sélecteur)."""
    from apps.crm.selectors import leads_signes_sans_devis_accepte
    return [r.violation(
        None, "Lead à l'étape Signé sans devis accepté.",
        object_type='lead', object_id=lead['id'],
        reference=f"LEAD-{lead['id']}", company_id=company.pk,
        valeurs={'stage': lead['stage'], 'source': lead['source']},
        attendu='au moins un devis accepté')
        for lead in leads_signes_sans_devis_accepte(company)]


@regle('CRM_FROID_SANS_RAISON',
       "Lead Froid vivant sans raison de parcage (parc_raison vide)",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_SOCIETE)
def froid_sans_raison(r, company, ctx):
    """CADV76 (conception v4 §2 invariant 2, §6.2) — un lead au Froid doit dire
    POURQUOI il y est. Ni perdu, ni archivé, ni opposé (leur raison est le motif
    ou le drapeau) : voir ``leads_froid_sans_raison``. Aucune donnée personnelle."""
    from apps.crm.selectors import leads_froid_sans_raison
    return [r.violation(
        None, "Lead Froid sans raison de parcage.",
        object_type='lead', object_id=lead['id'],
        reference=f"LEAD-{lead['id']}", company_id=company.pk,
        valeurs={'stage': lead['stage'], 'source': lead['source']},
        attendu='une raison de parcage (parc_raison)')
        for lead in leads_froid_sans_raison(company)]


def _violations_lead(r, company, lignes, message, attendu):
    return [r.violation(
        None, message,
        object_type='lead', object_id=lead['id'],
        reference=f"LEAD-{lead['id']}", company_id=company.pk,
        valeurs={'stage': lead['stage'], 'source': lead['source']},
        attendu=attendu)
        for lead in lignes]


@regle('CRM_ACTIF_SANS_PROCHAINE_ETAPE',
       "Lead actif sans touche ouverte ni Standby daté à venir",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_SOCIETE)
def actif_sans_prochaine_etape(r, company, ctx):
    """CADV6 (conception v4 §6.2) — un prospect actif doit toujours avoir une suite."""
    from apps.crm.selectors import leads_actifs_sans_prochaine_etape
    return _violations_lead(
        r, company, leads_actifs_sans_prochaine_etape(company),
        "Lead actif sans prochaine étape.",
        'une touche ouverte ou un Standby daté à venir')


@regle('CRM_PARC_SANS_TOUCHE',
       "Lead parqué sans les appels ou touches qui justifient le parcage",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_SOCIETE)
def parc_sans_touche(r, company, ctx):
    """CADV6 — « injoignable » avec moins de 5 appels tracés, ou parcage à 0 touche."""
    from apps.crm.selectors import leads_parques_sans_touche
    return _violations_lead(
        r, company, leads_parques_sans_touche(company),
        "Lead parqué sans les touches qui justifient le parcage.",
        'les appels exigés (injoignable) ou au moins une touche humaine')


@regle('CRM_REVEIL_SANS_HISTORIQUE',
       "Réveil ouvert sur un lead jamais joint ni chiffré",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_SOCIETE)
def reveil_sans_historique(r, company, ctx):
    """CADV6 — un réveil n'a rien à réveiller sans conversation ni proposition."""
    from apps.crm.selectors import leads_reveil_aveugle
    return _violations_lead(
        r, company, leads_reveil_aveugle(company),
        "Réveil ouvert sur un lead jamais joint ni chiffré.",
        'aucun réveil ouvert sans conversation ni devis')


@regle('CRM_FERME_AVEC_TOUCHE_OUVERTE',
       "Lead perdu, archivé ou opposé avec une touche encore à faire",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_SOCIETE)
def ferme_avec_touche_ouverte(r, company, ctx):
    """CADV6 — un lead fermé n'a plus de touche à faire (hors réveil saisonnier voulu)."""
    from apps.crm.selectors import leads_fermes_avec_touche_ouverte
    return _violations_lead(
        r, company, leads_fermes_avec_touche_ouverte(company),
        "Lead fermé avec une touche encore à faire.",
        'aucune touche ouverte sur un lead perdu, archivé ou opposé')


@regle('CRM_SAISIE_JOINT_ANORMALE',
       "Taux de « joint » anormal sur une semaine pour un utilisateur",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_SOCIETE)
def saisie_joint_anormale(r, company, ctx):
    """CADV6 (conception v4 §7.5) — « joint » veut dire une conversation : au-delà de
    25 % (WhatsApp) ou 70 % (appel) sur 7 jours et 10 saisies, on regarde la saisie."""
    from apps.crm.selectors import saisies_joint_anormales
    return [r.violation(
        None, "Taux de « joint » anormal sur 7 jours.",
        object_type='utilisateur', object_id=ligne['user_id'],
        reference=f"USER-{ligne['user_id']}-{ligne['canal']}",
        company_id=company.pk, cle={'canal': ligne['canal']},
        valeurs={'canal': ligne['canal'], 'saisies': ligne['saisies'],
                 'joints': ligne['joints']},
        attendu='« joint » seulement pour une conversation réelle')
        for ligne in saisies_joint_anormales(company)]
