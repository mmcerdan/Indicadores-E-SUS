"""
main.py — FastAPI Backend
Plataforma Inteligente APS — Goianira
"""

import os
import math
import logging
import threading
from datetime import datetime, date, timedelta
from collections import defaultdict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="APS Goianira — API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://192.168.0.229:8095",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": os.getenv("ESUS_DB_HOST", "192.168.0.229"),
    "port": int(os.getenv("ESUS_DB_PORT", 5433)),
    "dbname": os.getenv("ESUS_DB_NAME", "esus"),
    "user": os.getenv("ESUS_DB_USER", "postgres"),
    "password": os.getenv("ESUS_DB_PASSWORD", ""),
}

# ---- Cache simples (5 min TTL) ----
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = timedelta(minutes=5)

def cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and datetime.now() - entry["ts"] < CACHE_TTL:
            return entry["data"]
        return None

def cache_set(key, data):
    with _cache_lock:
        _cache[key] = {"data": data, "ts": datetime.now()}

def cache_key(*args, **kwargs):
    return str(args) + str(sorted(kwargs.items()))


def get_db():
    return psycopg2.connect(**DB_CONFIG)

def fmt_row(r):
    for k, v in r.items():
        if isinstance(v, (datetime, date)):
            r[k] = v.isoformat()
    return r

def validar_periodo(inicio, fim):
    hoje = date.today()
    if inicio and fim:
        try:
            d_inicio = datetime.strptime(inicio, "%Y-%m-%d").date()
            d_fim = datetime.strptime(fim, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Formato de data inválido. Use YYYY-MM-DD.")
        dias = (d_fim - d_inicio).days
        if dias < 6:
            raise HTTPException(400, "Período mínimo é de 7 dias.")
        if dias > 731:
            raise HTTPException(400, "Período máximo é de 2 anos.")
        return d_inicio, d_fim
    if not inicio and not fim:
        hoje = date.today()
        d_fim = hoje.replace(day=1) - timedelta(days=1)
        d_inicio = d_fim.replace(day=1)
        return d_inicio, d_fim
    raise HTTPException(400, "Informe inicio e fim juntos.")

def periodo_sql(inicio, fim):
    d_inicio, d_fim = validar_periodo(inicio, fim)
    return int(d_inicio.strftime("%Y%m%d")), int(d_fim.strftime("%Y%m%d"))

# ---- Constantes ----
CBO_MED_ENF = (2823, 2818, 3603, 2820, 3612)
CBO_CD = (3295, 2827, 3656)
CBO_TSB = (3566, 3579)
CBO_CD_TSB = CBO_CD + CBO_TSB  # B3, B5 uses CD + TSB
CBO_ASB = (2953, 2834)
CBO_CD_TSB_ASB = CBO_CD + CBO_TSB + CBO_ASB  # B4 uses CD + TSB + ASB
CBO_EMULTI = (2816, 2833, 2817, 2823, 3665, 3279, 3610, 3600,
              3680, 3735, 3562, 3582, 3563, 3460, 2818, 2829, 2825)
TIPO_PROG = (2, 3, 8)
# B3 – Exodontia (NM): códigos SIGTAP exatos do numerador e denominador
B3_CODES_EXO = ('0414020138', '0414020146')
B3_CODES_ALL = B3_CODES_EXO + (
    '0101020058','0101020066','0101020074','0101020082','0101020090','0101020120',
    '0307010015','0307010031','0307010066','0307010074','0307010082','0307010104','0307010112','0307010120',
    '0307020010','0307020029','0307020070',
    '0307030024','0307030040','0307030059','0307030067','0307030075','0307030083',
    '0307050017',
)
# B5 – Preventivos: CD + TSB (denominador = preventivos + curativos + exodontias permanentes)
B5_PREVENTIVE = ('0101020058','0101020066','0101020074','0101020082','0101020104','0101020120','0307030040')
B5_DENOM = (
    '0101020058','0101020066','0101020074','0101020082','0101020090','0101020104','0101020120',
    '0414020138',
    '0307010015','0307010031','0307010066','0307010074','0307010082','0307010104','0307010112','0307010120',
    '0307020010','0307020029','0307020070',
    '0307030024','0307030040','0307030059','0307030067','0307030075','0307030083',
    '0307050017',
)
# B6 – TRA/ART: CD apenas (denominador = procedimentos restauradores)
B6_TRA_ART_STR = "('0307010074')"
B6_DENOM = ('0307010031','0307010074','0307010082','0307010104','0307010112','0307010120')
# Excluídos: Caps (180) e Centro Municipal de Diagnosticos (177)
DIM_UNIDADES = (163, 164, 165, 166, 167, 168, 169, 170, 171, 172,
                173, 174, 175, 176, 178, 179, 188)

SQL_INDIGENAS = """
WITH base AS (
  SELECT fci.co_seq_fat_cad_individual, fci.nu_cns, fci.nu_cpf_cidadao,
    fci.dt_nascimento, fci.co_fat_cidadao_pec, fci.co_dim_etnia, fci.co_dim_raca_cor, fci.nu_micro_area
  FROM tb_fat_cad_individual fci
  JOIN tb_dim_tipo_saida_cadastro tsc ON tsc.co_seq_dim_tipo_saida_cadastro = fci.co_dim_tipo_saida_cadastro
  WHERE tsc.nu_identificador = '-' AND fci.co_dim_raca_cor = 5 AND fci.st_ficha_inativa = 0
    AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND cid.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND cid.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER)
    AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid JOIN tb_fat_cidadao raiz ON cid.co_fat_cidadao_raiz = raiz.co_fat_cidadao_raiz WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND raiz.co_dim_tempo_validade > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND raiz.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND raiz.st_vivo=1 AND raiz.st_mudou=0)
)
SELECT eb.nu_cns AS cns, COALESCE(eb.nu_cpf_cidadao,'') AS cpf, c.no_cidadao AS nome,
  COALESCE(eb.dt_nascimento::TEXT,'') AS data_nascimento,
  COALESCE(et.no_etnia,'') AS etnia,
  COALESCE(du.no_unidade_saude,'') AS unidade_saude, COALESCE(du.nu_cnes,'') AS cnes,
  COALESCE(eb.nu_micro_area,'') AS microarea,
  CASE WHEN ar.co_fat_cidadao_pec IS NOT NULL THEN 1 ELSE 0 END AS flag_atendimento_recente,
  CASE WHEN cv.co_seq_fat_cidadao IS NOT NULL THEN 1 ELSE 0 END AS flag_vinculo_unidade,
  CASE WHEN eb.nu_cpf_cidadao IS NOT NULL AND TRIM(eb.nu_cpf_cidadao)<>'' AND eb.nu_cpf_cidadao!~'^0+$' THEN 1 ELSE 0 END AS flag_cpf_presente
FROM base eb
JOIN tb_fat_cidadao_pec c ON eb.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
LEFT JOIN tb_dim_etnia et ON eb.co_dim_etnia = et.co_seq_dim_etnia
LEFT JOIN (SELECT DISTINCT co_fat_cidadao_pec FROM tb_fat_atendimento_individual WHERE co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '12 months','YYYYMMDD')::INTEGER) ar ON eb.co_fat_cidadao_pec = ar.co_fat_cidadao_pec
LEFT JOIN tb_fat_cidadao cv ON cv.co_fat_cad_individual = eb.co_seq_fat_cad_individual AND cv.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND cv.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
LEFT JOIN tb_dim_unidade_saude du ON cv.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
ORDER BY c.no_cidadao;
"""

SQL_ESTRANGEIROS = """
WITH base AS (
  SELECT fci.co_seq_fat_cad_individual, fci.nu_cns, fci.nu_cpf_cidadao,
    fci.dt_nascimento, fci.co_fat_cidadao_pec, fci.co_dim_pais_nascimento, fci.nu_micro_area
  FROM tb_fat_cad_individual fci
  JOIN tb_dim_tipo_saida_cadastro tsc ON tsc.co_seq_dim_tipo_saida_cadastro = fci.co_dim_tipo_saida_cadastro
  WHERE tsc.nu_identificador = '-' AND fci.co_dim_nacionalidade = 3 AND fci.st_ficha_inativa = 0
    AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND cid.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND cid.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER)
    AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid JOIN tb_fat_cidadao raiz ON cid.co_fat_cidadao_raiz = raiz.co_fat_cidadao_raiz WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND raiz.co_dim_tempo_validade > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND raiz.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND raiz.st_vivo=1 AND raiz.st_mudou=0)
)
SELECT eb.nu_cns AS cns, COALESCE(eb.nu_cpf_cidadao,'') AS cpf, c.no_cidadao AS nome,
  COALESCE(eb.dt_nascimento::TEXT,'') AS data_nascimento, COALESCE(p.no_pais_portugues,'') AS pais_origem,
  COALESCE(du.no_unidade_saude,'') AS unidade_saude, COALESCE(du.nu_cnes,'') AS cnes,
  COALESCE(eb.nu_micro_area,'') AS microarea,
  CASE WHEN ar.co_fat_cidadao_pec IS NOT NULL THEN 1 ELSE 0 END AS flag_atendimento_recente,
  CASE WHEN cv.co_seq_fat_cidadao IS NOT NULL THEN 1 ELSE 0 END AS flag_vinculo_unidade,
  CASE WHEN eb.nu_cpf_cidadao IS NOT NULL AND TRIM(eb.nu_cpf_cidadao)<>'' AND eb.nu_cpf_cidadao!~'^0+$' THEN 1 ELSE 0 END AS flag_cpf_presente,
  1 AS flag_cns_valido
FROM base eb
JOIN tb_fat_cidadao_pec c ON eb.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
LEFT JOIN tb_pais p ON eb.co_dim_pais_nascimento = p.co_pais
LEFT JOIN (SELECT DISTINCT co_fat_cidadao_pec FROM tb_fat_atendimento_individual WHERE co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '12 months','YYYYMMDD')::INTEGER) ar ON eb.co_fat_cidadao_pec = ar.co_fat_cidadao_pec
LEFT JOIN tb_fat_cidadao cv ON cv.co_fat_cad_individual = eb.co_seq_fat_cad_individual AND cv.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND cv.co_dim_tempo <= TO_CHAR(current_DATE,'YYYYMMDD')::INTEGER
LEFT JOIN tb_dim_unidade_saude du ON cv.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
ORDER BY p.no_pais_portugues, c.no_cidadao;
"""

SQL_INCONSISTENCIAS = """
WITH dados AS (
  SELECT DISTINCT ON (p.co_seq_fat_cidadao_pec)
    p.co_seq_fat_cidadao_pec, p.no_cidadao, p.nu_cns, p.nu_cpf_cidadao,
    ci.dt_nascimento,
    te.no_equipe, du.no_unidade_saude
  FROM tb_fat_cidadao_pec p
  LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec
  LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
    AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
  LEFT JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
  LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
  WHERE p.st_faleceu = 0 AND (p.st_deletar IS NULL OR p.st_deletar = 0)
  ORDER BY p.co_seq_fat_cidadao_pec, ci.co_seq_fat_cad_individual DESC NULLS LAST
)
SELECT * FROM (
  SELECT 'duplicados' AS tipo, d.no_cidadao AS nome,
    COALESCE(d.dt_nascimento::TEXT,'') AS data_nascimento,
    COUNT(*)::INT AS quantidade,
    ARRAY_AGG(d.co_seq_fat_cidadao_pec::TEXT ORDER BY d.co_seq_fat_cidadao_pec) AS ids,
    ARRAY_AGG(COALESCE(d.nu_cns,'') ORDER BY d.co_seq_fat_cidadao_pec) AS cns_list,
    ARRAY_AGG(COALESCE(d.nu_cpf_cidadao,'') ORDER BY d.co_seq_fat_cidadao_pec) AS cpf_list,
    ARRAY_AGG(COALESCE(d.no_equipe,'') ORDER BY d.co_seq_fat_cidadao_pec) AS equipe_list,
    ARRAY_AGG(COALESCE(d.no_unidade_saude,'') ORDER BY d.co_seq_fat_cidadao_pec) AS unidade_list
  FROM dados d
  WHERE d.dt_nascimento IS NOT NULL
  GROUP BY d.no_cidadao, d.dt_nascimento
  HAVING COUNT(*) > 1
  UNION ALL
  SELECT 'rn_de' AS tipo, d.no_cidadao AS nome,
    COALESCE(d.dt_nascimento::TEXT,'') AS data_nascimento,
    1 AS quantidade,
    ARRAY[d.co_seq_fat_cidadao_pec::TEXT] AS ids,
    ARRAY[COALESCE(d.nu_cns,'')] AS cns_list,
    ARRAY[COALESCE(d.nu_cpf_cidadao,'')] AS cpf_list,
    ARRAY[COALESCE(d.no_equipe,'')] AS equipe_list,
    ARRAY[COALESCE(d.no_unidade_saude,'')] AS unidade_list
  FROM dados d
  WHERE d.no_cidadao ~* '^RN[[:space:]]'
) sub ORDER BY sub.tipo, sub.nome;
"""

# ---- Routes ----

@app.get("/api/unidades")
def get_unidades():
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT co_seq_dim_unidade_saude AS id, no_unidade_saude AS nome, nu_cnes AS cnes
                FROM tb_dim_unidade_saude
                WHERE co_seq_dim_unidade_saude IN {DIM_UNIDADES}
                ORDER BY no_unidade_saude
            """)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar unidades: %s", e)
        raise HTTPException(500, "Erro ao consultar unidades")
    return rows


@app.get("/api/equipes")
def get_equipes():
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT DISTINCT te.co_seq_dim_equipe AS id, te.no_equipe AS nome,
                  te.nu_ine AS ine, du.no_unidade_saude AS unidade
                FROM tb_fat_atendimento_individual a
                JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
                JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
                WHERE a.co_dim_unidade_saude_1 IN {DIM_UNIDADES}
                  AND te.nu_ine IS NOT NULL AND te.nu_ine != '-'
                ORDER BY du.no_unidade_saude, te.no_equipe
            """)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar equipes: %s", e)
        raise HTTPException(500, "Erro ao consultar equipes")
    return rows


@app.get("/api/indigenas")
def get_indigenas():
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_INDIGENAS)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar indígenas: %s", e)
        raise HTTPException(500, "Erro ao consultar indígenas")
    return {
        "total": len(rows),
        "totais": {
            "sem_cpf": sum(1 for r in rows if not r.get("flag_cpf_presente")),
            "sem_vinculo": sum(1 for r in rows if not r.get("flag_vinculo_unidade")),
            "sem_atendimento": sum(1 for r in rows if not r.get("flag_atendimento_recente")),
        },
        "dados": rows,
    }


@app.get("/api/estrangeiros")
def get_estrangeiros():
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_ESTRANGEIROS)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar estrangeiros: %s", e)
        raise HTTPException(500, "Erro ao consultar banco e-SUS")
    return {
        "total": len(rows),
        "totais": {
            "sem_cpf": sum(1 for r in rows if not r.get("flag_cpf_presente")),
            "sem_cns": sum(1 for r in rows if not r.get("flag_cns_valido")),
            "sem_vinculo_unidade": sum(1 for r in rows if not r.get("flag_vinculo_unidade")),
            "sem_atendimento_recente": sum(1 for r in rows if not r.get("flag_atendimento_recente")),
        },
        "dados": rows,
    }


@app.get("/api/inconsistencias")
def get_inconsistencias():
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_INCONSISTENCIAS)
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar inconsistências: %s", e)
        raise HTTPException(500, "Erro ao consultar inconsistências")
    duplicados = [fmt_row(r) for r in rows if r.get("tipo") == "duplicados"]
    rn_de = [fmt_row(r) for r in rows if r.get("tipo") == "rn_de"]
    return {"total": len(rows), "duplicados": duplicados, "rn_de": rn_de}


SQL_GESTANTES_DUM = """
WITH ultima_dum AS (
  SELECT DISTINCT ON (a.co_fat_cidadao_pec)
    a.co_fat_cidadao_pec,
    td.co_seq_dim_tempo AS dum,
    td.nu_ano || '-' || LPAD(td.nu_mes::TEXT,2,'0') || '-' || LPAD(td.nu_dia::TEXT,2,'0') AS dum_formatado,
    CEIL((CURRENT_DATE - TO_DATE(td.co_seq_dim_tempo::TEXT,'YYYYMMDD')) / 30.44) AS meses_desde_dum
  FROM tb_fat_atendimento_individual a
  JOIN tb_dim_tempo td ON a.co_dim_tempo_dum = td.co_seq_dim_tempo
  WHERE a.co_dim_tempo_dum IS NOT NULL AND a.co_dim_tempo_dum > 0
    AND a.co_dim_tempo_dum != 30001231
    AND a.co_dim_tempo_dum <= TO_CHAR(CURRENT_DATE - INTERVAL '11 months','YYYYMMDD')::INTEGER
  ORDER BY a.co_fat_cidadao_pec, a.co_dim_tempo_dum DESC
)
SELECT DISTINCT ON (u.co_fat_cidadao_pec)
  u.*, c.no_cidadao AS nome,
  COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
  du.no_unidade_saude AS unidade_saude, te.no_equipe
FROM ultima_dum u
JOIN tb_fat_cidadao_pec c ON u.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec AND (c.st_deletar IS NULL OR c.st_deletar = 0) AND c.st_faleceu = 0
LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
  AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
  AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
LEFT JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
ORDER BY u.co_fat_cidadao_pec, u.meses_desde_dum DESC;
"""


