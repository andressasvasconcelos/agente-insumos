"""
Agente de Cadastro de Insumos — All Wert Construtora
=====================================================

Versão 2 — Alterações em relação à v1:
- Base ativa atualizada (4.367 insumos ativos exportados do Sienge)
- Recomendação CRIAR_NOVO exibe: Nome sugerido · Conta Financeira · Grupo de Insumo
- Grupos de insumo e plano de contas carregados como referência para o Claude
"""

import streamlit as st
import pandas as pd

from core.matcher import Matcher
from core.claude_client import consultar_claude


st.set_page_config(
    page_title="Agente de Insumos — All Wert",
    page_icon="🏗️",
    layout="wide",
)


# ============================================================
# CACHE DE RECURSOS PESADOS
# ============================================================

@st.cache_resource(show_spinner="Carregando bases e modelo de IA (1ª vez ~30s)...")
def carregar_matcher() -> Matcher:
    base_ativa = pd.read_csv("data/base_ativa.csv", dtype=str).fillna("")
    base_modelo = pd.read_csv("data/base_modelo.csv", dtype=str).fillna("")
    return Matcher(base_ativa, base_modelo)


@st.cache_data
def carregar_referencias():
    grupos = pd.read_csv("data/grupos_insumo.csv", dtype=str).fillna("").to_dict("records")
    contas = pd.read_csv("data/contas_financeiras.csv", dtype=str).fillna("").to_dict("records")
    return grupos, contas


# ============================================================
# UI — SIDEBAR
# ============================================================

st.title("🏗️ Agente de Cadastro de Insumos")
st.caption(
    "Verifica se a solicitação pode reutilizar um insumo existente ou "
    "gera um nome padronizado com grupo e conta financeira para cadastro no Sienge."
)

with st.sidebar:
    st.header("⚙️ Configuração")

    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            help="Crie em console.anthropic.com. Em produção, configure via Streamlit Secrets.",
        )

    usar_claude = st.checkbox(
        "Usar Claude para validação e geração",
        value=bool(api_key),
        disabled=not api_key,
        help="Sem Claude, o agente devolve apenas os candidatos rankeados.",
    )

    st.divider()
    st.subheader("📊 Bases carregadas")
    matcher = carregar_matcher()
    grupos, contas = carregar_referencias()

    st.metric("Insumos na base ATIVA", len(matcher.base_ativa))
    st.metric("Insumos na base MODELO", len(matcher.base_modelo))
    st.metric("Grupos de insumo", len(grupos))
    st.metric("Contas financeiras", len(contas))


# ============================================================
# INPUT PRINCIPAL
# ============================================================

col1, col2 = st.columns([3, 1])
with col1:
    solicitacao = st.text_input(
        "Digite a solicitação de novo insumo:",
        placeholder="ex: Cimento CP-II 50kg / Argamassa colante interna / Tubo PVC 100mm",
    )
with col2:
    st.write("")
    st.write("")
    buscar = st.button("🔍 Analisar", type="primary", use_container_width=True)


# ============================================================
# EXECUÇÃO
# ============================================================

