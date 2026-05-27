import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";

const API = import.meta.env.VITE_API_URL || "";

export default function IndicadorB4() {
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
    fetch(`${API}/api/indicadores/b4${qs ? "?" + qs : ""}`)
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

  const classBadge = (v) => {
    if (!v || v === "Sem dados") return <span className="badge badge-ghost">Sem dados</span>;
    if (v === "Ótimo") return <span className="badge badge-success badge-outline">Ótimo</span>;
    if (v === "Bom") return <span className="badge badge-info badge-outline">Bom</span>;
    if (v === "Suficiente") return <span className="badge badge-warning badge-outline">Suficiente</span>;
    if (v === "Regular") return <span className="badge badge-error badge-outline">Regular</span>;
    return <span className="badge badge-ghost">{v}</span>;
  };

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-cyan-600" /></div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">B4 - Escovação Dentária Supervisionada</h1>
      <p className="text-sm text-gray-500">Cobertura de escovação supervisionada em crianças de 6 a 12 anos por equipe ESB</p>

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
        <button className="btn btn-sm bg-cyan-600 text-white rounded-xl hover:bg-cyan-700" onClick={carregar}>Filtrar</button>
        {data?.periodo && (
          <span className="text-xs text-gray-400 ml-2">Período: {data.periodo.inicio} a {data.periodo.fim}</span>
        )}
        <span className="text-sm text-gray-500">{filtrados.length} equipe(s)</span>
      </div>

      <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
        <table className="table table-zebra w-full">
          <thead className="bg-cyan-700 text-white">
            <tr>
              <th>Unidade</th>
              <th>Equipe</th>
              <th>INE</th>
              <th className="text-right">Atividades</th>
              <th className="text-right">Participantes</th>
              <th className="text-right">Crianças 6-12</th>
              <th className="text-right">%</th>
              <th className="text-center">Classificação</th>
            </tr>
          </thead>
          <tbody>
            {filtrados.map((r, i) => (
              <tr key={i}>
                <td className="font-medium">{r.unidade_saude}</td>
                <td>{r.no_equipe || "-"}</td>
                <td className="font-mono text-xs">{r.nu_ine || "-"}</td>
                <td className="text-right">{r.total_atividades ?? 0}</td>
                <td className="text-right">{r.total_participantes ?? 0}</td>
                <td className="text-right">{r.total_criancas ?? 0}</td>
                <td className="font-bold text-right">{r.percentual ?? 0}%</td>
                <td className="text-center">{classBadge(r.classificacao)}</td>
              </tr>
            ))}
            {!filtrados.length && <tr><td colSpan={8} className="text-center text-gray-400 py-8">Nenhum registro.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
