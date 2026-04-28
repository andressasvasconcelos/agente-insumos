"""
Cliente Claude (Anthropic API) para:
1. Validar se algum candidato realmente serve (semântica + contexto de obra)
2. Gerar nome novo no padrão da base modelo quando nada serve

Usa anthropic SDK + Claude Sonnet 4 (bom custo-benefício para o caso).
"""

import json
from anthropic import Anthropic

from core.matcher import Candidato


CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024


PROMPT_SYSTEM = """Você é um especialista em catalogação de insumos de construção civil.

Sua tarefa: ao receber uma SOLICITAÇÃO de novo insumo e uma lista de CANDIDATOS \
similares (de duas bases — ATIVA e MODELO), decidir uma de três ações:

1. **REUTILIZAR**: existe um insumo na base ATIVA que atende à solicitação \
(mesma essência técnica, mesma função na obra). Devolver o código e descrição.

2. **REVISAR_HUMANO**: há candidatos parecidos mas diferença técnica relevante \
(unidade diferente, especificação técnica distinta, marca incompatível). \
Devolver os 2-3 candidatos mais próximos com motivo da dúvida.

3. **CRIAR_NOVO**: nada serve. Gerar um nome novo seguindo RIGOROSAMENTE o padrão \
da base MODELO:
   - Title Case (Cada Palavra Maiúscula)
   - Estrutura: [Tipo] [Especificação] [Marca/Norma se relevante] [Dimensão/Medida]
   - Exemplos do padrão: "Cimento Portland Pozolanico 320", "Misturador Pia Parede 1/2\\"", \
"Argamassa Quartzolit 20 kg", "Tubo PVC Soldável 50mm"
   - Sem unidade no nome (a unidade é campo separado)
   - Sugerir SUBGRUPO da base modelo (ex: "02.013 - Metais") e UNIDADE adequada \
(un, m², m, kg, l, vb, h, m³, sc, pc, cj)

Responda SEMPRE em JSON válido, sem markdown, sem explicação fora do JSON.

Schema:
{
  "acao": "REUTILIZAR" | "REVISAR_HUMANO" | "CRIAR_NOVO",
  "justificativa": "1-2 frases explicando a decisão",
  "reutilizar": { "codigo": "...", "descricao": "..." } | null,
  "revisar": [ { "codigo": "...", "descricao": "...", "motivo_duvida": "..." } ] | null,
  "criar_novo": {
    "nome_sugerido": "Nome no padrão da base modelo",
    "subgrupo_sugerido": "XX.XXX - Nome do Subgrupo",
    "unidade_sugerida": "un|m2|m|kg|l|vb|h|m3|sc|pc|cj",
    "alternativas_de_nome": ["alternativa 1", "alternativa 2"]
  } | null
}
"""


def _formatar_candidatos(cands: list[Candidato], titulo: str) -> str:
    """Formata candidatos para o prompt do Claude."""
    if not cands:
        return f"### {titulo}\n(nenhum candidato relevante)\n"
    linhas = [f"### {titulo}"]
    for c in cands:
        unidade = f" | unidade: {c.unidade}" if c.unidade != "—" else ""
        linhas.append(
            f"- [{c.fonte}] cod={c.codigo} | score={c.score:.1f} | "
            f"grupo: {c.grupo}{unidade} | descrição: {c.descricao}"
        )
    return "\n".join(linhas) + "\n"


def consultar_claude(
    api_key: str,
    solicitacao: str,
    match_exato: Candidato | None,
    similares_ativa: list[Candidato],
    similares_modelo: list[Candidato],
) -> dict:
    """
    Chama Claude e retorna o JSON parseado com a decisão.

    Em caso de erro (API/parsing), retorna dict com 'erro' preenchido.
    """
    client = Anthropic(api_key=api_key)

    partes = [f"## SOLICITAÇÃO DO USUÁRIO\n{solicitacao}\n"]

    if match_exato:
        partes.append(
            f"## MATCH FUZZY EXATO ENCONTRADO (score {match_exato.score:.1f}%)\n"
            f"- Código: {match_exato.codigo}\n"
            f"- Descrição: {match_exato.descricao}\n"
            f"- Grupo: {match_exato.grupo}\n"
        )

    partes.append(
        _formatar_candidatos(
            similares_ativa, "TOP 5 SIMILARES NA BASE ATIVA (insumos já cadastrados)"
        )
    )
    partes.append(
        _formatar_candidatos(
            similares_modelo, "TOP 5 SIMILARES NA BASE MODELO (referência de padronização)"
        )
    )

    user_prompt = "\n".join(partes)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=PROMPT_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        texto = response.content[0].text.strip()

        # Limpar markdown caso Claude tenha adicionado
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
            texto = texto.strip()

        return json.loads(texto)

    except json.JSONDecodeError as e:
        return {
            "erro": f"Resposta do Claude não é JSON válido: {e}",
            "resposta_bruta": texto if "texto" in dir() else None,
        }
    except Exception as e:
        return {"erro": f"Erro na chamada da API: {type(e).__name__}: {e}"}
