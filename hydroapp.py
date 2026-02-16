import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import find_peaks
import io

# --- CONFIGURATION PAGE ---
st.set_page_config(
    page_title="Générateur d'Hydrogrammes", 
    layout="wide", 
    page_icon="🌊",
    initial_sidebar_state="expanded"
)

# --- CSS DESIGN ---
st.markdown("""
<style>
    :root {
        --primary-color: #0277BD; --bg-color: #FAFAFA; --sidebar-bg: #F5F7F9;
        --text-main: #2C3E50; --text-sidebar: #1F2937;
    }
    .stApp { background-color: var(--bg-color); color: var(--text-main); }
    section[data-testid="stSidebar"] { background-color: var(--sidebar-bg); border-right: 1px solid #E5E7EB; }
    section[data-testid="stSidebar"] * { color: var(--text-sidebar) !important; }
    
    /* Bouton Menu */
    button[kind="header"] { background-color: transparent !important; color: var(--primary-color) !important; }
    [data-testid="stSidebarCollapsedControl"] { color: var(--primary-color) !important; background-color: white !important; border: 1px solid #ddd; }
    
    /* Sliders & Inputs */
    .stSlider > div > div > div > div { background-color: var(--primary-color) !important; }
    .stTextInput > div > div > input { background-color: #FFFFFF !important; color: #000000 !important; }
    
    h1 { color: var(--primary-color) !important; }
    div[data-testid="stToolbar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("🌊 Générateur d'Hydrogrammes")
st.markdown("---")

# --- BARRE LATÉRALE ---
st.sidebar.header("1. Vos Données")

# --- CHOIX DE LA SOURCE ---
source_type = st.sidebar.radio("Source des données", ["Fichier CSV", "Saisie Manuelle / Coller"], index=0)

df = None # Initialisation

if source_type == "Fichier CSV":
    uploaded_file = st.sidebar.file_uploader("Glissez votre fichier CSV ici", type=["csv"])
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"Erreur de lecture CSV : {e}")

else: # Saisie Manuelle
    st.sidebar.info("Collez vos données depuis Excel ou remplissez le tableau.")
    
    # Création d'un dataframe vide par défaut pour l'éditeur
    default_data = pd.DataFrame([
        {"Date": "2026-02-04 08:00", "Simulé": 2394, "Observé": 2598},
        {"Date": "2026-02-04 12:00", "Simulé": 2100, "Observé": 2300},
        {"Date": "2026-02-04 16:00", "Simulé": 1800, "Observé": 1950},
    ])
    
    # Éditeur de données (Data Editor)
    edited_df = st.sidebar.data_editor(
        default_data, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True
    )
    
    if not edited_df.empty:
        df = edited_df

# 2. APPARENCE
st.sidebar.header("2. Apparence")
title = st.sidebar.text_input("Titre du graphique", "Hydrogramme de Crue")

c1, c2 = st.sidebar.columns(2)
col_sim_pick = c1.color_picker("Simulé", "#0288D1") 
col_obs_pick = c2.color_picker("Observé", "#D32F2F")

# 3. RÉGLAGES AVANCÉS
with st.sidebar.expander("⚙️ Réglages Avancés"):
    st.markdown("**Paramètres des Pics**")
    n_peaks = st.slider("Nombre de pics max", 1, 20, 6)
    peak_sensitivity = st.slider("Sensibilité détection", 1, 200, 10)
    
    st.markdown("**Mise en page**")
    global_x_offset = st.slider("Écartement horizontal (Négatif=Inverse)", -100, 100, 25)
    label_size = st.slider("Taille du texte", 8, 20, 11)
    show_hours = st.checkbox("Afficher les heures", value=True)
    
    st.markdown("**Titres des Axes**")
    ylabel = st.text_input("Titre Axe Y", "Débit (m³/s)")
    xlabel = st.text_input("Titre Axe X", "Date et Heure")

# --- FONCTIONS ---
def get_peak_indices(series, n, prominence=10, distance=5):
    series = series.fillna(0)
    peaks, _ = find_peaks(series, prominence=prominence, distance=distance)
    if len(peaks) == 0: return [series.idxmax()]
    peak_df = pd.DataFrame({'index': series.index[peaks], 'val': series.iloc[peaks].values})
    return sorted(peak_df.sort_values(by='val', ascending=False).head(n)['index'].tolist())

# --- LOGIQUE PRINCIPALE ---
if df is not None and not df.empty:
    try:
        # Détection auto des colonnes (robuste pour CSV et Saisie)
        cols = df.columns.tolist()
        
        # Logique de détection par mots-clés
        default_date = next((c for c in cols if any(x in c.lower() for x in ["date", "time", "heure"])), cols[0])
        default_sim = next((c for c in cols if "sim" in c.lower()), cols[1] if len(cols)>1 else cols[0])
        default_obs = next((c for c in cols if "obs" in c.lower()), cols[2] if len(cols)>2 else cols[0])

        if source_type == "Fichier CSV":
             with st.expander("Vérifier les colonnes détectées", expanded=False):
                c1, c2, c3 = st.columns(3)
                date_col = c1.selectbox("Date", cols, index=cols.index(default_date))
                sim_col = c2.selectbox("Simulé", cols, index=cols.index(default_sim))
                obs_col = c3.selectbox("Observé", cols, index=cols.index(default_obs))
        else:
             # Pour la saisie manuelle, on assume l'ordre ou les noms par défaut si l'utilisateur ne change rien
             date_col, sim_col, obs_col = default_date, default_sim, default_obs

        # Conversion et Tri
        # Gestion flexible des formats de date (DD/MM/YYYY ou YYYY-MM-DD)
        df['Datetime'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Datetime']) # Supprime les lignes sans date valide
        df = df.sort_values('Datetime')
        
        if df.empty:
            st.error("Aucune date valide trouvée. Vérifiez le format (ex: 04/02/2026 08:00).")
            st.stop()

        # DÉTECTION
        sim_indices = get_peak_indices(df[sim_col], n_peaks, prominence=peak_sensitivity)
        obs_indices = get_peak_indices(df[obs_col], n_peaks, prominence=peak_sensitivity)
        
        # AJUSTEMENT MANUEL
        st.sidebar.markdown("---")
        st.sidebar.header("3. Ajustement Manuel")
        st.sidebar.caption("Déplacez les étiquettes si elles se chevauchent.")
        
        manual_offsets = {} 
        expand_manual = len(sim_indices) + len(obs_indices) < 10
        
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

        # GÉNÉRATION GRAPHIQUE
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
        st.error(f"Une erreur est survenue : {e}")
        st.info("Vérifiez le format de vos données (dates notamment).")

else:
    st.info("👈 Commencez par choisir une source de données dans le menu.")
