
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
from io import BytesIO

# ---- Config ----
st.set_page_config(page_title="Port Orchard Backyard Birds", page_icon="🕊️", layout="wide")

@st.cache_data(show_spinner=False)
def load_state_from_supabase(user_id: str) -> pd.DataFrame:
    """
    Reads current per-species state for the given user_id
    from table public.bird_sightings.
    """
    if not SUPABASE_ENABLED or not user_id:
        return pd.DataFrame(columns=["species","seen","first_seen_date","notes"])
    try:
        resp = supabase.table("bird_sightings").select(
            "species, seen, first_seen_date, notes"
        ).eq("user_id", user_id).execute()
        rows = resp.data or []
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=["species","seen","first_seen_date","notes"])
        # Normalize
        df["seen"] = df.get("seen", False).fillna(False).astype(bool)
        for c in ["species","first_seen_date","notes"]:
            if c in df.columns:
                df[c] = df[c].fillna("")
        return df
    except Exception:
        return pd.DataFrame(columns=["species","seen","first_seen_date","notes"])


def merge_supabase_state(csv_df: pd.DataFrame, state_df: pd.DataFrame) -> pd.DataFrame:
    """
    Overlay Supabase state (seen/date/notes) onto CSV species metadata.
    CSV key: 'Species'; Supabase key: 'species'.
    """
    if state_df is None or state_df.empty:
        return csv_df.copy()

    state = state_df.rename(columns={
        "species": "Species",
        "first_seen_date": "Date first seen",
        "notes": "Notes"
    }).copy()

    # Map boolean seen -> 'Yes' / ''
    state["Seen?"] = state.get("seen", False).apply(lambda x: "Yes" if bool(x) else "")

    # Keep only overlay columns
    state = state[["Species", "Seen?", "Date first seen", "Notes"]]

    base = csv_df.copy()
    for col in ["Seen?", "Date first seen", "Notes"]:
        if col not in base.columns:
            base[col] = ""

    merged = base.merge(state, on="Species", how="left", suffixes=("", "_sb"))
    for col in ["Seen?", "Date first seen", "Notes"]:
        sb_col = f"{col}_sb"
        if sb_col in merged.columns:
            # If Supabase value present/non-empty, use it; else keep CSV
            merged[col] = merged[sb_col].where(merged[sb_col].notna() & (merged[sb_col] != ""), merged[col])
            merged.drop(columns=[sb_col], inplace=True)
    return merged.fillna("")


@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize columns
    for col in ["Seen?", "Date first seen", "Notes"]:
        if col not in df.columns:
            df[col] = ""
    # Ensure blanks instead of NaN
    df = df.fillna("")
    # Ensure Source / Photo columns exist
    if "Source" not in df.columns and "Photo (link)" in df.columns:
        df["Source"] = df["Photo (link)"]
    return df

