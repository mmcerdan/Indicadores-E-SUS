import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "";
const TABS = [
  { key: "fisica", label: "Deficientes Físicos", cor: "teal" },
  { key: "mental", label: "Deficientes Intelectuais/Cognitivos", cor: "purple" },
];

export default function Deficiencias() {
  const [tab, setTab] = useState("fisica");
  const [data, setData] = useState(null);
  const [busca, setBusca] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    setLoading(true);
    setError(null);
    setData(null);
    fetch(`${API}/api/deficiencia/${tab}`)
      .then((r) => { if (!r.ok) throw new Error("Erro ao carregar"); return r.json(); })
      .then((j) => { setData(j); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [tab]);

  function handleSort(key) {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
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
      <th className="cursor-pointer select-none" onClick={() => handleSort(sk)}>
        {label} {active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
      </th>
    );
  }

  const pacientes = data?.pacientes || [];
  const filtrados = busca
    ? pacientes.filter((p) =>
        [p.nome, p.cns, p.cpf, p.unidade_saude, p.equipe]
          .some((v) => v?.toLowerCase().includes(busca.toLowerCase()))
      )
    : pacientes;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Pessoas com Deficiência</h1>
          <p className="text-sm text-gray-500">Pacientes cadastrados com deficiência física ou intelectual/cognitiva</p>
        </div>
      </div>

      <div className="tabs tabs-boxed bg-white rounded-xl shadow">
        {TABS.map((t) => (
          <button key={t.key}
            className={`tab ${tab === t.key ? "tab-active font-semibold" : ""}`}
            onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {loading && <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-teal-600" /></div>}
      {error && <div className="alert alert-error">{error}</div>}
      {!loading && !error && (
        <>
          <div className="stats shadow rounded-xl">
            <div className="stat">
              <div className="stat-title text-gray-500 text-xs">Total</div>
              <div className="stat-value text-3xl" style={{ color: TABS.find(t => t.key === tab).cor === "teal" ? "#0d9488" : "#7c3aed" }}>
                {data?.total ?? 0}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <input
              type="text" placeholder="Buscar por nome, CNS, CPF, unidade ou equipe..."
              className="input input-bordered input-sm rounded-xl w-full max-w-md"
              value={busca} onChange={(e) => setBusca(e.target.value)}
            />
            <span className="text-xs text-gray-400">{filtrados.length} de {pacientes.length}</span>
          </div>

          <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
            <table className="table table-zebra w-full">
              <thead className="bg-slate-700 text-white">
                <tr>
                  <SortTh label="Nome" sortKey="nome" />
                  <SortTh label="CPF" sortKey="cpf" />
                  <SortTh label="CNS" sortKey="cns" />
                  <SortTh label="Nascimento" sortKey="data_nascimento" />
                  <SortTh label="Unidade" sortKey="unidade_saude" />
                  <SortTh label="Equipe" sortKey="equipe" />
                  <th>Tipos de Deficiência</th>
                </tr>
              </thead>
              <tbody>
                {sortRows(filtrados).map((p, i) => (
                  <tr key={i}>
                    <td className="font-medium">{p.nome}</td>
                    <td className="font-mono text-xs">{p.cpf || "—"}</td>
                    <td className="font-mono text-xs">{p.cns || "—"}</td>
                    <td className="text-xs">{(p.data_nascimento?.substring(0,10) || "").split("-").reverse().join("/") || "—"}</td>
                    <td className="text-xs">{p.unidade_saude || "—"}</td>
                    <td className="text-xs">{p.equipe || "—"}</td>
                    <td>
                      <div className="flex gap-1 flex-wrap">
                        {(p.tipos_deficiencia || []).map((t, j) => (
                          <span key={j} className="badge badge-sm badge-outline">{t}</span>
                        ))}
                        {(!p.tipos_deficiencia || p.tipos_deficiencia.length === 0) && <span className="text-xs text-gray-400">—</span>}
                      </div>
                    </td>
                  </tr>
                ))}
                {!filtrados.length && (
                  <tr><td colSpan={7} className="text-center text-gray-400 py-8">Nenhum paciente encontrado.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
