"""
Agente de Cadastro de Insumos — Construção Civil
=================================================

Web app Streamlit que recebe uma solicitação de novo insumo e:
1. Verifica se já existe na base ATIVA (match exato fuzzy)
2. Busca top-5 similares semânticos em ambas as bases
3. Usa Claude para validar e sugerir reutilização ou criar nome novo
   no padrão da base MODELO

Deploy: Streamlit Cloud (grátis). Ver DEPLOY.md.
"""

import streamlit as st
import pandas as pd

from core.matcher import Matcher
from core.claude_client import consultar_claude


st.set_page_config(
    page_title="Agente de Insumos — Construção Civil",
    page_icon="🏗️",
    layout="wide",
)


# ============================================================
# CACHE DE RECURSOS PESADOS
# ============================================================

@st.cache_resource(show_spinner="Carregando bases e modelo de IA (1ª vez ~30s)...")
def carregar_matcher() -> Matcher:
    """
    Carrega bases CSV e instancia o Matcher (com SBERT + embeddings).
    Cacheado para a sessão inteira do servidor.
    """
    base_ativa = pd.read_csv("data/base_ativa.csv")
    base_modelo = pd.read_csv("data/base_modelo.csv")
    return Matcher(base_ativa, base_modelo)


# ============================================================
# UI
# ============================================================

st.title("🏗️ Agente de Cadastro de Insumos")
st.caption(
    "Verifica se a solicitação pode reutilizar um insumo existente ou "
    "gera um nome novo no padrão da base modelo."
)

# --- Sidebar: configuração ---
with st.sidebar:
    st.header("⚙️ Configuração")

    # API Key: prioriza secrets, depois input manual
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
    st.metric("Insumos na base ATIVA", len(matcher.base_ativa))
    st.metric("Insumos na base MODELO", len(matcher.base_modelo))
    st.metric("Subgrupos na base MODELO", matcher.base_modelo["subgrupo"].nunique())


# --- Input principal ---
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

    # --- Painel de query ---
    st.divider()
    st.subheader("📥 Solicitação analisada")
    c1, c2 = st.columns(2)
    c1.write(f"**Original:** `{resultado['query']}`")
    c2.write(f"**Normalizada (uso interno):** `{resultado['query_normalizada']}`")

    # --- Match exato ---
    st.subheader("🎯 Match exato na base ATIVA")
    if resultado["match_exato"]:
        m = resultado["match_exato"]
        st.success(
            f"**JÁ EXISTE** — código `{m.codigo}` | score {m.score:.1f}%\n\n"
            f"📦 **{m.descricao}**  \n"
            f"Grupo: {m.grupo}"
        )
    else:
        st.info("Nenhum match exato encontrado (≥ 95% de similaridade).")

    # --- Similares ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📋 Top 5 — Base ATIVA")
        df_a = pd.DataFrame(
            [
                {
                    "Código": c.codigo,
                    "Descrição": c.descricao,
                    "Grupo": c.grupo,
                    "Score": f"{c.score:.1f}",
                }
                for c in resultado["similares_ativa"]
            ]
        )
        st.dataframe(df_a, use_container_width=True, hide_index=True)

    with col_b:
        st.subheader("📋 Top 5 — Base MODELO")
        df_m = pd.DataFrame(
            [
                {
                    "Código": c.codigo,
                    "Descrição": c.descricao,
                    "Subgrupo": c.grupo,
                    "Un.": c.unidade,
                    "Score": f"{c.score:.1f}",
                }
                for c in resultado["similares_modelo"]
            ]
        )
        st.dataframe(df_m, use_container_width=True, hide_index=True)

    # --- Claude (decisão) ---
    if usar_claude and api_key:
        st.divider()
        st.subheader("🤖 Recomendação do Agente (Claude)")

        with st.spinner("Consultando Claude..."):
            decisao = consultar_claude(
                api_key=api_key,
                solicitacao=solicitacao,
                match_exato=resultado["match_exato"],
                similares_ativa=resultado["similares_ativa"],
                similares_modelo=resultado["similares_modelo"],
            )

        if "erro" in decisao:
            st.error(f"Erro: {decisao['erro']}")
            if decisao.get("resposta_bruta"):
                with st.expander("Resposta bruta"):
                    st.code(decisao["resposta_bruta"])
        else:
            acao = decisao.get("acao", "?")
            just = decisao.get("justificativa", "")

            if acao == "REUTILIZAR":
                r = decisao.get("reutilizar", {}) or {}
                st.success(f"✅ **REUTILIZAR**\n\n{just}")
                st.markdown(
                    f"**Use o insumo:** `{r.get('codigo')}` — {r.get('descricao')}"
                )

            elif acao == "REVISAR_HUMANO":
                st.warning(f"⚠️ **REVISAR MANUALMENTE**\n\n{just}")
                for r in decisao.get("revisar", []) or []:
                    st.markdown(
                        f"- **{r.get('codigo')}** — {r.get('descricao')}  \n"
                        f"  *Dúvida:* {r.get('motivo_duvida')}"
                    )

            elif acao == "CRIAR_NOVO":
                c = decisao.get("criar_novo", {}) or {}
                st.info(f"🆕 **CRIAR NOVO INSUMO**\n\n{just}")
                col_x, col_y, col_z = st.columns(3)
                col_x.metric("Nome sugerido", c.get("nome_sugerido", "—"))
                col_y.metric("Subgrupo", c.get("subgrupo_sugerido", "—"))
                col_z.metric("Unidade", c.get("unidade_sugerida", "—"))

                alts = c.get("alternativas_de_nome", []) or []
                if alts:
                    st.markdown("**Alternativas de nome:**")
                    for a in alts:
                        st.markdown(f"- {a}")

            with st.expander("📄 Resposta JSON completa"):
                st.json(decisao)

    elif usar_claude is False and api_key:
        st.info("✓ Apenas matching ativo. Marque 'Usar Claude' para receber recomendação.")
    else:
        st.warning("⚠️ Configure a Anthropic API Key na barra lateral para ativar a recomendação automática.")

elif buscar:
    st.warning("Digite uma solicitação antes de buscar.")
