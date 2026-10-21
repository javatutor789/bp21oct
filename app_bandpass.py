"""
Narrow Bandpass Circuits - Configuration Tool
=============================================

Streamlit app that follows the "Python Program Tree" (Bandpass_Tree_Oct_16_26.pdf):

    Introduction page
      -> Narrow Bandpass Circuits
           Branch 1: Single Op Amp   (Non-Inverting / Inverting)
           Branch 2: Dual Op Amp
           Branch 3: Differential    (Single to Differential / Fully Differential)

Only the values CHOSEN / ENTERED by the user are saved (no limits, no
timestamps, no calculated values). Every save is appended to a CSV file on disk
and the details can be downloaded with a button.

Run:
    pip install streamlit pandas
    streamlit run app_bandpass.py
"""

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# 1. DECISION TREE (taken from the diagram, pages 1-4)
# ---------------------------------------------------------------------------
HZ, KHZ, MHZ = 1, 1_000, 1_000_000
FREQUENCY_UNITS = {"Hz": HZ, "kHz": KHZ, "MHz": MHZ}


@dataclass(frozen=True)
class GainOption:
    label: str                                   # text shown to the user
    f_max_hz: float                              # fcenter allowed: 1 Hz <= fcenter <= f_max_hz
    bw_pct: Tuple[float, float]                  # Pbandwidth as % of fcenter (low, high)
    gain_range_db: Optional[Tuple[float, float]] = None  # None -> fixed gain (e.g. 0 dB, 6 dB)

    @property
    def gain_is_range(self):
        return self.gain_range_db is not None

    @property
    def bw_is_range(self):
        return self.bw_pct[0] != self.bw_pct[1]


F_MIN_HZ = 1

# Page 2 - Branch 1: Single Op Amp (Non-Inverting and Inverting have the same limits)
_SINGLE_GAINS = [
    GainOption("Gain = 0 dB", 10 * MHZ, (10, 40)),
    GainOption("0 dB ≤ Gain ≤ 20 dB", 1 * MHZ, (10, 20), (0, 20)),
]

# Page 3 - Branch 2: Dual Op Amp
_DUAL_GAINS = [
    GainOption("Gain = 0 dB", 10 * MHZ, (10, 50)),
    GainOption("0 dB ≤ Gain ≤ 20 dB", 1 * MHZ, (10, 20), (0, 20)),
    GainOption("20 dB ≤ Gain ≤ 40 dB", 100 * KHZ, (10, 20), (20, 40)),
]

# Page 4 - Branch 3: Differential (Dual Op Amp)
_DIFF_SINGLE_TO_DIFF = [
    GainOption("Gain = 0 dB", 10 * MHZ, (80, 80)),
    GainOption("Gain = 6 dB", 10 * MHZ, (70, 70)),
]
_DIFF_FULLY = [
    GainOption("Gain = 0 dB", 10 * MHZ, (70, 70)),
    GainOption("Gain = 6 dB", 10 * MHZ, (60, 60)),
]

# circuit -> (sub-level label, {sub option: gain options}, passband definition)
TREE = {
    "Single Op Amp": (
        "Amplifier configuration",
        {"Non-Inverting": _SINGLE_GAINS, "Inverting": _SINGLE_GAINS},
        "−3 dB",
    ),
    "Dual Op Amp": (None, {None: _DUAL_GAINS}, "±0.5 dB"),
    "Differential": (
        "Differential configuration",
        {"Single to Differential": _DIFF_SINGLE_TO_DIFF, "Fully Differential": _DIFF_FULLY},
        "−3 dB",
    ),
}

INTRO_TEXT = (
    "This tool walks you through the narrow bandpass circuit decision tree. "
    "Choose a circuit type, then its configuration and gain, then enter the "
    "center frequency (and the bandwidth where the tree allows a range). "
    "Only the selected values are saved; where the tree fixes Pbandwidth as a % of fcenter, it is set automatically."
)

# ---------------------------------------------------------------------------
# 2. CSV STORAGE - only user-chosen values
# ---------------------------------------------------------------------------
CSV_PATH = Path(__file__).with_name("bandpass_saved_configurations.csv")

COLUMNS = [
    "Circuit Type",
    "Configuration",          # Non-Inverting / Inverting / Single to Differential / Fully Differential
    "Gain Selection",
    "Gain Value (dB)",        # only when the user enters a gain inside a range
    "Center Frequency Value",
    "Center Frequency Unit",
    "Bandwidth Value",        # entered by the user (range) or set automatically (fixed % of fcenter)
    "Bandwidth Unit",
]


def save_row(record):
    """Append one record to the CSV file (header written when the file is new)."""
    if CSV_PATH.exists() and CSV_PATH.stat().st_size > 0:
        with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
            header = next(csv.reader(f), [])
        if header != COLUMNS:  # file from an older version: keep it as a backup
            CSV_PATH.replace(CSV_PATH.with_suffix(".old.csv"))
    is_new = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({c: ("" if record.get(c) is None else record[c]) for c in COLUMNS})


