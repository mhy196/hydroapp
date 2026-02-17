import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import find_peaks
import io
import datetime
import numpy as np

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
    if st.button("🔄 Reset"): st.rerun()
st.markdown("---")

# INITIALISATION
df = None 

# --- BARRE LATÉRALE ---
st.sidebar.title("1. Données")
source_type = st.sidebar.radio("Source :", ["📂 Fichier CSV", "✍️ Saisie Manuelle Indépendante"], index=0)

# --- LOGIQUE D'IMPORTATION ---

# ---------------------------------------------------------
# CAS 1 : IMPORT CSV (AVEC FUSION DATE+HEURE)
# ---------------------------------------------------------
if source_type == "📂 Fichier CSV":
    st.sidebar.info("Format : Date, Simulé, Observé (ou Date + Heure séparées)")
    uploaded_file = st.sidebar.file_uploader("Fichier CSV", type=["csv"])
    
    if uploaded_file:
        try:
            # Lecture brute
            df_raw = pd.read_csv(uploaded_file, sep=None, engine='python')
            df_raw.columns = [c.strip() for c in df_raw.columns]
            cols = df_raw.columns.tolist()

            # Détection intelligente des colonnes
            # On cherche si on a 'date' ET 'heure' séparés
            date_part_col = next((c for c in cols if "date" in c.lower() and "heure" not in c.lower()), None)
            time_part_col = next((c for c in cols if any(x in c.lower() for x in ["heure", "time"]) and "date" not in c.lower()), None)
            
            # Ou une colonne combinée
            combined_col = next((c for c in cols if "date" in c.lower()), cols[0])

            # Sélecteurs
            with st.expander("✅ Configuration des Colonnes", expanded=True):
                # Option Fusion
                use_fusion = st.checkbox("Fusionner Date + Heure (ex: colonnes séparées)", value=(date_part_col is not None and time_part_col is not None))
                
                if use_fusion:
                    c1, c2 = st.columns(2)
                    col_d = c1.selectbox("Col. Date", cols, index=cols.index(date_part_col) if date_part_col else 0)
                    col_h = c2.selectbox("Col. Heure", cols, index=cols.index(time_part_col) if time_part_col else 0)
                else:
                    col_dt = st.selectbox("Col. Date/Heure complète", cols, index=cols.index(combined_col))
                
                default_sim = next((c for c in cols if "sim" in c.lower()), cols[1] if len(cols)>1 else cols[0])
                default_obs = next((c for c in cols if "obs" in c.lower()), cols[2] if len(cols)>2 else cols[0])
                
                c3, c4 = st.columns(2)
                sim_col_name = c3.selectbox("Col. Simulé", cols, index=cols.index(default_sim))
                obs_col_name = c4.selectbox("Col. Observé", cols, index=cols.index(default_obs))

            # Construction du DF
            df = pd.DataFrame()
            
            # Traitement Date
            if use_fusion:
                # On combine les chaînes et on convertit
                combined_series = df_raw[col_d].astype(str) + " " + df_raw[col_h].astype(str)
                df['Datetime'] = pd.to_datetime(combined_series, dayfirst=True, errors='coerce')
            else:
                df['Datetime'] = pd.to_datetime(df_raw[col_dt], dayfirst=True, errors='coerce')

            # Traitement Numérique (Nettoyage , et espaces)
            def clean_num(s): return pd.to_numeric(s.astype(str).str.replace(',', '.', regex=False).str.replace(' ', '', regex=False), errors='coerce')
            
            df['Simulé'] = clean_num(df_raw[sim_col_name])
            df['Observé'] = clean_num(df_raw[obs_col_name])
            
            # Finalisation
            df = df.dropna(subset=['Datetime'])
            df = df.sort_values('Datetime')
            
            # Mapping pour la suite
            sim_col, obs_col, date_col = 'Simulé', 'Observé', 'Datetime'

        except Exception as e:
            st.error(f"Erreur CSV : {e}")

