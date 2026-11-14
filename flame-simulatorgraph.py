import json
import math
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Flame in Freefall", page_icon="🔥", layout="wide")
st.markdown(
    "<style>.stApp{background:#020617;color:#e2e8f0}"
    "[data-testid=stSidebar]{background:#0f172a}"
    "[data-testid=stMetric]{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:12px}"
    "</style>",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------- model
FUELS = {  # class, quiescent-ish limiting O2 %, spread scale (mm/s equiv.)
    "PMMA": ("Solid", 15, 1.0), "Nomex": ("Solid", 17, 1.8), "Sibal": ("Solid", 16, 3.0),
    "Heptane": ("Liquid", 15, 4), "Methanol": ("Liquid", 12, 3),
    "Methane": ("Gas", 14, 8), "Propane": ("Gas", 15, 9),
}
DIL = {"N2": (0.0, 5), "CO2": (1.5, 15), "He": (2.0, 8)}  # LOC shift, suppression bonus
PRESETS = {
    "ISS": dict(o2=21.0, flow=10.0, p=1.0, fuel="PMMA", dil="N2"),
    "Artemis Lunar Base": dict(o2=34.0, flow=5.0, p=0.55, fuel="Nomex", dil="N2"),
    "Mars Transit": dict(o2=26.5, flow=8.0, p=0.70, fuel="Sibal", dil="N2"),
}
COLS = ["id", "proj", "obj", "fuel", "shape", "o2", "flow", "p", "dil", "sensors", "outcome", "why"]
BASE = [
    ("FLEX-M-N2", "FLEX", "Find limiting oxygen index (LOI) of methanol droplets in O2/N2", "Methanol", "Droplet, 1.5-4 mm dia", 12, 0, 1, "N2", "Backlit droplet camera, flame imager (CIR), radiometer", "Quasi-steady burn down to LOI ~12% O2", "Lowest sustained O2 for a liquid fuel: oxygen enrichment erodes margin fast."),
    ("FLEX-H-N2", "FLEX", "Find LOI of heptane droplets; cool-flame regime", "Heptane", "Droplet, 1.5-4 mm dia", 15, 0, 1, "N2", "Droplet camera, flame imager, radiometer", "Visible flame extinguished; cool flame persisted. LOI ~15% O2", "Cool flames can outlive visible flames, so a dark fire may still be a fire."),
    ("FLEX-M-He", "FLEX", "Methanol droplet burning in He-diluted air", "Methanol", "Droplet, 1.5-4 mm dia", 14, 0, 1, "He", "Droplet camera, flame imager", "LOI ~14% O2 (He in air, 1 atm)", "Helium raises the O2 needed to sustain burning: a modest suppressant in 1 atm air."),
    ("FLEX-H-He", "FLEX", "Heptane droplet burning in He-diluted air", "Heptane", "Droplet, 1.5-4 mm dia", 15, 0, 1, "He", "Droplet camera, flame imager", "LOI ~15% O2 (He in air, 1 atm)", "Diluent effect depends on fuel; heptane LOI barely moved with He."),
    ("FLEX-M-CO2", "FLEX", "Methanol droplets in O2/N2/CO2 at reduced pressure", "Methanol", "Droplet, 1.5-4 mm dia", 13, 0, 0.7, "CO2", "Droplet camera, flame imager", "Sustained to LOI ~12-13% O2 (0.7 atm, CO2 0-70%)", "Relevant to ISS CO2 extinguishers and low-pressure exploration cabins."),
    ("BASS2-PMMA-1", "BASS-II", "Flame spread over PMMA in low-speed flow", "PMMA", "Slab, 1 cm thick", 21, 8, 1, "N2", "Thermocouples, IR camera, radiometers, visible camera", "Sustained spread", "Thick plastics still spread in microgravity at ISS-like air."),
    ("BASS2-PMMA-2", "BASS-II", "Extinction limit of PMMA vs O2", "PMMA", "Slab, 1 cm thick", 14, 5, 1, "N2", "Thermocouples, IR camera, radiometers", "Extinguished (below LOC)", "Brackets the PMMA oxygen limit for exploration atmosphere margins."),
    ("BASS2-PMMA-CO2", "BASS-II", "CO2 suppression of PMMA flame", "PMMA", "Cylinder, 2 cm dia", 21, 10, 1, "CO2", "Thermocouples, radiometers, visible camera", "Extinguished with CO2 dilution", "Direct evidence on CO2 extinguishment of solid-fuel fires."),
    ("BASS2-SIBAL-1", "BASS-II", "Flame spread over thin SIBAL fabric", "Sibal", "Sheet, 5 x 25 cm", 21, 20, 1, "N2", "Thermocouples, IR camera, radiometers", "Sustained, fast spread", "Thin cotton-fiberglass fabric is the worst case for textiles."),
    ("BASS2-SIBAL-2", "BASS-II", "Low-flow quenching of SIBAL", "Sibal", "Sheet, 5 x 25 cm", 17, 2, 1, "N2", "Thermocouples, IR camera", "Extinguished at low flow", "Low ventilation can quench thin fuels, but only in a narrow window."),
    ("BASS2-NOMEX-1", "BASS-II", "Nomex flame spread at elevated O2", "Nomex", "Sheet, 5 x 25 cm", 25, 20, 1, "N2", "Thermocouples, radiometers, camera", "Sustained spread", "Fire-resistant fabric burns once O2 is raised: key for 25-34% O2 habitats."),
    ("SAME-1", "SAME", "Smoke particle size from overheated Teflon and Kapton", "Teflon/Kapton", "Wire-coiled sample", 21, 5, 1, "N2", "Smoke aerosol sensors, P-Trak, dust sampler", "No flame; smoke size distributions measured", "Detector thresholds tuned on Earth smoke may under-detect microgravity particles."),
    ("SAME-2", "SAME", "Smoke from overheated cotton and silicone rubber", "Cotton/Silicone", "Wire-coiled sample", 21, 5, 1, "N2", "Smoke aerosol sensors, P-Trak", "No flame; smoke size distributions measured", "Detectors must cover both soot and droplet aerosols."),
    ("SAFFIRE-I", "SAFFIRE", "Large-scale fire growth over a 0.4 x 1 m fabric", "Sibal", "Sheet, 40 x 100 cm", 21, 20, 1, "N2", "Thermocouples, radiometers, video, O2 and CO sensors", "Sustained; flame spread and heat release measured", "Only large-scale microgravity fire data; validates scaling from bench tests."),
    ("SAFFIRE-III", "SAFFIRE", "Large fire growth in elevated-O2 cabin air", "Sibal", "Sheet, 40 x 100 cm", 25, 20, 0.7, "N2", "Thermocouples, radiometers, video, gas sensors", "Sustained; faster spread at higher O2", "Tests the exploration-atmosphere assumption at large scale."),
]
SUGGESTIONS = [
    "Which diluent gas suppresses droplet flames fastest in microgravity?",
    "How does low ventilation affect flame spread on solid fuels?",
    "Which investigations cover smoke detection?",
    "What did SAFFIRE show at large scale?",
]


def loc_o2(fuel, dil, p, v):
    cls, base, _ = FUELS[fuel]
    low = 3 * math.exp(-v / 3) if cls == "Solid" else 0
    return base + DIL[dil][0] + 2.5 * (1 - p) + low + 0.04 * max(0, v - 15)


def model(o2, flow, p, fuel, dil):
    cls, _, k = FUELS[fuel]
    L = loc_o2(fuel, dil, p, flow)
    m = o2 - L
    spread = 0.0 if m <= 0 else k * (m / max(21 - L, 2)) ** 0.8 * (0.6 + 0.4 * min(1, flow / 10)) * p ** 0.3
    score = min(100, max(0, 50 - m * 4 + DIL[dil][1]))
    level, color = ("SAFE", "#10b981") if m < 0 else ("ELEVATED", "#f59e0b") if m < 8 else ("CRITICAL", "#ef4444")
    return dict(L=L, m=m, spread=spread, score=score, level=level, color=color, cls=cls)


def fuel_key(name):
    return next((k for k in FUELS if k.lower() in str(name).lower()), None)


def outcome_class(txt):
    if re.search(r"extingu|quench|below", txt, re.I):
        return "ext"
    if re.search(r"smoke|aerosol|no flame", txt, re.I):
        return "smoke"
    return "sus"


def relevance(r, s):
    fk = fuel_key(r["fuel"])
    fm = 1 if fk == s["fuel"] else 0.5 if fk and FUELS[fk][0] == FUELS[s["fuel"]][0] else 0
    dm = 1 if r["dil"] == s["dil"] else 0.4
    dist = (0.35 * min(1, abs(r["o2"] - s["o2"]) / 30) + 0.25 * min(1, abs(r["flow"] - s["flow"]) / 30)
            + 0.1 * min(1, abs(r["p"] - s["p"]) / 0.8) + 0.2 * (1 - fm) + 0.1 * (1 - dm))
    return round((1 - dist) * 100)


# ---------------------------------------------------------------- ingestion
ALIASES = {
    "id": ["id", "investigation", "run", "name"], "proj": ["project", "proj", "experiment"],
    "obj": ["objective", "obj", "title"], "fuel": ["fuel", "material", "sample"],
    "shape": ["shape", "size", "sample_shape"], "o2": ["o2", "oxygen", "o2_pct", "oxygen_pct"],
    "flow": ["flow", "airflow", "velocity", "flow_cm_s", "airflow_cm_s"],
    "p": ["pressure", "p", "pressure_atm"], "dil": ["diluent", "diluent_gas", "dil"],
    "sensors": ["sensors", "diagnostics"], "outcome": ["outcome", "result", "extinction"],
    "note": ["note", "notes", "readme", "summary"],
}


def normalize(rows):
    out = []
    for i, raw in enumerate(rows):
        lo = {str(k).lower().strip(): v for k, v in raw.items()}
        g = lambda key: next((lo[a] for a in ALIASES[key] if lo.get(a) not in (None, "")), None)
        try:
            o2 = float(g("o2"))
        except (TypeError, ValueError):
            continue
        note = g("note") or ""
        outcome = str(g("outcome") or "Not stated")
        out.append(dict(
            id=str(g("id") or f"UPLOAD-{i + 1}"), proj=str(g("proj") or "Uploaded"), obj=str(g("obj") or "(not stated)"),
            fuel=str(g("fuel") or "Unknown"), shape=str(g("shape") or "-"), o2=o2,
            flow=float(g("flow") or 0), p=float(g("p") or 1), dil=str(g("dil") or "N2").replace("\u2082", "2"),
            sensors=str(g("sensors") or "-"), outcome=outcome, why=str(note or outcome)))
    return pd.DataFrame(out, columns=COLS)


def load_upload(f):
    if f.name.lower().endswith(".json"):
        j = json.load(f)
        rows = j if isinstance(j, list) else j.get("records") or j.get("investigations") or j.get("data") or []
    else:
        rows = pd.read_csv(f).to_dict("records")
    df = normalize(rows)
    if df.empty:
        raise ValueError("no usable rows (need at least an O2 column)")
    return df


# ------------------------------------------------------------------ copilot
STOP = set("the a an of in on and or to how does what which is are for with at by did show about fastest most".split())
SYN = {"droplet": ["droplet", "methanol", "heptane"], "diluent": ["co2", "he", "n2", "diluent"],
       "suppress": ["co2", "he", "diluent", "extinguished", "loi"], "ventilation": ["flow", "airflow"],
       "airflow": ["flow"], "solid": ["pmma", "nomex", "sibal", "slab", "sheet"],
       "smoke": ["smoke", "aerosol", "detector"], "detection": ["smoke", "aerosol"], "detectors": ["smoke", "aerosol"],
       "large": ["saffire"], "helium": ["he"], "carbon": ["co2"], "nitrogen": ["n2"], "fabric": ["sibal", "nomex", "cotton"]}


def answer(q, df):
    ql = q.lower()
    toks = [w for w in re.findall(r"[a-z0-9]+", ql) if w not in STOP]
    toks = list(dict.fromkeys(t for w in toks for t in [w, *SYN.get(w, [])]))
    scored = []
    for _, r in df.iterrows():
        hay = " ".join(str(r[c]) for c in ["id", "proj", "obj", "fuel", "shape", "dil", "sensors", "outcome", "why"]).lower()
        s = sum(t in hay for t in toks)
        if s:
            scored.append((s, r))
    if not scored:
        return "No loaded investigation matches. Try a fuel, diluent, project (FLEX, BASS-II, SAME, SAFFIRE) or variable."
    scored.sort(key=lambda x: -x[0])
    out = []
    if re.search(r"diluent|suppress|extinguish|helium|co2|carbon", ql):
        best = {}
        for _, r in df.iterrows():
            if (outcome_class(r["outcome"]) == "sus" and r["flow"] == 0) or r["proj"] == "FLEX":
                if r["dil"] not in best or r["o2"] < best[r["dil"]]["o2"]:
                    best[r["dil"]] = r
        e = sorted(best.items(), key=lambda kv: -kv[1]["o2"])
        if e:
            lst = ", ".join(f"{k} {d['o2']:g}% [{d['id']}]" for k, d in e)
            out.append(f"**Finding:** lowest O2 at which flames were still sustained: {lst}. A higher floor means flames die sooner, "
                       f"so **{e[0][0]}** looks most suppressive here. Pressure and fuel differ between rows: screening comparison only.")
    elif re.search(r"flow|ventilation|velocity|spread", ql):
        sol = df[df["fuel"].map(lambda f: fuel_key(f) is not None and FUELS[fuel_key(f)][0] == "Solid")].sort_values("flow")
        if len(sol):
            lst = "; ".join(f"{r['flow']:g} cm/s -> {'extinguished' if outcome_class(r['outcome']) == 'ext' else 'sustained'} [{r['id']}]" for _, r in sol.iterrows())
            out.append(f"**Finding:** solid-fuel runs by airflow: {lst}. Quenching appears only at the lowest flows or O2; above ~5-10 cm/s spread is generally sustained.")
    for _, r in [x for x in scored[:4]]:
        out.append(f"- `[{r['id']}]` {r['obj']}  \n  fuel={r['fuel']} | O2={r['o2']:g}% | flow={r['flow']:g} cm/s | p={r['p']:g} atm | diluent={r['dil']} | outcome: {r['outcome']}")
    return "\n\n".join(out)


# --------------------------------------------------------------------- state
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(BASE, columns=COLS)
    st.session_state.chat = []
    st.session_state.update(env="ISS", **PRESETS["ISS"])


def apply_preset(name):
    st.session_state.update(env=name, **PRESETS[name])


def to_custom():
    st.session_state.env = "Custom"


df = st.session_state.data

# ------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### HABITAT SIMULATOR")
    c = st.columns(2)
    for i, name in enumerate(PRESETS):
        c[i % 2].button(name, on_click=apply_preset, args=(name,), use_container_width=True)
    c[1].button("Custom", on_click=to_custom, use_container_width=True)
    st.caption(f"Active: **{st.session_state.env}**")
    st.slider("O2 concentration (%)", 15.0, 85.0, key="o2", step=0.5, on_change=to_custom)
    st.slider("Airflow velocity (cm/s)", 0.0, 30.0, key="flow", step=0.5, on_change=to_custom)
    st.slider("Pressure (atm)", 0.3, 1.5, key="p", step=0.01, on_change=to_custom)
    st.selectbox("Fuel", list(FUELS), key="fuel", format_func=lambda k: f"{k} ({FUELS[k][0]})", on_change=to_custom)
    st.selectbox("Diluent gas", list(DIL), key="dil", on_change=to_custom)
    st.caption("Surrogate model anchored on FLEX LOI values; for triage, not certification.")

S = {k: st.session_state[k] for k in ("o2", "flow", "p", "fuel", "dil")}
M = model(**S)

st.title("🔥 Flame in Freefall")
st.caption(f"PSI fire-safety mission control · {len(df)} records loaded")
t1, t2, t3 = st.tabs(["1 · Risk Explorer", "2 · Ranker & Comparator", "3 · Ask PSI & Data"])

# ---------------------------------------------------------------------- tab 1
with t1:
    k = st.columns(4)
    k[0].metric("Limiting O2 (LOC)", f"{M['L']:.1f}%")
    k[1].metric("Flame spread", f"{M['spread']:.2f} mm/s", help="Equivalent front speed for liquid/gas fuels")
    k[2].metric("Suppression score", f"{M['score']:.0f}/100")
    k[3].metric("Risk level", M["level"], f"{M['m']:+.1f} pts O2 vs limit", delta_color="off")

    vs = list(range(0, 31))
    xb = [min(85, max(10, loc_o2(S["fuel"], S["dil"], S["p"], v))) for v in vs]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[10] * 31 + xb[::-1], y=vs + vs[::-1], fill="toself", fillcolor="rgba(16,185,129,.13)",
                             line=dict(width=0), hoverinfo="skip", name="Safe zone"))
    fig.add_trace(go.Scatter(x=[85] * 31 + xb[::-1], y=vs + vs[::-1], fill="toself", fillcolor="rgba(239,68,68,.13)",
                             line=dict(width=0), hoverinfo="skip", name="Ignition / spread risk"))
    fig.add_trace(go.Scatter(x=xb, y=vs, mode="lines", line=dict(color="#fbbf24", dash="dash", width=2), name="Boundary"))
    names = {"sus": ("Burn sustained", "#f59e0b"), "ext": ("Extinguished", "#10b981"), "smoke": ("Smoke / no flame", "#38bdf8")}
    cl = df["outcome"].map(outcome_class)
    for key, (label, col) in names.items():
        d = df[cl == key]
        if len(d):
            fig.add_trace(go.Scatter(x=d["o2"].clip(10, 85), y=d["flow"].clip(0, 30), mode="markers", name=label,
                                     marker=dict(size=11, color=col, line=dict(color="#020617", width=1)),
                                     text=d["id"] + ": " + d["fuel"] + ", " + d["outcome"], hoverinfo="text"))
    fig.add_trace(go.Scatter(x=[S["o2"]], y=[S["flow"]], mode="markers", name="Your habitat",
                             marker=dict(size=18, color=M["color"], symbol="circle", line=dict(color="white", width=3))))
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0f172a", plot_bgcolor="#0f172a", height=460,
                      xaxis=dict(title="O2 concentration (%)", range=[10, 85]), yaxis=dict(title="Airflow (cm/s)", range=[-1, 31]),
                      margin=dict(l=40, r=10, t=20, b=40))
    st.plotly_chart(fig, use_container_width=True)

    adv = [f"O2 is {-M['m']:.1f} points below the {M['L']:.1f}% limit for {S['fuel']}: sustained burning is not predicted."
           if M["m"] < 0 else f"{S['fuel']} can sustain a flame here, {M['m']:.1f} points above its limit."]
    if S["o2"] > 21:
        adv.append(f"Enriched O2 ({S['o2']:g}%) is the largest driver of spread; screening at 21% may not be conservative.")
    if S["p"] < 1:
        adv.append(f"Reduced pressure shifts the limit; ppO2 = {S['o2'] / 100 * S['p']:.3f} atm.")
    if M["cls"] == "Solid" and S["flow"] < 3:
        adv.append("Very low airflow can quench thin solids, but even slow drift restores spread.")
    if S["dil"] == "N2":
        adv.append("Switching diluent to CO2 or He raises the limiting O2 in this model (see FLEX rows).")
    st.markdown("**Actionable insights**\n" + "\n".join(f"- {a}" for a in adv))

