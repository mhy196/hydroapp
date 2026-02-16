import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import find_peaks
import io

# --- 1. CONFIGURATION PAGE (Menu Ouvert par défaut) ---
st.set_page_config(
    page_title="Générateur d'Hydrogrammes", 
    layout="wide", 
    page_icon="🌊",
    initial_sidebar_state="expanded" 
)

# --- 2. STYLE CSS ROBUSTE (ACCESSIBILITÉ MAXIMALE) ---
st.markdown("""
<style>
    /* VARIABLES */
    :root {
        --primary: #0277BD; 
        --bg: #FAFAFA;
        --sidebar: #F5F7F9;
        --text: #2C3E50;
    }

    /* FOND GLOBAL */
    .stApp { background-color: var(--bg); color: var(--text); }
    
    /* BARRE LATÉRALE - CONTRASTE */
    section[data-testid="stSidebar"] {
        background-color: var(--sidebar);
        border-right: 2px solid #E0E0E0;
    }
    
    /* TEXTES SIDEBAR */
    section[data-testid="stSidebar"] * {
        color: #1F2937 !important; /* Noir doux forcé */
    }

    /* --- SOLUTION MENU 1 : BOUTON FLÈCHE CUSTOMISÉ --- */
    /* On cible le bouton qui permet de rouvrir le menu */
    [data-testid="stSidebarCollapsedControl"] {
        background-color: #FFFFFF !important; 
        color: #0277BD !important;
        border: 2px solid #0277BD !important;
        border-radius: 50% !important;
        padding: 5px !important;
        width: 40px !important;
        height: 40px !important;
        top: 20px !important;
        left: 20px !important;
        z-index: 999999 !important; /* Au-dessus de tout */
        box-shadow: 2px 2px 10px rgba(0,0,0,0.2) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* Icône dans le bouton */
    [data-testid="stSidebarCollapsedControl"] svg {
        fill: #0277BD !important;
        width: 25px !important;
        height: 25px !important;
    }

    /* --- TABLEAU SAISIE MANUELLE (Espace et Lisibilité) --- */
    div[data-testid="stDataEditor"] {
        border: 1px solid #0277BD;
        border-radius: 8px;
        background-color: white;
    }

    /* SLIDERS & INPUTS */
    .stSlider > div > div > div > div { background-color: var(--primary) !important; }
    
    /* CACHER MENU DEBUG (optionnel) */
    div[data-testid="stToolbar"] { visibility: visible; } 
    
</style>
""", unsafe_allow_html=True)

# --- BOUTON SECOURS (SOLUTION MENU 2) ---
# Un bouton discret en haut à droite pour forcer la réouverture si besoin
col_title, col_reset = st.columns([6, 1])
with col_title:
    st.title("🌊 Générateur d'Hydrogrammes")
with col_reset:
    if st.button("🔄 Ouvrir Menu"):
        st.rerun()

st.markdown("---")

# --- INITIALISATION ---
df = None 

# --- BARRE LATÉRALE ---
st.sidebar.title("1. Données")

# CHOIX SOURCE
source_type = st.sidebar.radio(
    "Source des données :", 
    ["📂 Fichier CSV", "✍️ Saisie Manuelle / Excel"], 
    index=0
)

# --- LOGIQUE D'IMPORTATION ---

if source_type == "📂 Fichier CSV":
    st.sidebar.info("Format attendu : Colonnes Date, Simulé, Observé.")
    uploaded_file = st.sidebar.file_uploader("Glissez votre fichier ici", type=["csv"])
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"Erreur CSV : {e}")

