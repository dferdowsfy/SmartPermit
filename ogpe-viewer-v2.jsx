import React, { useState } from "react";
import {
  Landmark, Upload, FileText, LogOut, ArrowLeft, Download, Check,
  AlertTriangle, AlertCircle, Info, Loader2, ClipboardList, ChevronLeft, ChevronRight,
} from "lucide-react";

/* ------------------------------------------------------------------ *
 *  OGPe AI Plan Review — v2
 *  - Upload screen reads PRE-LOADED code sets and lets the user pick one
 *  - Viewer is Apple-Preview style: focal page + thumbnail rail with
 *    per-page annotation marks; markers overlay the focal page; clicking
 *    a marker / thumbnail / list item keeps all three in sync.
 *  In production the page images + manifest come from the PyMuPDF backend
 *  (GET /api/code-sets, POST /api/review, /files/{id}/page-NN.png).
 * ------------------------------------------------------------------ */

// Pre-loaded code sets (mirrors backend GET /api/code-sets)
const CODE_SETS = [
  { id: "prrc_2018", name: "PRRC 2018", desc: "Puerto Rico Residential Code (2018 IRC + PR amendments)" },
  { id: "prbc_2018", name: "PRBC 2018", desc: "Puerto Rico Building Code (2018 IBC + PR wind/seismic)" },
  { id: "unified_pr", name: "Unified Puerto Rico Code", desc: "PRRC + PRBC, San Juan jurisdiction" },
];

// Mirrors backend manifest: pages with baked-in marks + marker overlay coords.
const SHEETS = [
  { page: 1, label: "G-001", title: "Cover & Index" },
  { page: 2, label: "A-101", title: "Main Floor Plan" },
  { page: 3, label: "A-301", title: "Elevations" },
  { page: 4, label: "S-001", title: "Structural Notes" },
  { page: 5, label: "S-007", title: "Sections & Details" },
  { page: 6, label: "A-501", title: "Stair Details" },
  { page: 7, label: "A-601", title: "Window Schedule" },
  { page: 8, label: "C-001", title: "Site Plan" },
];

