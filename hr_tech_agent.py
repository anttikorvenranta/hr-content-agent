#!/usr/bin/env python3

#
#HR Tech Social Media AI Agent
#Searches trending HR tech articles, generates LinkedIn posts,
#stores them in Google Sheets, and sends email notifications.
#

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
"anthropic_api_key" : os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY"),

```
# Google Sheets (via Google Sheets API)
"google_sheets_credentials_file": "google_credentials.json",  # Service account JSON
"spreadsheet_id": "14QZxV8knM_g4AWEkcsXRewTIw42vr6ugdHOR8gXB0VE",  # From the Sheet URL
"sheet_name": "HR Tech Posts",

# Email (Gmail SMTP example)
"smtp_host": "smtp.gmail.com",
"smtp_port": 587,
"email_sender": "antti.korvenranta@gmail.com",
"email_password": os.getenv("EMAIL_PASSWORD", "YOUR_APP_PASSWORD"),  # Gmail App Password
"email_recipient": "antti.korvenranta@gmail.com",

# Search (using Serper.dev or similar — free tier available)
"serper_api_key": os.getenv("SERPER_API_KEY", "YOUR_SERPER_API_KEY"),

# Schedule
"run_every_days": 14,  # Every 2 weeks
```

}

# ============================================================

# STEP 1: SEARCH FOR TRENDING HR TECH ARTICLES

# ============================================================

def search_hr_tech_articles():
#Search for the most recent and trending HR tech articles.
print(“🔍 Searching for trending HR tech articles…”)

```
queries = [
    "HR technology trends 2025",
    "HR tech AI workforce management latest",
    "future of work technology trends",
    "employee experience technology 2025",
    "talent acquisition AI tools latest news",
]

articles = []
headers = {
    "X-API-KEY": CONFIG["serper_api_key"],
    "Content-Type": "application/json"
}

for query in queries[:3]:  # Limit to 3 queries to manage API usage
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
                    "source": r.get("source", "")
                })
    except Exception as e:
        print(f"  Search error for '{query}': {e}")

# Deduplicate by title
seen = set()
unique_articles = []
for a in articles:
    if a["title"] not in seen:
        seen.add(a["title"])
        unique_articles.append(a)

print(f"  Found {len(unique_articles)} unique articles")
return unique_articles[:15]  # Top 15 for validation
```

# ============================================================

# STEP 2: VALIDATE & SELECT MOST TRENDING ARTICLES (via Claude)

# ============================================================

def validate_and_select_articles(articles):
“”“Use Claude to identify the most trending and insightful articles.”””
print(“🤖 Validating and selecting most trending articles with Claude…”)

```
articles_text = "\n\n".join([
    f"Article {i+1}:\nTitle: {a['title']}\nSource: {a['source']}\nDate: {a['date']}\nSnippet: {a['snippet']}\nURL: {a['link']}"
    for i, a in enumerate(articles)
])

prompt = f"""You are an HR technology expert and thought leader. 
```

Here are {len(articles)} recent HR tech articles:

{articles_text}

Please:

1. Evaluate each article for: recency, credibility of source, relevance to HR professionals, and trending topic potential
1. Select the TOP 3 most impactful and trending articles
1. For each selected article, explain briefly WHY it’s trending and relevant

Return your response as JSON in this exact format:
{{
“selected_articles”: [
{{
“index”: <original article number 1-{len(articles)}>,
“title”: “<article title>”,
“url”: “<article url>”,
“why_trending”: “<2-3 sentence explanation of why this is trending and relevant to HR professionals>”
}}
]
}}

Return ONLY the JSON, no other text.”””

```
response = call_claude_api(prompt)
try:
    # Clean up response
    clean = response.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    data = json.loads(clean)
    selected = []
    for s in data.get("selected_articles", []):
        idx = s.get("index", 1) - 1
        if 0 <= idx < len(articles):
            article = articles[idx].copy()
            article["why_trending"] = s.get("why_trending", "")
            selected.append(article)
    print(f"  Selected {len(selected)} top articles")
    return selected
except Exception as e:
    print(f"  Parse error: {e}. Using first 3 articles.")
    return articles[:3]
```

# ============================================================

# STEP 3: GENERATE 3 LINKEDIN POST ALTERNATIVES (via Claude)

# ============================================================

def generate_linkedin_posts(selected_articles):
“”“Generate 3 different LinkedIn post alternatives based on selected articles.”””
print(“✍️  Generating 3 LinkedIn post alternatives…”)

```
articles_summary = "\n\n".join([
    f"Article: {a['title']}\nSource: {a['source']}\nKey insight: {a['why_trending']}\nURL: {a['link']}"
    for a in selected_articles
])

prompt = f"""You are a top HR thought leader and LinkedIn content strategist with 100k+ followers.
```

Based on these trending HR tech articles:

{articles_summary}

