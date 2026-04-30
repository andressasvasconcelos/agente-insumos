"""
Agente de Cadastro de Insumos — All Wert Construtora
v2.3 — motivo usado na busca semântica (SBERT) + no Claude
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
# CACHE
# ============================================================

@st.cache_resource(show_spinner="Carregando bases e modelo de IA (1ª vez ~30s)...")
def carregar_matcher() -> Matcher:
    base_ativa  = pd.read_csv("data/base_ativa.csv",  dtype=str).fillna("")
    base_modelo = pd.read_csv("data/base_modelo.csv", dtype=str).fillna("")
    return Matcher(base_ativa, base_modelo)


@st.cache_data
def carregar_referencias():
    grupos = pd.read_csv("data/grupos_insumo.csv",      dtype=str).fillna("").to_dict("records")
    contas = pd.read_csv("data/contas_financeiras.csv", dtype=str).fillna("").to_dict("records")
    return grupos, contas


# ============================================================
# HELPERS — compatível com resultado dict OU dataclass
# ============================================================

def _get(obj, key, default=""):
    try:
        return obj[key] if isinstance(obj, dict) else getattr(obj, key, default)
    except Exception:
        return default


def _candidatos(obj, key):
    items = _get(obj, key, []) or []
    result = []
    for c in items:
        if isinstance(c, dict):
            result.append(c)
        else:
            result.append({
                "codigo":           getattr(c, "codigo",           ""),
                "descricao":        getattr(c, "descricao",        ""),
                "grupo":            getattr(c, "grupo",            ""),
                "unidade":          getattr(c, "unidade",          ""),
                "score":            getattr(c, "score",            0),
                "cod_conta":        getattr(c, "cod_conta",        ""),
                "conta_financeira": getattr(c, "conta_financeira", ""),
            })
    return result


def _match_exato_dict(obj):
    m = _get(obj, "match_exato", None)
    if m is None:
        return None
    if isinstance(m, dict):
        return m
    return {
        "codigo":           getattr(m, "codigo",           ""),
        "descricao":        getattr(m, "descricao",        ""),
        "grupo":            getattr(m, "grupo",            ""),
        "score":            getattr(m, "score",            0),
        "cod_conta":        getattr(m, "cod_conta",        ""),
        "conta_financeira": getattr(m, "conta_financeira", ""),
    }


# ============================================================
# SIDEBAR
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
            help="Crie em console.anthropic.com. Em produção configure via Streamlit Secrets.",
        )

    usar_claude = st.checkbox(
        "Usar Claude para validação e geração",
        value=bool(api_key),
        disabled=not api_key,
    )

    st.divider()
    st.subheader("📊 Bases carregadas")
    matcher = carregar_matcher()
    grupos, contas = carregar_referencias()

    st.metric("Insumos na base ATIVA",  len(matcher.base_ativa))
    st.metric("Insumos na base MODELO", len(matcher.base_modelo))
    st.metric("Grupos de insumo",       len(grupos))
    st.metric("Contas financeiras",     len(contas))


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

motivo = st.text_area(
    "Motivo da utilização — onde e como será usado (ajuda na busca e na sugestão de nome):",
    placeholder="ex: Polimento de piso de mármore na fase de acabamento do Bloco A / "
                "Manutenção da retroescavadeira CAT 416 / "
                "Instalação elétrica de quadro de distribuição",
    height=80,
)


# ============================================================
# EXECUÇÃO
# ============================================================

if buscar and solicitacao.strip():
    with st.spinner("Buscando candidatos..."):
        # motivo passado ao matcher — enriquece o embedding de busca
        resultado = matcher.buscar(solicitacao, motivo=motivo.strip())

    st.divider()
    st.subheader("📥 Solicitação analisada")
    c1, c2 = st.columns(2)
    c1.write(f"**Insumo solicitado:** `{_get(resultado, 'query')}`")
    c2.write(f"**Normalizada:** `{_get(resultado, 'query_normalizada')}`")
    if motivo.strip():
        # Mostra a query enriquecida que foi usada na busca semântica
        enriq = _get(resultado, "query_enriquecida", "")
        st.write(f"**Motivo informado:** {motivo.strip()}")
        if enriq and enriq != _get(resultado, "query_normalizada"):
            st.caption(f"🔍 Busca semântica realizada com: *\"{enriq}\"*")

    # Match exato
    st.subheader("🎯 Match exato na base ATIVA")
    m = _match_exato_dict(resultado)
    if m:
        st.success(
            f"**JÁ EXISTE** — código `{m['codigo']}` | score {float(m['score']):.1f}%\n\n"
            f"📦 **{m['descricao']}**  \n"
            f"Grupo: {m['grupo']}  |  Conta: `{m['cod_conta']}` — {m['conta_financeira']}"
        )
    else:
        st.info("Nenhum match exato encontrado (≥ 95% de similaridade).")

    # Similares
    col_a, col_b = st.columns(2)
    similares_ativa  = _candidatos(resultado, "similares_ativa")
    similares_modelo = _candidatos(resultado, "similares_modelo")

    with col_a:
        st.subheader("📋 Top 5 — Base ATIVA")
        df_a = pd.DataFrame([
            {
                "Código":    c["codigo"],
                "Descrição": c["descricao"],
                "Grupo":     c["grupo"],
                "Conta":     c["cod_conta"],
                "Score":     f"{float(c['score']):.1f}",
            }
            for c in similares_ativa
        ])
        st.dataframe(df_a, use_container_width=True, hide_index=True)

    with col_b:
        st.subheader("📋 Top 5 — Base MODELO")
        df_m = pd.DataFrame([
            {
                "Código":    c["codigo"],
                "Descrição": c["descricao"],
                "Subgrupo":  c["grupo"],
                "Un.":       c["unidade"],
                "Score":     f"{float(c['score']):.1f}",
            }
            for c in similares_modelo
        ])
        st.dataframe(df_m, use_container_width=True, hide_index=True)

    # Claude
    if usar_claude and api_key:
        st.divider()
        st.subheader("🤖 Recomendação do Agente (Claude)")

        with st.spinner("Consultando Claude..."):
            decisao = consultar_claude(
                api_key=api_key,
                solicitacao=solicitacao,
                motivo=motivo.strip(),
                match_exato=m,
                similares_ativa=similares_ativa,
                similares_modelo=similares_modelo,
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

            if acao == "REUTILIZAR":
                r = decisao.get("reutilizar", {}) or {}
                st.success(f"✅ **REUTILIZAR**\n\n{just}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Código",  r.get("codigo",    "—"))
                col2.metric("Insumo",  r.get("descricao", "—"))
                col3.metric("Grupo",   r.get("grupo",     "—"))
                if r.get("conta_financeira_codigo"):
                    st.info(
                        f"💰 Conta: `{r.get('conta_financeira_codigo')}` — "
                        f"{r.get('conta_financeira_descricao','')}"
                    )

            elif acao == "REVISAR_HUMANO":
                st.warning(f"⚠️ **REVISAR MANUALMENTE**\n\n{just}")
                for r in decisao.get("revisar", []) or []:
                    st.markdown(
                        f"- **{r.get('codigo')}** — {r.get('descricao')}  \n"
                        f"  *Dúvida:* {r.get('motivo_duvida')}"
                    )

            elif acao == "CRIAR_NOVO":
                c     = decisao.get("criar_novo", {}) or {}
                grupo = c.get("grupo_insumo",     {}) or {}
                conta = c.get("conta_financeira",  {}) or {}

                st.info(f"🆕 **CRIAR NOVO INSUMO**\n\n{just}")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("📝 Nome sugerido",   c.get("nome_sugerido",   "—"))
                col2.metric("🗂️ Grupo de Insumo", grupo.get("descricao",  "—"),
                            help=f"Ref: {grupo.get('ref','')}")
                col3.metric("🏗️ Tipo de Uso",     grupo.get("tipo",        "—"))
                col4.metric("📦 Unidade",          c.get("unidade_sugerida","—"))

                st.markdown(
                    f"💰 **Conta Financeira:** `{conta.get('codigo','—')}` — "
                    f"{conta.get('descricao','—')}"
                )

                alts = c.get("alternativas_de_nome", []) or []
                if alts:
                    st.markdown("**Alternativas de nome:**")
                    for a in alts:
                        st.markdown(f"- {a}")

            with st.expander("📄 Resposta JSON completa"):
                st.json(decisao)

    elif not api_key:
        st.warning("⚠️ Configure a Anthropic API Key para ativar a recomendação automática.")
    else:
        st.info("✓ Apenas matching ativo. Marque 'Usar Claude' para receber recomendação.")

elif buscar:
    st.warning("Digite uma solicitação antes de buscar.")