@app.get("/api/inconsistencias/gestantes")
def get_inconsistencias_gestantes():
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_GESTANTES_DUM)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar gestantes DUM: %s", e)
        raise HTTPException(500, "Erro ao consultar gestantes com DUM antiga")
    return {"total": len(rows), "gestantes": rows}


SQL_MORADOR_RUA = """
SELECT DISTINCT ON (c.co_seq_fat_cidadao_pec)
  c.co_seq_fat_cidadao_pec AS paciente_id, c.no_cidadao AS nome,
  COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
  COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
  du.no_unidade_saude AS unidade_saude, te.no_equipe
FROM tb_fat_cidadao_pec c
JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
  AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
  AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
LEFT JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
WHERE ci.st_morador_rua = 1
  AND (c.st_deletar IS NULL OR c.st_deletar = 0)
  AND c.st_faleceu = 0
ORDER BY c.co_seq_fat_cidadao_pec;
"""


@app.get("/api/inconsistencias/morador-rua")
def get_morador_rua():
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_MORADOR_RUA)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar moradores de rua: %s", e)
        raise HTTPException(500, "Erro ao consultar moradores de rua")
    return {"total": len(rows), "pacientes": rows}


SQL_DEFICIENCIA = """
SELECT DISTINCT ON (c.co_seq_fat_cidadao_pec)
  c.no_cidadao AS nome,
  COALESCE(c.nu_cns, '') AS cns,
  COALESCE(c.nu_cpf_cidadao, '') AS cpf,
  COALESCE(ci.dt_nascimento::TEXT, '') AS data_nascimento,
  COALESCE(du.no_unidade_saude, '') AS unidade_saude,
  COALESCE(te.no_equipe, '') AS equipe,
  ci.st_defi_fisica,
  ci.st_defi_intelectual_cognitiva,
  ci.st_defi_tea,
  ci.st_defi_auditiva,
  ci.st_defi_visual,
  ci.st_defi_outra
FROM tb_fat_cidadao_pec c
JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
JOIN tb_dim_tipo_saida_cadastro tsc ON tsc.co_seq_dim_tipo_saida_cadastro = ci.co_dim_tipo_saida_cadastro
LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
  AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
  AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
LEFT JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
WHERE tsc.nu_identificador = '-'
  AND ci.st_ficha_inativa = 0
  AND (c.st_deletar IS NULL OR c.st_deletar = 0)
  AND c.st_faleceu = 0
  AND {condicao}
ORDER BY c.co_seq_fat_cidadao_pec;
"""


def get_deficiencia(tipo):
    cond_map = {
        "fisica": "ci.st_defi_fisica = 1",
        "mental": "ci.st_defi_intelectual_cognitiva = 1",
    }
    cond = cond_map.get(tipo)
    if not cond:
        raise HTTPException(400, "Tipo inválido. Use 'fisica' ou 'mental'.")
    sql = SQL_DEFICIENCIA.format(condicao=cond)
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar deficiencia %s: %s", tipo, e)
        raise HTTPException(500, "Erro ao consultar deficientes")
    rotulos = {
        "st_defi_fisica": "Física",
        "st_defi_intelectual_cognitiva": "Intelectual/Cognitiva",
        "st_defi_tea": "TEA",
        "st_defi_auditiva": "Auditiva",
        "st_defi_visual": "Visual",
        "st_defi_outra": "Outra",
    }
    for r in rows:
        tipos = [rotulos[k] for k, v in r.items() if k.startswith("st_defi_") and v == 1]
        r["tipos_deficiencia"] = tipos
    return {"total": len(rows), "pacientes": rows}


@app.get("/api/deficiencia/fisica")
def get_deficiencia_fisica():
    return get_deficiencia("fisica")


@app.get("/api/deficiencia/mental")
def get_deficiencia_mental():
    return get_deficiencia("mental")


BOLSA_PACIENTES_SQL = """
WITH cpfs AS (
    SELECT DISTINCT bf.nu_documento AS doc, bf.no_cidadao AS nome_bolsa
    FROM tb_cidadao_bolsa_familia bf
    WHERE bf.ds_vigencia = (SELECT MAX(ds_vigencia) FROM tb_cidadao_bolsa_familia)
      AND bf.tp_documento = 'CPF'
),
pacientes AS (
    SELECT p.co_seq_fat_cidadao_pec,
        MIN(c.nome_bolsa) AS nome_bolsa,
        MIN(p.no_cidadao) AS nome_esus,
        MIN(p.nu_cpf_cidadao) AS cpf,
        MIN(p.nu_cns) AS cns,
        MIN(cad.dt_nascimento) AS dt_nascimento
    FROM cpfs c
    JOIN tb_fat_cidadao_pec p ON p.nu_cpf_cidadao = c.doc
        AND p.st_faleceu = 0 AND (p.st_deletar IS NULL OR p.st_deletar = 0)
    LEFT JOIN tb_fat_cad_individual cad ON cad.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec
    GROUP BY p.co_seq_fat_cidadao_pec
)
SELECT
    p.nome_bolsa, p.nome_esus,
    COALESCE(p.cpf,'') AS cpf, COALESCE(p.cns,'') AS cns,
    p.dt_nascimento,
    v.no_unidade_saude, v.nu_cnes, v.no_equipe,
    CASE WHEN c1.co_fat_cidadao_pec IS NULL THEN 1 ELSE 0 END AS pendencia_consulta,
    CASE WHEN p.dt_nascimento IS NOT NULL AND p.dt_nascimento >= CURRENT_DATE - INTERVAL '7 years'
         AND v1.co_fat_cidadao_pec IS NULL THEN 1 ELSE 0 END AS pendencia_vacina,
    CASE WHEN p.dt_nascimento IS NOT NULL AND p.dt_nascimento >= CURRENT_DATE - INTERVAL '7 years'
         AND pa1.co_fat_cidadao_pec IS NULL THEN 1 ELSE 0 END AS pendencia_peso_altura,
    CASE WHEN ga1.co_fat_cidadao_pec IS NOT NULL AND pn1.co_fat_cidadao_pec IS NULL THEN 1 ELSE 0 END AS pendencia_prenatal
FROM pacientes p
LEFT JOIN LATERAL (
    SELECT du.no_unidade_saude, du.nu_cnes, te.no_equipe
    FROM tb_fat_cad_individual cad
    JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = cad.co_seq_fat_cad_individual
        AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
        AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    LEFT JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
    WHERE cad.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec
    ORDER BY f.co_dim_tempo DESC
    LIMIT 1
) v ON TRUE
LEFT JOIN LATERAL (
    SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_atendimento_individual a
    WHERE a.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec AND a.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '6 months', 'YYYYMMDD')::INTEGER LIMIT 1
) c1 ON TRUE
LEFT JOIN LATERAL (
    SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_vacinacao va
    WHERE va.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec AND va.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '12 months', 'YYYYMMDD')::INTEGER LIMIT 1
) v1 ON TRUE
LEFT JOIN LATERAL (
    SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_atendimento_individual a
    WHERE a.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec AND a.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '12 months', 'YYYYMMDD')::INTEGER AND a.nu_peso IS NOT NULL AND a.nu_altura IS NOT NULL LIMIT 1
) pa1 ON TRUE
LEFT JOIN LATERAL (
    SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_rel_op_gestante g
    WHERE g.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec AND g.dt_inicio_gestacao IS NOT NULL AND (g.dt_fim_puerperio IS NULL OR g.dt_fim_puerperio >= CURRENT_DATE) LIMIT 1
) ga1 ON TRUE
LEFT JOIN LATERAL (
    SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_atendimento_individual a
    JOIN tb_dim_cbo cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
    WHERE a.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec AND a.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '3 months', 'YYYYMMDD')::INTEGER AND (cb.nu_cbo LIKE '2235%%' OR cb.nu_cbo LIKE '225%%') LIMIT 1
) pn1 ON TRUE
ORDER BY v.no_unidade_saude NULLS LAST, p.nome_esus NULLS LAST
"""

BOLSA_IDS_SQL = """
WITH cpfs AS (
    SELECT DISTINCT bf.nu_documento AS doc
    FROM tb_cidadao_bolsa_familia bf
    WHERE bf.ds_vigencia = (SELECT MAX(ds_vigencia) FROM tb_cidadao_bolsa_familia)
      AND bf.tp_documento = 'CPF'
),
pacientes AS (
    SELECT p.co_seq_fat_cidadao_pec
    FROM cpfs c
    JOIN tb_fat_cidadao_pec p ON p.nu_cpf_cidadao = c.doc
        AND p.st_faleceu = 0 AND (p.st_deletar IS NULL OR p.st_deletar = 0)
    GROUP BY p.co_seq_fat_cidadao_pec
)
SELECT p.co_seq_fat_cidadao_pec
FROM pacientes p
ORDER BY p.co_seq_fat_cidadao_pec
"""

BOLSA_AGREGADOS_SQL = """
WITH cpfs AS (
    SELECT DISTINCT bf.nu_documento AS doc
    FROM tb_cidadao_bolsa_familia bf
    WHERE bf.ds_vigencia = (SELECT MAX(ds_vigencia) FROM tb_cidadao_bolsa_familia)
      AND bf.tp_documento = 'CPF'
),
ids AS (
    SELECT p.co_seq_fat_cidadao_pec, MIN(cad.dt_nascimento) AS dt_nascimento
    FROM cpfs c
    JOIN tb_fat_cidadao_pec p ON p.nu_cpf_cidadao = c.doc AND p.st_faleceu = 0 AND (p.st_deletar IS NULL OR p.st_deletar = 0)
    LEFT JOIN tb_fat_cad_individual cad ON cad.co_fat_cidadao_pec = p.co_seq_fat_cidadao_pec
    GROUP BY p.co_seq_fat_cidadao_pec
)
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN c1.co_fat_cidadao_pec IS NULL THEN 1 ELSE 0 END) AS pendencia_consulta,
    SUM(CASE WHEN i.dt_nascimento IS NOT NULL AND i.dt_nascimento >= CURRENT_DATE - INTERVAL '7 years' AND v1.co_fat_cidadao_pec IS NULL THEN 1 ELSE 0 END) AS pendencia_vacina,
    SUM(CASE WHEN i.dt_nascimento IS NOT NULL AND i.dt_nascimento >= CURRENT_DATE - INTERVAL '7 years' AND pa1.co_fat_cidadao_pec IS NULL THEN 1 ELSE 0 END) AS pendencia_peso_altura,
    SUM(CASE WHEN ga1.co_fat_cidadao_pec IS NOT NULL AND pn1.co_fat_cidadao_pec IS NULL THEN 1 ELSE 0 END) AS pendencia_prenatal
FROM ids i
LEFT JOIN LATERAL (SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_atendimento_individual a WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec AND a.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '6 months', 'YYYYMMDD')::INTEGER LIMIT 1) c1 ON TRUE
LEFT JOIN LATERAL (SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_vacinacao va WHERE va.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec AND va.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '12 months', 'YYYYMMDD')::INTEGER LIMIT 1) v1 ON TRUE
LEFT JOIN LATERAL (SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_atendimento_individual a WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec AND a.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '12 months', 'YYYYMMDD')::INTEGER AND a.nu_peso IS NOT NULL AND a.nu_altura IS NOT NULL LIMIT 1) pa1 ON TRUE
LEFT JOIN LATERAL (SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_rel_op_gestante g WHERE g.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec AND g.dt_inicio_gestacao IS NOT NULL AND (g.dt_fim_puerperio IS NULL OR g.dt_fim_puerperio >= CURRENT_DATE) LIMIT 1) ga1 ON TRUE
LEFT JOIN LATERAL (SELECT 1 AS co_fat_cidadao_pec FROM tb_fat_atendimento_individual a JOIN tb_dim_cbo cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec AND a.co_dim_tempo >= TO_CHAR(CURRENT_DATE - INTERVAL '3 months', 'YYYYMMDD')::INTEGER AND (cb.nu_cbo LIKE '2235%%' OR cb.nu_cbo LIKE '225%%') LIMIT 1) pn1 ON TRUE
"""


@app.get("/api/bolsa-familia")
def get_bolsa_familia(unidade: str = Query(None), pagina: int = Query(1, alias="pagina"), por_pagina: int = Query(500, alias="por_pagina")):
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SET statement_timeout = 60000")
            # Step 1: total count (fast)
            cur.execute("SELECT COUNT(*) AS v FROM (" + BOLSA_IDS_SQL + ") sub")
            total = cur.fetchone()["v"]
            # Step 2: paginated IDs
            offset = (pagina - 1) * por_pagina
            cur.execute(BOLSA_IDS_SQL + f" LIMIT {por_pagina} OFFSET {offset}")
            ids = [r["co_seq_fat_cidadao_pec"] for r in cur.fetchall()]
            # Step 3: full data for those IDs (inject filtered CTE)
            if ids:
                ids_list = ", ".join(str(i) for i in ids)
                sql = BOLSA_PACIENTES_SQL.replace(
                    "FROM pacientes p",
                    f"FROM (SELECT * FROM pacientes WHERE co_seq_fat_cidadao_pec IN ({ids_list})) p"
                )
                cur.execute(sql)
                rows = [fmt_row(r) for r in cur.fetchall()]
            else:
                rows = []
            # Step 4: aggregates (separate query)
            cur.execute(BOLSA_AGREGADOS_SQL)
            aggr = cur.fetchone()
        conn.close()
    except Exception as e:
        log.error("Erro ao consultar bolsa familia: %s", e)
        raise HTTPException(500, "Erro ao consultar beneficiários Bolsa Família")
    total_pendencias = (aggr["pendencia_consulta"] if aggr else 0) + (aggr["pendencia_vacina"] if aggr else 0) + (aggr["pendencia_peso_altura"] if aggr else 0) + (aggr["pendencia_prenatal"] if aggr else 0)
    return {
        "total": total,
        "total_pendencias": total_pendencias,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": max(1, (total + por_pagina - 1) // por_pagina),
        "beneficiarios": rows,
        "agregados": {
            "pendencia_consulta": aggr["pendencia_consulta"] if aggr else 0,
            "pendencia_vacina": aggr["pendencia_vacina"] if aggr else 0,
            "pendencia_peso_altura": aggr["pendencia_peso_altura"] if aggr else 0,
            "pendencia_prenatal": aggr["pendencia_prenatal"] if aggr else 0,
        },
    }


@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS v FROM tb_fat_cidadao_pec WHERE st_faleceu=0 AND (st_deletar IS NULL OR st_deletar=0)")
            total_cidadaos = cur.fetchone()["v"]
            cur.execute("SELECT COUNT(DISTINCT c.co_seq_fat_cidadao_pec) AS v FROM tb_fat_cidadao_pec c JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec WHERE ci.st_morador_rua = 1 AND (c.st_deletar IS NULL OR c.st_deletar = 0) AND c.st_faleceu = 0")
            total_morador_rua = cur.fetchone()["v"]
            cur.execute("""
                SELECT COUNT(*) AS v FROM tb_fat_cad_individual fci
                JOIN tb_dim_tipo_saida_cadastro tsc ON tsc.co_seq_dim_tipo_saida_cadastro = fci.co_dim_tipo_saida_cadastro
                WHERE tsc.nu_identificador = '-' AND fci.co_dim_nacionalidade = 3 AND fci.st_ficha_inativa = 0
                  AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND cid.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND cid.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER)
                  AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid JOIN tb_fat_cidadao raiz ON cid.co_fat_cidadao_raiz = raiz.co_fat_cidadao_raiz WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND raiz.co_dim_tempo_validade > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND raiz.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND raiz.st_vivo=1 AND raiz.st_mudou=0)
            """)
            total_estrangeiros = cur.fetchone()["v"]
            cur.execute("""
                SELECT COUNT(*) AS v FROM tb_fat_cad_individual fci
                JOIN tb_dim_tipo_saida_cadastro tsc ON tsc.co_seq_dim_tipo_saida_cadastro = fci.co_dim_tipo_saida_cadastro
                WHERE tsc.nu_identificador = '-' AND fci.co_dim_raca_cor = 5 AND fci.st_ficha_inativa = 0
                  AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND cid.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND cid.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER)
                  AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid JOIN tb_fat_cidadao raiz ON cid.co_fat_cidadao_raiz = raiz.co_fat_cidadao_raiz WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND raiz.co_dim_tempo_validade > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND raiz.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND raiz.st_vivo=1 AND raiz.st_mudou=0)
            """)
            total_indigenas = cur.fetchone()["v"]
            cur.execute("""
                SELECT COUNT(DISTINCT fci.co_seq_fat_cad_individual) AS v
                FROM tb_fat_cad_individual fci
                JOIN tb_dim_tipo_saida_cadastro tsc ON tsc.co_seq_dim_tipo_saida_cadastro = fci.co_dim_tipo_saida_cadastro
                JOIN tb_fat_cidadao_pec c ON fci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
                WHERE tsc.nu_identificador = '-' AND fci.st_defi_fisica = 1 AND fci.st_ficha_inativa = 0
                  AND (c.st_deletar IS NULL OR c.st_deletar = 0) AND c.st_faleceu = 0
                  AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND cid.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND cid.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER)
            """)
            total_def_fisica = cur.fetchone()["v"]
            cur.execute("""
                SELECT COUNT(DISTINCT fci.co_seq_fat_cad_individual) AS v
                FROM tb_fat_cad_individual fci
                JOIN tb_dim_tipo_saida_cadastro tsc ON tsc.co_seq_dim_tipo_saida_cadastro = fci.co_dim_tipo_saida_cadastro
                JOIN tb_fat_cidadao_pec c ON fci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
                WHERE tsc.nu_identificador = '-' AND fci.st_defi_intelectual_cognitiva = 1 AND fci.st_ficha_inativa = 0
                  AND (c.st_deletar IS NULL OR c.st_deletar = 0) AND c.st_faleceu = 0
                  AND EXISTS (SELECT 1 FROM tb_fat_cidadao cid WHERE cid.co_fat_cad_individual = fci.co_seq_fat_cad_individual AND cid.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER AND cid.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER)
            """)
            total_def_mental = cur.fetchone()["v"]
        conn.close()
    except Exception as e:
        log.error("Erro dashboard stats: %s", e)
        raise HTTPException(500, "Erro ao carregar estatísticas")
    return {
        "total_cidadaos": total_cidadaos,
        "total_morador_rua": total_morador_rua,
        "total_estrangeiros": total_estrangeiros,
        "total_indigenas": total_indigenas,
        "total_def_fisica": total_def_fisica,
        "total_def_mental": total_def_mental,
    }