if buscar and solicitacao.strip():
    with st.spinner("Buscando candidatos..."):
        resultado = matcher.buscar(solicitacao)

    # --- Query ---
    st.divider()
    st.subheader("📥 Solicitação analisada")
    c1, c2 = st.columns(2)
    c1.write(f"**Original:** `{resultado.query}`")
    c2.write(f"**Normalizada:** `{resultado.query_normalizada}`")

    # --- Match exato ---
    st.subheader("🎯 Match exato na base ATIVA")
    if resultado.match_exato:
        m = resultado.match_exato
        st.success(
            f"**JÁ EXISTE** — código `{m.codigo}` | score {m.score:.1f}%\n\n"
            f"📦 **{m.descricao}**  \n"
            f"Grupo: {m.grupo}  |  Conta: `{m.cod_conta}` — {m.conta_financeira}"
        )
    else:
        st.info("Nenhum match exato encontrado (≥ 95% de similaridade).")

    # --- Similares ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📋 Top 5 — Base ATIVA")
        df_a = pd.DataFrame([
            {
                "Código": c.codigo,
                "Descrição": c.descricao,
                "Grupo": c.grupo,
                "Conta": c.cod_conta,
                "Score": f"{c.score:.1f}",
            }
            for c in resultado.similares_ativa
        ])
        st.dataframe(df_a, use_container_width=True, hide_index=True)

    with col_b:
        st.subheader("📋 Top 5 — Base MODELO")
        df_m = pd.DataFrame([
            {
                "Código": c.codigo,
                "Descrição": c.descricao,
                "Subgrupo": c.grupo,
                "Un.": c.unidade,
                "Score": f"{c.score:.1f}",
            }
            for c in resultado.similares_modelo
        ])
        st.dataframe(df_m, use_container_width=True, hide_index=True)

    # --- Claude ---
    if usar_claude and api_key:
        st.divider()
        st.subheader("🤖 Recomendação do Agente (Claude)")

        with st.spinner("Consultando Claude..."):
            decisao = consultar_claude(
                api_key=api_key,
                solicitacao=solicitacao,
                match_exato=resultado.match_exato,
                similares_ativa=resultado.similares_ativa,
                similares_modelo=resultado.similares_modelo,
                grupos=grupos,
                contas=contas,
            )

        if "erro" in decisao:
            st.error(f"Erro: {decisao['erro']}")
            if decisao.get("resposta_bruta"):
                with st.expander("Resposta bruta"):
                    st.code(decisao["resposta_bruta"])
        else:
            acao = decisao.get("acao", "?")
            just = decisao.get("justificativa", "")

            # ── REUTILIZAR ──
            if acao == "REUTILIZAR":
                r = decisao.get("reutilizar", {}) or {}
                st.success(f"✅ **REUTILIZAR**\n\n{just}")

                col1, col2, col3 = st.columns(3)
                col1.metric("Código", r.get("codigo", "—"))
                col2.metric("Insumo", r.get("descricao", "—"))
                col3.metric("Grupo", r.get("grupo", "—"))

                if r.get("conta_financeira_codigo"):
                    st.info(
                        f"💰 Conta Financeira: `{r.get('conta_financeira_codigo')}` — "
                        f"{r.get('conta_financeira_descricao', '')}"
                    )

            # ── REVISAR_HUMANO ──
            elif acao == "REVISAR_HUMANO":
                st.warning(f"⚠️ **REVISAR MANUALMENTE**\n\n{just}")
                for r in decisao.get("revisar", []) or []:
                    st.markdown(
                        f"- **{r.get('codigo')}** — {r.get('descricao')}  \n"
                        f"  *Dúvida:* {r.get('motivo_duvida')}"
                    )

            # ── CRIAR_NOVO ──
            elif acao == "CRIAR_NOVO":
                c = decisao.get("criar_novo", {}) or {}
                st.info(f"🆕 **CRIAR NOVO INSUMO**\n\n{just}")

                # Campos principais em destaque
                col1, col2, col3 = st.columns(3)
                col1.metric("📝 Nome sugerido", c.get("nome_sugerido", "—"))

                grupo = c.get("grupo_insumo", {}) or {}
                col2.metric(
                    "🗂️ Grupo de Insumo",
                    grupo.get("descricao", "—"),
                    help=f"Ref: {grupo.get('ref', '')}",
                )

                conta = c.get("conta_financeira", {}) or {}
                col3.metric(
                    "💰 Conta Financeira",
                    conta.get("descricao", "—"),
                    help=f"Código: {conta.get('codigo', '')}",
                )

                # Linha com detalhes adicionais
                colA, colB = st.columns(2)
                colA.write(f"**Código da conta:** `{conta.get('codigo', '—')}`")
                colB.write(f"**Unidade sugerida:** `{c.get('unidade_sugerida', '—')}`")

                alts = c.get("alternativas_de_nome", []) or []
                if alts:
                    st.markdown("**Alternativas de nome:**")
                    for a in alts:
                        st.markdown(f"- {a}")

            with st.expander("📄 Resposta JSON completa"):
                st.json(decisao)

    elif not api_key:
        st.warning(
            "⚠️ Configure a Anthropic API Key na barra lateral para ativar a recomendação automática."
        )
    else:
        st.info("✓ Apenas matching ativo. Marque 'Usar Claude' para receber recomendação.")

elif buscar:
    st.warning("Digite uma solicitação antes de buscar.")
