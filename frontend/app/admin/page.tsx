'use client';

import { useEffect, useState } from 'react';
import {
  createAdminSource,
  deleteAdminSource,
  getAdminOverview,
  getAdminSettings,
  getAdminSources,
  runAdminDoubanBackfill,
  runAdminIncremental,
  runAdminSourceDiscovery,
  runAdminSource,
  updateAdminSettings,
  updateAdminSource,
  getCollectSources,
  createCollectSource,
  updateCollectSource,
  deleteCollectSource,
  testCollectSource,
  runCollectSource,
  getCollectTasks,
  getCollectTimingTasks,
  updateCollectTimingTask,
  runCollectTimingTask,
  getCollectBindings,
  saveCollectBindings,
} from '@/lib/api';
import { AdminOverview, AdminSettings, CollectSource, CollectTask, CollectTimingTask, CollectTypeBinding, CrawlSource } from '@/lib/types';

const API_KEY_STORAGE = 'acg:admin:api-key';

const defaultSettings: AdminSettings = {
  _id: 'admin',
  auto_incremental_enabled: false,
  incremental_interval_minutes: 60,
  incremental_limit: 20,
  incremental_min_hours: 6,
  auto_discover_enabled: false,
  auto_source_discovery_enabled: false,
  source_discovery_interval_minutes: 180,
  crawler_proxy_url: '',
  douban_backfill_enabled: false,
  douban_backfill_interval_minutes: 60,
  douban_backfill_limit: 50,
  douban_search_url: 'https://s.stdlang.com/search',
  douban_backfill_timeout_seconds: 20,
};

