import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import BuscaAtiva from "../components/BuscaAtiva";

const API = import.meta.env.VITE_API_URL || "";

export default function IndicadorC6() {
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
    fetch(`${API}/api/indicadores/c6${qs ? "?" + qs : ""}`)
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

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-indigo-600" /></div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">C6 — Cuidado da Pessoa Idosa</h1>
      <p className="text-sm text-gray-500">Acompanhamento de pessoas com 60+ anos: 4 boas práticas (A–D, 25pts cada, total 100pts/pessoa)</p>

      <details className="bg-white p-4 rounded-xl shadow text-sm">
        <summary className="cursor-pointer font-medium text-indigo-700">Legenda das práticas A–D</summary>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
          <div><span className="font-bold text-indigo-600">A</span> (25pt) — ≥1 consulta médica(o)/enfermeira(o) nos últimos 12 meses</div>
          <div><span className="font-bold text-indigo-600">B</span> (25pt) — ≥1 registro simultâneo de peso e altura nos últimos 12 meses</div>
          <div><span className="font-bold text-indigo-600">C</span> (25pt) — ≥2 visitas ACS/TACS (intervalo ≥30 dias) nos últimos 12 meses</div>
          <div><span className="font-bold text-indigo-600">D</span> (25pt) — ≥1 dose vacina influenza (cód. 33/77) nos últimos 12 meses</div>
        </div>
        <div className="mt-2 text-gray-400 text-xs">Fonte: Nota Metodológica SAPS/MS 2024 · Pessoa idosa ≥ 60 anos · Max 100pts/pessoa</div>
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
        <button className="btn btn-sm bg-indigo-600 text-white rounded-xl hover:bg-indigo-700" onClick={carregar}>Filtrar</button>
        {data?.periodo && (
          <span className="text-xs text-gray-400 ml-2">Período: {data.periodo.inicio} a {data.periodo.fim}</span>
        )}
        <span className="text-sm text-gray-500">{filtrados.length} equipe(s)</span>
      </div>

      <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
        <table className="table table-zebra w-full text-xs">
          <thead className="bg-indigo-700 text-white">
            <tr>
              <th rowSpan={2}>Unidade</th>
              <th rowSpan={2}>Equipe</th>
              <th rowSpan={2}>INE</th>
              <th rowSpan={2}>Idosos</th>
              <th colSpan={4} className="text-center border-b border-indigo-600">Boas Práticas (A–D)</th>
              <th rowSpan={2}>Pontos</th>
              <th rowSpan={2}>%</th>
              <th rowSpan={2}>Classif.</th>
            </tr>
            <tr className="bg-indigo-600">
              <th className="font-normal" title="≥1 consulta méd/enf 12m">A</th>
              <th className="font-normal" title="≥1 peso+altura 12m">B</th>
              <th className="font-normal" title="≥2 visitas ACS/TACS 12m">C</th>
              <th className="font-normal" title="≥1 influenza 12m">D</th>
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
                  <td className="font-bold">{r.soma_praticas ?? 0}</td>
                  <td className="font-bold">{r.percentual != null ? `${r.percentual}%` : "-"}</td>
                  <td><span className={`badge ${badge} badge-sm`}>{cls || "-"}</span></td>
                </tr>
              );
            })}
            {!filtrados.length && <tr><td colSpan={13} className="text-center text-gray-400 py-8">Nenhum registro.</td></tr>}
          </tbody>
        </table>
      </div>

      <BuscaAtiva indicador="c6" label="Pessoa Idosa"
        unidade={filtroUnidade} equipe={filtroEquipe}
        inicio={inicio} fim={fim} />
    </div>
  );
}