import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import BuscaAtiva from "../components/BuscaAtiva";

const API = import.meta.env.VITE_API_URL || "";

export default function IndicadorC4() {
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
    fetch(`${API}/api/indicadores/c4${qs ? "?" + qs : ""}`)
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

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-blue-600" /></div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">C4 — Cuidado da Pessoa com Diabetes</h1>
      <p className="text-sm text-gray-500">Acompanhamento de pessoas com diabetes: 6 boas práticas (A–F, 1pt cada, total 6pts/pessoa)</p>

      <details className="bg-white p-4 rounded-xl shadow text-sm">
        <summary className="cursor-pointer font-medium text-blue-700">Legenda das práticas A–F</summary>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
          <div><span className="font-bold text-blue-600">A</span> (1pt) — ≥1 consulta médica(o)/enfermeira(o) nos últimos 6 meses</div>
          <div><span className="font-bold text-blue-600">B</span> (1pt) — ≥1 aferição de pressão arterial nos últimos 6 meses</div>
          <div><span className="font-bold text-blue-600">C</span> (1pt) — ≥1 registro simultâneo de peso e altura nos últimos 12 meses</div>
          <div><span className="font-bold text-blue-600">D</span> (1pt) — ≥2 visitas ACS/TACS (intervalo ≥30 dias) nos últimos 12 meses</div>
          <div><span className="font-bold text-blue-600">E</span> (1pt) — ≥1 registro de hemoglobina glicada nos últimos 12 meses</div>
          <div><span className="font-bold text-blue-600">F</span> (1pt) — ≥1 exame do pé diabético nos últimos 12 meses</div>
        </div>
        <div className="mt-2 text-gray-400 text-xs">Fonte: Nota Metodológica SAPS/MS 2024 · Cada pessoa pode atingir até 6 pontos</div>
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
        <button className="btn btn-sm bg-blue-600 text-white rounded-xl hover:bg-blue-700" onClick={carregar}>Filtrar</button>
        {data?.periodo && (
          <span className="text-xs text-gray-400 ml-2">Período: {data.periodo.inicio} a {data.periodo.fim}</span>
        )}
        <span className="text-sm text-gray-500">{filtrados.length} equipe(s)</span>
      </div>

      <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
        <table className="table table-zebra w-full text-xs">
          <thead className="bg-blue-700 text-white">
            <tr>
              <th rowSpan={2}>Unidade</th>
              <th rowSpan={2}>Equipe</th>
              <th rowSpan={2}>INE</th>
              <th rowSpan={2}>Pessoas DM</th>
              <th colSpan={6} className="text-center border-b border-blue-600">Boas Práticas (A–F)</th>
              <th rowSpan={2}>Pontos</th>
              <th rowSpan={2}>%</th>
              <th rowSpan={2}>Classif.</th>
            </tr>
            <tr className="bg-blue-600">
              <th className="font-normal" title="≥1 consulta méd/enf 6m">A</th>
              <th className="font-normal" title="≥1 PA 6m">B</th>
              <th className="font-normal" title="≥1 peso+altura 12m">C</th>
              <th className="font-normal" title="≥2 visitas ACS/TACS 12m">D</th>
              <th className="font-normal" title="≥1 HbA1c 12m">E</th>
              <th className="font-normal" title="≥1 pé diabético 12m">F</th>
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
                  <td className="font-bold">{r.total_pessoas ?? 0}</td>
                  <td>{r.pratica_a ?? 0}</td>
                  <td>{r.pratica_b ?? 0}</td>
                  <td>{r.pratica_c ?? 0}</td>
                  <td>{r.pratica_d ?? 0}</td>
                  <td>{r.pratica_e ?? 0}</td>
                  <td>{r.pratica_f ?? 0}</td>
                  <td className="font-bold">{r.soma_praticas ?? 0}</td>
                  <td className="font-bold">{r.percentual != null ? `${r.percentual}%` : "-"}</td>
                  <td><span className={`badge ${badge} badge-sm`}>{cls || "-"}</span></td>
                </tr>
              );
            })}
            {!filtrados.length && <tr><td colSpan={15} className="text-center text-gray-400 py-8">Nenhum registro.</td></tr>}
          </tbody>
        </table>
      </div>

      <BuscaAtiva indicador="c4" label="Diabetes"
        unidade={filtroUnidade} equipe={filtroEquipe}
        inicio={inicio} fim={fim} />
    </div>
  );
}
