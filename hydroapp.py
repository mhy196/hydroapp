import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import find_peaks
import io
import datetime
import numpy as np
import re

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(
    page_title="Générateur d'Hydrogrammes", 
    layout="wide", 
    page_icon="🌊",
    initial_sidebar_state="expanded" 
)

# --- 2. CSS ---
st.markdown("""
<style>
    :root { --primary: #0277BD; --bg: #FAFAFA; --sidebar: #F5F7F9; --text: #2C3E50; }
    .stApp { background-color: var(--bg); color: var(--text); }
    section[data-testid="stSidebar"] { background-color: var(--sidebar); border-right: 2px solid #E0E0E0; }
    section[data-testid="stSidebar"] * { color: #1F2937 !important; }
    [data-testid="stSidebarCollapsedControl"] {
        background-color: #FFFFFF !important; color: #0277BD !important;
        border: 2px solid #0277BD !important; border-radius: 50%;
        width: 40px; height: 40px; z-index: 999999;
    }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        background-color: #FFFFFF !important; color: #000000 !important;
    }
    h1 { color: var(--primary) !important; }
    div[data-testid="stToolbar"] { visibility: visible; }
</style>
""", unsafe_allow_html=True)

# EN-TÊTE
col_title, col_reset = st.columns([6, 1])
with col_title: st.title("🌊 Générateur d'Hydrogrammes")
with col_reset: 
    if st.button("🔄 Reset"): 
        st.session_state.clear()
        st.rerun()
st.markdown("---")

# --- GESTION DE LA MÉMOIRE ---
if 'df_global' not in st.session_state:
    st.session_state.df_global = None
if 'last_source' not in st.session_state:
    st.session_state.last_source = None

# --- BARRE LATÉRALE ---
st.sidebar.title("1. Données")
source_type = st.sidebar.radio("Source :", ["📂 Fichier CSV", "✍️ Saisie Manuelle Indépendante"], index=0)

if st.session_state.last_source != source_type:
    st.session_state.df_global = None
    st.session_state.last_source = source_type

# --- FONCTIONS UTILITAIRES ---
def smart_date_parser(series):
    sample = series.dropna().astype(str).iloc[0] if not series.dropna().empty else ""
    if re.match(r'^\d{4}', sample):
        return pd.to_datetime(series, dayfirst=False, errors='coerce')
    dt_fr = pd.to_datetime(series, dayfirst=True, errors='coerce')
    nat_fr = dt_fr.isna().sum()
    dt_iso = pd.to_datetime(series, dayfirst=False, errors='coerce')
    nat_iso = dt_iso.isna().sum()
    if nat_fr <= nat_iso: return dt_fr
    else: return dt_iso

def clean_num(s):
    return pd.to_numeric(s.astype(str).str.replace(',', '.', regex=False).str.replace(' ', '', regex=False), errors='coerce')

# --- LOGIQUE D'IMPORTATION ---
if source_type == "📂 Fichier CSV":
    st.sidebar.info("Format : Date, Simulé, Observé")
    uploaded_file = st.sidebar.file_uploader("Fichier CSV", type=["csv"], key="csv_uploader")
    
    if uploaded_file:
        try:
            df_raw = pd.read_csv(uploaded_file, sep=None, engine='python')
            df_raw.columns = [c.strip() for c in df_raw.columns]
            cols = df_raw.columns.tolist()

            date_part_col = next((c for c in cols if "date" in c.lower() and "heure" not in c.lower()), None)
            time_part_col = next((c for c in cols if any(x in c.lower() for x in ["heure", "time"]) and "date" not in c.lower()), None)
            combined_col = next((c for c in cols if "date" in c.lower()), cols[0])
            
            with st.expander("✅ Configuration Colonnes", expanded=True):
                use_fusion = st.checkbox("Fusionner Date + Heure", value=(date_part_col is not None and time_part_col is not None))
                if use_fusion:
                    c1, c2 = st.columns(2)
                    col_d = c1.selectbox("Col. Date", cols, index=cols.index(date_part_col) if date_part_col else 0)
                    col_h = c2.selectbox("Col. Heure", cols, index=cols.index(time_part_col) if time_part_col else 0)
                else:
                    col_dt = st.selectbox("Col. Date/Heure", cols, index=cols.index(combined_col))
                
                default_sim = next((c for c in cols if "sim" in c.lower()), cols[1] if len(cols)>1 else cols[0])
                default_obs = next((c for c in cols if "obs" in c.lower()), cols[2] if len(cols)>2 else cols[0])
                c3, c4 = st.columns(2)
                sim_col_name = c3.selectbox("Col. Simulé", cols, index=cols.index(default_sim))
                obs_col_name = c4.selectbox("Col. Observé", cols, index=cols.index(default_obs))

            df = pd.DataFrame()
            if use_fusion:
                combined_series = df_raw[col_d].astype(str) + " " + df_raw[col_h].astype(str)
                df['Datetime'] = smart_date_parser(combined_series)
            else:
                df['Datetime'] = smart_date_parser(df_raw[col_dt])

            df['Simulé'] = clean_num(df_raw[sim_col_name])
            df['Observé'] = clean_num(df_raw[obs_col_name])
            df = df.dropna(subset=['Datetime'])
            df = df.sort_values('Datetime')
            st.session_state.df_global = df

        except Exception as e:
            st.error(f"Erreur CSV : {e}")

