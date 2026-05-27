import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import ErrorBoundary from "./components/ErrorBoundary";
import IndicadorC1 from "./pages/IndicadorC1";
import IndicadorC2 from "./pages/IndicadorC2";
import IndicadorC3 from "./pages/IndicadorC3";
import IndicadorC4 from "./pages/IndicadorC4";
import IndicadorC5 from "./pages/IndicadorC5";
import IndicadorC6 from "./pages/IndicadorC6";
import IndicadorC7 from "./pages/IndicadorC7";
import IndicadorB1 from "./pages/IndicadorB1";
import IndicadorB2 from "./pages/IndicadorB2";
import IndicadorB3 from "./pages/IndicadorB3";
import IndicadorB4 from "./pages/IndicadorB4";
import IndicadorB5 from "./pages/IndicadorB5";
import IndicadorB6 from "./pages/IndicadorB6";
import IndicadorM1 from "./pages/IndicadorM1";
import IndicadorM2 from "./pages/IndicadorM2";
import Inconsistencias from "./pages/Inconsistencias";
import Estrangeiros from "./pages/Estrangeiros";
import Indigenas from "./pages/Indigenas";
import MoradorRua from "./pages/MoradorRua";
import Deficiencias from "./pages/Deficiencias";
import BolsaFamilia from "./pages/BolsaFamilia";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/indicadores/c1", label: "C1 Mais Acesso" },
  { to: "/indicadores/c2", label: "C2 Desenv. Infantil" },
  { to: "/indicadores/c3", label: "C3 Gestação/Puerpério" },
  { to: "/indicadores/c4", label: "C4 Diabetes" },
  { to: "/indicadores/c5", label: "C5 Hipertensão" },
  { to: "/indicadores/c6", label: "C6 Idoso" },
  { to: "/indicadores/c7", label: "C7 Prevenção Câncer" },
  { to: "/indicadores/b1", label: "B1 1ª Consulta" },
  { to: "/indicadores/b2", label: "B2 Trat. Concluído" },
  { to: "/indicadores/b3", label: "B3 Exodontia" },
  { to: "/indicadores/b4", label: "B4 Escovação" },
  { to: "/indicadores/b5", label: "B5 Preventivos" },
  { to: "/indicadores/b6", label: "B6 TRA/ART" },
  { to: "/indicadores/m1", label: "M1 Média eMulti" },
  { to: "/indicadores/m2", label: "M2 Ações eMulti" },
  { to: "/inconsistencias", label: "Inconsistências" },
  { to: "/estrangeiros", label: "Estrangeiros" },
  { to: "/indigenas", label: "Indígenas" },
  { to: "/morador-rua", label: "Morador de Rua" },
  { to: "/deficiencias", label: "Deficiências" },
  { to: "/bolsa-familia", label: "Bolsa Família" },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <header className="bg-teal-700 text-white shadow-md">
          <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
            <h1 className="text-lg font-bold">APS Goianira</h1>
          </div>
          <nav className="max-w-7xl mx-auto px-4 pb-2 flex gap-2 text-sm flex-wrap">
            {NAV.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `px-2 py-1 rounded transition-colors whitespace-nowrap ${
                    isActive
                      ? "bg-white text-teal-800 font-semibold"
                      : "text-teal-100 hover:bg-teal-600"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </header>
        <main className="flex-1 max-w-7xl mx-auto w-full p-4">
          <Routes>
            <Route path="/" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
            <Route path="/indicadores/c1" element={<IndicadorC1 />} />
            <Route path="/indicadores/c2" element={<IndicadorC2 />} />
            <Route path="/indicadores/c3" element={<IndicadorC3 />} />
            <Route path="/indicadores/c4" element={<IndicadorC4 />} />
            <Route path="/indicadores/c5" element={<IndicadorC5 />} />
            <Route path="/indicadores/c6" element={<IndicadorC6 />} />
            <Route path="/indicadores/c7" element={<IndicadorC7 />} />
            <Route path="/indicadores/b1" element={<IndicadorB1 />} />
            <Route path="/indicadores/b2" element={<IndicadorB2 />} />
            <Route path="/indicadores/b3" element={<IndicadorB3 />} />
            <Route path="/indicadores/b4" element={<IndicadorB4 />} />
            <Route path="/indicadores/b5" element={<IndicadorB5 />} />
            <Route path="/indicadores/b6" element={<IndicadorB6 />} />
            <Route path="/indicadores/m1" element={<IndicadorM1 />} />
            <Route path="/indicadores/m2" element={<IndicadorM2 />} />
            <Route path="/inconsistencias" element={<Inconsistencias />} />
            <Route path="/estrangeiros" element={<Estrangeiros />} />
            <Route path="/indigenas" element={<Indigenas />} />
            <Route path="/morador-rua" element={<MoradorRua />} />
            <Route path="/deficiencias" element={<Deficiencias />} />
            <Route path="/bolsa-familia" element={<BolsaFamilia />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
