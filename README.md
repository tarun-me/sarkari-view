# 🎯 Automated AI-Powered Sarkari Job Tracker

A fully integrated, automated, and modern **Government Job & Exam Recruitment Notification Tracker**. This portal automatically extracts and filters the top 15 latest notifications from central/state government portals and web aggregators (like Sarkari Result) every 4 hours. 

The data, parsed using the Groq Llama 3.3 Engine, is synced directly to a cloud-based **Supabase Database (PostgreSQL)** and displayed live on a Streamlit dashboard.

🌐 **Live Project Dashboard:** [Paste Your Streamlit Live Link Here]

---

## 🏗️ System Architecture & Workflow

The fully automated data flow of the system executes seamlessly across the following layers:

1. **Scraper Trigger:** GitHub Actions Cron Scheduler invokes the server wake-up every 4 hours.
2. **Stealth Extraction Layer:** The Headless Selenium Engine and Backup HTTP Fallback Engine pull raw data (text/PDFs) from targeted websites.
3. **Local Filter:** Data proceeds to the processing stream only if relevant keywords are matched.
4. **AI Parsing & Verification:** The Groq Llama 3.3 model extracts core structural attributes from raw text/PDF blocks.
5. **Database Smart Sync:** Supabase checks if the data is a new entry (Insert) or an update (Merge). Duplicate items are automatically blocked.
6. **Frontend View:** Global users access live dynamic entries on the Streamlit web application dashboard.

---

## 🛠️ Tech Stack Matrix

* **Frontend View Panel:** Streamlit Web Framework, Pandas (Interactive Clean Dataframes)
* **Web Scraping Infrastructure:** Python 3.11, Selenium WebDriver (Headless Architecture Optimization), BeautifulSoup4, Custom Python Requests
* **Data Processing Layer:** pdfplumber Engine (Binary Stream PDF Text Extraction)
* **Cloud Database Pipeline:** Supabase (Cloud Infrastructure powered by Relational PostgreSQL Engine)
* **Machine Learning Engine:** Groq Cloud Native API Integration (Llama 3.3 70B Model - JSON Mode)
* **Automation Scheduler:** GitHub Actions Runner Instances (Ubuntu Cloud Architecture Continuous Deployment)

---

## 🚀 Key Technical Implementation Features

* **Dual-Engine Stealth Web Scraper:** Equipped with a Headless Selenium Engine (Eager Loading Strategy) and an active **Stealth HTTP Fallback** system. If heavy JavaScript tracking scripts or firewalls (NIC Network Layer) drop the automated browser request, the script instantly switches to a mobile user-agent to decode the raw HTML text.
* **Aggregator Deep Path Crawling:** Beyond basic target listing updates, it tracks dynamic routes (`/latestjob/`, `/force/`, `/ssc/`, `/bank/`) of the Sarkari Result portal, fully parsing the descriptions of the **Top 15 Job Posts** to ensure critical updates like Agniveer, Navy, Army, and banking metrics are never missed.
* **Intelligent AI Parsing via Groq:** To conserve token usage and server resources, raw context blocks are passed directly to the Groq Cloud API (`llama-3.3-70b-versatile`) pipeline, ensuring high execution speed and advanced contextual inference capabilities.
* **Zero Duplication Merge Engine:** The project backend utilizes a double protection layer:
  1. *AI Level Validation:* The Groq pipeline matches text fields and identifies existing IDs to intelligently overwrite (Merge) auto-updates.
  2. *Database Constraints:* The Supabase `notice_subject` column enforces a strict `UNIQUE` constraint, completely preventing repeated textual injections system-wide.

---

## ⚙️ Core Secrets & Environment Variables

To ensure secure integration and execution, adding the following configuration parameters to your repository secrets or `.env` file is mandatory:

```env
GROQ_API_KEY=your_groq_cloud_dashboard_api_key
SUPABASE_URL=your_supabase_project_rest_endpoint
SUPABASE_KEY=your_supabase_anon_public_jwt_token
```

<h3>💻 Local Machine Development Setup
Follow these steps to run the configuration and server files on your local machine:</h3>

1. Clone the Repository
``` 
git clone [https://github.com/your-username/sarkari-view.git](https://github.com/your-username/sarkari-view.git)
cd sarkari-view
```

2. Install External Project Modules
```
pip install -r requirements.txt
```

3. Setup Local Configuration Details:
Create a .env text file inside the root folder and populate it with your credentials:
```
GROQ_API_KEY="your-groq-key-token-here"
SUPABASE_URL="[https://your-project-id.supabase.co](https://your-project-id.supabase.co)"
SUPABASE_KEY="your-long-anon-public-jwt-key"
```
4. Run Core Backend Aggregator Script
```
python ai_aggregator.py
```
6. Launch Local Web Server UI Panel
```
streamlit run app.py
```
