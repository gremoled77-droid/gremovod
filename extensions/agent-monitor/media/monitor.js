/* All source content is assigned through textContent; Markdown is displayed as plain text. */
(() => {
  const api = acquireVsCodeApi();
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = String(text);
    if (cls) n.className = cls;
    return n;
  };
  let selected;
  const saved = api.getState() || {};
  let restorePending = Object.keys(saved).length > 0;
  const fields = ['agent', 'task', 'pr', 'status', 'from', 'to', 'search'];
  for (const key of ['from', 'to', 'search']) if (saved[key]) $(key).value = saved[key];
  function filters() {
    const state = Object.fromEntries(fields.map(k => [k, $(k).value]));
    api.setState(state);
    const filter = {...state};
    for (const key of ['from', 'to']) if (filter[key]) filter[key] = new Date(filter[key]).toISOString();
    api.postMessage({type: 'filter', filter});
  }
  $('filters').addEventListener('submit', e => e.preventDefault());
  $('filters').addEventListener('input', filters);
  $('filters').addEventListener('reset', () => setTimeout(filters, 0));
  $('refresh').onclick = () => api.postMessage({type: 'refresh'});
  $('more').onclick = () => api.postMessage({type: 'more'});
  $('copy').onclick = () => api.postMessage({type: 'copy', id: selected});
  $('open').onclick = () => api.postMessage({type: 'open', id: selected});
  function pairs(id, rows) {
    $(id).replaceChildren(...rows.flatMap(([key, value]) => [el('dt', key), el('dd', value ?? 'Unknown')]));
  }
  function choose(id) {
    selected = id;
    api.postMessage({type: 'detail', id});
  }
  window.addEventListener('message', ({data: m}) => {
    if (m.type === 'error') {
      $('freshness').textContent = m.message;
      return;
    }
    if (m.type === 'detail') {
      if (selected !== m.id) return;
      $('detail').textContent = m.text;
      $('detail-meta').textContent = m.meta;
      $('copy').disabled = false;
      $('open').disabled = !m.canOpen;
      return;
    }
    if (m.type !== 'snapshot') return;
    $('freshness').textContent =
      `Снимок: ${m.updated} · GitHub: ${m.githubStatus} · Последний успешный запрос: ${m.lastGitHub || 'Unknown'} · Следующий запрос не ранее: ${m.nextGitHub}`;
    $('warnings').replaceChildren(...m.warnings.map(w => el('p', w, 'warning')));
    for (const key of ['agent', 'task', 'pr', 'status']) {
      const control = $(key),
        previous = control.value || saved[key] || '';
      control.replaceChildren(
        new Option('Все', ''),
        ...m.choices[key]
          .sort((a, b) => String(a).localeCompare(String(b)))
          .map(x => new Option(String(x), String(x)))
      );
      if ([...control.options].some(o => o.value === previous)) control.value = previous;
      delete saved[key];
    }
    const p = m.pulls.find(p => String(p.number) === $('pr').value) || m.pulls[0];
    const review = p?.review;
    const metrics = [
      [
        'Конвейер',
        review?.status === 'Changes requested'
          ? 'Waiting · замечания Codex'
          : review?.status === 'Review clear'
            ? 'Waiting for owner'
            : 'Unknown',
      ],
      ['Задача / PR', p ? `${p.task || 'Unknown'} · #${p.number}` : 'Unknown'],
      ['Ветка рабочей папки', m.git.branch],
      ['Последнее событие', m.lastEvent || 'Unknown'],
      ['GitHub', m.githubStatus],
      ['Следующая задача', p?.next || 'Unknown'],
      [
        'Локальный диспетчер',
        m.local.connected ? 'State connected · live activity Unknown' : 'Not connected',
      ],
      [
        'Локальные CLI',
        Object.entries(m.cli)
          .map(([k, v]) => `${k}: ${v}`)
          .join('\n'),
      ],
    ];
    $('overview').replaceChildren(
      ...metrics.map(([name, value]) => {
        const n = el('div', undefined, 'metric');
        n.append(el('small', name), el('strong', value));
        return n;
      })
    );
    pairs('minimax', [
      ['Текущая активность', 'Unknown · нет heartbeat'],
      ['Последняя запись', m.local.lastRun],
      ['Задача', p?.task],
      ['Worktree наблюдения', m.git.worktree],
      ['Worktree агента', 'Unknown · не записана dispatcher v2'],
      ['Раунды исправлений', m.local.rounds[p?.task] ?? 'Unknown'],
      ['Тесты агента', 'Unknown · см. отчёты / GitHub Actions'],
      ['Изменённые файлы', m.git.changed.length ? m.git.changed.join('\n') : 'Нет в наблюдаемой папке'],
      ['Ответ на замечания', 'Unknown · запуск/ответ требует источника'],
    ]);
    pairs('codex', [
      ['GitHub PR', p ? `#${p.number}` : 'Unknown'],
      ['HEAD SHA', p?.sha],
      ['Ревью GitHub', review?.status],
      ['SHA ревью', review?.sha],
      [
        'P0 / P1 / P2 на HEAD',
        review ? `${review.p0} / ${review.p1} / ${review.p2} (зафиксированы, не число открытых)` : 'Unknown',
      ],
      ['Вердикт', review?.status],
      ['Локальный Codex CLI', 'Unknown · отдельный источник отчётов'],
      [
        'Причина ожидания',
        review?.status === 'Changes requested'
          ? 'Есть замечания; выполнение MiniMax не подтверждено'
          : 'Нет подтверждённого следующего действия',
      ],
    ]);
    $('count').textContent =
      `${m.shown} / ${m.count} событий · ${m.observed} ID в журнале · окно истории ${m.retained} / 5000`;
    $('timeline').replaceChildren(
      ...m.events.map(e => {
        const tr = el('tr'),
          time = el('td', new Date(e.timestamp).toLocaleString()),
          agent = el('td', e.agent),
          main = el('td'),
          refs = el('td', e.pr_number ? `#${e.pr_number}` : '—');
        time.append(el('small', e.source));
        agent.append(el('small', e.task_id || 'Task Unknown'));
        const button = el('button', e.summary || e.event_type, 'event');
        button.onclick = () => choose(e.event_id);
        main.append(button, el('small', e.event_type), el('span', `${e.severity} · ${e.status}`, 'badge'));
        refs.append(el('small', e.commit_sha?.slice(0, 12) || 'SHA Unknown'));
        tr.append(time, agent, main, refs);
        return tr;
      })
    );
    if (!m.events.length) {
      const tr = el('tr'),
        td = el('td', 'Событий по выбранным фильтрам нет.');
      td.colSpan = 4;
      tr.append(td);
      $('timeline').append(tr);
    }
    $('more').disabled = m.shown >= m.count;
    if (!selected && m.events.length)
      choose(m.events.find(e => e.event_type === 'finding')?.event_id || m.events[0].event_id);
    if (restorePending) {
      restorePending = false;
      for (const k of Object.keys(saved)) delete saved[k];
      filters();
    }
  });
  api.postMessage({type: 'ready'});
})();
