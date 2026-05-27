import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "";
const PENDENCIAS = [
  { key: "pendencia_consulta", label: "Sem Consulta (6m)", color: "badge-warning" },
  { key: "pendencia_vacina", label: "Vacina Atrasada", color: "badge-error" },
  { key: "pendencia_peso_altura", label: "Sem Peso/Altura (12m)", color: "badge-error" },
  { key: "pendencia_prenatal", label: "Pré-natal Atrasado", color: "badge-warning" },
];

export default function BolsaFamilia() {
  const [data, setData] = useState(null);
  const [unidades, setUnidades] = useState([]);
  const [busca, setBusca] = useState("");
  const [filtroUnidade, setFiltroUnidade] = useState("");
  const [pagina, setPagina] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    fetch(`${API}/api/unidades`)
      .then((r) => r.json())
      .then((j) => setUnidades(j))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filtroUnidade) params.set("unidade", filtroUnidade);
    params.set("pagina", pagina);
    params.set("por_pagina", "500");
    fetch(`${API}/api/bolsa-familia?${params}`)
      .then((r) => { if (!r.ok) throw new Error("Erro ao carregar"); return r.json(); })
      .then((j) => { setData(j); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [filtroUnidade, pagina]);

  function handleSort(key) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  }

  function sortRows(arr) {
    if (!sortKey || !arr) return arr;
    return [...arr].sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (va == null) va = ""; if (vb == null) vb = "";
      if (typeof va === "number" && typeof vb === "number")
        return sortDir === "asc" ? va - vb : vb - va;
      return sortDir === "asc"
        ? String(va).localeCompare(String(vb))
        : String(vb).localeCompare(String(va));
    });
  }

  function SortTh({ label, sortKey: sk }) {
    const active = sortKey === sk;
    return (
      <th className="cursor-pointer select-none whitespace-nowrap" onClick={() => handleSort(sk)}>
        {label} {active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
      </th>
    );
  }

  const beneficiarios = data?.beneficiarios || [];
  const filtrados = busca
    ? beneficiarios.filter((b) =>
        [b.nome_bolsa, b.nome_esus, b.cpf, b.cns, b.no_unidade_saude, b.no_equipe]
          .some((v) => v?.toLowerCase().includes(busca.toLowerCase()))
      )
    : beneficiarios;

  const loadPagina = (p) => { setPagina(p); window.scrollTo(0, 0); };

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-teal-600" /></div>;
  if (error) return <div className="alert alert-error">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Bolsa Família</h1>
          <p className="text-sm text-gray-500">Beneficiários do Programa Bolsa Família — condicionalidades de saúde</p>
        </div>
      </div>

      <div className="flex gap-4 flex-wrap">
        <div className="stats shadow rounded-xl">
          <div className="stat">
            <div className="stat-title text-gray-500 text-xs">Total Beneficiários</div>
            <div className="stat-value text-3xl text-teal-600">{data?.total ?? 0}</div>
          </div>
        </div>
        <div className="stats shadow rounded-xl">
          <div className="stat">
            <div className="stat-title text-gray-500 text-xs">Sem Consulta (6m)</div>
            <div className="stat-value text-3xl text-amber-600">{data?.agregados?.pendencia_consulta ?? 0}</div>
          </div>
        </div>
        <div className="stats shadow rounded-xl">
          <div className="stat">
            <div className="stat-title text-gray-500 text-xs">Vacina Atrasada</div>
            <div className="stat-value text-3xl text-red-600">{data?.agregados?.pendencia_vacina ?? 0}</div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <select className="select select-bordered select-sm rounded-xl w-full max-w-xs"
          value={filtroUnidade} onChange={(e) => { setFiltroUnidade(e.target.value); setPagina(1); }}>
          <option value="">Todas as Unidades</option>
          {unidades.map((u) => <option key={u.id} value={u.nome}>{u.nome}</option>)}
        </select>
        <input type="text" placeholder="Buscar por nome, CPF, CNS, unidade ou equipe..."
          className="input input-bordered input-sm rounded-xl w-full max-w-md"
          value={busca} onChange={(e) => setBusca(e.target.value)} />
      </div>

      <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
        <table className="table table-zebra w-full text-xs">
          <thead className="bg-slate-700 text-white">
            <tr>
              <SortTh label="Nome" sortKey="nome_bolsa" />
              <SortTh label="CPF" sortKey="cpf" />
              <SortTh label="CNS" sortKey="cns" />
              <SortTh label="Nascimento" sortKey="dt_nascimento" />
              <SortTh label="Unidade" sortKey="no_unidade_saude" />
              <SortTh label="Equipe" sortKey="no_equipe" />
              <th className="text-center">Pendências</th>
            </tr>
          </thead>
          <tbody>
            {sortRows(filtrados).map((b, i) => (
              <tr key={i}>
                <td className="font-medium whitespace-nowrap">{b.nome_bolsa}</td>
                <td className="font-mono">{b.cpf || "—"}</td>
                <td className="font-mono">{b.cns || "—"}</td>
                <td className="whitespace-nowrap">
                  {(b.dt_nascimento?.substring(0, 10) || "").split("-").reverse().join("/") || "—"}
                </td>
                <td className="max-w-[200px] truncate" title={b.no_unidade_saude}>{b.no_unidade_saude || "—"}</td>
                <td>{b.no_equipe || "—"}</td>
                <td>
                  <div className="flex gap-1 flex-wrap">
                    {PENDENCIAS.map((p) =>
                      b[p.key] ? <span key={p.key} className={`badge badge-sm ${p.color}`}>{p.label}</span> : null
                    )}
                    {!PENDENCIAS.some((p) => b[p.key]) && (
                      <span className="badge badge-sm badge-success gap-1">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                        OK
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!filtrados.length && (
              <tr><td colSpan={7} className="text-center text-gray-400 py-8">Nenhum beneficiário encontrado.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data?.total_paginas > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button className="btn btn-sm rounded-xl" disabled={pagina <= 1} onClick={() => loadPagina(pagina - 1)}>Anterior</button>
          <span className="text-sm text-gray-500">
            Página {data.pagina} de {data.total_paginas}
          </span>
          <button className="btn btn-sm rounded-xl" disabled={pagina >= data.total_paginas} onClick={() => loadPagina(pagina + 1)}>Próxima</button>
        </div>
      )}
    </div>
  );
}
