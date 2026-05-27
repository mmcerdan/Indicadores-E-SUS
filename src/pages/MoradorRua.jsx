import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "";

export default function MoradorRua() {
  const [data, setData] = useState(null);
  const [busca, setBusca] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    fetch(`${API}/api/inconsistencias/morador-rua`)
      .then((r) => { if (!r.ok) throw new Error("Erro ao carregar"); return r.json(); })
      .then((j) => { setData(j); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

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
        [p.nome, p.cns, p.cpf, p.unidade_saude, p.no_equipe]
          .some((v) => v?.toLowerCase().includes(busca.toLowerCase()))
      )
    : pacientes;

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-teal-600" /></div>;
  if (error) return <div className="alert alert-error">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Moradores em Situação de Rua</h1>
          <p className="text-sm text-gray-500">Pacientes cadastrados como morador de rua</p>
        </div>
      </div>

      <div className="stats shadow rounded-xl">
        <div className="stat">
          <div className="stat-title text-gray-500 text-xs">Total de Moradores de Rua</div>
          <div className="stat-value text-3xl text-teal-600">{data?.total ?? 0}</div>
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
              <SortTh label="CNS" sortKey="cns" />
              <SortTh label="CPF" sortKey="cpf" />
              <SortTh label="Nascimento" sortKey="data_nascimento" />
              <SortTh label="Unidade" sortKey="unidade_saude" />
              <SortTh label="Equipe" sortKey="no_equipe" />
            </tr>
          </thead>
          <tbody>
            {sortRows(filtrados).map((p, i) => (
              <tr key={i}>
                <td className="font-medium">{p.nome}</td>
                <td className="font-mono text-xs">{p.cns || "—"}</td>
                <td className="font-mono text-xs">{p.cpf || "—"}</td>
                <td className="text-xs">{(p.data_nascimento?.substring(0,10) || "").split("-").reverse().join("/") || "—"}</td>
                <td className="text-xs">{p.unidade_saude || "—"}</td>
                <td className="text-xs">{p.no_equipe || "—"}</td>
              </tr>
            ))}
            {!filtrados.length && (
              <tr><td colSpan={6} className="text-center text-gray-400 py-8">Nenhum morador de rua encontrado.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