else:
    st.info("💡 Définissez le Début et la Fin, puis collez vos données.")
    def parse_text_data(text):
        if not text.strip(): return []
        clean = text.replace('\n', ' ').replace(',', '.').replace(';', ' ')
        return [float(v) for v in clean.split() if v.strip()]

    with st.container():
        st.markdown("### 🔵 Série Simulée")
        c1, c2, c3, c4, c5 = st.columns(5)
        sim_start_d = c1.date_input("Date Début (Sim)", datetime.date.today())
        sim_start_t = c2.time_input("Heure Début (Sim)", datetime.time(8, 0))
        sim_end_d   = c3.date_input("Date Fin (Sim)", datetime.date.today())
        sim_end_t   = c4.time_input("Heure Fin (Sim)", datetime.time(20, 0))
        sim_step    = c5.number_input("Pas (h)", 1, 24, 1, key="step_sim")
        
        start_dt_sim = datetime.datetime.combine(sim_start_d, sim_start_t)
        end_dt_sim   = datetime.datetime.combine(sim_end_d, sim_end_t)
        sim_dates = pd.date_range(start=start_dt_sim, end=end_dt_sim, freq=f'{sim_step}h')
        nb_sim = len(sim_dates)
        st.caption(f"📅 Période : {start_dt_sim} -> {end_dt_sim} | **{nb_sim} valeurs attendues**")

        sim_txt = st.text_area("Collez valeurs SIM", height=100, key="txt_sim")
        sim_vals = parse_text_data(sim_txt)
        if sim_vals: st.caption(f"✅ {len(sim_vals)} valeurs")

    st.markdown("---")
    
    with st.container():
        st.markdown("### 🔴 Série Observée")
        c1, c2, c3, c4, c5 = st.columns(5)
        obs_start_d = c1.date_input("Date Début (Obs)", datetime.date.today())
        obs_start_t = c2.time_input("Heure Début (Obs)", datetime.time(8, 0))
        obs_end_d   = c3.date_input("Date Fin (Obs)", datetime.date.today())
        obs_end_t   = c4.time_input("Heure Fin (Obs)", datetime.time(20, 0))
        obs_step    = c5.number_input("Pas (h)", 1, 24, 1, key="step_obs")
        
        start_dt_obs = datetime.datetime.combine(obs_start_d, obs_start_t)
        end_dt_obs   = datetime.datetime.combine(obs_end_d, obs_end_t)
        obs_dates = pd.date_range(start=start_dt_obs, end=end_dt_obs, freq=f'{obs_step}h')
        nb_obs = len(obs_dates)
        st.caption(f"📅 Période : {start_dt_obs} -> {end_dt_obs} | **{nb_obs} valeurs attendues**")

        obs_txt = st.text_area("Collez valeurs OBS", height=100, key="txt_obs")
        obs_vals = parse_text_data(obs_txt)
        if obs_vals: st.caption(f"✅ {len(obs_vals)} valeurs")

    if st.button("Générer Graphique Combiné", type="primary"):
        df_sim = pd.DataFrame()
        if sim_vals and nb_sim > 0:
            L = min(len(sim_vals), len(sim_dates))
            df_sim = pd.DataFrame({'Datetime': sim_dates[:L], 'Simulé': sim_vals[:L]}).set_index('Datetime')

        df_obs = pd.DataFrame()
        if obs_vals and nb_obs > 0:
            L = min(len(obs_vals), len(obs_dates))
            df_obs = pd.DataFrame({'Datetime': obs_dates[:L], 'Observé': obs_vals[:L]}).set_index('Datetime')
        
        if not df_sim.empty or not df_obs.empty:
            if not df_sim.empty and not df_obs.empty:
                df = df_sim.join(df_obs, how='outer').reset_index()
            elif not df_sim.empty:
                df = df_sim.reset_index()
                df['Observé'] = np.nan
            else:
                df = df_obs.reset_index()
                df['Simulé'] = np.nan
            st.session_state.df_global = df.sort_values('Datetime')
        else:
            st.error("Aucune donnée valide.")