@st.cache_data(show_spinner=False)
def get_og_image(url: str) -> str | None:
    """Try to fetch an OpenGraph/Twitter image for the given page URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; BackyardBirdsBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Prefer og:image then twitter:image
        og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
        tw = soup.find("meta", attrs={"name": "twitter:image"}) or soup.find("meta", property="twitter:image")
        for tag in [og, tw]:
            if tag and tag.get("content"):
                return tag.get("content")
    except Exception:
        return None
    return None

# Optional Supabase integration
SUPABASE_ENABLED = False
try:
    from supabase import create_client, Client  # type: ignore
    if "supabase" in st.secrets and all(k in st.secrets["supabase"] for k in ("url", "anon_key")):
        SUPABASE_ENABLED = True
        sb_url = st.secrets["supabase"]["url"]
        sb_key = st.secrets["supabase"]["anon_key"]
        supabase: "Client" = create_client(sb_url, sb_key)
except Exception:
    SUPABASE_ENABLED = False

def supabase_upsert(record: dict):
    if not SUPABASE_ENABLED:
        return
    try:
        supabase.table("bird_sightings").upsert(record, on_conflict="species").execute()
    except Exception as e:
        st.warning(f"Supabase upsert failed: {e}")


def require_supabase():
    if not SUPABASE_ENABLED:
        st.error("Supabase not configured. Add [supabase] url and anon_key in secrets.")
        st.stop()

def auth_ui():
    """Simple email/password auth. Returns (user, session) or (None, None)."""
    require_supabase()

    # Existing session?
    try:
        curr = supabase.auth.get_session()
        if curr and curr.session:
            st.session_state["session"] = curr.session
            st.session_state["user"] = curr.session.user
    except Exception:
        pass

    if "user" in st.session_state and st.session_state["user"]:
        with st.sidebar:
            st.success(f"Logged in: {st.session_state['user'].email}")
            if st.button("Sign out"):
                supabase.auth.sign_out()
                st.session_state.pop("user", None)
                st.session_state.pop("session", None)
                st.rerun()
        return st.session_state["user"], st.session_state["session"]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sign In")
        with st.form("signin_form", clear_on_submit=False):
            email = st.text_input("Email", key="signin_email")
            pw = st.text_input("Password", type="password", key="signin_pw")
            submit = st.form_submit_button("Sign In")
        if submit:
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state["session"] = res.session
                st.session_state["user"] = res.user
                st.success(f"Signed in as {res.user.email}")
                st.rerun()
            except Exception as e:
                st.error(f"Sign-in failed: {e}")

    with col2:
        st.subheader("Sign Up")
        with st.form("signup_form", clear_on_submit=False):
            email2 = st.text_input("Email ", key="signup_email")
            pw2 = st.text_input("Password ", type="password", key="signup_pw")
            submit2 = st.form_submit_button("Create Account")
        if submit2:
            try:
                supabase.auth.sign_up({"email": email2, "password": pw2})
                st.success("Check your email to confirm, then sign in.")
            except Exception as e:
                st.error(f"Sign-up failed: {e}")

    return None, None


st.title("🕊️ Port Orchard Backyard Birds Tracker")
st.caption("Photos © their respective sources. Source links go to Audubon / All About Birds pages.")

user = None
user_id = None
if SUPABASE_ENABLED:
    user, _ = auth_ui()
    if not user:
        st.info("Sign in (or create an account) to track your sightings.")
        st.stop()
    user_id = user.id

data_path = st.text_input("CSV data path", value="birds_db.csv")
csv_df = load_data(data_path)
sb_state_df = load_state_from_supabase(user_id) if SUPABASE_ENABLED else pd.DataFrame()

def merge_supabase_state(csv_df: pd.DataFrame, state_df: pd.DataFrame) -> pd.DataFrame:
    if state_df is None or state_df.empty:
        return csv_df.copy()
    state = state_df.rename(columns={
        "species": "Species",
        "first_seen_date": "Date first seen",
        "notes": "Notes"
    }).copy()
    state["Seen?"] = state.get("seen", False).apply(lambda x: "Yes" if bool(x) else "")
    state = state[["Species","Seen?","Date first seen","Notes"]]
    base = csv_df.copy()
    for col in ["Seen?", "Date first seen", "Notes"]:
        if col not in base.columns:
            base[col] = ""
    merged = base.merge(state, on="Species", how="left", suffixes=("", "_sb"))
    for col in ["Seen?", "Date first seen", "Notes"]:
        sb_col = f"{col}_sb"
        if sb_col in merged.columns:
            merged[col] = merged[sb_col].where(merged[sb_col].notna() & (merged[sb_col] != ""), merged[col])
            merged.drop(columns=[sb_col], inplace=True)
    return merged.fillna("")

df = merge_supabase_state(csv_df, sb_state_df)



# Sidebar bulk helpers
with st.sidebar:
    st.header("Bulk Actions")
    mark_all_seen = st.button("Mark ALL as seen (today)")
    clear_all_seen = st.button("Clear ALL seen/notes/dates")

if mark_all_seen:
    today_str = date.today().isoformat()
    df["Seen?"] = "Yes"
    df["Date first seen"] = today_str
    df["Notes"] = df["Notes"].fillna("")
if clear_all_seen:
    df["Seen?"] = ""
    df["Date first seen"] = ""
    df["Notes"] = ""

# Display birds
for i, row in df.iterrows():
    st.markdown("---")
    cols = st.columns([1, 2, 2])
    # Image / links
    with cols[0]:
        img_url = None
        # Prefer a direct "Image URL" column if present
        if "Image URL" in df.columns and isinstance(row.get("Image URL"), str) and row["Image URL"].strip():
            img_url = row["Image URL"]
        # Otherwise try to scrape OG image from Photo/Source page
        elif isinstance(row.get("Photo (link)"), str) and row["Photo (link)"].strip():
            img_url = get_og_image(row["Photo (link)"])
        elif isinstance(row.get("Source"), str) and row["Source"].strip():
            img_url = get_og_image(row["Source"])

        if img_url:
            try:
                st.image(img_url, caption=row.get("Species", ""), use_container_width=True)
            except Exception:
                st.write("🔗", row.get("Species", ""))
                if isinstance(row.get("Photo (link)"), str) and row["Photo (link)"].strip():
                    st.link_button("Open photo page", row["Photo (link)"])
        else:
            st.write("🔗", row.get("Species", ""))
            if isinstance(row.get("Photo (link)"), str) and row["Photo (link)"].strip():
                st.link_button("Open photo page", row["Photo (link)"])

        # Always show Source link
        if isinstance(row.get("Source"), str) and row["Source"].strip():
            st.markdown(f"[Source]({row['Source']})")

    # Description / habitat
    with cols[1]:
        st.subheader(row.get("Species", "Unknown"))
        st.write(row.get("Description", ""))
        st.markdown(f"**Best time to see:** {row.get('Best time in Port Orchard', '')}")
        st.markdown(f"**Favorite foods:** {row.get('Favorite foods', '')}")
        st.markdown(f"**Typical habitat:** {row.get('Typical habitat', '')}")

    # Inputs for seen / date / notes
    with cols[2]:
        seen_key = f"seen_{i}"
        date_key = f"date_{i}"
        notes_key = f"notes_{i}"

        seen_val = st.checkbox("Seen in my yard", value=(str(row.get("Seen?", "")).strip().lower() == "yes"), key=seen_key)

        # Parse any existing date
        existing_date = None
        try:
            if isinstance(row.get("Date first seen"), str) and row["Date first seen"].strip():
                existing_date = datetime.fromisoformat(row["Date first seen"]).date()
        except Exception:
            existing_date = None

        # Date input should only show if "seen" is checked, otherwise keep blank
        if seen_val:
            date_val = st.date_input(
                "Date first seen",
                value=existing_date or date.today(),
                key=date_key
            )
        else:
            date_val = None

        notes_val = st.text_area("Notes (where/how you saw it)", value=row.get("Notes", ""), key=notes_key, height=80)

    # Persist per-row changes to dataframe (but don't write to disk/db until Save)
    df.at[i, "Seen?"] = "Yes" if seen_val else ""
    df.at[i, "Date first seen"] = date_val.isoformat() if date_val else ""
    df.at[i, "Notes"] = notes_val

st.markdown("---")
save_cols = st.columns([1,1,2])
with save_cols[0]:
    if st.button("💾 Save to CSV"):
        df.to_csv(data_path, index=False)
        st.success(f"Saved to {data_path}")

with save_cols[1]:
    if SUPABASE_ENABLED:
        if st.button("⬆️ Save Sightings"):
            for _, row in df.iterrows():
                record = {
                    "user_id": user_id,  # NEW
                    "species": row.get("Species", ""),
                    "seen": True if str(row.get("Seen?", "")).strip().lower() == "yes" else False,
                    "first_seen_date": row.get("Date first seen", None) or None,
                    "notes": row.get("Notes", "") or "",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
                try:
                    # NEW: conflict on (user_id, species)
                    supabase.table("bird_sightings").upsert(
                        record, on_conflict="user_id,species"
                    ).execute()
                except Exception as e:
                    st.warning(f"Supabase upsert failed: {e}")
            st.success("Synced to Supabase (per user).")
            st.cache_data.clear()
            st.rerun()
    else:
        st.info("Supabase syncing is disabled. Add 'supabase.url' and 'supabase.anon_key' to secrets to enable.")

# Export button (always available)
csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download updated CSV", data=csv_bytes, file_name="birds_db.csv", mime="text/csv")
