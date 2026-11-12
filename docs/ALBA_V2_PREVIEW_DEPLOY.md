# ALBA 2.0 — Independent browser preview

The Streamlit prototype in this branch is ready for a **separate preview
deployment**. The existing production app remains on `main`; do not
change its deployment branch.

## Direct deployment entry

[Open ALBA 2.0 deployment in Streamlit Community Cloud](https://share.streamlit.io/deploy?repository=Driniwb%2FALBA-AI&branch=develop%2Falba-v2&mainModule=app.py)

This is the **deployment form**, not a live ALBA 2.0 application URL.
If Streamlit does not prefill the form, choose **Paste GitHub URL** and use:

`https://github.com/Driniwb/ALBA-AI/blob/develop/alba-v2/app.py`

Then confirm the branch and main file below, choose a distinct subdomain,
and select Deploy. The Streamlit account owner must authorize publication.
Only Streamlit can return the new live app URL after deployment.

## Deployment coordinates

| Field | Value |
|---|---|
| Repository | `Driniwb/ALBA-AI` |
| Branch | `develop/alba-v2` |
| Main file / entrypoint | `app.py` |
| Suggested preview subdomain | `alba-v2-preview` (only if available) |
| Python dependencies | `requirements.txt` |

Steps in [Streamlit Community Cloud](https://share.streamlit.io/):

1. Open the workspace that owns the repository and choose **Create app**.
2. Choose **Yup, I have an app**.
3. Enter the repository, `develop/alba-v2`, and `app.py`.
4. Choose a distinct preview URL and **Deploy**.
5. For functioning AI chat, configure `CLOUDFLARE_ACCOUNT_ID` and
   `CLOUDFLARE_API_TOKEN` in the **preview app's secrets settings**.
   NEVER commit credentials to GitHub.
6. For UI-only evaluation, AI credentials are optional; the chat will
   clearly show that the service is not configured.

Do not copy production OIDC or production `ALBA_DATABASE_URL` into
a preview app by default. Account persistence needs an independently
reviewed, correctly isolated data store and authentication configuration.

## What is actually available in the prototype

- Default **Legal Assistant** chat; existing Chat Workspace features.
- New chat, saved chats, projects, chat renaming and moving.
- Sidebar conversation **search by title/project name**.
- Public PDF/DOCX/XLSX/PPTX attachment excerpts via native `+`.
- Dedicated shortcuts to Legal Drafting, ToC Builder and EU Reporting.
- Optional right-hand **Sources & documents** panel with separate tabs.
- Only **user-shared** links to official QBZ/EUR-Lex acts appear as
  references; they are NOT automatically retrieved or certified.
- Browser-guest saves use browser storage; account-backed persistence
  requires verified OIDC **and** PostgreSQL.

## What is explicitly NOT deployed yet

- Automatic official-source retrieval, verified current-law citations, or
  complete legal research in the chat. The isolated retrieval experiments
  in this branch are NOT wired into the chat.
- An indexed, persistent document library (the documents tab lists
  only uploaded excerpt names from this conversation).
- An accurate live replica or proprietary branding of eulaw.ai.

The new design follows general patterns publicly documented by EU Law AI:
chat-first legal work, projects/history, contextual sources and document
review, with distinct ALBA branding.

## QA before production

Run the automated suite:

```bash
python -m unittest discover -s tests -v
```

Then review the preview manually on desktop and mobile: create a project,
send a public synthetic chat, reopen it, search conversations, attach a
public document, open/close sources, navigate to each drafting tool, and
confirm a new chat starts with a clean history.

The preview is not public until a separate Streamlit app is created.
Do NOT invent or advertise a preview URL before the platform returns it.
