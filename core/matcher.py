"""
Matcher híbrido: fuzzy (RapidFuzz) + semântico (sentence-transformers).

Pipeline:
1. Normaliza a query
2. Busca fuzzy ≥ 95% na base ATIVA → match exato (evita duplicata)
3. Se não achou: busca semântica top-N na base ATIVA + base MODELO
4. Retorna candidatos ranqueados com score
"""

from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from sentence_transformers import SentenceTransformer

from core.normalizer import normalizar


# Modelo SBERT multilíngue, leve e bom em PT-BR
# 'paraphrase-multilingual-MiniLM-L12-v2' tem ~470MB e roda em CPU
SBERT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Limiares
FUZZY_EXATO_THRESHOLD = 95   # ≥ 95% → considerado match exato/duplicata
TOP_N_SEMANTICO = 5          # quantos candidatos por base


@dataclass
class Candidato:
    fonte: Literal["ativa", "modelo"]
    codigo: str
    descricao: str
    grupo: str
    unidade: str
    score: float  # 0..100
    tipo_match: Literal["exato", "semantico"]


class Matcher:
    """Encapsula bases + embeddings em memória."""

    def __init__(self, base_ativa: pd.DataFrame, base_modelo: pd.DataFrame):
        self.base_ativa = base_ativa.copy()
        self.base_modelo = base_modelo.copy()

        # Pré-normalizar para fuzzy
        self.base_ativa["_norm"] = self.base_ativa["descricao"].apply(normalizar)
        self.base_modelo["_norm"] = self.base_modelo["descricao"].apply(normalizar)

        # Carregar modelo SBERT (lazy se quiser, mas Streamlit cacheia o objeto)
        self.model = SentenceTransformer(SBERT_MODEL_NAME)

        # Pré-computar embeddings (custo: ~30s na 1ª execução, depois cacheado)
        self.emb_ativa = self.model.encode(
            self.base_ativa["_norm"].tolist(),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        self.emb_modelo = self.model.encode(
            self.base_modelo["_norm"].tolist(),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def buscar_fuzzy_exato(self, query_norm: str) -> Candidato | None:
        """
        Busca match fuzzy ≥ FUZZY_EXATO_THRESHOLD na base ATIVA.
        Retorna o melhor match se encontrado, senão None.
        """
        choices = self.base_ativa["_norm"].tolist()
        if not choices:
            return None
        result = process.extractOne(
            query_norm, choices, scorer=fuzz.token_sort_ratio
        )
        if result is None:
            return None
        match_str, score, idx = result
        if score >= FUZZY_EXATO_THRESHOLD:
            row = self.base_ativa.iloc[idx]
            return Candidato(
                fonte="ativa",
                codigo=str(row["codigo"]),
                descricao=row["descricao"],
                grupo=row.get("grupo", "—"),
                unidade="—",  # base ativa não tem unidade
                score=float(score),
                tipo_match="exato",
            )
        return None

    def buscar_semantico(
        self, query_norm: str, top_n: int = TOP_N_SEMANTICO
    ) -> tuple[list[Candidato], list[Candidato]]:
        """
        Busca semântica top-N em ambas as bases.
        Retorna (candidatos_ativa, candidatos_modelo).
        """
        q_emb = self.model.encode(
            [query_norm],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        # Cosseno = produto interno (já normalizado)
        sim_ativa = self.emb_ativa @ q_emb
        sim_modelo = self.emb_modelo @ q_emb

        idx_ativa = np.argsort(-sim_ativa)[:top_n]
        idx_modelo = np.argsort(-sim_modelo)[:top_n]

        cands_ativa = [
            Candidato(
                fonte="ativa",
                codigo=str(self.base_ativa.iloc[i]["codigo"]),
                descricao=self.base_ativa.iloc[i]["descricao"],
                grupo=self.base_ativa.iloc[i].get("grupo", "—"),
                unidade="—",
                score=float(sim_ativa[i] * 100),  # 0..100
                tipo_match="semantico",
            )
            for i in idx_ativa
        ]

        cands_modelo = [
            Candidato(
                fonte="modelo",
                codigo=str(self.base_modelo.iloc[i]["codigo"]),
                descricao=self.base_modelo.iloc[i]["descricao"],
                grupo=str(self.base_modelo.iloc[i].get("subgrupo", "—")),
                unidade=str(self.base_modelo.iloc[i].get("unidade", "—")),
                score=float(sim_modelo[i] * 100),
                tipo_match="semantico",
            )
            for i in idx_modelo
        ]

        return cands_ativa, cands_modelo

    def buscar(self, query: str) -> dict:
        """
        Pipeline completo. Retorna dict pronto para a UI:
        {
          'query': str,
          'query_normalizada': str,
          'match_exato': Candidato | None,
          'similares_ativa': list[Candidato],
          'similares_modelo': list[Candidato],
        }
        """
        query_norm = normalizar(query)
        match_exato = self.buscar_fuzzy_exato(query_norm)
        sim_ativa, sim_modelo = self.buscar_semantico(query_norm)

        return {
            "query": query,
            "query_normalizada": query_norm,
            "match_exato": match_exato,
            "similares_ativa": sim_ativa,
            "similares_modelo": sim_modelo,
        }
