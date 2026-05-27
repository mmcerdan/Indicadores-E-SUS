import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "";

export default function ModuloEstrangeiros() {
  const [rows, setRows] = useState([]);
  const [busca, setBusca] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    fetch(`${API}/api/estrangeiros`)
      .then((r) => r.json())
      .then((j) => { setRows(j.dados || []); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-teal-600" /></div>;
  if (error) return <div className="alert alert-error">Erro: {error}</div>;

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function sortRows(arr) {
    if (!sortKey) return arr;
    return [...arr].sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (va == null) va = "";
      if (vb == null) vb = "";
      if (typeof va === "number" && typeof vb === "number") {
        return sortDir === "asc" ? va - vb : vb - va;
      }
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

  const filtrados = sortRows(
    busca
      ? rows.filter((r) =>
          Object.values(r).some((v) => String(v).toLowerCase().includes(busca.toLowerCase()))
        )
      : rows
  );

  const total = rows.length;
  const comAtendimento = rows.filter((r) => r.flag_atendimento_recente).length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3">
        <div className="stat rounded-xl shadow bg-white">
          <div className="stat-title text-xs">Total</div>
          <div className="stat-value text-2xl text-teal-600">{total}</div>
          <div className="stat-desc text-xs">Estrangeiros ativos</div>
        </div>
        <div className="stat rounded-xl shadow bg-white">
          <div className="stat-title text-xs">Atendimento (12m)</div>
          <div className="stat-value text-2xl text-blue-600">{comAtendimento}</div>
          <div className="stat-desc text-xs">Pacientes com atendimento recente</div>
        </div>
      </div>

      <div className="flex gap-2 items-center">
        <input
          type="text"
          placeholder="Buscar na tabela..."
          className="input input-bordered input-sm rounded-xl w-full max-w-xs"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
        <span className="text-xs text-gray-400">{filtrados.length} de {total}</span>
      </div>

      <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
        <table className="table table-zebra w-full">
          <thead className="bg-teal-700 text-white">
            <tr>
              <SortTh label="Nome" sortKey="nome" />
              <SortTh label="CNS" sortKey="cns" />
              <SortTh label="CPF" sortKey="cpf" />
              <SortTh label="Nacionalidade" sortKey="pais_origem" />
              <SortTh label="Unidade" sortKey="unidade_saude" />
              <SortTh label="Atend. (12m)" sortKey="flag_atendimento_recente" />
              <SortTh label="Vínculo Unid." sortKey="flag_vinculo_unidade" />
              <SortTh label="CPF" sortKey="flag_cpf_presente" />
              <SortTh label="CNS Válido" sortKey="flag_cns_valido" />
            </tr>
          </thead>
          <tbody>
            {filtrados.map((r, i) => (
              <tr key={i}>
                <td className="font-medium">{r.nome}</td>
                <td className="font-mono text-xs">{r.cns || "-"}</td>
                <td className="font-mono text-xs">{r.cpf || "-"}</td>
                <td>{r.pais_origem}</td>
                <td>{r.unidade_saude || "-"}</td>
                <td>{r.flag_atendimento_recente ? "Sim" : "Não"}</td>
                <td>{r.flag_vinculo_unidade ? "Sim" : "Não"}</td>
                <td>{r.flag_cpf_presente ? "Sim" : "Não"}</td>
                <td>{r.flag_cns_valido ? "Sim" : "Não"}</td>
              </tr>
            ))}
            {!filtrados.length && <tr><td colSpan={9} className="text-center text-gray-400 py-8">Nenhum estrangeiro encontrado.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