def agregar_por_unidade(rows):
    agg = defaultdict(lambda: {"total_atendimentos": 0, "programada": 0,
                               "total_cd": 0, "pessoas_1a_consulta": 0,
                               "pessoas_atendidas": 0, "cnes": ""})
    for r in rows:
        u = r["unidade_saude"]
        agg[u]["cnes"] = r.get("cnes", "")
        agg[u]["total_atendimentos"] += r.get("total_atendimentos", 0) or 0
        agg[u]["programada"] += r.get("programada", 0) or 0
        agg[u]["total_cd"] += r.get("total_cd", 0) or 0
        agg[u]["pessoas_1a_consulta"] += r.get("pessoas_1a_consulta", 0) or 0
        agg[u]["pessoas_atendidas"] += r.get("pessoas_atendidas", 0) or 0
    result = []
    for u, v in sorted(agg.items()):
        row = {"unidade_saude": u, "cnes": v["cnes"],
               "total_atendimentos": v["total_atendimentos"],
               "programada": v["programada"],
               "perc_programada": round(100.0 * v["programada"] / v["total_atendimentos"], 2) if v["total_atendimentos"] else 0,
               "total_cd": v["total_cd"],
               "pessoas_1a_consulta": v["pessoas_1a_consulta"],
               "pessoas_atendidas": v["pessoas_atendidas"]}
        result.append(row)
    return result


def executar_indicador(sql, params, unidade=None):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        conn.close()
        raise e
    if unidade:
        rows = [r for r in rows if unidade.lower() in r.get("unidade_saude","").lower() or unidade in r.get("cnes","")]
    return rows



