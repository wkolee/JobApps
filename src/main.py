import yaml
from pathlib import Path
from src.sourcing.greenhouse import fetch_greenhouse_jobs, fetch_greenhouse_description
from src.sourcing.lever import fetch_lever_jobs, fetch_lever_description
from src.sourcing.targets import load_targets, resolve_targets
from src.scoring.rules import simple_score
from src.tailoring.llm_tailor import make_tailored_summary, make_cover_letter
from src.tracking.store import get_conn, upsert_application

CONFIG = yaml.safe_load(Path("config/config.yml").read_text())
TITLES = yaml.safe_load(Path("config/titles.yml").read_text())

# Replace with real targets

def run():
    # Load category-based targets (enterprise/midmarket/startup)
    raw_targets = load_targets("config/targets.yml")
    targets = resolve_targets(raw_targets)
    print({k: len(v) for k,v in targets.items()})
    
    # flatten by provider
    gh_handles = [x['handle'] for cat in targets.values() for x in cat if x['provider']=='greenhouse']
    lv_handles = [x['handle'] for cat in targets.values() for x in cat if x['provider']=='lever']
    
    conn = get_conn(CONFIG["tracking_db"])
    base_resume = Path(CONFIG["resume_path"]).read_text()
    collected = []

    for gh in gh_handles:
        try:
            collected += fetch_greenhouse_jobs(gh)
        except Exception as e:
            print(f"[greenhouse:{gh}] failed: {e}")

    for lv in lv_handles:
        try:
            collected += fetch_lever_jobs(lv)
        except Exception as e:
            print(f"[lever:{lv}] failed: {e}")

    for job in collected:
        try:
            jd = fetch_greenhouse_description(job["url"]) if job["source"]=="greenhouse" else fetch_lever_description(job["url"])

            score = simple_score(jd, job["title"], {
                "titles": TITLES,
                "skills_must_have": CONFIG["skills_must_have"],
                "skills_nice_to_have": CONFIG["skills_nice_to_have"]
            })

            status = "found"
            if score >= CONFIG["min_score_to_tailor"]:
                why_fit = make_tailored_summary(jd, base_resume, job["title"], job["company"])
                cover_letter = make_cover_letter(CONFIG["cover_letter_template"], job["title"], job["company"], why_fit)
                out = Path("data/output/tailored"); out.mkdir(parents=True, exist_ok=True)
                safe = f"{job['company']}_{job['title']}".replace('/','-').replace(' ','_')
                (out / f"{safe}__cover_letter.txt").write_text(cover_letter)
                status = "tailored"

            upsert_application(conn, {
                "source": job["source"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "url": job["url"],
                "score": score,
                "status": status
            })
            print(f"[{job['source']}] {job['company']} — {job['title']} — score={score:.2f} — {status}")
        except Exception as e:
            print(f"[process] {job.get('url','?')} failed: {e}")

if __name__ == "__main__":
    run()