Create 3 DIFFERENT LinkedIn post alternatives. Each post should:

- Be 150-250 words long
- Start with a compelling hook (question, bold statement, or surprising fact)
- Include 2-3 key insights synthesized from the articles
- Be written in first person, authentic professional voice
- End with a thought-provoking question to drive engagement
- Include 5-7 relevant hashtags at the end
- Feel human, not AI-generated

Make each post DISTINCTLY different in:

- Post 1: Data/statistics focused angle — lead with numbers and trends
- Post 2: Personal reflection/opinion angle — share a strong POV on what this means for HR leaders
- Post 3: Practical/actionable angle — focus on what HR teams should DO with this information

Return ONLY a JSON object in this exact format:
{{
“posts”: [
{{
“style”: “Data & Trends”,
“text”: “<full post text with hashtags>”,
“hook”: “<first sentence preview>”
}},
{{
“style”: “Thought Leadership”,
“text”: “<full post text with hashtags>”,
“hook”: “<first sentence preview>”
}},
{{
“style”: “Practical & Actionable”,
“text”: “<full post text with hashtags>”,
“hook”: “<first sentence preview>”
}}
],
“source_articles”: [”{selected_articles[0][‘title’] if selected_articles else ‘’}”, “{selected_articles[1][‘title’] if len(selected_articles) > 1 else ‘’}”, “{selected_articles[2][‘title’] if len(selected_articles) > 2 else ‘’}”],
“generated_date”: “{datetime.now().strftime(’%Y-%m-%d’)}”
}}”””

```
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
```

# ============================================================

# STEP 4: SAVE TO GOOGLE SHEETS

# ============================================================

def save_to_google_sheets(posts_data, selected_articles):
“”“Save the generated posts to Google Sheets.”””
print(“📊 Saving posts to Google Sheets…”)

```
try:
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # Support credentials from environment variable (for GitHub Actions)
    # or from a local JSON file (for running on your own machine)
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

    # Get or create the worksheet
    try:
        worksheet = sheet.worksheet(CONFIG["sheet_name"])
    except:
        worksheet = sheet.add_worksheet(CONFIG["sheet_name"], rows=1000, cols=10)
        # Add headers
        headers = [
            "Date Generated", "Run #", "Style", "Hook Preview",
            "Full Post Text", "Status", "Source Articles", "Notes"
        ]
        worksheet.append_row(headers)
        # Format headers (bold)
        worksheet.format("A1:H1", {"textFormat": {"bold": True}})

    # Determine run number
    all_values = worksheet.get_all_values()
    run_number = max(1, len(all_values))  # Approximate run counter

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    sources = " | ".join([a.get("title", "")[:60] for a in selected_articles])

    rows_added = []
    for i, post in enumerate(posts_data.get("posts", [])):
        row = [
            date_str,
            f"Run #{run_number}",
            post.get("style", f"Option {i+1}"),
            post.get("hook", "")[:100],
            post.get("text", ""),
            "Pending Review",  # User will change to Selected/Used
            sources if i == 0 else "",  # Only show sources on first row
            ""
        ]
        worksheet.append_row(row)
        rows_added.append(row)

    # Add separator row
    worksheet.append_row(["---", "", "", "", "", "", "", ""])

    print(f"  ✅ Saved {len(rows_added)} posts to Google Sheets")
    sheet_url = f"https://docs.google.com/spreadsheets/d/{CONFIG['spreadsheet_id']}"
    return sheet_url, rows_added

except ImportError:
    print("  ⚠️  gspread not installed. Run: pip install gspread google-auth")
    return None, []
except Exception as e:
    print(f"  ❌ Google Sheets error: {e}")
    return None, []
```

# ============================================================

# STEP 5: SEND EMAIL NOTIFICATION

# ============================================================

def send_email_notification(posts_data, sheet_url, selected_articles):
“”“Send email notification that new posts are ready.”””
print(“📧 Sending email notification…”)

