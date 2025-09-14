
# Port Orchard Backyard Birds Tracker

This is a Streamlit app + CSV for tracking backyard birds in Port Orchard, WA.

## Quickstart (local)

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Put `port_orchard_backyard_birds_tracker.csv` in the same folder as `streamlit_app.py`.
   (You can use the one exported from ChatGPT.)

3. Run the app:
   ```bash
   streamlit run streamlit_app.py
   ```

4. Use the UI to mark birds as seen, add notes, and pick dates. Click **Save to CSV** to persist locally.
   Optional: Click **Download updated CSV** for a fresh copy.

## (Optional) Save to a free hosted database with Supabase

Supabase offers a generous free tier (hosted Postgres + REST).

1. Sign up at https://supabase.com/ and create a **New Project**.
2. In the SQL editor, paste `supabase_schema.sql` to create the `bird_sightings` table and a dev policy.
3. In **Project Settings → API**, copy your **Project URL** and **anon public key**.
4. Create a `.streamlit/secrets.toml` file next to `streamlit_app.py`:
   ```toml
   [supabase]
   url = "https://YOUR-PROJECT-REF.supabase.co"
   anon_key = "YOUR_ANON_KEY"
   ```
5. Run the app. The **Sync to Supabase** button will upsert records into the `bird_sightings` table.

> ⚠️ The included policy (`allow_anon_rw`) is meant for personal/dev use only. For production, replace with authenticated policies that tie rows to a user ID.

## Images
The app tries to extract an OpenGraph image from the species page in the **Photo (link)**/**Source** column.
You can also add a direct `Image URL` column to the CSV for explicit images.
