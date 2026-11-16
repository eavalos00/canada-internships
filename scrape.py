"""Pull Canadian internship, co-op and new-grad roles from public job boards.

Sources: Greenhouse, Lever and Ashby public job-board feeds (no login needed).
Edit companies.json to add companies. Output: jobs.json, README.md, skipped.json.
"""
import json, re, datetime, requests

C = json.load(open("companies.json"))
ROLE = re.compile(r"\b(intern|internship|co-?op|new[ -]?grad|graduate program|student|summer analyst|early career)\b", re.I)
SKIP = re.compile(r"\b(senior|staff|principal|manager|director|lead)\b", re.I)
CANADA = re.compile(
    r"canada|toronto|montr[eé]al|vancouver|waterloo|kitchener|ottawa|calgary|edmonton|halifax|winnipeg|"
    r"victoria|quebec|qu[eé]bec|mississauga|burnaby|saskatoon|regina|\b(ON|BC|AB|QC|NS|MB|SK|NB|NL|PE)\b", re.I)

jobs, skipped = [], []
HEAD = {"User-Agent": "campus-talent-jobs-bot (+https://www.joincampustalent.com)"}

def get(url):
    try:
        r = requests.get(url, headers=HEAD, timeout=25)
        return r.json() if r.ok else None
    except Exception:
        return None

def add(company, title, loc, url, source, posted=None):
    loc = loc or ""
    if ROLE.search(title) and not SKIP.search(title) and CANADA.search(loc):
        jobs.append({"company": company, "title": title.strip(), "location": loc.strip(),
                     "url": url, "source": source, "posted": posted})

for c in C.get("greenhouse", []):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{c}/jobs")
    if d is None: skipped.append(["greenhouse", c]); continue
    for j in d.get("jobs", []):
        add(c, j["title"], (j.get("location") or {}).get("name"), j["absolute_url"], "greenhouse", j.get("updated_at"))

for c in C.get("lever", []):
    d = get(f"https://api.lever.co/v0/postings/{c}?mode=json")
    if d is None: skipped.append(["lever", c]); continue
    for j in d:
        cats = j.get("categories") or {}
        locs = ", ".join(cats.get("allLocations") or [cats.get("location") or ""])
        posted = datetime.datetime.utcfromtimestamp(j["createdAt"] / 1000).isoformat() if j.get("createdAt") else None
        add(c, j["text"], locs, j["hostedUrl"], "lever", posted)

for c in C.get("ashby", []):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{c}")
    if d is None: skipped.append(["ashby", c]); continue
    for j in d.get("jobs", []):
        locs = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        add(c, j["title"], ", ".join(x for x in locs if x), j["jobUrl"], "ashby", j.get("publishedAt"))

MULTI = re.compile(r"^\d+ Locations?$", re.I)
for w in C.get("workday", []):
    m = re.match(r"https://([^/]+)/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)", w["url"])
    if not m: skipped.append(["workday", w["name"]]); continue
    host, site = m.groups(); tenant = host.split(".")[0]
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    ok = False
    for q in ["intern", "co-op", "student", "new grad"]:
        for offset in range(0, 200, 20):
            try:
                r = requests.post(api, json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": q},
                                  headers={**HEAD, "Content-Type": "application/json", "Accept": "application/json"}, timeout=25)
                d = r.json() if r.ok else None
            except Exception:
                d = None
            if not d: break
            ok = True
            posts = d.get("jobPostings", [])
            for j in posts:
                loc = j.get("locationsText", "")
                if w.get("canadian") and MULTI.match(loc): loc = loc + " (Canada)"
                add(w["name"], j.get("title", ""), loc, f"https://{host}/{site}{j.get('externalPath', '')}", "workday", j.get("postedOn"))
            if len(posts) < 20: break
    if not ok: skipped.append(["workday", w["name"]])

seen, unique = set(), []
for j in sorted(jobs, key=lambda j: (j["company"].lower(), j["title"])):
    if j["url"] not in seen:
        seen.add(j["url"]); unique.append(j)

now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
json.dump({"updated": now, "count": len(unique), "jobs": unique}, open("jobs.json", "w"), indent=2, ensure_ascii=False)
json.dump(skipped, open("skipped.json", "w"), indent=2)

rows = "\n".join(f"| {j['company']} | [{j['title']}]({j['url']}) | {j['location']} |" for j in unique)
open("README.md", "w").write(f"""# Canadian internships, co-ops and new-grad roles

Pulled automatically from public company job boards by [Campus Talent](https://www.joincampustalent.com). Updated daily.

**{len(unique)} open roles** · last updated {now}

| Company | Role | Location |
|---|---|---|
{rows}

Want the best of these in your inbox every week? [Join the free weekly list](https://www.joincampustalent.com/roles.html).
""")
print(f"{len(unique)} roles, {len(skipped)} boards skipped")
