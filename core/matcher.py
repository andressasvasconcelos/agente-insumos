"""
matcher.py  v2.2
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer
import numpy as np

from core.normalizer import normalizar


FUZZY_EXATO_THRESHOLD = 95
TOP_N = 5
SBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


@dataclass
class Candidato:
    codigo: str
    descricao: str
    grupo: str
    unidade: str
    score: float
    cod_conta: str = ""
    conta_financeira: str = ""


class Matcher:
    def __init__(self, base_ativa: pd.DataFrame, base_modelo: pd.DataFrame):
        self.base_ativa  = base_ativa
        self.base_modelo = base_modelo

        self._ativa_norm  = base_ativa["descricao"].fillna("").apply(normalizar).tolist()
        self._modelo_norm = base_modelo["descricao"].fillna("").apply(normalizar).tolist()

        self._model = SentenceTransformer(SBERT_MODEL)
        self._emb_ativa = self._model.encode(
            self._ativa_norm, batch_size=64,
            show_progress_bar=False, normalize_embeddings=True
        )
        self._emb_modelo = self._model.encode(
            self._modelo_norm, batch_size=64,
            show_progress_bar=False, normalize_embeddings=True
        )

    def _to_candidato_ativa(self, row: dict, score: float) -> Candidato:
        return Candidato(
            codigo=str(row.get("codigo", "")),
            descricao=str(row.get("descricao", "")),
            grupo=str(row.get("grupo", "")),
            unidade=str(row.get("unidade", "")),
            score=score,
            cod_conta=str(row.get("cod_conta", "")),
            conta_financeira=str(row.get("conta_financeira", "")),
        )

    def _to_candidato_modelo(self, row: dict, score: float) -> Candidato:
        return Candidato(
            codigo=str(row.get("codigo", row.get("subgrupo_cod", ""))),
            descricao=str(row.get("descricao", "")),
            grupo=str(row.get("subgrupo", row.get("grupo", ""))),
            unidade=str(row.get("unidade", "")),
            score=score,
        )

    def buscar(self, query: str, motivo: str = "") -> dict:
        query_norm = normalizar(query)

        if motivo.strip():
            query_enriquecida = normalizar(f"{query} {motivo}")
        else:
            query_enriquecida = query_norm

        # Match exato fuzzy (só pelo nome)
        scores_fuzzy = [fuzz.token_sort_ratio(query_norm, d) for d in self._ativa_norm]
        melhor_idx   = int(np.argmax(scores_fuzzy))
        melhor_score = scores_fuzzy[melhor_idx]
        match_exato  = None
        if melhor_score >= FUZZY_EXATO_THRESHOLD:
            row = self.base_ativa.iloc[melhor_idx].to_dict()
            match_exato = self._to_candidato_ativa(row, melhor_score)

        # Embedding com query enriquecida
        emb_query = self._model.encode(
            [query_enriquecida], normalize_embeddings=True,
            show_progress_bar=False
        )[0]

        sims_ativa = (self._emb_ativa @ emb_query) * 100
        top_ativa  = np.argsort(sims_ativa)[::-1][:TOP_N]
        similares_ativa = [
            self._to_candidato_ativa(
                self.base_ativa.iloc[i].to_dict(), float(sims_ativa[i])
            )
            for i in top_ativa
        ]

        sims_modelo = (self._emb_modelo @ emb_query) * 100
        top_modelo  = np.argsort(sims_modelo)[::-1][:TOP_N]
        similares_modelo = [
            self._to_candidato_modelo(
                self.base_modelo.iloc[i].to_dict(), float(sims_modelo[i])
            )
            for i in top_modelo
        ]

        return {
            "query":             query,
            "query_normalizada": query_norm,
            "query_enriquecida": query_enriquecida,
            "match_exato":       match_exato,
            "similares_ativa":   similares_ativa,
            "similares_modelo":  similares_modelo,
        }
