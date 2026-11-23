"""PubMedから精神科の新着論文を集めて data/papers.json に保存する。

GitHub Actions から毎日実行される。標準ライブラリだけで動く。
PubMed の E-utilities（無料の公開API）を使い、論文のタイトル・雑誌・日付などの
書誌情報だけを保存する（抄録は保存せず、PubMed へのリンクで読む）。
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
EMAIL = os.environ.get('NCBI_EMAIL', '')        # 任意：NCBIへの連絡先
DAYS = int(os.environ.get('DAYS', '10'))         # 何日前までの新着を探すか
KEEP_DAYS = 180                                  # 一覧に残す期間
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'papers.json')

# ---- テーマ（タイトル・抄録の語で探す。新着論文はMeSHがまだ付いていないため） ----
TOPICS = {
    'scz': ('統合失調症', 'schizophreni*[tiab] OR psychosis[tiab] OR psychoses[tiab] OR psychotic[tiab] OR antipsychotic*[tiab] OR clozapine[tiab] OR schizoaffective[tiab]'),
    'mood': ('気分障害', '"major depressive"[tiab] OR "depressive disorder"[tiab] OR "treatment-resistant depression"[tiab] OR "bipolar disorder"[tiab] OR "bipolar depression"[tiab] OR mania[tiab] OR antidepressant*[tiab] OR lithium[tiab] OR esketamine[tiab] OR "electroconvulsive"[tiab] OR "postpartum depression"[tiab] OR "perinatal depression"[tiab] OR suicid*[ti]'),
    'dem': ('認知症', 'dementia[tiab] OR alzheimer*[tiab] OR "lewy body"[tiab] OR "mild cognitive impairment"[tiab] OR delirium[tiab] OR frontotemporal[tiab] OR lecanemab[tiab] OR donanemab[tiab] OR "neuropsychiatric symptoms"[tiab]'),
    'dev': ('発達障害', 'ADHD[tiab] OR "attention-deficit"[tiab] OR "attention deficit"[tiab] OR autism[tiab] OR autistic[tiab] OR neurodevelopmental[tiab] OR "tic disorder*"[tiab] OR tourette[tiab] OR "intellectual disability"[tiab] OR "learning disorder*"[tiab]'),
    'oth': ('その他', '"anxiety disorder*"[tiab] OR "panic disorder"[tiab] OR "social anxiety"[tiab] OR "generalized anxiety"[tiab] OR "obsessive-compulsive"[tiab] OR PTSD[tiab] OR posttraumatic[tiab] OR "post-traumatic"[tiab] OR "alcohol use disorder"[tiab] OR "substance use disorder*"[tiab] OR "opioid use disorder"[tiab] OR "eating disorder*"[tiab] OR "anorexia nervosa"[tiab] OR "bulimia nervosa"[tiab] OR "binge eating"[tiab] OR insomnia[tiab] OR "borderline personality"[tiab] OR "somatic symptom"[tiab]'),
}
# 臨床的な研究デザインに絞る（ガイドライン・RCT・メタ解析・系統的レビュー・コホート）
DESIGN = ('randomi*[tiab] OR "meta-analysis"[tiab] OR "meta-analyses"[tiab] OR "systematic review"[tiab] OR "umbrella review"[tiab] '
          'OR guideline*[ti] OR consensus[ti] OR cohort[tiab] OR "target trial"[tiab] OR "clinical trial"[pt] OR "randomized controlled trial"[pt] '
          'OR "meta-analysis"[pt] OR "systematic review"[pt] OR "practice guideline"[pt] OR guideline[pt]')
EXCLUDE = 'protocol[ti] OR "study protocol"[tiab] OR (animals[mh] NOT humans[mh]) OR rat[ti] OR rats[ti] OR mice[ti] OR mouse[ti] OR erratum[pt] OR comment[pt]'
LANG = 'english[la] OR japanese[la]'

MAJOR = {'JAMA Psychiatry', 'Lancet Psychiatry', 'Am J Psychiatry', 'World Psychiatry', 'Mol Psychiatry', 'Biol Psychiatry',
         'Schizophr Bull', 'Br J Psychiatry', 'Psychiatry Clin Neurosci', 'N Engl J Med', 'Lancet', 'JAMA', 'BMJ',
         'Neuropsychopharmacology', 'J Clin Psychiatry', 'Psychol Med', 'Alzheimers Dement', 'JAMA Neurol', 'Lancet Neurol',
         'J Am Acad Child Adolesc Psychiatry', 'JAMA Pediatr', 'Nat Med', 'Lancet Healthy Longev', 'Am J Geriatr Psychiatry',
         'Bipolar Disord', 'Schizophr Res', 'J Affect Disord', 'Addiction', 'Sleep', 'Int J Eat Disord'}


def get(endpoint, **params):
    params.update(db='pubmed', retmode='json', tool='psy-papers')
    if EMAIL: params['email'] = EMAIL
    url = BASE + endpoint + '?' + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                time.sleep(0.4)                  # APIキーなしは毎秒3回まで
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            print('retry', attempt + 1, e, file=sys.stderr); time.sleep(3 * (attempt + 1))
    raise RuntimeError('PubMed に接続できませんでした: ' + endpoint)


def search(term):
    res = get('esearch.fcgi', term=term, datetype='edat', reldate=DAYS, retmax=400, sort='pub_date')
    return res['esearchresult'].get('idlist', [])


def design_of(title, pubtypes):
    t, p = title.lower(), ' '.join(pubtypes).lower()
    if 'guideline' in p or re.search(r'\bguideline|consensus statement|recommendations?\b', t): return 'ガイドライン'
    if 'meta-analysis' in p or 'systematic review' in p or re.search(r'meta-analy|systematic review|umbrella review|network meta', t): return 'メタ解析・SR'
    if 'randomized controlled trial' in p or re.search(r'randomi[sz]ed|randomised|\brct\b', t): return 'RCT'
    if 'clinical trial' in p or re.search(r'\btrial\b', t): return '臨床試験'
    if re.search(r'cohort|registry|nationwide|population-based|target trial|longitudinal', t): return 'コホート'
    return 'その他'


def clean(s):
    s = re.sub(r'<[^>]+>', '', s or '')
    return re.sub(r'\s+', ' ', s).strip()


def summarize(ids):
    out = {}
    for i in range(0, len(ids), 150):
        res = get('esummary.fcgi', id=','.join(ids[i:i + 150]))['result']
        for uid in res.get('uids', []):
            d = res[uid]
            title = clean(d.get('title'))
            if not title: continue
            authors = [a['name'] for a in d.get('authors', []) if a.get('authtype') == 'Author']
            doi = next((x['value'] for x in d.get('articleids', []) if x.get('idtype') == 'doi'), '')
            sort = (d.get('sortpubdate') or '')[:10].replace('/', '-')
            out[uid] = {
                'pmid': uid, 'title': title, 'journal': d.get('fulljournalname', ''), 'source': d.get('source', ''),
                'date': sort, 'pubdate': d.get('epubdate') or d.get('pubdate', ''),
                'authors': (authors[0] + (' ほか' if len(authors) > 1 else '')) if authors else '',
                'doi': doi, 'design': design_of(title, d.get('pubtype', [])),
                'major': d.get('source', '') in MAJOR,
            }
    return out


def main():
    today = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d')
    try:
        old = json.load(open(OUT, encoding='utf-8'))
    except Exception:
        old = {'papers': []}
    papers = {p['pmid']: p for p in old.get('papers', [])}

    found = {}
    for key, (name, q) in TOPICS.items():
        term = f'({q}) AND ({DESIGN}) AND ({LANG}) NOT ({EXCLUDE})'
        ids = search(term)
        jp = set(search(f'({term}) AND japan[ad]'))
        print(f'{name}: {len(ids)}件（日本 {len(jp)}件）')
        for pid in ids:
            f = found.setdefault(pid, {'topics': set(), 'jp': False})
            f['topics'].add(key); f['jp'] = f['jp'] or pid in jp

    new_ids = [pid for pid in found if pid not in papers]
    meta = summarize(new_ids) if new_ids else {}
    for pid, f in found.items():
        if pid in papers:
            p = papers[pid]
            p['topics'] = sorted(set(p['topics']) | f['topics']); p['jp'] = p.get('jp') or f['jp']
        elif pid in meta:
            papers[pid] = dict(meta[pid], topics=sorted(f['topics']), jp=f['jp'], added=today)

    limit = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
    kept = [p for p in papers.values() if p.get('added', today) >= limit]
    kept.sort(key=lambda p: (p.get('added', ''), p.get('date', '')), reverse=True)
    data = {'updated': datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M'),
            'topics': {k: v[0] for k, v in TOPICS.items()}, 'papers': kept}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'新規 {len(meta)}件・合計 {len(kept)}件を保存しました')


if __name__ == '__main__':
    main()