const FINDINGS = [
  { id: "HF-01", sev: "High", page: 1, title: "Missing professional seal", code: "PRBC 107 / CIAPR", bbox: [0.62, 0.74, 0.90, 0.90], evidence: "No CIAPR seal/signature/date in any title block.", correction: "Apply a CIAPR-licensed seal, signature, and date to every sheet." },
  { id: "HF-02", sev: "High", page: 1, title: "Architectural set incomplete", code: "PRBC 107.2", bbox: [0.08, 0.50, 0.45, 0.62], evidence: "Index lists sheets; full architectural set not submitted.", correction: "Submit the complete architectural set matching the index." },
  { id: "LF-03", sev: "Low", page: 1, title: "Drawing index mismatch", code: "QA", bbox: [0.08, 0.62, 0.45, 0.72], evidence: "Index lists sheets not present in the package.", correction: "Reconcile the index with the submitted sheets." },
  { id: "HF-07", sev: "High", page: 2, title: "EERO not verifiable", code: "PRRC R310", bbox: [0.10, 0.18, 0.45, 0.32], evidence: "Bedroom 2 = Fixed Glass 36x72; no net-clear-opening tabulated.", correction: "Add net-clear-opening + sill columns; provide a compliant operable EERO per bedroom." },
  { id: "MF-05", sev: "Medium", page: 2, title: "Garage/dwelling separation incomplete", code: "IRC R302.6", bbox: [0.10, 0.40, 0.45, 0.52], evidence: "Habitable room above garage; no 5/8\" Type X ceiling.", correction: "Call out 5/8\" Type X garage ceiling + protected penetrations." },
  { id: "HF-06", sev: "High", page: 2, title: "Dwelling unit count ambiguous", code: "PRRC R202", bbox: [0.10, 0.55, 0.50, 0.70], evidence: "Second kitchen + separable lower level; unit count unstated.", correction: "State unit count; if two units, show separation + independent egress." },
  { id: "HF-08", sev: "High", page: 3, title: "Windborne-debris protection not shown", code: "PRBC 1609.2", bbox: [0.30, 0.12, 0.72, 0.30], evidence: "Large fixed glazing, no shutters; San Juan is in the debris region.", correction: "Add an opening-protection schedule with per-opening design pressures." },
  { id: "HF-09", sev: "High", page: 4, title: "Seismic design category not stated", code: "ASCE 7 / PRBC 1613", bbox: [0.10, 0.20, 0.50, 0.32], evidence: "Notes say 'Seismic Zone C'; no site Ss/S1 or SDC.", correction: "Provide Ss/S1, derive SDC, show lateral + ACI 318 Ch.18 detailing." },
  { id: "MF-01", sev: "Medium", page: 4, title: "Wind speed not PR basis", code: "PRBC 1609", bbox: [0.10, 0.30, 0.55, 0.42], evidence: "Notes say 76/90 mph; PR is ~145-170 mph ultimate.", correction: "Re-state design wind speed from the PR map / ASCE 7 Hazard Tool." },
  { id: "MF-03", sev: "Medium", page: 4, title: "Corrosion-resistant connectors missing", code: "PRBC amendment", bbox: [0.10, 0.40, 0.55, 0.52], evidence: "'STD GALVANIZED' connectors for exposed members.", correction: "Upgrade exposed connectors/anchors to the required corrosion class." },
  { id: "MF-06", sev: "Medium", page: 4, title: "Energy compliance not Zone 1A", code: "IECC 2018 1A", bbox: [0.10, 0.52, 0.55, 0.62], evidence: "Cold-climate carryovers (ground snow 71 psf).", correction: "Re-run energy for Zone 1A; remove snow/cold-climate items." },
  { id: "HF-05", sev: "High", page: 5, title: "Guardrail design missing", code: "IRC R312", bbox: [0.10, 0.14, 0.46, 0.30], evidence: "Balcony edge >30\" drop; 'no detail provided'.", correction: "Add a guard detail: 36\" min, infill <4\" sphere, 50 plf/200 lb loads." },
  { id: "LF-04", sev: "Low", page: 5, title: "Illustrative views not labeled", code: "QA", bbox: [0.10, 0.34, 0.45, 0.46], evidence: "Diagrammatic views not labeled 'not for construction'.", correction: "Label diagrammatic vs. for-construction views." },
  { id: "MF-04", sev: "Medium", page: 6, title: "Stair width below minimum", code: "IRC R311.7", bbox: [0.10, 0.14, 0.45, 0.26], evidence: "Stair note 'min width 34in'.", correction: "Correct note to 36\" minimum clear width." },
  { id: "LF-01", sev: "Low", page: 7, title: "Window schedule numbering gap", code: "QA", bbox: [0.10, 0.30, 0.45, 0.42], evidence: "Tags skip W1-19.", correction: "Confirm no window dropped; renumber or note the gap." },
  { id: "LF-02", sev: "Low", page: 7, title: "No net-clear-opening column", code: "QA / R310", bbox: [0.10, 0.44, 0.45, 0.56], evidence: "Schedule lacks a net-clear-opening column.", correction: "Add a net-clear-opening column to the window schedule." },
  { id: "MF-02", sev: "Medium", page: 8, title: "Flood zone determination absent", code: "PRBC App.G", bbox: [0.10, 0.20, 0.50, 0.34], evidence: "Coastal parcel; no FEMA zone or BFE shown.", correction: "Add flood determination; if SFHA show BFE + ASCE 24." },
];

const SEV = {
  High: { dot: "bg-red-600", text: "text-red-700", chip: "bg-red-50 text-red-700 border-red-200", icon: AlertTriangle },
  Medium: { dot: "bg-amber-500", text: "text-amber-700", chip: "bg-amber-50 text-amber-700 border-amber-200", icon: AlertCircle },
  Low: { dot: "bg-gray-400", text: "text-gray-600", chip: "bg-gray-100 text-gray-600 border-gray-300", icon: Info },
};
const COUNTS = { High: FINDINGS.filter(f=>f.sev==="High").length, Medium: FINDINGS.filter(f=>f.sev==="Medium").length, Low: FINDINGS.filter(f=>f.sev==="Low").length };

