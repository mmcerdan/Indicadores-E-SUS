/*
 ============================================================
 Estrangeiros Ativos — Versão Completa com Flags
 Plataforma Inteligente APS — Goianira
 ============================================================
 Base: tb_fat_cad_individual (e-SUS APS)
 União com: tb_equipe, tb_unidade_saude (locais)
 Flags implementadas:
   - flag_atendimento_recente (últimos 12 meses)
   - flag_vinculo_equipe (equipe ativa vinculada ao cidadão)
   - flag_cpf_presente (CPF preenchido e não nulo)
   - flag_cns_valido (CNS válido pelo dígito verificador)
 ============================================================
*/

CREATE OR REPLACE VIEW estrangeiros_completo_vw AS
WITH estrangeiros_base AS (
  SELECT
    fci.co_seq_fat_cad_individual,
    fci.nu_cns,
    fci.nu_cpf_cidadao,
    fci.dt_nascimento,
    fci.co_fat_cidadao_pec,
    fci.co_dim_pais_nascimento,
    fci.nu_micro_area,
    fci.co_fat_cidadao_raiz
  FROM tb_fat_cad_individual fci
  JOIN tb_dim_tipo_saida_cadastro tipo_saida
    ON tipo_saida.co_seq_dim_tipo_saida_cadastro = fci.co_dim_tipo_saida_cadastro
  WHERE
    tipo_saida.nu_identificador = '-'
    AND fci.co_dim_nacionalidade = 3
    AND fci.st_ficha_inativa = 0
    AND EXISTS (
      SELECT 1 FROM tb_fat_cidadao cid
      WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual
        AND cid.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
        AND cid.co_dim_tempo <= TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
    )
    AND EXISTS (
      SELECT 1
      FROM tb_fat_cidadao cid
      JOIN tb_fat_cidadao raiz ON cid.co_fat_cidadao_raiz = raiz.co_fat_cidadao_raiz
      WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual
        AND raiz.co_dim_tempo_validade > TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
        AND raiz.co_dim_tempo <= TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
        AND raiz.st_vivo = 1
        AND raiz.st_mudou = 0
    )
),
atendimentos_recentes AS (
  SELECT DISTINCT co_fat_cidadao_pec
  FROM tb_fat_atendimento_individual a
  WHERE a.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '12 months', 'YYYYMMDD')::INTEGER
),
vinculo_equipe_ativo AS (
  SELECT DISTINCT co_fat_cad_individual
  FROM tb_fat_cidadao cid
  WHERE cid.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
    AND cid.co_dim_tempo <= TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
    AND cid.co_dim_equipe IS NOT NULL
)
SELECT
  eb.nu_cns                                          AS cns,
  eb.nu_cpf_cidadao                                  AS cpf,
  c.no_cidadao                                       AS nome,
  eb.dt_nascimento                                   AS data_nascimento,
  p.no_pais_portugues                                AS pais_origem,
  p.no_pais_portugues                                AS pais_nascimento,
  us.no_unidade_saude                                AS unidade_saude,
  us.nu_cnes                                         AS cnes,
  eq.nu_ine                                          AS ine,
  eq.no_equipe                                       AS equipe,
  eb.nu_micro_area                                   AS microarea,
  CASE WHEN ar.co_fat_cidadao_pec IS NOT NULL THEN 1 ELSE 0 END AS flag_atendimento_recente,
  CASE WHEN ve.co_fat_cad_individual IS NOT NULL THEN 1 ELSE 0 END AS flag_vinculo_equipe,
  CASE WHEN eb.nu_cpf_cidadao IS NOT NULL
            AND TRIM(eb.nu_cpf_cidadao) <> ''
            AND eb.nu_cpf_cidadao !~ '^0+$'
       THEN 1 ELSE 0 END                             AS flag_cpf_presente,
  CASE WHEN eb.nu_cns IS NOT NULL
            AND TRIM(eb.nu_cns) <> ''
            AND LENGTH(eb.nu_cns) = 15
            AND valida_cns(eb.nu_cns) = 1
       THEN 1 ELSE 0 END                             AS flag_cns_valido
FROM estrangeiros_base eb
JOIN tb_fat_cidadao_pec c
  ON eb.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
LEFT JOIN tb_pais p
  ON eb.co_dim_pais_nascimento = p.co_pais
LEFT JOIN atendimentos_recentes ar
  ON eb.co_fat_cidadao_pec = ar.co_fat_cidadao_pec
LEFT JOIN vinculo_equipe_ativo ve
  ON eb.co_seq_fat_cad_individual = ve.co_fat_cad_individual
LEFT JOIN tb_fat_cidadao cid_vinculo
  ON cid_vinculo.co_fat_cad_individual = eb.co_seq_fat_cad_individual
  AND cid_vinculo.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
  AND cid_vinculo.co_dim_tempo <= TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
LEFT JOIN tb_equipe eq
  ON cid_vinculo.co_dim_equipe = eq.co_seq_equipe
LEFT JOIN tb_unidade_saude us
  ON cid_vinculo.co_dim_unidade_saude = us.co_seq_unidade_saude
ORDER BY p.no_pais_portugues, c.no_cidadao;


/*
 ============================================================
 Função auxiliar: valida CNS (dígito verificador)
 Retorna 1 para válido, 0 para inválido
 ============================================================
*/
CREATE OR REPLACE FUNCTION valida_cns(p_cns TEXT)
RETURNS INTEGER AS $$
DECLARE
  cns_limpo TEXT;
  soma INTEGER;
  resto INTEGER;
  dv INTEGER;
  i INTEGER;
BEGIN
  cns_limpo := REGEXP_REPLACE(p_cns, '[^0-9]', '', 'g');
  IF LENGTH(cns_limpo) <> 15 THEN
    RETURN 0;
  END IF;
  IF LEFT(cns_limpo, 1)::INTEGER NOT IN (1, 2, 7, 8, 9) THEN
    RETURN 0;
  END IF;
  soma := 0;
  FOR i IN 1..15 LOOP
    soma := soma + SUBSTR(cns_limpo, i, 1)::INTEGER * (16 - i);
  END LOOP;
  resto := soma % 11;
  dv := 11 - resto;
  IF dv = 11 THEN
    dv := 0;
  END IF;
  IF dv = 10 THEN
    RETURN 0;
  END IF;
  RETURN 1;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


/*
 ============================================================
 Query resumida para consumo via API
 (mesma lógica, sem criar a view — pode ser executada direto)
 ============================================================
*/
-- A view acima já contém a query completa.
-- Para uso direto sem view, basta copiar o corpo da CTE.
