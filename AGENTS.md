# AGENTS.md — APS Goianira

Plataforma Municipal de Inteligência da APS, integrada ao PostgreSQL do e-SUS APS.

## Stack

- **Backend:** FastAPI + psycopg2 + schedule
- **Frontend:** React + Vite + Tailwind + daisyUI + react-router-dom
- **ETL:** Python (agendado 04:00 com `schedule`)
- **Banco fonte:** e-SUS APS PostgreSQL (porta 5433)
- **Banco BI:** PostgreSQL auxiliar `bi_aps` (mesmo host/config)

## Comandos

```bash
# Backend — servidor de desenvolvimento
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ETL — execução única
cd backend && python etl_base.py

# Frontend
cd frontend
npm install
npm run dev          # dev server em :5173
npm run build        # produção → dist/
```

## Estrutura

```
backend/
  main.py            # FastAPI (22 rotas: estrangeiros, inconsistencias,
                     #   dashboard, C1–C7, B1–B6, M1–M2, unidades, equipes,
                     #   indigenas, health)
  etl_base.py        # ETL agendado 04:00, cria tabelas BI_APS
  sql/
    estrangeiros_completo.sql  # View + função valida_cns + flags
  requirements.txt
frontend/
  src/
    App.jsx                   # React Router com navegação (19 páginas)
    pages/
      Dashboard.jsx           # Dashboard municipal por UBS
      IndicadorC1.jsx  a IndicadorC7.jsx  # C1 a C7 com unidade+equipe+filtro
      IndicadorB1.jsx  a IndicadorB6.jsx  # B1 a B6 com unidade+equipe+filtro
      IndicadorM1.jsx  + IndicadorM2.jsx  # M1 e M2 com unidade+equipe+filtro
      Inconsistencias.jsx     # Nomes duplicados + RN/DE
      Estrangeiros.jsx        # Módulo estrangeiros
      Indigenas.jsx           # Módulo indígenas
      MoradorRua.jsx          # Módulo morador de rua
    components/
      ModuloEstrangeiros.jsx  # Cards gerenciais + tabela com busca
      BuscaAtiva.jsx          # Componente reutilizável de busca ativa (C1-2, C6-7, B1-3, B5-6)
  package.json       # Vite + React + Tailwind + daisyUI + recharts
```

## Rotas da API

| Rota | Descrição |
|---|---|
| `GET /api/unidades` | Lista de UBS |
| `GET /api/equipes` | Lista de equipes (com unidade) |
| `GET /api/indigenas` | Indígenas ativos |
| `GET /api/estrangeiros` | Estrangeiros ativos com flags |
| `GET /api/inconsistencias` | Nomes duplicados + iniciando com RN/DE |
| `GET /api/indicadores/municipio` | Dashboard municipal (média C1 por UBS) |
| `GET /api/indicadores/{c1..c7,b1..b6,m1,m2}?unidade=&inicio=&fim=` | Indicador detalhado por equipe |
| `GET /api/busca-ativa/{c1,c2,c6,c7,b1,b2,b3,b5,b6}?unidade=&equipe=&inicio=&fim=` | Busca Ativa — pacientes que precisam de atendimento |
| `GET /api/inconsistencias` | Nomes duplicados + iniciando com RN/DE |
| `GET /api/inconsistencias/gestantes` | Gestantes com DUM antiga |
| `GET /api/inconsistencias/morador-rua` | Pacientes em situação de rua |
| `GET /api/health` | Health check |

## Regras de Negócio (e-SUS APS Goianira)