export default function AdminPage() {
  const [apiKey, setApiKey] = useState('');
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [settings, setSettings] = useState<AdminSettings>(defaultSettings);
  const [sources, setSources] = useState<CrawlSource[]>([]);
  const [message, setMessage] = useState('');
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: '',
    domain: '',
    seed_url: '',
    homepage_url: '',
    category_pages: '',
    recent_pages: '',
    search_url_template: '',
    search_title_limit: 50,
    search_pagination_max_pages: 200,
    max_depth: 3,
    discovery_max_depth: 1,
    enabled: true,
    notes: '',
  });
  const [editForm, setEditForm] = useState({
    name: '',
    domain: '',
    seed_url: '',
    homepage_url: '',
    category_pages: '',
    recent_pages: '',
    search_url_template: '',
    search_title_limit: 50,
    search_pagination_max_pages: 200,
    max_depth: 3,
    discovery_max_depth: 1,
    enabled: true,
    notes: '',
  });

  useEffect(() => {
    const stored = window.localStorage.getItem(API_KEY_STORAGE) || '';
    if (stored) {
      setApiKey(stored);
      void loadAll(stored);
    }
  }, []);

  async function loadAll(key: string) {
    setLoading(true);
    setError('');
    try {
      const [overviewData, settingsData, sourcesData] = await Promise.all([
        getAdminOverview(key),
        getAdminSettings(key),
        getAdminSources(key),
      ]);
      setOverview(overviewData);
      setSettings(settingsData);
      setSources(sourcesData.data);
      setConnected(true);
      window.localStorage.setItem(API_KEY_STORAGE, key);
    } catch (err) {
      setConnected(false);
      setOverview(null);
      setSources([]);
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveSettings() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const updated = await updateAdminSettings(apiKey, {
        auto_incremental_enabled: settings.auto_incremental_enabled,
        incremental_interval_minutes: Number(settings.incremental_interval_minutes),
        incremental_limit: Number(settings.incremental_limit),
        incremental_min_hours: Number(settings.incremental_min_hours),
        auto_discover_enabled: settings.auto_discover_enabled,
        auto_source_discovery_enabled: settings.auto_source_discovery_enabled,
        source_discovery_interval_minutes: Number(settings.source_discovery_interval_minutes),
        crawler_proxy_url: settings.crawler_proxy_url || '',
        douban_backfill_enabled: settings.douban_backfill_enabled,
        douban_backfill_interval_minutes: Number(settings.douban_backfill_interval_minutes),
        douban_backfill_limit: Number(settings.douban_backfill_limit),
        douban_search_url: settings.douban_search_url || 'https://s.stdlang.com/search',
        douban_backfill_timeout_seconds: Number(settings.douban_backfill_timeout_seconds),
      });
      setSettings(updated);
      setMessage('调度设置已保存');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateSource() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      await createAdminSource(apiKey, {
        name: form.name,
        domain: form.domain,
        seed_url: form.seed_url,
        homepage_url: form.homepage_url,
        category_pages: splitLines(form.category_pages),
        recent_pages: splitLines(form.recent_pages),
        search_url_template: form.search_url_template,
        search_title_limit: Number(form.search_title_limit),
        search_pagination_max_pages: Number(form.search_pagination_max_pages),
        max_depth: Number(form.max_depth),
        discovery_max_depth: Number(form.discovery_max_depth),
        enabled: form.enabled,
        notes: form.notes,
      });
      setForm({
        name: '',
        domain: '',
        seed_url: '',
        homepage_url: '',
        category_pages: '',
        recent_pages: '',
        search_url_template: '',
        search_title_limit: 50,
        search_pagination_max_pages: 200,
        max_depth: 3,
        discovery_max_depth: 1,
        enabled: true,
        notes: '',
      });
      setMessage('自定义爬虫源已添加');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败');
    } finally {
      setLoading(false);
    }
  }

  async function toggleSource(source: CrawlSource) {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      await updateAdminSource(apiKey, source._id, { enabled: !source.enabled });
      setMessage(`已${source.enabled ? '停用' : '启用'} ${source.name}`);
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新失败');
    } finally {
      setLoading(false);
    }
  }

  function beginEditSource(source: CrawlSource) {
    setEditingSourceId(source._id);
    setEditForm({
      name: source.name || '',
      domain: source.domain || '',
      seed_url: source.seed_url || '',
      homepage_url: source.homepage_url || '',
      category_pages: (source.category_pages || []).join('\n'),
      recent_pages: (source.recent_pages || []).join('\n'),
      search_url_template: source.search_url_template || '',
      search_title_limit: source.search_title_limit ?? 50,
      search_pagination_max_pages: source.search_pagination_max_pages ?? 200,
      max_depth: source.max_depth ?? 3,
      discovery_max_depth: source.discovery_max_depth ?? 1,
      enabled: source.enabled,
      notes: source.notes || '',
    });
  }

  function cancelEditSource() {
    setEditingSourceId(null);
  }

  async function handleSaveSource(sourceId: string) {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      await updateAdminSource(apiKey, sourceId, {
        name: editForm.name,
        domain: editForm.domain,
        seed_url: editForm.seed_url,
        homepage_url: editForm.homepage_url,
        category_pages: splitLines(editForm.category_pages),
        recent_pages: splitLines(editForm.recent_pages),
        search_url_template: editForm.search_url_template,
        search_title_limit: Number(editForm.search_title_limit),
        search_pagination_max_pages: Number(editForm.search_pagination_max_pages),
        max_depth: Number(editForm.max_depth),
        discovery_max_depth: Number(editForm.discovery_max_depth),
        enabled: editForm.enabled,
        notes: editForm.notes,
      });
      setEditingSourceId(null);
      setMessage('爬虫源已保存');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存爬虫源失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteSource(source: CrawlSource) {
    const confirmed = window.confirm(`确认删除爬虫源「${source.name}」吗？`);
    if (!confirmed) {
      return;
    }

    setLoading(true);
    setMessage('');
    setError('');
    try {
      await deleteAdminSource(apiKey, source._id);
      if (editingSourceId === source._id) {
        setEditingSourceId(null);
      }
      setMessage(`已删除 ${source.name}`);
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunSource(sourceId: string) {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      await runAdminSource(apiKey, sourceId);
      setMessage('已触发单站抓取');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '触发失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunIncremental() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const result = await runAdminIncremental(apiKey);
      setMessage(result.started ? `增量任务状态：${result.status}` : result.reason || '未启动');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '增量任务失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunSourceDiscovery() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const result = await runAdminSourceDiscovery(apiKey);
      setMessage(result.started ? '站点级发现任务已转入后台执行' : result.reason || '未启动');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '站点发现任务失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunDoubanBackfill() {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const result = await runAdminDoubanBackfill(apiKey);
      setMessage(result.started ? `豆瓣补齐任务已启动：${result.status || 'running'}` : result.reason || '未启动');
      await loadAll(apiKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : '豆瓣补齐任务失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-grain px-4 py-8 md:px-8 xl:px-10">
      <div className="mx-auto max-w-[1600px]">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mb-3 inline-flex rounded-full border border-ember/30 bg-ember/10 px-4 py-2 text-xs uppercase tracking-[0.28em] text-parchment/80">
              Admin Console
            </div>
            <h1 className="text-4xl font-semibold text-parchment">视频机器人管理台</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-parchment/70">
              配置自动增量巡检、自定义爬虫站点，并手动触发单站抓取。
            </p>
          </div>
        </div>

        <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_160px]">
            <label className="block">
              <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">Admin API Key</div>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="输入服务端 ADMIN_API_KEY"
                className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition placeholder:text-ash focus:border-ember/60"
              />
            </label>
            <button
              type="button"
              onClick={() => loadAll(apiKey)}
              disabled={!apiKey || loading}
              className="rounded-2xl bg-ember px-4 py-3 text-sm font-semibold text-black transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {connected ? '重新连接' : '连接后台'}
            </button>
          </div>
          {message ? <p className="mt-4 text-sm text-emerald-300">{message}</p> : null}
          {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
        </section>

        {connected ? (
          <div className="mt-8 grid gap-8">
            <section className="grid gap-4 md:grid-cols-3">
              <Card label="手动爬虫源">{overview?.source_count ?? 0}</Card>
              <Card label="启用中的源">{overview?.enabled_source_count ?? 0}</Card>
              <Card label="上次增量状态">{overview?.settings.last_incremental_status || 'idle'}</Card>
            </section>

            <section className="grid gap-4 md:grid-cols-2">
              <Card label="上次站点发现状态">{overview?.settings.last_source_discovery_status || 'idle'}</Card>
              <Card label="站点发现周期">{settings.source_discovery_interval_minutes} 分钟</Card>
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-semibold text-parchment">自动调度设置</h2>
                  <p className="mt-2 text-sm text-parchment/70">动画级增量巡检与站点级发现任务分开调度，站点级发现会在后台异步执行。</p>
                </div>
                <button
                  type="button"
                  onClick={handleRunIncremental}
                  disabled={loading}
                  className="rounded-full border border-ember/40 bg-ember/15 px-4 py-2 text-sm text-parchment transition hover:bg-ember/25"
                >
                  立即执行增量巡检
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <ToggleField
                  label="启用自动增量"
                  checked={settings.auto_incremental_enabled}
                  onChange={(value) => setSettings((current) => ({ ...current, auto_incremental_enabled: value }))}
                />
                <NumberField
                  label="巡检间隔(分钟)"
                  value={settings.incremental_interval_minutes}
                  onChange={(value) => setSettings((current) => ({ ...current, incremental_interval_minutes: value }))}
                />
                <NumberField
                  label="每轮数量"
                  value={settings.incremental_limit}
                  onChange={(value) => setSettings((current) => ({ ...current, incremental_limit: value }))}
                />
                <NumberField
                  label="最小间隔(小时)"
                  value={settings.incremental_min_hours}
                  onChange={(value) => setSettings((current) => ({ ...current, incremental_min_hours: value }))}
                />
              </div>

              <div className="mt-4">
                <ToggleField
                  label="自动 discover 预留开关"
                  checked={settings.auto_discover_enabled}
                  onChange={(value) => setSettings((current) => ({ ...current, auto_discover_enabled: value }))}
                />
              </div>

              <button
                type="button"
                onClick={handleSaveSettings}
                disabled={loading}
                className="mt-5 rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110"
              >
                保存增量巡检设置
              </button>

              {overview?.settings.last_incremental_output ? (
                <pre className="scrollbar-thin mt-5 max-w-full overflow-auto whitespace-pre-wrap break-all rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-parchment/75">
                  {overview.settings.last_incremental_output}
                </pre>
              ) : null}
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-semibold text-parchment">站点级增量发现</h2>
                  <p className="mt-2 text-sm text-parchment/70">只回访手动源配置的入口页，浅抓取发现新动画，不深度全站扩散。</p>
                </div>
                <button
                  type="button"
                  onClick={handleRunSourceDiscovery}
                  disabled={loading}
                  className="rounded-full border border-ember/40 bg-ember/15 px-4 py-2 text-sm text-parchment transition hover:bg-ember/25"
                >
                  立即执行站点发现
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <ToggleField
                  label="启用站点级增量发现"
                  checked={settings.auto_source_discovery_enabled}
                  onChange={(value) => setSettings((current) => ({ ...current, auto_source_discovery_enabled: value }))}
                />
                <NumberField
                  label="发现周期(分钟)"
                  value={settings.source_discovery_interval_minutes}
                  onChange={(value) => setSettings((current) => ({ ...current, source_discovery_interval_minutes: value }))}
                />
                <TextField
                  label="爬虫代理 URL"
                  value={settings.crawler_proxy_url || ''}
                  onChange={(value) => setSettings((current) => ({ ...current, crawler_proxy_url: value }))}
                />
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleSaveSettings}
                  disabled={loading}
                  className="rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110"
                >
                  保存站点发现设置
                </button>
                <div className="flex items-center text-sm text-parchment/60">
                  这里的开关和周期修改后，需要单独保存才会生效。
                </div>
              </div>

              {overview?.settings.last_source_discovery_output ? (
                <pre className="scrollbar-thin mt-5 max-w-full overflow-auto whitespace-pre-wrap break-all rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-parchment/75">
                  {overview.settings.last_source_discovery_output}
                </pre>
              ) : null}
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-semibold text-parchment">豆瓣补齐任务</h2>
                  <p className="mt-2 text-sm text-parchment/70">扫描 `poster_local` 为空的数据，通过 SearXNG 搜索豆瓣 subject 页，补齐年份、导演、简介与海报。</p>
                </div>
                <button
                  type="button"
                  onClick={handleRunDoubanBackfill}
                  disabled={loading}
                  className="rounded-full border border-ember/40 bg-ember/15 px-4 py-2 text-sm text-parchment transition hover:bg-ember/25"
                >
                  立即执行豆瓣补齐
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <ToggleField
                  label="启用豆瓣补齐"
                  checked={!!settings.douban_backfill_enabled}
                  onChange={(value) => setSettings((current) => ({ ...current, douban_backfill_enabled: value }))}
                />
                <NumberField
                  label="补齐周期(分钟)"
                  value={settings.douban_backfill_interval_minutes || 60}
                  onChange={(value) => setSettings((current) => ({ ...current, douban_backfill_interval_minutes: value }))}
                />
                <NumberField
                  label="每轮补齐数量"
                  value={settings.douban_backfill_limit || 50}
                  onChange={(value) => setSettings((current) => ({ ...current, douban_backfill_limit: value }))}
                />
                <TextField
                  label="SearXNG 搜索地址"
                  value={settings.douban_search_url || 'https://s.stdlang.com/search'}
                  onChange={(value) => setSettings((current) => ({ ...current, douban_search_url: value }))}
                />
                <NumberField
                  label="豆瓣解析超时(秒)"
                  value={settings.douban_backfill_timeout_seconds || 20}
                  onChange={(value) => setSettings((current) => ({ ...current, douban_backfill_timeout_seconds: value }))}
                />
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleSaveSettings}
                  disabled={loading}
                  className="rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110"
                >
                  保存豆瓣补齐设置
                </button>
                <div className="flex items-center text-sm text-parchment/60">
                  subject 页会走代理，海报下载直连，不走代理。
                </div>
              </div>

              {overview?.settings.last_douban_backfill_output ? (
                <pre className="scrollbar-thin mt-5 max-w-full overflow-auto whitespace-pre-wrap break-all rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-parchment/75">
                  {overview.settings.last_douban_backfill_output}
                </pre>
              ) : null}
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <h2 className="text-2xl font-semibold text-parchment">新增自定义爬虫源</h2>
              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <TextField label="名称" value={form.name} onChange={(value) => setForm((current) => ({ ...current, name: value }))} />
                <TextField label="域名" value={form.domain} onChange={(value) => setForm((current) => ({ ...current, domain: value }))} />
                <TextField label="seed_url" value={form.seed_url} onChange={(value) => setForm((current) => ({ ...current, seed_url: value }))} />
                <TextField label="首页 URL" value={form.homepage_url} onChange={(value) => setForm((current) => ({ ...current, homepage_url: value }))} />
                <TextField label="搜索页模板" value={form.search_url_template} onChange={(value) => setForm((current) => ({ ...current, search_url_template: value }))} />
                <NumberField label="搜索标题数" value={form.search_title_limit} onChange={(value) => setForm((current) => ({ ...current, search_title_limit: value }))} />
                <NumberField label="搜索分页上限" value={form.search_pagination_max_pages} onChange={(value) => setForm((current) => ({ ...current, search_pagination_max_pages: value }))} />
                <TextAreaField label="分类页列表(每行一个)" value={form.category_pages} onChange={(value) => setForm((current) => ({ ...current, category_pages: value }))} />
                <TextAreaField label="最近更新页列表(每行一个)" value={form.recent_pages} onChange={(value) => setForm((current) => ({ ...current, recent_pages: value }))} />
                <NumberField label="最大深度" value={form.max_depth} onChange={(value) => setForm((current) => ({ ...current, max_depth: value }))} />
                <NumberField label="发现任务深度" value={form.discovery_max_depth} onChange={(value) => setForm((current) => ({ ...current, discovery_max_depth: value }))} />
                <TextField label="备注" value={form.notes} onChange={(value) => setForm((current) => ({ ...current, notes: value }))} />
                <ToggleField label="创建后启用" checked={form.enabled} onChange={(value) => setForm((current) => ({ ...current, enabled: value }))} />
              </div>
              <button
                type="button"
                onClick={handleCreateSource}
                disabled={loading || !form.name || (!form.domain && !form.seed_url)}
                className="mt-5 rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                添加爬虫源
              </button>
            </section>

            <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
              <h2 className="text-2xl font-semibold text-parchment">手动爬虫源列表</h2>
              <div className="mt-5 grid gap-4">
                {sources.map((source) => (
                  <div key={source._id} className="rounded-[24px] border border-white/10 bg-black/20 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="text-lg font-semibold text-parchment">{source.name}</div>
                        <div className="mt-2 text-sm text-parchment/70">
                          {source.seed_url || source.domain || '未配置入口'}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-ash">
                          <span>max_depth={source.max_depth}</span>
                          <span>discovery_depth={source.discovery_max_depth ?? 1}</span>
                          <span>{source.enabled ? 'enabled' : 'disabled'}</span>
                          <span>{source.last_run_status || 'never-run'}</span>
                          <span>{source.last_discovery_status || 'never-discovery'}</span>
                        </div>
                        {source.last_run_at ? <div className="mt-2 text-xs text-parchment/55">上次抓取: {source.last_run_at}</div> : null}
                        {source.last_discovery_at ? <div className="mt-1 text-xs text-parchment/55">上次发现: {source.last_discovery_at}</div> : null}
                        {source.homepage_url ? <div className="mt-2 text-xs text-parchment/55">首页: {source.homepage_url}</div> : null}
                        {source.search_url_template ? (
                          <div className="mt-1 max-w-full break-all text-xs text-parchment/55">
                            搜索页: {source.search_url_template}，每轮 {source.search_title_limit ?? 50} 个标题，分页上限 {source.search_pagination_max_pages ?? 200}
                          </div>
                        ) : null}
                        {!!source.category_pages?.length ? <div className="mt-1 text-xs text-parchment/55">分类页: {source.category_pages.length} 个</div> : null}
                        {!!source.recent_pages?.length ? <div className="mt-1 text-xs text-parchment/55">最近更新页: {source.recent_pages.length} 个</div> : null}
                        {source.notes ? <div className="mt-2 text-sm text-parchment/60">{source.notes}</div> : null}
                        {source.last_run_output ? (
                          <pre className="scrollbar-thin mt-3 max-w-full overflow-auto whitespace-pre-wrap break-all rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-parchment/75">
                            {source.last_run_output}
                          </pre>
                        ) : null}
                        {source.last_discovery_output ? (
                          <pre className="scrollbar-thin mt-3 max-w-full overflow-auto whitespace-pre-wrap break-all rounded-2xl border border-ember/20 bg-black/30 p-4 text-xs leading-6 text-parchment/75">
                            {source.last_discovery_output}
                          </pre>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={() => beginEditSource(source)}
                          className="rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment"
                        >
                          编辑
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleSource(source)}
                          className="rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment"
                        >
                          {source.enabled ? '停用' : '启用'}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRunSource(source._id)}
                          className="rounded-full bg-ember px-4 py-2 text-sm font-semibold text-black transition hover:brightness-110"
                        >
                          立即抓取
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteSource(source)}
                          className="rounded-full border border-rose-400/30 bg-rose-400/10 px-4 py-2 text-sm text-rose-200 transition hover:bg-rose-400/20"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                    {editingSourceId === source._id ? (
                      <div className="mt-5 rounded-[24px] border border-ember/20 bg-black/20 p-4">
                        <div className="mb-4 text-sm font-medium text-parchment">编辑爬虫源</div>
                        <div className="grid gap-4 lg:grid-cols-2">
                          <TextField label="名称" value={editForm.name} onChange={(value) => setEditForm((current) => ({ ...current, name: value }))} />
                          <TextField label="域名" value={editForm.domain} onChange={(value) => setEditForm((current) => ({ ...current, domain: value }))} />
                          <TextField label="seed_url" value={editForm.seed_url} onChange={(value) => setEditForm((current) => ({ ...current, seed_url: value }))} />
                          <TextField label="首页 URL" value={editForm.homepage_url} onChange={(value) => setEditForm((current) => ({ ...current, homepage_url: value }))} />
                          <TextField label="搜索页模板" value={editForm.search_url_template} onChange={(value) => setEditForm((current) => ({ ...current, search_url_template: value }))} />
                          <NumberField label="搜索标题数" value={editForm.search_title_limit} onChange={(value) => setEditForm((current) => ({ ...current, search_title_limit: value }))} />
                          <NumberField label="搜索分页上限" value={editForm.search_pagination_max_pages} onChange={(value) => setEditForm((current) => ({ ...current, search_pagination_max_pages: value }))} />
                          <TextAreaField label="分类页列表(每行一个)" value={editForm.category_pages} onChange={(value) => setEditForm((current) => ({ ...current, category_pages: value }))} />
                          <TextAreaField label="最近更新页列表(每行一个)" value={editForm.recent_pages} onChange={(value) => setEditForm((current) => ({ ...current, recent_pages: value }))} />
                          <NumberField label="最大深度" value={editForm.max_depth} onChange={(value) => setEditForm((current) => ({ ...current, max_depth: value }))} />
                          <NumberField label="发现任务深度" value={editForm.discovery_max_depth} onChange={(value) => setEditForm((current) => ({ ...current, discovery_max_depth: value }))} />
                          <TextField label="备注" value={editForm.notes} onChange={(value) => setEditForm((current) => ({ ...current, notes: value }))} />
                          <ToggleField label="启用" checked={editForm.enabled} onChange={(value) => setEditForm((current) => ({ ...current, enabled: value }))} />
                        </div>
                        <div className="mt-5 flex flex-wrap gap-3">
                          <button
                            type="button"
                            onClick={() => handleSaveSource(source._id)}
                            disabled={loading || !editForm.name || (!editForm.domain && !editForm.seed_url)}
                            className="rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            保存修改
                          </button>
                          <button
                            type="button"
                            onClick={cancelEditSource}
                            disabled={loading}
                            className="rounded-2xl border border-white/10 bg-white/[0.05] px-5 py-3 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ))}
                {!sources.length ? <div className="text-sm text-ash">暂无自定义爬虫源。</div> : null}
              </div>
            </section>

            {/* -------- 采集源管理 (JSON/XML 资源站) -------- */}
            <CollectSourcesSection apiKey={apiKey} loading={loading} setLoading={setLoading} setError={setError} setMessage={setMessage} />
          </div>
        ) : null}
      </div>
    </main>
  );
}

// -------- 采集源管理组件 --------

const COLLECT_RANGE_OPTIONS = [
  { key: 'today', label: '今日更新' },
  { key: '2day', label: '2日内更新' },
  { key: 'week', label: '本周更新' },
  { key: 'month', label: '30日内更新' },
  { key: '3month', label: '90日内更新' },
  { key: 'all', label: '全量采集' },
];

function CollectSourcesSection({
  apiKey,
  loading,
  setLoading,
  setError,
  setMessage,
}: {
  apiKey: string;
  loading: boolean;
  setLoading: (v: boolean) => void;
  setError: (v: string) => void;
  setMessage: (v: string) => void;
}) {
  const [collectSources, setCollectSources] = useState<CollectSource[]>([]);
  const [collectTasks, setCollectTasks] = useState<CollectTask[]>([]);
  const [timingTasks, setTimingTasks] = useState<CollectTimingTask[]>([]);
  const [showCollectTab, setShowCollectTab] = useState<'sources' | 'timing'>('sources');
  const [bindingSourceId, setBindingSourceId] = useState<string | null>(null);
  const [bindingRows, setBindingRows] = useState<Array<CollectTypeBinding & { enabled: boolean }>>([]);
  const [bindingLocalTypes, setBindingLocalTypes] = useState<Array<{ name: string; count: number }>>([]);
  const [bindingLoading, setBindingLoading] = useState(false);
  const [bindingRemoteError, setBindingRemoteError] = useState('');
  const [collectForm, setCollectForm] = useState({
    name: '',
    url: '',
    type: 'json' as 'json' | 'xml',
    appid: '',
    appkey: '',
    bind: false,
  });
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!apiKey) return;
    void loadCollectData();
  }, [apiKey]);

  async function loadCollectData() {
    try {
      const [sourcesRes, tasksRes, timingRes] = await Promise.all([
        getCollectSources(apiKey),
        getCollectTasks(apiKey),
        getCollectTimingTasks(apiKey),
      ]);
      setCollectSources(sourcesRes.data);
      setCollectTasks(tasksRes.data);
      setTimingTasks(timingRes.data);
    } catch {
      // silent
    }
  }

  async function handleCreateCollectSource() {
    setLoading(true);
    setError('');
    setMessage('');
    try {
      await createCollectSource(apiKey, collectForm);
      setCollectForm({ name: '', url: '', type: 'json', appid: '', appkey: '', bind: false });
      setMessage('采集源已添加');
      await loadCollectData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleCollectSource(source: CollectSource) {
    setLoading(true);
    setError('');
    try {
      await updateCollectSource(apiKey, source._id, { status: !source.status });
      setMessage(`已${source.status ? '停用' : '启用'} ${source.name}`);
      await loadCollectData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteCollectSource(source: CollectSource) {
    if (!window.confirm(`确认删除采集源「${source.name}」吗？`)) return;
    setLoading(true);
    setError('');
    try {
      await deleteCollectSource(apiKey, source._id);
      setMessage(`已删除 ${source.name}`);
      await loadCollectData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleTestCollectSource(sourceId: string) {
    setError('');
    setTestResults((prev) => ({ ...prev, [sourceId]: '测试中...' }));
    try {
      const result = await testCollectSource(apiKey, sourceId);
      setTestResults((prev) => ({
        ...prev,
        [sourceId]: result.ok ? `✅ ${result.message}` : `❌ ${result.message}`,
      }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [sourceId]: `❌ ${err instanceof Error ? err.message : '测试失败'}`,
      }));
    }
  }

  async function handleRunCollectSource(sourceId: string, range: string) {
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const result = await runCollectSource(apiKey, sourceId, range);
      setMessage(result.message);
      await loadCollectData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '采集失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleTimingTask(task: CollectTimingTask) {
    setLoading(true);
    setError('');
    try {
      await updateCollectTimingTask(apiKey, task.id, { status: task.status === 1 ? 0 : 1 });
      await loadCollectData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新定时任务失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRunTimingTask(task: CollectTimingTask) {
    if (!window.confirm(`确认立即执行「${task.des}」吗？这将为所有启用的采集源创建采集任务。`)) return;
    setLoading(true);
    setError('');
    try {
      const result = await runCollectTimingTask(apiKey, task.id);
      setMessage(result.message);
      await loadCollectData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '执行失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleOpenBindings(sourceId: string) {
    if (bindingSourceId === sourceId) {
      setBindingSourceId(null);
      setBindingRows([]);
      setBindingLocalTypes([]);
      setBindingRemoteError('');
      return;
    }

    setBindingSourceId(sourceId);
    setBindingLoading(true);
    setBindingRemoteError('');
    setError('');
    try {
      const result = await getCollectBindings(apiKey, sourceId);
      setBindingRows(
        result.bindings.map((row) => ({
          ...row,
          enabled: !!row.local_type,
          local_type: row.local_type || row.source_type_name || '',
        })),
      );
      setBindingLocalTypes(result.local_types || []);
      setBindingRemoteError(result.remote_type_error || '');
    } catch (err) {
      setBindingRows([]);
      setBindingLocalTypes([]);
      setBindingRemoteError('');
      setError(err instanceof Error ? err.message : '加载远程分类失败');
    } finally {
      setBindingLoading(false);
    }
  }

  function updateBindingRow(index: number, patch: Partial<CollectTypeBinding & { enabled: boolean }>) {
    setBindingRows((current) => current.map((row, rowIndex) => {
      if (rowIndex !== index) return row;
      return { ...row, ...patch };
    }));
  }

  async function handleSaveBindings(sourceId: string) {
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const selected = bindingRows
        .filter((row) => row.enabled)
        .map((row) => ({
          sourceTypeId: row.source_type_id,
          sourceTypeName: row.source_type_name,
          localType: row.local_type?.trim() || row.source_type_name,
        }));
      await saveCollectBindings(apiKey, sourceId, selected);
      setMessage(`已保存远程分类，共 ${selected.length} 个`);
      await loadCollectData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存远程分类失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
      <div className="mb-5">
        <h2 className="text-2xl font-semibold text-parchment">📡 资源站采集源管理</h2>
        <p className="mt-2 text-sm text-parchment/70">对接支持 JSON/XML 格式的资源站 API，按时间范围采集动画数据。</p>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-2">
        <button
          type="button"
          onClick={() => setShowCollectTab('sources')}
          className={`rounded-full px-5 py-2 text-sm font-medium transition ${
            showCollectTab === 'sources'
              ? 'bg-ember text-black'
              : 'border border-white/10 text-parchment/60 hover:text-parchment'
          }`}
        >
          采集源 ({collectSources.length})
        </button>
        <button
          type="button"
          onClick={() => setShowCollectTab('timing')}
          className={`rounded-full px-5 py-2 text-sm font-medium transition ${
            showCollectTab === 'timing'
              ? 'bg-ember text-black'
              : 'border border-white/10 text-parchment/60 hover:text-parchment'
          }`}
        >
          定时任务 ({timingTasks.filter((t) => t.status === 1).length}/{timingTasks.length})
        </button>
      </div>

      {showCollectTab === 'sources' ? (
        <>
          {/* 添加采集源 */}
          <div className="mb-6 rounded-[24px] border border-ember/20 bg-black/20 p-5">
            <div className="mb-4 text-sm font-medium text-parchment">添加采集源</div>
            <div className="grid gap-4 md:grid-cols-3">
              <TextField label="名称" value={collectForm.name} onChange={(v) => setCollectForm((p) => ({ ...p, name: v }))} />
              <TextField label="接口地址" value={collectForm.url} onChange={(v) => setCollectForm((p) => ({ ...p, url: v }))} />
              <label className="block">
                <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">类型</div>
                <select
                  value={collectForm.type}
                  onChange={(e) => setCollectForm((p) => ({ ...p, type: e.target.value as 'json' | 'xml' }))}
                  className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none"
                >
                  <option value="json">JSON</option>
                  <option value="xml">XML</option>
                </select>
              </label>
              <TextField label="App ID(可选)" value={collectForm.appid} onChange={(v) => setCollectForm((p) => ({ ...p, appid: v }))} />
              <TextField label="App Key(可选)" value={collectForm.appkey} onChange={(v) => setCollectForm((p) => ({ ...p, appkey: v }))} />
              <ToggleField label="启用采集" checked={true} onChange={() => {}} />
            </div>
            <button
              type="button"
              onClick={handleCreateCollectSource}
              disabled={loading || !collectForm.name || !collectForm.url}
              className="mt-4 rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110 disabled:opacity-40"
            >
              添加采集源
            </button>
          </div>

          {/* 采集源列表 */}
          <div className="space-y-4">
            {collectSources.map((source) => (
              <div key={source._id} className="rounded-[24px] border border-white/10 bg-black/20 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="truncate text-base font-medium text-parchment">{source.name}</h3>
                      <span className={`rounded-full px-2 py-0.5 text-xs ${source.status ? 'bg-emerald-400/20 text-emerald-300' : 'bg-rose-400/20 text-rose-300'}`}>
                        {source.status ? '启用' : '停用'}
                      </span>
                      <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-ash">{source.type.toUpperCase()}</span>
                    </div>
                    <p className="mt-1 truncate text-xs text-ash">{source.url}</p>
                    {source.last_collect ? (
                      <p className="mt-1 text-xs text-parchment/50">
                        上次采集: {new Date(source.last_collect).toLocaleString('zh-CN')} · 累计: {source.collect_num} 条
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-ash">尚未采集</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => handleTestCollectSource(source._id)}
                      className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-parchment/60 transition hover:border-white/20 hover:text-parchment"
                    >
                      测试连接
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOpenBindings(source._id)}
                      className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-parchment/60 transition hover:border-white/20 hover:text-parchment"
                    >
                      {bindingSourceId === source._id ? '收起分类' : '远程分类'}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleCollectSource(source)}
                      className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-parchment/60 transition hover:border-white/20 hover:text-parchment"
                    >
                      {source.status ? '停用' : '启用'}
                    </button>
                    <select
                      defaultValue=""
                      onChange={(e) => {
                        if (e.target.value) handleRunCollectSource(source._id, e.target.value);
                        e.target.value = '';
                      }}
                      className="rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-xs text-parchment/60 outline-none"
                    >
                      <option value="">手动采集 ▾</option>
                      {COLLECT_RANGE_OPTIONS.map((opt) => (
                        <option key={opt.key} value={opt.key}>{opt.label}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => handleDeleteCollectSource(source)}
                      className="rounded-full border border-rose-400/30 bg-rose-400/10 px-3 py-1.5 text-xs text-rose-200 transition hover:bg-rose-400/20"
                    >
                      删除
                    </button>
                  </div>
                </div>
                {testResults[source._id] ? (
                  <p className="mt-3 text-xs text-parchment/60">{testResults[source._id]}</p>
                ) : null}
                {bindingSourceId === source._id ? (
                  <div className="mt-4 rounded-[20px] border border-ember/15 bg-black/25 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-parchment">远程分类采集选择</div>
                        <p className="mt-1 text-xs leading-6 text-parchment/60">
                          只有勾选的远程分类会参与采集，右侧填写或确认入库分类名。留空时会默认使用远程分类名。
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleSaveBindings(source._id)}
                        disabled={loading || bindingLoading}
                        className="rounded-full bg-ember px-4 py-2 text-xs font-semibold text-black transition hover:brightness-110 disabled:opacity-50"
                      >
                        保存分类选择
                      </button>
                    </div>
                    {bindingRemoteError ? (
                      <p className="mt-3 text-xs text-amber-300">远程分类获取异常：{bindingRemoteError}</p>
                    ) : null}
                    {bindingLoading ? (
                      <p className="mt-3 text-xs text-ash">正在加载远程分类...</p>
                    ) : null}
                    {!bindingLoading && bindingRows.length > 0 ? (
                      <div className="mt-4 space-y-3">
                        {bindingRows.map((row, index) => (
                          <div key={row.source_type_id} className="grid gap-3 rounded-2xl border border-white/8 bg-black/25 p-3 md:grid-cols-[minmax(0,220px)_minmax(0,1fr)]">
                            <label className="flex items-center gap-3">
                              <input
                                type="checkbox"
                                checked={row.enabled}
                                onChange={(event) => updateBindingRow(index, {
                                  enabled: event.target.checked,
                                  local_type: event.target.checked
                                    ? (row.local_type || row.source_type_name)
                                    : row.local_type,
                                })}
                                className="h-4 w-4 rounded border-white/20 bg-transparent"
                              />
                              <div>
                                <div className="text-sm text-parchment">{row.source_type_name || `分类 ${row.source_type_id}`}</div>
                                <div className="text-xs text-ash">远程 ID: {row.source_type_id}</div>
                              </div>
                            </label>
                            <label className="block">
                              <div className="mb-2 text-[11px] uppercase tracking-[0.24em] text-ash">入库分类名</div>
                              <input
                                list="collect-local-type-options"
                                value={row.local_type || ''}
                                onChange={(event) => updateBindingRow(index, { local_type: event.target.value })}
                                disabled={!row.enabled}
                                placeholder={row.source_type_name || '输入分类名'}
                                className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-parchment outline-none transition focus:border-ember/60 disabled:cursor-not-allowed disabled:opacity-40"
                              />
                            </label>
                          </div>
                        ))}
                        <datalist id="collect-local-type-options">
                          {bindingLocalTypes.map((item) => (
                            <option key={item.name} value={item.name}>
                              {item.name} ({item.count})
                            </option>
                          ))}
                        </datalist>
                      </div>
                    ) : null}
                    {!bindingLoading && !bindingRows.length ? (
                      <p className="mt-3 text-xs text-ash">当前没有可配置的远程分类。</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))}
            {!collectSources.length ? <div className="text-sm text-ash">暂无采集源，请添加 JSON/XML 资源站接口地址。</div> : null}
          </div>

          {/* 最近任务列表 */}
          {collectTasks.length > 0 ? (
            <div className="mt-8">
              <h3 className="mb-4 text-sm font-medium text-parchment/70">最近采集任务</h3>
              <div className="space-y-2">
                {collectTasks.slice(0, 10).map((task) => (
                  <div key={task._id} className="flex items-center justify-between rounded-xl border border-white/5 bg-black/20 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <span className="text-sm text-parchment">{task.source_name || task.collect_source}</span>
                      <span className="ml-2 text-xs text-ash">· {task.range}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs ${task.status === 'success' ? 'text-emerald-300' : task.status === 'failed' ? 'text-rose-300' : task.status === 'running' ? 'text-amber-300' : 'text-ash'}`}>
                        {task.status === 'success' ? `完成 (新${task.created} 更${task.updated})` : task.status === 'failed' ? '失败' : task.status === 'running' ? '运行中' : '等待中'}
                      </span>
                      <span className="text-xs text-ash">{task.message}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : (
        /* 定时任务管理 */
        <div className="space-y-4">
          <p className="text-sm text-parchment/60">配置采集定时任务，系统会按设定的周几和小时自动触发采集。支持立即手动执行。</p>
          {timingTasks.map((task) => (
            <div key={task.id} className="flex flex-wrap items-center justify-between gap-3 rounded-[24px] border border-white/10 bg-black/20 p-5">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3">
                  <h3 className="text-base font-medium text-parchment">{task.des}</h3>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${task.status === 1 ? 'bg-emerald-400/20 text-emerald-300' : 'bg-rose-400/20 text-rose-300'}`}>
                    {task.status === 1 ? '启用' : '停用'}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-ash">范围: {task.param.type}</span>
                </div>
                {task.status === 1 && task.weeks && task.hours ? (
                  <p className="mt-1 text-xs text-ash">
                    周期: {task.weeks} · 时刻: {task.hours}
                    {task.runtime ? ` · 上次: ${new Date(task.runtime).toLocaleString('zh-CN')}` : ''}
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-ash">手动触发模式（无自动调度）</p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleToggleTimingTask(task)}
                  className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-parchment/60 transition hover:border-white/20 hover:text-parchment"
                >
                  {task.status === 1 ? '停用' : '启用'}
                </button>
                <button
                  type="button"
                  onClick={() => handleRunTimingTask(task)}
                  className="rounded-full bg-ember px-4 py-1.5 text-xs font-semibold text-black transition hover:brightness-110"
                >
                  立即执行
                </button>
              </div>
            </div>
          ))}
          {!timingTasks.length ? <div className="text-sm text-ash">暂无定时任务配置。</div> : null}
        </div>
      )}
    </section>
  );
}

function Card({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card">
      <div className="text-xs uppercase tracking-[0.24em] text-ash">{label}</div>
      <div className="mt-4 text-4xl font-semibold text-parchment">{children}</div>
    </div>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">{label}</div>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition focus:border-ember/60"
      />
    </label>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="block">
      <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">{label}</div>
      <input
        type="number"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition focus:border-ember/60"
      />
    </label>
  );
}

function TextAreaField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">{label}</div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition focus:border-ember/60"
      />
    </label>
  );
}

function ToggleField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
      <span className="text-sm text-parchment/80">{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 accent-[#c96b2c]" />
    </label>
  );
}

function splitLines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}
