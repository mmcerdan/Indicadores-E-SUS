import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import BuscaAtiva from "../components/BuscaAtiva";

const API = import.meta.env.VITE_API_URL || "";

export default function IndicadorC3() {
  const hoje = new Date();
  const trintaDiasAtras = new Date(hoje);
  trintaDiasAtras.setDate(trintaDiasAtras.getDate() - 30);
  const pad = (n) => String(n).padStart(2, "0");
  const dataPadrao = `${trintaDiasAtras.getFullYear()}-${pad(trintaDiasAtras.getMonth()+1)}-${pad(trintaDiasAtras.getDate())}`;
  const hojeStr = `${hoje.getFullYear()}-${pad(hoje.getMonth()+1)}-${pad(hoje.getDate())}`;
  const [params] = useSearchParams();
  const [data, setData] = useState(null);
  const [unidades, setUnidades] = useState([]);
  const [equipes, setEquipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filtroUnidade, setFiltroUnidade] = useState(params.get("unidade") || "");
  const [filtroEquipe, setFiltroEquipe] = useState("");
  const [inicio, setInicio] = useState(dataPadrao);
  const [fim, setFim] = useState(hojeStr);

  useEffect(() => {
    fetch(`${API}/api/unidades`)
      .then((r) => r.json())
      .then((j) => setUnidades(j))
      .catch(() => {});
    fetch(`${API}/api/equipes`)
      .then((r) => r.json())
      .then((j) => setEquipes(j))
      .catch(() => {});
  }, []);

  const equipesFiltradas = filtroUnidade
    ? equipes.filter((e) => e.unidade === filtroUnidade)
    : equipes;

  function carregar() {
    setLoading(true);
    const p = new URLSearchParams();
    if (filtroUnidade) p.set("unidade", filtroUnidade);
    if (inicio) p.set("inicio", inicio);
    if (fim) p.set("fim", fim);
    const qs = p.toString();
    fetch(`${API}/api/indicadores/c3${qs ? "?" + qs : ""}`)
      .then((r) => r.json())
      .then((j) => { setData(j); setLoading(false); })
      .catch(() => setLoading(false));
  }

  useEffect(() => { carregar(); }, []);

  const rows = data?.ubs || [];
  const filtrados = rows.filter((r) => {
    if (filtroUnidade && !r.unidade_saude.toLowerCase().includes(filtroUnidade.toLowerCase())) return false;
    if (filtroEquipe && r.no_equipe !== filtroEquipe) return false;
    return true;
  });

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-pink-600" /></div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">C3 — Cuidado na Gestação e Puerpério</h1>
      <p className="text-sm text-gray-500">Acompanhamento de gestantes e puérperas: 11 boas práticas (A=10pts, B–K=9pts cada, total 100pts/gestação)</p>

      <details className="bg-white p-4 rounded-xl shadow text-sm">
        <summary className="cursor-pointer font-medium text-pink-700">Legenda das práticas A–K</summary>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
          <div><span className="font-bold text-pink-600">A</span> (10pt) — 1ª consulta médica(o)/enfermeira(o) até a 12ª semana de gestação</div>
          <div><span className="font-bold text-pink-600">B</span> (9pt) — ≥7 consultas médica(o)/enfermeira(o) durante a gestação</div>
          <div><span className="font-bold text-pink-600">C</span> (9pt) — ≥7 aferições de pressão arterial na gestação</div>
          <div><span className="font-bold text-pink-600">D</span> (9pt) — ≥7 registros simultâneos de peso e altura na gestação</div>
          <div><span className="font-bold text-pink-600">E</span> (9pt) — ≥3 visitas domiciliares ACS/TACS após 1ª consulta do pré-natal</div>
          <div><span className="font-bold text-pink-600">F</span> (9pt) — Vacina dTpa registrada a partir da 20ª semana de gestação</div>
          <div><span className="font-bold text-pink-600">G</span> (9pt) — Testes rápidos/exames para sífilis, HIV, hepatites B e C no 1º trimestre</div>
          <div><span className="font-bold text-pink-600">H</span> (9pt) — Testes rápidos/exames para sífilis e HIV no 3º trimestre</div>
          <div><span className="font-bold text-pink-600">I</span> (9pt) — ≥1 consulta médica(o)/enfermeira(o) durante o puerpério</div>
          <div><span className="font-bold text-pink-600">J</span> (9pt) — ≥1 visita domiciliar ACS/TACS durante o puerpério</div>
          <div><span className="font-bold text-pink-600">K</span> (9pt) — ≥1 atividade em saúde bucal (CD/TSB) durante a gestação</div>
        </div>
        <div className="mt-2 text-gray-400 text-xs">Fonte: Nota Metodológica SAPS/MS 2024 · Cada gestação pode atingir até 100 pontos</div>
      </details>

      <div className="flex gap-3 items-end flex-wrap bg-white p-4 rounded-xl shadow">
        <div>
          <label className="label-text text-xs text-gray-500">Unidade</label>
          <select className="select select-bordered select-sm rounded-xl w-full max-w-xs" value={filtroUnidade}
            onChange={(e) => { setFiltroUnidade(e.target.value); setFiltroEquipe(""); }}>
            <option value="">Todas</option>
            {unidades.map((u) => <option key={u.id} value={u.nome}>{u.nome}</option>)}
          </select>
        </div>
        <div>
          <label className="label-text text-xs text-gray-500">Equipe</label>
          <select className="select select-bordered select-sm rounded-xl w-full max-w-xs" value={filtroEquipe}
            onChange={(e) => setFiltroEquipe(e.target.value)}>
            <option value="">Todas</option>
            {equipesFiltradas.map((e) => <option key={e.id} value={e.nome}>{e.nome}</option>)}
          </select>
        </div>
        <div>
          <label className="label-text text-xs text-gray-500">Data início</label>
          <input type="date" className="input input-bordered input-sm rounded-xl" value={inicio}
            onChange={(e) => setInicio(e.target.value)} />
        </div>
        <div>
          <label className="label-text text-xs text-gray-500">Data fim</label>
          <input type="date" className="input input-bordered input-sm rounded-xl" value={fim}
            onChange={(e) => setFim(e.target.value)} />
        </div>
        <button className="btn btn-sm bg-pink-600 text-white rounded-xl hover:bg-pink-700" onClick={carregar}>Filtrar</button>
        {data?.periodo && (
          <span className="text-xs text-gray-400 ml-2">Período: {data.periodo.inicio} a {data.periodo.fim}</span>
        )}
        <span className="text-sm text-gray-500">{filtrados.length} equipe(s)</span>
      </div>

      <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
        <table className="table table-zebra w-full text-xs">
          <thead className="bg-pink-700 text-white">
            <tr>
              <th rowSpan={2}>Unidade</th>
              <th rowSpan={2}>Equipe</th>
              <th rowSpan={2}>INE</th>
              <th rowSpan={2}>Gest.</th>
              <th colSpan={11} className="text-center border-b border-pink-600">Boas Práticas (A–K)</th>
              <th rowSpan={2}>Pontos</th>
              <th rowSpan={2}>%</th>
              <th rowSpan={2}>Classif.</th>
            </tr>
            <tr className="bg-pink-600">
              <th className="font-normal" title="1ª consulta ≤12ª sem">A</th>
              <th className="font-normal" title="≥7 consultas">B</th>
              <th className="font-normal" title="≥7 aferições PA">C</th>
              <th className="font-normal" title="≥7 peso+altura">D</th>
              <th className="font-normal" title="≥3 visitas ACS/TACS">E</th>
              <th className="font-normal" title="dTpa ≥20ª sem">F</th>
              <th className="font-normal" title="Testes 1º tri">G</th>
              <th className="font-normal" title="Testes 3º tri">H</th>
              <th className="font-normal" title="≥1 consulta puerperal">I</th>
              <th className="font-normal" title="≥1 visita puerpério">J</th>
              <th className="font-normal" title="≥1 odontológico">K</th>
            </tr>
          </thead>
          <tbody>
            {filtrados.map((r, i) => {
              const cls = r.classificacao;
              let badge = "badge-ghost";
              if (cls === "Ótimo") badge = "badge-success";
              else if (cls === "Bom") badge = "badge-info";
              else if (cls === "Suficiente") badge = "badge-warning";
              else if (cls === "Regular") badge = "badge-error";
              return (
                <tr key={i}>
                  <td className="font-medium">{r.unidade_saude}</td>
                  <td>{r.no_equipe || "-"}</td>
                  <td className="font-mono">{r.nu_ine || "-"}</td>
                  <td className="font-bold">{r.total_gestacoes ?? 0}</td>
                  <td>{r.pratica_a ?? 0}</td>
                  <td>{r.pratica_b ?? 0}</td>
                  <td>{r.pratica_c ?? 0}</td>
                  <td>{r.pratica_d ?? 0}</td>
                  <td>{r.pratica_e ?? 0}</td>
                  <td>{r.pratica_f ?? 0}</td>
                  <td>{r.pratica_g ?? 0}</td>
                  <td>{r.pratica_h ?? 0}</td>
                  <td>{r.pratica_i ?? 0}</td>
                  <td>{r.pratica_j ?? 0}</td>
                  <td>{r.pratica_k ?? 0}</td>
                  <td className="font-bold">{r.soma_pontos ?? 0}</td>
                  <td className="font-bold">{r.percentual != null ? `${r.percentual}%` : "-"}</td>
                  <td><span className={`badge ${badge} badge-sm`}>{cls || "-"}</span></td>
                </tr>
              );
            })}
            {!filtrados.length && <tr><td colSpan={19} className="text-center text-gray-400 py-8">Nenhum registro.</td></tr>}
          </tbody>
        </table>
      </div>

      <BuscaAtiva indicador="c3" label="Gestação/Puerpério"
        unidade={filtroUnidade} equipe={filtroEquipe}
        inicio={inicio} fim={fim} />
    </div>
  );
}
