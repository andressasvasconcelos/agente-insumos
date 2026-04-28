# 🏗️ Agente de Cadastro de Insumos — Construção Civil

Web app que recebe uma solicitação de novo insumo e decide:
- ✅ **Reutilizar** um insumo existente na base ATIVA
- ⚠️ **Revisar manualmente** quando há candidatos parecidos mas com diferença técnica
- 🆕 **Criar novo** com nome no padrão da base MODELO

## Arquitetura

```
[Solicitação do usuário]
        ↓
[Normalização]  → lowercase, remove acentos, expande abreviações (CP-II, PVC...)
        ↓
[Match fuzzy ≥ 95%]  → na base ATIVA → encontrou? Devolve "JÁ EXISTE"
        ↓ (se não)
[Embedding semântico SBERT]  → top 5 ATIVA + top 5 MODELO
        ↓
[Claude Sonnet 4]  → valida candidatos + gera nome novo se necessário
        ↓
[Decisão JSON]  → REUTILIZAR | REVISAR_HUMANO | CRIAR_NOVO
```

### Por que duas bases?
- **Base ATIVA** (`base_ativa.csv`): 4.365 insumos cadastrados hoje. Fonte para
  detectar duplicatas e propor reutilização.
- **Base MODELO** (`base_modelo.csv`): 2.157 insumos de referência com hierarquia
  granular (55 subgrupos, ex: `02.013 - Metais`). Fonte para padrão de
  nomenclatura ao criar novo.

### Por que híbrido SBERT + Claude?
- **SBERT** (offline, grátis, rápido): faz a busca dos top candidatos.
- **Claude** (API paga, ~R$ 0,01/consulta): valida semanticamente e gera nome
  novo seguindo o padrão da base modelo.
- A API só é chamada **uma vez** por consulta, com contexto rico já filtrado.

## Estrutura

```
agente-insumos/
├── app.py                    # Streamlit app
├── requirements.txt          # Dependências fixadas
├── .streamlit/
│   └── secrets.toml.example  # Template para API key
├── data/
│   ├── base_ativa.csv        # Insumos ativos (tratados)
│   └── base_modelo.csv       # Padrão de referência
├── core/
│   ├── normalizer.py         # Normalização + abreviações setor
│   ├── matcher.py            # Match exato + SBERT
│   └── claude_client.py      # Validação + geração via Claude
├── README.md                 # Este arquivo
└── DEPLOY.md                 # Guia passo a passo Streamlit Cloud
```

## Rodar localmente

```bash
# 1. Clonar/baixar este projeto
cd agente-insumos

# 2. Criar venv
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar API key
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite secrets.toml com sua chave real (console.anthropic.com)

# 5. Rodar
streamlit run app.py
```

A 1ª execução baixa o modelo SBERT (~470MB) e gera embeddings (~30s).
As próximas iniciam em ~5s graças ao cache do Streamlit.

## Deploy em produção

Ver `DEPLOY.md` para passo a passo no Streamlit Community Cloud (grátis).

## Custos

- **Streamlit Cloud**: grátis (1 app público).
- **Anthropic API**: ~R$ 0,01–0,03 por consulta (Claude Sonnet 4).
- **SBERT**: roda no servidor Streamlit, sem custo adicional.

Estimativa: 100 consultas/dia ≈ R$ 30–90/mês.

## Limitações conhecidas

1. **Base ativa tem inconsistências** (160 duplicatas, classificações erradas).
   O agente sinaliza candidatos mas a decisão final continua humana.
2. **Dicionário de abreviações é fixo** (`core/normalizer.py`). Adicione termos
   específicos da sua empresa conforme necessário.
3. **SBERT multilíngue tem limites em jargão muito técnico** — Claude compensa,
   mas vale calibrar os limiares (`FUZZY_EXATO_THRESHOLD = 95`) com casos reais.
4. **Sem persistência**: o app não grava decisões em banco. Para histórico,
   integrar com Google Sheets / Supabase.

## Próximos passos sugeridos

- [ ] Log de decisões em CSV/Sheets para auditoria
- [ ] Botão "Aplicar decisão" → exporta linha pronta para o ERP
- [ ] Modo batch (CSV de entrada → CSV de saída)
- [ ] Métricas de uso (quantos REUTILIZAR vs CRIAR_NOVO por mês)
- [ ] Treinar limiares com feedback humano