function GovTopBar() {
  return (
    <div className="w-full bg-emerald-900 text-white text-xs">
      <div className="mx-auto max-w-7xl px-4 py-1.5 flex items-center justify-between">
        <span className="tracking-wide">Gobierno de Puerto Rico</span><span className="text-emerald-200">.pr.gov</span>
      </div>
    </div>
  );
}
function Seal({ size = 40 }) {
  return <div className="rounded-full border-2 border-emerald-800 bg-emerald-50 flex items-center justify-center text-emerald-800 shrink-0" style={{ width: size, height: size }}><Landmark size={size*0.5}/></div>;
}
function SevBadge({ sev }) {
  const s = SEV[sev];
  return <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${s.chip}`}><span className={`h-1.5 w-1.5 rounded-full ${s.dot}`}/>{sev}</span>;
}
const inputCls = "w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600";

function AppHeader({ left, right }) {
  return (
    <>
      <GovTopBar/>
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">{left || (<><Seal/><div className="leading-tight"><p className="text-sm font-semibold text-emerald-800">Oficina de Gerencia de Permisos</p><p className="text-xs text-gray-500">AI Plan Review</p></div></>)}</div>
          <div className="flex items-center gap-4 text-sm">{right}</div>
        </div>
      </header>
    </>
  );
}

/* ----------------------------- Upload ----------------------------- */
const STEPS = [["Uploading documents","Subiendo documentos"],["Reading drawings","Leyendo planos"],["Checking applicable code sections","Verificando secciones de c\u00f3digo"],["Generating findings","Generando hallazgos"],["Creating annotated PDF","Creando PDF anotado"],["Preparing correction notice","Preparando notificaci\u00f3n"]];

function UploadScreen({ onRun, onLogout }) {
  const [codeSet, setCodeSet] = useState("unified_pr");
  const [step, setStep] = useState(-1);
  const running = step >= 0;
  React.useEffect(() => {
    if (step < 0) return;
    if (step >= STEPS.length) { const t = setTimeout(onRun, 450); return () => clearTimeout(t); }
    const t = setTimeout(() => setStep(s => s + 1), 800); return () => clearTimeout(t);
  }, [step]);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader right={<><span className="text-gray-600">Carlos Rivera, P.E.</span><button onClick={onLogout} className="inline-flex items-center gap-1 text-teal-700 hover:underline"><LogOut size={14}/>Logout</button></>}/>
      <main className="flex-1"><div className="mx-auto max-w-3xl px-4 py-8">
        <div className="rounded-lg border border-gray-200 bg-white p-6 sm:p-8 shadow-sm">
          <h2 className="text-xl font-bold text-gray-900">Submit Plans for AI Review</h2>
          <p className="text-sm text-gray-500">Someter planos para revisi\u00f3n AI</p>
          <p className="mt-3 text-sm text-gray-600">Upload the permit package PDF and pick a pre-loaded Puerto Rico code set. The system screens the drawings against that set and returns a preliminary correction notice with an annotated PDF.</p>

          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block"><span className="text-sm font-medium text-gray-800">Project Name</span><input className={`${inputCls} mt-1.5`} defaultValue="Modelo D"/></label>
            <label className="block"><span className="text-sm font-medium text-gray-800">Municipality / Municipio</span><input className={`${inputCls} mt-1.5`} defaultValue="San Juan"/></label>
            <label className="block"><span className="text-sm font-medium text-gray-800">Permit Type</span><select className={`${inputCls} mt-1.5`}><option>Construction</option><option>Use</option><option>Consolidated (PCOC)</option></select></label>
            <label className="block"><span className="text-sm font-medium text-gray-800">Project Type</span><select className={`${inputCls} mt-1.5`}><option>Residential</option><option>Commercial</option><option>Mixed Use</option></select></label>
          </div>

          {/* Pre-loaded code set picker */}
          <div className="mt-5">
            <span className="text-sm font-medium text-gray-800">Code Set / Conjunto de c\u00f3digos</span>
            <p className="text-xs text-gray-500">Pre-loaded \u2014 select the set to check the drawing against.</p>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-3">
              {CODE_SETS.map(cs => (
                <button key={cs.id} onClick={() => setCodeSet(cs.id)}
                  className={`text-left rounded-md border p-3 ${codeSet===cs.id ? "border-teal-700 ring-1 ring-teal-700 bg-teal-50/50" : "border-gray-300 bg-white hover:bg-gray-50"}`}>
                  <span className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-900">{cs.name}</span>
                    {codeSet===cs.id && <Check size={15} className="text-teal-700"/>}
                  </span>
                  <span className="mt-0.5 block text-xs text-gray-500">{cs.desc}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5">
            <span className="text-sm font-medium text-gray-800">Permit package (PDF)</span>
            <div className="mt-1.5 rounded-md border-2 border-dashed border-gray-300 bg-gray-50 px-6 py-8 text-center">
              <Upload className="mx-auto text-gray-400" size={24}/>
              <p className="mt-2 text-sm text-gray-600">Drag and drop PDF files here</p>
              <button className="mt-3 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">Choose File</button>
              <p className="mt-2 text-xs text-gray-400">modelo-d-permit-package.pdf</p>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button onClick={() => setStep(0)} disabled={running} className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50">
              {running ? <Loader2 size={16} className="animate-spin"/> : <ClipboardList size={16}/>}Run AI Review</button>
            <button disabled={running} className="rounded-md border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50">Clear Form</button>
            <span className="text-xs text-gray-400">Engine: Grok 4.20 (low) \u00b7 checking against <b className="text-gray-600">{CODE_SETS.find(c=>c.id===codeSet).name}</b></span>
          </div>

          {running && (
            <ul className="mt-6 space-y-2 rounded-md border border-gray-200 bg-gray-50 p-4">
              {STEPS.map(([en,es],i)=>{const done=i<step,active=i===step;return(
                <li key={en} className="flex items-center gap-2 text-sm">
                  {done?<Check size={16} className="text-emerald-700"/>:active?<Loader2 size={16} className="animate-spin text-teal-700"/>:<span className="h-4 w-4 rounded-full border border-gray-300"/>}
                  <span className={done?"text-gray-500":active?"text-gray-900 font-medium":"text-gray-400"}>{en} <span className="text-gray-400">/ {es}</span></span>
                </li>);})}
            </ul>
          )}
        </div>
      </div></main>
    </div>
  );
}

/* ------------------------ Preview-style Viewer ------------------------ */
function MockPage({ label, title, markers, activeId, onMarker }) {
  // a stand-in for the PyMuPDF-rendered page image; markers overlay by bbox
  return (
    <div className="relative w-full bg-white border border-gray-300 shadow-sm" style={{ aspectRatio: "11 / 8.5" }}>
      <div className="absolute inset-3 border border-gray-300">
        <div className="absolute inset-5 grid grid-cols-3 grid-rows-2 gap-3 opacity-50">
          <div className="border border-gray-300"/><div className="border border-gray-300 col-span-2"/>
          <div className="border border-gray-300 col-span-2"/><div className="border border-gray-300"/>
        </div>
        <div className="absolute bottom-0 right-0 w-44 border-l border-t border-gray-400 bg-gray-50 p-2 text-[9px] text-gray-500">
          <p className="font-bold text-gray-700">OFICINA DE GERENCIA DE PERMISOS</p>
          <p>Modelo D \u00b7 San Juan</p><p className="text-sm font-bold text-gray-900">{label}</p><p>{title}</p>
        </div>
      </div>
      {markers.map(m => {
        const [x0,y0,x1,y1] = m.bbox; const s = SEV[m.sev];
        const active = m.id === activeId;
        return (
          <div key={m.id} className="absolute" style={{ left:`${x0*100}%`, top:`${y0*100}%`, width:`${(x1-x0)*100}%`, height:`${(y1-y0)*100}%` }}>
            <div className={`absolute inset-0 border-2 ${active?"border-teal-600":""}`} style={{ borderColor: active ? undefined : (m.sev==="High"?"#dc2626":m.sev==="Medium"?"#f59e0b":"#9ca3af") }}/>
            <button onClick={()=>onMarker(m.id)} title={m.title}
              className={`absolute -top-3 left-0 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold text-white shadow ring-1 ring-white ${m.sev==="High"?"bg-red-600":m.sev==="Medium"?"bg-amber-500":"bg-gray-500"} ${active?"outline outline-2 outline-teal-600":""}`}>
              {m.id}
            </button>
          </div>
        );
      })}
    </div>
  );
}

function ViewerScreen({ onBack }) {
  const [pageNo, setPageNo] = useState(2);
  const [activeId, setActiveId] = useState("HF-07");
  const pageMarkers = FINDINGS.filter(f => f.page === pageNo);
  const sel = FINDINGS.find(f => f.id === activeId);
  const annByPage = SHEETS.map(s => ({ ...s, n: FINDINGS.filter(f=>f.page===s.page).length, hi: FINDINGS.some(f=>f.page===s.page && f.sev==="High") }));

  function selectPage(p) { setPageNo(p); const first = FINDINGS.find(f=>f.page===p); if (first) setActiveId(first.id); }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      <GovTopBar/>
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-3 flex items-center justify-between">
          <button onClick={onBack} className="inline-flex items-center gap-1.5 text-sm text-teal-700 hover:underline"><ArrowLeft size={16}/>Back to Results</button>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">Modelo D \u00b7 {COUNTS.High+COUNTS.Medium+COUNTS.Low} findings</span>
            <button className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800"><Download size={15}/>Download Annotated PDF</button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-4 py-4 grid grid-cols-1 lg:grid-cols-[120px_1fr_300px] gap-4">
          {/* Thumbnail rail (Preview-style) with per-page annotation marks */}
          <div className="rounded-lg border border-gray-200 bg-white p-2 self-start max-h-[660px] overflow-auto">
            <p className="px-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Pages</p>
            <ul className="space-y-2">
              {annByPage.map(s => (
                <li key={s.page}>
                  <button onClick={()=>selectPage(s.page)} className={`relative block w-full rounded border ${pageNo===s.page?"border-teal-600 ring-1 ring-teal-600":"border-gray-200 hover:border-gray-300"} bg-white p-1`}>
                    <div className="relative bg-gray-50 border border-gray-200" style={{ aspectRatio:"11 / 8.5" }}>
                      <div className="absolute inset-1 border border-gray-200"/>
                      <span className="absolute bottom-0.5 right-1 text-[8px] font-bold text-gray-500">{s.label}</span>
                      {/* annotation mark on the page thumbnail */}
                      {s.n > 0 && (
                        <span className={`absolute top-0.5 left-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[9px] font-bold text-white ${s.hi?"bg-red-600":"bg-amber-500"}`}>{s.n}</span>
                      )}
                    </div>
                    <span className="mt-1 block text-center text-[10px] text-gray-500">p{s.page}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Focal page */}
          <div className="rounded-lg border border-gray-200 bg-gray-200 p-4 shadow-inner">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button onClick={()=>selectPage(Math.max(1,pageNo-1))} className="rounded border border-gray-300 bg-white p-1 hover:bg-gray-50"><ChevronLeft size={16}/></button>
                <span className="text-sm font-medium text-gray-700">{SHEETS[pageNo-1].label} \u2014 {SHEETS[pageNo-1].title}</span>
                <button onClick={()=>selectPage(Math.min(SHEETS.length,pageNo+1))} className="rounded border border-gray-300 bg-white p-1 hover:bg-gray-50"><ChevronRight size={16}/></button>
              </div>
              <span className="text-xs text-gray-500">{pageMarkers.length} annotation{pageMarkers.length!==1?"s":""} on this page</span>
            </div>
            <div className="mx-auto max-w-3xl">
              <MockPage label={SHEETS[pageNo-1].label} title={SHEETS[pageNo-1].title} markers={pageMarkers} activeId={activeId} onMarker={setActiveId}/>
            </div>
          </div>

          {/* Detail + findings list */}
          <div className="space-y-4 self-start">
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-200 px-4 py-2 flex items-center justify-between"><span className="text-xs font-bold text-gray-900">Annotation Detail</span><span className="font-mono text-xs text-gray-500">{sel.id}</span></div>
              <div className="px-4 py-3 space-y-3">
                <div className="flex items-center gap-2"><SevBadge sev={sel.sev}/><span className="text-sm font-semibold text-gray-900">{sel.title}</span></div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div><dt className="uppercase tracking-wide text-gray-400">Page / Sheet</dt><dd className="text-gray-700">p{sel.page} \u00b7 {SHEETS[sel.page-1].label}</dd></div>
                  <div><dt className="uppercase tracking-wide text-gray-400">Code</dt><dd className="text-gray-700">{sel.code}</dd></div>
                </div>
                <div><dt className="text-xs uppercase tracking-wide text-gray-400">Evidence</dt><dd className="mt-0.5 text-sm text-gray-700">{sel.evidence}</dd></div>
                <div><dt className="text-xs uppercase tracking-wide text-gray-400">Required Correction</dt><dd className="mt-0.5 text-sm text-gray-700">{sel.correction}</dd></div>
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-200 px-4 py-2 text-xs font-bold text-gray-900">All Findings ({FINDINGS.length})</div>
              <ul className="divide-y divide-gray-100 max-h-[300px] overflow-auto">
                {FINDINGS.map(f => (
                  <li key={f.id}>
                    <button onClick={()=>{ setPageNo(f.page); setActiveId(f.id); }} className={`w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-gray-50 ${activeId===f.id?"bg-teal-50/60":""}`}>
                      <span className={`h-2 w-2 rounded-full ${SEV[f.sev].dot}`}/>
                      <span className="font-mono text-[11px] text-gray-500 w-12">{f.id}</span>
                      <span className="flex-1 truncate text-xs text-gray-700">{f.title}</span>
                      <span className="text-[10px] text-gray-400">p{f.page}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState("upload");
  return (
    <div className="font-sans text-gray-900 antialiased">
      <div className="fixed bottom-3 right-3 z-50 flex gap-1 rounded-md border border-gray-300 bg-white/95 p-1 text-xs shadow">
        {["upload","viewer"].map(s=>(<button key={s} onClick={()=>setScreen(s)} className={`rounded px-2 py-1 capitalize ${screen===s?"bg-teal-700 text-white":"text-gray-600 hover:bg-gray-100"}`}>{s}</button>))}
      </div>
      {screen==="upload" && <UploadScreen onRun={()=>setScreen("viewer")} onLogout={()=>setScreen("upload")}/>}
      {screen==="viewer" && <ViewerScreen onBack={()=>setScreen("upload")}/>}
    </div>
  );
}
