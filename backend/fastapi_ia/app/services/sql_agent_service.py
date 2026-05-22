"""
Service Agent SQL — LangChain SQL Agent sur PostgreSQL.
TODO Phase 3 (Sem. 5-6) : implémenter la logique LangChain.
"""
from __future__ import annotations

import os
from typing import Any


# TODO Sem. 5 : décommenter et implémenter
# from langchain_community.utilities import SQLDatabase
# from langchain_community.agent_toolkits import create_sql_agent
# from langchain_openai import ChatOpenAI
# from sqlalchemy import create_engine


class SQLAgentService:
    """
    Encapsule le LangChain SQL Agent qui répond aux questions
    en langage naturel en interrogeant PostgreSQL.

    Architecture (Phase 3) :
        Question NL → LLM → SQL → DB → Résultat → Réponse NL
    """

    def __init__(self) -> None:
        self._agent = None  # lazy init

    def _get_agent(self):
        """
        Initialise l'agent LangChain SQL à la première utilisation.

        TODO Sem. 5 :
        1. Créer un SQLAlchemy engine sur DATABASE_URL
        2. Créer un SQLDatabase LangChain
        3. Créer le ChatOpenAI ou ChatAnthropic LLM
        4. Créer le sql_agent avec create_sql_agent
        5. Configurer le prefix de sécurité (lecture seule)
        """
        if self._agent is None:
            # PLACEHOLDER
            pass
        return self._agent

    async def query(self, question: str, user_id: int | None = None) -> dict[str, Any]:
        """
        Exécute une question en langage naturel via l'agent SQL.

        Args:
            question: La question en langage naturel (ex: "Quel est le chiffre d'affaires du mois?")
            user_id: ID de l'utilisateur pour le logging

        Returns:
            {
              "answer": str,       # Réponse en langage naturel
              "sql_query": str,    # Requête SQL générée
              "data": list | None  # Données brutes (optionnel)
            }

        TODO Sem. 5 :
            agent = self._get_agent()
            result = await agent.ainvoke({"input": question})
            return {"answer": result["output"], "sql_query": ..., "data": ...}
        """
        # PLACEHOLDER — retourne une réponse simulée en attendant
        return {
            "answer": f"(TODO) Réponse simulée pour : '{question}'",
            "sql_query": "-- SQL sera généré ici",
            "data": None,
        }

    async def get_schema_summary(self) -> dict[str, Any]:
        """
        Retourne un résumé du schéma de la base de données.

        TODO Sem. 5 : utiliser db.get_table_info() de LangChain.
        """
        # PLACEHOLDER
        tables = [
            "auth_user", "stock_produit", "stock_mouvementstock",
            "crm_client", "ventes_devis", "ventes_ligndevis",
            "ventes_boncommande", "ventes_facture", "ventes_lignefacture",
        ]
        return {"tables": tables, "status": "placeholder"}


# Singleton exporté
sql_agent_service = SQLAgentService()
