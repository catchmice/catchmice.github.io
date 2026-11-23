/* CatchMICE language selection and presentation helpers. */
(() => {
  'use strict';

  const preferenceKey = 'cm_language';
  const url = new URL(location.href);
  const valid = value => value === 'ko' || value === 'en';
  let preference;
  try { preference = localStorage.getItem(preferenceKey); } catch {}
  const requested = url.searchParams.get('lang');
  const language = valid(requested) ? requested : valid(preference) ? preference : 'ko';
  const english = language === 'en';
  const { labels = {}, content = {} } = window.CatchMICEEnglish || {};
  const korean = /[가-힣]/;
  const dateFormat = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' });
  const monthFormat = new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric' });
  document.documentElement.lang = language;

  const exact = value => Object.hasOwn(labels, value) ? labels[value] : value;

  function experience(value) {
    return value
      .replace(/신입인턴/g, 'Entry-level internship')
      .replace(/경력무관\(경력우대\)/g, 'Any experience (experienced applicants preferred)')
      .replace(/경력무관\(신입포함\)/g, 'Any experience, including entry level')
      .replace(/경력무관|경력\(연수무관\)|경력\(년수무관\)/g, 'Any experience')
      .replace(/경력\s*(\d+)~(\d+)년/g, 'Experience: $1–$2 years')
      .replace(/경력\s*(\d+)년↑/g, 'Experience: $1+ years')
      .replace(/경력\s*(\d+)년↓/g, 'Experience: up to $1 years')
      .replace(/경력/g, 'Experienced')
      .replace(/신입/g, 'Entry level')
      .replace(/파견직\s*(\d+)년/g, '$1-year dispatched assignment')
      .replace(/영어능통 필요|영어 커뮤니케이션 필수/g, 'English proficiency required')
      .replace(/TOEIC (\d+)↑/g, 'TOEIC $1+')
      .replace(/정규직/g, 'Permanent')
      .replace(/계약직/g, 'Contract')
      .replace(/기간제/g, 'Fixed term')
      .replace(/프리랜서/g, 'Freelance')
      .replace(/인턴/g, 'Internship')
      .replace(/전환\s*가능/g, 'potential conversion');
  }

  function field(dataset, item, key) {
    const source = item[key];
    if (!english || typeof source !== 'string') return source;
    const authored = item[key + '_en'];
    if (typeof authored === 'string' && authored.trim()) return authored;
    const titles = content[dataset];
    const entry = titles && Object.hasOwn(titles, item.title) ? titles[item.title] : undefined;
    const translation = entry?.[key];
    if (key === 'title' && translation) return translation;
    if (translation && Object.hasOwn(translation, source)) return translation[source];
    return key === 'career' ? experience(source) : exact(source);
  }

  function searchFields(dataset, item, keys) {
    return keys.flatMap(key => english ? [item[key], field(dataset, item, key)] : [item[key]]);
  }

  const patterns = [
    [/^(\d+)년 (\d+)월$/, (_, y, m) => monthFormat.format(new Date(+y, m - 1))],
    [/^오늘 열리고 있는 행사가 (\d+)개 있어요!$/, (_, n) => `Events in progress today: ${n}`],
    [/^오늘의 AI 용어 · (\d+)월 (\d+)일$/, (_, m, d) => `AI Term of the Day · ${dateFormat.format(new Date(2024, m - 1, +d))}`],
    [/^모집 중인 공고 (\d+)개$/, (_, n) => `Open jobs: ${n}`],
    [/^(\d+\. )(.+)$/, (_, number, item) => number + exact(item)],
    [/^(.+)에서 열리는 행사$/, (_, venue) => `Events at ${exact(venue)}`],
    [/^관련 페이지 열기 \((.+)\) ↗$/, (_, source) => `Visit source (${exact(source)}) ↗`],
    [/^데이터 (Updated .+)$/, (_, date) => date],
    [/^최근 (Updated .+)$/, (_, date) => date],
    [/^(\d+)개 완료$/, (_, n) => `${n} complete`],
    [/^내 준비 진행률 (\d+)%$/, (_, n) => `My progress: ${n}%`],
    [/^내 조건\((.+)\)에 맞는 공고$/, (_, tags) => `Jobs matching my preferences (${localize(tags)})`],
    [/^(?:· )?전체 (\d+)개$/, (_, n) => `· ${n} total`],
    [/^— 가장 급한 건 (.+) \((.+)\)$/, (_, company, date) => `— ${exact(company)} (${localize(date)})`],
    [/^· 가장 최근 (.+)$/, (_, date) => `· Latest: ${date}`],
    [/^헤드라인:\s*(.+)$/, (_, titles) => `Headlines: ${titles}`],
    [/^분류는 (.+) 순이에요\.$/, (_, categories) => `Top categories: ${localize(categories)}`],
    [/^지역은 (.+) 순이에요\.$/, (_, regions) => `Top regions: ${localize(regions)}`],
    [/^마감 (\d+)일 이내$/, (_, days) => `Closing within ${days} days`],
    [/^준비 8단계 중 (\d+)개 완료 \((\d+)%\)$/, (_, n, percent) => `${n} of 8 steps complete (${percent}%)`],
    [/^채용 탭에서 (\d+)개 모두 보기$/, (_, n) => `See all ${n} in Careers`],
    [/^(?:(.+) )?(공고|행사|논문) (\d+)(?:개|편)를 찾았어요$/, (_, tags, kind, count) =>
      `Found ${count} ${exact(kind).toLowerCase()}${tags ? ' · ' + localize(tags) : ''}`],
    [/^(?:(.+) )?기사 (\d+)건을 골랐어요(?: \(전체 (\d+)건\))?$/, (_, tags, count, total) =>
      `Showing ${count} articles${total ? ' of ' + total : ''}${tags ? ' · ' + localize(tags) : ''}`],
    [/^조건: (.+?)(?: · 다른 조건으로 다시 물어봐 주세요\.)?$/, (_, tags) => `Filters: ${localize(tags)}`],
    [/^"(.+)" 검색$/, (_, query) => `Search: “${query}”`],
    [/^"(.+)" 단계를 함께 볼게요\.$/, (_, step) => `Review this step: ${exact(step)}.`],
    [/^다음 할 일은 "(.+)"이에요\.$/, (_, step) => `Next step: ${exact(step)}.`],
    [/^오늘의 AI 용어 · (.+) \((.+)\)$/, (_, title, term) => `AI term of the day · ${term}`],
    [/^([^·]+) \(([^()]+)\)$/, (original, label, detail) => {
      const translated = exact(label);
      if (translated === label) return original;
      return translated === detail ? detail : `${translated} (${detail})`;
    }],
    [/^(\d+)개 용어$/, (_, n) => `${n} terms`],
    [/^(\d+)개$/, (_, n) => n],
    [/^(\d+)건$/, (_, n) => n],
    [/^(\d+)편$/, (_, n) => n],
    [/^\+(\d+)개$/, (_, n) => `+${n} more`],
    [/^(\d+\/\d+) 완료$/, (_, n) => `${n} complete`],
    [/^(\d+)% 완료$/, (_, n) => `${n}% complete`],
    [/^지원함 (\d+)개$/, (_, n) => `Applications: ${n}`],
    [/^(D-\d+) 마감$/, (_, d) => `Closes ${d}`],
    [/^지원함 · (.+)$/, (_, date) => `Applied · ${date}`],
    [/^새 (뉴스|공고|행사) (\d+)개$/, (_, type, n) => `New ${exact(type).toLowerCase()}: ${n}`],
    [/^사전등록 마감 (.+)$/, (_, date) => `Registration closes ${date}`],
    [/^(.+?) 주변 핫플$/, (_, venue) => `Places near ${exact(venue)}`],
    [/^(.+) 맛집 찾기$/, (_, venue) => `Restaurants near ${exact(venue)}`],
    [/^(.+) 카페 찾기$/, (_, venue) => `Cafés near ${exact(venue)}`],
    [/^(.+)에서 찾아보기 ↗$/, (_, site) => `Search on ${exact(site)} ↗`],
    [/^(.+)에서 공고 보기 ↗$/, (_, site) => `View listing on ${exact(site)} ↗`],
    [/^(.+)에서 보기 ↗$/, (_, site) => `View on ${exact(site)} ↗`],
    [/^(저장 취소|저장): (.+)$/, (_, action, title) => `${exact(action)}: ${title}`],
    [/^(.+)을\(를\) 불러오는 중이에요\.$/, (_, type) => `Loading ${exact(type).toLowerCase()}…`],
    [/^(.+)을\(를\) 불러오지 못했어요\. 잠시 후 새로고침해 주세요\.$/, (_, type) => `Couldn’t load ${exact(type).toLowerCase()}. Try refreshing.`],
    [/^'(.+)'에 맞는 결과가 없어요\. 다른 단어로 찾아보세요\.$/, (_, query) => `No results for “${query}”. Try another search term.`],
    [/^(\d+)월 (\d+)일 (?:행사 (\d+)개|행사 없음)$/, (_, m, d, n) => `${dateFormat.format(new Date(2024, m - 1, +d))} · ${n ? n + ' events' : 'No events'}`],
    [/^(\d+)월 행사 (\d+)개$/, (_, m, n) => `${new Intl.DateTimeFormat('en',{month:'long'}).format(new Date(2024,m-1))} · ${n} events`],
    [/^(.+?)\(([^()]+)\) 행사 (\d+)개$/, (_, period, dates, n) => `${exact(period)} (${dates}) · ${n} events`],
    [/^(.+) · (\d+)개 행사 · 날짜를 다시 누르면 전체 보기$/, (_, dates, n) => `${dates} · ${n} events · Select the date again to clear it`],
    [/^([^·]+) (\d+)(개|편)?$/, (original, label, count) => {
      const translated = exact(label);
      return translated === label ? original : `${translated} (${count})`;
    }]
  ];

  function localize(value) {
    if (!english || typeof value !== 'string' || !korean.test(value)) return value;
    const translated = exact(value);
    if (translated !== value) return translated;
    for (const [pattern, translate] of patterns) {
      const match = value.match(pattern);
      if (match) return translate(...match);
    }
    if (value.includes(' · ')) return value.split(' · ').map(localize).join(' · ');
    if (value.startsWith('· ')) return '· ' + localize(value.slice(2));
    if (value.startsWith('— ')) return '— ' + localize(value.slice(2));
    if (value.endsWith(' ↗')) return localize(value.slice(0, -2)) + ' ↗';
    return value;
  }

  function translateNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const original = node.data;
      const trimmed = original.trim();
      const translated = localize(trimmed);
      if (translated !== trimmed) node.data = original.replace(trimmed, () => translated);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE || node.matches('script, style, code, [data-no-translate]')) return;
    for (const attr of ['aria-label', 'placeholder', 'alt', 'title']) {
      const original = node.getAttribute(attr);
      const translated = localize(original);
      if (translated !== original) node.setAttribute(attr, translated);
    }
    for (const child of node.childNodes) translateNode(child);
  }

  function install() {
    const controls = document.querySelectorAll('.cm-lang');
    for (const group of controls) {
      group.setAttribute('aria-label', english ? 'Site language' : '사이트 언어');
      for (const button of group.querySelectorAll('button')) {
        const chosen = button.dataset.language;
        button.setAttribute('aria-pressed', String(language === chosen));
        button.addEventListener('click', () => {
          try { localStorage.setItem(preferenceKey, chosen); } catch {}
          if (chosen === language) return;
          const next = new URL(location.href);
          next.searchParams.set('lang', chosen);
          location.assign(next);
        });
      }
    }
    if (!english) return;
    document.title = 'CatchMICE | Korea MICE News, Events & Careers';
    document.querySelector('meta[name="description"]').content =
      'Explore exhibitions, conventions, MICE news, jobs and research in Korea.';
    const crewTitle = document.querySelector('.crew-hero h2');
    if (crewTitle) crewTitle.textContent = 'Meet the CatchMICE Crew';
    const note = document.querySelector('#cm-language-note');
    if (note) note.hidden = false;
    translateNode(document.body);
    new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'characterData') {
          if (!record.target.parentElement?.closest('script, style, code, [data-no-translate]')) {
            translateNode(record.target);
          }
        } else if (!record.target.closest?.('script, style, code, [data-no-translate]')) {
          for (const node of record.addedNodes) translateNode(node);
        }
      }
    }).observe(document.body, { childList: true, characterData: true, subtree: true });
  }

  window.CatchMICELanguage = {
    english, field, localize, searchFields,
    formatDate: date => dateFormat.format(date)
  };
  document.addEventListener('DOMContentLoaded', install, { once: true });
})();