- **Estrangeiros:** nacionalidade = 3, ficha ativa, sem saída de cadastro
- **C1 (Mais Acesso):** programada = ids tipo_atendimento (2,3,8), espontânea = id 4; CBOs médicos (225130,225142,225170) + enfermeiros (223505,223565); thresholds: Ótimo 50-70, Bom 30-50, Suficiente 10-30, Regular ≤10 ou >70
- **C2 (Desenv. Infantil):** 5 boas práticas (A-E) de 20pts cada (total 100pts); MIAI (A/B), MIAI procedimentos + visitas (C), visitas ACS/TACS (D), vacinação (E); thresholds: Ótimo >75, Bom >50, Suficiente >25, Regular ≤25
- **C3 (Gestação/Puerpério):** 11 boas práticas (A-K), A=10pts, B-K=9pts cada (total 100pts); gestações identificadas via `tb_fat_rel_op_gestante`; vinculação por equipe via `tb_fat_cidadao` (registro atual); CBOs médicos (2231,2251,2252,2253) + enfermeiros (2235), ACS/TACS (515105,322255), CD (2232), TSB (3224); procedimentos SIGTAP p/ PA (0301100039), peso (0101040083), altura (0101040075), testes 1tri/3tri; dTpa código 57; thresholds: Ótimo >75, Bom >50, Suficiente >25, Regular ≤25
- **C4 (Diabetes):** 6 boas práticas (A–F), 1pt cada (máx 6pts/pessoa); elegibilidade via `ds_filtro_cids` (E10|E11|E14) ou `ds_filtro_ciaps` (T89|T90) desde 2013; A=consulta 6m, B=PA 6m, C=peso+altura 12m, D=2 visitas ACS/TACS (≥30d) 12m, E=HbA1c 12m, F=pé diabético 12m; thresholds: Ótimo >75, Bom >50, Suficiente >25, Regular ≤25
- **C5 (Hipertensão):** 4 boas práticas (A–D), 25pts cada (máx 100pts/pessoa); elegibilidade via `ds_filtro_cids` (I10|I11|I12|I13|I15|O10|O11) ou `ds_filtro_ciaps` (K86|K87) desde 2013; A=consulta 6m, B=PA 6m, C=peso+altura 12m, D=2 visitas ACS/TACS (≥30d) 12m; thresholds: Ótimo >75, Bom >50, Suficiente >25, Regular ≤25
- **C6 (Pessoa Idosa):** 4 boas práticas (A–D), 25pts cada, total 100pts/pessoa. População ≥ 60 anos vinculada via cadastro (`tb_fat_cidadao.co_dim_equipe`). A = ≥1 consulta méd/enf 12m, B = ≥1 peso+altura simultâneo 12m, C = ≥2 visitas ACS/TACS (≥30d) 12m, D = ≥1 dose influenza (cód. 33/77) 12m. Base usa LEFT JOIN `tb_fat_cidadao → tb_dim_equipe` (não via atendimento). BA C6: idosos sem CBO_MED_ENF no período.
- **C7 (Prevenção Câncer):** 4 práticas com denominadores por faixa etária: A=20pt colo 25-64a 36m (cód. citopatológico), B=30pt HPV 9-14a (cód. 67/93), C=30pt saúde sexual/reprodutiva 14-69a 12m (CID/CIAP), D=20pt mama 50-69a 24m. Percentual = Σ(cobertura × peso). BA C7: mulheres ≥9a sem CBO_MED_ENF no período.
- **B1 (1ª Consulta Odontológica):** Numerador = pessoas com 1ª consulta odontológica programática (SIGTAP 0301010153, CBO 2232). Denominador = população vinculada à equipe (via `tb_fat_cidadao → tb_fat_cad_individual → tb_fat_cidadao_pec`). Thresholds: Ótimo >5%, Bom >3% e ≤5%, Suficiente >1% e ≤3%, Regular ≤1%. BA B1: pacientes cadastrados sem 1ª consulta no período.
- **B2 (Tratamento Concluído):** Numerador = pessoas com `st_conduta_tratamento_concluid = 1` em `tb_fat_atendimento_odonto`. Denominador = pessoas com 1ª consulta odontológica programática (mesmo filtro B1). Thresholds: Ótimo >75%, Bom >50% e ≤75%, Suficiente >25% e ≤50%, Regular ≤25%. BA B2: pacientes com 1ª consulta mas sem tratamento concluído no período.
- **B3 (Taxa de Exodontia):** Menor-melhor. CBOs CD (2232-08, 2232-93, 2232-72) + TSB (3224-05, 3224-25). Numerador = exodontias (SIGTAP 0414020138, 0414020146). Denominador = total procedimentos preventivos + curativos + exodontias (26 códigos da NM). Thresholds: Ótimo ≥3 e <10, Bom ≥10 e <12, Suficiente ≥12 e <14, Regular <3 ou ≥14. BA B3: pacientes com exodontias no período.
- **B4 (Escovação Supervisionada):** Numerador = `SUM(nu_participantes)` de atividades coletivas com prática 9 (escovação supervisionada, via `tb_atividade_coletiva` → `rl_ativ_col_pratica_saude` → `tb_fat_atividade_coletiva` via UUID). Denominador = crianças 6-12 anos vinculadas à UBS. CBOs CD + TSB + ASB. Sem BA individual (coletiva não tem registro individual de participantes). Thresholds: Ótimo >1%, Bom >0.5%, Suficiente >0.25%, Regular ≤0.25%.
- **B5 (Procedimentos Preventivos):** Maior-melhor. CBOs CD + TSB (CBO_CD_TSB). Numerador = procedimentos preventivos (7 códigos SIGTAP: 0101020058, 0101020066, 0101020074, 0101020082, 0101020104, 0101020120, 0307030040). Denominador = CD: 25 códigos (B5_DENOM = B3_CODES_ALL exceto exodontia decíduo), TSB: apenas preventivos. Thresholds: Ótimo ≥65 e ≤85, Bom ≥55 e <65, Suficiente ≥40 e <55, Regular <40 ou >85. BA B5: pacientes com procedimento odontológico mas nenhum preventivo no período.
- **B6 (TRA/ART):** Maior-melhor. CBOs CD (CBO_CD, não TSB). Numerador = TRA/ART (SIGTAP 0307010074). Denominador = procedimentos restauradores (0307010031, 0307010074, 0307010082, 0307010104, 0307010112, 0307010120). Thresholds: Ótimo >8, Bom >6 e ≤8, Suficiente >3 e ≤6, Regular ≤3. BA B6: pacientes com procedimentos restauradores mas sem TRA/ART no período.
- **Flags de estrangeiros:** atendimento_recente (12m), vinculo_equipe, cpf_presente, cns_valido
- **Inconsistências:** nomes duplicados (`GROUP BY no_cidadao HAVING COUNT(*) > 1`) + nomes iniciando com `RN ` ou `DE `; equipe e unidade incluídas via LEFT JOIN tb_fat_cidadao → tb_dim_equipe
- **Morador de Rua:** `st_morador_rua = 1` em `tb_fat_cad_individual`
- **CORS:** liberado para localhost:5173, :3000 e IP interno 192.168.0.229:8095
- **BI_APS tabelas:** fato_atendimento, dim_paciente, dim_equipe, dim_unidade, fato_estrangeiros, fato_indicadores, fato_boas_praticas, busca_ativa, inconsistencias, fato_vacinacao, fato_visita_domiciliar
- **eAP Tipo 76:** visitas ACS/TACS não pontuam nos indicadores C (exceto C1)
- **Vacinas:** sempre considerar MIV (e-SUS) + RIA (RNDS)