@app.get("/api/indicadores/c1")
def get_c1(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      COUNT(*) AS total_atendimentos,
      SUM(CASE WHEN a.co_dim_tipo_atendimento IN {TIPO_PROG} THEN 1 ELSE 0 END) AS programada,
      ROUND(100.0 * SUM(CASE WHEN a.co_dim_tipo_atendimento IN {TIPO_PROG} THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 2) AS perc_programada
    FROM tb_fat_atendimento_individual a
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE a.co_dim_cbo_1 IN {CBO_MED_ENF}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
    GROUP BY du.no_unidade_saude, du.nu_cnes, te.no_equipe, te.nu_ine
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 70 or v < 10: return "Regular"
        if v >= 50: return "Ótimo"
        if v >= 30: return "Bom"
        return "Suficiente"
    for r in rows:
        r["classificacao"] = classif(r.get("perc_programada"))
    return {"indicador": "C1", "descricao": "Indicadores APS", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/indicadores/b1")
def get_b1(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    WITH populacao_ubs AS (
      SELECT f.co_dim_unidade_saude,
        COUNT(DISTINCT c.co_seq_fat_cidadao_pec) AS total_pessoas
      FROM tb_fat_cidadao_pec c
      LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
        AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
        AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      WHERE f.co_dim_unidade_saude IN {DIM_UNIDADES}
        AND (c.st_deletar IS NULL OR c.st_deletar = 0)
        AND c.st_faleceu = 0
      GROUP BY f.co_dim_unidade_saude
    ),
    primeira_consulta AS (
      SELECT a.co_dim_unidade_saude_1, a.co_dim_equipe_1,
        COUNT(DISTINCT a.co_fat_cidadao_pec) AS pessoas_1a_consulta
      FROM tb_fat_atend_odonto_proced a
      WHERE a.co_dim_cbo_1 IN {CBO_CD}
        AND a.co_dim_procedimento IN (SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced = '0301010153')
        AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
      GROUP BY a.co_dim_unidade_saude_1, a.co_dim_equipe_1
    )
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      pc.pessoas_1a_consulta,
      pu.total_pessoas,
      ROUND(100.0 * pc.pessoas_1a_consulta / NULLIF(pu.total_pessoas, 0), 2) AS percentual
    FROM primeira_consulta pc
    JOIN tb_dim_unidade_saude du ON pc.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON pc.co_dim_equipe_1 = te.co_seq_dim_equipe
    LEFT JOIN populacao_ubs pu ON pc.co_dim_unidade_saude_1 = pu.co_dim_unidade_saude
    WHERE te.no_equipe IS NOT NULL AND te.no_equipe != '' AND te.no_equipe != 'SEM EQUIPE'
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 5: return "Ótimo"
        if v > 3: return "Bom"
        if v > 1: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    return {"indicador": "B1", "descricao": "Indicadores da Odontologia", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/indicadores/m1")
def get_m1(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      COUNT(a.co_seq_fat_atd_ind) AS total_atendimentos,
      COUNT(DISTINCT a.co_fat_cidadao_pec) AS pessoas_atendidas,
      ROUND(1.0 * COUNT(a.co_seq_fat_atd_ind) / NULLIF(COUNT(DISTINCT a.co_fat_cidadao_pec),0), 2) AS media_atend_por_pessoa
    FROM tb_fat_atendimento_individual a
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE a.co_dim_cbo_1 IN {CBO_EMULTI}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
    GROUP BY du.no_unidade_saude, du.nu_cnes, te.no_equipe, te.nu_ine
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 3: return "Ótimo"
        if v >= 2: return "Bom"
        if v >= 1: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("media_atend_por_pessoa"))
    return {"indicador": "M1", "descricao": "Indicadores eMulti", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


# ========== C2 – Desenvolvimento Infantil (Nota Metodológica 2024) ==========
@app.get("/api/indicadores/c2")
def get_c2(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    ck = cache_key("c2", unidade, inicio, fim)
    cached = cache_get(ck)
    if cached: return cached
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    WITH cbo_med_enf AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
    ),
    cbo_antropometria AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
         OR nu_cbo LIKE '3222%%' OR nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    cbo_acs_tacs AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    proc_peso AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0101040083','ABPG039','0101040024')
    ),
    proc_altura AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0101040075','ABPG038','0101040024')
    ),
    -- Crianças ≤2 anos vinculadas à equipe via cadastro (tb_fat_cidadao)
    criancas_por_equipe AS (
      SELECT DISTINCT c.co_seq_fat_cidadao_pec AS co_fat_cidadao_pec,
        du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
        te.no_equipe, te.nu_ine, ci.dt_nascimento
      FROM tb_fat_cidadao_pec c
      JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
        AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
        AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
      JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
      WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND (c.st_deletar IS NULL OR c.st_deletar = 0)
        AND c.st_faleceu = 0
        AND ci.dt_nascimento IS NOT NULL
        AND ci.dt_nascimento >= TO_DATE({t_end}::TEXT, 'YYYYMMDD') - INTERVAL '2 years'
    ),
    -- A (20pts): 1ª consulta presencial médica(o)/enfermeira(o) até 30º dia de vida
    pratica_a AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM criancas_por_equipe cr
      JOIN tb_fat_atendimento_individual a ON cr.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.co_dim_tempo >= TO_CHAR(cr.dt_nascimento, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= TO_CHAR(cr.dt_nascimento + 30, 'YYYYMMDD')::INTEGER
    ),
    -- B (20pts): ≥9 consultas médica(o)/enfermeira(o) (presenciais ou remotas) até 2 anos
    consultas_b AS (
      SELECT DISTINCT a.co_fat_cidadao_pec, a.co_dim_tempo
      FROM criancas_por_equipe cr
      JOIN tb_fat_atendimento_individual a ON cr.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.co_dim_tempo >= TO_CHAR(cr.dt_nascimento, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= {t_end}
    ),
    pratica_b AS (
      SELECT co_fat_cidadao_pec
      FROM consultas_b
      GROUP BY co_fat_cidadao_pec
      HAVING COUNT(DISTINCT co_dim_tempo) >= 9
    ),
    -- C (20pts): ≥9 registros simultâneos Peso+Altura até 2 anos
    dias_peso_altura AS (
      SELECT ap.co_fat_cidadao_pec, ap.co_dim_tempo
      FROM criancas_por_equipe cr
      JOIN tb_fat_atd_ind_procedimentos ap ON cr.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_peso)
        AND ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_altura)
        AND ap.co_dim_tempo >= TO_CHAR(cr.dt_nascimento, 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo <= {t_end}
      UNION
      SELECT a.co_fat_cidadao_pec, a.co_dim_tempo
      FROM criancas_por_equipe cr
      JOIN tb_fat_atendimento_individual a ON cr.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_antropometria cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.nu_peso IS NOT NULL AND a.nu_altura IS NOT NULL
        AND a.co_dim_tempo >= TO_CHAR(cr.dt_nascimento, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= {t_end}
      UNION
      SELECT vd.co_fat_cidadao_pec, vd.co_dim_tempo
      FROM criancas_por_equipe cr
      JOIN tb_fat_visita_domiciliar vd ON cr.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      WHERE vd.nu_peso IS NOT NULL AND vd.nu_altura IS NOT NULL
        AND vd.co_dim_tempo >= TO_CHAR(cr.dt_nascimento, 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo <= {t_end}
    ),
    pratica_c AS (
      SELECT co_fat_cidadao_pec
      FROM dias_peso_altura
      GROUP BY co_fat_cidadao_pec
      HAVING COUNT(DISTINCT co_dim_tempo) >= 9
    ),
    -- D (20pts): ≥2 visitas ACS/TACS (1ª ≤30 dias, 2ª ≤6 meses)
    pratica_d AS (
      SELECT vd.co_fat_cidadao_pec
      FROM criancas_por_equipe cr
      JOIN tb_fat_visita_domiciliar vd ON cr.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      JOIN cbo_acs_tacs ac ON vd.co_dim_cbo = ac.co_seq_dim_cbo
      WHERE (vd.st_acomp_recem_nascido = 1 OR vd.st_acomp_crianca = 1)
        AND vd.co_dim_tempo >= TO_CHAR(cr.dt_nascimento, 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo <= TO_CHAR(cr.dt_nascimento + 180, 'YYYYMMDD')::INTEGER
      GROUP BY vd.co_fat_cidadao_pec
      HAVING COUNT(*) >= 2
         AND MIN(vd.co_dim_tempo) <= TO_CHAR(MIN(cr.dt_nascimento) + 30, 'YYYYMMDD')::INTEGER
    ),
    -- E (20pts): Esquema vacinal completo (Pentavalente, Polio, SCR, Pneumo)
    vacinas_completas AS (
      SELECT v.co_fat_cidadao_pec
      FROM criancas_por_equipe cr
      JOIN tb_fat_vacinacao v ON cr.co_fat_cidadao_pec = v.co_fat_cidadao_pec
      WHERE v.co_dim_tempo <= {t_end}
      GROUP BY v.co_fat_cidadao_pec
      HAVING
        SUM(CASE WHEN v.ds_filtro_imunobiologico ~ '\\|(09|17|29|39|42|43|46|47|58)\\|' THEN 1 ELSE 0 END) >= 3
        AND SUM(CASE WHEN v.ds_filtro_imunobiologico ~ '\\|(22|29|43|58)\\|' THEN 1 ELSE 0 END) >= 3
        AND SUM(CASE WHEN v.ds_filtro_imunobiologico ~ '\\|(24|56)\\|' THEN 1 ELSE 0 END) >= 2
        AND SUM(CASE WHEN v.ds_filtro_imunobiologico ~ '\\|(26|59|106|107)\\|' THEN 1 ELSE 0 END) >= 2
    ),
    agregado AS (
      SELECT ce.unidade_saude, ce.cnes, ce.no_equipe, ce.nu_ine,
        COUNT(DISTINCT ce.co_fat_cidadao_pec) AS total_criancas,
        COUNT(DISTINCT pa.co_fat_cidadao_pec) AS pratica_a,
        COUNT(DISTINCT pb.co_fat_cidadao_pec) AS pratica_b,
        COUNT(DISTINCT pc.co_fat_cidadao_pec) AS pratica_c,
        COUNT(DISTINCT pd.co_fat_cidadao_pec) AS pratica_d,
        COUNT(DISTINCT pe.co_fat_cidadao_pec) AS pratica_e
      FROM criancas_por_equipe ce
      LEFT JOIN pratica_a pa ON ce.co_fat_cidadao_pec = pa.co_fat_cidadao_pec
      LEFT JOIN pratica_b pb ON ce.co_fat_cidadao_pec = pb.co_fat_cidadao_pec
      LEFT JOIN pratica_c pc ON ce.co_fat_cidadao_pec = pc.co_fat_cidadao_pec
      LEFT JOIN pratica_d pd ON ce.co_fat_cidadao_pec = pd.co_fat_cidadao_pec
      LEFT JOIN vacinas_completas pe ON ce.co_fat_cidadao_pec = pe.co_fat_cidadao_pec
      GROUP BY ce.unidade_saude, ce.cnes, ce.no_equipe, ce.nu_ine
    )
    SELECT *,
      (pratica_a + pratica_b + pratica_c + pratica_d + pratica_e) AS soma_praticas,
      ROUND((pratica_a + pratica_b + pratica_c + pratica_d + pratica_e) * 20.0
        / NULLIF(total_criancas, 0), 2) AS percentual
    FROM agregado
    ORDER BY unidade_saude, no_equipe;
    """
    rows = executar_indicador(SQL, (), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 75: return "Ótimo"
        if v > 50: return "Bom"
        if v > 25: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    result = {"indicador": "C2", "descricao": "Boas Práticas no Desenvolvimento Infantil",
      "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}
    cache_set(ck, result)
    return result

# ========== C3 – Cuidado na Gestação e Puerpério ==========
@app.get("/api/indicadores/c3")
def get_c3(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    ck = cache_key("c3", unidade, inicio, fim)
    cached = cache_get(ck)
    if cached: return cached
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    WITH cbo_med_enf AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '225%%' OR nu_cbo LIKE '2231%%'
    ),
    cbo_acs_tacs AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    cbo_cd_tsb AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2232%%' OR nu_cbo LIKE '3224%%'
    ),
    proc_peso AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento
      WHERE co_proced IN ('0101040083','ABPG039')
    ),
    proc_altura AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento
      WHERE co_proced IN ('0101040075','ABPG038')
    ),
    proc_pa AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento
      WHERE co_proced = '0301100039'
    ),
    proc_teste_1tri AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento
      WHERE co_proced IN (
        '0214010040','0214010279','0214010058','0213010780','0213010500',
        '0214010074','0214010082','0214010252','0202031098','0202031110','0202031179',
        '0214010104','0214010236','0202030784','0202030970','0213010208',
        '0214010090','0214010309','0202030059','0202030679')
    ),
    proc_teste_3tri AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento
      WHERE co_proced IN (
        '0214010040','0214010279','0214010058','0213010780','0213010500',
        '0214010074','0214010082','0214010252','0202031098','0202031110','0202031179')
    ),
    -- Base: gestações ativas no período
    gestacoes_por_equipe AS (
      SELECT DISTINCT ON (g.co_fat_cidadao_pec, g.co_gestacao)
        g.co_fat_cidadao_pec, g.co_gestacao,
        g.dt_inicio_gestacao,
        g.dt_inicio_puerperio,
        COALESCE(g.dt_fim_puerperio, g.dt_inicio_puerperio + 42) AS dt_fim_puerperio,
        du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
        te.no_equipe, te.nu_ine
      FROM tb_fat_rel_op_gestante g
      JOIN tb_fat_cidadao_pec c ON g.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
        AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
        AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
      LEFT JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
      WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND g.dt_inicio_gestacao IS NOT NULL
        AND TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER <= %s
        AND (g.dt_fim_puerperio IS NULL
             OR TO_CHAR(g.dt_fim_puerperio, 'YYYYMMDD')::INTEGER >= %s)
      ORDER BY g.co_fat_cidadao_pec, g.co_gestacao, f.co_dim_tempo DESC
    ),
    -- 1ª consulta pré-natal (p/ prática E)
    primeira_consulta AS (
      SELECT DISTINCT ON (g.co_fat_cidadao_pec, g.co_gestacao)
        g.co_fat_cidadao_pec, g.co_gestacao, a.co_dim_tempo AS dt_primeira
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atendimento_individual a ON g.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo >= {t_start} AND a.co_dim_tempo <= {t_end}
      ORDER BY g.co_fat_cidadao_pec, g.co_gestacao, a.co_dim_tempo
    ),
    -- A (10pt): 1ª consulta médica(o)/enfermeira(o) até 12ª semana
    pratica_a AS (
      SELECT DISTINCT g.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atendimento_individual a ON g.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= TO_CHAR(g.dt_inicio_gestacao + 84, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo >= {t_start} AND a.co_dim_tempo <= {t_end}
    ),
    -- B (9pt): ≥7 consultas médica(o)/enfermeira(o) na gestação
    pratica_b AS (
      SELECT a.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atendimento_individual a ON g.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo >= {t_start} AND a.co_dim_tempo <= {t_end}
      GROUP BY a.co_fat_cidadao_pec, g.co_gestacao
      HAVING COUNT(*) >= 7
    ),
    -- C (9pt): ≥7 aferições de PA na gestação
    dias_pa AS (
      SELECT DISTINCT a.co_fat_cidadao_pec, g.co_gestacao, a.co_dim_tempo
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atendimento_individual a ON g.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      WHERE (a.nu_pressao_sistolica IS NOT NULL OR a.nu_pressao_diastolica IS NOT NULL)
        AND a.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo >= {t_start} AND a.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT ap.co_fat_cidadao_pec, g.co_gestacao, ap.co_dim_tempo
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atd_ind_procedimentos ap ON g.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_pa)
        AND ap.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo >= {t_start} AND ap.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT vd.co_fat_cidadao_pec, g.co_gestacao, vd.co_dim_tempo
      FROM gestacoes_por_equipe g
      JOIN tb_fat_visita_domiciliar vd ON g.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      WHERE vd.nu_medicao_pressao_arterial IS NOT NULL
        AND vd.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo >= {t_start} AND vd.co_dim_tempo <= {t_end}
    ),
    pratica_c AS (
      SELECT co_fat_cidadao_pec, co_gestacao
      FROM dias_pa
      GROUP BY co_fat_cidadao_pec, co_gestacao
      HAVING COUNT(*) >= 7
    ),
    -- D (9pt): ≥7 registros simultâneos peso+altura na gestação
    dias_peso_altura AS (
      SELECT DISTINCT a.co_fat_cidadao_pec, g.co_gestacao, a.co_dim_tempo
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atendimento_individual a ON g.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      WHERE a.nu_peso IS NOT NULL AND a.nu_altura IS NOT NULL
        AND a.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo >= {t_start} AND a.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT ap.co_fat_cidadao_pec, g.co_gestacao, ap.co_dim_tempo
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atd_ind_procedimentos ap ON g.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_peso)
        AND ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_altura)
        AND ap.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo >= {t_start} AND ap.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT vd.co_fat_cidadao_pec, g.co_gestacao, vd.co_dim_tempo
      FROM gestacoes_por_equipe g
      JOIN tb_fat_visita_domiciliar vd ON g.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      WHERE vd.nu_peso IS NOT NULL AND vd.nu_altura IS NOT NULL
        AND vd.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo >= {t_start} AND vd.co_dim_tempo <= {t_end}
    ),
    pratica_d AS (
      SELECT co_fat_cidadao_pec, co_gestacao
      FROM dias_peso_altura
      GROUP BY co_fat_cidadao_pec, co_gestacao
      HAVING COUNT(*) >= 7
    ),
    -- E (9pt): ≥3 visitas ACS/TACS após 1ª consulta pré-natal
    pratica_e AS (
      SELECT g.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_visita_domiciliar vd ON g.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      JOIN cbo_acs_tacs ac ON vd.co_dim_cbo = ac.co_seq_dim_cbo
      JOIN primeira_consulta pc ON g.co_fat_cidadao_pec = pc.co_fat_cidadao_pec
        AND g.co_gestacao = pc.co_gestacao
      WHERE vd.co_dim_tempo >= pc.dt_primeira
        AND vd.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo >= {t_start} AND vd.co_dim_tempo <= {t_end}
      GROUP BY g.co_fat_cidadao_pec, g.co_gestacao
      HAVING COUNT(*) >= 3
    ),
    -- F (9pt): dTpa a partir da 20ª semana
    pratica_f AS (
      SELECT DISTINCT g.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_vacinacao v ON g.co_fat_cidadao_pec = v.co_fat_cidadao_pec
      WHERE v.ds_filtro_imunobiologico ~ '\|57\|'
        AND v.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao + 140, 'YYYYMMDD')::INTEGER
        AND v.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND v.co_dim_tempo >= {t_start} AND v.co_dim_tempo <= {t_end}
    ),
    -- G (9pt): testes 1º trimestre (sífilis, HIV, HepB, HepC)
    pratica_g AS (
      SELECT DISTINCT g.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atd_ind_procedimentos ap ON g.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_teste_1tri)
        AND ap.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo <= TO_CHAR(g.dt_inicio_gestacao + 91, 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo >= {t_start} AND ap.co_dim_tempo <= {t_end}
    ),
    -- H (9pt): testes 3º trimestre (sífilis, HIV)
    pratica_h AS (
      SELECT DISTINCT g.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atd_ind_procedimentos ap ON g.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_teste_3tri)
        AND ap.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao + 196, 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND ap.co_dim_tempo >= {t_start} AND ap.co_dim_tempo <= {t_end}
    ),
    -- I (9pt): ≥1 consulta puerperal médica(o)/enfermeira(o)
    pratica_i AS (
      SELECT DISTINCT g.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atendimento_individual a ON g.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE g.dt_inicio_puerperio IS NOT NULL
        AND a.co_dim_tempo >= TO_CHAR(g.dt_inicio_puerperio, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo <= TO_CHAR(g.dt_fim_puerperio, 'YYYYMMDD')::INTEGER
        AND a.co_dim_tempo >= {t_start} AND a.co_dim_tempo <= {t_end}
    ),
    -- J (9pt): ≥1 visita ACS/TACS no puerpério
    pratica_j AS (
      SELECT DISTINCT g.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_visita_domiciliar vd ON g.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      JOIN cbo_acs_tacs ac ON vd.co_dim_cbo = ac.co_seq_dim_cbo
      WHERE g.dt_inicio_puerperio IS NOT NULL
        AND vd.co_dim_tempo >= TO_CHAR(g.dt_inicio_puerperio, 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo <= TO_CHAR(g.dt_fim_puerperio, 'YYYYMMDD')::INTEGER
        AND vd.co_dim_tempo >= {t_start} AND vd.co_dim_tempo <= {t_end}
    ),
    -- K (9pt): ≥1 atividade saúde bucal CD/TSB na gestação
    pratica_k AS (
      SELECT DISTINCT g.co_fat_cidadao_pec, g.co_gestacao
      FROM gestacoes_por_equipe g
      JOIN tb_fat_atendimento_odonto ao ON g.co_fat_cidadao_pec = ao.co_fat_cidadao_pec
      JOIN cbo_cd_tsb cb ON ao.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE ao.co_dim_tempo >= TO_CHAR(g.dt_inicio_gestacao, 'YYYYMMDD')::INTEGER
        AND ao.co_dim_tempo <= TO_CHAR(COALESCE(g.dt_inicio_puerperio - 1, CURRENT_DATE), 'YYYYMMDD')::INTEGER
        AND ao.co_dim_tempo >= {t_start} AND ao.co_dim_tempo <= {t_end}
    ),
    agregado AS (
      SELECT
        ge.unidade_saude, ge.cnes, ge.no_equipe, ge.nu_ine,
        COUNT(DISTINCT ge.co_fat_cidadao_pec::TEXT || '|' || ge.co_gestacao::TEXT) AS total_gestacoes,
        COUNT(DISTINCT pa.co_fat_cidadao_pec::TEXT || '|' || pa.co_gestacao::TEXT) AS pratica_a,
        COUNT(DISTINCT pb.co_fat_cidadao_pec::TEXT || '|' || pb.co_gestacao::TEXT) AS pratica_b,
        COUNT(DISTINCT pc.co_fat_cidadao_pec::TEXT || '|' || pc.co_gestacao::TEXT) AS pratica_c,
        COUNT(DISTINCT pd.co_fat_cidadao_pec::TEXT || '|' || pd.co_gestacao::TEXT) AS pratica_d,
        COUNT(DISTINCT pe.co_fat_cidadao_pec::TEXT || '|' || pe.co_gestacao::TEXT) AS pratica_e,
        COUNT(DISTINCT pf.co_fat_cidadao_pec::TEXT || '|' || pf.co_gestacao::TEXT) AS pratica_f,
        COUNT(DISTINCT pg.co_fat_cidadao_pec::TEXT || '|' || pg.co_gestacao::TEXT) AS pratica_g,
        COUNT(DISTINCT ph.co_fat_cidadao_pec::TEXT || '|' || ph.co_gestacao::TEXT) AS pratica_h,
        COUNT(DISTINCT pi.co_fat_cidadao_pec::TEXT || '|' || pi.co_gestacao::TEXT) AS pratica_i,
        COUNT(DISTINCT pj.co_fat_cidadao_pec::TEXT || '|' || pj.co_gestacao::TEXT) AS pratica_j,
        COUNT(DISTINCT pk.co_fat_cidadao_pec::TEXT || '|' || pk.co_gestacao::TEXT) AS pratica_k
      FROM gestacoes_por_equipe ge
      LEFT JOIN pratica_a pa ON ge.co_fat_cidadao_pec = pa.co_fat_cidadao_pec AND ge.co_gestacao = pa.co_gestacao
      LEFT JOIN pratica_b pb ON ge.co_fat_cidadao_pec = pb.co_fat_cidadao_pec AND ge.co_gestacao = pb.co_gestacao
      LEFT JOIN pratica_c pc ON ge.co_fat_cidadao_pec = pc.co_fat_cidadao_pec AND ge.co_gestacao = pc.co_gestacao
      LEFT JOIN pratica_d pd ON ge.co_fat_cidadao_pec = pd.co_fat_cidadao_pec AND ge.co_gestacao = pd.co_gestacao
      LEFT JOIN pratica_e pe ON ge.co_fat_cidadao_pec = pe.co_fat_cidadao_pec AND ge.co_gestacao = pe.co_gestacao
      LEFT JOIN pratica_f pf ON ge.co_fat_cidadao_pec = pf.co_fat_cidadao_pec AND ge.co_gestacao = pf.co_gestacao
      LEFT JOIN pratica_g pg ON ge.co_fat_cidadao_pec = pg.co_fat_cidadao_pec AND ge.co_gestacao = pg.co_gestacao
      LEFT JOIN pratica_h ph ON ge.co_fat_cidadao_pec = ph.co_fat_cidadao_pec AND ge.co_gestacao = ph.co_gestacao
      LEFT JOIN pratica_i pi ON ge.co_fat_cidadao_pec = pi.co_fat_cidadao_pec AND ge.co_gestacao = pi.co_gestacao
      LEFT JOIN pratica_j pj ON ge.co_fat_cidadao_pec = pj.co_fat_cidadao_pec AND ge.co_gestacao = pj.co_gestacao
      LEFT JOIN pratica_k pk ON ge.co_fat_cidadao_pec = pk.co_fat_cidadao_pec AND ge.co_gestacao = pk.co_gestacao
      GROUP BY ge.unidade_saude, ge.cnes, ge.no_equipe, ge.nu_ine
    )
    SELECT *,
      (pratica_a * 10 + (pratica_b + pratica_c + pratica_d + pratica_e + pratica_f + pratica_g + pratica_h + pratica_i + pratica_j + pratica_k) * 9) AS soma_pontos,
      ROUND((pratica_a * 10.0 + (pratica_b + pratica_c + pratica_d + pratica_e + pratica_f + pratica_g + pratica_h + pratica_i + pratica_j + pratica_k) * 9.0) * 100.0 / NULLIF(total_gestacoes * 100.0, 0), 2) AS percentual
    FROM agregado
    ORDER BY unidade_saude, no_equipe;
    """
    rows = executar_indicador(SQL, (t_end, t_start), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 75: return "Ótimo"
        if v > 50: return "Bom"
        if v > 25: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    result = {"indicador": "C3", "descricao": "Cuidado na Gestação e Puerpério",
      "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}
    cache_set(ck, result)
    return result

# ========== C4 – Diabetes ==========
# NM 2024: 6 boas práticas (A–F), cada uma vale 1pt, máximo 6pts por paciente
# Fonte: tb_fat_atendimento_individual.ds_filtro_cids / ds_filtro_ciaps (desde 2013)
CID_DIABETES = ('E10','E11','E14')
CIAP_DIABETES = ('T89','T90')

@app.get("/api/indicadores/c4")
def get_c4(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    ck = cache_key("c4", unidade, inicio, fim)
    cached = cache_get(ck)
    if cached: return cached
    t_start, t_end = periodo_sql(inicio, fim)
    # Períodos relativos (A/B = 6m, C/D/E/F = 12m anteriores a t_end)
    t_6m = int((datetime.strptime(str(t_end),"%Y%m%d") - timedelta(days=183)).strftime("%Y%m%d"))
    t_12m = int((datetime.strptime(str(t_end),"%Y%m%d") - timedelta(days=366)).strftime("%Y%m%d"))
    SQL = f"""
    WITH cbo_med_enf AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
    ),
    cbo_acs_tacs AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    cbo_procedimentos AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
         OR nu_cbo LIKE '2232%%' OR nu_cbo LIKE '2234%%' OR nu_cbo LIKE '2236%%' OR nu_cbo LIKE '2238%%'
         OR nu_cbo LIKE '2237%%' OR nu_cbo LIKE '2241%%' OR nu_cbo LIKE '3222%%' OR nu_cbo LIKE '2239%%'
         OR nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    proc_pa AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced = '0301100039'
    ),
    proc_peso AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0101040083','ABPG039','0101040024')
    ),
    proc_altura AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0101040075','ABPG038','0101040024')
    ),
    proc_hba1c AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0202010503','ABEX008')
    ),
    proc_pe AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced = '0301040095'
    ),
    -- Base: pessoas com diabetes (CID-10 E10-E14 ou CIAP-2 T89/T90 desde 2013)
    diabeticos_por_equipe AS (
      SELECT DISTINCT ON (a.co_fat_cidadao_pec)
        a.co_fat_cidadao_pec,
        du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
        te.no_equipe, te.nu_ine
      FROM tb_fat_atendimento_individual a
      JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
      JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
      JOIN tb_fat_cidadao_pec c ON a.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND (a.ds_filtro_cids ~ 'E10|E11|E14' OR a.ds_filtro_ciaps ~ 'T89|T90')
        AND a.co_dim_tempo >= 20130101
        AND (c.st_deletar IS NULL OR c.st_deletar = 0) AND c.st_faleceu = 0
      ORDER BY a.co_fat_cidadao_pec, a.co_dim_tempo DESC
    ),
    -- A (1pt): ≥1 consulta médica(o)/enfermeira(o) nos últimos 6 meses
    pratica_a AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_atendimento_individual a ON d.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.co_dim_tempo >= {t_6m} AND a.co_dim_tempo <= {t_end}
    ),
    -- B (1pt): ≥1 aferição PA nos últimos 6 meses
    dias_pa AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_atendimento_individual a ON d.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      WHERE (a.nu_pressao_sistolica IS NOT NULL OR a.nu_pressao_diastolica IS NOT NULL)
        AND a.co_dim_tempo >= {t_6m} AND a.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_atd_ind_procedimentos ap ON d.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_pa)
        AND ap.co_dim_tempo >= {t_6m} AND ap.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT vd.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_visita_domiciliar vd ON d.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      WHERE vd.nu_medicao_pressao_arterial IS NOT NULL
        AND vd.co_dim_tempo >= {t_6m} AND vd.co_dim_tempo <= {t_end}
    ),
    pratica_b AS (
      SELECT DISTINCT co_fat_cidadao_pec FROM dias_pa
    ),
    -- C (1pt): ≥1 registro simultâneo peso+altura nos últimos 12 meses
    dias_peso_altura AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_atendimento_individual a ON d.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      WHERE a.nu_peso IS NOT NULL AND a.nu_altura IS NOT NULL
        AND a.co_dim_tempo >= {t_12m} AND a.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_atd_ind_procedimentos ap ON d.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_peso)
        AND ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_altura)
        AND ap.co_dim_tempo >= {t_12m} AND ap.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT vd.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_visita_domiciliar vd ON d.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      WHERE vd.nu_peso IS NOT NULL AND vd.nu_altura IS NOT NULL
        AND vd.co_dim_tempo >= {t_12m} AND vd.co_dim_tempo <= {t_end}
    ),
    pratica_c AS (
      SELECT DISTINCT co_fat_cidadao_pec FROM dias_peso_altura
    ),
    -- D (1pt): ≥2 visitas ACS/TACS (≥30 dias intervalo) nos últimos 12 meses
    pratica_d AS (
      SELECT vd.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_visita_domiciliar vd ON d.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      JOIN cbo_acs_tacs ac ON vd.co_dim_cbo = ac.co_seq_dim_cbo
      WHERE vd.co_dim_tempo >= {t_12m} AND vd.co_dim_tempo <= {t_end}
      GROUP BY vd.co_fat_cidadao_pec
      HAVING COUNT(*) >= 2
        AND (MAX(vd.co_dim_tempo) - MIN(vd.co_dim_tempo)) >= 30
    ),
    -- E (1pt): ≥1 registro de hemoglobina glicada nos últimos 12 meses
    pratica_e AS (
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_atd_ind_procedimentos ap ON d.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_hba1c)
        AND ap.co_dim_tempo >= {t_12m} AND ap.co_dim_tempo <= {t_end}
    ),
    -- F (1pt): ≥1 exame do pé diabético nos últimos 12 meses
    pratica_f AS (
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM diabeticos_por_equipe d
      JOIN tb_fat_atd_ind_procedimentos ap ON d.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_pe)
        AND ap.co_dim_tempo >= {t_12m} AND ap.co_dim_tempo <= {t_end}
    ),
    agregado AS (
      SELECT d.unidade_saude, d.cnes, d.no_equipe, d.nu_ine,
        COUNT(DISTINCT d.co_fat_cidadao_pec) AS total_pessoas,
        COUNT(DISTINCT pa.co_fat_cidadao_pec) AS pratica_a,
        COUNT(DISTINCT pb.co_fat_cidadao_pec) AS pratica_b,
        COUNT(DISTINCT pc.co_fat_cidadao_pec) AS pratica_c,
        COUNT(DISTINCT pd.co_fat_cidadao_pec) AS pratica_d,
        COUNT(DISTINCT pe.co_fat_cidadao_pec) AS pratica_e,
        COUNT(DISTINCT pf.co_fat_cidadao_pec) AS pratica_f
      FROM diabeticos_por_equipe d
      LEFT JOIN pratica_a pa ON d.co_fat_cidadao_pec = pa.co_fat_cidadao_pec
      LEFT JOIN pratica_b pb ON d.co_fat_cidadao_pec = pb.co_fat_cidadao_pec
      LEFT JOIN pratica_c pc ON d.co_fat_cidadao_pec = pc.co_fat_cidadao_pec
      LEFT JOIN pratica_d pd ON d.co_fat_cidadao_pec = pd.co_fat_cidadao_pec
      LEFT JOIN pratica_e pe ON d.co_fat_cidadao_pec = pe.co_fat_cidadao_pec
      LEFT JOIN pratica_f pf ON d.co_fat_cidadao_pec = pf.co_fat_cidadao_pec
      GROUP BY d.unidade_saude, d.cnes, d.no_equipe, d.nu_ine
    )
    SELECT *,
      (pratica_a + pratica_b + pratica_c + pratica_d + pratica_e + pratica_f) AS soma_praticas,
      ROUND((pratica_a + pratica_b + pratica_c + pratica_d + pratica_e + pratica_f) * 100.0
        / NULLIF(total_pessoas * 6, 0), 2) AS percentual
    FROM agregado
    ORDER BY unidade_saude, no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 75: return "Ótimo"
        if v > 50: return "Bom"
        if v > 25: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    result = {"indicador": "C4", "descricao": "Cuidado da Pessoa com Diabetes",
      "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}
    cache_set(ck, result)
    return result

# ========== C5 – Hipertensão ==========
@app.get("/api/indicadores/c5")
def get_c5(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    ck = cache_key("c5", unidade, inicio, fim)
    cached = cache_get(ck)
    if cached: return cached
    t_start, t_end = periodo_sql(inicio, fim)
    t_6m = int((datetime.strptime(str(t_end),"%Y%m%d") - timedelta(days=183)).strftime("%Y%m%d"))
    t_12m = int((datetime.strptime(str(t_end),"%Y%m%d") - timedelta(days=366)).strftime("%Y%m%d"))
    SQL = f"""
    WITH cbo_med_enf AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
    ),
    cbo_acs_tacs AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    cbo_procedimentos AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
         OR nu_cbo LIKE '2232%%' OR nu_cbo LIKE '2234%%' OR nu_cbo LIKE '2236%%' OR nu_cbo LIKE '2238%%'
         OR nu_cbo LIKE '2237%%' OR nu_cbo LIKE '2241%%' OR nu_cbo LIKE '3222%%' OR nu_cbo LIKE '2239%%'
         OR nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    proc_pa AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced = '0301100039'
    ),
    proc_peso AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0101040083','ABPG039','0101040024')
    ),
    proc_altura AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0101040075','ABPG038','0101040024')
    ),
    -- Base: pessoas com hipertensão (CID-10 I10-I15, O10-O11 ou CIAP-2 K86/K87 desde 2013)
    hipertensos_por_equipe AS (
      SELECT DISTINCT ON (a.co_fat_cidadao_pec)
        a.co_fat_cidadao_pec,
        du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
        te.no_equipe, te.nu_ine
      FROM tb_fat_atendimento_individual a
      JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
      JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
      JOIN tb_fat_cidadao_pec c ON a.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND (a.ds_filtro_cids ~ 'I10|I11|I12|I13|I15|O10|O11' OR a.ds_filtro_ciaps ~ 'K86|K87')
        AND a.co_dim_tempo >= 20130101
        AND (c.st_deletar IS NULL OR c.st_deletar = 0) AND c.st_faleceu = 0
      ORDER BY a.co_fat_cidadao_pec, a.co_dim_tempo DESC
    ),
    -- A (25pt): ≥1 consulta médica(o)/enfermeira(o) nos últimos 6 meses
    pratica_a AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM hipertensos_por_equipe h
      JOIN tb_fat_atendimento_individual a ON h.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.co_dim_tempo >= {t_6m} AND a.co_dim_tempo <= {t_end}
    ),
    -- B (25pt): ≥1 aferição PA nos últimos 6 meses
    dias_pa AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM hipertensos_por_equipe h
      JOIN tb_fat_atendimento_individual a ON h.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      WHERE (a.nu_pressao_sistolica IS NOT NULL OR a.nu_pressao_diastolica IS NOT NULL)
        AND a.co_dim_tempo >= {t_6m} AND a.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM hipertensos_por_equipe h
      JOIN tb_fat_atd_ind_procedimentos ap ON h.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_pa)
        AND ap.co_dim_tempo >= {t_6m} AND ap.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT vd.co_fat_cidadao_pec
      FROM hipertensos_por_equipe h
      JOIN tb_fat_visita_domiciliar vd ON h.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      WHERE vd.nu_medicao_pressao_arterial IS NOT NULL
        AND vd.co_dim_tempo >= {t_6m} AND vd.co_dim_tempo <= {t_end}
    ),
    pratica_b AS (
      SELECT DISTINCT co_fat_cidadao_pec FROM dias_pa
    ),
    -- C (25pt): ≥1 registro simultâneo peso+altura nos últimos 12 meses
    dias_peso_altura AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM hipertensos_por_equipe h
      JOIN tb_fat_atendimento_individual a ON h.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      WHERE a.nu_peso IS NOT NULL AND a.nu_altura IS NOT NULL
        AND a.co_dim_tempo >= {t_12m} AND a.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM hipertensos_por_equipe h
      JOIN tb_fat_atd_ind_procedimentos ap ON h.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_peso)
        AND ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_altura)
        AND ap.co_dim_tempo >= {t_12m} AND ap.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT vd.co_fat_cidadao_pec
      FROM hipertensos_por_equipe h
      JOIN tb_fat_visita_domiciliar vd ON h.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      WHERE vd.nu_peso IS NOT NULL AND vd.nu_altura IS NOT NULL
        AND vd.co_dim_tempo >= {t_12m} AND vd.co_dim_tempo <= {t_end}
    ),
    pratica_c AS (
      SELECT DISTINCT co_fat_cidadao_pec FROM dias_peso_altura
    ),
    -- D (25pt): ≥2 visitas ACS/TACS (≥30 dias intervalo) nos últimos 12 meses
    pratica_d AS (
      SELECT vd.co_fat_cidadao_pec
      FROM hipertensos_por_equipe h
      JOIN tb_fat_visita_domiciliar vd ON h.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      JOIN cbo_acs_tacs ac ON vd.co_dim_cbo = ac.co_seq_dim_cbo
      WHERE vd.co_dim_tempo >= {t_12m} AND vd.co_dim_tempo <= {t_end}
      GROUP BY vd.co_fat_cidadao_pec
      HAVING COUNT(*) >= 2
        AND (MAX(vd.co_dim_tempo) - MIN(vd.co_dim_tempo)) >= 30
    ),
    agregado AS (
      SELECT h.unidade_saude, h.cnes, h.no_equipe, h.nu_ine,
        COUNT(DISTINCT h.co_fat_cidadao_pec) AS total_pessoas,
        COUNT(DISTINCT pa.co_fat_cidadao_pec) AS pratica_a,
        COUNT(DISTINCT pb.co_fat_cidadao_pec) AS pratica_b,
        COUNT(DISTINCT pc.co_fat_cidadao_pec) AS pratica_c,
        COUNT(DISTINCT pd.co_fat_cidadao_pec) AS pratica_d
      FROM hipertensos_por_equipe h
      LEFT JOIN pratica_a pa ON h.co_fat_cidadao_pec = pa.co_fat_cidadao_pec
      LEFT JOIN pratica_b pb ON h.co_fat_cidadao_pec = pb.co_fat_cidadao_pec
      LEFT JOIN pratica_c pc ON h.co_fat_cidadao_pec = pc.co_fat_cidadao_pec
      LEFT JOIN pratica_d pd ON h.co_fat_cidadao_pec = pd.co_fat_cidadao_pec
      GROUP BY h.unidade_saude, h.cnes, h.no_equipe, h.nu_ine
    )
    SELECT *,
      (pratica_a + pratica_b + pratica_c + pratica_d) AS soma_praticas,
      ROUND((pratica_a + pratica_b + pratica_c + pratica_d) * 100.0
        / NULLIF(total_pessoas * 4, 0), 2) AS percentual
    FROM agregado
    ORDER BY unidade_saude, no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 75: return "Ótimo"
        if v > 50: return "Bom"
        if v > 25: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    result = {"indicador": "C5", "descricao": "Cuidado da Pessoa com Hipertensão",
      "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}
    cache_set(ck, result)
    return result

# ========== C6 – Cuidado da Pessoa Idosa ==========
# NM 2024: 4 boas práticas (A–D), 25pts cada, total 100pts por pessoa idosa (≥ 60 anos)
@app.get("/api/indicadores/c6")
def get_c6(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    ck = cache_key("c6", unidade, inicio, fim)
    cached = cache_get(ck)
    if cached: return cached
    t_start, t_end = periodo_sql(inicio, fim)
    t_12m = int((datetime.strptime(str(t_end),"%Y%m%d") - timedelta(days=366)).strftime("%Y%m%d"))
    SQL = f"""
    WITH cbo_med_enf AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
    ),
    cbo_antropometria AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
         OR nu_cbo LIKE '3222%%' OR nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    cbo_acs_tacs AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo = '515105' OR nu_cbo = '322255'
    ),
    proc_peso AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0101040083','ABPG039','0101040024')
    ),
    proc_altura AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced IN ('0101040075','ABPG038','0101040024')
    ),
    -- Base: pessoas ≥ 60 anos vinculadas à equipe (via cadastro)
    idosos_por_equipe AS (
      SELECT DISTINCT c.co_seq_fat_cidadao_pec AS co_fat_cidadao_pec,
        du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
        te.no_equipe, te.nu_ine
      FROM tb_fat_cidadao_pec c
      LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
        AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
        AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
      LEFT JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
      WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND (c.st_deletar IS NULL OR c.st_deletar = 0)
        AND c.st_faleceu = 0
        AND ci.dt_nascimento IS NOT NULL
        AND ci.dt_nascimento <= CURRENT_DATE - INTERVAL '60 years'
    ),
    -- A (25pt): ≥1 consulta médica(o)/enfermeira(o) nos últimos 12 meses
    pratica_a AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM idosos_por_equipe d
      JOIN tb_fat_atendimento_individual a ON d.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.co_dim_tempo >= {t_12m} AND a.co_dim_tempo <= {t_end}
    ),
    -- B (25pt): ≥1 registro simultâneo peso+altura nos últimos 12 meses
    dias_peso_altura AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM idosos_por_equipe d
      JOIN tb_fat_atendimento_individual a ON d.co_fat_cidadao_pec = a.co_fat_cidadao_pec
      JOIN cbo_antropometria cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE a.nu_peso IS NOT NULL AND a.nu_altura IS NOT NULL
        AND a.co_dim_tempo >= {t_12m} AND a.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM idosos_por_equipe d
      JOIN tb_fat_atd_ind_procedimentos ap ON d.co_fat_cidadao_pec = ap.co_fat_cidadao_pec
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_peso)
        AND ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_altura)
        AND ap.co_dim_tempo >= {t_12m} AND ap.co_dim_tempo <= {t_end}
      UNION
      SELECT DISTINCT vd.co_fat_cidadao_pec
      FROM idosos_por_equipe d
      JOIN tb_fat_visita_domiciliar vd ON d.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      JOIN cbo_antropometria cb ON vd.co_dim_cbo = cb.co_seq_dim_cbo
      WHERE vd.nu_peso IS NOT NULL AND vd.nu_altura IS NOT NULL
        AND vd.co_dim_tempo >= {t_12m} AND vd.co_dim_tempo <= {t_end}
    ),
    pratica_b AS (
      SELECT DISTINCT co_fat_cidadao_pec FROM dias_peso_altura
    ),
    -- C (25pt): ≥2 visitas ACS/TACS (≥30 dias) nos últimos 12 meses
    pratica_c AS (
      SELECT vd.co_fat_cidadao_pec
      FROM idosos_por_equipe d
      JOIN tb_fat_visita_domiciliar vd ON d.co_fat_cidadao_pec = vd.co_fat_cidadao_pec
      JOIN cbo_acs_tacs ac ON vd.co_dim_cbo = ac.co_seq_dim_cbo
      WHERE vd.co_dim_tempo >= {t_12m} AND vd.co_dim_tempo <= {t_end}
      GROUP BY vd.co_fat_cidadao_pec
      HAVING COUNT(*) >= 2
        AND (MAX(vd.co_dim_tempo) - MIN(vd.co_dim_tempo)) >= 30
    ),
    -- D (25pt): ≥1 dose vacina influenza nos últimos 12 meses (códigos 33, 77)
    pratica_d AS (
      SELECT DISTINCT v.co_fat_cidadao_pec
      FROM idosos_por_equipe d
      JOIN tb_fat_vacinacao v ON d.co_fat_cidadao_pec = v.co_fat_cidadao_pec
      WHERE v.ds_filtro_imunobiologico ~ '\|(33|77)\|'
        AND v.co_dim_tempo >= {t_12m} AND v.co_dim_tempo <= {t_end}
    ),
    agregado AS (
      SELECT d.unidade_saude, d.cnes, d.no_equipe, d.nu_ine,
        COUNT(DISTINCT d.co_fat_cidadao_pec) AS total_pessoas,
        COUNT(DISTINCT pa.co_fat_cidadao_pec) AS pratica_a,
        COUNT(DISTINCT pb.co_fat_cidadao_pec) AS pratica_b,
        COUNT(DISTINCT pc.co_fat_cidadao_pec) AS pratica_c,
        COUNT(DISTINCT pd.co_fat_cidadao_pec) AS pratica_d
      FROM idosos_por_equipe d
      LEFT JOIN pratica_a pa ON d.co_fat_cidadao_pec = pa.co_fat_cidadao_pec
      LEFT JOIN pratica_b pb ON d.co_fat_cidadao_pec = pb.co_fat_cidadao_pec
      LEFT JOIN pratica_c pc ON d.co_fat_cidadao_pec = pc.co_fat_cidadao_pec
      LEFT JOIN pratica_d pd ON d.co_fat_cidadao_pec = pd.co_fat_cidadao_pec
      GROUP BY d.unidade_saude, d.cnes, d.no_equipe, d.nu_ine
    )
    SELECT *,
      (pratica_a + pratica_b + pratica_c + pratica_d) AS soma_praticas,
      ROUND((pratica_a + pratica_b + pratica_c + pratica_d) * 100.0
        / NULLIF(total_pessoas * 4, 0), 2) AS percentual
    FROM agregado
    ORDER BY unidade_saude, no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 75: return "Ótimo"
        if v > 50: return "Bom"
        if v > 25: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    result = {"indicador": "C6", "descricao": "Cuidado da Pessoa Idosa",
      "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}
    cache_set(ck, result)
    return result

# ========== C7 – Prevenção Câncer (Mulher) ==========
# NM 2024: 4 boas práticas com denominadores próprios por faixa etária
# A (20pt): colo do útero 25-64a, 36 meses; B (30pt): HPV 9-14a feminino
# C (30pt): saúde sexual/reprodutiva 14-69a, 12 meses; D (20pt): mama 50-69a, 24 meses
# Single-pass: pre-computa faixas etárias como flags, uma única agregação (sem FULL JOIN)
@app.get("/api/indicadores/c7")
def get_c7(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    ck = cache_key("c7", unidade, inicio, fim)
    cached = cache_get(ck)
    if cached: return cached
    t_start, t_end = periodo_sql(inicio, fim)
    t_end_date = datetime.strptime(str(t_end),"%Y%m%d")
    t_12m = int((t_end_date - timedelta(days=366)).strftime("%Y%m%d"))
    t_24m = int((t_end_date - timedelta(days=731)).strftime("%Y%m%d"))
    t_36m = int((t_end_date - timedelta(days=1096)).strftime("%Y%m%d"))
    t_end_s = t_end_date.strftime("%Y-%m-%d")
    # CID-10 e CIAP-2 para saúde sexual e reprodutiva (prática C)
    CID_C7_C = '|'.join([
        'N80[0-9]?','N91[0-5]?','N92[0-6]?','N93[089]?','N94[0-689]?',
        'N95[0-389]?','N96','N97[0-489]?','O0[34]','R102','T742',
        'Y05[0-9]','Z12[34]','Z20[56]','Z30[0-59]?','Z31[0-689]?',
        'Z320','Z600','Z630','Z640','Z70[0-389]?','Z717','Z725'
    ])
    CIAP_C7_C = 'B25|W02|W1[0-5]|W79|W82|X0[1-9]|X1[0-3]|X23|X24|X82|X89|Y14'
    SQL = f"""
    WITH cbo_med_enf AS (
      SELECT co_seq_dim_cbo FROM tb_dim_cbo
      WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
    ),
    proc_citopatologico AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento
      WHERE co_proced IN ('0201020033','0203010086','0203010019','0201020076','0201020084','ABEX001','ABP022')
    ),
    proc_mamografia AS (
      SELECT co_seq_dim_procedimento FROM tb_dim_procedimento
      WHERE co_proced IN ('0204030030','0204030188','ABP023')
    ),
    -- Base única: mulheres 9-69a com flags de faixa etária
    mulheres_9_69 AS (
      SELECT DISTINCT c.co_seq_fat_cidadao_pec AS co_fat_cidadao_pec,
        du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
        te.no_equipe, te.nu_ine,
        CASE WHEN ci.dt_nascimento <= '{t_end_s}'::DATE - INTERVAL '25 years'
              AND ci.dt_nascimento > '{t_end_s}'::DATE - INTERVAL '65 years' THEN 1 ELSE 0 END AS faixa_a,
        CASE WHEN ci.dt_nascimento <= '{t_end_s}'::DATE - INTERVAL '9 years'
              AND ci.dt_nascimento > '{t_end_s}'::DATE - INTERVAL '15 years' THEN 1 ELSE 0 END AS faixa_b,
        CASE WHEN ci.dt_nascimento <= '{t_end_s}'::DATE - INTERVAL '14 years'
              AND ci.dt_nascimento > '{t_end_s}'::DATE - INTERVAL '70 years' THEN 1 ELSE 0 END AS faixa_c,
        CASE WHEN ci.dt_nascimento <= '{t_end_s}'::DATE - INTERVAL '50 years'
              AND ci.dt_nascimento > '{t_end_s}'::DATE - INTERVAL '70 years' THEN 1 ELSE 0 END AS faixa_d
      FROM tb_fat_cidadao_pec c
      LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
        AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
        AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
      LEFT JOIN tb_dim_equipe te ON f.co_dim_equipe = te.co_seq_dim_equipe
      WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND (c.st_deletar IS NULL OR c.st_deletar = 0)
        AND c.st_faleceu = 0
        AND c.co_dim_sexo = 2
        AND ci.dt_nascimento IS NOT NULL
        AND ci.dt_nascimento <= '{t_end_s}'::DATE - INTERVAL '9 years'
        AND ci.dt_nascimento > '{t_end_s}'::DATE - INTERVAL '70 years'
    ),
    pratica_a AS (
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM tb_fat_atd_ind_procedimentos ap
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_citopatologico)
        AND ap.co_dim_tempo >= {t_36m} AND ap.co_dim_tempo <= {t_end}
    ),
    pratica_b AS (
      SELECT DISTINCT v.co_fat_cidadao_pec
      FROM tb_fat_vacinacao v
      WHERE v.ds_filtro_imunobiologico ~ '\|(67|93)\|'
        AND v.co_dim_tempo >= {t_start} AND v.co_dim_tempo <= {t_end}
    ),
    pratica_c AS (
      SELECT DISTINCT a.co_fat_cidadao_pec
      FROM tb_fat_atendimento_individual a
      JOIN cbo_med_enf cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
      WHERE (a.ds_filtro_cids ~ '{CID_C7_C}' OR a.ds_filtro_ciaps ~ '{CIAP_C7_C}')
        AND a.co_dim_tempo >= {t_12m} AND a.co_dim_tempo <= {t_end}
    ),
    pratica_d AS (
      SELECT DISTINCT ap.co_fat_cidadao_pec
      FROM tb_fat_atd_ind_procedimentos ap
      WHERE ap.co_dim_procedimento_avaliado IN (SELECT co_seq_dim_procedimento FROM proc_mamografia)
        AND ap.co_dim_tempo >= {t_24m} AND ap.co_dim_tempo <= {t_end}
    )
    SELECT m.unidade_saude, m.cnes, m.no_equipe, m.nu_ine,
      SUM(m.faixa_a) AS base_a,
      COUNT(DISTINCT CASE WHEN m.faixa_a = 1 THEN pa.co_fat_cidadao_pec END) AS pratica_a,
      SUM(m.faixa_b) AS base_b,
      COUNT(DISTINCT CASE WHEN m.faixa_b = 1 THEN pb.co_fat_cidadao_pec END) AS pratica_b,
      SUM(m.faixa_c) AS base_c,
      COUNT(DISTINCT CASE WHEN m.faixa_c = 1 THEN pc.co_fat_cidadao_pec END) AS pratica_c,
      SUM(m.faixa_d) AS base_d,
      COUNT(DISTINCT CASE WHEN m.faixa_d = 1 THEN pd.co_fat_cidadao_pec END) AS pratica_d,
      ROUND(
        COALESCE(COUNT(DISTINCT CASE WHEN m.faixa_a = 1 THEN pa.co_fat_cidadao_pec END)::numeric
          / NULLIF(SUM(m.faixa_a), 0), 0) * 20 +
        COALESCE(COUNT(DISTINCT CASE WHEN m.faixa_b = 1 THEN pb.co_fat_cidadao_pec END)::numeric
          / NULLIF(SUM(m.faixa_b), 0), 0) * 30 +
        COALESCE(COUNT(DISTINCT CASE WHEN m.faixa_c = 1 THEN pc.co_fat_cidadao_pec END)::numeric
          / NULLIF(SUM(m.faixa_c), 0), 0) * 30 +
        COALESCE(COUNT(DISTINCT CASE WHEN m.faixa_d = 1 THEN pd.co_fat_cidadao_pec END)::numeric
          / NULLIF(SUM(m.faixa_d), 0), 0) * 20
      , 2) AS percentual
    FROM mulheres_9_69 m
    LEFT JOIN pratica_a pa ON m.co_fat_cidadao_pec = pa.co_fat_cidadao_pec
    LEFT JOIN pratica_b pb ON m.co_fat_cidadao_pec = pb.co_fat_cidadao_pec
    LEFT JOIN pratica_c pc ON m.co_fat_cidadao_pec = pc.co_fat_cidadao_pec
    LEFT JOIN pratica_d pd ON m.co_fat_cidadao_pec = pd.co_fat_cidadao_pec
    GROUP BY m.unidade_saude, m.cnes, m.no_equipe, m.nu_ine
    ORDER BY m.unidade_saude, m.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 75: return "Ótimo"
        if v > 50: return "Bom"
        if v > 25: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    result = {"indicador": "C7", "descricao": "Cuidado da Mulher na Prevenção do Câncer",
      "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}
    cache_set(ck, result)
    return result

# ========== B2 – Tratamento Concluído ==========
@app.get("/api/indicadores/b2")
def get_b2(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    WITH primeira_consulta AS (
      SELECT a.co_dim_unidade_saude_1, a.co_dim_equipe_1,
        COUNT(DISTINCT a.co_fat_cidadao_pec) AS pessoas_1a_consulta
      FROM tb_fat_atend_odonto_proced a
      JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
      JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
      WHERE a.co_dim_cbo_1 IN {CBO_CD}
        AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND a.co_dim_procedimento IN (SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced = '0301010153')
        AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
      GROUP BY a.co_dim_unidade_saude_1, a.co_dim_equipe_1
    ),
    tratamento_concluido AS (
      SELECT a.co_dim_unidade_saude_1, a.co_dim_equipe_1,
        COUNT(DISTINCT a.co_fat_cidadao_pec) AS pessoas_tratamento_concluido
      FROM tb_fat_atendimento_odonto a
      WHERE a.co_dim_cbo_1 IN {CBO_CD}
        AND a.st_conduta_tratamento_concluid::int = 1
        AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
      GROUP BY a.co_dim_unidade_saude_1, a.co_dim_equipe_1
    )
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      COALESCE(pc.pessoas_1a_consulta, 0) AS pessoas_1a_consulta,
      COALESCE(tc.pessoas_tratamento_concluido, 0) AS pessoas_tratamento_concluido,
      CASE WHEN COALESCE(pc.pessoas_1a_consulta, 0) > 0
        THEN ROUND(100.0 * COALESCE(tc.pessoas_tratamento_concluido, 0) / pc.pessoas_1a_consulta, 2)
        ELSE 0
      END AS percentual
    FROM primeira_consulta pc
    LEFT JOIN tratamento_concluido tc
      ON pc.co_dim_unidade_saude_1 = tc.co_dim_unidade_saude_1
      AND pc.co_dim_equipe_1 = tc.co_dim_equipe_1
    JOIN tb_dim_unidade_saude du ON pc.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON pc.co_dim_equipe_1 = te.co_seq_dim_equipe
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end, t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 75: return "Ótimo"
        if v > 50: return "Bom"
        if v > 25: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    return {"indicador": "B2", "descricao": "Tratamento Odontológico Concluído", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}

# ========== B3 – Taxa de Exodontia ==========
@app.get("/api/indicadores/b3")
def get_b3(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    WITH proc_b3 AS (
      SELECT a.co_dim_unidade_saude_1, a.co_dim_equipe_1,
        COUNT(*) AS total_procedimentos,
        SUM(CASE WHEN dp.co_proced IN {B3_CODES_EXO} THEN 1 ELSE 0 END) AS exodontias
      FROM tb_fat_atend_odonto_proced a
      JOIN tb_dim_procedimento dp ON a.co_dim_procedimento = dp.co_seq_dim_procedimento
      JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
      JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
      WHERE a.co_dim_cbo_1 IN {CBO_CD_TSB}
        AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND dp.co_proced IN {B3_CODES_ALL}
        AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
      GROUP BY a.co_dim_unidade_saude_1, a.co_dim_equipe_1
    )
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      p.exodontias, p.total_procedimentos,
      ROUND(100.0 * p.exodontias / NULLIF(p.total_procedimentos, 0), 2) AS percentual
    FROM proc_b3 p
    JOIN tb_dim_unidade_saude du ON p.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON p.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE te.no_equipe IS NOT NULL AND te.no_equipe != '' AND te.no_equipe != 'SEM EQUIPE'
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v >= 3 and v < 10: return "Ótimo"
        if v >= 10 and v < 12: return "Bom"
        if v >= 12 and v < 14: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    return {"indicador": "B3", "descricao": "Taxa de Exodontias Realizadas", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}

# ========== B4 – Escovação Supervisionada ==========
@app.get("/api/indicadores/b4")
def get_b4(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    WITH populacao_ubs AS (
      SELECT f.co_dim_unidade_saude,
        COUNT(DISTINCT c.co_seq_fat_cidadao_pec) AS total_criancas
      FROM tb_fat_cidadao_pec c
      LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
      LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
        AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
        AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      WHERE f.co_dim_unidade_saude IN {DIM_UNIDADES}
        AND (c.st_deletar IS NULL OR c.st_deletar = 0)
        AND c.st_faleceu = 0
        AND ci.dt_nascimento IS NOT NULL
        AND EXTRACT(YEAR FROM AGE(CURRENT_DATE, ci.dt_nascimento)) BETWEEN 6 AND 12
      GROUP BY f.co_dim_unidade_saude
    ),
    escovacao AS (
      SELECT fa.co_dim_unidade_saude, fa.co_dim_equipe,
        SUM(fa.nu_participantes) AS total_participantes,
        COUNT(*) AS total_atividades
      FROM tb_atividade_coletiva ta
      JOIN rl_ativ_col_pratica_saude r ON ta.co_seq_atividade_coletiva = r.co_atividade_coletiva
      JOIN tb_fat_atividade_coletiva fa ON ta.co_unico_atividade_coletiva = fa.nu_uuid_ficha
      WHERE r.co_pratica_saude = 9
        AND fa.co_dim_cbo IN {CBO_CD_TSB_ASB}
        AND fa.co_dim_tempo >= %s AND fa.co_dim_tempo <= %s
      GROUP BY fa.co_dim_unidade_saude, fa.co_dim_equipe
    )
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      COALESCE(e.total_participantes, 0) AS total_participantes,
      COALESCE(e.total_atividades, 0) AS total_atividades,
      pu.total_criancas,
      CASE WHEN COALESCE(pu.total_criancas, 0) > 0
        THEN ROUND(100.0 * COALESCE(e.total_participantes, 0) / pu.total_criancas, 2)
        ELSE 0
      END AS percentual
    FROM escovacao e
    JOIN tb_dim_unidade_saude du ON e.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON e.co_dim_equipe = te.co_seq_dim_equipe
    LEFT JOIN populacao_ubs pu ON e.co_dim_unidade_saude = pu.co_dim_unidade_saude
    WHERE te.no_equipe IS NOT NULL AND te.no_equipe != '' AND te.no_equipe != 'SEM EQUIPE'
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 1: return "Ótimo"
        if v > 0.5: return "Bom"
        if v > 0.25: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    return {"indicador": "B4", "descricao": "Escovação Dentária Supervisionada", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}

# ========== B5 – Procedimentos Odontológicos Preventivos ==========
@app.get("/api/indicadores/b5")
def get_b5(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    WITH proc_b5 AS (
      SELECT a.co_dim_unidade_saude_1, a.co_dim_equipe_1,
        COUNT(*) AS total_procedimentos,
        SUM(CASE WHEN dp.co_proced IN {B5_PREVENTIVE} THEN 1 ELSE 0 END) AS preventivos
      FROM tb_fat_atend_odonto_proced a
      JOIN tb_dim_procedimento dp ON a.co_dim_procedimento = dp.co_seq_dim_procedimento
      JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
      WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
        AND (
          (a.co_dim_cbo_1 IN {CBO_CD} AND dp.co_proced IN {B5_DENOM})
          OR
          (a.co_dim_cbo_1 IN {CBO_TSB} AND dp.co_proced IN {B5_PREVENTIVE})
        )
      GROUP BY a.co_dim_unidade_saude_1, a.co_dim_equipe_1
    )
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      p.total_procedimentos, p.preventivos,
      ROUND(100.0 * p.preventivos / NULLIF(p.total_procedimentos, 0), 2) AS percentual
    FROM proc_b5 p
    JOIN tb_dim_unidade_saude du ON p.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON p.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE te.no_equipe IS NOT NULL AND te.no_equipe != '' AND te.no_equipe != 'SEM EQUIPE'
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v >= 65 and v <= 85: return "Ótimo"
        if v >= 55 and v < 65: return "Bom"
        if v >= 40 and v < 55: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    return {"indicador": "B5", "descricao": "Procedimentos Odontológicos Preventivos", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}

# ========== B6 – TRA/ART ==========
@app.get("/api/indicadores/b6")
def get_b6(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    WITH proc_b6 AS (
      SELECT a.co_dim_unidade_saude_1, a.co_dim_equipe_1,
        COUNT(*) AS total_restauradores,
        SUM(CASE WHEN dp.co_proced IN {B6_TRA_ART_STR} THEN 1 ELSE 0 END) AS tra_art
      FROM tb_fat_atend_odonto_proced a
      JOIN tb_dim_procedimento dp ON a.co_dim_procedimento = dp.co_seq_dim_procedimento
      JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
      WHERE a.co_dim_cbo_1 IN {CBO_CD}
        AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
        AND dp.co_proced IN {B6_DENOM}
        AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
      GROUP BY a.co_dim_unidade_saude_1, a.co_dim_equipe_1
    )
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      p.total_restauradores, p.tra_art,
      CASE WHEN COALESCE(p.total_restauradores, 0) > 0
        THEN ROUND(100.0 * p.tra_art / p.total_restauradores, 2)
        ELSE 0
      END AS percentual
    FROM proc_b6 p
    JOIN tb_dim_unidade_saude du ON p.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON p.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE te.no_equipe IS NOT NULL AND te.no_equipe != '' AND te.no_equipe != 'SEM EQUIPE'
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 8: return "Ótimo"
        if v > 6: return "Bom"
        if v > 3: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("percentual"))
    return {"indicador": "B6", "descricao": "Tratamento Restaurador Atraumático (TRA/ART)", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}

# ========== M2 – Ações Interprofissionais eMulti ==========
@app.get("/api/indicadores/m2")
def get_m2(unidade: str = Query(None), inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    SQL = f"""
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      COUNT(DISTINCT a.co_fat_cidadao_pec) AS pessoas_atendidas,
      COUNT(*) AS total_acoes,
      ROUND(1.0 * COUNT(*) / NULLIF(COUNT(DISTINCT a.co_fat_cidadao_pec),0), 2) AS media_acoes_por_pessoa
    FROM tb_fat_atendimento_individual a
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE a.co_dim_cbo_1 IN {CBO_EMULTI}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
    GROUP BY du.no_unidade_saude, du.nu_cnes, te.no_equipe, te.nu_ine
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """
    rows = executar_indicador(SQL, (t_start, t_end), unidade)
    def classif(v):
        if v is None: return "Sem dados"
        if v > 3: return "Ótimo"
        if v >= 2: return "Bom"
        if v >= 1: return "Suficiente"
        return "Regular"
    for r in rows:
        r["classificacao"] = classif(r.get("media_acoes_por_pessoa"))
    return {"indicador": "M2", "descricao": "Ações Interprofissionais realizadas pela eMulti", "ubs": rows,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}

# ========== Dashboard municipal (updated) ==========
@app.get("/api/indicadores/municipio")
def get_dashboard_municipio(inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)

    SQL_C1 = f"""
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      COUNT(*) AS total_atendimentos,
      SUM(CASE WHEN a.co_dim_tipo_atendimento IN {TIPO_PROG} THEN 1 ELSE 0 END) AS programada
    FROM tb_fat_atendimento_individual a
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE a.co_dim_cbo_1 IN {CBO_MED_ENF}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
    GROUP BY du.no_unidade_saude, du.nu_cnes, te.no_equipe, te.nu_ine
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """

    SQL_B1 = f"""
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      COUNT(DISTINCT a.co_fat_cidadao_pec) AS pessoas_1a_consulta
    FROM tb_fat_atend_odonto_proced a
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE a.co_dim_cbo_1 IN {CBO_CD}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_procedimento IN (SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced = '0301010153')
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
    GROUP BY du.no_unidade_saude, du.nu_cnes, te.no_equipe, te.nu_ine
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """

    SQL_M1 = f"""
    SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
      te.no_equipe, te.nu_ine,
      COUNT(a.co_seq_fat_atd_ind) AS total_atendimentos,
      COUNT(DISTINCT a.co_fat_cidadao_pec) AS pessoas_atendidas
    FROM tb_fat_atendimento_individual a
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    WHERE a.co_dim_cbo_1 IN {CBO_EMULTI}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
    GROUP BY du.no_unidade_saude, du.nu_cnes, te.no_equipe, te.nu_ine
    ORDER BY du.no_unidade_saude, te.no_equipe;
    """

    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_C1, (t_start, t_end))
            c1_equipes = [fmt_row(r) for r in cur.fetchall()]
            cur.execute(SQL_B1, (t_start, t_end))
            b1_equipes = [fmt_row(r) for r in cur.fetchall()]
            cur.execute(SQL_M1, (t_start, t_end))
            m1_equipes = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("Erro no dashboard: %s", e)
        raise HTTPException(500, "Erro ao calcular dashboard")

    c1_ubs = agregar_por_unidade(c1_equipes)
    b1_ubs = agregar_por_unidade(b1_equipes)
    m1_ubs = agregar_por_unidade(m1_equipes)

    for i, r in enumerate(m1_ubs):
        pa = r.get("pessoas_atendidas", 0) or 0
        ta = r.get("total_atendimentos", 0) or 0
        m1_ubs[i]["media_atend_por_pessoa"] = round(1.0 * ta / pa, 2) if pa else 0

    def media(vals, key):
        vals = [r[key] for r in vals if r.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0

    def classif_c1(v):
        if v is None: return "Sem dados"
        if v > 70 or v < 10: return "Regular"
        if v >= 50: return "Ótimo"
        if v >= 30: return "Bom"
        return "Suficiente"

    def classif_m1(v):
        if v is None: return "Sem dados"
        if v > 3: return "Ótimo"
        if v >= 2: return "Bom"
        if v >= 1: return "Suficiente"
        return "Regular"

    c1_media = media(c1_ubs, "perc_programada")
    b1_total = sum(r.get("pessoas_1a_consulta", 0) for r in b1_ubs)
    m1_media = media(m1_ubs, "media_atend_por_pessoa")

    return {
        "competencia": f"{t_start}-{t_end}",
        "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"), "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")},
        "c1": {"media_municipal": c1_media, "classificacao": classif_c1(c1_media), "ubs": c1_ubs},
        "b1": {"total_municipal": b1_total, "ubs": b1_ubs},
        "m1": {"media_municipal": m1_media, "classificacao": classif_m1(m1_media), "ubs": m1_ubs},
    }


# =====================================================================
# Busca Ativa — pacientes que precisam de atendimento
# =====================================================================

def gap_para_nivel_C1(perc_atual, total, programada, alvo):
    """Quantas consultas programadas a mais são necessárias para atingir `alvo`%?
    Fórmula: (P + X) / (T + X) >= alvo/100  =>  X >= (alvo*T - P) / (1 - alvo)
    """
    if perc_atual is None or total is None or total == 0:
        return None
    if perc_atual >= alvo:
        return 0
    t = alvo / 100.0
    x = (t * total - programada) / (1.0 - t)
    return max(0, math.ceil(x))


def gap_reverter_C1(perc_atual, total, programada, alvo_superior):
    """Quando perc > 70%, precisa de mais espontâneas para voltar ao alvo.
    (P) / (T + X) <= alvo_superior/100  =>  X >= P / (alvo/100) - T
    """
    if perc_atual is None or total is None or total == 0:
        return None
    if perc_atual <= alvo_superior:
        return 0
    t = alvo_superior / 100.0
    x = programada / t - total
    return max(0, math.ceil(x))


NIVEIS_C1 = [
    ("Ótimo",    50, 70),
    ("Bom",      30, 50),
    ("Suficiente", 10, 30),
    ("Regular",   0, 10),
]
# Para >70% o inverso: precisa de mais espontâneas
NIVEIS_C1_REVERSO = [
    ("Ótimo",    50, 70),
    ("Bom",      30, 50),
    ("Suficiente", 10, 30),
    ("Regular",   0, 10),
]


def analisar_gap_c1(perc_atual, total, programada):
    """Retorna dict com análise de gap para C1."""
    result = {"atual": perc_atual, "classificacao": "Sem dados", "gaps": []}
    if perc_atual is None:
        return result

    perc = perc_atual
    # Classifica atual
    if perc > 70 or perc <= 10:
        result["classificacao"] = "Regular"
    elif perc >= 50:
        result["classificacao"] = "Ótimo"
    elif perc >= 30:
        result["classificacao"] = "Bom"
    else:
        result["classificacao"] = "Suficiente"

    if result["classificacao"] == "Ótimo":
        result["gaps"].append({"nivel": "Ótimo (já atingido)", "faltam": 0, "tipo": "—"})
        return result

    if perc > 70:
        # Precisa de mais espontâneas
        for nome, lim_inf, lim_sup in NIVEIS_C1:
            if lim_inf <= perc <= lim_sup:
                # já está neste nível, pula
                continue
            if lim_sup < 70:
                continue
            faltam = gap_reverter_C1(perc, total, programada, lim_sup)
            result["gaps"].append({
                "nivel": nome,
                "meta": f"≤{lim_sup}%",
                "faltam": faltam,
                "tipo": "consultas espontâneas",
            })
            break
        # Sempre mostra o ótimo
        faltam_otimo = gap_reverter_C1(perc, total, programada, 70)
        if faltam_otimo is not None and faltam_otimo > 0:
            result["gaps"].append({
                "nivel": "Ótimo",
                "meta": "≤70%",
                "faltam": faltam_otimo,
                "tipo": "consultas espontâneas",
            })
    elif perc < 50:
        # Precisa de mais programadas — mostra todos os níveis acima
        niveis_acima = [n for n in NIVEIS_C1 if n[0] in ("Bom", "Ótimo")]
        for nome, lim_inf, lim_sup in niveis_acima:
            if perc >= lim_inf:
                continue
            faltam = gap_para_nivel_C1(perc, total, programada, lim_inf)
            if faltam is not None and faltam > 0:
                result["gaps"].append({
                    "nivel": nome,
                    "meta": f"≥{lim_inf}%",
                    "faltam": faltam,
                    "tipo": "consultas programadas",
                })

    return result


# ----- SQLs de Busca Ativa -----

SQL_BA_C1 = f"""
WITH pacientes_foco AS (
    SELECT DISTINCT a.co_fat_cidadao_pec
    FROM tb_fat_atendimento_individual a
    WHERE a.co_dim_cbo_1 IN {CBO_MED_ENF}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
    EXCEPT
    SELECT DISTINCT a.co_fat_cidadao_pec
    FROM tb_fat_atendimento_individual a
    WHERE a.co_dim_cbo_1 IN {CBO_MED_ENF}
      AND a.co_dim_tipo_atendimento IN {TIPO_PROG}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
)
SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
  te.no_equipe, te.nu_ine,
  c.no_cidadao AS nome, COALESCE(c.nu_cns,'') AS cns,
  COALESCE(c.nu_cpf_cidadao,'') AS cpf,
  COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
  COUNT(*) AS total_consultas_no_periodo
FROM pacientes_foco pf
JOIN tb_fat_atendimento_individual a ON a.co_fat_cidadao_pec = pf.co_fat_cidadao_pec
JOIN tb_fat_cidadao_pec c ON pf.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
WHERE a.co_dim_cbo_1 IN {CBO_MED_ENF}
  AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
  AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
GROUP BY du.no_unidade_saude, du.nu_cnes, te.no_equipe, te.nu_ine,
  c.no_cidadao, c.nu_cns, c.nu_cpf_cidadao, ci.dt_nascimento
ORDER BY du.no_unidade_saude, te.no_equipe, c.no_cidadao;
"""

SQL_BA_C6 = f"""
WITH cbo_med_enf AS (
    SELECT co_seq_dim_cbo FROM tb_dim_cbo
    WHERE nu_cbo LIKE '2235%%' OR nu_cbo LIKE '2231%%' OR nu_cbo LIKE '2251%%' OR nu_cbo LIKE '2252%%' OR nu_cbo LIKE '2253%%'
),
idosos_area AS (
    SELECT DISTINCT c.co_seq_fat_cidadao_pec, c.no_cidadao AS nome,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes
    FROM tb_fat_cidadao_pec c
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
      AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND (c.st_deletar IS NULL OR c.st_deletar = 0)
      AND c.st_faleceu = 0
      AND ci.dt_nascimento IS NOT NULL
      AND ci.dt_nascimento <= CURRENT_DATE - INTERVAL '60 years'
)
SELECT i.*
FROM idosos_area i
WHERE NOT EXISTS (
    SELECT 1 FROM tb_fat_atendimento_individual a
    WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec
      AND a.co_dim_cbo_1 IN (SELECT co_seq_dim_cbo FROM cbo_med_enf)
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
)
ORDER BY i.unidade_saude, i.nome;
"""

SQL_BA_C7 = f"""
WITH mulheres_area AS (
    SELECT DISTINCT c.co_seq_fat_cidadao_pec, c.no_cidadao AS nome,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes
    FROM tb_fat_cidadao_pec c
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
      AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND (c.st_deletar IS NULL OR c.st_deletar = 0)
      AND c.st_faleceu = 0
      AND ci.dt_nascimento IS NOT NULL
      AND c.co_dim_sexo = 2
      AND ci.dt_nascimento <= CURRENT_DATE - INTERVAL '9 years'
)
SELECT i.*
FROM mulheres_area i
WHERE NOT EXISTS (
    SELECT 1 FROM tb_fat_atendimento_individual a
    WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec
      AND a.co_dim_cbo_1 IN {CBO_MED_ENF}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
)
ORDER BY i.unidade_saude, i.nome;
"""

SQL_BA_B1 = f"""
WITH pacientes_sem_consulta_odonto AS (
    SELECT DISTINCT c.co_seq_fat_cidadao_pec, c.no_cidadao,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes
    FROM tb_fat_cidadao_pec c
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
      AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND (c.st_deletar IS NULL OR c.st_deletar = 0)
      AND c.st_faleceu = 0
    EXCEPT
    SELECT DISTINCT c2.co_seq_fat_cidadao_pec, c2.no_cidadao,
      COALESCE(c2.nu_cns,'') AS cns, COALESCE(c2.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci2.dt_nascimento::TEXT,'') AS data_nascimento,
      du2.no_unidade_saude AS unidade_saude, du2.nu_cnes
    FROM tb_fat_atend_odonto_proced a
    JOIN tb_fat_cidadao_pec c2 ON a.co_fat_cidadao_pec = c2.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci2 ON ci2.co_fat_cidadao_pec = c2.co_seq_fat_cidadao_pec
    JOIN tb_dim_unidade_saude du2 ON a.co_dim_unidade_saude_1 = du2.co_seq_dim_unidade_saude
    WHERE a.co_dim_cbo_1 IN {CBO_CD}
      AND du2.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
)
SELECT * FROM pacientes_sem_consulta_odonto
ORDER BY unidade_saude, no_cidadao;
"""

SQL_BA_B2 = f"""
WITH pacientes_primeira_cdn AS (
    SELECT DISTINCT a.co_fat_cidadao_pec, c.no_cidadao,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes
    FROM tb_fat_atend_odonto_proced a
    JOIN tb_fat_cidadao_pec c ON a.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    WHERE a.co_dim_cbo_1 IN {CBO_CD}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_procedimento IN (SELECT co_seq_dim_procedimento FROM tb_dim_procedimento WHERE co_proced = '0301010153')
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
    EXCEPT
    SELECT DISTINCT a2.co_fat_cidadao_pec, c2.no_cidadao,
      COALESCE(c2.nu_cns,'') AS cns, COALESCE(c2.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci2.dt_nascimento::TEXT,'') AS data_nascimento,
      du2.no_unidade_saude AS unidade_saude, du2.nu_cnes
    FROM tb_fat_atendimento_odonto a2
    JOIN tb_fat_cidadao_pec c2 ON a2.co_fat_cidadao_pec = c2.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci2 ON ci2.co_fat_cidadao_pec = c2.co_seq_fat_cidadao_pec
    JOIN tb_dim_unidade_saude du2 ON a2.co_dim_unidade_saude_1 = du2.co_seq_dim_unidade_saude
    WHERE a2.co_dim_cbo_1 IN {CBO_CD}
      AND du2.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a2.st_conduta_tratamento_concluid::int = 1
      AND a2.co_dim_tempo >= %s AND a2.co_dim_tempo <= %s
)
SELECT * FROM pacientes_primeira_cdn
ORDER BY unidade_saude, no_cidadao;
"""

SQL_BA_B3 = f"""
WITH pacientes_exodontia AS (
    SELECT DISTINCT a.co_fat_cidadao_pec, c.no_cidadao,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes,
      COUNT(*) AS total_procedimentos,
      SUM(CASE WHEN dp.co_proced IN {B3_CODES_EXO} THEN 1 ELSE 0 END) AS exodontias,
      SUM(CASE WHEN dp.co_proced NOT IN {B3_CODES_EXO} THEN 1 ELSE 0 END) AS preventivos_curativos
    FROM tb_fat_atend_odonto_proced a
    JOIN tb_fat_cidadao_pec c ON a.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    JOIN tb_dim_procedimento dp ON a.co_dim_procedimento = dp.co_seq_dim_procedimento
    WHERE a.co_dim_cbo_1 IN {CBO_CD_TSB}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND dp.co_proced IN {B3_CODES_ALL}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
      AND te.no_equipe IS NOT NULL AND te.no_equipe != '' AND te.no_equipe != 'SEM EQUIPE'
    GROUP BY a.co_fat_cidadao_pec, c.no_cidadao, c.nu_cns, c.nu_cpf_cidadao,
      ci.dt_nascimento, du.no_unidade_saude, du.nu_cnes
    HAVING SUM(CASE WHEN dp.co_proced IN {B3_CODES_EXO} THEN 1 ELSE 0 END) > 0
)
SELECT co_fat_cidadao_pec AS paciente_id, no_cidadao AS nome,
  cns, cpf, data_nascimento, unidade_saude, nu_cnes,
  exodontias, preventivos_curativos, total_procedimentos
FROM pacientes_exodontia
ORDER BY unidade_saude, nome;
"""

SQL_BA_B5 = f"""
WITH pacientes_denominador AS (
    SELECT DISTINCT a.co_fat_cidadao_pec, c.no_cidadao,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes,
      te.no_equipe
    FROM tb_fat_atend_odonto_proced a
    JOIN tb_fat_cidadao_pec c ON a.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    JOIN tb_dim_procedimento dp ON a.co_dim_procedimento = dp.co_seq_dim_procedimento
    WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
      AND te.no_equipe IS NOT NULL AND te.no_equipe != '' AND te.no_equipe != 'SEM EQUIPE'
      AND (
        (a.co_dim_cbo_1 IN {CBO_CD} AND dp.co_proced IN {B5_DENOM})
        OR
        (a.co_dim_cbo_1 IN {CBO_TSB} AND dp.co_proced IN {B5_PREVENTIVE})
      )
    EXCEPT
    SELECT DISTINCT a2.co_fat_cidadao_pec, c2.no_cidadao,
      COALESCE(c2.nu_cns,'') AS cns, COALESCE(c2.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci2.dt_nascimento::TEXT,'') AS data_nascimento,
      du2.no_unidade_saude AS unidade_saude, du2.nu_cnes,
      te2.no_equipe
    FROM tb_fat_atend_odonto_proced a2
    JOIN tb_fat_cidadao_pec c2 ON a2.co_fat_cidadao_pec = c2.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci2 ON ci2.co_fat_cidadao_pec = c2.co_seq_fat_cidadao_pec
    JOIN tb_dim_unidade_saude du2 ON a2.co_dim_unidade_saude_1 = du2.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te2 ON a2.co_dim_equipe_1 = te2.co_seq_dim_equipe
    JOIN tb_dim_procedimento dp2 ON a2.co_dim_procedimento = dp2.co_seq_dim_procedimento
    WHERE a2.co_dim_cbo_1 IN {CBO_CD_TSB}
      AND du2.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND dp2.co_proced IN {B5_PREVENTIVE}
      AND a2.co_dim_tempo >= %s AND a2.co_dim_tempo <= %s
      AND te2.no_equipe IS NOT NULL AND te2.no_equipe != '' AND te2.no_equipe != 'SEM EQUIPE'
)
SELECT co_fat_cidadao_pec AS paciente_id, no_cidadao AS nome,
  cns, cpf, data_nascimento, unidade_saude, nu_cnes,
  no_equipe
FROM pacientes_denominador
ORDER BY unidade_saude, nome;
"""

SQL_BA_B6 = f"""
WITH pacientes_restauradores AS (
    SELECT DISTINCT a.co_fat_cidadao_pec, c.no_cidadao,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes,
      te.no_equipe
    FROM tb_fat_atend_odonto_proced a
    JOIN tb_fat_cidadao_pec c ON a.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
    JOIN tb_dim_procedimento dp ON a.co_dim_procedimento = dp.co_seq_dim_procedimento
    WHERE a.co_dim_cbo_1 IN {CBO_CD}
      AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND dp.co_proced IN {B6_DENOM}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
      AND te.no_equipe IS NOT NULL AND te.no_equipe != '' AND te.no_equipe != 'SEM EQUIPE'
    EXCEPT
    SELECT DISTINCT a2.co_fat_cidadao_pec, c2.no_cidadao,
      COALESCE(c2.nu_cns,'') AS cns, COALESCE(c2.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci2.dt_nascimento::TEXT,'') AS data_nascimento,
      du2.no_unidade_saude AS unidade_saude, du2.nu_cnes,
      te2.no_equipe
    FROM tb_fat_atend_odonto_proced a2
    JOIN tb_fat_cidadao_pec c2 ON a2.co_fat_cidadao_pec = c2.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci2 ON ci2.co_fat_cidadao_pec = c2.co_seq_fat_cidadao_pec
    JOIN tb_dim_unidade_saude du2 ON a2.co_dim_unidade_saude_1 = du2.co_seq_dim_unidade_saude
    JOIN tb_dim_equipe te2 ON a2.co_dim_equipe_1 = te2.co_seq_dim_equipe
    JOIN tb_dim_procedimento dp2 ON a2.co_dim_procedimento = dp2.co_seq_dim_procedimento
    WHERE a2.co_dim_cbo_1 IN {CBO_CD}
      AND du2.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND dp2.co_proced IN {B6_TRA_ART_STR}
      AND a2.co_dim_tempo >= %s AND a2.co_dim_tempo <= %s
      AND te2.no_equipe IS NOT NULL AND te2.no_equipe != '' AND te2.no_equipe != 'SEM EQUIPE'
)
SELECT co_fat_cidadao_pec AS paciente_id, no_cidadao AS nome,
  cns, cpf, data_nascimento, unidade_saude, nu_cnes,
  no_equipe
FROM pacientes_restauradores
ORDER BY unidade_saude, nome;
"""

SQL_BA_C2 = f"""
WITH criancas_area AS (
    SELECT DISTINCT c.co_seq_fat_cidadao_pec, c.no_cidadao,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes
    FROM tb_fat_cidadao_pec c
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
      AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND (c.st_deletar IS NULL OR c.st_deletar = 0)
      AND c.st_faleceu = 0
      AND ci.dt_nascimento IS NOT NULL
      AND EXTRACT(YEAR FROM AGE(CURRENT_DATE, ci.dt_nascimento)) <= 2
)
SELECT i.*
FROM criancas_area i
WHERE NOT EXISTS (
    SELECT 1 FROM tb_fat_atendimento_individual a
    WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec
      AND a.co_dim_cbo_1 IN {CBO_MED_ENF}
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
)
ORDER BY i.unidade_saude, i.no_cidadao;
"""


def executar_busca_ativa(sql, params, unidade=None, equipe=None):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = [fmt_row(r) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        conn.close()
        raise e
    if unidade:
        rows = [r for r in rows if unidade.lower() in r.get("unidade_saude","").lower()]
    if equipe:
        rows = [r for r in rows if r.get("no_equipe") == equipe]
    return rows


@app.get("/api/busca-ativa/c1")
def get_ba_c1(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_C1,
          (t_start, t_end, t_start, t_end, t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa C1: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para C1")

    # Agrupa por equipe + agrega gap
    eq_map = defaultdict(lambda: {"pacientes": [], "total": 0, "programada": 0})
    for p in pacientes:
        key = (p["unidade_saude"], p["cnes"], p.get("no_equipe",""), p.get("nu_ine",""))
        eq_map[key]["pacientes"].append(p)
        eq_map[key]["total"] += p.get("total_consultas_no_periodo", 0) or 0

    # Pega indicador atual por equipe
    try:
        rows_c1 = executar_indicador(f"""
          SELECT du.no_unidade_saude AS unidade_saude, du.nu_cnes AS cnes,
            te.no_equipe, te.nu_ine,
            COUNT(*) AS total_atendimentos,
            SUM(CASE WHEN a.co_dim_tipo_atendimento IN {TIPO_PROG} THEN 1 ELSE 0 END) AS programada
          FROM tb_fat_atendimento_individual a
          JOIN tb_dim_unidade_saude du ON a.co_dim_unidade_saude_1 = du.co_seq_dim_unidade_saude
          JOIN tb_dim_equipe te ON a.co_dim_equipe_1 = te.co_seq_dim_equipe
          WHERE a.co_dim_cbo_1 IN {CBO_MED_ENF}
            AND du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
            AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
          GROUP BY du.no_unidade_saude, du.nu_cnes, te.no_equipe, te.nu_ine
          ORDER BY du.no_unidade_saude, te.no_equipe;
        """, (t_start, t_end), unidade)
    except Exception as e:
        log.error("Erro ao buscar indicador C1 p/ gap: %s", e)
        rows_c1 = []

    resumo = []
    for r in rows_c1:
        perc = r.get("perc_programada") or (
            round(100.0 * (r["programada"] or 0) / (r["total_atendimentos"] or 1), 2)
            if r.get("total_atendimentos") else 0
        )
        total = r.get("total_atendimentos", 0) or 0
        prog = r.get("programada", 0) or 0
        gap = analisar_gap_c1(perc, total, prog)
        key = (r["unidade_saude"], r["cnes"], r.get("no_equipe",""), r.get("nu_ine",""))
        eq_pacientes = eq_map.get(key, {}).get("pacientes", [])
        resumo.append({
            "unidade_saude": r["unidade_saude"],
            "cnes": r["cnes"],
            "no_equipe": r.get("no_equipe",""),
            "nu_ine": r.get("nu_ine",""),
            "atual": {"valor": perc, "classificacao": gap["classificacao"]},
            "gaps": gap["gaps"],
            "total_pacientes_para_busca": len(eq_pacientes),
            "pacientes": eq_pacientes,
        })

    return {"indicador": "c1", "descricao": "Busca Ativa — Mais Acesso",
      "resumo": resumo,
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")},
      "total_pacientes_identificados": len(pacientes)}


@app.get("/api/busca-ativa/c6")
def get_ba_c6(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_C6, (t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa C6: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para C6")

    return {"indicador": "c6", "descricao": "Busca Ativa — Pessoa Idosa",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/busca-ativa/c7")
def get_ba_c7(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_C7, (t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa C7: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para C7")

    return {"indicador": "c7", "descricao": "Busca Ativa — Prevenção do Câncer",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/busca-ativa/b1")
def get_ba_b1(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_B1, (t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa B1: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para B1")

    return {"indicador": "b1", "descricao": "Busca Ativa — 1ª Consulta Odontológica",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/busca-ativa/b2")
def get_ba_b2(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_B2, (t_start, t_end, t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa B2: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para B2")

    return {"indicador": "b2", "descricao": "Busca Ativa — Tratamento Concluído",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/busca-ativa/b3")
def get_ba_b3(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_B3, (t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa B3: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para B3")

    return {"indicador": "b3", "descricao": "Busca Ativa — Exodontia",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/busca-ativa/b5")
def get_ba_b5(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_B5, (t_start, t_end, t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa B5: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para B5")

    return {"indicador": "b5", "descricao": "Busca Ativa — Procedimentos Preventivos",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/busca-ativa/b6")
def get_ba_b6(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_B6, (t_start, t_end, t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa B6: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para B6")

    return {"indicador": "b6", "descricao": "Busca Ativa — TRA/ART",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/busca-ativa/c2")
def get_ba_c2(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_C2, (t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa C2: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para C2")

    return {"indicador": "c2", "descricao": "Busca Ativa — Desenvolvimento Infantil",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


SQL_BA_C3 = f"""
WITH gestantes_area AS (
    SELECT DISTINCT c.co_seq_fat_cidadao_pec, c.no_cidadao AS nome,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes
    FROM tb_fat_rel_op_gestante g
    JOIN tb_fat_cidadao_pec c ON g.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
      AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND (c.st_deletar IS NULL OR c.st_deletar = 0)
      AND c.st_faleceu = 0
      AND ci.dt_nascimento IS NOT NULL
      AND g.dt_inicio_gestacao IS NOT NULL
      AND TO_CHAR(g.dt_inicio_gestacao,'YYYYMMDD')::INTEGER <= %s
      AND (g.dt_fim_puerperio IS NULL
           OR TO_CHAR(g.dt_fim_puerperio,'YYYYMMDD')::INTEGER >= %s)
)
SELECT i.*
FROM gestantes_area i
WHERE NOT EXISTS (
    SELECT 1 FROM tb_fat_atendimento_individual a
    JOIN tb_dim_cbo cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
    WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec
      AND (cb.nu_cbo LIKE '2235%%' OR cb.nu_cbo LIKE '225%%' OR cb.nu_cbo LIKE '2231%%')
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
)
ORDER BY i.unidade_saude, i.nome;
"""


@app.get("/api/busca-ativa/c3")
def get_ba_c3(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_C3,
          (t_end, t_start, t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa C3: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para C3")

    return {"indicador": "c3", "descricao": "Busca Ativa — Gestantes sem consulta no período",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


SQL_BA_C4 = f"""
WITH diabeticos_area AS (
    SELECT DISTINCT c.co_seq_fat_cidadao_pec, c.no_cidadao AS nome,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes
    FROM tb_fat_atendimento_individual a
    JOIN tb_fat_cidadao_pec c ON a.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
      AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND (a.ds_filtro_cids ~ 'E10|E11|E14' OR a.ds_filtro_ciaps ~ 'T89|T90')
      AND a.co_dim_tempo >= 20130101
      AND (c.st_deletar IS NULL OR c.st_deletar = 0)
      AND c.st_faleceu = 0
)
SELECT DISTINCT i.*
FROM diabeticos_area i
WHERE NOT EXISTS (
    SELECT 1 FROM tb_fat_atendimento_individual a
    JOIN tb_dim_cbo cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
    WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec
      AND (cb.nu_cbo LIKE '2235%%' OR cb.nu_cbo LIKE '225%%' OR cb.nu_cbo LIKE '2231%%')
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
)
ORDER BY i.unidade_saude, i.nome;
"""

@app.get("/api/busca-ativa/c4")
def get_ba_c4(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_C4, (t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa C4: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para C4")
    return {"indicador": "c4", "descricao": "Busca Ativa — Diabéticos sem consulta no período",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


SQL_BA_C5 = f"""
WITH hipertensos_area AS (
    SELECT DISTINCT c.co_seq_fat_cidadao_pec, c.no_cidadao AS nome,
      COALESCE(c.nu_cns,'') AS cns, COALESCE(c.nu_cpf_cidadao,'') AS cpf,
      COALESCE(ci.dt_nascimento::TEXT,'') AS data_nascimento,
      du.no_unidade_saude AS unidade_saude, du.nu_cnes
    FROM tb_fat_atendimento_individual a
    JOIN tb_fat_cidadao_pec c ON a.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cad_individual ci ON ci.co_fat_cidadao_pec = c.co_seq_fat_cidadao_pec
    LEFT JOIN tb_fat_cidadao f ON f.co_fat_cad_individual = ci.co_seq_fat_cad_individual
      AND f.co_dim_tempo_valdd_unidd_saud > TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
      AND f.co_dim_tempo <= TO_CHAR(CURRENT_DATE,'YYYYMMDD')::INTEGER
    LEFT JOIN tb_dim_unidade_saude du ON f.co_dim_unidade_saude = du.co_seq_dim_unidade_saude
    WHERE du.co_seq_dim_unidade_saude IN {DIM_UNIDADES}
      AND (a.ds_filtro_cids ~ 'I10|I11|I12|I13|I15|O10|O11' OR a.ds_filtro_ciaps ~ 'K86|K87')
      AND a.co_dim_tempo >= 20130101
      AND (c.st_deletar IS NULL OR c.st_deletar = 0)
      AND c.st_faleceu = 0
)
SELECT DISTINCT i.*
FROM hipertensos_area i
WHERE NOT EXISTS (
    SELECT 1 FROM tb_fat_atendimento_individual a
    JOIN tb_dim_cbo cb ON a.co_dim_cbo_1 = cb.co_seq_dim_cbo
    WHERE a.co_fat_cidadao_pec = i.co_seq_fat_cidadao_pec
      AND (cb.nu_cbo LIKE '2235%%' OR cb.nu_cbo LIKE '225%%' OR cb.nu_cbo LIKE '2231%%')
      AND a.co_dim_tempo >= %s AND a.co_dim_tempo <= %s
)
ORDER BY i.unidade_saude, i.nome;
"""

@app.get("/api/busca-ativa/c5")
def get_ba_c5(unidade: str = Query(None), equipe: str = Query(None),
              inicio: str = Query(None), fim: str = Query(None)):
    t_start, t_end = periodo_sql(inicio, fim)
    try:
        pacientes = executar_busca_ativa(SQL_BA_C5, (t_start, t_end), unidade, equipe)
    except Exception as e:
        log.error("Erro busca ativa C5: %s", e)
        raise HTTPException(500, "Erro ao buscar pacientes para C5")
    return {"indicador": "c5", "descricao": "Busca Ativa — Hipertensos sem consulta no período",
      "pacientes": pacientes,
      "total_pacientes_identificados": len(pacientes),
      "periodo": {"inicio": datetime.strptime(str(t_start),"%Y%m%d").strftime("%Y-%m-%d"),
                  "fim": datetime.strptime(str(t_end),"%Y%m%d").strftime("%Y-%m-%d")}}


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
