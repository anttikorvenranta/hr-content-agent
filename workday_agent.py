#!/usr/bin/env python3
"""
Workday Content AI Agent
Searches trending Workday announcements, product releases, and community
discussions from public sources, generates LinkedIn posts, stores them
in Google Sheets, and sends email notifications every 2 weeks.
"""

import os
import json
import time
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ============================================================
# CONFIGURATION — Fill these in before running
# ============================================================
CONFIG = {
    # Anthropic API
    "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY"),

    # Google Sheets
    "google_sheets_credentials_file": "google_credentials.json",
    "spreadsheet_id": "YOUR_GOOGLE_SHEET_ID",  # ✏️ Change this
    "sheet_name": "Workday Posts",              # Separate tab from HR Tech agent

    # Email
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "email_sender": "your_email@gmail.com",     # ✏️ Change this
    "email_password": os.getenv("EMAIL_PASSWORD", "YOUR_APP_PASSWORD"),
    "email_recipient": "your_email@gmail.com",  # ✏️ Change this

    # Search
    "serper_api_key": os.getenv("SERPER_API_KEY", "YOUR_SERPER_API_KEY"),

    # Schedule
    "run_every_days": 14,
}

# ============================================================
# STEP 1: SEARCH WORKDAY-SPECIFIC PUBLIC SOURCES
# ============================================================
def search_workday_content():
    """Search public Workday sources for announcements and trending discussions."""
    print("🔍 Searching Workday public sources...")

    # Targeted queries covering product announcements + community discussions
    queries = [
        "Workday product announcement release 2025",
        "Workday new features update site:blog.workday.com OR site:newsroom.workday.com",
        "Workday community trending discussion HR finance",
        "Workday AI machine learning announcement",
        "Workday release notes update latest",
        "\"Workday\" announcement OR release OR update",
    ]

    # Also fetch Workday's official blog RSS/pages directly
    direct_sources = [
        {
            "url": "https://blog.workday.com/en-us/topic/product-and-technology.html",
            "source_name": "Workday Blog — Product & Technology"
        },
        {
            "url": "https://newsroom.workday.com/news-releases",
            "source_name": "Workday Newsroom"
        },
    ]

    articles = []
    headers = {
        "X-API-KEY": CONFIG["serper_api_key"],
        "Content-Type": "application/json"
    }

    # Search via Serper
    for query in queries[:4]:
        payload = {
            "q": query,
            "num": 5,
            "tbs": "qdr:m"  # Past month only
        }
        try:
            response = requests.post(
                "https://google.serper.dev/news",
                headers=headers,
                json=payload,
                timeout=10
            )
            if response.status_code == 200:
                results = response.json().get("news", [])
                for r in results:
                    articles.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", ""),
                        "link": r.get("link", ""),
                        "date": r.get("date", ""),
                        "source": r.get("source", ""),
                        "content_type": classify_content_type(r.get("title", ""), r.get("snippet", ""))
                    })
        except Exception as e:
            print(f"  Search error for '{query}': {e}")

    # Also search web (not just news) for official Workday pages
    for query in ["Workday release notes 2025", "Workday new features announcement"]:
        payload = {"q": query, "num": 5}
        try:
            response = requests.post(
                "https://google.serper.dev/search",
                headers=headers,
                json=payload,
                timeout=10
            )
            if response.status_code == 200:
                results = response.json().get("organic", [])
                for r in results:
                    # Prioritise official Workday domains
                    link = r.get("link", "")
                    if any(d in link for d in ["workday.com", "blog.workday", "newsroom.workday"]):
                        articles.append({
                            "title": r.get("title", ""),
                            "snippet": r.get("snippet", ""),
                            "link": link,
                            "date": "Recent",
                            "source": "Workday Official",
                            "content_type": classify_content_type(r.get("title", ""), r.get("snippet", ""))
                        })
        except Exception as e:
            print(f"  Web search error: {e}")

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        key = a["title"].lower()[:60]
        if key and key not in seen:
            seen.add(key)
            unique.append(a)

    print(f"  Found {len(unique)} unique Workday items")
    return unique[:20]


def classify_content_type(title, snippet):
    """Classify whether content is an announcement/release or community discussion."""
    text = (title + " " + snippet).lower()
    if any(w in text for w in ["release", "announce", "launch", "new feature", "update", "version"]):
        return "Product Announcement"
    elif any(w in text for w in ["community", "discussion", "forum", "tip", "best practice", "how to"]):
        return "Community Discussion"
    else:
        return "Workday News"


