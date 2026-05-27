import { useState } from "react";

const API = import.meta.env.VITE_API_URL || "";

export default function BuscaAtiva({ indicador, label, unidade, equipe, inicio, fim }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");
  const [aberto, setAberto] = useState(false);

  function carregar() {
    setLoading(true);
    setErro("");
    const p = new URLSearchParams();
    if (unidade) p.set("unidade", unidade);
    if (equipe) p.set("equipe", equipe);
    if (inicio) p.set("inicio", inicio);
    if (fim) p.set("fim", fim);
    const qs = p.toString();
    fetch(`${API}/api/busca-ativa/${indicador}${qs ? "?" + qs : ""}`)
      .then((r) => {
        if (!r.ok) throw new Error("Erro na requisição");
        return r.json();
      })
      .then((j) => { setData(j); setLoading(false); setAberto(true); })
      .catch((e) => { setErro(e.message); setLoading(false); });
  }

  return (
    <div className="rounded-xl border border-dashed border-amber-400 bg-amber-50 p-4 mt-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="font-bold text-amber-800 flex items-center gap-2">
            <span className="text-lg">🔍</span> Busca Ativa — {label}
          </h3>
          {data && (
            <p className="text-sm text-amber-700">
              {data.total_pacientes_identificados ?? 0} paciente(s) identificado(s)
              {data.periodo && ` (${data.periodo.inicio} a ${data.periodo.fim})`}
            </p>
          )}
        </div>
        <button
          className={`btn btn-sm rounded-xl ${loading ? "btn-disabled" : "bg-amber-600 text-white hover:bg-amber-700"}`}
          onClick={carregar}
          disabled={loading}
        >
          {loading ? <span className="loading loading-spinner loading-xs" /> : null}
          {loading ? "Carregando..." : aberto ? "Recarregar" : "Carregar Busca Ativa"}
        </button>
      </div>

      {erro && <p className="text-sm text-red-600 mt-2">{erro}</p>}

      {aberto && data && (
        <div className="mt-4 space-y-4">
          {data.resumo ? <ResumoComGaps resumo={data.resumo} /> : <TabelaPacientes pacientes={data.pacientes || []} />}
        </div>
      )}
    </div>
  );
}

function ResumoComGaps({ resumo }) {
  const [expandido, setExpandido] = useState({});
  if (!resumo?.length) return <p className="text-sm text-gray-500 italic">Nenhum paciente identificado.</p>;

  return (
    <div className="space-y-3">
      {resumo.map((eq, i) => {
        const key = `${eq.unidade_saude}-${eq.no_equipe}-${i}`;
        const exp = expandido[key] || false;
        return (
          <div key={key} className="bg-white rounded-xl shadow-sm border border-amber-200 overflow-hidden">
            <button
              className="w-full flex items-center justify-between p-3 hover:bg-amber-50 text-left"
              onClick={() => setExpandido((prev) => ({ ...prev, [key]: !prev[key] }))}
            >
              <div>
                <p className="font-semibold text-sm">{eq.unidade_saude}</p>
                <p className="text-xs text-gray-500">{eq.no_equipe || "Sem equipe"} · INE {eq.nu_ine || "-"}</p>
              </div>
              <div className="text-right text-xs space-y-0.5">
                <span className="font-bold text-base block">{eq.atual.valor ?? "—"}%</span>
                <ClassBadge2 v={eq.atual.classificacao} />
              </div>
            </button>
            {exp && (
              <div className="border-t border-amber-100 p-3 space-y-3">
                {eq.gaps?.filter((g) => g.faltam > 0).length > 0 && (
                  <div className="flex gap-2 flex-wrap">
                    {eq.gaps.filter((g) => g.faltam > 0).map((g, gi) => (
                      <div key={gi} className="bg-amber-100 text-amber-800 px-3 py-1.5 rounded-lg text-xs">
                        <strong className="block text-sm">{g.faltam}</strong>
                        {g.tipo} para <strong>{g.nivel}</strong> ({g.meta})
                      </div>
                    ))}
                  </div>
                )}
                {eq.pacientes?.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="table table-xs w-full">
                      <thead>
                        <tr className="text-amber-700">
                          <th>Paciente</th>
                          <th>CNS</th>
                          <th>CPF</th>
                          <th>Consultas</th>
                        </tr>
                      </thead>
                      <tbody>
                        {eq.pacientes.map((p, pi) => (
                          <tr key={pi}>
                            <td className="font-medium">{p.nome}</td>
                            <td className="font-mono text-xs">{p.cns}</td>
                            <td className="font-mono text-xs">{p.cpf}</td>
                            <td>{p.total_consultas_no_periodo ?? "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 italic">Sem pacientes nesta equipe.</p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function TabelaPacientes({ pacientes }) {
  if (!pacientes?.length) return <p className="text-sm text-gray-500 italic">Nenhum paciente identificado.</p>;

  const [filtro, setFiltro] = useState("");
  const filtrados = filtro
    ? pacientes.filter((p) => p.nome?.toLowerCase().includes(filtro.toLowerCase()) || p.unidade_saude?.toLowerCase().includes(filtro.toLowerCase()))
    : pacientes;

  return (
    <div>
      <input
        type="text"
        placeholder="Buscar por nome ou unidade..."
        className="input input-bordered input-sm rounded-xl w-full max-w-xs mb-2"
        value={filtro}
        onChange={(e) => setFiltro(e.target.value)}
      />
      <div className="overflow-x-auto rounded-xl border border-amber-200">
        <table className="table table-zebra w-full">
          <thead className="bg-amber-600 text-white">
            <tr>
              <th>Unidade</th>
              <th>Paciente</th>
              <th>CNS</th>
              <th>CPF</th>
              <th>Nascimento</th>
            </tr>
          </thead>
          <tbody>
            {filtrados.map((p, i) => (
              <tr key={i}>
                <td className="text-xs">{p.unidade_saude}</td>
                <td className="font-medium">{p.nome}</td>
                <td className="font-mono text-xs">{p.cns}</td>
                <td className="font-mono text-xs">{p.cpf}</td>
                <td className="text-xs">{(p.data_nascimento?.substring(0,10) || "").split("-").reverse().join("/") || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-1">{filtrados.length} registro(s)</p>
    </div>
  );
}

function ClassBadge2({ v }) {
  const m = {
    "Ótimo": "badge-success",
    "Bom": "badge-info",
    "Suficiente": "badge-warning",
    "Regular": "badge-error",
    "Sem dados": "badge-ghost",
  };
  return <span className={`badge badge-sm ${m[v] || "badge-ghost"}`}>{v}</span>;
}
