import re

import httpx

UA = {"User-Agent": "AvsarDootBot/0.1 (eligibility-matching; local-dev)"}


def strip_html(html: str) -> str:
    html = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def main():
    api = "https://www.sarkariresult.com/wp-json/wp/v2/posts?per_page=1"
    post = httpx.get(api, headers=UA, timeout=25).json()[0]
    print("content rendered len", len(post.get("content", {}).get("rendered", "")))
    print(strip_html(post.get("content", {}).get("rendered", ""))[:1500])

    url = "https://www.sarkariresult.com/2026/ssc-junior-engineer-2026/"
    html = httpx.get(url, headers=UA, timeout=25, follow_redirects=True).text
    # extract entry-content
    m = re.search(r'class="[^"]*entry-content[^"]*"([\s\S]{0,20000})</div>', html)
    print("\nSR DETAIL", url, "html", len(html), "entry match", bool(m))
    chunk = m.group(0) if m else html
    text = strip_html(chunk)
    print(text[:2000])
    links = re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]{0,80})', html)
    print("\nLINKS")
    for href, label in links:
        lab = strip_html(label)
        if any(k in lab.lower() for k in ("official", "apply", "notification", "website", "ssc")):
            print(lab, "->", href)

    fja_url = "https://www.freejobalert.com/articles/ssc-je-recruitment-2026-apply-online-for-1748-junior-engineer-posts-3066132"
    # might 404; try from listing
    listing = httpx.get("https://www.freejobalert.com/government-jobs/", headers=UA, timeout=25).text
    arts = re.findall(r'href="(https://www\.freejobalert\.com/articles/[^"]+)"', listing)
    print("\nFJA article count", len(set(arts)), "sample", arts[0] if arts else None)
    if arts:
        fhtml = httpx.get(arts[0], headers=UA, timeout=25, follow_redirects=True).text
        print("FJA detail", arts[0], len(fhtml))
        print(strip_html(fhtml)[400:2200])
        for href, label in re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]{0,80})', fhtml):
            lab = strip_html(label)
            if any(k in lab.lower() for k in ("official", "apply", "notification", "website")):
                print(lab, "->", href)


if __name__ == "__main__":
    main()