# ---------------------------------------------------------
# CAS 2 : SAISIE MANUELLE INDÉPENDANTE
# ---------------------------------------------------------
else:
    st.info("💡 **Mode Indépendant :** Définissez le début de chaque série séparément.")

    # Fonction utilitaire pour parser le texte collé
    def parse_text_data(text):
        if not text.strip(): return []
        clean = text.replace('\n', ' ').replace(',', '.').replace(';', ' ')
        return [float(v) for v in clean.split() if v.strip()]

    # --- BLOC 1 : SIMULÉ ---
    with st.container():
        st.markdown("### 🔵 Série Simulée")
        c1, c2, c3 = st.columns([1, 1, 2])
        sim_start_d = c1.date_input("Date Début (Sim)", datetime.date.today())
        sim_start_t = c2.time_input("Heure Début (Sim)", datetime.time(8, 0))
        sim_step = c3.number_input("Pas (heures)", 1, 24, 1, key="step_sim")
        
        sim_txt = st.text_area("Collez les valeurs SIMULÉES ici (Excel)", height=100, key="txt_sim")
        sim_vals = parse_text_data(sim_txt)
        
        if sim_vals:
            st.caption(f"✅ {len(sim_vals)} valeurs détectées")
        
    st.markdown("---")
    
    # --- BLOC 2 : OBSERVÉ ---
    with st.container():
        st.markdown("### 🔴 Série Observée")
        c1, c2, c3 = st.columns([1, 1, 2])
        obs_start_d = c1.date_input("Date Début (Obs)", datetime.date.today())
        obs_start_t = c2.time_input("Heure Début (Obs)", datetime.time(8, 0))
        obs_step = c3.number_input("Pas (heures)", 1, 24, 1, key="step_obs")
        
        obs_txt = st.text_area("Collez les valeurs OBSERVÉES ici (Excel)", height=100, key="txt_obs")
        obs_vals = parse_text_data(obs_txt)

        if obs_vals:
            st.caption(f"✅ {len(obs_vals)} valeurs détectées")

    # BOUTON GÉNÉRATION
    if st.button("Générer Graphique Combiné", type="primary"):
        if not sim_vals and not obs_vals:
            st.error("Veuillez entrer au moins une série de données.")
        else:
            # Construction Série Simulé
            df_sim = pd.DataFrame()
            if sim_vals:
                start_dt = datetime.datetime.combine(sim_start_d, sim_start_t)
                dates = pd.date_range(start=start_dt, periods=len(sim_vals), freq=f'{sim_step}h')
                df_sim = pd.DataFrame({'Datetime': dates, 'Simulé': sim_vals})
                df_sim.set_index('Datetime', inplace=True)

            # Construction Série Observé
            df_obs = pd.DataFrame()
            if obs_vals:
                start_dt = datetime.datetime.combine(obs_start_d, obs_start_t)
                dates = pd.date_range(start=start_dt, periods=len(obs_vals), freq=f'{obs_step}h')
                df_obs = pd.DataFrame({'Datetime': dates, 'Observé': obs_vals})
                df_obs.set_index('Datetime', inplace=True)
            
            # FUSION (Outer Join sur l'index temporel)
            # Cela aligne automatiquement les dates !
            if not df_sim.empty and not df_obs.empty:
                df = df_sim.join(df_obs, how='outer').reset_index()
            elif not df_sim.empty:
                df = df_sim.reset_index()
                df['Observé'] = np.nan
            else:
                df = df_obs.reset_index()
                df['Simulé'] = np.nan
            
            df = df.sort_values('Datetime')
            sim_col, obs_col, date_col = 'Simulé', 'Observé', 'Datetime'

# --- SUITE BARRE LATÉRALE ---
st.sidebar.markdown("---")
st.sidebar.header("2. Apparence")
title = st.sidebar.text_input("Titre", "Hydrogramme de Crue")
c1, c2 = st.sidebar.columns(2)
col_sim_pick = c1.color_picker("Simulé", "#0288D1") 
col_obs_pick = c2.color_picker("Observé", "#D32F2F")

with st.sidebar.expander("⚙️ Réglages Avancés"):
    st.markdown("**Pics**")
    n_peaks = st.slider("Max Pics", 1, 20, 6)
    peak_sensitivity = st.slider("Sensibilité", 1, 200, 10)
    st.markdown("**Layout**")
    global_x_offset = st.slider("Écart Horizontal (Neg=Inv)", -100, 100, 25)
    label_size = st.slider("Taille Texte", 8, 20, 11)
    show_hours = st.checkbox("Heures sur Axe X", value=True)
    st.markdown("**Axes**")
    ylabel = st.text_input("Label Y", "Débit (m³/s)")
    xlabel = st.text_input("Label X", "Date et Heure")