# --- SUITE BARRE LATÉRALE ---
st.sidebar.markdown("---")
st.sidebar.header("2. Apparence")

# --- NOUVEAU : GESTION DES TITRES ---
show_main_title = st.sidebar.checkbox("Afficher le titre", value=True)
if show_main_title:
    title = st.sidebar.text_input("Titre", "Hydrogramme de Crue")
else:
    title = ""

c1, c2 = st.sidebar.columns(2)
col_sim_pick = c1.color_picker("Simulé", "#0288D1") 
col_obs_pick = c2.color_picker("Observé", "#D32F2F")

with st.sidebar.expander("⚙️ Réglages Avancés"):
    st.markdown("**Pics & Points**")
    n_peaks = st.slider("Max Pics", 1, 20, 6)
    peak_sensitivity = st.slider("Sensibilité", 1, 200, 10)
    # --- NOUVEAU : TAILLE DES POINTS ---
    point_size = st.slider("Taille des points", 50, 500, 180, step=10)
    
    st.markdown("**Layout**")
    global_x_offset = st.slider("Écart Horizontal (Neg=Inv)", -100, 100, 25)
    label_size = st.slider("Taille Texte", 8, 20, 11)
    
    st.markdown("**Axes**")
    # --- NOUVEAU : GESTION DES TITRES AXES ---
    show_axis_titles = st.checkbox("Afficher les titres des axes", value=True)
    if show_axis_titles:
        ylabel = st.text_input("Label Y", "Débit (m³/s)")
        xlabel = st.text_input("Label X", "Date et Heure")
    else:
        ylabel = ""
        xlabel = ""
        
    show_hours = st.checkbox("Heures sur Axe X", value=True)

# --- FONCTIONS PICS ---
def get_peak_indices(series, n, prominence=10, distance=5):
    series = series.fillna(0)
    peaks, _ = find_peaks(series, prominence=prominence, distance=distance)
    if len(peaks) == 0 and not series.empty: return [series.idxmax()]
    elif len(peaks) == 0: return []
    peak_df = pd.DataFrame({'index': series.index[peaks], 'val': series.iloc[peaks].values})
    return sorted(peak_df.sort_values(by='val', ascending=False).head(n)['index'].tolist())

