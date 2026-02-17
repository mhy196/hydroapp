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

# --- 2. CSS ROBUSTE ---
st.markdown("""
<style>
    :root { --primary: #0277BD; --bg: #FAFAFA; --sidebar: #F5F7F9; --text: #2C3E50; }
    .stApp { background-color: var(--bg); color: var(--text); }
    section[data-testid="stSidebar"] { background-color: var(--sidebar); border-right: 2px solid #E0E0E0; }
    section[data-testid="stSidebar"] * { color: #1F2937 !important; }
    
    /* Bouton Menu (Flèche) */
    [data-testid="stSidebarCollapsedControl"] {
        background-color: #FFFFFF !important; color: #0277BD !important;
        border: 2px solid #0277BD !important; border-radius: 50%;
        width: 40px; height: 40px; z-index: 999999;
    }
    
    /* Inputs Saisie */
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        background-color: #FFFFFF !important; color: #000000 !important;
    }
    
    h1 { color: var(--primary) !important; }
    div[data-testid="stToolbar"] { visibility: visible; }
</style>
""", unsafe_allow_html=True)

# BOUTON SECOURS
col_title, col_reset = st.columns([6, 1])
with col_title: st.title("🌊 Générateur d'Hydrogrammes")
with col_reset: 
    if st.button("🔄 Reset"): st.rerun()

st.markdown("---")

# --- INITIALISATION ---
df = None 

# --- BARRE LATÉRALE (NAVIGATION) ---
st.sidebar.title("1. Données")
source_type = st.sidebar.radio("Source :", ["📂 Fichier CSV", "✍️ Saisie Manuelle"], index=0)

# --- LOGIQUE D'IMPORTATION ---

# ---------------------------------------------------------
# CAS 1 : IMPORT CSV (AMÉLIORÉ POUR ROBUSTESSE)
# ---------------------------------------------------------
if source_type == "📂 Fichier CSV":
    st.sidebar.info("Format : Date, Simulé, Observé")
    uploaded_file = st.sidebar.file_uploader("Fichier CSV", type=["csv"])
    
    if uploaded_file:
        try:
            # engine='python' et sep=None détecte automatiquement ; ou ,
            df_raw = pd.read_csv(uploaded_file, sep=None, engine='python')
            
            # Nettoyage des colonnes (suppression espaces)
            df_raw.columns = [c.strip() for c in df_raw.columns]
            cols = df_raw.columns.tolist()

            # Détection colonnes
            default_date = next((c for c in cols if any(x in c.lower() for x in ["date", "time", "heure"])), cols[0])
            default_sim = next((c for c in cols if "sim" in c.lower()), cols[1] if len(cols)>1 else cols[0])
            default_obs = next((c for c in cols if "obs" in c.lower()), cols[2] if len(cols)>2 else cols[0])

            with st.expander("✅ Vérifier les colonnes", expanded=True):
                c1, c2, c3 = st.columns(3)
                date_col = c1.selectbox("Date", cols, index=cols.index(default_date))
                sim_col = c2.selectbox("Simulé", cols, index=cols.index(default_sim))
                obs_col = c3.selectbox("Observé", cols, index=cols.index(default_obs))

            # Création du DF final propre
            df = pd.DataFrame()
            # Conversion Date robuste
            df['Datetime'] = pd.to_datetime(df_raw[date_col], dayfirst=True, errors='coerce')
            
            # Conversion Numérique robuste (gère "1 000", "1,5", etc)
            def clean_numeric(series):
                # Convertit en string, remplace , par ., enlève les espaces, puis convertit en nombre
                return pd.to_numeric(series.astype(str).str.replace(',', '.', regex=False).str.replace(' ', '', regex=False), errors='coerce')

            df[sim_col] = clean_numeric(df_raw[sim_col])
            df[obs_col] = clean_numeric(df_raw[obs_col])
            
            # Supprime les dates invalides
            df = df.dropna(subset=['Datetime'])
            df = df.sort_values('Datetime')

        except Exception as e:
            st.error(f"Erreur lors de la lecture du CSV : {e}")

