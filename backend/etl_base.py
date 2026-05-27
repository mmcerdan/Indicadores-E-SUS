"""
etl_base.py — ETL de integração e-SUS APS → BI_APS
Plataforma Inteligente APS — Goianira
"""

import os
import sys
import logging
from datetime import datetime, date

import schedule
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("etl_base.log"),
    ],
)
log = logging.getLogger(__name__)

ESUS_DB = {
    "host": os.getenv("ESUS_DB_HOST", "192.168.0.229"),
    "port": int(os.getenv("ESUS_DB_PORT", 5433)),
    "dbname": os.getenv("ESUS_DB_NAME", "esus"),
    "user": os.getenv("ESUS_DB_USER", "postgres"),
    "password": os.getenv("ESUS_DB_PASSWORD", ""),
}

BI_DB = {
    "host": os.getenv("BI_DB_HOST", ESUS_DB["host"]),
    "port": int(os.getenv("BI_DB_PORT", ESUS_DB["port"])),
    "dbname": os.getenv("BI_DB_NAME", "bi_aps"),
    "user": os.getenv("BI_DB_USER", ESUS_DB["user"]),
    "password": os.getenv("BI_DB_PASSWORD", ESUS_DB["password"]),
}

DDL_TABLES = """
-- Dimensão: Paciente
CREATE TABLE IF NOT EXISTS dim_paciente (
    sk_paciente      SERIAL PRIMARY KEY,
    cns              VARCHAR(15) UNIQUE,
    cpf              VARCHAR(11),
    nome             VARCHAR(300),
    data_nascimento  DATE,
    sexo             CHAR(1),
    nome_mae         VARCHAR(300),
    nacionalidade    INTEGER,
    pais_nascimento  INTEGER,
    micro_area       VARCHAR(10),
    etnia            INTEGER,
    st_vivo          SMALLINT DEFAULT 1,
    dt_carga         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dimensão: Equipe
CREATE TABLE IF NOT EXISTS dim_equipe (
    sk_equipe    SERIAL PRIMARY KEY,
    nu_ine       VARCHAR(10) UNIQUE,
    no_equipe    VARCHAR(300),
    tp_equipe    VARCHAR(50),
    cnes         VARCHAR(7),
    no_unidade   VARCHAR(300),
    dt_carga     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dimensão: Unidade de Saúde
CREATE TABLE IF NOT EXISTS dim_unidade (
    sk_unidade  SERIAL PRIMARY KEY,
    cnes        VARCHAR(7) UNIQUE,
    no_unidade  VARCHAR(300),
    tp_unidade  VARCHAR(50),
    dt_carga    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dimensão: SIGTAP
CREATE TABLE IF NOT EXISTS dim_sigtap (
    sk_sigtap    SERIAL PRIMARY KEY,
    co_sigtap    VARCHAR(20) UNIQUE,
    no_procedimento VARCHAR(300),
    categoria    VARCHAR(50),
    dt_carga     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fato: Atendimento
CREATE TABLE IF NOT EXISTS fato_atendimento (
    sk_atendimento      SERIAL PRIMARY KEY,
    co_fat_cidadao_pec  BIGINT,
    cns_paciente        VARCHAR(15),
    cns_profissional    VARCHAR(15),
    nu_ine              VARCHAR(10),
    cnes_unidade        VARCHAR(7),
    tp_atendimento      VARCHAR(50),
    ds_tipo_demanda     VARCHAR(100),
    co_sigtap           VARCHAR(20),
    competencia         INTEGER,
    dt_atendimento      DATE,
    dt_carga            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fato: Indicadores por INE/competência
CREATE TABLE IF NOT EXISTS fato_indicadores (
    sk_indicador    SERIAL PRIMARY KEY,
    nu_ine          VARCHAR(10),
    competencia     INTEGER,
    cd_indicador    VARCHAR(10),
    numerador       NUMERIC(12,4),
    denominador     NUMERIC(12,4),
    vl_indicador    NUMERIC(10,4),
    classificacao   VARCHAR(20),
    dt_carga        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fato: Boas Práticas (por pessoa/indicador C)
CREATE TABLE IF NOT EXISTS fato_boas_praticas (
    sk_boas_praticas  SERIAL PRIMARY KEY,
    cns               VARCHAR(15),
    nu_ine            VARCHAR(10),
    competencia       INTEGER,
    cd_indicador      VARCHAR(10),
    pontuacao         NUMERIC(5,2),
    boas_praticas     JSONB,
    dt_carga          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fato: Estrangeiros
CREATE TABLE IF NOT EXISTS fato_estrangeiros (
    sk_estrangeiro       SERIAL PRIMARY KEY,
    cns                  VARCHAR(15),
    cpf                  VARCHAR(11),
    nome                 VARCHAR(300),
    data_nascimento      DATE,
    pais_origem          VARCHAR(200),
    pais_nascimento      VARCHAR(200),
    unidade_saude        VARCHAR(300),
    cnes                 VARCHAR(7),
    ine                  VARCHAR(10),
    equipe               VARCHAR(300),
    microarea            VARCHAR(10),
    flag_atendimento_recente SMALLINT DEFAULT 0,
    flag_vinculo_equipe  SMALLINT DEFAULT 0,
    flag_cpf_presente    SMALLINT DEFAULT 0,
    flag_cns_valido      SMALLINT DEFAULT 0,
    dt_carga             DATE DEFAULT CURRENT_DATE
);

-- Inconsistências
CREATE TABLE IF NOT EXISTS inconsistencias (
    sk_inconsistencia SERIAL PRIMARY KEY,
    cns               VARCHAR(15),
    cpf               VARCHAR(11),
    tp_inconsistencia VARCHAR(100),
    descricao         TEXT,
    dt_deteccao       DATE DEFAULT CURRENT_DATE
);

-- Busca Ativa
CREATE TABLE IF NOT EXISTS busca_ativa (
    sk_busca_ativa  SERIAL PRIMARY KEY,
    cns             VARCHAR(15),
    cpf             VARCHAR(11),
    nome            VARCHAR(300),
    condicao        VARCHAR(100),
    nu_ine          VARCHAR(10),
    micro_area      VARCHAR(10),
    telefone        VARCHAR(20),
    acs_responsavel VARCHAR(300),
    prioridade      SMALLINT DEFAULT 0,
    dt_geracao      DATE DEFAULT CURRENT_DATE
);

-- Vacinação
CREATE TABLE IF NOT EXISTS fato_vacinacao (
    sk_vacinacao   SERIAL PRIMARY KEY,
    cns            VARCHAR(15),
    co_sigtap      VARCHAR(20),
    ds_vacina      VARCHAR(200),
    dose           VARCHAR(50),
    dt_aplicacao   DATE,
    fonte          VARCHAR(10),
    dt_carga       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Visita Domiciliar
CREATE TABLE IF NOT EXISTS fato_visita_domiciliar (
    sk_visita     SERIAL PRIMARY KEY,
    cns           VARCHAR(15),
    cns_acs       VARCHAR(15),
    nu_ine        VARCHAR(10),
    dt_visita     DATE,
    tp_visita     VARCHAR(50),
    dt_carga      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SQL_ESTRANGEIROS_ETL = """