```
posts = posts_data.get("posts", [])
date_str = datetime.now().strftime("%B %d, %Y")
next_run = (datetime.now() + timedelta(days=CONFIG["run_every_days"])).strftime("%B %d, %Y")

# Build HTML email
posts_html = ""
for i, post in enumerate(posts):
    posts_html += f"""
    <div style="background:#f8f9fa;border-left:4px solid #0077b5;padding:16px;margin:16px 0;border-radius:4px;">
        <h3 style="color:#0077b5;margin:0 0 8px 0;">Option {i+1}: {post.get('style','')}</h3>
        <p style="color:#666;font-style:italic;margin:0 0 12px 0;">"{post.get('hook','')[:120]}..."</p>
        <details>
            <summary style="cursor:pointer;color:#0077b5;font-weight:bold;">View full post →</summary>
            <pre style="white-space:pre-wrap;font-family:Georgia,serif;margin:12px 0;line-height:1.6;">{post.get('text','')}</pre>
        </details>
    </div>"""

sources_html = "".join([
    f'<li><a href="{a.get("link","#")}">{a.get("title","")}</a> — {a.get("source","")}</li>'
    for a in selected_articles
])

html_body = f"""
<html><body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;color:#333;">
    <div style="background:#0077b5;color:white;padding:24px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:22px;">🚀 Your HR Tech LinkedIn Posts Are Ready!</h1>
        <p style="margin:8px 0 0 0;opacity:0.9;">Generated on {date_str}</p>
    </div>
    <div style="padding:24px;border:1px solid #e0e0e0;border-top:none;">
        <p>Your bi-weekly HR tech content is ready for review. I found <strong>{len(selected_articles)} trending articles</strong> and generated <strong>3 post alternatives</strong> for you.</p>

        <h2 style="color:#0077b5;">📰 Source Articles This Week</h2>
        <ul style="line-height:1.8;">{sources_html}</ul>

        <h2 style="color:#0077b5;">✍️ Your 3 Post Options</h2>
        <p style="color:#666;">Preview each option below. Full text available in Google Sheets.</p>
        {posts_html}

        <div style="background:#e8f4fd;padding:16px;border-radius:8px;margin:24px 0;">
            <strong>📊 Review & Select in Google Sheets:</strong><br>
            <a href="{sheet_url or '#'}" style="color:#0077b5;">{sheet_url or 'See your Google Sheet'}</a><br>
            <small>Change "Status" column from "Pending Review" → "Selected" for your chosen post.</small>
        </div>

        <p style="color:#888;font-size:13px;border-top:1px solid #eee;padding-top:16px;">
            Next batch will be generated on: <strong>{next_run}</strong><br>
            This is your automated HR Tech Content Agent
        </p>
    </div>
</html></body>"""

try:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚀 New HR Tech Posts Ready for Review — {date_str}"
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
```

# ============================================================

# HELPER: Call Claude API

# ============================================================

def call_claude_api(prompt, max_tokens=1500):
“”“Call the Anthropic Claude API.”””
headers = {
“x-api-key”: CONFIG[“anthropic_api_key”],
“anthropic-version”: “2023-06-01”,
“content-type”: “application/json”
}
payload = {
“model”: “claude-sonnet-4-20250514”,
“max_tokens”: max_tokens,
“messages”: [{“role”: “user”, “content”: prompt}]
}
try:
response = requests.post(
“https://api.anthropic.com/v1/messages”,
headers=headers,
json=payload,
timeout=60
)
if response.status_code == 200:
return response.json()[“content”][0][“text”]
else:
print(f”  Claude API error: {response.status_code} — {response.text[:200]}”)
return “”
except Exception as e:
print(f”  Claude API exception: {e}”)
return “”

# ============================================================

# MAIN AGENT RUNNER

# ============================================================

def run_agent():
“”“Run the full HR Tech content agent pipeline.”””
print(”\n” + “=”*60)
print(“🤖 HR TECH CONTENT AGENT — Starting Run”)
print(f”   {datetime.now().strftime(’%Y-%m-%d %H:%M:%S’)}”)
print(”=”*60 + “\n”)

```
# Step 1: Search
articles = search_hr_tech_articles()
if not articles:
    print("❌ No articles found. Check your Serper API key.")
    return

# Step 2: Validate
selected = validate_and_select_articles(articles)
if not selected:
    print("❌ Could not select articles.")
    return

# Step 3: Generate posts
posts_data = generate_linkedin_posts(selected)
if not posts_data.get("posts"):
    print("❌ Could not generate posts.")
    return

# Step 4: Save to Google Sheets
sheet_url, rows = save_to_google_sheets(posts_data, selected)

# Step 5: Send email
send_email_notification(posts_data, sheet_url, selected)

print("\n" + "="*60)
print("✅ AGENT RUN COMPLETE")
print(f"   Posts generated: {len(posts_data.get('posts', []))}")
print(f"   Source articles: {len(selected)}")
print(f"   Next run: {(datetime.now() + timedelta(days=CONFIG['run_every_days'])).strftime('%Y-%m-%d')}")
print("="*60 + "\n")
```

# ============================================================

# SCHEDULER (runs every 14 days)

# ============================================================

def run_with_schedule():
“”“Run the agent on a schedule.”””
try:
import schedule
print(f”⏰ Scheduler started — agent will run every {CONFIG[‘run_every_days’]} days”)
print(”   Running first batch now…\n”)

```
    # Run immediately on start
    run_agent()

    # Schedule future runs
    schedule.every(CONFIG["run_every_days"]).days.do(run_agent)

    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour

except ImportError:
    print("📦 schedule not installed. Run: pip install schedule")
    print("Running agent once now instead...\n")
    run_agent()
```

if **name** == “**main**”:
import sys
if “–once” in sys.argv:
run_agent()
else:
run_with_schedule()
