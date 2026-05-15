# --- 2. THEME-AGNOSTIC BRANDING CLOAK & HIGH-CONTRAST SPACING ---
st.markdown("""
    <style>
    /* 1. Nuke standard internal structural layout targets and host elements safely */
    [data-testid="stHeader"], header, footer, .stAppFooter, #MainMenu, [data-testid="stDecoration"],
    button[title="Collapse sidebar"], input[aria-label="Show sidebar"], 
    [data-testid="viewerBadge"], .stDeployButton, [class*="viewerBadge"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        opacity: 0 !important;
    }
    
    /* Absolute target to bury the lower-right hosting bar */
    footer, [data-testid="stFooterBlock"], iframe + div {
        display: none !important;
    }
    
    /* 2. Re-stabilize standard application canvas block container */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        margin-top: 0px !important;
    }
    
    /* 3. Custom Dashboard UI Theme Elements */
    .main-header {
        background: linear-gradient(90deg, #ff8c00, #ff0080);
        padding: 20px; border-radius: 15px; text-align: center;
        color: white !important; font-family: 'Arial Black', sans-serif; font-size: 2rem; margin-bottom: 30px;
    }
    
    /* Force high-contrast values inside Metric Cards */
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.08) !important; 
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        padding: 15px; border-radius: 10px;
    }
    div[data-testid="stMetricValue"] div {
        color: #ffffff !important; /* Forces numbers to stay white and readable */
        font-weight: bold !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #cbd5e1 !important; /* Forces sublabels to remain light gray */
    }
    
    .section-header {
        background-color: #e2e8f0; padding: 6px 12px; border-radius: 4px;
        font-weight: bold; margin-bottom: 10px; margin-top: 25px; color: #1e293b;
    }
    
    /* Domain Track Tables Styling */
    .domain-header {
        padding: 12px; border-radius: 8px 8px 0px 0px; text-align: center;
        font-weight: bold; color: #f8fafc; margin-top: 20px; font-size: 1.1rem; letter-spacing: 0.5px;
    }
    .lvl-bg { background-color: rgba(14, 116, 144, 0.3); border: 1px solid #06b6d4; border-bottom: none; }
    .cv-bg { background-color: rgba(21, 128, 61, 0.3); border: 1px solid #10b981; border-bottom: none; }
    .dc-bg { background-color: rgba(161, 98, 7, 0.3); border: 1px solid #eab308; border-bottom: none; }
    .overall-bg { background-color: rgba(147, 51, 234, 0.3); border: 1px solid #a855f7; border-bottom: none; }
    .award-card { background: rgba(255, 215, 0, 0.1); border: 2px solid #ffd700; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; min-height: 160px; }
    </style>
""", unsafe_allow_html=True)