# ============================================================
# STEP 2: VALIDATE & SELECT TOP WORKDAY CONTENT (via Claude)
# ============================================================
def validate_and_select_content(articles):
    """Use Claude to pick the most impactful Workday items."""
    print("🤖 Validating and selecting top Workday content with Claude...")

    articles_text = "\n\n".join([
        f"Item {i+1}:\nTitle: {a['title']}\nType: {a['content_type']}\nSource: {a['source']}\nDate: {a['date']}\nSnippet: {a['snippet']}\nURL: {a['link']}"
        for i, a in enumerate(articles)
    ])

    prompt = f"""You are a Workday platform expert and HR technology thought leader.

Here are {len(articles)} recent Workday-related items from public sources:

{articles_text}

Please:
1. Evaluate each item for: recency, official source credibility, impact on Workday users/admins/HR professionals, and discussion potential
2. Prioritise: official Workday product announcements, significant feature releases, and highly discussed community topics
3. Select the TOP 3 most impactful items
4. For each, explain WHY it matters to Workday practitioners

Return ONLY JSON in this exact format:
{{
  "selected_articles": [
    {{
      "index": <original item number 1-{len(articles)}>,
      "title": "<item title>",
      "url": "<item url>",
      "content_type": "<Product Announcement or Community Discussion or Workday News>",
      "why_trending": "<2-3 sentences on why this matters to Workday users and HR/Finance professionals>"
    }}
  ]
}}"""

    response = call_claude_api(prompt)
    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            if clean.endswith("```"):
                clean = clean[:-3]
        data = json.loads(clean)
        selected = []
        for s in data.get("selected_articles", []):
            idx = s.get("index", 1) - 1
            if 0 <= idx < len(articles):
                article = articles[idx].copy()
                article["why_trending"] = s.get("why_trending", "")
                article["content_type"] = s.get("content_type", article.get("content_type", ""))
                selected.append(article)
        print(f"  Selected {len(selected)} top Workday items")
        return selected
    except Exception as e:
        print(f"  Parse error: {e}. Using first 3 items.")
        return articles[:3]


# ============================================================
# STEP 3: GENERATE 3 LINKEDIN POST ALTERNATIVES (via Claude)
# ============================================================
def generate_linkedin_posts(selected_articles):
    """Generate 3 LinkedIn post alternatives focused on Workday content."""
    print("✍️  Generating 3 Workday LinkedIn post alternatives...")

    articles_summary = "\n\n".join([
        f"Item: {a['title']}\nType: {a.get('content_type','')}\nKey insight: {a['why_trending']}\nURL: {a['link']}"
        for a in selected_articles
    ])

    prompt = f"""You are a Workday thought leader, certified consultant, and LinkedIn content creator with 50k+ followers in the Workday ecosystem.

Based on these trending Workday items:

{articles_summary}

Create 3 DIFFERENT LinkedIn post alternatives. Each post should:
- Be 150-250 words long
- Start with a compelling hook relevant to Workday practitioners (admins, implementers, HR/Finance leaders)
- Reference specific Workday features, modules, or community topics naturally
- Be written in first person, authentic professional voice — like a real Workday consultant sharing insights
- End with a thought-provoking question to spark discussion in the Workday community
- Include 5-7 relevant hashtags (mix of #Workday, #WorkdayHCM, #WorkdayFinancials, #HRTech etc.)
- Feel human and specific — NOT generic AI content

Make each post DISTINCTLY different:
- Post 1: "What's New" angle — focus on the product announcement/release and what it means for Workday customers
- Post 2: Practitioner insight — share a strong opinion on how this changes day-to-day work for Workday admins or end users
- Post 3: Community & best practice — frame around what the Workday community is discussing and what practitioners should know

Return ONLY a JSON object in this exact format:
{{
  "posts": [
    {{
      "style": "What's New in Workday",
      "text": "<full post text with hashtags>",
      "hook": "<first sentence>"
    }},
    {{
      "style": "Practitioner Insight",
      "text": "<full post text with hashtags>",
      "hook": "<first sentence>"
    }},
    {{
      "style": "Community & Best Practice",
      "text": "<full post text with hashtags>",
      "hook": "<first sentence>"
    }}
  ],
  "source_articles": ["{selected_articles[0]['title'] if selected_articles else ''}", "{selected_articles[1]['title'] if len(selected_articles) > 1 else ''}", "{selected_articles[2]['title'] if len(selected_articles) > 2 else ''}"],
  "generated_date": "{datetime.now().strftime('%Y-%m-%d')}"
}}"""

    response = call_claude_api(prompt, max_tokens=2000)
    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            if clean.endswith("```"):
                clean = clean[:-3]
        data = json.loads(clean)
        print(f"  Generated {len(data.get('posts', []))} post alternatives")
        return data
    except Exception as e:
        print(f"  Parse error: {e}")
        return {"posts": [], "source_articles": [], "generated_date": datetime.now().strftime('%Y-%m-%d')}


