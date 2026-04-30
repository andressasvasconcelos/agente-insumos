"""
claude_client.py  v2.2
Envia contexto ao Claude e interpreta a decisão JSON.
"""

import json
import anthropic


PROMPT_SYSTEM = """Você é um especialista em cadastro de insumos para construção civil
no sistema Sienge da empresa All Wert Construtora.

Você receberá:
1. A solicitação bruta do usuário
2. O motivo da utilização (onde e como será usado) — use isso para afinar a classificação
3. Os top candidatos da base ATIVA (insumos já cadastrados)
4. Os top candidatos da base MODELO (referência de nomenclatura)
5. A lista completa de GRUPOS DE INSUMO disponíveis no Sienge
6. A lista completa de CONTAS FINANCEIRAS disponíveis no plano de contas

Sua tarefa: analisar e retornar EXCLUSIVAMENTE um JSON válido, sem texto fora do JSON.

Escolha UMA das três ações:

━━━ REUTILIZAR ━━━
Use quando um insumo da base ATIVA é semanticamente idêntico à solicitação.
{
  "acao": "REUTILIZAR",
  "justificativa": "string",
  "reutilizar": {
    "codigo": "string",
    "descricao": "string",
    "grupo": "string",
    "conta_financeira_codigo": "string",
    "conta_financeira_descricao": "string"
  }
}

━━━ REVISAR_HUMANO ━━━
Use quando há candidatos parecidos mas com diferença técnica relevante.
{
  "acao": "REVISAR_HUMANO",
  "justificativa": "string",
  "revisar": [
    {
      "codigo": "string",
      "descricao": "string",
      "motivo_duvida": "string"
    }
  ]
}

━━━ CRIAR_NOVO ━━━
Use quando nenhum candidato serve. Gere nome no padrão da base modelo
e classifique com o grupo de insumo e conta financeira mais adequados.
{
  "acao": "CRIAR_NOVO",
  "justificativa": "string",
  "criar_novo": {
    "nome_sugerido": "string (nome padronizado para cadastro no Sienge)",
    "grupo_insumo": {
      "ref": "string",
      "descricao": "string",
      "tipo": "string"
    },
    "conta_financeira": {
      "codigo": "string",
      "descricao": "string"
    },
    "unidade_sugerida": "string",
    "alternativas_de_nome": ["string", "string"]
  }
}

Regras:
- Use o motivo da utilização para escolher o grupo e conta corretos
- Siga EXATAMENTE o padrão de nomenclatura dos insumos da base modelo
- Escolha grupo e conta SOMENTE da lista fornecida — nunca invente
- Retorne SOMENTE o JSON, sem markdown, sem texto fora do JSON
"""


def _montar_contexto(
    solicitacao: str,
    motivo: str,
    match_exato,
    similares_ativa: list,
    similares_modelo: list,
    grupos: list,
    contas: list,
) -> str:
    linhas = [f"SOLICITAÇÃO: {solicitacao}\n"]

    if motivo:
        linhas.append(f"MOTIVO / ONDE SERÁ USADO: {motivo}\n")

    if match_exato:
        m = match_exato if isinstance(match_exato, dict) else vars(match_exato)
        linhas.append(
            f"MATCH EXATO NA BASE ATIVA (score {float(m.get('score',0)):.1f}%):\n"
            f"  Código: {m.get('codigo','')} | {m.get('descricao','')} | "
            f"Grupo: {m.get('grupo','')} | "
            f"Conta: {m.get('cod_conta','')} — {m.get('conta_financeira','')}\n"
        )

    linhas.append("TOP CANDIDATOS — BASE ATIVA:")
    for c in similares_ativa:
        cd = c if isinstance(c, dict) else vars(c)
        linhas.append(
            f"  [{float(cd.get('score',0)):.1f}%] Cód {cd.get('codigo','')} | "
            f"{cd.get('descricao','')} | Grupo: {cd.get('grupo','')} | "
            f"Conta: {cd.get('cod_conta','')} — {cd.get('conta_financeira','')}"
        )

    linhas.append("\nTOP CANDIDATOS — BASE MODELO:")
    for c in similares_modelo:
        cd = c if isinstance(c, dict) else vars(c)
        linhas.append(
            f"  [{float(cd.get('score',0)):.1f}%] Cód {cd.get('codigo','')} | "
            f"{cd.get('descricao','')} | Subgrupo: {cd.get('grupo','')} | "
            f"Un: {cd.get('unidade','')}"
        )

    if grupos:
        linhas.append("\nGRUPOS DE INSUMO DISPONÍVEIS:")
        for g in grupos:
            linhas.append(
                f"  Ref {g.get('ref','')} | {g.get('descricao','')} | Tipo: {g.get('tipo','')}"
            )

    if contas:
        linhas.append("\nCONTAS FINANCEIRAS DISPONÍVEIS:")
        for ct in contas:
            linhas.append(f"  {ct.get('codigo','')} | {ct.get('descricao','')}")

    return "\n".join(linhas)


def consultar_claude(
    api_key: str,
    solicitacao: str,
    match_exato,
    similares_ativa: list,
    similares_modelo: list,
    motivo: str = "",
    grupos: list = None,
    contas: list = None,
) -> dict:
    client = anthropic.Anthropic(api_key=api_key)

    contexto = _montar_contexto(
        solicitacao=solicitacao,
        motivo=motivo,
        match_exato=match_exato,
        similares_ativa=similares_ativa,
        similares_modelo=similares_modelo,
        grupos=grupos or [],
        contas=contas or [],
    )

    resposta_bruta = ""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=PROMPT_SYSTEM,
            messages=[{"role": "user", "content": contexto}],
        )
        resposta_bruta = msg.content[0].text.strip()

        if resposta_bruta.startswith("```"):
            resposta_bruta = resposta_bruta.split("```")[1]
            if resposta_bruta.startswith("json"):
                resposta_bruta = resposta_bruta[4:]

        return json.loads(resposta_bruta)

    except json.JSONDecodeError as e:
        return {"erro": f"JSON inválido: {e}", "resposta_bruta": resposta_bruta}
    except Exception as e:
        return {"erro": str(e)}