## Performance (30+ usuários simultâneos)

- Queries SQL devem ser otimizadas com índices apropriados, evitar subqueries aninhadas e usar CTEs + DISTINCT ON quando necessário
- Endpoints de listagem (estrangeiros, indígenas, inconsistencias) com mais de 10k registros devem usar paginação no backend quando possível
- Evitar loops Python em datasets grandes — delegar agregação ao PostgreSQL
- Frontend: evitar re-renders desnecessários (useMemo/useCallback em listas filtradas); busca textual deve ser case-insensitive no lado do cliente apenas para conjuntos pequenos (< 5k registros)
- Conexões com banco devem ser abertas e fechadas por request (sem pooling excessivo)
- Respostas da API devem incluir apenas campos necessários ao frontend, sem joins desnecessários

## Convenções importantes

- `.env` na raiz com credenciais do banco e-SUS (somente leitura)
- ETL não sobrecarrega o e-SUS — roda contra banco auxiliar BI_APS
- Validação CNS: função `valida_cns()` no PostgreSQL (dígito verificador)
- Frontend usa Vite proxy (`/api` → `localhost:8000`) em dev
- Dimension tables do e-SUS: `co_seq_dim_tipo_atendimento`, `co_seq_dim_cbo`, `co_seq_dim_tempo` (formato YYYYMMDD)
- Tabelas locais (não dimensionais): `tb_equipe` (PK `co_seq_equipe`), `tb_unidade_saude` (PK `co_seq_unidade_saude`)