# --- FONCTIONS & PLOT ---
def get_peak_indices(series, n, prominence=10, distance=5):
    series = series.fillna(0)
    peaks, _ = find_peaks(series, prominence=prominence, distance=distance)
    if len(peaks) == 0 and not series.empty: return [series.idxmax()]
    elif len(peaks) == 0: return []
    peak_df = pd.DataFrame({'index': series.index[peaks], 'val': series.iloc[peaks].values})
    return sorted(peak_df.sort_values(by='val', ascending=False).head(n)['index'].tolist())

if df is not None and not df.empty:
    try:
        # Calculs Pics
        sim_indices = get_peak_indices(df[sim_col], n_peaks, prominence=peak_sensitivity)
        obs_indices = get_peak_indices(df[obs_col], n_peaks, prominence=peak_sensitivity)
        
        # AJUSTEMENT MANUEL (SIDEBAR)
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

        # GRAPHIQUE
        fig, ax = plt.subplots(figsize=(16, 9), facecolor='white')
        
        # Tracé Simulé
        if sim_col in df and df[sim_col].notna().any():
            ax.plot(df['Datetime'], df[sim_col], color=col_sim_pick, lw=2.5, label='Débit Simulé', zorder=2)
            
            # Labels Sim
            for idx in sim_indices:
                val = df.loc[idx, sim_col]
                time = df.loc[idx, 'Datetime']
                base_x, base_y = global_x_offset, 40
                mdx, mdy = manual_offsets.get(f"sim_{idx}", (0,0))
                ax.scatter(time, val, color=col_sim_pick, s=180, zorder=5, edgecolors='white', lw=2)
                ax.annotate(f"{val:.0f}", xy=(time, val), xytext=(base_x + mdx, base_y + mdy), 
                            textcoords='offset points', ha='center', va='bottom', fontsize=label_size, fontweight='bold', color=col_sim_pick,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col_sim_pick, lw=1.5, alpha=0.95),
                            arrowprops=dict(arrowstyle="-", color=col_sim_pick, lw=1.5), zorder=10)

        # Tracé Observé
        if obs_col in df and df[obs_col].notna().any():
            ax.plot(df['Datetime'], df[obs_col], color=col_obs_pick, lw=2.5, ls='--', label='Débit Observé', zorder=2)
            
            # Labels Obs
            for idx in obs_indices:
                val = df.loc[idx, obs_col]
                time = df.loc[idx, 'Datetime']
                base_x, base_y = -global_x_offset, 40
                mdx, mdy = manual_offsets.get(f"obs_{idx}", (0,0))
                ax.scatter(time, val, color=col_obs_pick, s=180, zorder=5, edgecolors='white', lw=2)
                ax.annotate(f"{val:.0f}", xy=(time, val), xytext=(base_x + mdx, base_y + mdy), 
                            textcoords='offset points', ha='center', va='bottom', fontsize=label_size, fontweight='bold', color=col_obs_pick,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col_obs_pick, lw=1.5, alpha=0.95),
                            arrowprops=dict(arrowstyle="-", color=col_obs_pick, lw=1.5), zorder=10)
        
        ax.set_title(title, fontsize=20, fontweight='600', pad=20, color='#2C3E50')
        ax.set_ylabel(ylabel, fontsize=12, fontweight='bold', color='#2C3E50')
        ax.set_xlabel(xlabel, fontsize=12, fontweight='bold', color='#2C3E50')
        ax.grid(True, alpha=0.2, color='#2C3E50', ls='-')
        ax.legend(fontsize=11, loc='upper right', frameon=True, framealpha=1.0, facecolor='white', edgecolor='#E1E4E8').set_zorder(10)
        
        # Axe X
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
        
        clean_title = title.replace(" ", "_").lower()
        img = io.BytesIO()
        fig.savefig(img, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        st.download_button("💾 Télécharger l'image", data=img, file_name=f"{clean_title}.png", mime="image/png", use_container_width=True)

    except Exception as e:
        st.error(f"Erreur technique : {e}")