# --- AFFICHAGE PERSISTANT ---
if st.session_state.df_global is not None:
    df = st.session_state.df_global
    sim_col, obs_col = 'Simulé', 'Observé'

    try:
        sim_indices = get_peak_indices(df[sim_col], n_peaks, prominence=peak_sensitivity)
        obs_indices = get_peak_indices(df[obs_col], n_peaks, prominence=peak_sensitivity)
        
        st.sidebar.markdown("---")
        st.sidebar.header("3. Ajustement Fin")
        manual_offsets = {}
        expand_manual = len(sim_indices) + len(obs_indices) < 8
        
        with st.sidebar.expander("🔵 Pics Simulé", expanded=expand_manual):
            for idx in sim_indices:
                t_str = df.loc[idx, 'Datetime'].strftime('%d/%m %Hh')
                v = df.loc[idx, sim_col]
                st.markdown(f"**{t_str}** : {v:.0f}")
                c_x, c_y = st.columns(2)
                dx = c_x.number_input(f"↔ X", value=0, key=f"sx_{idx}", step=5)
                dy = c_y.number_input(f"↕ Y", value=0, key=f"sy_{idx}", step=5)
                manual_offsets[f"sim_{idx}"] = (dx, dy)
                st.markdown("---")

        with st.sidebar.expander("🔴 Pics Observé", expanded=expand_manual):
            for idx in obs_indices:
                t_str = df.loc[idx, 'Datetime'].strftime('%d/%m %Hh')
                v = df.loc[idx, obs_col]
                st.markdown(f"**{t_str}** : {v:.0f}")
                c_x, c_y = st.columns(2)
                dx = c_x.number_input(f"↔ X", value=0, key=f"ox_{idx}", step=5)
                dy = c_y.number_input(f"↕ Y", value=0, key=f"oy_{idx}", step=5)
                manual_offsets[f"obs_{idx}"] = (dx, dy)
                st.markdown("---")

        fig, ax = plt.subplots(figsize=(16, 9), facecolor='white')
        
        if sim_col in df and df[sim_col].notna().any():
            ax.plot(df['Datetime'], df[sim_col], color=col_sim_pick, lw=2.5, label='Débit Simulé', zorder=2)
            for idx in sim_indices:
                val = df.loc[idx, sim_col]
                time = df.loc[idx, 'Datetime']
                base_x, base_y = global_x_offset, 40
                mdx, mdy = manual_offsets.get(f"sim_{idx}", (0,0))
                # Utilisation de point_size
                ax.scatter(time, val, color=col_sim_pick, s=point_size, zorder=5, edgecolors='white', lw=2)
                ax.annotate(f"{val:.0f}", xy=(time, val), xytext=(base_x + mdx, base_y + mdy), 
                            textcoords='offset points', ha='center', va='bottom', fontsize=label_size, fontweight='bold', color=col_sim_pick,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col_sim_pick, lw=1.5, alpha=0.95),
                            arrowprops=dict(arrowstyle="-", color=col_sim_pick, lw=1.5), zorder=10)

        if obs_col in df and df[obs_col].notna().any():
            ax.plot(df['Datetime'], df[obs_col], color=col_obs_pick, lw=2.5, ls='--', label='Débit Observé', zorder=2)
            for idx in obs_indices:
                val = df.loc[idx, obs_col]
                time = df.loc[idx, 'Datetime']
                base_x, base_y = -global_x_offset, 40
                mdx, mdy = manual_offsets.get(f"obs_{idx}", (0,0))
                # Utilisation de point_size
                ax.scatter(time, val, color=col_obs_pick, s=point_size, zorder=5, edgecolors='white', lw=2)
                ax.annotate(f"{val:.0f}", xy=(time, val), xytext=(base_x + mdx, base_y + mdy), 
                            textcoords='offset points', ha='center', va='bottom', fontsize=label_size, fontweight='bold', color=col_obs_pick,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col_obs_pick, lw=1.5, alpha=0.95),
                            arrowprops=dict(arrowstyle="-", color=col_obs_pick, lw=1.5), zorder=10)
        
        # Gestion conditionnelle des titres
        if show_main_title:
            ax.set_title(title, fontsize=20, fontweight='600', pad=20, color='#2C3E50')
        
        if show_axis_titles:
            ax.set_ylabel(ylabel, fontsize=12, fontweight='bold', color='#2C3E50')
            ax.set_xlabel(xlabel, fontsize=12, fontweight='bold', color='#2C3E50')
            
        ax.grid(True, alpha=0.2, color='#2C3E50', ls='-')
        ax.legend(fontsize=11, loc='upper right', frameon=True, framealpha=1.0, facecolor='white', edgecolor='#E1E4E8').set_zorder(10)
        
        duration = (df['Datetime'].max() - df['Datetime'].min()).days
        if duration < 5:
            locator = mdates.HourLocator(interval=4 if show_hours else 24)
            fmt = '%d/%m %Hh' if show_hours else '%d/%m'
        else:
            locator = mdates.HourLocator(interval=12) if show_hours else mdates.DayLocator(interval=2)
            fmt = '%d/%m %Hh' if show_hours else '%d/%m'
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        plt.setp(ax.get_xticklabels(), rotation=90, ha='center', fontsize=10)
        for spine in ax.spines.values(): spine.set_edgecolor('#BDC3C7')
            
        st.pyplot(fig)
        
        clean_title = title.replace(" ", "_").lower() if title else "hydrogramme"
        img = io.BytesIO()
        fig.savefig(img, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        st.download_button("💾 Télécharger l'image", data=img, file_name=f"{clean_title}.png", mime="image/png", use_container_width=True)

    except Exception as e:
        st.error(f"Erreur technique : {e}")
