# Déficit Calórico

App para acompanhar déficit calórico diário e total, substituindo a planilha. Hospedado na nuvem
(Streamlit Community Cloud) com os dados guardados num banco Postgres gratuito (Supabase), então
funciona de qualquer lugar, mesmo com o computador desligado.

## Persistência

Os dados ficam num banco Postgres no Supabase, em três tabelas simples (cada uma guarda os registros
como JSON numa coluna `jsonb`):

- `config`: perfil pessoal, Basal escolhido, kcal por kg de gordura, metas.
- `registros`: histórico diário (Consumido, Treino Bruto, Minutos de Treino), uma linha por data.
- `composicao`: medições esporádicas de peso, % de gordura e % de massa magra, uma linha por data.

O app (local ou hospedado) sempre lê e escreve nesse mesmo banco — não existe mais cópia local dos
dados. Rodar o app localmente também exige as credenciais do Supabase configuradas (veja abaixo).

## Configuração inicial (uma vez só)

### 1. Criar as tabelas no Supabase

No painel do seu projeto Supabase, abra o **SQL Editor** e rode:

```sql
create table if not exists config (
  id text primary key,
  data jsonb not null
);
create table if not exists registros (
  data_iso text primary key,
  data jsonb not null
);
create table if not exists composicao (
  data_iso text primary key,
  data jsonb not null
);
```

### 2. Configurar as credenciais

Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha com:

- `app_password`: uma senha à sua escolha, para proteger o acesso ao app.
- `[postgres]`: host, porta, nome do banco, usuário e senha — encontrados em
  *Project Settings → Database → Connection parameters* no painel do Supabase.

Esse arquivo **não vai para o Git** (está no `.gitignore`). Ao publicar no Streamlit Community Cloud,
cole o mesmo conteúdo na aba de **Secrets** das configurações do app por lá.

### 3. Instalar dependências

```
pip install -r requirements.txt
```

### 4. Migrar dados antigos (só se você já tinha usado a versão local)

```
python migrate_to_supabase.py
```

Lê os arquivos antigos em `data/*.json` (se existirem) e grava tudo no Supabase. Rode uma vez só.

## Como rodar localmente

```
streamlit run app.py
```

Abre em `http://localhost:8501`, já lendo/gravando direto no Supabase.

## Deploy no Streamlit Community Cloud

1. Suba o projeto para um repositório no GitHub (o `.gitignore` já impede que `secrets.toml` e a pasta
   `data/` antiga sejam enviados).
2. Em [share.streamlit.io](https://share.streamlit.io), crie um novo app apontando para esse repositório
   e para o arquivo `app.py`.
3. Nas configurações do app (⋮ → Settings → Secrets), cole o mesmo conteúdo do seu
   `.streamlit/secrets.toml` local.
4. Pronto — o link gerado funciona de qualquer lugar, protegido pela senha definida em `app_password`.
   Pode usar "Adicionar à tela de início" no navegador do celular para um atalho tipo app.

## Fluxo de uso

1. Aba **Perfil (TMB/TDEE)**: preencha seus dados, calcule TMB (Mifflin-St Jeor, Harris-Benedict, e Katch-McArdle se informar % de gordura) e TDEE por nível de atividade, e escolha/salve o valor Basal do sistema. Pode refazer isso quando quiser (ex.: após emagrecer) ou sobrescrever o Basal manualmente a qualquer momento.
2. Aba **Registro Diário**: informe Consumido, Treino Bruto e Minutos de Treino do dia.
3. Aba **Composição Corporal**: registre esporadicamente peso, % de gordura e % de massa magra.
4. Aba **Histórico**: veja todos os dias com as colunas calculadas, edite ou exclua um dia.
5. Aba **Resumo e Metas**: déficit total acumulado e % atingido de cada meta de perda de gordura.
6. Aba **Gráfico**: evolução do déficit diário/acumulado e da composição corporal ao longo do tempo.
7. Aba **Configurações**: ajuste kcal por kg de gordura (padrão 7700), a lista de metas em kg, e exporte seus dados em CSV/JSON.
