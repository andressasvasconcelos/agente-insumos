# 🚀 Deploy no Streamlit Community Cloud

Guia passo a passo. Custo: **R$ 0/mês** (Streamlit Cloud) + **API Claude por uso**.

## Pré-requisitos

- Conta GitHub (gratuita): https://github.com/signup
- Conta Anthropic com API key: https://console.anthropic.com
- Conta Streamlit Cloud (login com GitHub): https://share.streamlit.io

## Passo 1 — Subir o projeto no GitHub

1. Crie um repositório novo no GitHub:
   - Nome sugerido: `agente-insumos`
   - **Privado** (recomendado, mesmo sem dados sensíveis)

2. No terminal, dentro da pasta `agente-insumos/`:

   ```bash
   git init
   git add .
   git commit -m "Versão inicial do agente"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/agente-insumos.git
   git push -u origin main
   ```

3. **Confira que o `secrets.toml` real NÃO foi commitado** (o `.gitignore` cuida disso).
   Se aparecer no GitHub, gere uma nova API key e revogue a antiga imediatamente.

## Passo 2 — Obter a API Key da Anthropic

1. Acesse https://console.anthropic.com
2. Vá em **Settings → API Keys → Create Key**
3. Copie a chave (começa com `sk-ant-`). **Você só vê uma vez**.
4. Adicione créditos em **Billing** (mínimo US$ 5).

## Passo 3 — Deploy no Streamlit Cloud

1. Acesse https://share.streamlit.io e faça login com GitHub.
2. Clique **New app**.
3. Preencha:
   - **Repository**: `SEU_USUARIO/agente-insumos`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. Clique **Advanced settings** → **Secrets** e cole:

   ```toml
   ANTHROPIC_API_KEY = "sk-ant-sua-chave-aqui"
   ```

5. Clique **Deploy**.

A 1ª build leva ~5–10 min (instala dependências + baixa modelo SBERT).
Builds seguintes (após pushes) levam ~2 min.

## Passo 4 — Testar

Acesse a URL gerada (formato `https://SEU_USUARIO-agente-insumos-app-xxxx.streamlit.app`)
e teste com casos como:

| Caso | Resultado esperado |
|---|---|
| `Cimento Portland Pozolanico 320` | Match exato (já existe) |
| `Cimento CP-II 50kg` | Similares + Claude decide reutilizar ou criar |
| `Drone para vistoria de obra` | Criar novo (não existe na base) |

## Manutenção

### Atualizar as bases

1. Substitua os arquivos em `data/base_ativa.csv` e `data/base_modelo.csv`.
2. `git push` — Streamlit Cloud reimplanta sozinho.
3. O cache de embeddings é regenerado na 1ª execução (~30s).

### Atualizar abreviações do setor

Edite `core/normalizer.py` → dicionário `ABREVIACOES`. Faça `git push`.

### Monitorar custo da API Claude

Acompanhe em https://console.anthropic.com → **Usage**.
Configure **Spend limit** em Billing → **Usage limits** para evitar surpresas.

## Troubleshooting

**Erro: "ModuleNotFoundError: sentence_transformers"**
→ Verifique se `requirements.txt` está na raiz e tem a linha `sentence-transformers`.

**App lento na 1ª consulta**
→ Normal: SBERT está gerando embeddings das 6.500 linhas. Próximas são instantâneas.

**Claude retorna erro JSON**
→ Veja o expander "Resposta JSON completa" no app. Pode ser que o modelo
  encontrou ambiguidade — ajuste o `PROMPT_SYSTEM` em `core/claude_client.py`.

**API key vazou no GitHub**
→ Revogue imediatamente em console.anthropic.com → API Keys → Delete.
  Gere uma nova e atualize no Streamlit Secrets.

## Compartilhar o app com sua equipe

No Streamlit Cloud → **Settings → Sharing**:
- **Public**: qualquer um com o link acessa (cuidado: usa SUA API key).
- **Private (GitHub-based)**: só usuários do seu repositório acessam.

Para uso interno da empresa, use **Private**.