def load_saved():
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def record_to_csv_text(record):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerow({c: ("" if record.get(c) is None else record[c]) for c in COLUMNS})
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 3. HELPERS
# ---------------------------------------------------------------------------
KEY_CIRCUIT, KEY_SUB, KEY_GAIN = "k_circuit", "k_sub", "k_gain"
KEY_GAIN_VAL = "k_gain_val"
KEY_FC_VAL, KEY_FC_UNIT = "k_fc_val", "k_fc_unit"
KEY_BW_VAL, KEY_BW_UNIT = "k_bw_val", "k_bw_unit"
ALL_KEYS = [KEY_SUB, KEY_GAIN, KEY_GAIN_VAL, KEY_FC_VAL, KEY_FC_UNIT, KEY_BW_VAL, KEY_BW_UNIT]


def fmt_hz(hz):
    for div, unit in ((MHZ, "MHz"), (KHZ, "kHz"), (HZ, "Hz")):
        if hz >= div:
            return f"{hz / div:g} {unit}"
    return f"{hz:g} Hz"


def fmt_pct(p):
    return f"{p:g}%"


def clear(*keys):
    for k in keys:
        st.session_state.pop(k, None)
    st.session_state["msg"] = None


def on_circuit_change():
    clear(*ALL_KEYS)


def on_sub_change():
    clear(KEY_GAIN, KEY_GAIN_VAL, KEY_FC_VAL, KEY_FC_UNIT, KEY_BW_VAL, KEY_BW_UNIT)


def on_gain_change():
    clear(KEY_GAIN_VAL, KEY_FC_VAL, KEY_FC_UNIT, KEY_BW_VAL, KEY_BW_UNIT)


def on_value_change():
    st.session_state["msg"] = None


def number_with_unit(title, value_key, unit_key, placeholder):
    """Number box + unit radio. Returns (value, unit) or (None, None) if incomplete."""
    st.markdown(f"**{title}**")
    c1, c2 = st.columns([2, 3])
    with c1:
        value = st.number_input(
            f"{title} value", min_value=0.0, value=None, step=0.1, format="%g",
            key=value_key, placeholder=placeholder, on_change=on_value_change,
            label_visibility="collapsed",
        )
    with c2:
        unit = st.radio(
            f"{title} unit", list(FREQUENCY_UNITS), index=None, horizontal=True,
            key=unit_key, on_change=on_value_change, label_visibility="collapsed",
        )
    if value is None or unit is None:
        st.caption("Enter a number and pick a unit (Hz, kHz or MHz).")
        return None, None
    return value, unit


# ---------------------------------------------------------------------------
# 4. INPUT FLOW (follows the tree top to bottom)
# ---------------------------------------------------------------------------
def collect_selections(circuit):
    """
    Render the branch for `circuit`. Returns the record of USER-CHOSEN values
    once every required step is complete and valid, otherwise None.
    """
    sub_label, sub_map, passband = TREE[circuit]
    record = {c: None for c in COLUMNS}
    record["Circuit Type"] = circuit

    # level 2 (only Single Op Amp and Differential have one)
    sub = None
    if sub_label:
        sub = st.radio(sub_label, list(sub_map), index=None, horizontal=True,
                       key=KEY_SUB, on_change=on_sub_change)
        if sub is None:
            return None
        record["Configuration"] = sub

    # gain
    options = {g.label: g for g in sub_map[sub]}
    gain_label = st.radio("Gain", list(options), index=None, horizontal=True,
                          key=KEY_GAIN, on_change=on_gain_change)
    if gain_label is None:
        return None
    gain = options[gain_label]
    record["Gain Selection"] = gain_label

    # tree limits for this path (shown to the user, NOT saved)
    bw_text = (f"{fmt_pct(gain.bw_pct[0])} to {fmt_pct(gain.bw_pct[1])} of fcenter"
               if gain.bw_is_range else f"{fmt_pct(gain.bw_pct[0])} of fcenter")
    st.info(
        f"**Allowed center frequency:** {fmt_hz(F_MIN_HZ)} ≤ fcenter ≤ {fmt_hz(gain.f_max_hz)}  \n"
        f"**Pbandwidth ({passband} passband):** {bw_text}"
    )

    complete = True

    # gain value inside a range
    if gain.gain_is_range:
        lo, hi = gain.gain_range_db
        gv = st.number_input(
            f"Gain value (dB) — between {lo:g} and {hi:g} dB", min_value=float(lo),
            max_value=float(hi), value=None, step=0.5, format="%g", key=KEY_GAIN_VAL,
            placeholder=f"e.g. {(lo + hi) / 2:g}", on_change=on_value_change,
        )
        if gv is None:
            complete = False
        else:
            record["Gain Value (dB)"] = gv

    # center frequency
    fc_val, fc_unit = number_with_unit("Center frequency (fcenter)", KEY_FC_VAL, KEY_FC_UNIT, "e.g. 2.5")
    if fc_val is None:
        return None
    fc_hz = fc_val * FREQUENCY_UNITS[fc_unit]
    if not (F_MIN_HZ <= fc_hz <= gain.f_max_hz * (1 + 1e-9)):
        st.error(f"{fc_val:g} {fc_unit} is outside the allowed range "
                 f"{fmt_hz(F_MIN_HZ)} to {fmt_hz(gain.f_max_hz)}.")
        return None
    record["Center Frequency Value"] = fc_val
    record["Center Frequency Unit"] = fc_unit

    # bandwidth - fixed by the tree (set automatically) or chosen within a range
    if not gain.bw_is_range:
        pct = gain.bw_pct[0]
        auto_bw = float(f"{fc_val * pct / 100:.10g}")
        record["Bandwidth Value"] = auto_bw
        record["Bandwidth Unit"] = fc_unit
        st.success(f"Pbandwidth is set automatically: {pct:g}% of fcenter = {auto_bw:g} {fc_unit}")
    else:
        lo_hz = fc_hz * gain.bw_pct[0] / 100
        hi_hz = fc_hz * gain.bw_pct[1] / 100
        st.caption(f"For fcenter = {fc_val:g} {fc_unit}, Pbandwidth must be between "
                   f"{fmt_hz(lo_hz)} and {fmt_hz(hi_hz)}.")
        bw_val, bw_unit = number_with_unit("Pbandwidth", KEY_BW_VAL, KEY_BW_UNIT, "e.g. 200")
        if bw_val is None:
            return None
        bw_hz = bw_val * FREQUENCY_UNITS[bw_unit]
        if not (lo_hz * (1 - 1e-9) <= bw_hz <= hi_hz * (1 + 1e-9)):
            st.error(f"{bw_val:g} {bw_unit} is outside the allowed Pbandwidth range "
                     f"{fmt_hz(lo_hz)} to {fmt_hz(hi_hz)}.")
            return None
        record["Bandwidth Value"] = bw_val
        record["Bandwidth Unit"] = bw_unit

    return record if complete else None