# ============================================================
# STEP 4: SAVE TO GOOGLE SHEETS
# ============================================================
def save_to_google_sheets(posts_data, selected_articles):
    """Save the generated Workday posts to Google Sheets."""
    print("📊 Saving Workday posts to Google Sheets...")

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Support credentials from environment variable (GitHub Actions)
        # or from a local JSON file (running locally)
        google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if google_creds_json:
            import json as _json
            creds_dict = _json.loads(google_creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(
                CONFIG["google_sheets_credentials_file"],
                scopes=scopes
            )

        client = gspread.authorize(creds)
        sheet = client.open_by_key(CONFIG["spreadsheet_id"])

        try:
            worksheet = sheet.worksheet(CONFIG["sheet_name"])
        except:
            worksheet = sheet.add_worksheet(CONFIG["sheet_name"], rows=1000, cols=10)
            headers = [
                "Date Generated", "Run #", "Style", "Content Type",
                "Hook Preview", "Full Post Text", "Status", "Source Items", "Notes"
            ]
            worksheet.append_row(headers)
            worksheet.format("A1:I1", {"textFormat": {"bold": True}})

        all_values = worksheet.get_all_values()
        run_number = max(1, len(all_values))

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        sources = " | ".join([a.get("title", "")[:60] for a in selected_articles])
        content_types = ", ".join(set([a.get("content_type", "") for a in selected_articles]))

        rows_added = []
        for i, post in enumerate(posts_data.get("posts", [])):
            row = [
                date_str,
                f"Run #{run_number}",
                post.get("style", f"Option {i+1}"),
                content_types if i == 0 else "",
                post.get("hook", "")[:100],
                post.get("text", ""),
                "Pending Review",
                sources if i == 0 else "",
                ""
            ]
            worksheet.append_row(row)
            rows_added.append(row)

        worksheet.append_row(["---", "", "", "", "", "", "", "", ""])

        print(f"  ✅ Saved {len(rows_added)} Workday posts to Google Sheets")
        sheet_url = f"https://docs.google.com/spreadsheets/d/{CONFIG['spreadsheet_id']}"
        return sheet_url, rows_added

    except ImportError:
        print("  ⚠️  gspread not installed. Run: pip install gspread google-auth")
        return None, []
    except Exception as e:
        print(f"  ❌ Google Sheets error: {e}")
        return None, []


# ============================================================
# STEP 5: SEND EMAIL NOTIFICATION
# ============================================================
def send_email_notification(posts_data, sheet_url, selected_articles):
    """Send email notification that new Workday posts are ready."""
    print("📧 Sending email notification...")

    posts = posts_data.get("posts", [])
    date_str = datetime.now().strftime("%B %d, %Y")
    next_run = (datetime.now() + timedelta(days=CONFIG["run_every_days"])).strftime("%B %d, %Y")

    posts_html = ""
    for i, post in enumerate(posts):
        posts_html += f"""
        <div style="background:#f8f9fa;border-left:4px solid #f05a28;padding:16px;margin:16px 0;border-radius:4px;">
            <h3 style="color:#f05a28;margin:0 0 8px 0;">Option {i+1}: {post.get('style','')}</h3>
            <p style="color:#666;font-style:italic;margin:0 0 12px 0;">"{post.get('hook','')[:120]}..."</p>
            <details>
                <summary style="cursor:pointer;color:#f05a28;font-weight:bold;">View full post →</summary>
                <pre style="white-space:pre-wrap;font-family:Georgia,serif;margin:12px 0;line-height:1.6;">{post.get('text','')}</pre>
            </details>
        </div>"""

    sources_html = "".join([
        f'<li><a href="{a.get("link","#")}">{a.get("title","")}</a> <span style="color:#999;font-size:12px;">— {a.get("content_type","")}</span></li>'
        for a in selected_articles
    ])

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;color:#333;">
        <div style="background:#f05a28;color:white;padding:24px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:22px;">⚡ Your Workday LinkedIn Posts Are Ready!</h1>
            <p style="margin:8px 0 0 0;opacity:0.9;">Generated on {date_str}</p>
        </div>
        <div style="padding:24px;border:1px solid #e0e0e0;border-top:none;">
            <p>Your bi-weekly Workday content is ready for review. I found <strong>{len(selected_articles)} trending Workday items</strong> and generated <strong>3 post alternatives</strong> for you.</p>

            <h2 style="color:#f05a28;">📰 Source Content This Cycle</h2>
            <ul style="line-height:1.8;">{sources_html}</ul>

            <h2 style="color:#f05a28;">✍️ Your 3 Post Options</h2>
            <p style="color:#666;">Preview each option below. Full text available in Google Sheets.</p>
            {posts_html}

            <div style="background:#fff3ee;padding:16px;border-radius:8px;margin:24px 0;border:1px solid #f05a28;">
                <strong>📊 Review & Select in Google Sheets:</strong><br>
                <a href="{sheet_url or '#'}" style="color:#f05a28;">{sheet_url or 'See your Google Sheet'}</a><br>
                <small>Change "Status" from "Pending Review" → "Selected" for your chosen post. Tab: <strong>Workday Posts</strong></small>
            </div>

            <p style="color:#888;font-size:13px;border-top:1px solid #eee;padding-top:16px;">
                Next batch will be generated on: <strong>{next_run}</strong><br>
                This is your automated Workday Content Agent
            </p>
        </div>
    </html></body>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"⚡ New Workday Posts Ready for Review — {date_str}"
        msg["From"] = CONFIG["email_sender"]
        msg["To"] = CONFIG["email_recipient"]
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(CONFIG["smtp_host"], CONFIG["smtp_port"]) as server:
            server.starttls()
            server.login(CONFIG["email_sender"], CONFIG["email_password"])
            server.sendmail(CONFIG["email_sender"], CONFIG["email_recipient"], msg.as_string())

        print(f"  ✅ Email sent to {CONFIG['email_recipient']}")
    except Exception as e:
        print(f"  ❌ Email error: {e}")


# ============================================================
# HELPER: Call Claude API
# ============================================================
def call_claude_api(prompt, max_tokens=1500):
    """Call the Anthropic Claude API."""
    headers = {
        "x-api-key": CONFIG["anthropic_api_key"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60
        )
        if response.status_code == 200:
            return response.json()["content"][0]["text"]
        else:
            print(f"  Claude API error: {response.status_code} — {response.text[:200]}")
            return ""
    except Exception as e:
        print(f"  Claude API exception: {e}")
        return ""


# ============================================================
# MAIN AGENT RUNNER
# ============================================================
def run_agent():
    """Run the full Workday content agent pipeline."""
    print("\n" + "="*60)
    print("⚡ WORKDAY CONTENT AGENT — Starting Run")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

    articles = search_workday_content()
    if not articles:
        print("❌ No Workday content found. Check your Serper API key.")
        return

    selected = validate_and_select_content(articles)
    if not selected:
        print("❌ Could not select content.")
        return

    posts_data = generate_linkedin_posts(selected)
    if not posts_data.get("posts"):
        print("❌ Could not generate posts.")
        return

    sheet_url, rows = save_to_google_sheets(posts_data, selected)
    send_email_notification(posts_data, sheet_url, selected)

    print("\n" + "="*60)
    print("✅ WORKDAY AGENT RUN COMPLETE")
    print(f"   Posts generated: {len(posts_data.get('posts', []))}")
    print(f"   Source items: {len(selected)}")
    print(f"   Next run: {(datetime.now() + timedelta(days=CONFIG['run_every_days'])).strftime('%Y-%m-%d')}")
    print("="*60 + "\n")


# ============================================================
# SCHEDULER
# ============================================================
def run_with_schedule():
    """Run the agent on a schedule."""
    try:
        import schedule
        print(f"⏰ Scheduler started — Workday agent runs every {CONFIG['run_every_days']} days")
        run_agent()
        schedule.every(CONFIG["run_every_days"]).days.do(run_agent)
        while True:
            schedule.run_pending()
            time.sleep(3600)
    except ImportError:
        print("📦 schedule not installed. Run: pip install schedule")
        run_agent()


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        run_agent()
    else:
        run_with_schedule()