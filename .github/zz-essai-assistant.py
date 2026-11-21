"""TEMPORAIRE (zz-scratch-assistant-2111) — essai du VRAI assistant sur un runner.

Rejoue les deux conversations de Reda du 20/11/2026 (anonymisées) et des questions
simples, contre le service d'IA réel (moteur natif, copilote allumé), puis imprime
chaque réponse, les outils appelés et les cartes. Jamais la production. Usage :
    python zz-essai-assistant.py <jeton JWT> <url du service IA>
"""
import json
import sys
import time
import urllib.request

JETON, URL = sys.argv[1], sys.argv[2].rstrip("/")


def poser(question, ecran="/crm/leads"):
    corps = json.dumps({"question": question, "contexte": {"ecran": ecran}}).encode()
    req = urllib.request.Request(URL + "/sql-agent/query", data=corps, method="POST", headers={
        "Authorization": "Bearer " + JETON, "Content-Type": "application/json"})
    debut = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as rep:
            data = json.loads(rep.read())
    except urllib.error.HTTPError as exc:
        data = {"answer": f"HTTP {exc.code} {exc.read()[:300]!r}", "cartes": []}
    cartes = data.get("cartes") or []
    props = [c.get("action_key") for c in cartes if c.get("type") == "proposition"]
    print("\n" + "=" * 100)
    print(f"Q ({ecran}) : {question}")
    print(f"-- {time.time() - debut:.1f} s ; outils : {data.get('outils_appeles')} ; "
          f"cartes : {[c.get('carte') or c.get('type') for c in cartes]} ; PROPOSITIONS : {props}")
    print("R :", data.get("answer"))
    return data, props


def effacer():
    req = urllib.request.Request(URL + "/sql-agent/history", method="DELETE",
                                 headers={"Authorization": "Bearer " + JETON})
    urllib.request.urlopen(req, timeout=30).read()


bilan = {}
effacer()
_, p1 = poser("Créer un nouveau client et rajoute qu'il a une facture de 600 dirhams et qu'il habite à "
              "Souhail, je veux que tu me fasses un devis pour ce client, il s'appelle Hamza Essai")
_, p2 = poser("Safi est la ville", ecran="/apps")
_, p3 = poser("Non change le nombre de panneaux à 8 panneaux pour les deux solutions", ecran="/apps")
_, p4 = poser("Ajoute 2 Smart Meter au devis", ecran="/apps")
_, p5 = poser("Ok donne moi le nouveau devis", ecran="/apps")
bilan["devis_en_un_tour_propositions"] = p1 + p2 + p3 + p4 + p5

effacer()
_, q1 = poser("10 panneaux solaires avec onduleur triphasé de 10kw et une batterie de 5kwh pour commencer. "
              "Make a quote for this client. Name : Mehdi Essai, number : +212 600 000 111, Casablanca")
_, q2 = poser("N'utilise pas la structure acier, mets la structure aluminium à la place", ecran="/apps")
bilan["mehdi_propositions"] = q1 + q2

effacer()
for question, ecran in (
        ("Combien de leads froids j'ai ?", "/crm/leads"),
        ("Qui dois-je relancer aujourd'hui ?", "/crm/relances"),
        ("Où je modifie les modèles de messages ?", "/crm/leads"),
        ("Comment je planifie une visite technique ?", "/crm/leads"),
        ("Quel est le prix du panneau 710 W ?", "/ventes/devis"),
        ("Combien de devis ont été créés ce mois-ci ?", "/ventes/devis"),
        ("C'est quoi le total du devis de Hamza Essai, option par option ?", "/ventes/devis"),
        ("Qui est le responsable du lead Mehdi Essai ?", "/crm/leads"),
        ("Comment je délègue mes dossiers à une collègue ?", "/crm/relances"),
        ("Mon point du matin", "/crm/cockpit"),
        ("Quelles factures sont impayées ?", "/ventes/factures"),
        ("Combien de batteries il reste en stock ?", "/stock"),
):
    poser(question, ecran)

print("\n" + "=" * 100)
print("BILAN :", json.dumps(bilan, ensure_ascii=False))