# ---------------------------------------------------------
# CAS 2 : SAISIE MANUELLE (NOUVELLE LOGIQUE)
# ---------------------------------------------------------
else:
    st.info("💡 **Générateur Automatique :** Définissez la période, puis collez simplement vos valeurs.")
    
    # 1. Configuration Temporelle
    c1, c2, c3, c4, c5 = st.columns(5)
    start_d = c1.date_input("Date Début", datetime.date.today())
    start_t = c2.time_input("Heure Début", datetime.time(8, 0))
    end_d = c3.date_input("Date Fin", datetime.date.today() + datetime.timedelta(days=1))
    end_t = c4.time_input("Heure Fin", datetime.time(8, 0))
    step_h = c5.number_input("Pas (heures)", min_value=1, value=1)
    
    # Génération de l'axe temps
    start_dt = datetime.datetime.combine(start_d, start_t)
    end_dt = datetime.datetime.combine(end_d, end_t)
    
    if start_dt >= end_dt:
        st.error("⚠️ La date de fin doit être après la date de début.")
    else:
        # Création de la plage de dates
        date_range = pd.date_range(start=start_dt, end=end_dt, freq=f'{step_h}h')
        nb_values = len(date_range)
        
        st.markdown(f"**⏳ Période :** {nb_values} valeurs attendues (de {start_dt} à {end_dt})")
        
        # 2. Saisie des Valeurs (Text Area pour copier-coller)
        col_sim, col_obs = st.columns(2)
        
        def parse_values(text, expected_len):
            if not text.strip(): return None
            # Remplace virgules, retours à la ligne par espaces, puis split
            clean_text = text.replace('\n', ' ').replace(',', '.').replace(';', ' ')
            try:
                values = [float(v) for v in clean_text.split() if v.strip()]
                return values
            except:
                return "error"

        with col_sim:
            st.markdown("### 🔵 Débits Simulé")
            txt_sim = st.text_area("Collez les valeurs ici (Excel, liste...)", height=150, help="Copiez votre colonne Excel et collez-la ici.")
            vals_sim = parse_values(txt_sim, nb_values)
            
            if vals_sim == "error": st.warning("Contient du texte non numérique.")
            elif vals_sim and len(vals_sim) != nb_values: 
                st.warning(f"⚠️ {len(vals_sim)} valeurs entrées / {nb_values} attendues")
            elif vals_sim: st.success(f"✅ {len(vals_sim)} valeurs valides")

        with col_obs:
            st.markdown("### 🔴 Débits Observé")
            txt_obs = st.text_area("Collez les valeurs ici", height=150)
            vals_obs = parse_values(txt_obs, nb_values)
            
            if vals_obs == "error": st.warning("Erreur format.")
            elif vals_obs and len(vals_obs) != nb_values: 
                st.warning(f"⚠️ {len(vals_obs)} valeurs / {nb_values} attendues")
            elif vals_obs: st.success("✅ OK")

        # 3. Validation
        if st.button("Générer le Graphique", type="primary"):
            if vals_sim and vals_obs and len(vals_sim) == nb_values and len(vals_obs) == nb_values:
                df = pd.DataFrame({
                    'Datetime': date_range,
                    'Simulé': vals_sim,
                    'Observé': vals_obs
                })
                # On définit les colonnes pour la suite
                sim_col = 'Simulé'
                obs_col = 'Observé'
                date_col = 'Datetime'
            else:
                st.error("Veuillez vérifier que le nombre de valeurs correspond exactement à la période définie.")

# --- SUITE BARRE LATÉRALE (RÉGLAGES) ---
st.sidebar.markdown("---")
st.sidebar.header("2. Apparence")

title = st.sidebar.text_input("Titre", "Hydrogramme de Crue")
c1, c2 = st.sidebar.columns(2)
col_sim_pick = c1.color_picker("Simulé", "#0288D1") 
col_obs_pick = c2.color_picker("Observé", "#D32F2F")

# RÉGLAGES AVANCÉS
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

# --- FONCTIONS ---
def get_peak_indices(series, n, prominence=10, distance=5):
    series = series.fillna(0)
    peaks, _ = find_peaks(series, prominence=prominence, distance=distance)
    if len(peaks) == 0: return [series.idxmax()]
    peak_df = pd.DataFrame({'index': series.index[peaks], 'val': series.iloc[peaks].values})
    return sorted(peak_df.sort_values(by='val', ascending=False).head(n)['index'].tolist())

# --- TRAITEMENT & GRAPHIQUE ---
if df is not None and not df.empty:
    try:
        # Si c'est un CSV, les noms de colonnes ont été définis plus haut.
        # Si c'est manuel, ils sont définis dans le bloc manuel.
        # On vérifie juste qu'on a bien les noms.
        if 'sim_col' not in locals(): # Cas CSV où df est chargé mais vars pas globales
             # On recupère les noms du df
             cols = df.columns
             # On assume l'ordre standard du nettoyage CSV
             date_col, sim_col, obs_col = cols[0], cols[1], cols[2] # Fallback simple

        # Calculs Pics
        sim_indices = get_peak_indices(df[sim_col], n_peaks, prominence=peak_sensitivity)
        obs_indices = get_peak_indices(df[obs_col], n_peaks, prominence=peak_sensitivity)
        
        # --- AJUSTEMENT MANUEL (SIDEBAR) ---
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

        # --- GRAPHIQUE ---
        fig, ax = plt.subplots(figsize=(16, 9), facecolor='white')
        
        ax.plot(df['Datetime'], df[sim_col], color=col_sim_pick, lw=2.5, label='Débit Simulé', zorder=2)
        ax.plot(df['Datetime'], df[obs_col], color=col_obs_pick, lw=2.5, ls='--', label='Débit Observé', zorder=2)
        
        def draw_labels(indices, col_name, color, is_sim):
            for idx in indices:
                val = df.loc[idx, col_name]
                time = df.loc[idx, 'Datetime']
                
                base_x = global_x_offset if is_sim else -global_x_offset
                base_y = 40 
                
                k = f"sim_{idx}" if is_sim else f"obs_{idx}"
                mdx, mdy = manual_offsets.get(k, (0,0))
                
                ax.scatter(time, val, color=color, s=180, zorder=5, edgecolors='white', lw=2)
                ax.annotate(f"{val:.0f}", xy=(time, val), xytext=(base_x + mdx, base_y + mdy), 
                            textcoords='offset points', ha='center', va='bottom', 
                            fontsize=label_size, fontweight='bold', color=color,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, lw=1.5, alpha=0.95),
                            arrowprops=dict(arrowstyle="-", color=color, lw=1.5), zorder=10)

        draw_labels(sim_indices, sim_col, col_sim_pick, is_sim=True)
        draw_labels(obs_indices, obs_col, col_obs_pick, is_sim=False)
        
        ax.set_title(title, fontsize=20, fontweight='600', pad=20, color='#2C3E50')
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
        
        clean_title = title.replace(" ", "_").lower()
        img = io.BytesIO()
        fig.savefig(img, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        st.download_button("💾 Télécharger l'image", data=img, file_name=f"{clean_title}.png", mime="image/png", use_container_width=True)

    except Exception as e:
        st.error(f"Erreur de traitement : {e}")

else:
    if source_type == "📂 Fichier CSV":
        st.info("👈 Commencez par glisser votre fichier CSV dans le menu de gauche.")