INSERT INTO fato_estrangeiros (
    cns, cpf, nome, data_nascimento, pais_origem, pais_nascimento,
    unidade_saude, cnes, ine, equipe, microarea,
    flag_atendimento_recente, flag_vinculo_equipe,
    flag_cpf_presente, flag_cns_valido, dt_carga
)
SELECT
    e.cns,
    e.cpf,
    e.nome,
    e.data_nascimento,
    e.pais_origem,
    e.pais_nascimento,
    e.unidade_saude,
    e.cnes,
    e.ine,
    e.equipe,
    e.microarea,
    e.flag_atendimento_recente,
    e.flag_vinculo_equipe,
    e.flag_cpf_presente,
    e.flag_cns_valido,
    CURRENT_DATE
FROM estrangeiros_completo_vw e
ON CONFLICT DO NOTHING;
"""


def get_conn_esus():
    return psycopg2.connect(**ESUS_DB)


def get_conn_bi():
    return psycopg2.connect(**BI_DB)


def criar_estrutura_bi():
    log.info("Criando/verificando estrutura do banco BI_APS...")
    conn = get_conn_bi()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL_TABLES)
        conn.commit()
        log.info("Estrutura do BI_APS criada/verificada com sucesso.")
    except Exception as e:
        conn.rollback()
        log.error("Erro ao criar estrutura BI_APS: %s", e)
        raise
    finally:
        conn.close()


def carregar_estrangeiros():
    log.info("Iniciando carga de estrangeiros...")
    try:
        conn_bi = get_conn_bi()
        with conn_bi.cursor() as cur:
            cur.execute("TRUNCATE TABLE fato_estrangeiros;")
            cur.execute(SQL_ESTRANGEIROS_ETL)
        conn_bi.commit()
        conn_bi.close()
        log.info("Carga de estrangeiros concluída.")
    except Exception as e:
        log.error("Erro na carga de estrangeiros: %s", e)


def executar_etl_completo():
    log.info("=" * 60)
    log.info("INÍCIO DA ROTINA ETL — %s", datetime.now().isoformat())
    log.info("=" * 60)
    try:
        criar_estrutura_bi()
        carregar_estrangeiros()
    except Exception as e:
        log.error("ETL interrompido por erro: %s", e)
    log.info("FIM DA ROTINA ETL — %s", datetime.now().isoformat())
    log.info("=" * 60)


if __name__ == "__main__":
    executar_etl_completo()
    log.info("Agendando ETL para 04:00 todos os dias...")
    schedule.every().day.at("04:00").do(executar_etl_completo)
    log.info("Agendador ativo. Aguardando horário programado...")
    while True:
        schedule.run_pending()
        schedule.idle_seconds()
