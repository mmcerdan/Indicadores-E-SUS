import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "";

export default function Inconsistencias() {
  const [data, setData] = useState(null);
  const [gestantes, setGestantes] = useState(null);
  const [loading, setLoading] = useState(true);
  const [aba, setAba] = useState("duplicados");
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    fetch(`${API}/api/inconsistencias`)
      .then((r) => r.json())
      .then((j) => setData(j))
      .catch(() => {});
    fetch(`${API}/api/inconsistencias/gestantes`)
      .then((r) => r.json())
      .then((j) => setGestantes(j))
      .catch(() => {});
    Promise.all([]).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-teal-600" /></div>;

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function sortRows(arr) {
    if (!sortKey || !arr) return arr;
    return [...arr].sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (va == null) va = "";
      if (vb == null) vb = "";
      if (Array.isArray(va)) va = va.join(", ");
      if (Array.isArray(vb)) vb = vb.join(", ");
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

  const abas = [
    { key: "duplicados", label: "Nomes Duplicados", count: data?.duplicados?.length || 0 },
    { key: "rn_de", label: "RN / DE", count: data?.rn_de?.length || 0 },
    { key: "gestantes", label: "Gestantes DUM Antiga", count: gestantes?.total || 0 },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Inconsistências Cadastrais</h1>
      <p className="text-sm text-gray-500">Pacientes com possíveis erros no cadastro</p>

      <div className="tabs tabs-boxed bg-white rounded-xl shadow-sm">
        {abas.map(({ key, label, count }) => (
          <button
            key={key}
            className={`tab ${aba === key ? "tab-active bg-teal-700 text-white" : ""}`}
            onClick={() => setAba(key)}
          >
            {label} <span className="ml-1 text-xs opacity-70">({count})</span>
          </button>
        ))}
      </div>

      {aba === "duplicados" && (
        <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
          <table className="table table-zebra w-full">
            <thead className="bg-amber-600 text-white">
              <tr>
                <SortTh label="Nome" sortKey="nome" />
                <SortTh label="Nascimento" sortKey="data_nascimento" />
                <SortTh label="Qtd" sortKey="quantidade" />
                <SortTh label="CNS" sortKey="cns_list" />
                <SortTh label="CPF" sortKey="cpf_list" />
                <SortTh label="Unidade" sortKey="unidade_list" />
                <SortTh label="Equipe" sortKey="equipe_list" />
              </tr>
            </thead>
            <tbody>
              {sortRows(data?.duplicados)?.map((r, i) => (
                <tr key={i}>
                  <td className="font-medium">{r.nome}</td>
                  <td className="text-xs">{(r.data_nascimento||"").split("-").reverse().join("/")||"—"}</td>
                  <td><span className="badge badge-error badge-sm">{r.quantidade}</span></td>
                  <td className="font-mono text-sm max-w-xs break-all">{r.cns_list?.join(", ") || "—"}</td>
                  <td className="font-mono text-sm max-w-xs break-all">{r.cpf_list?.join(", ") || "—"}</td>
                  <td className="text-sm max-w-xs break-all">{r.unidade_list?.join(", ") || "—"}</td>
                  <td className="text-sm max-w-xs break-all">{r.equipe_list?.join(", ") || "—"}</td>
                </tr>
              ))}
              {(!data?.duplicados || data.duplicados.length === 0) && (
                <tr><td colSpan={7} className="text-center text-gray-400 py-8">Nenhum nome duplicado encontrado.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {aba === "rn_de" && (
        <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
          <table className="table table-zebra w-full">
            <thead className="bg-rose-600 text-white">
              <tr>
                <SortTh label="Nome" sortKey="nome" />
                <SortTh label="Nascimento" sortKey="data_nascimento" />
                <SortTh label="CNS" sortKey="cns_list" />
                <SortTh label="CPF" sortKey="cpf_list" />
                <SortTh label="Unidade" sortKey="unidade_list" />
                <SortTh label="Equipe" sortKey="equipe_list" />
              </tr>
            </thead>
            <tbody>
              {sortRows(data?.rn_de)?.map((r, i) => (
                <tr key={i}>
                  <td className="font-medium text-rose-700">{r.nome}</td>
                  <td className="text-xs">{(r.data_nascimento||"").split("-").reverse().join("/")||"—"}</td>
                  <td className="font-mono text-sm">{r.cns_list?.[0] || "—"}</td>
                  <td className="font-mono text-sm">{r.cpf_list?.[0] || "—"}</td>
                  <td className="text-sm">{r.unidade_list?.[0] || "—"}</td>
                  <td className="text-sm">{r.equipe_list?.[0] || "—"}</td>
                </tr>
              ))}
              {(!data?.rn_de || data.rn_de.length === 0) && (
                <tr><td colSpan={6} className="text-center text-gray-400 py-8">Nenhum registro RN/DE encontrado.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {aba === "gestantes" && (
        <div className="overflow-x-auto rounded-xl shadow border border-gray-200">
          <table className="table table-zebra w-full">
            <thead className="bg-purple-600 text-white">
              <tr>
                <SortTh label="Nome" sortKey="nome" />
                <SortTh label="CNS" sortKey="cns" />
                <SortTh label="CPF" sortKey="cpf" />
                <SortTh label="DUM" sortKey="dum_formatado" />
                <SortTh label="Meses" sortKey="meses_desde_dum" />
                <SortTh label="Unidade" sortKey="unidade_saude" />
                <SortTh label="Equipe" sortKey="no_equipe" />
              </tr>
            </thead>
            <tbody>
              {sortRows(gestantes?.gestantes)?.map((r, i) => (
                <tr key={i}>
                  <td className="font-medium">{r.nome}</td>
                  <td className="font-mono text-sm">{r.cns || "—"}</td>
                  <td className="font-mono text-sm">{r.cpf || "—"}</td>
                  <td className="font-mono text-sm">{r.dum_formatado || r.dum || "—"}</td>
                  <td><span className="badge badge-error badge-sm">{r.meses_desde_dum ?? "?"}m</span></td>
                  <td>{r.unidade_saude || "—"}</td>
                  <td>{r.no_equipe || "—"}</td>
                </tr>
              ))}
              {(!gestantes?.gestantes || gestantes.gestantes.length === 0) && (
                <tr><td colSpan={7} className="text-center text-gray-400 py-8">Nenhuma gestante com DUM antiga.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
}
