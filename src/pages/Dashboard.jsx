import { useState, useEffect } from "react";
import { Link } from "react-router-dom";

const API = import.meta.env.VITE_API_URL || "";

const INDICADORES = [
  { id: "c1", label: "C1 — Mais Acesso", link: "/indicadores/c1" },
  { id: "c2", label: "C2 — Desenvolvimento Infantil", link: "/indicadores/c2" },
  { id: "c3", label: "C3 — Gestação e Puerpério", link: "/indicadores/c3" },
  { id: "c4", label: "C4 — Diabetes", link: "/indicadores/c4" },
  { id: "c5", label: "C5 — Hipertensão", link: "/indicadores/c5" },
  { id: "c6", label: "C6 — Pessoa Idosa", link: "/indicadores/c6" },
  { id: "c7", label: "C7 — Prevenção do Câncer", link: "/indicadores/c7" },
  { id: "b1", label: "B1 — 1ª Consulta Odontológica", link: "/indicadores/b1" },
  { id: "b2", label: "B2 — Tratamento Concluído", link: "/indicadores/b2" },
  { id: "b3", label: "B3 — Taxa de Exodontia", link: "/indicadores/b3" },
  { id: "b4", label: "B4 — Escovação Supervisionada", link: "/indicadores/b4" },
  { id: "b5", label: "B5 — Procedimentos Preventivos", link: "/indicadores/b5" },
  { id: "b6", label: "B6 — TRA/ART", link: "/indicadores/b6" },
  { id: "m1", label: "M1 — Atendimentos eMulti", link: "/indicadores/m1" },
  { id: "m2", label: "M2 — Ações Interprofissionais", link: "/indicadores/m2" },
];

const CLASSES = [
  { key: "Ótimo", color: "bg-emerald-500", textColor: "text-emerald-700", bgColor: "bg-emerald-100" },
  { key: "Bom", color: "bg-blue-500", textColor: "text-blue-700", bgColor: "bg-blue-100" },
  { key: "Suficiente", color: "bg-amber-500", textColor: "text-amber-700", bgColor: "bg-amber-100" },
  { key: "Regular", color: "bg-red-500", textColor: "text-red-700", bgColor: "bg-red-100" },
];

function StatCard({ titulo, valor, cor }) {
  return (
    <div className="rounded-xl shadow bg-white p-5 border-l-4 flex items-center" style={{ borderLeftColor: cor }}>
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wide">{titulo}</p>
        <p className="text-2xl font-bold" style={{ color: cor }}>{valor != null ? valor.toLocaleString("pt-BR") : "—"}</p>
      </div>
    </div>
  );
}