else: # SAISIE MANUELLE (AFFICHER AU CENTRE POUR PLUS DE PLACE)
    st.info("💡 **Mode Édition :** Copiez vos données depuis Excel (Ctrl+C) et collez-les dans la première case ci-dessous (Ctrl+V).")
    
    # Données par défaut pour guider l'utilisateur
    default_data = pd.DataFrame([
        {"Date": "04/02/2026 08:00", "Simulé": 2394, "Observé": 2598},
        {"Date": "04/02/2026 12:00", "Simulé": 2100, "Observé": 2300},
        {"Date": "04/02/2026 16:00", "Simulé": 1800, "Observé": 1950},
        {"Date": "04/02/2026 20:00", "Simulé": 1500, "Observé": 1600},
    ])

    # Le tableau est maintenant dans la page principale (plus large)
    edited_df = st.data_editor(
        default_data,
        num_rows="dynamic",
        use_container_width=True,
        height=300, # Assez haut pour voir
        column_config={
            "Date": st.column_config.TextColumn("Date (JJ/MM/AAAA HH:MM)", help="Format recommandé: 04/02/2026 08:00"),
            "Simulé": st.column_config.NumberColumn("Débit Simulé (m³/s)"),
            "Observé": st.column_config.NumberColumn("Débit Observé (m³/s)"),
        }
    )
    
    if not edited_df.empty:
        df = edited_df

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
    # Slider Horizontal (Négatif = Inverse)
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
        # Nettoyage des noms de colonnes (strip spaces)
        df.columns = [c.strip() for c in df.columns]
        cols = df.columns.tolist()
        
        # Détection automatique des colonnes
        # On cherche 'date' ou 'time', 'sim', 'obs'
        default_date = next((c for c in cols if any(x in c.lower() for x in ["date", "time", "heure"])), cols[0])
        default_sim = next((c for c in cols if "sim" in c.lower()), cols[1] if len(cols)>1 else cols[0])
        default_obs = next((c for c in cols if "obs" in c.lower()), cols[2] if len(cols)>2 else cols[0])

        # Si import CSV, on permet de corriger les colonnes. Si manuel, on fait confiance au tableau.
        if source_type == "📂 Fichier CSV":
             with st.expander("✅ Vérifier les colonnes détectées", expanded=False):
                col_sel1, col_sel2, col_sel3 = st.columns(3)
                date_col = col_sel1.selectbox("Date", cols, index=cols.index(default_date))
                sim_col = col_sel2.selectbox("Simulé", cols, index=cols.index(default_sim))
                obs_col = col_sel3.selectbox("Observé", cols, index=cols.index(default_obs))
        else:
             date_col, sim_col, obs_col = default_date, default_sim, default_obs

        # Conversion Dates
        df['Datetime'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Datetime']) 
        df = df.sort_values('Datetime')

        if df.empty:
            st.warning("⚠️ Aucune date valide. Vérifiez le format (JJ/MM/AAAA HH:MM).")
            st.stop()

        # Calculs Pics
        sim_indices = get_peak_indices(df[sim_col], n_peaks, prominence=peak_sensitivity)
        obs_indices = get_peak_indices(df[obs_col], n_peaks, prominence=peak_sensitivity)
        
        # --- AJUSTEMENT MANUEL (SIDEBAR) ---
        st.sidebar.markdown("---")
        st.sidebar.header("3. Ajustement Fin")
        manual_offsets = {}
        
        # On affiche les ajustements si le nombre de pics est raisonnable
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
                
                # Offset Global
                base_x = global_x_offset if is_sim else -global_x_offset
                base_y = 40 
                
                # Offset Manuel
                k = f"sim_{idx}" if is_sim else f"obs_{idx}"
                mdx, mdy = manual_offsets.get(k, (0,0))
                
                # Dessin
                ax.scatter(time, val, color=color, s=180, zorder=5, edgecolors='white', lw=2)
                ax.annotate(f"{val:.0f}", xy=(time, val), xytext=(base_x + mdx, base_y + mdy), 
                            textcoords='offset points', ha='center', va='bottom', 
                            fontsize=label_size, fontweight='bold', color=color,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, lw=1.5, alpha=0.95),
                            arrowprops=dict(arrowstyle="-", color=color, lw=1.5), zorder=10)

        draw_labels(sim_indices, sim_col, col_sim_pick, is_sim=True)
        draw_labels(obs_indices, obs_col, col_obs_pick, is_sim=False)
        
        # TITRES & STYLE
        ax.set_title(title, fontsize=20, fontweight='600', pad=20, color='#2C3E50')
        ax.set_ylabel(ylabel, fontsize=12, fontweight='bold', color='#2C3E50')
        ax.set_xlabel(xlabel, fontsize=12, fontweight='bold', color='#2C3E50')
        ax.grid(True, alpha=0.2, color='#2C3E50', ls='-')
        ax.legend(fontsize=11, loc='upper right', frameon=True, framealpha=1.0, facecolor='white', edgecolor='#E1E4E8').set_zorder(10)
        
        # AXE X
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
        
        # DOWNLOAD
        clean_title = title.replace(" ", "_").lower()
        img = io.BytesIO()
        fig.savefig(img, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        st.download_button("💾 Télécharger l'image", data=img, file_name=f"{clean_title}.png", mime="image/png", use_container_width=True)

    except Exception as e:
        st.error(f"Une erreur est survenue : {e}")

else:
    if source_type == "📂 Fichier CSV":
        st.info("👈 Commencez par glisser votre fichier CSV dans le menu de gauche.")