# ---------------------------------------------------------------------- tab 2
with t2:
    st.subheader("SI relevance ranker")
    rk = df.assign(score=df.apply(lambda r: relevance(r, S), axis=1)).sort_values("score", ascending=False).head(6)
    for _, r in rk.iterrows():
        a, b = st.columns([1, 6])
        a.markdown(f"### {r['score']}%")
        b.markdown(f"**{r['id']}** · {r['proj']} · {r['fuel']} · {r['o2']:g}% O2 · {r['flow']:g} cm/s · {r['dil']}  \n{r['why']}")
    st.subheader("Experiment diff")
    ids = df["id"].tolist()
    c1, c2 = st.columns(2)
    a_id = c1.selectbox("Run A", ids, index=0)
    b_id = c2.selectbox("Run B", ids, index=min(1, len(ids) - 1))
    A, B = df[df["id"] == a_id].iloc[0], df[df["id"] == b_id].iloc[0]
    rows = [("Experimental objective", "obj"), ("Fuel sample", "fuel"), ("Shape / size", "shape"), ("O2 (%)", "o2"),
            ("Airflow (cm/s)", "flow"), ("Pressure (atm)", "p"), ("Diluent", "dil"), ("Sensors used", "sensors"),
            ("Extinction outcome", "outcome")]
    diff = pd.DataFrame({"Parameter": [n for n, _ in rows], a_id: [str(A[c]) for _, c in rows], b_id: [str(B[c]) for _, c in rows]})
    st.dataframe(diff.style.apply(lambda r: ["background:#78350f55" if r[a_id] != r[b_id] else "" for _ in r], axis=1),
                 use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------- tab 3
with t3:
    st.subheader("Ask PSI copilot")
    qcols = st.columns(len(SUGGESTIONS))
    picked = None
    for i, s in enumerate(SUGGESTIONS):
        if qcols[i].button(s, key=f"sg{i}"):
            picked = s
    q = st.chat_input("Ask about fuels, diluents, airflow, smoke, or an investigation ID") or picked
    if q:
        st.session_state.chat.insert(0, (q, answer(q, df)))
    for qq, aa in st.session_state.chat:
        with st.container(border=True):
            st.markdown(f"**Q: {qq}**")
            st.markdown(aa)

    st.subheader("Data ingestion")
    st.caption("Upload nasa_summary.json or a PSI .csv. Columns: id, project, objective, fuel, shape, o2, flow (cm/s), "
               "pressure (atm), diluent, sensors, outcome, note. JSON: an array or {\"records\": [...]}.")
    up = st.file_uploader("Drop file here", type=["json", "csv"])
    if up is not None and st.session_state.get("last_up") != (up.name, up.size):
        try:
            st.session_state.data = load_upload(up)
            st.session_state.last_up = (up.name, up.size)
            st.success(f"Loaded {len(st.session_state.data)} records from {up.name}")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not parse {up.name}: {e}")
    if st.button("Reset to baseline"):
        st.session_state.data = pd.DataFrame(BASE, columns=COLS)
        st.session_state.pop("last_up", None)
        st.rerun()
    st.dataframe(df.drop(columns=["why"]), use_container_width=True, hide_index=True)