function IndicatorChart({ indicador, data }) {
  if (!data) return (
    <div className="rounded-xl shadow bg-white p-5 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-3/4 mb-3"></div>
      <div className="h-7 bg-gray-200 rounded-full mb-2"></div>
      <div className="h-4 bg-gray-200 rounded w-1/3"></div>
    </div>
  );
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  if (total === 0) return null;
  return (
    <Link to={indicador.link} className="rounded-xl shadow bg-white p-5 hover:shadow-lg transition block">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{indicador.label}</h3>
      <div className="flex h-7 rounded-full overflow-hidden mb-2">
        {CLASSES.map((c) => {
          const count = data[c.key] || 0;
          if (count === 0) return null;
          return (
            <div key={c.key} className={c.color + " flex items-center justify-center text-xs text-white font-bold"}
              style={{ width: `${(count / total) * 100}%`, minWidth: count > 0 ? "1.5rem" : 0 }}>
              {count}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {CLASSES.map((c) => {
          const count = data[c.key] || 0;
          if (count === 0) return null;
          return (
            <span key={c.key} className={"px-2 py-0.5 rounded-full font-medium " + c.bgColor + " " + c.textColor}>
              {c.key}: {count}
            </span>
          );
        })}
      </div>
      {total > 0 && <p className="text-xs text-gray-400 mt-2">{total} {total === 1 ? "UBS" : "UBS"}</p>}
    </Link>
  );
}

export default function Dashboard() {
  const hoje = new Date();
  const trintaDiasAtras = new Date(hoje);
  trintaDiasAtras.setDate(trintaDiasAtras.getDate() - 30);
  const pad = (n) => String(n).padStart(2, "0");
  const dataPadrao = `${trintaDiasAtras.getFullYear()}-${pad(trintaDiasAtras.getMonth()+1)}-${pad(trintaDiasAtras.getDate())}`;
  const hojeStr = `${hoje.getFullYear()}-${pad(hoje.getMonth()+1)}-${pad(hoje.getDate())}`;

  const [stats, setStats] = useState(null);
  const [dists, setDists] = useState({});
  const [loading, setLoading] = useState(true);
  const [chartsLoading, setChartsLoading] = useState(true);
  const [inicio, setInicio] = useState(dataPadrao);
  const [fim, setFim] = useState(hojeStr);

  function carregar(i, f) {
    setLoading(true);
    setDists({});
    const params = i || f ? `?${i ? `inicio=${i}` : ""}${i && f ? "&" : ""}${f ? `fim=${f}` : ""}` : "";

    function fetchJSON(url) {
      return fetch(url).then((r) => r.ok ? r.json() : null).catch(() => null);
    }

    fetchJSON(`${API}/api/dashboard/stats`).then((s) => {
      setStats(s);
      setLoading(false);
    });

    function fetchIndicator(ind) {
      return fetchJSON(`${API}/api/indicadores/${ind.id}${params}`).then((res) => {
        if (!res || !res.ubs) return;
        const dist = { "Ótimo": 0, "Bom": 0, "Suficiente": 0, "Regular": 0 };
        res.ubs.forEach((u) => {
          const c = u.classificacao;
          if (c && dist[c] !== undefined) dist[c]++;
        });
        setDists((prev) => ({ ...prev, [ind.id]: dist }));
      });
    }
    let idx = 0;
    function next() {
      if (idx >= INDICADORES.length) { setChartsLoading(false); return; }
      const batch = INDICADORES.slice(idx, idx + 4);
      idx += 4;
      Promise.all(batch.map(fetchIndicator)).then(next);
    }
    next();
  }

  useEffect(() => { carregar(inicio, fim); }, []);
  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-teal-600" /></div>;
  if (!stats) return <div className="alert alert-error">Dashboard indisponível</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Dashboard Municipal</h1>

      <div className="flex gap-3 items-end flex-wrap bg-white p-4 rounded-xl shadow">
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
        <button className="btn btn-sm btn-teal bg-teal-600 text-white rounded-xl hover:bg-teal-700"
          onClick={() => carregar(inicio, fim)}>Filtrar</button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
        <StatCard titulo="Total Cidadãos" valor={stats.total_cidadaos} cor="#059669" />
        <StatCard titulo="Morador de Rua" valor={stats.total_morador_rua} cor="#d97706" />
        <StatCard titulo="Estrangeiros" valor={stats.total_estrangeiros} cor="#0284c7" />
        <StatCard titulo="Indígenas" valor={stats.total_indigenas} cor="#7c3aed" />
        <StatCard titulo="Def. Física" valor={stats.total_def_fisica} cor="#dc2626" />
        <StatCard titulo="Def. Intelectual" valor={stats.total_def_mental} cor="#2563eb" />
      </div>

      <h2 className="text-lg font-bold text-gray-700">Classificação dos Indicadores por UBS</h2>
      {chartsLoading && <p className="text-xs text-gray-400 mb-2">Carregando indicadores...</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {INDICADORES.map((ind) => (
          <IndicatorChart key={ind.id} indicador={ind} data={dists[ind.id]} />
        ))}
      </div>
    </div>
  );
}