# ---------------------------------------------------------------------------
# 5. DISPLAY, SAVE, DOWNLOAD
# ---------------------------------------------------------------------------
def show_summary(record):
    st.subheader("Your Selected Configuration")
    rows = []
    for k, v in record.items():
        if v is None or k == "Bandwidth Unit":
            continue
        if k == "Bandwidth Value":
            k, v = "Pbandwidth", f"{v:g} {record['Bandwidth Unit']}"
        elif k == "Center Frequency Value":
            k, v = "Center Frequency (fcenter)", f"{v:g} {record['Center Frequency Unit']}"
        elif k == "Center Frequency Unit":
            continue
        rows.append((k, str(v)))
    st.table(pd.DataFrame(rows, columns=["Item", "Your choice"]).set_index("Item"))


def render_save_and_download(record):
    st.subheader("Save and Download")
    c_save, c_dl = st.columns(2)
    with c_save:
        if st.button("Save to CSV file", type="primary"):
            save_row(record)
            st.session_state["msg"] = f"Saved to {CSV_PATH.name}."
    with c_dl:
        st.download_button(
            "Download these details (CSV)",
            data=record_to_csv_text(record),
            file_name="bandpass_configuration.csv",
            mime="text/csv",
        )
    if st.session_state.get("msg"):
        st.success(st.session_state["msg"])


def render_saved_file():
    saved = load_saved()
    st.subheader("Saved configurations")
    if saved.empty:
        st.caption("Nothing saved yet.")
        return
    st.dataframe(saved, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Download all saved data (CSV)",
            data=CSV_PATH.read_bytes(),
            file_name=CSV_PATH.name,
            mime="text/csv",
            key="dl_all",
        )
    with c2:
        if st.button("Clear saved file"):
            CSV_PATH.unlink(missing_ok=True)
            st.session_state["msg"] = None
            st.rerun()


# ---------------------------------------------------------------------------
# 6. MAIN
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Narrow Bandpass Circuits", layout="wide")
    st.session_state.setdefault("msg", None)

    st.title("Narrow Bandpass Circuits")
    st.caption("Version 3 — Pbandwidth auto-set for fixed-bandwidth paths")
    st.write(INTRO_TEXT)
    with st.expander("Notes"):
        st.markdown(
            "- **fcenter** is the bandpass center frequency.\n"
            "- **Pbandwidth** is the passband frequency range.\n"
            "- Passband definition: **−3 dB** for Single Op Amp and Differential, "
            "**±0.5 dB** for Dual Op Amp."
        )

    circuit = st.radio("Circuit type", list(TREE), index=None, horizontal=True,
                       key=KEY_CIRCUIT, on_change=on_circuit_change)
    if circuit is None:
        st.caption("Select a circuit type to continue.")
        st.divider()
        render_saved_file()
        return

    st.divider()
    st.subheader(circuit)
    record = collect_selections(circuit)

    if record is None:
        st.caption("Complete all selections above to see the summary and save.")
    else:
        st.divider()
        show_summary(record)
        st.divider()
        render_save_and_download(record)

    st.divider()
    render_saved_file()


if __name__ == "__main__":
    main()
